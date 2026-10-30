#!/usr/bin/env python3
"""
Checks the run chart report, which gives every point of a range in one pass, against its single-date form and against
ACT Core's run chart endpoint, on a running ACT stack.

It first seeds a new test clinic with the cases where the one-pass SQL departs from the single-date form in structure,
its LEAD() windows and their tie-breaks, so that the comparison crosses them: a patient re-enrolled after an enrolment
ended in a terminal state, a patient whose diagnosis category changes from RHD to CHD between two points, a patient whose
regimen changes from BPG to oral penicillin between two points, and a patient with two consultations at one datetime, the
first with a completed recommendation and an RHD diagnosis, the second with an open one and a CHD diagnosis. It asserts
that clinic's rows at a weekly point before and one after the changes, figure by figure.

For daily, weekly and monthly ranges it asserts that the one-pass report's point dates are the rule's (the end, then a
day back, the Sunday before, or the last day of the month before, while not before the start); that for every point and
every clinic row, and the all-clinics row, its eight counts equal RHD Run Chart Metrics (as of a date) evaluated for that
day, number for number, and that the patients it lists in bpg_patient_ids are as many as that report counts on BPG; and
that GET /actcore/runchart answers each metric's points from those figures, with the adherent count at today's point
equal to the as-of report's figure from ACT Core's adherence rows once they are refreshed. It prints how long ACT Core
takes to answer a year of weekly points and two years of monthly points.

Usage: python3 tests/reports/run_chart_points.py [--base http://localhost/openmrs] [--user admin] [--password ...]
The seeded patients and clinic are left on the stack, and the adherence refresh runs; run it against a test stack only.
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
RHD_REGISTRY = '7d73e143-a550-5a9d-aecd-dd771add098d'
TERMINAL_STATE = '407a4a4d-bc47-51e2-aa48-32e9a8d5634f'
RHD_ID_TYPE = '240f85fa-46e1-540e-9234-2796c623f7ea'
RHD_ID_SOURCE = 'f1c4a7be-160e-5d9b-ae5a-345cb15186dc'
CARDIAC_CLINIC_ATTRIBUTE = 'fe261119-2911-5b36-be40-8f9827826987'
CONSULTATION_TYPE = 'c2503561-c00d-5460-8157-43d594472b4a'
CONSULTATION_FORM = '4b063fc7-996f-3001-8500-8940e201be8f'
DIAGNOSIS = '594b4495-36dc-52a6-9810-15a9e2e2dcb9'
DIAGNOSIS_CATEGORY = '1a5aa050-661d-5e89-95d7-c1eba476df22'
RHD = '4e529463-2036-5327-ad69-7cbd39df86a1'
CHD = '365e75bb-35bc-503f-b8db-53bea2528d1b'
REGIMEN = '668e0221-8b41-5669-9ad8-78e193d42494'
BPG_Q28 = '50be4b26-6c5b-5aaa-9254-3bfd313b4522'
ORAL_PENICILLIN_V = 'b9884219-358a-594b-94f5-f8a8863a25f3'
DATE_STARTED = '5bcc7d12-b279-5955-815c-090a1f392071'
RECOMMENDATION = 'ce93d393-1df5-587f-bf11-c373eac2ccf4'
PROCEDURE_TYPE = '3a576b80-744a-59ee-9515-d9fdca06f3d7'
SURGERY = 'aa5fefb0-cf61-5f36-82e6-31dbbdf3f616'
AORTIC_VALVE = 'cd9c582a-71f9-5441-97a8-6d50d7dc15c8'
URGENCY = '7b8eda07-34b6-55f2-ab6c-1b295f41918b'
URGENT = '33bf504a-15f2-5504-9bdc-ddded0b5eb00'
COMPLETED = '1632f8dc-195d-5d67-a52e-6c7a057cb536'
YES = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
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


def registrant(stack, clinic, suffix, *, birthdate):
    identifier = stack.call('POST', f'/idgen/identifiersource/{RHD_ID_SOURCE}/identifier', {})['identifier']
    patient = stack.call('POST', '/patient', {
        'person': {'names': [{'givenName': 'Run chart', 'familyName': f'Test {suffix}'}], 'gender': 'F',
                   'birthdate': birthdate, 'attributes': [{'attributeType': CARDIAC_CLINIC_ATTRIBUTE, 'value': clinic}]},
        'identifiers': [{'identifierType': RHD_ID_TYPE, 'identifier': identifier, 'location': clinic, 'preferred': True}],
    })
    return patient['uuid']


def enrol(stack, patient, enrolled, *, completed=None):
    """Dates the RHD Registry enrolment ACT Core opens on registration, and ends it in the terminal state when asked."""
    enrolments = stack.call('GET', f'/programenrollment?patient={patient}&v=custom:(uuid,program:(uuid))')['results']
    enrolment = next((e['uuid'] for e in enrolments if e['program']['uuid'] == RHD_REGISTRY), None)
    if not enrolment:
        sys.exit('ACT Core did not enrol the new patient in the RHD Registry on registration, as this test expects')
    stack.call('POST', f'/programenrollment/{enrolment}', {'dateEnrolled': enrolled})
    if completed:
        stack.call('POST', f'/programenrollment/{enrolment}',
                   {'states': [{'state': TERMINAL_STATE, 'startDate': completed}], 'dateCompleted': completed})


def consultation(stack, patient, clinic, when, obs):
    stack.call('POST', '/encounter', {'patient': patient, 'encounterType': CONSULTATION_TYPE, 'form': CONSULTATION_FORM,
                                      'location': clinic, 'encounterDatetime': when, 'obs': obs})


def diagnosis(category):
    return {'concept': DIAGNOSIS, 'groupMembers': [{'concept': DIAGNOSIS_CATEGORY, 'value': category}]}


def regimen(answer, started):
    return {'concept': REGIMEN, 'groupMembers': [{'concept': REGIMEN, 'value': answer}, {'concept': DATE_STARTED, 'value': started}]}


def recommendation(*members):
    return {'concept': RECOMMENDATION, 'groupMembers': [{'concept': PROCEDURE_TYPE, 'value': SURGERY},
                                                        {'concept': RECOMMENDATION, 'value': AORTIC_VALVE}, *members]}


def seed_window_cases(stack, today):
    """A new clinic whose patients' latest enrolment, diagnosis, regimen and consultation differ between the points."""
    day = lambda days: (today - datetime.timedelta(days=days)).isoformat()
    stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    clinic = stack.call('POST', '/location', {'name': f'Run Chart Test Clinic {stamp}'})['uuid']
    re_enrolled = registrant(stack, clinic, f'{stamp} re-enrolled', birthdate='2010-05-01')
    enrol(stack, re_enrolled, day(200), completed=day(120))
    stack.call('POST', '/programenrollment', {'patient': re_enrolled, 'program': RHD_REGISTRY, 'dateEnrolled': day(40)})
    rediagnosed = registrant(stack, clinic, f'{stamp} rediagnosed', birthdate='2010-05-01')
    enrol(stack, rediagnosed, day(200))
    consultation(stack, rediagnosed, clinic, day(150) + 'T10:00:00', [diagnosis(RHD), regimen(BPG_Q28, day(150))])
    consultation(stack, rediagnosed, clinic, day(60) + 'T10:00:00', [diagnosis(CHD)])
    switched = registrant(stack, clinic, f'{stamp} switched to oral', birthdate='2010-05-01')
    enrol(stack, switched, day(200))
    consultation(stack, switched, clinic, day(150) + 'T10:00:00', [diagnosis(RHD), regimen(BPG_Q28, day(150))])
    consultation(stack, switched, clinic, day(60) + 'T10:00:00', [regimen(ORAL_PENICILLIN_V, day(60))])
    same_day = registrant(stack, clinic, f'{stamp} two consultations one day', birthdate='2010-05-01')
    enrol(stack, same_day, day(200))
    consultation(stack, same_day, clinic, day(60) + 'T10:00:00',
                 [diagnosis(RHD), regimen(BPG_Q28, day(60)), recommendation({'concept': COMPLETED, 'value': YES})])
    consultation(stack, same_day, clinic, day(60) + 'T10:00:00',
                 [diagnosis(CHD), recommendation({'concept': URGENCY, 'value': URGENT})])
    return clinic


