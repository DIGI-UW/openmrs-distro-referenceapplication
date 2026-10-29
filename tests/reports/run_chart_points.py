#!/usr/bin/env python3
"""
Checks the run chart report, which gives every point of a range in one pass, against its single-date form and against
ACT Core's run chart endpoint, on a running ACT stack.

For daily, weekly and monthly ranges it asserts that the one-pass report's point dates are the rule's (the end, then a
day back, the Sunday before, or the last day of the month before, while not before the start); that for every point and
every clinic row, and the all-clinics row, its eight counts equal RHD Run Chart Metrics (as of a date) evaluated for that
day, number for number, and that the patients it lists in bpg_patient_ids are as many as that report counts on BPG; and
that GET /actcore/runchart answers each metric's points from those figures, with the adherent count at today's point
equal to the as-of report's figure from ACT Core's adherence rows once they are refreshed. It prints how long ACT Core
takes to answer a year of weekly points and two years of monthly points.

Usage: python3 tests/reports/run_chart_points.py [--base http://localhost/openmrs] [--user admin] [--password ...]
It writes nothing but the adherence refresh; run it against a test stack.
"""
import argparse
import base64
import datetime
import json
import math
import sys
import time
import urllib.parse
import urllib.request

ONE_PASS = 'ba3371da-3c6c-4fb2-bf47-0c3fcfe9dce1'
AS_OF = '4f2c9d8e-1b7a-4e36-9c05-7d3a8b2e6f41'
COUNTS = ['total_registrants', 'active_registrants', 'active_registrants_seen_last_7_months',
          'active_registrants_prescribed_prophylaxis', 'consultation_visit_total',
          'consultation_visits_with_echocardiogram_resulted', 'consultation_visits_with_intervention',
          'interventions_completed']
PERCENT_OF = {'active_registrants_seen_last_7_months': 'active_registrants',
              'active_registrants_prescribed_prophylaxis': 'active_registrants',
              'active_registrants_adherent': 'active_registrants',
              'consultation_visits_with_echocardiogram_resulted': 'consultation_visit_total',
              'consultation_visits_with_intervention': 'consultation_visit_total'}
# The eight charted metrics: the counts less consultation_visit_total, which is only a denominator, plus adherent
METRICS = [c for c in COUNTS if c != 'consultation_visit_total']
METRICS.insert(4, 'active_registrants_adherent')


class Stack:
    def __init__(self, base, user, password):
        self.base = base.rstrip('/') + '/ws/rest/v1'
        self.auth = 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()

    def call(self, method, path, body=None):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={'Authorization': self.auth, 'Content-Type': 'application/json'},
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return json.loads(response.read() or b'{}')
        except urllib.error.HTTPError as error:
            sys.exit(f'{method} {path} answered {error.code}: {error.read().decode()[:600]}')

    def rows(self, report, **params):
        query = urllib.parse.urlencode(params)
        return self.call('GET', f'/reportingrest/reportdata/{report}?{query}')['dataSets'][0]['rows']


failures = []


def check(what, actual, expected):
    if actual != expected:
        failures.append(f'{what}: expected {expected!r}, got {actual!r}')


def day_of(value):
    """A date as the report answers it: an ISO string, or milliseconds since the epoch."""
    if isinstance(value, (int, float)):
        return datetime.datetime.fromtimestamp(value / 1000).date().isoformat()
    return str(value)[:10]


def point_dates(start, end, points):
    """The rule ACT Core and the SQL share, earliest first."""
    dates = []
    day = end
    while day >= start:
        dates.insert(0, day)
        if points == 'day':
            day = day - datetime.timedelta(days=1)
        elif points == 'week':
            day = day - datetime.timedelta(days=day.isoweekday())
        else:
            first = day.replace(day=1)
            day = first - datetime.timedelta(days=1)
    return dates


def ids_of(listed):
    return [] if not listed else [int(x) for x in str(listed).split(',') if x.strip()]


def percent(numerator, denominator):
    """ACT Core's rounding: Math.round, which rounds a half up, to one decimal; None of nobody."""
    return None if denominator == 0 else math.floor(1000 * numerator / denominator + 0.5) / 10


