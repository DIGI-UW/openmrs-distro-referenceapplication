#!/usr/bin/env python3
"""
Checks the RHD Patient Information form: screening with where, when and the age at screening shown only for a
Screen + of Yes, the school only for a school screening, the VHT's name and contact, the Diagnosis section with
the one-choice rheumatic diagnosis and optional stage (AR-150), no confirmatory echo follow-up, and no Status section (AR-208): an enrolment ends through
the ACT app's Update patient status, and the Status questions' concepts stay for answers migrated from ACT 2.0. The RHD
Consultation Visit does not record the diagnosis, per the revert of AR-167.

Usage: python3 tests/frontend/patient_information_act2.py
"""
import csv
import json
import pathlib
import unittest

CONFIG = pathlib.Path(__file__).resolve().parents[2] / 'distro' / 'configuration'
FORMS = CONFIG / 'ampathforms'
YES = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
DIAGNOSIS_GROUP = '594b4495-36dc-52a6-9810-15a9e2e2dcb9'
FOLLOW_UP_STATUS = 'c25c84d9-1f23-4426-8d43-ad1e3829cbb7'
CASE_DETECTED_BY = '955632a1-82f7-5b84-a341-de85f95588d1'
# The ACT 2.0 Status questions: Status, Date of Status Change, Reason Inactive, Relocation Area, Cause of Death,
# Date of Death, Details of Death and Pregnant or Postpartum at Death.
STATUS_QUESTIONS = {
    '634a259d-fce2-5c93-b480-54f522c09a33',
    '1fb9ec14-a08a-581b-a5fb-c9ad8bbdf9e2',
    'ecc7c952-37fb-5aba-b492-ba090f544829',
    '32f3e45d-c2a8-5c19-b4d1-9306251426f6',
    '409f09ab-9a03-5c81-8d04-0e970531765b',
    '07534416-c1c2-5772-83d8-76a429986ec0',
    'a4d27e8c-0c90-571f-be54-a6132c7a1d69',
    '4e66ea66-6bac-5a83-93be-3c2c8aabf49f',
}
SCHOOL_SCREENING = '5b7d5eb4-4c6a-52cb-95f3-ac5033708fc9'
SCHOOL_NAME = 'cfd8f77a-a2b5-5836-96c1-d3e5fdd48e02'


def sections(form):
    data = json.loads((FORMS / form).read_text())
    return {section['label']: section['questions'] for page in data['pages'] for section in page['sections']}


def every_question(items):
    for q in items:
        yield q
        yield from every_question(q.get('questions', []))


class PatientInformationRecordsTheDiagnosis(unittest.TestCase):
    def setUp(self):
        self.pi = sections('rhd_patient_information.json')

    def test_sections_in_order(self):
        self.assertEqual(
            list(self.pi), ['Screening', 'Diagnosis', 'Village health team', 'Where to find the patient']
        )

    def test_screening_asks_where_when_and_the_age_only_for_a_positive_screen(self):
        ids = [q['id'] for q in self.pi['Screening']]
        self.assertEqual(
            ids, ['screening_note', 'screen_positive', 'case_detected_by', 'school_name', 'screen_positive_date', 'age_at_screening']
        )
        by_id = {q['id']: q for q in self.pi['Screening']}
        self.assertEqual(by_id['case_detected_by']['questionOptions']['concept'], CASE_DETECTED_BY)
        for qid in ('case_detected_by', 'screen_positive_date', 'age_at_screening'):
            self.assertEqual(by_id[qid]['hide']['hideWhenExpression'], f"screen_positive !== '{YES}'", qid)
        age = by_id['age_at_screening']
        self.assertTrue(age['readonly'])
        self.assertIn('patient.birthDate', age['questionOptions']['calculate']['calculateExpression'])
        self.assertIn('screen_positive_date', age['questionOptions']['calculate']['calculateExpression'])

    def test_school_name_only_for_a_positive_school_screening(self):
        school = {q['id']: q for q in self.pi['Screening']}['school_name']
        self.assertEqual(school['label'], 'School Name')
        self.assertEqual(school['type'], 'obs')
        self.assertEqual(school['questionOptions'], {'rendering': 'text', 'concept': SCHOOL_NAME})
        self.assertEqual(
            school['hide']['hideWhenExpression'],
            f"screen_positive !== '{YES}' || case_detected_by !== '{SCHOOL_SCREENING}'",
        )

    def test_the_vht_has_a_name_and_a_contact(self):
        ids = [q['id'] for q in self.pi['Village health team']]
        self.assertEqual(ids[:2], ['vht_name', 'vht_contact'])

    def test_a_diagnosis_section_with_the_one_choice_rheumatic_diagnosis(self):
        group = [q for q in self.pi['Diagnosis'] if q.get('type') == 'obsGroup']
        self.assertEqual(len(group), 1)
        self.assertEqual(group[0]['questionOptions']['concept'], DIAGNOSIS_GROUP)
        self.assertEqual(group[0]['questionOptions']['rendering'], 'repeating')
        # The one-choice rheumatic diagnosis with its optional stage (AR-150).
        rhd = [q for q in group[0]['questions'] if q['id'] == 'diagnosis_details_rhd'][0]
        self.assertEqual(rhd['questionOptions']['rendering'], 'radio')

    def test_no_follow_up_status(self):
        concepts = {q.get('questionOptions', {}).get('concept') for q in every_question([q for qs in self.pi.values() for q in qs])}
        self.assertNotIn(FOLLOW_UP_STATUS, concepts)

    def test_no_status_questions_but_their_concepts_stay_for_migration(self):
        # Answering Inactive here never ended the enrolment, so the questions are gone; Update patient status ends it.
        concepts = {q.get('questionOptions', {}).get('concept') for q in every_question([q for qs in self.pi.values() for q in qs])}
        self.assertFalse(STATUS_QUESTIONS & concepts)
        with open(CONFIG / 'concepts' / 'rhd_questions_registration.csv', newline='') as f:
            defined = {row['Uuid'] for row in csv.DictReader(f)}
        self.assertEqual(STATUS_QUESTIONS - defined, set())


class ConsultationDoesNotRecordTheDiagnosis(unittest.TestCase):
    def test_no_diagnosis_section(self):
        consultation = sections('rhd_consultation.json')
        self.assertNotIn('Diagnosis', consultation)
        concepts = {q.get('questionOptions', {}).get('concept') for q in every_question([q for qs in consultation.values() for q in qs])}
        self.assertNotIn(DIAGNOSIS_GROUP, concepts)


if __name__ == '__main__':
    unittest.main()
