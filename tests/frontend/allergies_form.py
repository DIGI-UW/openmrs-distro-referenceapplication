#!/usr/bin/env python3
"""
Checks allergies are recorded on an RHD Allergies form of their own: one allergy per save, with the consultation's
questions and concepts plus a Date Resolved, recorded by the clinician and the community clinician, counted by the
reports, and not asked for on the consultation.

Usage: python3 tests/frontend/allergies_form.py
"""
import csv
import hashlib
import re
import json
import pathlib
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'distro' / 'configuration'
ALLERGIES = CONFIG / 'ampathforms' / 'rhd_allergies.json'
CONSULTATION = CONFIG / 'ampathforms' / 'rhd_consultation.json'

ALLERGY = 'cd73e118-64ee-5855-b276-f7cb44fdcf7e'
REACTION = '8200713e-8647-52f0-b93d-841e4e9687b7'
DATE_ADDED = 'b8514967-2259-5a4d-9ac5-b9319144b8dc'
DATE_RESOLVED = '8fbebbea-16dd-5dc5-98f0-c522cab26e19'
ENCOUNTER_TYPE = '8a687651-3554-4255-941c-812d7a21312e'
PENICILLIN = {'149071AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', 'b4e6c064-ab4f-5ee4-9837-094731ee23d4'}
# Initializer names an ampath form by this uuid, its name and its version.
AMPATH_FORMS_UUID = '794c4598-ab82-47ca-8d18-483a8abe6f4f'


def every_question(items):
    for q in items:
        yield q
        yield from every_question(q.get('questions', []))


def questions(path):
    form = json.loads(path.read_text())
    return list(every_question([q for page in form['pages'] for section in page['sections'] for q in section['questions']]))


def by_id(path):
    return {q['id']: q for q in questions(path) if 'id' in q}


def rows(name, key):
    with (CONFIG / name).open(newline='') as handle:
        return {row[key]: row for row in csv.DictReader(handle)}


class AllergiesForm(unittest.TestCase):
    def test_is_its_own_form_and_encounter_type(self):
        form = json.loads(ALLERGIES.read_text())
        self.assertEqual((form['name'], form['version'], form['encounter']), ('RHD Allergies', '1', 'RHD Allergies'))
        types = rows('encountertypes/rhd_encountertypes.csv', 'uuid')
        self.assertEqual(types[ENCOUNTER_TYPE]['name'], 'RHD Allergies')
        self.assertEqual(types[ENCOUNTER_TYPE]['edit privilege'], 'Task: act.enterAllergies')

    def test_the_consultation_button_names_the_uuid_initializer_gives_it(self):
        form = json.loads(ALLERGIES.read_text())
        seed = '_'.join([AMPATH_FORMS_UUID, form['name'], form['version']])
        derived = str(uuid.UUID(bytes=hashlib.md5(seed.encode()).digest(), version=3))
        button = by_id(CONSULTATION)['add_allergy']['questionOptions']
        self.assertEqual(button['workspaceProps']['form']['uuid'], derived)

    def test_records_one_allergy_with_the_consultations_questions(self):
        questions_by_id = by_id(ALLERGIES)
        group = questions_by_id['allergyEntry']
        self.assertEqual(group['questionOptions'], {'rendering': 'group', 'concept': ALLERGY})
        self.assertEqual(
            [q['id'] for q in group['questions']],
            ['allergy', 'reaction_allergies_group', 'dateAdded_allergy', 'dateResolved_allergy'],
        )
        allergy = questions_by_id['allergy']
        self.assertTrue(allergy['required'])
        self.assertEqual(allergy['questionOptions']['concept'], ALLERGY)
        self.assertLessEqual(PENICILLIN, {a['concept'] for a in allergy['questionOptions']['answers']})
        self.assertEqual(questions_by_id['reaction_allergies']['questionOptions']['concept'], REACTION)
        self.assertEqual(questions_by_id['reaction_allergies']['questionOptions']['rendering'], 'checkbox')
        self.assertEqual(questions_by_id['dateResolved_allergy']['questionOptions']['concept'], DATE_RESOLVED)

    def test_date_added_is_today_for_a_new_allergy_and_kept_on_edit(self):
        added = by_id(ALLERGIES)['dateAdded_allergy']
        self.assertTrue(added['required'])
        self.assertEqual(added['questionOptions']['concept'], DATE_ADDED)
        self.assertEqual(added['questionOptions']['calculate']['calculateExpression'], "mode === 'enter' ? today() : null")

    def test_date_resolved_is_a_date_concept(self):
        concept = rows('concepts/rhd_questions_consultation.csv', 'Uuid')[DATE_RESOLVED]
        self.assertEqual(concept['Same as mappings'], 'ACT-RHD:q_allergy_date_resolved')
        self.assertEqual(str(uuid.uuid5(uuid.NAMESPACE_URL, concept['Same as mappings'])), DATE_RESOLVED)
        self.assertEqual((concept['Fully specified name:en'], concept['Data type']), ('Date Resolved', 'Date'))


