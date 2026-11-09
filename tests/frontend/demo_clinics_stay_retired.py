#!/usr/bin/env python3
"""
Checks every clinic the demo retires stays retired on a fresh database (AR-187). Initializer runs the location tag
maps after the locations and saves each mapped location with the row's void/retire value, so a mapped clinic is
retired again by a tag map file that runs after the main one.

Usage: python3 tests/frontend/demo_clinics_stay_retired.py
"""
import csv
import pathlib
import unittest

CONFIG = pathlib.Path(__file__).resolve().parents[2] / 'distro' / 'configuration'
RETIRED = CONFIG / 'locations' / 'rhd_uganda_clinics_demo_retired.csv'
TAG_MAPS = CONFIG / 'locationtagmaps' / 'rhd_uganda_clinic_tagmaps.csv'
TAG_MAPS_RETIRED = CONFIG / 'locationtagmaps' / 'rhd_uganda_clinic_tagmaps_demo_retired.csv'


def rows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


class DemoClinicsStayRetired(unittest.TestCase):
    def test_every_mapped_retired_clinic_is_retired_again_after_the_tag_maps(self):
        retired = {r['name'] for r in rows(RETIRED) if r['void/retire'] == 'true'}
        mapped = {r['location'] for r in rows(TAG_MAPS) if r.get('void/retire', 'false') != 'true'}
        retired_again = {r['location'] for r in rows(TAG_MAPS_RETIRED) if r['void/retire'] == 'true'}
        self.assertTrue(retired & mapped)
        self.assertEqual(retired & mapped, retired_again)

    def test_the_retire_file_runs_after_the_main_tag_map_file(self):
        # Initializer orders a domain's files by path when none sets an order
        self.assertLess(str(TAG_MAPS), str(TAG_MAPS_RETIRED))

    def test_the_two_demo_clinics_are_not_retired(self):
        retired_again = {r['location'] for r in rows(TAG_MAPS_RETIRED)}
        self.assertFalse({'Uganda Heart Institute Tertiary', 'Acimi HCIII'} & retired_again)


if __name__ == '__main__':
    unittest.main()
