#!/usr/bin/env python3
"""
Checks the RHD forms refuse impossible numbers as ACT 2.0 did (AR-199): LVEF 0 to 100, ICU stay, ventilation and
bypass times not negative, and Birth Weight a number from 0 to 7 kg, on both the form question and the concept, with
a birth weight saved as text before still shown, read-only.

Usage: python3 tests/frontend/form_ranges.py
"""
import csv
import json
import pathlib
import unittest

CONFIG = pathlib.Path(__file__).resolve().parents[2] / 'distro' / 'configuration'
LVEF = 'ed630fda-8451-53c0-929e-40eafd9bca9b'
ICU_STAY = '5b409279-ec02-50a9-8d68-9953f526beeb'
VENTILATION_TIME = '26f8371b-ef08-5a2d-ab3d-88d384b142a5'
BYPASS_TIME = '6acafff7-7a23-50e6-8bca-24d8fc77c87d'
BIRTH_WEIGHT_KG = '2a6c28f9-6845-558b-b2a1-3efbb8f123ff'
BIRTH_WEIGHT_TEXT = '864deea0-d006-559e-b5fb-5b26c4c56fa5'


def questions(form):
    data = json.loads((CONFIG / 'ampathforms' / form).read_text())

    def walk(items):
        for q in items:
            yield q
            yield from walk(q.get('questions', []))

    return {q['id']: q for page in data['pages'] for section in page['sections'] for q in walk(section['questions'])}


def concepts():
    rows = {}
    for path in (CONFIG / 'concepts').glob('*.csv'):
        with path.open(newline='') as handle:
            for row in csv.DictReader(handle):
                rows[row['Uuid']] = row
    return rows


class FormsSetTheRanges(unittest.TestCase):
    def assertRange(self, question, concept, low, high=None):
        options = question['questionOptions']
        self.assertEqual(options['concept'], concept)
        self.assertEqual(options['rendering'], 'number')
        self.assertEqual(options.get('min'), low)
        self.assertEqual(options.get('max'), high)

    def test_lvef(self):
        self.assertRange(questions('rhd_echocardiogram.json')['left_ventricular_ejection_fraction'], LVEF, '0', '100')

    def test_procedure_times(self):
        interventions = questions('rhd_interventions.json')
        self.assertRange(interventions['icu_stay'], ICU_STAY, '0')
        self.assertRange(interventions['ventilation_time'], VENTILATION_TIME, '0')
        self.assertRange(interventions['cardiopulmonary_bypass_time'], BYPASS_TIME, '0')

    def test_birth_weight_is_a_number_in_kg(self):
        self.assertRange(questions('rhd_pregnancy.json')['birth_weight_kg'], BIRTH_WEIGHT_KG, '0', '7')

    def test_a_text_birth_weight_saved_before_still_shows(self):
        pregnancy = questions('rhd_pregnancy.json')
        ids = list(pregnancy)
        # Keeps the id its saved answers' form field path names, or the form engine gives them to no field.
        self.assertEqual(ids[ids.index('birth_weight_kg') + 1], 'neonatal_weight_kg')
        legacy = pregnancy['neonatal_weight_kg']
        self.assertEqual(legacy['questionOptions'], {'rendering': 'text', 'concept': BIRTH_WEIGHT_TEXT})
        self.assertTrue(legacy['readonly'])
        self.assertEqual(legacy['hide']['hideWhenExpression'], 'isEmpty(neonatal_weight_kg)')


class ConceptsSetTheRanges(unittest.TestCase):
    def setUp(self):
        self.concepts = concepts()

    def assertAbsolute(self, uuid, low, high=''):
        row = self.concepts[uuid]
        self.assertEqual(row['Data type'], 'Numeric')
        self.assertEqual((row.get('Absolute low'), row.get('Absolute high') or ''), (low, high))

    def test_ranges(self):
        self.assertAbsolute(LVEF, '0', '100')
        self.assertAbsolute(ICU_STAY, '0')
        self.assertAbsolute(VENTILATION_TIME, '0')
        self.assertAbsolute(BYPASS_TIME, '0')
        self.assertAbsolute(BIRTH_WEIGHT_KG, '0', '7')

    def test_birth_weight_in_kg_with_decimals(self):
        row = self.concepts[BIRTH_WEIGHT_KG]
        self.assertEqual((row['Fully specified name:en'], row['Units'], row['Allow decimals']), ('Birth Weight (kg)', 'kg', 'true'))

    def test_the_text_birth_weight_stays(self):
        row = self.concepts[BIRTH_WEIGHT_TEXT]
        self.assertEqual((row['Data type'], row['Void/Retire']), ('Text', ''))


if __name__ == '__main__':
    unittest.main()
