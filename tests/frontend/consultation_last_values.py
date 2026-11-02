#!/usr/bin/env python3
"""
Checks the RHD Consultation Visit form offers last time's answer, to reuse with one click, on the questions a clinician
should not have to re-enter each visit (AR-112): the secondary prophylaxis regimen, its start date, duration and data
entry; whether endocarditis prophylaxis is recommended; and each cardiac medication's name, dose, interval and start
date. The form engine reads them from the patient's previous consultation.

Usage: python3 tests/frontend/consultation_last_values.py
"""
import json
import pathlib
import unittest

FORM = (
    pathlib.Path(__file__).resolve().parents[2]
    / 'distro' / 'configuration' / 'ampathforms' / 'rhd_consultation.json'
)

OFFERED = {
    'secondary_antibiotic_prophylaxis', 'sap_date_started',
    'secondary_antibiotic_prophylaxis_duration', 'secondary_antibiotic_prophylaxis_data_entry',
    'sbe_prophylaxis_indicated',
    'cardiac_medication', 'dosing_consultation_visit', 'dosing_interval', 'cardiac_med_date_started',
}
# Stopping a regimen or a medicine is this visit's news, so those are never offered from last time.
NOT_OFFERED = {'sap_date_stopped', 'reason_stopped', 'cardiac_med_date_stopped', 'penicillin_allergy_acknowledged'}


def every_question(items):
    for q in items:
        yield q
        yield from every_question(q.get('questions', []))


class ConsultationOffersLastValues(unittest.TestCase):
    def setUp(self):
        form = json.loads(FORM.read_text())
        self.by_id = {
            q.get('id'): q
            for q in every_question([q for page in form['pages'] for section in page['sections'] for q in section['questions']])
        }

    def test_offers_last_time_on_the_prophylaxis_and_medication_questions(self):
        for qid in OFFERED:
            self.assertTrue(self.by_id[qid]['questionOptions'].get('enablePreviousValue'), qid)

    def test_never_on_what_stops_or_confirms(self):
        for qid in NOT_OFFERED:
            self.assertFalse(self.by_id[qid]['questionOptions'].get('enablePreviousValue'), qid)


if __name__ == '__main__':
    unittest.main()
