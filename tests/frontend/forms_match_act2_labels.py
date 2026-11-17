#!/usr/bin/env python3
"""
Checks the RHD forms use ACT 2.0's wording where the team asked for it (AR-115): the consultation's Complication,
Medication, Dose, Key Findings/Recommendations and endocarditis labels, the Patient Information location labels,
the BPG anaphylaxis labels, the capitalised prophylaxis and Reason Stopped answers, Tetralogy of Fallot among Patient Information's
congenital diagnoses, Pregnant or Postpartum at Death back on the Patient Information form, and the echo's
Wilkins Score before the suitability questions.

Usage: python3 tests/frontend/forms_match_act2_labels.py
"""
import csv
import json
import pathlib
import unittest

CONFIG = pathlib.Path(__file__).resolve().parents[2] / 'distro' / 'configuration'
FORMS = CONFIG / 'ampathforms'
DEATH = '159AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
TETRALOGY_OF_FALLOT = '124944AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
PREGNANT_OR_POSTPARTUM_AT_DEATH = '4e66ea66-6bac-5a83-93be-3c2c8aabf49f'


def form(name):
    return json.loads((FORMS / name).read_text())


def every_question(node):
    if isinstance(node, dict):
        if 'label' in node and 'id' in node:
            yield node
        for value in node.values():
            yield from every_question(value)
    elif isinstance(node, list):
        for value in node:
            yield from every_question(value)


def labels(name):
    return {q['id']: q['label'] for q in every_question(form(name))}


def answers(question):
    return [a['label'] for a in question['questionOptions']['answers']]


def concept_names():
    names = {}
    for path in (CONFIG / 'concepts').glob('rhd_*.csv'):
        with path.open(newline='') as handle:
            for row in csv.DictReader(handle):
                names[row['Uuid']] = row['Fully specified name:en']
    return names


class ConsultationUsesAct2Wording(unittest.TestCase):
    def setUp(self):
        self.labels = labels('rhd_consultation.json')
        self.questions = {q['id']: q for q in every_question(form('rhd_consultation.json'))}

    def test_labels(self):
        self.assertEqual(self.labels['rhdComplications'], 'Complication')
        self.assertEqual(self.labels['cardiac_medication'], 'Medication')
        self.assertEqual(self.labels['dosing_consultation_visit'], 'Dose')
        self.assertEqual(self.labels['key_findings_recommendations'], 'Key Findings/Recommendations')
        self.assertEqual(self.labels['sbe_prophylaxis_indicated'], 'Is endocarditis prophylaxis recommended')

    def test_prophylaxis_and_reason_stopped_answers_are_capitalised(self):
        regimens = answers(self.questions['secondary_antibiotic_prophylaxis'])
        self.assertEqual(
            regimens[3:8],
            ['Oral Penicillin V', 'Oral Sulfadiazine', 'Oral Erythromycin', 'Oral Clarithromycin', 'Oral Azithromycin'],
        )
        self.assertEqual(answers(self.questions['reason_stopped'])[2:4], ['Provider Stopped', 'Patient Preference'])