class WhoRecordsAllergies(unittest.TestCase):
    def test_the_clinician_and_the_community_clinician_and_not_the_data_clerk(self):
        roles = rows('roles/act_roles.csv', 'Role name')
        self.assertEqual(roles['Application: ACT Allergies']['Privileges'], 'Task: act.enterAllergies')
        inherits = lambda role: roles[role]['Inherited roles'].split(';')
        self.assertIn('Application: ACT Allergies', inherits('Organizational: ACT Clinician'))
        self.assertIn('Application: ACT Allergies', inherits('Organizational: ACT Community Clinician'))
        self.assertNotIn('Application: ACT Allergies', inherits('Organizational: ACT Data Clerk'))
        privileges = rows('privileges/rhd_privileges.csv', 'Privilege name')
        self.assertIn('Task: act.enterAllergies', privileges)


class ConsultationAsksNoAllergy(unittest.TestCase):
    def test_no_saved_question_asks_for_an_allergy(self):
        saved = [
            q for q in questions(CONSULTATION)
            if q.get('questionOptions', {}).get('concept') == ALLERGY and not q['questionOptions'].get('isTransient')
        ]
        self.assertEqual(saved, [])


class ReportsCountTheForm(unittest.TestCase):
    def test_the_encounters_export_and_the_instance_figures_list_it(self):
        for report in ('encounters/sql/rhd_encounters.sql', 'instance/sql/rhd_instance_kpis.sql'):
            sql = (CONFIG / 'reports' / 'reportdescriptors' / report).read_text()
            self.assertIn(f"'{ENCOUNTER_TYPE}'", sql, report)

    def test_the_flag_and_the_report_skip_an_allergy_whose_latest_record_is_resolved(self):
        flag = next(row for row in csv.reader((CONFIG / 'flags' / 'rhd_flags.csv').open()) if row[1:2] == ['RHD penicillin allergy on BPG'])
        patients = (CONFIG / 'reports' / 'reportdescriptors' / 'patients' / 'sql' / 'rhd_patients.sql').read_text()
        resolved = f"concept_id = (SELECT concept_id FROM concept WHERE uuid = '{DATE_RESOLVED}')"
        for name, sql, alias in (('flag', flag[4], 'al'), ('rhd_patients.sql', patients, 'o_pen')):
            sql = ' '.join(sql.split())
            # No later record of the same allergy answer, and no Date Resolved in this record's group.
            self.assertRegex(sql, rf'NOT EXISTS \(SELECT 1 FROM obs \w+ WHERE \w+\.person_id = {alias}\.person_id .*'
                             rf'\w+\.value_coded = {alias}\.value_coded', name)
            self.assertRegex(sql, rf'NOT EXISTS \(SELECT 1 FROM obs \w+ WHERE \w+\.obs_group_id = {alias}\.obs_group_id '
                             rf'AND \w+\.voided = 0 AND \w+\.{re.escape(resolved)}\)', name)


if __name__ == '__main__':
    unittest.main()
