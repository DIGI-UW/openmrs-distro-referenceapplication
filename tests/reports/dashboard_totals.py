#!/usr/bin/env python3
"""
Checks the Dashboard's count reports against the lists they summarise, on a running ACT stack.

It seeds a new test clinic with three registrants (an enrolment ended in a terminal state, an active patient with no
birth date, and an active patient whose latest diagnosis is RHD with no details and who has one open and one completed
recommendation), then asserts the counts at that clinic and, for every clinic, that rhd_dashboard_registrants and
rhd_dashboard_waitlist total what the RHD Patient List and the Procedural Waiting List list.

Usage: python3 tests/reports/dashboard_totals.py [--base http://localhost/openmrs] [--user admin] [--password ...]
The seeded patients and clinic are left on the stack; run it against a test stack only.
"""
import argparse
import base64
import datetime
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter

REGISTRY = 'f1a2b3c4-d5e6-7890-abcd-ef1234567890'
WAITING_LIST = '5b0f1c2e-9d3a-4c1b-8f6e-2a7d9e4b3c10'
REGISTRANTS = '3b0a6c2e-8f41-5d7b-9e15-6a2c4d8f0b71'
WAITLIST = '9d4e2f7a-1c63-5b08-8a2d-4f6e1b9c3a52'

RHD_REGISTRY = '7d73e143-a550-5a9d-aecd-dd771add098d'
TERMINAL_STATE = '407a4a4d-bc47-51e2-aa48-32e9a8d5634f'
TERMINAL_STATE_CONCEPT = '6a5113cc-1ecc-5f83-bddd-6a74a79daf5a'
RHD_ID_TYPE = '240f85fa-46e1-540e-9234-2796c623f7ea'
RHD_ID_SOURCE = 'f1c4a7be-160e-5d9b-ae5a-345cb15186dc'
CARDIAC_CLINIC_ATTRIBUTE = 'fe261119-2911-5b36-be40-8f9827826987'
CONSULTATION_TYPE = 'c2503561-c00d-5460-8157-43d594472b4a'
CONSULTATION_FORM = '4b063fc7-996f-3001-8500-8940e201be8f'
DIAGNOSIS = '594b4495-36dc-52a6-9810-15a9e2e2dcb9'
DIAGNOSIS_CATEGORY = '1a5aa050-661d-5e89-95d7-c1eba476df22'
RHD = '4e529463-2036-5327-ad69-7cbd39df86a1'
RECOMMENDATION = 'ce93d393-1df5-587f-bf11-c373eac2ccf4'
URGENCY = '7b8eda07-34b6-55f2-ab6c-1b295f41918b'
URGENT = '33bf504a-15f2-5504-9bdc-ddded0b5eb00'
COMPLETED = '1632f8dc-195d-5d67-a52e-6c7a057cb536'
YES = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
AORTIC_VALVE = 'cd9c582a-71f9-5441-97a8-6d50d7dc15c8'
MITRAL_BALLOON = 'af9429ff-1b76-55f3-81ca-a9f775d93fb4'


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
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read() or b'{}')
        except urllib.error.HTTPError as error:
            sys.exit(f'{method} {path} answered {error.code}: {error.read().decode()[:600]}')

    def rows(self, report, **params):
        query = urllib.parse.urlencode(params)
        data_sets = self.call('GET', f'/reportingrest/reportdata/{report}?{query}')['dataSets']
        return data_sets[0]['rows']


failures = []


def check(what, actual, expected):
    if actual != expected:
        failures.append(f'{what}: expected {expected!r}, got {actual!r}')


