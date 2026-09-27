# RHD flags: end-to-end scenarios

Gherkin scenarios for the RHD critical data flags, written to be followed by hand in a browser or
automated with a Gherkin runner.

## Setup

1. Start the stack on an empty database: `docker compose down -v && docker compose up --build`.
2. Wait for the backend to finish starting (the RHD flags are loaded by Initializer).
3. Seed the demo patients: `python3 scripts/seed-rhd-demo.py` (see `--help` for another server or
   credentials). It ends with "All 20 patients carry the flags their scenario should raise."
4. Serve the RHD frontend module, as the README's "RHD flags" section describes, and sign in at
   http://localhost:8090/openmrs/spa as `admin` at Uganda Heart Institute Tertiary.

Scenarios that change data (clearing a flag, a new patient, a hand-made flag) are independent of
each other, but each changes the patients it names; reseed on a fresh database to run them again.

| File | Covers |
|---|---|
| `flags-on-the-chart.feature` | Which seeded patients carry which flag, and how flags look |
| `worklists.feature` | The patient list per flag and its counts |
| `missing-data.feature` | The RHD workspace: form, field, days pending, Open form |
| `clearing-flags.feature` | A flag clears when the data is saved |
| `new-patient.feature` | A new patient is flagged and joins, then leaves, a worklist |
| `scheduled-refresh.feature` | The daily task and running it on demand |
| `hand-made-flags-and-lists.feature` | A flag and a list created without configuration |
