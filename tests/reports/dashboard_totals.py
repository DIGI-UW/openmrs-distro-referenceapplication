#!/usr/bin/env python3
"""
Checks the Dashboard's count reports against the lists they summarise, on a running ACT stack.

It seeds a new test clinic with eight registrants (an enrolment ended in a terminal state, an active patient with no
birth date, a patient whose only recommendation is None, an active patient whose latest diagnosis is RHD with no details and who has one open recommendation and two
done on Procedures and Outcomes since, a patient whose surgery recommended 400 days ago is recorded done today and whose
diagnosis is RHD B with acute rheumatic fever, a patient whose balloon valvuloplasty was done the day after its consultation
400 days ago and whose consultation is then moved to that day, a patient with a surgery done and a balloon valvuloplasty
open whose enrolment then ended, and a patient registered
at 19 who is 20 now and whose Screen + changed from No to core's True), some with Patient Information encounters, then
asserts the counts at that clinic today and yesterday, and with a diagnosis category limiting the active registrants'
sex, age and disease (RHD, which two of them have, and congenital heart disease, which none has); and, for every clinic,
that rhd_dashboard_registrants, rhd_dashboard_waitlist and rhd_dashboard_screening total what the RHD Patient List and
the Procedural Waiting List list. A patient seeded at a second, primary-care-only location, screen-positive with RHD, counts
in the screening cascade and diagnoses for the clinics listed.

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
CASCADE = '9c6751ae-65fc-5f25-9aa6-8c65cb1dff68'
OPTIMISATION = '733a512c-3243-4e91-a44a-06a8e5384606'
REGISTRANT_PATIENTS = 'e8296d2d-def8-5f8e-ba2d-78c59859b9e3'
WAITLIST_PATIENTS = 'bc987343-8b70-5f95-84a8-d017cffa14da'
CASCADE_PATIENTS = '7c62fcfd-03b2-5d84-9cea-92a43b70ae76'
OPTIMISATION_PATIENTS = '45c646b2-f223-585e-963a-3c74fe883ae4'
SCREENING = '0f4b7c2d-6a1e-5d93-8b47-2c9e1f5a3d68'
SCREENING_CASCADE = '8b257a0c-7e96-5a01-9672-975cae3b0419'
SCREENING_DIAGNOSES = '6ddf6b36-2789-4733-8433-a877d54795cf'
PROGRAMME = 'c4a9e2d1-7b3f-4e58-9a16-2f0d8b5c7e31'
PATIENT_INFORMATION_TYPE = 'ffdc883f-f99f-496a-83f9-2c3c581e1af0'
SCREEN_POSITIVE = '82a5fbb5-038d-57b8-82d1-3fd0ac95673d'
CASE_DETECTED_BY = '955632a1-82f7-5b84-a341-de85f95588d1'
NO = '1066AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
SCHOOL_SCREENING = '5b7d5eb4-4c6a-52cb-95f3-ac5033708fc9'
CLINICAL_PRESENTATION = '28452410-f2a2-5ad7-9590-43e47df1d254'
# How the screening section names Case Detected By, by the answer's name as the registry prints it; any other is Other
DETECTION_BUCKETS = {'School health screening': 'School', 'Community-based screening': 'Community',
                     'Healthcare center screening': 'Health facility', 'Clinical presentation': 'Clinical presentation',
                     'Pregnancy/labor': 'Pregnancy / labor', 'Pregnancy / labor': 'Pregnancy / labor',
                     'Coincidental finding': 'Coincidental finding', 'Post-mortem': 'Post-mortem'}
# A patient with no answer: Not recorded when screen-positive, else never asked (AR-203)
UNANSWERED = ('Not recorded', 'Not screen-positive')

RHD_REGISTRY = '7d73e143-a550-5a9d-aecd-dd771add098d'
TERMINAL_STATE = '407a4a4d-bc47-51e2-aa48-32e9a8d5634f'
TERMINAL_STATE_CONCEPT = '6a5113cc-1ecc-5f83-bddd-6a74a79daf5a'
RHD_ID_TYPE = '240f85fa-46e1-540e-9234-2796c623f7ea'
RHD_ID_SOURCE = 'f1c4a7be-160e-5d9b-ae5a-345cb15186dc'
CARDIAC_CLINIC_ATTRIBUTE = 'fe261119-2911-5b36-be40-8f9827826987'
PRIMARY_CARE_CLINIC_ATTRIBUTE = '695f2990-236f-5d7c-b8aa-ddbdb22400f4'
CONSULTATION_TYPE = 'c2503561-c00d-5460-8157-43d594472b4a'
CONSULTATION_FORM = '4b063fc7-996f-3001-8500-8940e201be8f'
DIAGNOSIS = '594b4495-36dc-52a6-9810-15a9e2e2dcb9'
DIAGNOSIS_CATEGORY = '1a5aa050-661d-5e89-95d7-c1eba476df22'
RHD = '4e529463-2036-5327-ad69-7cbd39df86a1'
CONGENITAL = '365e75bb-35bc-503f-b8db-53bea2528d1b'
RECOMMENDATION = 'ce93d393-1df5-587f-bf11-c373eac2ccf4'
PROCEDURE_TYPE = '3a576b80-744a-59ee-9515-d9fdca06f3d7'
SURGERY = 'aa5fefb0-cf61-5f36-82e6-31dbbdf3f616'
CATHETERIZATION = '91a4d13f-4bc8-54b0-a107-f4ab84cb7d60'
NO_INTERVENTION = '1107AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
URGENCY = '7b8eda07-34b6-55f2-ab6c-1b295f41918b'
URGENT = '33bf504a-15f2-5504-9bdc-ddded0b5eb00'
YES = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
CORE_TRUE = 'cf82933b-3f3f-45e7-a5ab-5d31aaee3da3'
AORTIC_VALVE = 'cd9c582a-71f9-5441-97a8-6d50d7dc15c8'
MITRAL_BALLOON = 'af9429ff-1b76-55f3-81ca-a9f775d93fb4'
PULMONARY_VALVULOPLASTY = '36b3cc68-c53f-5a23-8380-24dbaf9c88fb'
PROCEDURES_TYPE = 'c9b87090-8768-50be-987e-8ca0a8983429'
PROCEDURES_FORM = 'bf762810-2bf1-3ca3-bdbe-8bd71fd5d59a'
PROCEDURE_DATE = '6cbb5176-144a-576b-9b3d-c9e9d6bc5f5a'
SURGERY_TYPE = '46f4af80-b783-59f4-beb1-81144ccf3084'
CATHETERIZATION_TYPE = 'bb4a77ee-836a-57e7-a262-632fa22288d2'
RHD_DETAILS = 'cfe17bb5-4a76-5f3a-9e1c-7b1e9b84a8e3'
ACUTE_RHEUMATIC_FEVER = 'cbfcf051-bee3-549d-b233-e5be0e7d691a'
RHD_B = '5e019f88-6b33-5749-8804-d9686ae680d5'


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


def registrant(stack, clinic, suffix, *, birthdate, gender='F', attribute=CARDIAC_CLINIC_ATTRIBUTE):
    person = {'names': [{'givenName': 'Dashboard', 'familyName': f'Test {suffix}'}], 'gender': gender,
              'attributes': [{'attributeType': attribute, 'value': clinic}]}
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
    return stack.call('POST', '/encounter', {'patient': patient, 'encounterType': CONSULTATION_TYPE,
                                             'form': CONSULTATION_FORM, 'location': clinic,
                                             'encounterDatetime': when, 'obs': obs})['uuid']


def recommendation(procedure_type, procedure, *members):
    return {'concept': RECOMMENDATION, 'groupMembers': [{'concept': PROCEDURE_TYPE, 'value': procedure_type},
                                                        {'concept': RECOMMENDATION, 'value': procedure}, *members]}


def procedure(stack, patient, clinic, when, kind, done):
    """A Procedures and Outcomes encounter recording one surgery or catheterization, dated by its Date of Procedure."""
    stack.call('POST', '/encounter', {'patient': patient, 'encounterType': PROCEDURES_TYPE, 'form': PROCEDURES_FORM,
                                      'location': clinic, 'encounterDatetime': when,
                                      'obs': [{'concept': PROCEDURE_DATE, 'value': when},
                                              {'concept': kind, 'groupMembers': [{'concept': kind, 'value': done}]}]})


def patient_information(stack, patient, clinic, when, answers):
    stack.call('POST', '/encounter', {'patient': patient, 'encounterType': PATIENT_INFORMATION_TYPE, 'location': clinic,
                                      'encounterDatetime': when,
                                      'obs': [{'concept': concept, 'value': value} for concept, value in answers]})


def by(rows, breakdown, key='label', value='patients'):
    return {row[key]: int(row[value]) for row in rows if row['breakdown'] == breakdown}


def params_clinic(params):
    return {key: value for key, value in params.items() if key != 'endDate'}


def check_figure_lists(stack, where, *, registrants_only=False, **params):
    """Every figure the count reports give equals the rows of its patients report, with the same parameters."""
    def listed(report, **figure):
        return len(stack.rows(report, **params, **figure))

    registrants = stack.rows(REGISTRANTS, **params)
    for row in registrants:
        check(f"{row['breakdown']} {row['label']} listed at {where}",
              listed(REGISTRANT_PATIENTS, breakdown=row['breakdown'], label=row['label']), int(row['patients']))
    status = by(registrants, 'status')
    check(f'registered listed at {where}', listed(REGISTRANT_PATIENTS, breakdown='registered'), sum(status.values()))
    check(f'active listed at {where}', listed(REGISTRANT_PATIENTS, breakdown='active'), status.get('Active', 0))
    if registrants_only:
        return

    for row in stack.rows(WAITLIST, **params):
        if row['breakdown'] == 'open':
            got = listed(WAITLIST_PATIENTS, breakdown='open', procedure=row['procedure'], urgency=row['urgency'])
            check(f"open {row['procedure']} {row['urgency']} listed at {where}", got, int(row['recommendations']))
        elif row['breakdown'] == 'total':
            check(f'waiting listed at {where}', listed(WAITLIST_PATIENTS, breakdown='total'), int(row['patients']))
            check(f'open recommendations listed at {where}', listed(WAITLIST_PATIENTS, breakdown='open'),
                  int(row['recommendations']))
        else:
            check(f"performed {row['procedure']} listed at {where}",
                  listed(WAITLIST_PATIENTS, breakdown='performed', procedure=row['procedure']), int(row['recommendations']))

    for row in stack.rows(CASCADE, **params):
        check(f"cascade {row['step']} listed at {where}", listed(CASCADE_PATIENTS, step=row['step']), int(row['patients']))

    for row in stack.rows(OPTIMISATION, **params):
        check(f"{row['measure']} done listed at {where}", listed(OPTIMISATION_PATIENTS, measure=row['measure'], outcome='done'),
              int(row['done']))
        if row['not_done'] is not None:
            check(f"{row['measure']} not done listed at {where}",
                  listed(OPTIMISATION_PATIENTS, measure=row['measure'], outcome='notDone'), int(row['not_done']))


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
    patient_information(stack, rhd, clinic, day(300) + 'T09:00:00',
                        [(SCREEN_POSITIVE, YES), (CASE_DETECTED_BY, SCHOOL_SCREENING)])
    patient_information(stack, unknown_age, clinic, day(200) + 'T09:00:00',
                        [(SCREEN_POSITIVE, NO), (CASE_DETECTED_BY, CLINICAL_PRESENTATION)])
    # Registered before the period the screening check reads, so never counted in it
    patient_information(stack, ended, clinic, day(400) + 'T09:00:00',
                        [(SCREEN_POSITIVE, YES), (CASE_DETECTED_BY, SCHOOL_SCREENING)])
    registered_at_19 = today - datetime.timedelta(days=250)
    birthday = registered_at_19 + datetime.timedelta(days=50)
    rescreened = registrant(stack, clinic, f'{stamp} rescreened',
                            birthdate=birthday.replace(year=birthday.year - 20, day=min(birthday.day, 28)).isoformat())
    enrol(stack, rescreened, day(250))
    patient_information(stack, rescreened, clinic, day(250) + 'T09:00:00', [(SCREEN_POSITIVE, NO)])
    patient_information(stack, rescreened, clinic, day(100) + 'T09:00:00', [(SCREEN_POSITIVE, CORE_TRUE)])
    consultation(stack, rhd, clinic, day(20) + 'T10:00:00', [
        {'concept': DIAGNOSIS, 'groupMembers': [{'concept': DIAGNOSIS_CATEGORY, 'value': RHD}]},
        recommendation(SURGERY, AORTIC_VALVE, {'concept': URGENCY, 'value': URGENT}),
        recommendation(CATHETERIZATION, MITRAL_BALLOON),
        recommendation(CATHETERIZATION, PULMONARY_VALVULOPLASTY),
    ])
    procedure(stack, rhd, clinic, day(15) + 'T10:00:00', CATHETERIZATION_TYPE, MITRAL_BALLOON)
    procedure(stack, rhd, clinic, day(10) + 'T10:00:00', CATHETERIZATION_TYPE, PULMONARY_VALVULOPLASTY)
    operated_later = registrant(stack, clinic, f'{stamp} operated later', birthdate='1990-03-15')
    enrol(stack, operated_later, day(500))
    consultation(stack, operated_later, clinic, day(400) + 'T10:00:00', [
        {'concept': DIAGNOSIS, 'groupMembers': [{'concept': DIAGNOSIS_CATEGORY, 'value': RHD},
                                                {'concept': RHD_DETAILS, 'value': ACUTE_RHEUMATIC_FEVER},
                                                {'concept': RHD_DETAILS, 'value': RHD_B}]},
        recommendation(SURGERY, AORTIC_VALVE, {'concept': URGENCY, 'value': URGENT}),
    ])
    operated_then_ended = registrant(stack, clinic, f'{stamp} operated then ended', birthdate='1990-03-15')
    enrol(stack, operated_then_ended, day(300))
    consultation(stack, operated_then_ended, clinic, day(100) + 'T10:00:00', [
        recommendation(SURGERY, AORTIC_VALVE),
        recommendation(CATHETERIZATION, MITRAL_BALLOON, {'concept': URGENCY, 'value': URGENT}),
    ])
    procedure(stack, operated_then_ended, clinic, day(90) + 'T10:00:00', SURGERY_TYPE, AORTIC_VALVE)
    enrol(stack, operated_then_ended, day(300), completed=day(50))
    moved = registrant(stack, clinic, f'{stamp} visit moved', birthdate='1990-03-15')
    enrol(stack, moved, day(500))
    moved_consultation = consultation(stack, moved, clinic, day(400) + 'T10:00:00', [
        recommendation(CATHETERIZATION, MITRAL_BALLOON),
    ])
    procedure(stack, moved, clinic, day(399) + 'T10:00:00', CATHETERIZATION_TYPE, MITRAL_BALLOON)
    # Done on the consultation's day once it is moved: still done, as the match includes that day.
    stack.call('POST', f'/encounter/{moved_consultation}', {'encounterDatetime': day(399) + 'T10:00:00'})
    # Recorded today, after the yesterday checks' end date.
    procedure(stack, operated_later, clinic, day(0) + 'T10:00:00', SURGERY_TYPE, AORTIC_VALVE)
    # A Procedure Type of None, which the form saves as a recommendation with no procedure, is not waited for (AR-195).
    not_recommended = registrant(stack, clinic, f'{stamp} no intervention', birthdate='1990-03-15')
    enrol(stack, not_recommended, day(400))
    consultation(stack, not_recommended, clinic, day(5) + 'T10:00:00', [
        {'concept': RECOMMENDATION, 'groupMembers': [{'concept': PROCEDURE_TYPE, 'value': NO_INTERVENTION}]},
    ])

    end = today.isoformat()
    at_clinic = stack.rows(REGISTRANTS, endDate=end, cardiacClinic=clinic)
    check('status at the test clinic', by(at_clinic, 'status'), {'Active': 6, terminal_name: 2})
    check('age at the test clinic', by(at_clinic, 'age'), {'20-39': 5, 'Age unknown': 1})
    # Acute rheumatic fever beside RHD B counts under RHD B alone.
    check('disease at the test clinic', by(at_clinic, 'disease'),
          {'RHD, details not recorded': 1, 'RHD B': 1, 'No diagnosis yet': 4})
    check('sex at the test clinic', by(at_clinic, 'sex'), {'Female': 5, 'Male': 1})
    rhd_only = stack.rows(REGISTRANTS, endDate=end, cardiacClinic=clinic, category=RHD)
    check('status at the test clinic, RHD only', by(rhd_only, 'status'), by(at_clinic, 'status'))
    check('sex at the test clinic, RHD only', by(rhd_only, 'sex'), {'Female': 2})
    check('age at the test clinic, RHD only', by(rhd_only, 'age'), {'20-39': 2})
    check('disease at the test clinic, RHD only', by(rhd_only, 'disease'), {'RHD, details not recorded': 1, 'RHD B': 1})
    congenital_only = stack.rows(REGISTRANTS, endDate=end, cardiacClinic=clinic, category=CONGENITAL)
    check('status at the test clinic, congenital only', by(congenital_only, 'status'), by(at_clinic, 'status'))
    for breakdown in ('sex', 'age', 'disease'):
        check(f'{breakdown} at the test clinic, congenital only', by(congenital_only, breakdown), {})

    waitlist = stack.rows(WAITLIST, endDate=end, cardiacClinic=clinic)
    check('registrants among the clinics listed', by(stack.rows(REGISTRANTS, endDate=end, clinics=clinic), 'status'),
          by(at_clinic, 'status'))
    check('waitlist among the clinics listed', stack.rows(WAITLIST, endDate=end, clinics=clinic), waitlist)
    open_rows = [row for row in waitlist if row['breakdown'] == 'open']
    # Neither the open rows nor the total count the None recommendation.
    check('open recommendations at the test clinic',
          [(row['procedure'], row['urgency'], int(row['patients']), int(row['recommendations'])) for row in open_rows],
          [('Aortic valve', '2: urgent (60 days/2 months)', 1, 1)])
    check('total waiting at the test clinic', by(waitlist, 'total', 'procedure', 'patients'), {'All': 1})
    check('performed at the test clinic', by(waitlist, 'performed', 'procedure', 'recommendations'),
          {'Mitral balloon valvuloplasty': 1, 'Surgery': 2})

    yesterday = stack.rows(WAITLIST, endDate=day(1), cardiacClinic=clinic)
    check('open at the test clinic before the later completion',
          [(row['procedure'], row['urgency'], int(row['patients']), int(row['recommendations']))
           for row in yesterday if row['breakdown'] == 'open'],
          [('Aortic valve', '2: urgent (60 days/2 months)', 2, 2)])
    check('performed at the test clinic before the later completion',
          by(yesterday, 'performed', 'procedure', 'recommendations'),
          {'Mitral balloon valvuloplasty': 1, 'Surgery': 1})

    registry = stack.rows(REGISTRY, startDate='1900-01-01', endDate=end)
    if not registry:
        failures.append('the RHD Patient List has no rows, so nothing was compared')
    waiting = stack.rows(WAITING_LIST)
    alive = lambda row: row['enrollment_status'] == 'Active' and not row.get('deceased')
    clinics = {None} | {row.get('cardiac_clinic') for row in registry if row.get('cardiac_clinic')}
    # Every location, retired ones too: a name search leaves retired clinics out, and the demo seed retires most.
    uuids, start = {}, 0
    while True:
        page = stack.call('GET', f'/location?includeAll=true&v=custom:(uuid,display)&limit=100&startIndex={start}')['results']
        uuids.update({location['display']: location['uuid'] for location in page})
        if len(page) < 100:
            break
        start += 100
    for name in sorted(clinics, key=str):
        params = {'endDate': end, **({'cardiacClinic': uuids[name]} if name else {})}
        listed = [row for row in registry if not name or row.get('cardiac_clinic') == name]
        if name:
            # Real clinics have injections, which the seeded ones do not, so this covers the on-time columns too.
            check(f'programme among {name} listed', stack.rows(PROGRAMME, startDate=day(364), endDate=end, clinics=uuids[name]),
                  stack.rows(PROGRAMME, startDate=day(364), endDate=end, cardiacClinic=uuids[name]))
        counts = stack.rows(REGISTRANTS, **params)
        status = by(counts, 'status')
        where = name or 'every clinic'
        active_in = lambda report: {row['step']: int(row['patients']) for row in stack.rows(report, **params)}.get('Active')
        check(f'screening Active equals care cascade Active at {where}', active_in(SCREENING_CASCADE), active_in(CASCADE))
        check(f'registrants at {where}', sum(status.values()), len(listed))
        check(f'active at {where}', status.get('Active', 0), sum(1 for row in listed if alive(row)))
        for breakdown in ('sex', 'age', 'disease'):
            check(f'{breakdown} total at {where}', sum(by(counts, breakdown).values()), status.get('Active', 0))
        registered_here = [row for row in listed if day(364) <= str(row.get('date_enrolled'))[:10] <= end]
        screening = stack.rows(SCREENING, startDate=day(364), endDate=end, **params_clinic(params))
        check(f'screening registered at {where}', by(screening, 'total').get('Registered', 0), len(registered_here))
        check(f'screening female at {where}', by(screening, 'female').get('Female', 0),
              sum(1 for row in registered_here if row.get('sex') == 'F'))
        # The Patient List has no Screen +, so the two labels of an unanswered patient are checked together.
        detected = {}
        for row in registered_here:
            name_ = row.get('case_detected_by')
            bucket = DETECTION_BUCKETS.get(name_, 'Other') if name_ else 'Unanswered'
            detected[bucket] = detected.get(bucket, 0) + 1
        reported = {}
        for label, patients in by(screening, 'detected').items():
            bucket = 'Unanswered' if label in UNANSWERED else label
            reported[bucket] = reported.get(bucket, 0) + patients
        check(f'screening detection at {where}', reported, detected)
        for breakdown in ('screen', 'age', 'detected'):
            check(f'screening {breakdown} total at {where}', sum(by(screening, breakdown).values()), len(registered_here))
        waiting_here = [row for row in waiting if not name or row.get('cardiac_clinic') == name]
        open_rows = [row for row in stack.rows(WAITLIST, **params) if row['breakdown'] == 'open']
        check(f'open recommendations at {where}', sum(int(row['recommendations']) for row in open_rows),
              len(waiting_here))
        check(f'patients waiting at {where}', by(stack.rows(WAITLIST, **params), 'total', 'procedure', 'patients'),
              {'All': len({row['patient_uuid'] for row in waiting_here})})

    # Registered in the 365 days to today at the test clinic: no birth date (Screen + No, Clinical presentation), rhd
    # (Yes, School), operated then ended (nothing recorded, so never asked where it was screened) and rescreened (core's
    # True after No, adolescent when registered, screen-positive with no answer);
    # ended, operated later, visit moved and no intervention were registered before.
    period = {'startDate': day(364), 'endDate': end}
    screening = stack.rows(SCREENING, **period, cardiacClinic=clinic)
    check('screening total at the test clinic', by(screening, 'total'), {'Registered': 4})
    check('screening female at the test clinic', by(screening, 'female'), {'Female': 3})
    check('screening Screen + at the test clinic', by(screening, 'screen'), {'Yes': 2, 'No': 1, 'Not recorded': 1})
    check('screening age at the test clinic', by(screening, 'age'),
          {'Adults 20+': 2, 'Adolescents 10-19': 1, 'Age unknown': 1})
    check('screening detection at the test clinic', by(screening, 'detected'),
          {'School': 1, 'Clinical presentation': 1, 'Not screen-positive': 1, 'Not recorded': 1})
    # Rescreened's True, saved after this period, still counts.
    check('screening Screen + for a period ended before the later answer',
          by(stack.rows(SCREENING, startDate=day(364), endDate=day(150), cardiacClinic=clinic), 'screen'),
          {'Yes': 2, 'No': 1, 'Not recorded': 1})
    check('screening among the clinics listed', stack.rows(SCREENING, **period, clinics=clinic), screening)
    check('screening cascade at the test clinic',
          {row['step']: int(row['patients']) for row in stack.rows(SCREENING_CASCADE, endDate=end, cardiacClinic=clinic)},
          {'Active': 2, 'Confirmatory Diagnosis': 1, 'Diagnosed': 1, 'Heart Disease': 1})
    for report, label in ((SCREENING_CASCADE, 'screening cascade'), (SCREENING_DIAGNOSES, 'screening diagnoses')):
        check(f'{label} among the clinics listed', stack.rows(report, endDate=end, clinics=clinic),
              stack.rows(report, endDate=end, cardiacClinic=clinic))
    # A patient whose only clinic is a primary-care one counts among the clinics listed, as a site administrator's would.
    primary_care = stack.call('POST', '/location', {'name': f'Dashboard Test Primary Care {stamp}'})['uuid']
    primary_care_only = registrant(stack, primary_care, f'{stamp} primary care only', birthdate='1990-03-15',
                                   attribute=PRIMARY_CARE_CLINIC_ATTRIBUTE)
    enrol(stack, primary_care_only, day(100))
    patient_information(stack, primary_care_only, primary_care, day(100) + 'T09:00:00', [(SCREEN_POSITIVE, YES)])
    consultation(stack, primary_care_only, primary_care, day(20) + 'T10:00:00', [
        {'concept': DIAGNOSIS, 'groupMembers': [{'concept': DIAGNOSIS_CATEGORY, 'value': RHD}]},
    ])
    check('screening cascade among a primary-care clinic listed',
          {row['step']: int(row['patients']) for row in stack.rows(SCREENING_CASCADE, endDate=end, clinics=primary_care)},
          {'Active': 1, 'Confirmatory Diagnosis': 1, 'Diagnosed': 1, 'Heart Disease': 1})
    check('screening diagnoses among a primary-care clinic listed',
          by(stack.rows(SCREENING_DIAGNOSES, endDate=end, clinics=primary_care), 'category', 'category'),
          {'Rheumatic Heart Disease/Rheumatic Fever': 1})
    # A patient who died with the enrolment still open counts until the death date, as the care cascade counts them.
    deceased_clinic = stack.call('POST', '/location', {'name': f'Dashboard Test Deceased {stamp}'})['uuid']
    deceased = registrant(stack, deceased_clinic, f'{stamp} deceased', birthdate='1992-07-01')
    enrol(stack, deceased, day(100))
    patient_information(stack, deceased, deceased_clinic, day(100) + 'T09:00:00', [(SCREEN_POSITIVE, YES)])
    consultation(stack, deceased, deceased_clinic, day(20) + 'T10:00:00', [
        {'concept': DIAGNOSIS, 'groupMembers': [{'concept': DIAGNOSIS_CATEGORY, 'value': RHD}]},
    ])
    stack.call('POST', f'/person/{deceased}', {'dead': True, 'deathDate': day(5), 'causeOfDeathNonCoded': 'Dashboard test'})
    for when, alive in ((day(10), 1), (end, 0)):
        steps = lambda report: {row['step']: int(row['patients']) for row in stack.rows(report, endDate=when, clinics=deceased_clinic)}
        check(f'screening cascade of a patient who died, as of {when}', steps(SCREENING_CASCADE),
              {'Active': alive, 'Confirmatory Diagnosis': alive, 'Diagnosed': alive, 'Heart Disease': alive})
        check(f'care cascade Active of a patient who died, as of {when}', steps(CASCADE).get('Active'), alive)
        check(f'screening diagnoses of a patient who died, as of {when}',
              by(stack.rows(SCREENING_DIAGNOSES, endDate=when, clinics=deceased_clinic), 'category', 'category'),
              {'Rheumatic Heart Disease/Rheumatic Fever': 1} if alive else {})
    # The programme report files patients under their primary care clinic, so only the SQL can hold it to a cardiac one.
    active_by_facility = {}
    for where, scope, limit, active in (('the test clinic', {'cardiacClinic': clinic}, clinic, 6),
                                         ('a primary-care clinic', {'primaryCareClinic': primary_care}, primary_care, 1)):
        listed = stack.rows(PROGRAMME, **period, clinics=limit)
        check(f'programme among {where} listed', listed, stack.rows(PROGRAMME, **period, **scope))
        check(f'programme active among {where} listed', sum(int(row['active_patients']) for row in listed), active)
        for row in listed:
            facility = row['facility_uuid']
            active_by_facility[facility] = active_by_facility.get(facility, 0) + int(row['active_patients'])
    both = stack.rows(PROGRAMME, **period, clinics=f'{clinic},{primary_care}')
    check('programme active by facility among two clinics listed',
          {row['facility_uuid']: int(row['active_patients']) for row in both}, active_by_facility)
    check('programme active among two clinics listed', sum(int(row['active_patients']) for row in both), 7)

    check_figure_lists(stack, 'the test clinic', endDate=end, cardiacClinic=clinic)
    check_figure_lists(stack, 'the test clinic, RHD only', registrants_only=True, endDate=end, cardiacClinic=clinic, category=RHD)
    check_figure_lists(stack, 'every clinic, RHD only', registrants_only=True, endDate=end, category=RHD)
    check_figure_lists(stack, 'the clinics listed', endDate=end, clinics=clinic)
    check_figure_lists(stack, 'every clinic', endDate=end)
    check_figure_lists(stack, 'every clinic a day back', endDate=day(1))

    if failures:
        print('\n'.join(failures))
        sys.exit(1)
    print(f'ok: {len(clinics)} clinic groupings compared, test clinic {clinic_name}')


if __name__ == '__main__':
    main()
