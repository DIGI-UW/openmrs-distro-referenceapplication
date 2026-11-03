#!/usr/bin/env python3
"""
Checks the RHD Consultation Visit form opens with the patient's current allergies: a read-only, unsaved line first in
the form, filled by the actAllergies helper the ACT app registers with the form engine and kept up to date by its
act-current-allergies control; then an Add allergy button opening the RHD Allergies form beside the consultation
(#319).

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
        self.assertEqual(options['rendering'], 'act-current-allergies')
        self.assertTrue(options['isTransient'])

    def test_is_followed_by_add_allergy(self):
        button = questions()[1]
        self.assertEqual(button['id'], 'add_allergy')
        options = button['questionOptions']
        self.assertEqual(options['rendering'], 'workspace-launcher')
        self.assertEqual(options['buttonLabel'], 'Add allergy')
        # The ACT app's window for it, beside the consultation, which stays open.
        self.assertEqual(options['workspaceName'], 'act-allergy-form-entry-workspace')
        props = options['workspaceProps']
        self.assertEqual(props['form']['display'], 'RHD Allergies')
        self.assertEqual(props['additionalProps'], {'mode': 'enter', 'openClinicalFormsWorkspaceOnFormClose': False})
        self.assertNotIn('hide', button)

    def test_reads_like_the_other_unsaved_lines(self):
        by_id = {q['id']: q for q in questions() if 'id' in q}
        self.assertEqual(
            by_id['current_allergies']['questionOptions']['concept'],
            by_id['latest_inr']['questionOptions']['concept'],
        )


if __name__ == '__main__':
    unittest.main()