def check_window_cases(by_date, clinic, today):
    """The seeded clinic's row at the Sunday on or before 80 days ago, before its changes, and at the last Sunday, after.

    Before: re-enrolled is inactive, rediagnosed and switched are seen, on BPG and prescribed, and each has one visit.
    After: re-enrolled is active again, rediagnosed is CHD and switched oral, so one is prescribed and nobody is on BPG,
    and the same-day pair counts two visits with an intervention; the later consultation of the pair, with the open
    recommendation and the CHD diagnosis, is the latest, so nothing is completed and nobody is prescribed there.
    """
    sunday = lambda d: (d - datetime.timedelta(days=d.isoweekday() % 7)).isoformat()
    before, after = sunday(today - datetime.timedelta(days=80)), sunday(today)
    columns = COUNTS + ['active_registrants_on_bpg']
    expected = {before: [4, 3, 2, 2, 2, 0, 0, 0, 2], after: [4, 4, 3, 1, 6, 0, 2, 0, 0]}
    for point, figures in expected.items():
        row = by_date.get(point, {}).get(clinic)
        check(f'seeded clinic at {point}', row and [int(row[c]) for c in columns], figures)


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

    clinic = seed_window_cases(stack, today)
    ranges = [(days(20), today, 'day'), (days(365), today, 'week'), (days(730), today, 'month'),
              (days(28 + today.isoweekday()), days(today.isoweekday()), 'week'),
              ((today.replace(day=1) - datetime.timedelta(days=100)).replace(day=1), today.replace(day=1) - datetime.timedelta(days=1), 'month')]
    answers = {}
    for start, end, points in ranges:
        by_date = check_range(stack, start, end, points)
        answers[(start, end, points)] = check_endpoint(stack, start, end, points, by_date)
        if (start, end, points) == (days(365), today, 'week'):
            check_window_cases(by_date, clinic, today)
    check_adherent_today(stack, answers[(days(365), today, 'week')], today)

    if failures:
        print(f'{len(failures)} failures:')
        for failure in failures[:80]:
            print(' ', failure)
        sys.exit(1)
    print('all run chart checks passed')


if __name__ == '__main__':
    main()
