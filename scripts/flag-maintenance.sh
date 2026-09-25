#!/bin/sh
# Keeps patient flags and the patient lists built from them current.
#
# Two steps, in order, because the lists are built from whatever the flags currently say:
# re-evaluate the flags, then mirror each one into its list. Running them apart would let
# a list describe a flag state that no longer exists.
set -eu

BASE="${OMRS_BASE_URL:-http://backend:8080/openmrs}"
INTERVAL="${OMRS_FLAG_REBUILD_INTERVAL:-86400}"
USER="${OMRS_FLAG_ADMIN_USER:-admin}"
PASS="${OMRS_FLAG_ADMIN_PASSWORD:-Admin123}"
HERE="$(dirname "$0")"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) flag-maintenance: $*"; }

until curl -sf -o /dev/null -u "$USER:$PASS" "$BASE/ws/rest/v1/session"; do
  log "waiting for $BASE"
  sleep 10
done
log "backend reachable, cycle every ${INTERVAL}s"

while true; do
  sh "$HERE/refresh-patient-flags.sh" || log "flag refresh failed"
  sh "$HERE/sync-flag-lists.sh" || log "list sync failed"
  sleep "$INTERVAL"
done
