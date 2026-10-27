# Backend startup errors (27 October 2026)

What the backend logs as an error when it starts, and why. Taken from a fresh local stack
(`docker compose up` on `main` at `7c563ad1`, image `itechuw/openmrs-reference-application-3-backend:nightly`,
OpenMRS 2.8.10-SNAPSHOT, MariaDB 10.11.7) on 27 October 2026. The database was empty, so the setup wizard
ran and every Liquibase changeset ran for the first time.

The backend came up healthy. The ACT RHD content (clinics, forms, concepts, flags, scheduled tasks) loaded
without errors. Item 1 can make some saves fail. Item 2 was reference-application demo content that did not load; it is now fixed for
fresh setups. Items 3 to 6 are noise.

| # | Logged as | Source | Harmful? |
|---|---|---|---|
| 1 | `ERROR AuditBackfillDao ... diverging from base table ... must be widened manually` (95 lines) and `ERROR AuditBackfillService ... Column sync failed for 95 audit table(s)` | Audit Log module (`auditlogweb` 1.1.0-SNAPSHOT) | Yes, for 24 columns |
| 2 | `ERROR BaseCsvLoader ... could not be constructed or saved` (49 rows across 6 files) and `ERROR BaseFileLoader ... Could not find a form named 'Test Form 1'` | Initializer loading the reference-application demo content | Demo content only; fixed |
| 3 | `ERROR BrokerService.checkSystemUsageLimits ... Temporary Store limit is 51200 mb ... only has 44324 mb` | ActiveMQ inside the Event module | No |
| 4 | `java.lang.IllegalStateException: Filters cannot be added to context [/openmrs]` | OpenMRS core `WebComponentRegistrar` | No |
| 5 | `SEVERE HostConfig.beforeStart Unable to create directory for deployment: [/usr/local/tomcat/conf/Catalina/localhost]` | Tomcat | No |
| 6 | `ERROR CommonsLoggingOutput ... Attribute "moduleId" must be declared for element type "allow"` (and `"signatures"`) | DWR, the legacy UI's AJAX library | No |

## 1. Audit tables narrower than the tables they audit

**What it says.** For 95 tables, the Envers audit copy (`<table>_AUD`) has a column whose type differs from
the base table, and the Audit Log module refuses to change it automatically. It then reports that column
sync failed for all 95 and that "audited writes to them may fail".

**Why it happens.** The two sets of tables are built from different sources:

- Base tables come from the Liquibase changelogs of core and the modules, which have widened columns over
  the years (`description` to `TEXT`, privileges to `VARCHAR(255)`, `uuid` as `CHAR(38)`).
- Audit tables are created by Hibernate Envers from the Hibernate mappings (`hibernate.integration.envers.enabled=true`
  in the runtime properties). The mappings carry their own `length` values, which were never updated when
  Liquibase widened the column, and Hibernate always writes `uuid` as `VARCHAR(38)` and text as `LONGTEXT`.

On startup the module compares the two and only alters an audit column automatically when it is missing.
Any type difference, in either direction, is logged as an error and left for a person to fix.

**Which differences matter.** Of the differences logged:

| Kind | Count | Effect |
|---|---|---|
| `uuid` is `VARCHAR(38)`, base is `CHAR(38)` | 91 | None. Same length. |
| Audit column is wider than the base (`LONGTEXT` vs `TEXT`, `DATETIME` vs `DATE`, `BIGINT` vs `INT`, `DATETIME` vs `TIMESTAMP`) | 74 | None. Every base value fits. |
| **Audit column is narrower than the base** | **24** | **A save can fail.** |

The database runs with `STRICT_TRANS_TABLES`, so when a value fits the base column but is too long for the
audit column, the Envers insert fails with "Data too long" and the whole transaction rolls back. The user
sees the save fail, not just a missing audit row. The narrower columns:

