#!/bin/sh
# Mirrors each patient flag into a patient list of the same name.
#
# A cohort list holds static membership: nothing in the cohort module recomputes it, so
# a list only matches its flag if something keeps the two in step. This reads the flags
# the module has already evaluated, so the list and the patient chart always agree, and
# a list is never fresher than the sweep that produced it.
#
# Removal end-dates the membership instead of deleting it. A deleted membership is voided,
# and the module still counts a voided row when it rejects a duplicate, so a patient who
# left a list could never rejoin it. An end-dated row can be superseded.
#
# Membership is written over REST. The add and remove sets are computed in SQL because
# the flag to patients direction is not exposed over REST at all, so the database read
# is required regardless, and using it for the diff avoids parsing JSON in the shell.
set -eu

BASE="${OMRS_BASE_URL:-http://backend:8080/openmrs}"
USER="${OMRS_FLAG_ADMIN_USER:-admin}"
PASS="${OMRS_FLAG_ADMIN_PASSWORD:-Admin123}"
DB_HOST="${OMRS_DB_HOST:-db}"
DB_NAME="${OMRS_DB_NAME:-openmrs}"
DB_USER="${OMRS_DB_USER:-openmrs}"
DB_PASS="${OMRS_DB_PASSWORD:-openmrs}"
COHORT_TYPE="${OMRS_LIST_COHORT_TYPE:-eee9970e-7ca0-4e8c-a280-c33e9d5f6a04}"
# Only flags carrying this tag get a list. Empty means every enabled flag.
TAG="${OMRS_LIST_FLAG_TAG:-}"
REST="$BASE/ws/rest/v1"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) sync-flag-lists: $*"; }
sql() { mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -N -B -e "$1"; }
api() { curl -sf -u "$USER:$PASS" -H 'Content-Type: application/json' "$@"; }

tag_clause=""
if [ -n "$TAG" ]; then
  tag_clause="AND EXISTS ( SELECT 1 FROM patientflags_flag_tag ft
     JOIN patientflags_tag t ON t.tag_id = ft.tag_id
     WHERE ft.flag_id = f.flag_id AND t.name = '$TAG' )"
fi

# A flag name can contain anything, so pass it to the API as JSON built by the shell only
# after stripping the quote characters that would break the document.
sql "SELECT f.uuid, REPLACE(REPLACE(f.name, '\\\\', ''), '\"', '') FROM patientflags_flag f
     WHERE f.enabled = 1 AND f.retired = 0 $tag_clause ORDER BY f.name;" \
| while IFS="$(printf '\t')" read -r flag_uuid flag_name; do
  [ -n "$flag_uuid" ] || continue

  cohort_uuid=$(sql "SELECT uuid FROM cohort WHERE name = '$flag_name' AND voided = 0 LIMIT 1;")
  if [ -z "$cohort_uuid" ]; then
    cohort_uuid=$(api -X POST -d "{\"name\":\"$flag_name\",\"description\":\"Patients currently flagged: $flag_name\",\"cohortType\":\"$COHORT_TYPE\"}" \
      "$REST/cohortm/cohort" | grep -o '"uuid":"[^"]*"' | head -1 | cut -d'"' -f4)
    [ -n "$cohort_uuid" ] || { log "could not create list for '$flag_name'"; continue; }
    log "created list '$flag_name'"
  fi

  added=0
  for patient in $(sql "SELECT p.uuid FROM patientflags_patient_flag pf
      JOIN patientflags_flag f ON f.flag_id = pf.flag_id
      JOIN person p ON p.person_id = pf.patient_id
      WHERE f.uuid = '$flag_uuid' AND NOT EXISTS (
        SELECT 1 FROM cohort_member cm JOIN cohort c ON c.cohort_id = cm.cohort_id
        WHERE c.uuid = '$cohort_uuid' AND cm.patient_id = pf.patient_id
          AND cm.voided = 0 AND ( cm.end_date IS NULL OR cm.end_date > NOW() ) );"); do
    api -X POST -d "{\"patient\":\"$patient\",\"cohort\":\"$cohort_uuid\",\"startDate\":\"$(date -u +%Y-%m-%d)\"}" \
      -o /dev/null "$REST/cohortm/cohortmember" && added=$((added + 1)) || log "add failed: $patient"
  done

  removed=0
  for membership in $(sql "SELECT cm.uuid FROM cohort_member cm
      JOIN cohort c ON c.cohort_id = cm.cohort_id
      WHERE c.uuid = '$cohort_uuid' AND cm.voided = 0
        AND ( cm.end_date IS NULL OR cm.end_date > NOW() )
        AND NOT EXISTS (
          SELECT 1 FROM patientflags_patient_flag pf JOIN patientflags_flag f ON f.flag_id = pf.flag_id
          WHERE f.uuid = '$flag_uuid' AND pf.patient_id = cm.patient_id );"); do
    api -X POST -d "{\"endDate\":\"$(date -u +%Y-%m-%d)\"}" -o /dev/null \
      "$REST/cohortm/cohortmember/$membership" && removed=$((removed + 1)) || log "remove failed: $membership"
  done

  log "'$flag_name': +$added -$removed"
done
