# Critical data flag rules

Regression tests for the RHD flag definitions in `distro/configuration/flags/`, which carry over
the "critical data flags" from the ACT 2.0 registry. A critical data flag marks a field that
should have been completed on a form and was not.

    python3 test_flag_rules.py       # 35 cases: does each rule match the right patients
    python3 test_flag_lifecycle.py   # 12 cases: does a flag clear when the gap is filled

Both talk to `http://localhost/openmrs` as `admin`, seed their own patients under the identifiers
`rhd95xxx` and `rhd96xxx`, and are safe to re-run. They evaluate flags by re-saving each flag
definition over REST, which is what the patientflags module does on a definition change, so they
do not wait for the scheduled task.

`test_flag_rules.py` covers each rule's positive cases, its negatives, and the boundary a day
either side of every time window. Two defects it caught, both now fixed:

- the 30-day follow-up rule chased patients who had died in hospital, which ACT 2.0 excludes
- the death rule tested CIEL's `1066` for a boolean No, but a boolean obs stores whatever
  `concept.false` points at, which is a different concept here, so that branch never matched

What these do not cover: the scheduled refresh and the list sync, which belong to the
[rhdflags module](https://github.com/mherman22/openmrs-module-rhd-flags) and need a running
scheduler rather than a REST call.