| Audit column | Audit type | Base type |
|---|---|---|
| `form_AUD.description` | VARCHAR(1024) | TEXT |
| `encounter_type_AUD.description` | VARCHAR(1024) | TEXT |
| `concept_reference_source_AUD.description` | VARCHAR(1024) | TEXT |
| `program_AUD.description` | VARCHAR(500) | TEXT |
| `order_set_AUD.description` | VARCHAR(255) | VARCHAR(1000) |
| `serialized_object_AUD.retire_reason` | VARCHAR(255) | VARCHAR(1000) |
| `notification_template_AUD.template` | VARCHAR(255) | TEXT |
| `notification_template_AUD.recipients` | VARCHAR(255) | VARCHAR(512) |
| `scheduler_task_config_AUD.name` | VARCHAR(50) | VARCHAR(255) |
| `scheduler_task_config_AUD.schedulable_class` | VARCHAR(1024) | TEXT |
| `hl7_in_queue_AUD.hl7_source_key` | VARCHAR(1024) | TEXT |
| `hl7_in_error_AUD.hl7_source_key` | VARCHAR(1024) | TEXT |
| `concept_reference_term_AUD.version` | VARCHAR(50) | VARCHAR(255) |
| `concept_stop_word_AUD.locale` | VARCHAR(20) | VARCHAR(50) |
| `encounter_diagnosis_AUD.certainty` | VARCHAR(50) | VARCHAR(255) |
| `privilege_AUD.privilege` | VARCHAR(250) | VARCHAR(255) |
| `role_privilege_AUD.privilege` | VARCHAR(250) | VARCHAR(255) |
| `encounter_type_AUD.view_privilege`, `edit_privilege` | VARCHAR(250) | VARCHAR(255) |
| `global_property_AUD.view_privilege`, `edit_privilege`, `delete_privilege` | VARCHAR(250) | VARCHAR(255) |
| `person_attribute_type_AUD.edit_privilege` | VARCHAR(250) | VARCHAR(255) |
| `patient_identifier_type_AUD.format_description` | VARCHAR(250) | VARCHAR(255) |

None of the data loaded today is long enough to hit these (the longest scheduler task name is 45
characters, privilege 51, encounter type description 162, concept source description 397). The ones most
likely to be hit in practice are a scheduler task name over 50 characters, a privilege name of 251 to 255
characters, and a form, encounter type or concept source description over 1024 characters.

**Also worth knowing.**

- The module also logged `Created 1 missing Envers audit table(s)` and added 102 missing columns (for
  example `form_AUD.xslt`, `form_AUD.template` and six columns on `referral_order_AUD`). Those are the
  automatic part working as intended.
- The global property `auditlogweb.auditColumnSync.versionFingerprint` is still empty after startup. The
  sync appears to record the fingerprint only when it succeeds, so the same 95 errors are expected again on every
  restart until the columns are widened (not yet confirmed by a restart).

**Fix.** Widen the 24 narrower audit columns to the base type, once per database, with `ALTER TABLE ...
MODIFY` (for example `ALTER TABLE scheduler_task_config_AUD MODIFY name VARCHAR(255)`). This could be
shipped as a Liquibase changeset in ACT Core, or raised upstream with the Audit Log module so it widens
audit columns automatically when the audit type is narrower. The 91 `uuid` differences and the 74 wider
columns need no change, but the module will keep logging them; quieting that needs a module change to
treat "audit is at least as wide" as compatible.

## 2. Reference-application demo content that does not load

**What it says.** After the OCL concept import (19:18 on this stack, 12 minutes after startup), Initializer
loads the rest of the configuration folder. For six files it
prints the rows it could not save, with a stack trace per row, and an "ERROR SUMMARY" per file. All six
files come from the upstream `referenceapplication` and `referenceapplication-demo` content packages, not
from ACT. Every ACT file (`rhd_*`) loaded.

