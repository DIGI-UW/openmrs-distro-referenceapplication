#!/usr/bin/env python3
"""
Checks that choosing Other on a medication, interventional recommendation, allergy, INR indication or chronic health
condition opens a text field for what it is, as ACT 2.0 did and #125 did for BPG and adherence (AR-205): the field
follows its question in the same group, shows only for Other, carries the previous value when its question does,
and is a Text concept of its own in its section's set.

Usage: python3 tests/frontend/forms_other_fields.py
"""
import csv
import json
import pathlib
import unittest

CONFIG = pathlib.Path(__file__).resolve().parents[2] / 'distro' / 'configuration'
OTHER = '5622AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
OTHER_RECOMMENDATION = '4ff41d80-a6f6-5e65-b20a-66b31ce1baa6'
SURGERY = 'aa5fefb0-cf61-5f36-82e6-31dbbdf3f616'
CATHETERIZATION = '91a4d13f-4bc8-54b0-a107-f4ab84cb7d60'

OTHER_MEDICATION = 'f317415d-aed3-514b-8d9c-e11a79987646'
OTHER_INTERVENTIONAL = '1a1c54ad-632f-5be0-a78a-6f6d6401c059'
OTHER_ALLERGY = '9afb116d-e840-5dda-995f-aea75491675b'
OTHER_INR_INDICATION = 'edc5a6a1-e3b5-5273-9cab-8769f9db22ea'
OTHER_CONDITION = 'fa9214bd-7b36-57ab-836d-a2eaf7898bbe'

# (form, question the field follows, field id, its concept, hide expression)
FIELDS = [
    ('rhd_consultation.json', 'cardiac_medication', 'other_cardiac_medication', OTHER_MEDICATION,
     f"cardiac_medication !== '{OTHER}'"),
    ('rhd_medication_update.json', 'cardiac_medication', 'other_cardiac_medication', OTHER_MEDICATION,
     f"cardiac_medication !== '{OTHER}'"),
    ('rhd_consultation.json', 'interventional_recommendation_catheterization', 'other_interventional_recommendation',
     OTHER_INTERVENTIONAL,
     f"!((procedureType === '{SURGERY}' && interventional_recommendation_surgery === '{OTHER_RECOMMENDATION}') || "
     f"(procedureType === '{CATHETERIZATION}' && interventional_recommendation_catheterization === '{OTHER_RECOMMENDATION}'))"),
    ('rhd_allergies.json', 'allergy', 'other_allergy', OTHER_ALLERGY, f"allergy !== '{OTHER}'"),
    ('rhd_inr_monitoring.json', 'indication_inr_monitoring', 'other_inr_indication', OTHER_INR_INDICATION,
     f"indication_inr_monitoring !== '{OTHER}'"),
    ('rhd_consultation.json', 'chronicHealthCondition', 'other_chronic_health_condition', OTHER_CONDITION,
     f"chronicHealthCondition !== '{OTHER}'"),
]

# (set, the question concept the new one follows, the new concept)
SET_MEMBERS = [
    ('e5869082-9fd1-5036-be9e-f63c39e2c947', '0734567e-4f0a-5090-9d74-b953921a30e6', OTHER_MEDICATION),
    ('1179ec8f-364e-54a0-ab1a-e958db6bd371', 'd80478b2-4ed2-5d93-a604-6b5b50dab441', OTHER_CONDITION),
    ('01f4aca2-e29e-58b9-a92a-4d2d987d5fe0', 'ce93d393-1df5-587f-bf11-c373eac2ccf4', OTHER_INTERVENTIONAL),
    ('878f91cc-af76-568e-a9bd-b3a18119d367', '6e8ed53f-15e6-5b00-9ed0-44b11bd2d638', OTHER_INR_INDICATION),
]


def form(name):
    return json.loads((CONFIG / 'ampathforms' / name).read_text())


def groups(node):
    """Every list of sibling questions in the form, with the sections' lists."""
    if isinstance(node, dict):
        if isinstance(node.get('questions'), list):
            yield node['questions']
        for value in node.values():
            yield from groups(value)
    elif isinstance(node, list):
        for value in node:
            yield from groups(value)


def fields(node):
    for siblings in groups(node):
        yield from siblings


def concepts():
    rows = {}
    for path in (CONFIG / 'concepts').glob('*.csv'):
        with path.open(newline='') as handle:
            for row in csv.DictReader(handle):
                rows[row['Uuid']] = row
    return rows


class OtherOpensAField(unittest.TestCase):
    def test_each_other_answer_has_its_field_right_after_it(self):
        for name, after, field_id, concept, hide in FIELDS:
            with self.subTest(form=name, field=field_id):
                siblings = next(s for s in groups(form(name)) if any(q.get('id') == after for q in s))
                ids = [q.get('id') for q in siblings]
                self.assertEqual(ids[ids.index(after) + 1], field_id)
                field = siblings[ids.index(field_id)]
                options = {'rendering': 'text', 'concept': concept}
                if siblings[ids.index(after)]['questionOptions'].get('enablePreviousValue'):
                    options['enablePreviousValue'] = True
                self.assertEqual(field['type'], 'obs')
                self.assertEqual(field['questionOptions'], options)
                self.assertEqual(field['hide']['hideWhenExpression'], hide)

    def test_each_new_concept_is_one_field_per_form(self):
        for name in {f[0] for f in FIELDS}:
            used = [q.get('questionOptions', {}).get('concept') for q in fields(form(name))]
            for concept in {f[3] for f in FIELDS if f[0] == name}:
                with self.subTest(form=name, concept=concept):
                    self.assertEqual(used.count(concept), 1)


class TheConceptsAreText(unittest.TestCase):
    def setUp(self):
        self.concepts = concepts()

    def test_text_questions(self):
        for concept in {f[3] for f in FIELDS}:
            with self.subTest(concept=concept):
                row = self.concepts[concept]
                self.assertEqual((row['Data class'], row['Data type']), ('Question', 'Text'))
                self.assertTrue(row['Same as mappings'].startswith('ACT-RHD:q_other_'))

    def test_each_joins_its_section_set_after_its_question(self):
        by_name = {row['Fully specified name:en']: uuid for uuid, row in self.concepts.items()}
        for set_uuid, question, concept in SET_MEMBERS:
            with self.subTest(set=set_uuid):
                members = [m.strip() for m in self.concepts[set_uuid]['Members'].split(';')]
                resolved = [m if m in self.concepts else by_name.get(m) for m in members]
                self.assertEqual(resolved[resolved.index(question) + 1], concept)


if __name__ == '__main__':
    unittest.main()
