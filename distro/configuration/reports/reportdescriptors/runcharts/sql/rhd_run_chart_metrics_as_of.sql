-- =============================================================================
-- RHD Run Chart Metrics (as of a date)
-- ACT 2.0's runchart_record metrics (scheduled_record_calcs.py create_clinic_daily_record), as of the end date.
-- One row per clinic, a patient counting at both their clinics, and one row with no clinic_uuid counting each patient once.
-- Parameter: @endDate
-- The single-date form of rhd_run_chart_metrics.sql, which gives every point of a range in one pass: the run charts read
-- that one, and tests/reports/run_chart_points.py checks the two agree. active_registrants_on_bpg counts the patients the
-- one-pass row lists in bpg_patient_ids; active_registrants_adherent reads ACT Core's adherence rows as of its last run.
-- =============================================================================
WITH registrant AS (
    -- The latest RHD Registry enrolment by the end date, and whether it is open then
    SELECT pp.patient_id, (pp.date_completed IS NULL OR DATE(pp.date_completed) > DATE(@endDate)) AS active
    FROM patient_program pp
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    -- Not dead on the end date, as the care cascade counts
    JOIN person p ON p.person_id = pp.patient_id AND p.voided = 0
     AND NOT (p.dead = 1 AND (p.death_date IS NULL OR DATE(p.death_date) <= DATE(@endDate)))
    WHERE pp.voided = 0
      AND DATE(pp.date_enrolled) <= DATE(@endDate)
      AND NOT EXISTS (
          SELECT 1 FROM patient_program later
          WHERE later.patient_id = pp.patient_id AND later.program_id = pp.program_id AND later.voided = 0
            AND DATE(later.date_enrolled) <= DATE(@endDate)
            AND (later.date_enrolled > pp.date_enrolled
                 OR (later.date_enrolled = pp.date_enrolled AND later.patient_program_id > pp.patient_program_id))
      )
),
clinic_patient AS (
    SELECT DISTINCT l.uuid AS clinic_uuid, r.patient_id
    FROM registrant r
    JOIN person_attribute pa ON pa.person_id = r.patient_id AND pa.voided = 0
     AND pa.person_attribute_type_id IN (SELECT person_attribute_type_id FROM person_attribute_type
                                          WHERE uuid IN ('fe261119-2911-5b36-be40-8f9827826987',
                                                         '695f2990-236f-5d7c-b8aa-ddbdb22400f4'))
    JOIN location l ON l.location_id = pa.value
    UNION ALL
    SELECT NULL, r.patient_id FROM registrant r
),
-- Each active patient's latest Diagnosis group with a Category, not answered inactive or secondary, as the care cascade takes it
diagnosis AS (
    SELECT g.person_id, g.obs_id, g.obs_datetime
    FROM obs g
    JOIN registrant r ON r.patient_id = g.person_id AND r.active
    WHERE g.voided = 0 AND g.obs_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
      AND g.concept_id = (SELECT concept_id FROM concept WHERE uuid = '594b4495-36dc-52a6-9810-15a9e2e2dcb9')
      AND EXISTS (SELECT 1 FROM obs has_cat WHERE has_cat.obs_group_id = g.obs_id AND has_cat.voided = 0
                  AND has_cat.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1a5aa050-661d-5e89-95d7-c1eba476df22'))
      AND NOT EXISTS (
          SELECT 1 FROM obs x
          WHERE x.obs_group_id = g.obs_id AND x.voided = 0
            AND ((x.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'b1b5d279-8013-5ae4-83a7-0f2bd9bc8457')
                  AND x.value_coded = (SELECT concept_id FROM concept WHERE uuid = '1066AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))
              OR (x.concept_id = (SELECT concept_id FROM concept WHERE uuid = '97c025b2-f42c-5c53-8aaa-0506c8dd3774')
                  AND x.value_coded = (SELECT concept_id FROM concept WHERE uuid = 'af45fb2a-ed18-5beb-935e-8e4d92df2dac'))))
),
rhd AS (
    SELECT d.person_id AS patient_id FROM diagnosis d
    JOIN obs cat ON cat.obs_group_id = d.obs_id AND cat.voided = 0
     AND cat.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1a5aa050-661d-5e89-95d7-c1eba476df22')
     AND cat.value_coded = (SELECT concept_id FROM concept WHERE uuid = '4e529463-2036-5327-ad69-7cbd39df86a1')
    WHERE NOT EXISTS (SELECT 1 FROM diagnosis later
                      WHERE later.person_id = d.person_id
                        AND (later.obs_datetime > d.obs_datetime OR (later.obs_datetime = d.obs_datetime AND later.obs_id > d.obs_id)))
),
-- The regimens in the latest consultation recording one, without a Date Stopped, as the care cascade reads them
sap_encounter AS (
    SELECT o.person_id,
           SUBSTRING_INDEX(GROUP_CONCAT(o.encounter_id ORDER BY o.obs_datetime DESC, o.obs_id DESC), ',', 1) AS encounter_id
    FROM obs o
    JOIN rhd r ON r.patient_id = o.person_id
    WHERE o.voided = 0 AND o.value_coded IS NOT NULL AND o.obs_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
      AND o.concept_id = (SELECT concept_id FROM concept WHERE uuid = '668e0221-8b41-5669-9ad8-78e193d42494')
    GROUP BY o.person_id
),
sap_in_force AS (
    SELECT o.person_id, ans.uuid AS regimen_uuid
    FROM sap_encounter s
    JOIN obs o ON o.person_id = s.person_id AND o.encounter_id = s.encounter_id AND o.voided = 0 AND o.value_coded IS NOT NULL
     AND o.concept_id = (SELECT concept_id FROM concept WHERE uuid = '668e0221-8b41-5669-9ad8-78e193d42494')
    JOIN concept ans ON ans.concept_id = o.value_coded
    WHERE NOT EXISTS (SELECT 1 FROM obs st WHERE st.obs_group_id = o.obs_group_id AND st.voided = 0
                        AND st.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'd75edc42-3213-5a06-9228-4e5735b9594b'))
),
prescribed AS (
    SELECT DISTINCT person_id FROM sap_in_force
    WHERE regimen_uuid IN ('50be4b26-6c5b-5aaa-9254-3bfd313b4522','2f3ee632-dd14-51b0-a4ec-de10e7958019',
                           '91230c88-6a90-5d45-af50-fa6155fe5dd7','b9884219-358a-594b-94f5-f8a8863a25f3',
                           'f2e06eb2-5c25-5e53-9e01-246112d05976','fb8b6676-689b-5daa-83f7-1456210c587f',
                           'f6f25d63-bd1a-51cb-9596-e74a19759429','1af922b8-acee-56c8-b184-eaef4e58e23a')
),
bpg AS (
    SELECT DISTINCT person_id FROM sap_in_force
    WHERE regimen_uuid IN ('50be4b26-6c5b-5aaa-9254-3bfd313b4522','2f3ee632-dd14-51b0-a4ec-de10e7958019',
                           '91230c88-6a90-5d45-af50-fa6155fe5dd7')
),
-- Every consultation by the end date of the active patients, and whether it is their latest
all_consultation AS (
    SELECT e.encounter_id, e.patient_id, e.encounter_datetime,
           NOT EXISTS (SELECT 1 FROM encounter later
                       WHERE later.patient_id = e.patient_id AND later.voided = 0
                         AND later.encounter_type = e.encounter_type
                         AND later.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
                         AND (later.encounter_datetime > e.encounter_datetime
                              OR (later.encounter_datetime = e.encounter_datetime AND later.encounter_id > e.encounter_id))) AS latest
    FROM encounter e
    JOIN registrant r ON r.patient_id = e.patient_id AND r.active
    WHERE e.voided = 0
      AND e.encounter_type = (SELECT encounter_type_id FROM encounter_type WHERE uuid = 'c2503561-c00d-5460-8157-43d594472b4a')
      AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
),
-- Each interventional recommendation, as rhd_medical_optimisation.sql counts it
recommendation AS (
    SELECT c.encounter_id, c.patient_id, c.latest,
           -- Completed is only read on a latest consultation, as ACT 2.0 counted its recommendations
           (c.latest AND (
               EXISTS (SELECT 1 FROM obs done
                       WHERE done.obs_group_id = g.obs_id AND done.voided = 0
                         AND done.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1632f8dc-195d-5d67-a52e-6c7a057cb536')
                         AND done.value_coded IN ((SELECT CAST(property_value AS UNSIGNED) FROM global_property WHERE property = 'concept.true'),
                                                  (SELECT concept_id FROM concept WHERE uuid = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA')))
               -- Or the procedure recorded on Procedures and Outcomes on or after the consultation's day (AR-162)
               OR EXISTS (
                   SELECT 1 FROM obs pd
                   JOIN encounter pd_e ON pd_e.encounter_id = pd.encounter_id AND pd_e.voided = 0
                   LEFT JOIN obs pd_d ON pd_d.encounter_id = pd_e.encounter_id AND pd_d.voided = 0
                       AND pd_d.concept_id = (SELECT concept_id FROM concept WHERE uuid = '6cbb5176-144a-576b-9b3d-c9e9d6bc5f5a')
                   WHERE pd.person_id = c.patient_id AND pd.voided = 0
                     AND pd.concept_id IN ((SELECT concept_id FROM concept WHERE uuid = '46f4af80-b783-59f4-beb1-81144ccf3084'),
                                           (SELECT concept_id FROM concept WHERE uuid = 'bb4a77ee-836a-57e7-a262-632fa22288d2'))
                     AND pd.value_coded = proc.value_coded
                     AND DATE(COALESCE(pd_d.value_datetime, pd_e.encounter_datetime)) >= DATE(c.encounter_datetime)
                     AND DATE(COALESCE(pd_d.value_datetime, pd_e.encounter_datetime)) <= DATE(@endDate)))) AS completed
    FROM all_consultation c
    JOIN obs g ON g.encounter_id = c.encounter_id AND g.voided = 0 AND g.obs_group_id IS NULL
     AND g.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'ce93d393-1df5-587f-bf11-c373eac2ccf4')
    -- The recommended procedure is the group's member with the group's concept
    LEFT JOIN obs proc ON proc.obs_group_id = g.obs_id AND proc.voided = 0 AND proc.concept_id = g.concept_id
    -- A Procedure Type of None records that no intervention is recommended
    WHERE NOT EXISTS (SELECT 1 FROM obs typ
                      WHERE typ.obs_group_id = g.obs_id AND typ.voided = 0
                        AND typ.concept_id = (SELECT concept_id FROM concept WHERE uuid = '3a576b80-744a-59ee-9515-d9fdca06f3d7')
                        AND typ.value_coded = (SELECT concept_id FROM concept WHERE uuid = '1107AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))
),
-- The consultations in the 365 days to the end date, each with whether an echo fell in the 13 months to it
consultation AS (
    SELECT c.patient_id,
           EXISTS (SELECT 1 FROM encounter echo
                   JOIN encounter_type et ON et.encounter_type_id = echo.encounter_type AND et.uuid = '730f5ec2-7102-55d0-8602-2d792844f245'
                   WHERE echo.patient_id = c.patient_id AND echo.voided = 0
                     AND echo.encounter_datetime >= DATE_SUB(DATE(c.encounter_datetime), INTERVAL 394 DAY)
                     AND echo.encounter_datetime < DATE_ADD(DATE(c.encounter_datetime), INTERVAL 1 DAY)) AS with_echo,
           EXISTS (SELECT 1 FROM recommendation rc WHERE rc.encounter_id = c.encounter_id) AS with_recommendation
    FROM all_consultation c
    WHERE c.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 365 DAY)
),
-- Each registrant's measures; adherence is ACT Core's rows as of its last run
measure AS (
    SELECT r.patient_id, r.active,
           r.active AND (
               EXISTS (SELECT 1 FROM encounter e
                       JOIN encounter_type et ON et.encounter_type_id = e.encounter_type AND et.uuid = 'c2503561-c00d-5460-8157-43d594472b4a'
                       WHERE e.patient_id = r.patient_id AND e.voided = 0
                         AND e.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 210 DAY)
                         AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY))
               OR EXISTS (SELECT 1 FROM obs d
                          WHERE d.person_id = r.patient_id AND d.voided = 0
                            AND d.concept_id = (SELECT concept_id FROM concept WHERE uuid = '183fb30e-b861-5b7c-806f-7118a40f2b51')
                            AND d.value_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 210 DAY)
                            AND d.value_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY))) AS seen,
           EXISTS (SELECT 1 FROM prescribed pr WHERE pr.person_id = r.patient_id) AS prescribed,
           EXISTS (SELECT 1 FROM bpg b WHERE b.person_id = r.patient_id) AS on_bpg,
           (EXISTS (SELECT 1 FROM bpg b WHERE b.person_id = r.patient_id) AND adh.adherence >= 0.8) IS TRUE AS adherent,
           (SELECT COUNT(*) FROM recommendation rc
            WHERE rc.patient_id = r.patient_id AND rc.latest AND rc.completed) AS completed
    FROM registrant r
    LEFT JOIN actcore_prophylaxis_adherence adh ON adh.patient_id = r.patient_id
),
visits AS (
    SELECT patient_id, COUNT(*) AS total, SUM(with_echo) AS with_echo, SUM(with_recommendation) AS with_recommendation
    FROM consultation GROUP BY patient_id
)
SELECT cp.clinic_uuid,
       COUNT(*)                                AS total_registrants,
       SUM(m.active)                           AS active_registrants,
       SUM(m.seen)                             AS active_registrants_seen_last_7_months,
       SUM(m.prescribed)                       AS active_registrants_prescribed_prophylaxis,
       SUM(m.adherent)                         AS active_registrants_adherent,
       SUM(m.on_bpg)                           AS active_registrants_on_bpg,
       COALESCE(SUM(v.total), 0)               AS consultation_visit_total,
       COALESCE(SUM(v.with_echo), 0)           AS consultation_visits_with_echocardiogram_resulted,
       COALESCE(SUM(v.with_recommendation), 0) AS consultation_visits_with_intervention,
       SUM(m.completed)                        AS interventions_completed
FROM clinic_patient cp
JOIN measure m ON m.patient_id = cp.patient_id
LEFT JOIN visits v ON v.patient_id = cp.patient_id
GROUP BY cp.clinic_uuid
UNION ALL
-- The all-clinics row with nobody registered, so a check against the one-pass report has a row to compare
SELECT NULL, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
WHERE NOT EXISTS (SELECT 1 FROM registrant)
ORDER BY clinic_uuid
