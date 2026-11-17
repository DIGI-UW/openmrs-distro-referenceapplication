#!/usr/bin/env python3
"""
Checks that a running ACT stack keeps the clinics' clock, so the days it stores and reports are the clinics' days.

It saves a consultation at 00:30 yesterday in the clinics' time zone, which is still the day before in UTC, then asserts
that the REST API returns that time with the zone's offset and that the RHD Patient List gives it as yesterday's last
consultation date. With --db-container it also asserts that the database's NOW() runs at the zone's offset.

Usage: python3 tests/reports/clinic_time_zone.py [--base http://localhost/openmrs] [--user admin] [--password ...]
       [--zone Africa/Kampala] [--db-container <name>]
The seeded patient and clinic are left on the stack; run it against a test stack only.
"""
import argparse
import datetime
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

from dashboard_totals import REGISTRY, Stack, consultation, enrol, registrant


def report_day(value):
    if isinstance(value, list):
        return datetime.date(*value[:3]).isoformat()
    return str(value)[:10] if value else None


def same_wall_clock(returned, expected):
    """Whether a REST datetime is the expected time at the expected offset, in whichever ISO form the server writes.
    The offset is compared too: a server on UTC returns 21:30+0000, the same instant as 00:30+0300."""
    try:
        parsed = datetime.datetime.fromisoformat(re.sub(r'([+-]\d\d)(\d\d)$', r'\1:\2', returned))
    except (TypeError, ValueError):
        return False
    return parsed == expected and parsed.utcoffset() == expected.utcoffset()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://localhost/openmrs')
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default='Admin123')
    parser.add_argument('--zone', default='Africa/Kampala')
    parser.add_argument('--db-container')
    args = parser.parse_args()
    stack = Stack(args.base, args.user, args.password)
    zone = ZoneInfo(args.zone)

    today = datetime.datetime.now(zone).date()
    yesterday = today - datetime.timedelta(days=1)
    seen = datetime.datetime.combine(yesterday, datetime.time(0, 30), tzinfo=zone)
    offset = seen.strftime('%z')
    stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    failures = []

    clinic = stack.call('POST', '/location', {'name': f'Time Zone Test Clinic {stamp}'})['uuid']
    patient = registrant(stack, clinic, f'{stamp} time zone', birthdate='2005-04-01')
    enrol(stack, patient, (today - datetime.timedelta(days=30)).isoformat())
    encounter = consultation(stack, patient, clinic, seen.isoformat(), [])

    returned = stack.call('GET', f'/encounter/{encounter}?v=custom:(encounterDatetime)')['encounterDatetime']
    if not same_wall_clock(returned, seen):
        failures.append(f'REST encounterDatetime: expected {yesterday}T00:30 at {offset}, got {returned}')

    rows = stack.rows(REGISTRY, startDate='1900-01-01', endDate=today.isoformat())
    row = next((row for row in rows if row.get('patient_uuid') == patient), None)
    if row is None:
        failures.append('the RHD Patient List does not list the test patient')
    elif report_day(row.get('last_consultation_date')) != yesterday.isoformat():
        failures.append(f"RHD Patient List last_consultation_date: expected {yesterday}, "
                        f"got {report_day(row.get('last_consultation_date'))}")

    if args.db_container:
        query = 'SELECT TIMESTAMPDIFF(MINUTE, UTC_TIMESTAMP(), NOW())'
        mysql = 'mysql -N -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "$1"'
        expected = round(datetime.datetime.now(zone).utcoffset().total_seconds() / 60)
        try:
            result = subprocess.run(['docker', 'exec', args.db_container, 'sh', '-c', mysql, 'sh', query],
                                    capture_output=True, text=True)
            minutes = int(result.stdout.strip())
        except (OSError, ValueError) as error:
            detail = (result.stderr or result.stdout).strip() if isinstance(error, ValueError) else str(error)
            failures.append(f'database NOW() could not be read from {args.db_container}: {detail or "no output"}')
        else:
            if abs(minutes - expected) > 1:
                failures.append(f'database NOW() is UTC{minutes:+d} minutes, expected {expected:+d}')

    if failures:
        sys.exit('FAIL\n' + '\n'.join(failures))
    print(f'OK: a consultation at 00:30 on {yesterday} in {args.zone} is stored and reported on {yesterday}')


if __name__ == '__main__':
    main()
