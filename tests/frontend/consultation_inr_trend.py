#!/usr/bin/env python3
"""
Checks the RHD Consultation Visit form carries the INR trend: a question after Latest INR, in the same section, that
the ACT app's `act-inr-chart` form control renders and that is never submitted (type `control`).

Usage: python3 tests/frontend/consultation_inr_trend.py
"""
import json
import pathlib
import unittest

FORM = (
    pathlib.Path(__file__).resolve().parents[2]
    / 'distro' / 'configuration' / 'ampathforms' / 'rhd_consultation.json'
)


def sections():
    return json.loads(FORM.read_text())['pages'][0]['sections']


def trend_section():
    return next(s for s in sections() if any(q.get('id') == 'inr_trend' for q in s['questions']))


class ConsultationInrTrend(unittest.TestCase):
    def test_follows_latest_inr(self):
        ids = [q.get('id') for q in trend_section()['questions']]
        self.assertEqual(ids[ids.index('latest_inr') + 1], 'inr_trend')

    def test_is_rendered_by_the_app_control_and_never_submitted(self):
        question = next(q for q in trend_section()['questions'] if q.get('id') == 'inr_trend')
        self.assertEqual(question['type'], 'control')
        self.assertEqual(question['questionOptions'], {'rendering': 'act-inr-chart'})


if __name__ == '__main__':
    unittest.main()
