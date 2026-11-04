#!/usr/bin/env python3
"""
Checks users see the forms without the "RHD " prefix (AR-184) while each form keeps the name, and so the uuid,
Initializer derives from it: a ui.i18n.Form.name message gives the shown name, and nothing in the forms names
a form by its old name.

Usage: python3 tests/frontend/form_display_names.py
"""
import hashlib
import json
import pathlib
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
FORMS = ROOT / 'distro' / 'configuration' / 'ampathforms'
MESSAGES = ROOT / 'distro' / 'configuration' / 'messageproperties' / 'forms_en.properties'
COMPOSE = ROOT / 'docker-compose.yml'
# Initializer names an ampath form by this uuid, its name and its version.
AMPATH_FORMS_UUID = '794c4598-ab82-47ca-8d18-483a8abe6f4f'
PREFIX = 'RHD '


def form_uuid(name, version):
    digest = bytearray(hashlib.md5(f'{AMPATH_FORMS_UUID}_{name}_{version}'.encode()).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def forms():
    return {path.name: json.loads(path.read_text()) for path in sorted(FORMS.glob('*.json'))}


def messages():
    pairs = (line.split('=', 1) for line in MESSAGES.read_text().splitlines() if line and not line.startswith('#'))
    return {key.strip(): value.strip() for key, value in pairs}


def strings(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)
    elif isinstance(node, str):
        yield node


def workspace_props(node):
    if isinstance(node, dict):
        if isinstance(node.get('workspaceProps'), dict):
            yield node['workspaceProps']
        for value in node.values():
            yield from workspace_props(value)
    elif isinstance(node, list):
        for value in node:
            yield from workspace_props(value)


class FormDisplayNames(unittest.TestCase):
    def test_every_rhd_form_is_shown_without_the_prefix(self):
        prefixed = {f['name']: f for f in forms().values() if f['name'].startswith(PREFIX)}
        self.assertEqual(len(prefixed), 12)
        shown = messages()
        for name, form in prefixed.items():
            key = f"ui.i18n.Form.name.{form_uuid(name, form['version'])}"
            self.assertEqual(shown.get(key), name[len(PREFIX):], name)
        self.assertEqual(len(shown), len(prefixed))

    def test_keeps_the_names_and_so_the_uuids_the_config_uses(self):
        # The consultation's uuid, as the app config, reports and flags name it.
        consultation = forms()['rhd_consultation.json']
        self.assertEqual(form_uuid(consultation['name'], consultation['version']), '4b063fc7-996f-3001-8500-8940e201be8f')

    def test_no_form_heading_or_window_title_names_a_form_by_its_old_name(self):
        old = {f['name'] for f in forms().values() if f['name'].startswith(PREFIX)}
        for file, form in forms().items():
            for page in form['pages']:
                self.assertNotIn(page['label'], old, file)
            # The encounter type keeps its name: it is not a form name.
            body = {k: v for k, v in form.items() if k not in ('name', 'encounter')}
            self.assertFalse(old & set(strings(body)), file)

    def test_headings_and_window_titles_match_the_shown_name(self):
        shown = messages()
        uuids = {form_uuid(f['name'], f['version']) for f in forms().values() if f['name'].startswith(PREFIX)}
        for file, form in forms().items():
            name = shown.get(f"ui.i18n.Form.name.{form_uuid(form['name'], form['version'])}")
            if name:
                self.assertIn(name, [page['label'] for page in form['pages']], file)
            for props in workspace_props(form):
                uuid_ = props.get('form', {}).get('uuid')
                if uuid_ in uuids:
                    self.assertEqual(props['form'].get('display'), shown[f'ui.i18n.Form.name.{uuid_}'], file)
                    self.assertEqual(props.get('workspaceTitle'), shown[f'ui.i18n.Form.name.{uuid_}'], file)

    def test_the_stack_mounts_the_messages(self):
        self.assertIn(
            './distro/configuration/messageproperties:/openmrs/distribution/openmrs_config/messageproperties:ro',
            COMPOSE.read_text(),
        )


if __name__ == '__main__':
    unittest.main()
