# ACT RHD Registry — Report Descriptors

This directory contains all report definitions for the ACT RHD registry. Reports are defined as
**plain YAML + SQL files** — no Java code, no custom module, no recompilation required.

---

## How it works

### The processing engine: `ReportLoader` (openmrs-module-reporting)

The class `org.openmrs.module.reporting.config.ReportLoader` (shipped inside `openmrs-module-reporting`)
is responsible for finding and loading every `.yml` file in this directory tree.

```
Server startup
     │
     ▼
ReportingModuleActivator.started()
     │
     └─▶ ReportLoader.loadReportsFromConfig()
              │
              ├─ Scans:  {appDataDir}/configuration/reports/reportdescriptors/**/*.yml
              │
              ├─ For each .yml file:
              │     Jackson (YAMLFactory) → ReportDescriptor POJO
              │     The YAML's parent directory is recorded as the SQL search root
              │
              └─ For each ReportDescriptor:
                    constructReportDefinition()   → builds ReportDefinition + SqlDataSetDefinition
                    saveReportDefinition()        → upserts by UUID (preserves old ReportRequests)
                    constructReportDesigns()      → builds CSV/XLS output wrappers
                    saveReportDesigns()           → persists output format config
```

The Initializer module copies everything under `distro/configuration/` into
`{appDataDir}/configuration/` at startup, so this directory is automatically deployed.

**Nothing else is needed.** No Java module. No Spring bean. No annotation.

---

## YAML schema

```yaml
key: uniqueCamelCaseKey           # internal lookup key
uuid: "xxxxxxxx-..."              # stable UUID — used to upsert without duplicating
name: "Human readable name"       # shown in the reporting UI
description: "What this exports"

parameters:
  - key: startDate                # referenced as :startDate in SQL
    type: java.util.Date
    label: "Start Date"
  - key: endDate
    type: java.util.Date
    label: "End Date"

datasets:
  - key: myDataset
    type: sql
    config:
      sql: "sql/my_query.sql"     # path relative to this YAML file's directory

designs:
  - type: csv                     # output format shown in reporting UI
    uuid: "yyyyyyyy-..."          # stable UUID for the ReportDesign object
```

### Parameter types supported
| YAML type | SQL placeholder |
|---|---|
| `java.util.Date` | `:startDate`, `:endDate` |
| `java.lang.Integer` | `:someParam` |
| `org.openmrs.Location` | `:location` |

### Design types supported
| `type` | Renderer class |
|---|---|
| `csv` | `CsvReportRenderer` |
| `xls` | `XlsReportRenderer` (requires `template:` path) |

---

## SQL conventions

- Parameters are referenced with a **colon prefix**: `:startDate`, `:endDate`
- SQL files live in a `sql/` subdirectory **next to** their `.yml` file
- `ReportLoader` resolves SQL paths relative to the directory containing the YAML
- All concept and encounter type lookups use **UUID sub-selects** — never hardcoded integer IDs,
  which differ between environments
- Date range pattern: `>= :startDate AND < DATE_ADD(:endDate, INTERVAL 1 DAY)` to make `:endDate` inclusive

---

## Reports in this directory

### `cascade/` — Programme-level cascade indicators

| File | UUID | Parameter | Description |
|---|---|---|---|
| `rhd_care_cascade.yml` | `9c6751ae-...` | `endDate` | 6-step funnel: Active → Prescribed → Oral → BPG → Initiated → Adherent |
| `rhd_screening_cascade.yml` | `8b257a0c-...` | `endDate` | 4-step funnel: Active → Echo pending → Confirmed → Heart disease |

> These were previously implemented as Java `@Component` classes
> (`RhdCareCascadeReportManager`, `RhdScreeningCascadeReportManager`) in
> `openmrs-module-customreports`. The SQL is identical; only the Java wrapper was removed.

---

### `patients/` — Patient registry list