def registrant(stack, clinic, suffix, *, birthdate, gender='F'):
    person = {'names': [{'givenName': 'Dashboard', 'familyName': f'Test {suffix}'}], 'gender': gender,
              'attributes': [{'attributeType': CARDIAC_CLINIC_ATTRIBUTE, 'value': clinic}]}
    if birthdate:
        person['birthdate'] = birthdate
    identifier = stack.call('POST', f'/idgen/identifiersource/{RHD_ID_SOURCE}/identifier', {})['identifier']
    patient = stack.call('POST', '/patient', {
        'person': person,
        'identifiers': [{'identifierType': RHD_ID_TYPE, 'identifier': identifier,
                         'location': clinic, 'preferred': True}],
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
    stack.call('POST', '/encounter', {'patient': patient, 'encounterType': CONSULTATION_TYPE,
                                      'form': CONSULTATION_FORM, 'location': clinic,
                                      'encounterDatetime': when, 'obs': obs})


def by(rows, breakdown, key='label', value='patients'):
    return {row[key]: int(row[value]) for row in rows if row['breakdown'] == breakdown}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://localhost/openmrs')
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default='Admin123')
    args = parser.parse_args()
    stack = Stack(args.base, args.user, args.password)

    today = datetime.date.today()
    day = lambda days: (today - datetime.timedelta(days=days)).isoformat()
    stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    clinic_name = f'Dashboard Test Clinic {stamp}'
    clinic = stack.call('POST', '/location', {'name': clinic_name})['uuid']
    # The report names a state by its English preferred name, whatever the user's locale.
    names = stack.call('GET', f'/concept/{TERMINAL_STATE_CONCEPT}?v=custom:(names:(name,locale,localePreferred))')['names']
    terminal_name = next(n['name'] for n in names if n['locale'] == 'en' and n['localePreferred'])

    ended = registrant(stack, clinic, f'{stamp} ended', birthdate='2010-05-01')
    enrol(stack, ended, day(400), completed=day(30))
    unknown_age = registrant(stack, clinic, f'{stamp} no birth date', birthdate=None, gender='M')
    enrol(stack, unknown_age, day(200))
    rhd = registrant(stack, clinic, f'{stamp} rhd', birthdate='1990-03-15')
    enrol(stack, rhd, day(300))
    consultation(stack, rhd, clinic, day(20) + 'T10:00:00', [
        {'concept': DIAGNOSIS, 'groupMembers': [{'concept': DIAGNOSIS_CATEGORY, 'value': RHD}]},
        {'concept': RECOMMENDATION, 'groupMembers': [{'concept': RECOMMENDATION, 'value': AORTIC_VALVE},
                                                     {'concept': URGENCY, 'value': URGENT}]},
        {'concept': RECOMMENDATION, 'groupMembers': [{'concept': RECOMMENDATION, 'value': MITRAL_BALLOON},
                                                     {'concept': COMPLETED, 'value': YES}]},
    ])

    end = today.isoformat()
    at_clinic = stack.rows(REGISTRANTS, endDate=end, cardiacClinic=clinic)
    check('status at the test clinic', by(at_clinic, 'status'), {'Active': 2, terminal_name: 1})
    check('age at the test clinic', by(at_clinic, 'age'), {'20-39': 1, 'Age unknown': 1})
    check('disease at the test clinic', by(at_clinic, 'disease'),
          {'RHD, details not recorded': 1, 'No diagnosis yet': 1})
    check('sex at the test clinic', by(at_clinic, 'sex'), {'Female': 1, 'Male': 1})

    waitlist = stack.rows(WAITLIST, endDate=end, cardiacClinic=clinic)
    check('registrants among the clinics listed', by(stack.rows(REGISTRANTS, endDate=end, clinics=clinic), 'status'),
          by(at_clinic, 'status'))
    check('waitlist among the clinics listed', stack.rows(WAITLIST, endDate=end, clinics=clinic), waitlist)
    open_rows = [row for row in waitlist if row['breakdown'] == 'open']
    check('open recommendations at the test clinic',
          [(row['procedure'], row['urgency'], int(row['patients']), int(row['recommendations'])) for row in open_rows],
          [('Aortic valve repair/replacement', '2: urgent (60 days/2 months)', 1, 1)])
    check('total waiting at the test clinic', by(waitlist, 'total', 'procedure', 'patients'), {'All': 1})
    check('performed at the test clinic', by(waitlist, 'performed', 'procedure', 'recommendations'),
          {'Mitral balloon valvuloplasty': 1, 'Other procedure': 0})

    registry = stack.rows(REGISTRY, startDate='1900-01-01', endDate=end)
    if not registry:
        failures.append('the RHD Patient List has no rows, so nothing was compared')
    waiting = stack.rows(WAITING_LIST)
    alive = lambda row: row['enrollment_status'] == 'Active' and not row.get('deceased')
    clinics = {None} | {row.get('cardiac_clinic') for row in registry if row.get('cardiac_clinic')}
    uuids = {}
    for name in clinics - {None}:
        found = stack.call('GET', f'/location?q={urllib.parse.quote(name)}&v=custom:(uuid,display)')['results']
        uuids[name] = next(location['uuid'] for location in found if location['display'] == name)
    for name in sorted(clinics, key=str):
        params = {'endDate': end, **({'cardiacClinic': uuids[name]} if name else {})}
        listed = [row for row in registry if not name or row.get('cardiac_clinic') == name]
        counts = stack.rows(REGISTRANTS, **params)
        status = by(counts, 'status')
        where = name or 'every clinic'
        check(f'registrants at {where}', sum(status.values()), len(listed))
        check(f'active at {where}', status.get('Active', 0), sum(1 for row in listed if alive(row)))
        for breakdown in ('sex', 'age', 'disease'):
            check(f'{breakdown} total at {where}', sum(by(counts, breakdown).values()), status.get('Active', 0))
        waiting_here = [row for row in waiting if not name or row.get('cardiac_clinic') == name]
        open_rows = [row for row in stack.rows(WAITLIST, **params) if row['breakdown'] == 'open']
        check(f'open recommendations at {where}', sum(int(row['recommendations']) for row in open_rows),
              len(waiting_here))
        check(f'patients waiting at {where}', by(stack.rows(WAITLIST, **params), 'total', 'procedure', 'patients'),
              {'All': len({row['patient_uuid'] for row in waiting_here})})

    if failures:
        print('\n'.join(failures))
        sys.exit(1)
    print(f'ok: {len(clinics)} clinic groupings compared, test clinic {clinic_name}')


if __name__ == '__main__':
    main()
