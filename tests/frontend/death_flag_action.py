#!/usr/bin/env python3
"""
Checks the "RHD death not recorded on patient" flag opens the ACT app's Update patient status, which offers Deceased
only to users who may also end the registry enrolment, and that the stock Mark patient deceased stays out of reach.

Usage: python3 tests/frontend/death_flag_action.py
"""
import json
import pathlib
import unittest

CONFIG = pathlib.Path(__file__).resolve().parents[2] / 'frontend' / 'config-core_demo.json'


def config():
    return json.loads(CONFIG.read_text())


class DeathFlagAction(unittest.TestCase):
    def test_opens_update_patient_status(self):
        actions = config()['@openmrs/esm-patient-flags-app']['flagActions']
        death = [a for a in actions if a['flagName'] == 'RHD death not recorded on patient']
        self.assertEqual(death, [{'flagName': 'RHD death not recorded on patient',
                                  'workspace': 'act-update-patient-status-workspace'}])

    def test_no_flag_opens_the_stock_mark_patient_deceased(self):
        actions = config()['@openmrs/esm-patient-flags-app']
        workspaces = [a.get('workspace') for a in actions['flagActions'] + actions['tagActions']]
        self.assertNotIn('mark-patient-deceased-workspace-form', workspaces)

    def test_keeps_the_stock_mark_patient_deceased_button_removed(self):
        slots = config()['@openmrs/esm-patient-chart-app']['extensionSlots']
        self.assertIn('mark-patient-deceased-button', slots['patient-actions-slot']['remove'])


if __name__ == '__main__':
    unittest.main()