| File | Rows not saved | Error |
|---|---|---|
| `concepts/referenceapplication-demo/programs_workflows_states_core-demo.csv` | 6 of 6 | `Concept Source is required` |
| `concepts/referenceapplication-demo/diagnosis_core-demo.csv` | 34 of 44 | `Concept Source is required` |
| `programworkflows/referenceapplication-demo/programworkflows-package-hiv-core_demo.csv` | 3 of 3 | `NullPointerException ... "concept" is null` |
| `programworkflowstates/referenceapplication-demo/programworkflowstates_demo-package-core_demo.csv` | 3 of 3 | `No workflow could be fetched from the CSV line` |
| `queues/referenceapplication-demo/queues-core_demo.csv` | 2 of 2 | `location: queue.location.null` |
| `fhirconceptsources/referenceapplication/fhirconceptsources.csv` | 1 of 5 | `concept source 'ANCDAK' not found` |
| `ampathformstranslations/referenceapplication-showcase/test_form_1_translations_fr-showcase.json` | whole file | `Could not find a form named 'Test Form 1'` |

There are three separate causes.

**a. The demo files name concept sources that are hidden.** The demo CSVs map concepts to `SNOMED MVP`,
`ICD-10` and `ANCDAK`. The content package defines those three sources in
`conceptsources/referenceapplication/reference_conceptsources.csv`, but `docker-compose.yml` mounts
`./distro/configuration/conceptsources` over the whole `conceptsources` folder, so that file is never seen.
The OCL import later creates similar sources under other names (`SNOMED-MVP`, `ICD-10-WHO`, `ANC-DAK`), which
Initializer does not match. The repo already worked around this for one name: its own
`reference_conceptsources.csv` adds a `SNOMED CT` alias. The other three had no alias.

It then cascades through the HIV demo program:

- The six program concepts (`HIV treatment status`, `Program status`, `Lost to follow-up`, ...) are never
  created.
- The program workflow rows refer to `HIV treatment status`, which does not exist, so Initializer hits a
  `NullPointerException` while naming the workflow.
- The workflow state rows refer to those workflows, which were not created.

Of the 34 diagnosis rows, 21 are concepts that already exist from the OCL Diagnoses Starter Kit, so only
the CSV's changes to them (the French names and the "(ICD code)" suffix) are lost. The other 13 are not
created. The PMTCT and HIV program concepts are also missing.

**b. The demo queues point at a location the stack hides.** Both demo queues (Outpatient Triage, Outpatient
Consultation) are at `Outpatient Clinic` (`44c3efb0-2583-4c80-a79e-1f756a03c0a1`). That location is defined
in the demo package's `locations/referenceapplication-demo/locations-core_demo.csv`. `docker-compose.yml`
mounts `./distro/configuration/locations` over the whole of `openmrs_config/locations`, rather than into a
subfolder as it does for concepts and programs (`.../concepts/rhd`, `.../programs/rhd`). The mount replaces
the folder, so the demo locations file is not visible and only `rhd_uganda_clinics.csv` loads. With no
`Outpatient Clinic`, the queue has no location and fails validation.

**c. The showcase form translation has no form.** `docker-compose.yml` also mounts
`./distro/configuration/ampathforms` over the whole `ampathforms` folder, so the showcase forms (including
`Test Form 1`) are hidden and only the `rhd_*.json` forms load. The French translation for `Test Form 1`
is in a different folder (`ampathformstranslations`), which is not mounted over, so it still loads and
cannot find its form.

**Effect.** ACT does not use any of this content: the HIV program, the demo queues, the demo diagnoses
or the ANC FHIR mapping. Nothing ACT users see is affected. The cost was noise: about 3,000 log lines that
made real errors harder to spot.

**Fixed.**

- (a) `distro/configuration/conceptsources/reference_conceptsources.csv` now also defines `SNOMED MVP`,
  `ICD-10` and `ANCDAK`, with the content package's own UUIDs, so they are the same sources if the package
  file is ever loaded.
- (b) and (c) Hiding the demo locations and forms is intentional (ACT ships its own clinics and forms), so
  `docker-compose.yml` now also mounts two empty folders, `distro/configuration/queues` and
  `distro/configuration/ampathformstranslations`, over the demo queues and the showcase translation.

Checked on a throwaway stack with a fresh database: no Initializer errors. The HIV demo workflows and
states, the demo diagnoses and all five FHIR concept sources load; no demo queues are created; the RHD
clinics and scheduled tasks are unchanged.

Databases that already exist do not change. Initializer stores a checksum for a file even when its rows
fail, so it does not retry the unchanged demo files; only fresh setups are quieter.

