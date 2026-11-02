#!/usr/bin/env python3
"""
Checks the patient banner shows the anaphylaxis alert first (AR-180): the ACT app's act-anaphylaxis-alert leads the
patient banner's tags, before the prophylaxis, INR, allergies and clinical pills.

Usage: python3 tests/frontend/banner_anaphylaxis_alert.py
"""
import json
import pathlib
import unittest

CONFIG = pathlib.Path(__file__).resolve().parents[2] / 'frontend' / 'config-core_demo.json'


class BannerAnaphylaxisAlert(unittest.TestCase):
    def test_the_alert_leads_the_banner_tags(self):
        slot = json.loads(CONFIG.read_text())['@openmrs/esm-patient-chart-app']['extensionSlots'][
            'patient-banner-tags-slot'
        ]
        self.assertEqual(slot['order'][0], 'act-anaphylaxis-alert')


if __name__ == '__main__':
    unittest.main()