def check_range(stack, start, end, points):
    label = f'{points} {start}..{end}'
    rows = stack.rows(ONE_PASS, startDate=start.isoformat(), endDate=end.isoformat(), points=points)
    by_date = {}
    for row in rows:
        by_date.setdefault(day_of(row['point_date']), {})[row['clinic_uuid']] = row
    expected = [d.isoformat() for d in point_dates(start, end, points)]
    check(f'{label}: point dates', sorted(by_date), [d for d in expected if d in by_date])
    for day in expected:
        as_of = {row['clinic_uuid']: row for row in stack.rows(AS_OF, endDate=day)}
        clinics = by_date.get(day)
        if clinics is None:
            # No row for the day means nobody was registered by it, which the as-of report says with a row of zeros
            check(f'{label} {day}: nobody registered', int(as_of[None]['total_registrants']), 0)
            continue
        check(f'{label} {day}: clinics', sorted(clinics, key=str), sorted(as_of, key=str))
        for clinic, row in clinics.items():
            reference = as_of.get(clinic)
            if reference is None:
                continue
            for column in COUNTS:
                check(f'{label} {day} {clinic or "all clinics"} {column}', int(row[column]), int(reference[column]))
            check(f'{label} {day} {clinic or "all clinics"} active_registrants_on_bpg', int(row['active_registrants_on_bpg']),
                  int(reference['active_registrants_on_bpg']))
            check(f'{label} {day} {clinic or "all clinics"} bpg_patient_ids', len(ids_of(row['bpg_patient_ids'])),
                  int(row['active_registrants_on_bpg']))
    return by_date


def check_endpoint(stack, start, end, points, by_date):
    label = f'{points} {start}..{end}'
    query = urllib.parse.urlencode({'startDate': start.isoformat(), 'endDate': end.isoformat(), 'points': points})
    started = time.monotonic()
    answer = stack.call('GET', f'/actcore/runchart?{query}')
    elapsed = time.monotonic() - started
    print(f'{label}: ACT Core answered {len(point_dates(start, end, points))} points of every metric in {elapsed:.2f}s')
    check(f'{label}: period', answer['period'], points)
    expected = [d.isoformat() for d in point_dates(start, end, points)]
    for metric in METRICS:
        series = answer['metrics'][metric]['points']
        check(f'{label} {metric}: point dates', [p['date'] for p in series], expected)
        for point in series:
            row = by_date.get(point['date'], {}).get(None)
            if metric == 'active_registrants_adherent':
                numerator = None
            else:
                numerator = int(row[metric]) if row else 0
            denominator = PERCENT_OF.get(metric)
            if denominator is None:
                if numerator is not None:
                    check(f'{label} {metric} {point["date"]}', (point['value'], point['count'], point['total']),
                          (float(numerator), numerator, None))
            else:
                total = int(row[denominator]) if row else 0
                if numerator is not None:
                    value = percent(numerator, total)
                    check(f'{label} {metric} {point["date"]}', (point['value'], point['count'], point['total']),
                          (value, numerator, total))
                else:
                    check(f'{label} {metric} {point["date"]} total', point['total'], total)
                    if row:
                        check(f'{label} {metric} {point["date"]} adherent within the BPG count',
                              point['count'] <= int(row['active_registrants_on_bpg']), True)
                    else:
                        check(f'{label} {metric} {point["date"]} adherent of nobody', point['count'], 0)
    return answer


def check_adherent_today(stack, answer, today):
    """ACT Core's rows, once refreshed, hold today's replay, so the as-of report's adherent figure is today's point."""
    stack.call('POST', '/actcore/refresh', {})
    reference = {row['clinic_uuid']: row for row in stack.rows(AS_OF, endDate=today.isoformat())}[None]
    last = answer['metrics']['active_registrants_adherent']['points'][-1]
    check('adherent today', (last['date'], last['count']), (today.isoformat(), int(reference['active_registrants_adherent'])))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://localhost/openmrs')
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default='Admin123')
    args = parser.parse_args()
    stack = Stack(args.base, args.user, args.password)
    today = datetime.date.today()
    days = lambda n: today - datetime.timedelta(days=n)

    check('rule: a Sunday end is not repeated', point_dates(datetime.date(2026, 10, 1), datetime.date(2026, 10, 18), 'week'),
          [datetime.date(2026, 10, 4), datetime.date(2026, 10, 11), datetime.date(2026, 10, 18)])
    check('rule: a month end steps to the shorter month', point_dates(datetime.date(2026, 1, 31), datetime.date(2026, 3, 31), 'month'),
          [datetime.date(2026, 1, 31), datetime.date(2026, 2, 28), datetime.date(2026, 3, 31)])

    ranges = [(days(20), today, 'day'), (days(365), today, 'week'), (days(730), today, 'month'),
              (days(28 + today.isoweekday()), days(today.isoweekday()), 'week'),
              ((today.replace(day=1) - datetime.timedelta(days=100)).replace(day=1), today.replace(day=1) - datetime.timedelta(days=1), 'month')]
    answers = {}
    for start, end, points in ranges:
        by_date = check_range(stack, start, end, points)
        answers[(start, end, points)] = check_endpoint(stack, start, end, points, by_date)
    check_adherent_today(stack, answers[(days(365), today, 'week')], today)

    if failures:
        print(f'{len(failures)} failures:')
        for failure in failures[:80]:
            print(' ', failure)
        sys.exit(1)
    print('all run chart checks passed')


if __name__ == '__main__':
    main()
