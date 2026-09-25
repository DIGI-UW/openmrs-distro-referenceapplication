#!/bin/sh
# Periodically re-evaluates every enabled patient flag.
#
# The patientflags module evaluates a flag when the flag definition is saved, and
# otherwise only through AOP advice on write operations. Three of the RHD flags are
# time-based, so a patient who becomes overdue while nobody writes to their record is
# never flagged. Saving a flag over REST re-evaluates it for all patients, so this
# re-saves each enabled flag with its own current value.
#
# The module's admin rebuild page cannot be driven from here: it is behind CSRFGuard,
# whose token is only issued to a browser session.
#
# Each sweep deletes and recreates every row, so a flag's date_created is the time of
# the last sweep rather than the time the patient first met the criteria. Anything that
# reports how long a flag has been raised is wrong by up to one interval, which is why
# this runs daily rather than hourly. Reconciling rows in place needs FlagEvaluator
# .evalCohort(flag, null) from a scheduled task, which is a module rather than a script.
set -eu

BASE="${OMRS_BASE_URL:-http://backend:8080/openmrs}"
INTERVAL="${OMRS_FLAG_REBUILD_INTERVAL:-86400}"
USER="${OMRS_FLAG_ADMIN_USER:-admin}"
PASS="${OMRS_FLAG_ADMIN_PASSWORD:-Admin123}"
REST="$BASE/ws/rest/v1"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) refresh-patient-flags: $*"; }

# Each flag arrives as {"uuid":"...","enabled":true,...}. Splitting on the brace puts one
# flag per line, so a disabled flag is dropped rather than being switched back on.
enabled_flag_uuids() {
  curl -sf -u "$USER:$PASS" "$REST/patientflags/flag?v=custom:(uuid,enabled)" \
    | tr '{' '\n' \
    | grep '"enabled":true' \
    | sed -n 's/.*"uuid":"\([^"]*\)".*/\1/p'
}

refresh_flag() {
  curl -sf -o /dev/null -u "$USER:$PASS" \
    -X POST -H 'Content-Type: application/json' -d '{"enabled":true}' \
    "$REST/patientflags/flag/$1"
}

until curl -sf -o /dev/null -u "$USER:$PASS" "$REST/session"; do
  log "waiting for $BASE"
  sleep 10
done
log "backend reachable, refreshing every ${INTERVAL}s"

while true; do
  ok=0
  failed=0
  for uuid in $(enabled_flag_uuids); do
    if refresh_flag "$uuid"; then
      ok=$((ok + 1))
    else
      failed=$((failed + 1))
      log "failed to refresh $uuid"
    fi
  done
  log "refreshed $ok flag(s), $failed failure(s)"
  sleep "$INTERVAL"
done
