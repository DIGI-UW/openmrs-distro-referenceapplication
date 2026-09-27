# Critical data flag rules

Regression tests for the RHD flag definitions in `distro/configuration/flags/`, which carry over
the "critical data flags" from the ACT 2.0 registry. A critical data flag marks a field that
should have been completed on a form and was not.

    python3 test_flag_rules.py       # 44 cases: does each rule match the right patients
    python3 test_flag_lifecycle.py   # 13 cases: does a flag clear when the gap is filled
    python3 test_gap_queries.py      # 7 cases: does each flag's gap query name the encounter to complete

All three talk to `http://localhost/openmrs` as `admin` and seed their own patients under the
identifiers `rhd95xxx`, `rhd96xxx` and `rhd97xxx`. Each voids what an earlier run recorded for its
patients before it seeds them: the rule cases are dated relative to today, so a patient seeded on an
earlier day would decide a boundary case on stale dates, and the lifecycle run ends with each gap
filled, so it would otherwise never see the flag raised. So all three are safe to re-run. The rule
and lifecycle tests evaluate flags by re-saving each flag definition over REST, which is what the
patientflags module does on a definition change, so they do not wait for the scheduled task.

`test_gap_queries.py` checks the gap queries in
`distro/configuration/globalproperties/rhd_flag_gap_queries.xml` through the rhdflags gap look-up,
which needs the rhdflags omod described in the top-level README.

`test_flag_rules.py` covers each rule's positive cases, its negatives, and the boundary a day
either side of every time window. Defects it caught, all now fixed:

- the 30-day follow-up rule chased patients who had died in hospital, which ACT 2.0 excludes
- the death rule tested CIEL's `1066` for a boolean No, but a boolean obs stores whatever
  `concept.false` points at, which is a different concept here, so that branch never matched
- the lifecycle test itself only passed the first time, which is how the reset above came about
- the overdue rule used every BPG regimen ever prescribed, so a patient switched to oral
  prophylaxis, or from Q21 to Q28, stayed overdue on the old interval; it now reads the latest
- the lost to follow-up rule counted any encounter of the consultation type, which nine forms
  share (Consent and Allergies among them); it now counts only the RHD Consultation Visit and
  RHD Consultation Update forms, as ACT 2.0 counted only consultation visits

What these do not cover: the scheduled refresh and the list sync, which belong to the
[rhdflags module](https://github.com/mherman22/openmrs-module-rhd-flags) and need a running
scheduler rather than a REST call.
