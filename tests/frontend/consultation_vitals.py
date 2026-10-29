#!/usr/bin/env python3
"""
Checks the RHD Consultation Visit form shows the vitals the nurse recorded earlier in the visit instead of asking for
them again: a read-only, unsaved line after the allergies, filled by the actVisitVitals helper the ACT app registers
with the form engine, and a Record vitals button that shows only when the visit has none.

Usage: python3 tests/frontend/consultation_vitals.py
"""
import json
import pathlib
import unittest

FORM = (
    pathlib.Path(__file__).resolve().parents[2]
    / 'distro' / 'configuration' / 'ampathforms' / 'rhd_consultation.json'
)

# The vitals app's concepts, which the form no longer asks for (AR-144).
VITALS = {
    '5085AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', '5086AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', '5087AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    '5088AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', '5242AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', '5092AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    '5089AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', '5090AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', '1343AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
}


def questions():
    form = json.loads(FORM.read_text())
    return [q for section in form['pages'][0]['sections'] for q in section['questions']]


def every_question(items):
    for q in items:
        yield q
        yield from every_question(q.get('questions', []))


class ConsultationVitals(unittest.TestCase):
    def test_follows_the_allergies(self):
        ids = [q.get('id') for q in questions()]
        self.assertEqual(ids[:3], ['current_allergies', 'current_vitals', 'record_vitals'])

    def test_is_filled_from_the_visit_by_the_helper_and_never_saved(self):
        vitals = questions()[1]
        self.assertTrue(vitals['readonly'])
        options = vitals['questionOptions']
        self.assertEqual(options['calculate']['calculateExpression'], 'actVisitVitals(patient.id, visit.uuid)')
        self.assertTrue(options['isTransient'])

    def test_offers_the_vitals_form_only_when_the_visit_has_none(self):
        button = questions()[2]
        self.assertEqual(button['questionOptions']['rendering'], 'workspace-launcher')
        self.assertEqual(button['questionOptions']['workspaceName'], 'patient-vitals-biometrics-form-workspace')
        # The text the helper returns when the visit has no vitals.
        self.assertEqual(
            button['hide']['hideWhenExpression'], "current_vitals !== 'Vitals not recorded at this visit'"
        )

    def test_asks_for_no_vital_or_mechanical_valve_contraindication(self):
        saved = [q for q in every_question(questions()) if not q.get('questionOptions', {}).get('isTransient')]
        self.assertFalse(VITALS & {q.get('questionOptions', {}).get('concept') for q in saved})
        self.assertFalse([q for q in saved if 'mechanical valve' in q.get('label', '').lower()])


if __name__ == '__main__':
    unittest.main()
