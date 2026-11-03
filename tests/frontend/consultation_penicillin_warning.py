#!/usr/bin/env python3
"""
Checks the RHD Consultation Visit form warns and asks for confirmation before a BPG regimen is prescribed (AR-171)
when the patient's current allergies (the actAllergies line) include penicillin.

Usage: python3 tests/frontend/consultation_penicillin_warning.py
"""
import json
import pathlib
import unittest

FORM = (
    pathlib.Path(__file__).resolve().parents[2]
    / 'distro' / 'configuration' / 'ampathforms' / 'rhd_consultation.json'
)

BPG = {
    '50be4b26-6c5b-5aaa-9254-3bfd313b4522',  # Q28 day BPG
    '2f3ee632-dd14-51b0-a4ec-de10e7958019',  # Q21 day BPG
    '91230c88-6a90-5d45-af50-fa6155fe5dd7',  # Q14 day BPG
}
ACKNOWLEDGED = '83ab9ae1-aec7-5f30-9273-6d7fd855594e'
YES = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'


def every_question(items):
    for q in items:
        yield q
        yield from every_question(q.get('questions', []))


def questions():
    form = json.loads(FORM.read_text())
    return list(every_question([q for page in form['pages'] for section in page['sections'] for q in section['questions']]))


def by_id(qid):
    return next(q for q in questions() if q.get('id') == qid)


class ConsultationPenicillinWarning(unittest.TestCase):
    def test_follow_the_regimen_inside_each_prophylaxis_entry(self):
        ids = [q['id'] for q in by_id('secondaryAntibioticProphylaxisEntry')['questions']]
        self.assertEqual(
            ids[:3], ['secondary_antibiotic_prophylaxis', 'penicillin_bpg_warning', 'penicillin_allergy_acknowledged']
        )

    def test_show_only_for_bpg_with_a_penicillin_allergy(self):
        for qid in ('penicillin_bpg_warning', 'penicillin_allergy_acknowledged'):
            expression = by_id(qid)['hide']['hideWhenExpression']
            self.assertTrue(expression.startswith('!('), qid)
            self.assertIn('.includes(secondary_antibiotic_prophylaxis)', expression)
            for concept in BPG:
                self.assertIn(concept, expression, qid)
            self.assertIn("[current_allergies].join('').includes('PENICILLIN ALLERGY')", expression)
            self.assertNotIn('allergy_1', expression, qid)
            self.assertNotIn('[allergy,', expression, qid)

    def test_the_regimen_select_offers_the_three_bpg_answers(self):
        answers = {a['concept'] for a in by_id('secondary_antibiotic_prophylaxis')['questionOptions']['answers']}
        self.assertTrue(BPG <= answers)

    def test_the_warning_names_the_penicillin_and_an_alternative(self):
        text = ' '.join(by_id('penicillin_bpg_warning')['value'])
        self.assertIn('benzathine penicillin', text)
        self.assertIn('erythromycin', text)

    def test_the_confirmation_is_required_and_records_yes(self):
        ack = by_id('penicillin_allergy_acknowledged')
        self.assertTrue(ack['required'])
        self.assertEqual(ack['questionOptions']['concept'], ACKNOWLEDGED)
        self.assertEqual([a['concept'] for a in ack['questionOptions']['answers']], [YES])
        self.assertEqual(ack['hide'], by_id('penicillin_bpg_warning')['hide'])


if __name__ == '__main__':
    unittest.main()