| File | UUID | Parameters | Description |
|---|---|---|---|
| `rhd_patients.yml` | `f1a2b3c4-...` | `startDate`, `endDate` | One row per patient enrolled in the RHD program within the date range. Includes demographics, identifiers, diagnosis category, case detection method, penicillin allergy flag, and date of last consultation. |

---

### `visits/` — Visit-level summary

| File | UUID | Parameters | Description |
|---|---|---|---|
| `rhd_visits.yml` | `b2c3d4e5-...` | `startDate`, `endDate` | One row per OpenMRS visit containing at least one RHD encounter. Aggregates encounter types seen per visit, NYHA class, and prophylaxis regimen. |

---

### `encounters/` — Encounter-level export

| File | UUID | Parameters | Description |
|---|---|---|---|
| `rhd_encounters.yml` | `d4e5f6a7-...` | `startDate`, `endDate` | One row per encounter across all 9 RHD encounter types. Includes type-specific key fields (NYHA for consultations, INR value for INR monitoring, adverse reaction flag for BPG). |

---

### `inr/` — Anticoagulation INR monitoring

| File | UUID | Parameters | Description |
|---|---|---|---|
| `inr_monitoring.yml` | `d3a1f2b4-...` | `startDate`, `endDate` | One row per INR reading (the form uses a repeating obs group — up to 20 readings per encounter). Includes INR value, target range, date of reading, and a computed `in_therapeutic_range` flag. |

---

## Adding a new report

1. Create a subdirectory: `reportdescriptors/myreport/`
2. Write the descriptor: `reportdescriptors/myreport/myreport.yml`
3. Write the SQL: `reportdescriptors/myreport/sql/myreport.sql`
4. Generate a UUID for the report and its CSV design (e.g. `uuidgen` or any UUID v4 generator)
5. Restart OpenMRS — `ReportLoader` will pick it up automatically

The report will appear in **OpenMRS → Reporting → Browse Reports**.

---

## Encounter type UUIDs (reference)

| Name | UUID |
|---|---|
| RHD Consultation Visit | `c2503561-c00d-5460-8157-43d594472b4a` |
| RHD BPG Delivery | `04cf03db-3b8e-5020-84b0-50b06338767a` |
| RHD Echocardiogram | `730f5ec2-7102-55d0-8602-2d792844f245` |
| RHD Electrocardiogram | `64c3f35f-a3ec-59d6-8178-0ca9f068cda8` |
| RHD Hospital Admission | `181e0106-35d3-537a-a25e-18d3ebf61883` |
| RHD Pregnancy | `ce6b111e-9beb-5a91-91ad-ec5043976fd5` |
| RHD Oral Adherence | `55271793-ef37-58da-9d86-1d9092a5a809` |
| RHD Interventions and Outcomes | `c9b87090-8768-50be-987e-8ca0a8983429` |
| RHD INR Monitoring | `b4bb88a3-9a04-5142-85bd-bb63c270f632` |

## Patient identifier type UUIDs (reference)

| Name | UUID |
|---|---|
| RHD ID (primary) | `240f85fa-46e1-540e-9234-2796c623f7ea` |
| External Patient ID | `810bfaee-85de-5a81-b79c-954774076594` |
| Alternate ID | `060a2595-da89-5509-8cf4-645a8e50ad8a` |
| National ID | `fdd6f720-743b-57fc-915a-87c0f571097b` |

---

## Why not `commonreports` or a custom Java module?

| Approach | What it requires | When to use |
|---|---|---|
| **This approach (YAML + SQL)** | Text editor only | New data exports, site-specific reports |
| `commonreports` Java `ReportManager` | Java module compile + deploy | Complex logic that can't be expressed in SQL |
| `openmrs-module-customreports` | Same as above | _(deprecated by this approach)_ |

The `openmrs-module-reporting` module's `ReportLoader` was built specifically to avoid the Java
compilation cycle for straightforward SQL-based reports. The cascade, patient, visit, encounter,
and INR reports in this directory were all previously defined as Java classes and have been
migrated here.