## 3. ActiveMQ temporary store larger than the disk

**What it says.** ActiveMQ, the message broker the Event module embeds, is configured with a 100 GB store
and a 50 GB temporary store. The Docker volume `/openmrs/data` has about 44 GB free, so the broker logs a
warning for the store and an error for the temporary store.

**Why it happens.** These are ActiveMQ's built-in defaults; the Event module does not lower them. The broker
shrinks the limits to the space available and carries on.

**Effect.** None at this scale. Events are small and short-lived. On a server whose disk is nearly full the
broker would block producers once the space ran out, but the database would be in trouble first.

## 4. "Filters cannot be added to context"

**What it says.** A stack trace from `org.openmrs.web.WebComponentRegistrar.setServletContext` while modules
are started.

**Why it happens.** When OpenMRS starts its modules it refreshes the Spring context. The refresh re-creates
`WebComponentRegistrar`, which tries to register the web filters with Tomcat again. Tomcat only allows
filters to be added before the web application has finished starting, so it throws. The filters were
already registered on the first pass, so nothing is missing.

**Effect.** None. This is a long-standing OpenMRS core message seen on every 2.x startup that loads modules.

## 5. Tomcat cannot create its deployment directory

**What it says.** `Unable to create directory for deployment: [/usr/local/tomcat/conf/Catalina/localhost]`.

**Why it happens.** The image runs Tomcat as a non-root user, and `conf/` belongs to root. Tomcat tries to
create a folder for per-application context files. The image does not use such files (the OpenMRS war is
deployed from `webapps/`).

**Effect.** None.

## 6. DWR "Attribute moduleId must be declared"

**What it says.** Two lines, `Line=4 Attribute "moduleId" must be declared for element type "allow"` and
`Line=384 ... "signatures"`, logged as each module's legacy web layer starts.

**Why it happens.** OpenMRS adds a `moduleId` attribute to the DWR configuration it builds from the
modules, but the DWR document type it validates against has no such attribute. DWR's parser reports it and
then reads the file anyway.

**Effect.** None. DWR only serves the legacy 2.x admin pages.

## Warnings that look alarming but are expected

- **`Task 'RHD Patient Flag Refresh' not found`** (and `RHD Prophylaxis Adherence Refresh`, `RHD Run Chart
  Snapshot`): ACT Core looks its scheduled tasks up before creating them on first start. All three exist and
  are started afterwards.

- **`Unable to find a runtime properties file ... Initial setup is needed`**: first start on an empty
  volume. The setup wizard runs automatically and writes the file.
- **`Continuing past ... precondition error: Empty result set, expected one row`** (four times, FHIR2
  changesets): these changesets look up the CIEL and LOINC concept sources and the default duration unit,
  which do not exist yet on an empty database. The changesets are written to continue in that case.
- **`Specified key was too long; max key length is 3072 bytes`** (Metadata Mapping changeset
  `metadatamapping-2016-02-07-1310-b-non-mysql`): MariaDB is treated as "non-MySQL", so the index on
  `metadata_class` is created over the full column. MariaDB trims the index to its maximum key length and
  reports it; the index is created.
- **`Due to mariadb SQL limitations, modifyDataType will lose primary key/...`**: Liquibase's generic
  caution for MariaDB. The affected changesets restate the settings they need.
- **`Task 'Queue Module - Auto Close ... Queue Entries' not found`**: the Queue module looks its tasks up
  before creating them on first start.
- **`Address hierarchy configuration file has changed, reloading it`** and **`The exisiting address ...
  is being wiped`**: Initializer loading `addresshierarchy.csv` for the first time (9 seconds).
- **`IdgenTask ... Not running scheduled task. DaemonToken = null; enabled = false`**: the ID generation
  module's pool-filling task is not enabled. Identifiers are still generated on demand at registration.
- **`No @Authorized annotation applies to ...`**: core and REST methods that are deliberately unguarded.
- **`Name 'PK_HL7_IN_ERROR' ignored for PRIMARY key`**: MariaDB ignores names on primary keys.