class PatientInformationUsesAct2Wording(unittest.TestCase):
    def setUp(self):
        self.questions = {q['id']: q for q in every_question(form('rhd_patient_information.json'))}

    def test_location_labels(self):
        self.assertEqual(self.questions['village_area_of_residence']['label'], 'District/Area of Residence')
        self.assertEqual(
            self.questions['additional_information_to_help_locate_patient']['label'], 'Additional Location Information'
        )

    # The Diagnosis questions moved here from the consultation (#327).
    def test_tetralogy_of_fallot_is_a_congenital_diagnosis(self):
        congenital = self.questions['diagnosis_details_congenital']['questionOptions']['answers']
        by_label = {a['label']: a['concept'] for a in congenital}
        self.assertEqual(by_label['Tetralogy of Fallot'], TETRALOGY_OF_FALLOT)
        self.assertEqual(len(congenital), 25)
        self.assertEqual([a['label'] for a in congenital], sorted(by_label, key=str.lower))

    def test_pregnant_or_postpartum_at_death_for_a_woman_who_died(self):
        question = self.questions['pregnant_or_postpartum_at_death']
        self.assertEqual(question['label'], 'Pregnant or Postpartum at Death')
        self.assertEqual(question['questionOptions']['concept'], PREGNANT_OR_POSTPARTUM_AT_DEATH)
        self.assertEqual(answers(question), ['Yes', 'No'])
        self.assertTrue(question['required'])
        self.assertEqual(
            question['hide']['hideWhenExpression'],
            f"reason_inactive !== '{DEATH}' || patient.gender !== 'female'",
        )
        # It follows Details of Death, as on ACT 2.0.
        ids = [q['id'] for q in every_question(form('rhd_patient_information.json'))]
        self.assertEqual(ids[ids.index('details_of_events_leading_up_to_death') + 1], 'pregnant_or_postpartum_at_death')


class OtherFormsUseAct2Wording(unittest.TestCase):
    def test_bpg_anaphylaxis_labels(self):
        bpg = labels('rhd_bpg.json')
        self.assertEqual(
            bpg['time_since_injection_symptom_onset'], 'Approximate time between injection and symptoms onset'
        )
        self.assertEqual(bpg['describe_anaphylaxis_events'], 'Describe anaphylaxis events')

    def test_medication_update_says_medication(self):
        self.assertEqual(labels('rhd_medication_update.json')['cardiac_medication'], 'Medication')

    def test_echo_asks_wilkins_score_before_the_suitability_questions(self):
        ids = [q['id'] for q in form('rhd_echocardiogram.json')['pages'][0]['sections'][0]['questions']]
        self.assertEqual(
            ids[ids.index('mitralValveAnteriorLeafletLength'):],
            [
                'mitralValveAnteriorLeafletLength',
                'wilkins_score',
                'is_patient_suitable_for_mitral_valve_repair',
                'mitral_valve_repair_reasoning',
                'is_patient_suitable_for_bav',
                'if_no_why',
                'other_findings_on_echocardiogram',
            ],
        )


class ConceptNamesFollowTheLabels(unittest.TestCase):
    def test_renamed_concepts(self):
        names = concept_names()
        self.assertEqual(names['a04d2268-a7de-589f-b4b6-92c47c13e342'], 'Complication')
        self.assertEqual(names['8879385e-d35e-50a3-a3d0-4333d95d4878'], 'Dose')
        self.assertEqual(names['c5641213-1ec1-5378-b6de-9135ca25a56d'], 'District/Area of Residence')
        self.assertEqual(names['2cebe220-2a9d-5c53-be68-f2257a4bfc9e'], 'Additional Location Information')
        self.assertEqual(
            names['87986835-7aed-5489-80e9-cbe407bfce23'], 'Approximate time between injection and symptoms onset'
        )
        self.assertEqual(names['01ca2486-79e4-5988-86b2-953fb45bf927'], 'Describe anaphylaxis events')
        self.assertEqual(names['b9884219-358a-594b-94f5-f8a8863a25f3'], 'Oral Penicillin V')
        self.assertEqual(names['eaf16fa9-03d7-5846-94c3-b02805889ed9'], 'Provider Stopped')
        self.assertEqual(names['39af49bd-5dd0-5acd-8ffb-260bc83dbfd7'], 'Patient Preference')
        self.assertEqual(names[PREGNANT_OR_POSTPARTUM_AT_DEATH], 'Pregnant or Postpartum at Death')
        # Medication keeps its Cardiac Medication name: CIEL 161189 already owns the name Medication.
        self.assertEqual(names['0734567e-4f0a-5090-9d74-b953921a30e6'], 'Cardiac Medication')


if __name__ == '__main__':
    unittest.main()
