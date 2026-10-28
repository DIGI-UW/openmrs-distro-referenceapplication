#!/usr/bin/env python3
"""
Checks the report privileges the distribution's configuration declares, with the standard library only.

Every ACT report names the privilege that runs it under `config: privilege:` in its descriptor, and ACT Core
refuses a user who lacks it; a report that names none is for administrators only. So a descriptor, the privilege
table and the role table have to agree. Run with: python3 -m unittest discover -s tests/config
"""
import csv
import pathlib
import re
import unittest

CONFIGURATION = pathlib.Path(__file__).resolve().parents[2] / 'distro' / 'configuration'
DESCRIPTORS = sorted((CONFIGURATION / 'reports' / 'reportdescriptors').glob('*/*.yml'))
PREFIX = 'Task: act.report.'

# Instance wide counts with no patient in them: nothing for a clinic to limit
INSTANCE_WIDE = {'rhdInstanceKpis', 'rhdRunChartMetrics'}

# Report privileges no role is granted, on purpose: ACT Core runs the report only in its scheduler task and
# snapshot thread, where the check is skipped, and no screen runs it as a user. Administrators and super users hold it.
ADMIN_ONLY = {PREFIX + 'runChartMetrics'}


def privilege_of(descriptor):
    match = re.search(r'^config:\s*\n\s+privilege:\s*"([^"]+)"\s*$', descriptor.read_text(), re.M)
    return match.group(1) if match else None


def declared_privileges():
    with open(CONFIGURATION / 'privileges' / 'rhd_privileges.csv', newline='') as handle:
        return {row['Privilege name'] for row in csv.DictReader(handle)}


def granted_privileges():
    granted = set()
    with open(CONFIGURATION / 'roles' / 'act_roles.csv', newline='') as handle:
        for row in csv.DictReader(handle):
            granted.update(name for name in row['Privileges'].split(';') if name)
    return granted


class ReportPrivileges(unittest.TestCase):

    def test_there_are_descriptors_to_check(self):
        self.assertGreaterEqual(len(DESCRIPTORS), 22)

    def test_every_descriptor_names_a_privilege_the_privilege_table_defines(self):
        defined = declared_privileges()
        for descriptor in DESCRIPTORS:
            privilege = privilege_of(descriptor)
            self.assertIsNotNone(privilege, '%s names no privilege under config: privilege:' % descriptor.name)
            self.assertTrue(privilege.startswith(PREFIX), '%s: %s' % (descriptor.name, privilege))
            self.assertIn(privilege, defined, '%s names %s, which rhd_privileges.csv does not define' % (descriptor.name, privilege))

    def test_every_report_privilege_is_run_by_a_descriptor_and_granted_to_a_role(self):
        named = {privilege_of(descriptor) for descriptor in DESCRIPTORS}
        granted = granted_privileges()
        for privilege in sorted(p for p in declared_privileges() if p.startswith(PREFIX)):
            self.assertIn(privilege, named, '%s guards no report' % privilege)
            if privilege in ADMIN_ONLY:
                self.assertNotIn(privilege, granted, '%s is listed as admin only but a role grants it' % privilege)
            else:
                self.assertIn(privilege, granted, '%s is granted to no role' % privilege)

    def test_no_role_grants_a_report_privilege_that_is_not_defined(self):
        defined = declared_privileges()
        for privilege in sorted(p for p in granted_privileges() if p.startswith(PREFIX)):
            self.assertIn(privilege, defined, '%s is granted but not defined' % privilege)

    def test_every_report_but_the_instance_wide_ones_takes_the_clinics_a_limited_user_is_held_to(self):
        for descriptor in DESCRIPTORS:
            key = re.search(r'^key:\s*(\S+)', descriptor.read_text(), re.M).group(1)
            declares = re.search(r'^\s+- key: clinics\s*$', descriptor.read_text(), re.M) is not None
            if key in INSTANCE_WIDE:
                continue
            self.assertTrue(declares, '%s declares no clinics parameter, so ACT Core cannot hold a limited user to their clinics' % key)

    def test_the_sql_of_every_report_that_takes_clinics_reads_them(self):
        for descriptor in DESCRIPTORS:
            text = descriptor.read_text()
            if re.search(r'^\s+- key: clinics\s*$', text, re.M) is None:
                continue
            sql = descriptor.parent / re.search(r'config:\s*"(sql/[^"]+\.sql)"', text).group(1)
            self.assertIn('@clinics', sql.read_text(), '%s takes clinics but %s never reads @clinics' % (descriptor.name, sql.name))


if __name__ == '__main__':
    unittest.main()
