#!/usr/bin/env python3
"""
Checks the RHD Consultation Visit form opens with the patient's current allergies: a read-only, unsaved line first in
the form, filled by the actAllergies helper the ACT app registers with the form engine.

Usage: python3 tests/frontend/consultation_allergies.py
"""
import json
import pathlib
import unittest

FORM = (
    pathlib.Path(__file__).resolve().parents[2]
    / 'distro' / 'configuration' / 'ampathforms' / 'rhd_consultation.json'
)


def questions():
    form = json.loads(FORM.read_text())
    return [q for section in form['pages'][0]['sections'] for q in section['questions']]


class ConsultationAllergies(unittest.TestCase):
    def test_opens_the_form(self):
        first = questions()[0]
        self.assertEqual(first['id'], 'current_allergies')
        self.assertTrue(first['readonly'])

    def test_is_filled_by_the_helper_and_never_saved(self):
        options = questions()[0]['questionOptions']
        self.assertEqual(options['calculate']['calculateExpression'], 'actAllergies(patient.id)')
        self.assertTrue(options['isTransient'])

    def test_reads_like_the_other_unsaved_lines(self):
        by_id = {q['id']: q for q in questions() if 'id' in q}
        self.assertEqual(
            by_id['current_allergies']['questionOptions']['concept'],
            by_id['latest_inr']['questionOptions']['concept'],
        )


if __name__ == '__main__':
    unittest.main()
