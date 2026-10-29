#!/usr/bin/env python3
"""
Checks the patient chart's left menu order in frontend/config-core_demo.json: the clinician's workflow, with every
link the distro adds listed in the order so none falls to the bottom.

Usage: python3 tests/frontend/chart_menu_order.py
"""
import json
import pathlib
import unittest

CONFIG = pathlib.Path(__file__).resolve().parents[2] / 'frontend' / 'config-core_demo.json'

CLINICIAN_ORDER = [
    'charts-summary-dashboard',  # Patient summary
    'allergies-summary-dashboard',  # Allergies
    'results-summary-dashboard',  # Vitals & Biometrics (the id upstream gives its link)
    'act-cardiac-tests-dashboard-link',  # Cardiac tests
    'act-consultations-dashboard-link',  # Consultation visits
    'act-prophylaxis-dashboard-link',  # Prophylaxis
    'test-results-summary-dashboard',  # Results
    'encounters-summary-dashboard',  # Visits
    'act-research-dashboard-link',  # Research participation
    'programs-summary-dashboard',  # Programs
    'growth-chart-dashboard-link',  # Growth chart
]


def slot():
    config = json.loads(CONFIG.read_text())
    return config['@openmrs/esm-patient-chart-app']['extensionSlots']['patient-chart-dashboard-slot']


class ChartMenuOrder(unittest.TestCase):
    def test_follows_the_clinicians_visit_workflow(self):
        order = slot()['order']
        self.assertEqual([i for i in order if i in CLINICIAN_ORDER], CLINICIAN_ORDER)

    def test_lists_every_added_link(self):
        self.assertLessEqual(set(slot()['add']), set(slot()['order']))


if __name__ == '__main__':
    unittest.main()
