# ACT 3.0: the flags a patient's chart can show

Every flag is a rule the server evaluates against the patient's record. A flag shows on the patient's
chart banner and in the lists on ACT home for as long as its rule matches, and goes when the record
changes so that it no longer matches. The rules are in the distribution's configuration
(`distro/configuration/flags/rhd_flags.csv`); this page says what each one means in plain words.

## When flags refresh

- **Once a day** by default, ACT Core re-evaluates every flag for every patient and mirrors the
  results into the lists on ACT home (the interval is the scheduler's, changed in Manage Scheduler),
  and an administrator can run the same refresh at any time from Admin, Flags and adherence.
- **When a person is saved** (registration, Edit patient details, Update patient status marking a patient deceased), that patient's
  flags are re-evaluated as soon as the save commits, so a data-quality flag about registration
  clears the moment the missing field is filled.

A flag a clinician judges not to apply can be **dismissed** from the chart (Task: act.dismissFlags). A
dismissed flag stays hidden until its rule stops matching and later matches again.

## Colours

| Colour | Priority | Meaning |
|---|---|---|
| Red | RHD High | A clinical action is overdue |
| Blue | RHD Early Warning | A clinical action is due soon |
| Orange | RHD Data Quality | A required field is missing from a completed form or from registration |

## The flags

| Flag on the chart | Colour | Shows when | Clears when |
|---|---|---|---|
| BPG injection overdue | Red | The patient is on an injection regimen (Q14, Q21 or Q28 day BPG) and ACT Core's next due date, from the last injection and the regimen's interval, has passed | An injection is recorded, the regimen changes to oral or None, or prophylaxis is stopped |
| Oral prophylaxis overdue | Red | The patient is on an oral regimen and ACT Core's next due date for an oral entry has passed | An oral adherence entry is recorded, the regimen changes, or prophylaxis is stopped |
| Lost to follow-up: no data for 7 months | Red | A patient with a prescription has had no RHD Consultation Visit and no dose (injection or oral entry) for 210 days; a patient never dosed counts too. From ACT 2.0's "Needs Prophylaxis Data, red" | Any consultation or dose is recorded |
| No data for 5 months | Blue | As above, but for 150 days; at 210 days "Lost to follow-up" takes over. From ACT 2.0's "Needs Prophylaxis Data, blue" | Any consultation or dose is recorded |
| Cardiology follow-up due | Blue | The latest RHD Consultation Visit's Next Consultation Time Amount and Period, counted from that visit's date, falls within the next 30 days or has passed, and the patient is enrolled in the RHD Registry | A new consultation is recorded |
| INR review due | Blue | The latest RHD INR Monitoring's Next INR Date falls within the next 30 days or has passed, the patient is enrolled in the RHD Registry, and their latest cardiac medication is warfarin and not stopped | A new INR monitoring entry is recorded, or warfarin is stopped |
| Secondary antibiotic prophylaxis not recorded for the RHD or ARF diagnosis | Orange | Patient Information records an RHD, ARF or related diagnosis (current, not marked inactive or secondary) and no consultation has recorded a secondary antibiotic prophylaxis answer, including None. Shows from registration with a diagnosis until the first consultation. From ACT 2.0's rule 1 | A consultation records a prophylaxis regimen, or None |
| Date of Consent missing: consent is Yes | Orange | Registration says Consent Obtained is Yes but has no Date of Consent | The date is added through Edit patient details |
| Date of Patient Follow-Up due on Procedures and Outcomes | Orange | The patient was discharged more than 30 days ago and that Procedures and Outcomes encounter has no follow-up contact recorded. From ACT 2.0's rule 4 | The follow-up date is recorded on that encounter |
| INR Target missing on RHD INR Monitoring | Orange | The patient is prescribed warfarin and the INR Monitoring has no INR target | The target is recorded |
| Perfusion Issues missing on Procedures and Outcomes | Orange | A hospitalisation ended in discharge or death and Perfusion Issues was not answered | The field is answered |
| Site Infection missing on Procedures and Outcomes | Orange | As above, for Site Infection | The field is answered |
| Bacterial Sepsis missing on Procedures and Outcomes | Orange | As above, for Bacterial Sepsis | The field is answered |
| Delivery mode missing on RHD Pregnancy | Orange | The pregnancy's estimated due date passed 30 or more days ago and no delivery is recorded | The delivery is recorded |
| Death recorded on a form but not on the patient | Orange | A form records the patient's death but the patient record is not marked deceased | Update patient status on the chart (Deceased), or the form's death answer is corrected |

Flags tagged **RHD** (the red and blue ones) are decision support; flags tagged **Critical data** (the
orange ones) are the data-completeness checks carried over from ACT 2.0's critical data flags.
