#!/usr/bin/env python3
"""
Checks the RHD Patient Information form: screening with where, when and the age at screening shown only for a
Screen + of Yes, the VHT's name and contact, the Diagnosis section with the one-choice rheumatic diagnosis and
optional stage (AR-150), and no confirmatory echo follow-up. The RHD Consultation Visit does not record the
diagnosis, per the revert of AR-167.

Usage: python3 tests/frontend/patient_information_act2.py
"""
import json
import pathlib
import unittest

FORMS = pathlib.Path(__file__).resolve().parents[2] / 'distro' / 'configuration' / 'ampathforms'
YES = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
DIAGNOSIS_GROUP = '594b4495-36dc-52a6-9810-15a9e2e2dcb9'
FOLLOW_UP_STATUS = 'c25c84d9-1f23-4426-8d43-ad1e3829cbb7'
CASE_DETECTED_BY = '955632a1-82f7-5b84-a341-de85f95588d1'


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
            list(self.pi), ['Screening', 'Diagnosis', 'Village health team', 'Status', 'Where to find the patient']
        )

    def test_screening_asks_where_when_and_the_age_only_for_a_positive_screen(self):
        ids = [q['id'] for q in self.pi['Screening']]
        self.assertEqual(ids, ['screening_note', 'screen_positive', 'case_detected_by', 'screen_positive_date', 'age_at_screening'])
        by_id = {q['id']: q for q in self.pi['Screening']}
        self.assertEqual(by_id['case_detected_by']['questionOptions']['concept'], CASE_DETECTED_BY)
        for qid in ('case_detected_by', 'screen_positive_date', 'age_at_screening'):
            self.assertEqual(by_id[qid]['hide']['hideWhenExpression'], f"screen_positive !== '{YES}'", qid)
        age = by_id['age_at_screening']
        self.assertTrue(age['readonly'])
        self.assertIn('patient.birthDate', age['questionOptions']['calculate']['calculateExpression'])
        self.assertIn('screen_positive_date', age['questionOptions']['calculate']['calculateExpression'])

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


class ConsultationDoesNotRecordTheDiagnosis(unittest.TestCase):
    def test_no_diagnosis_section(self):
        consultation = sections('rhd_consultation.json')
        self.assertNotIn('Diagnosis', consultation)
        concepts = {q.get('questionOptions', {}).get('concept') for q in every_question([q for qs in consultation.values() for q in qs])}
        self.assertNotIn(DIAGNOSIS_GROUP, concepts)


if __name__ == '__main__':
    unittest.main()
