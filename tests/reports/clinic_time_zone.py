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
import subprocess
import sys
from zoneinfo import ZoneInfo

from dashboard_totals import REGISTRY, Stack, consultation, enrol, registrant


def report_day(value):
    if isinstance(value, list):
        return datetime.date(*value[:3]).isoformat()
    return str(value)[:10] if value else None


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
    if returned != f'{yesterday.isoformat()}T00:30:00.000{offset}':
        failures.append(f'REST encounterDatetime: expected {yesterday}T00:30:00.000{offset}, got {returned}')

    rows = stack.rows(REGISTRY, startDate='1900-01-01', endDate=today.isoformat())
    row = next((row for row in rows if row.get('patient_uuid') == patient), None)
    if row is None:
        failures.append('the RHD Patient List does not list the test patient')
    elif report_day(row.get('last_consultation_date')) != yesterday.isoformat():
        failures.append(f"RHD Patient List last_consultation_date: expected {yesterday}, "
                        f"got {report_day(row.get('last_consultation_date'))}")

    if args.db_container:
        query = 'SELECT TIMESTAMPDIFF(MINUTE, UTC_TIMESTAMP(), NOW())'
        minutes = subprocess.run(['docker', 'exec', args.db_container, 'mysql', '-N', '-uopenmrs', '-popenmrs',
                                  'openmrs', '-e', query], capture_output=True, text=True, check=True).stdout.strip()
        expected = round(datetime.datetime.now(zone).utcoffset().total_seconds() / 60)
        if abs(int(minutes) - expected) > 1:
            failures.append(f'database NOW() is UTC{int(minutes):+d} minutes, expected {expected:+d}')

    if failures:
        sys.exit('FAIL\n' + '\n'.join(failures))
    print(f'OK: a consultation at 00:30 on {yesterday} in {args.zone} is stored and reported on {yesterday}')


if __name__ == '__main__':
    main()
