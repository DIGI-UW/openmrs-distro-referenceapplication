-- =============================================================================
-- RHD Run Chart Metrics
-- ACT 2.0's runchart_record metrics (scheduled_record_calcs.py create_clinic_daily_record) as of every point of a range, in one pass.
-- For each point: one row per clinic, a patient counting at both their clinics, and one row with no clinic_uuid counting each patient once.
-- Parameters: @startDate and @endDate, and @points (day, week or month).
-- A point is the figure as of the last day of its period, the last point as of the end date: the end, then a day back,
-- or the Sunday before, or the last day of the month before, while the day is not before the start.
-- Adherence is not counted here: bpg_patient_ids lists the active patients on an in-force BPG regimen as of the point,
-- and ACT Core replays each one's dose history to that day.
-- No line ends with a semicolon, which the report runner would read as the end of a statement.
-- =============================================================================
WITH RECURSIVE point AS (
    SELECT DATE(@endDate) AS d
    UNION ALL
    SELECT CASE @points
               WHEN 'day' THEN d - INTERVAL 1 DAY
               WHEN 'month' THEN LAST_DAY(d - INTERVAL 1 MONTH)
               ELSE d - INTERVAL (WEEKDAY(d) + 1) DAY
           END
    FROM point
    WHERE CASE @points
               WHEN 'day' THEN d - INTERVAL 1 DAY
               WHEN 'month' THEN LAST_DAY(d - INTERVAL 1 MONTH)
               ELSE d - INTERVAL (WEEKDAY(d) + 1) DAY
           END >= DATE(@startDate)
),
-- Each RHD Registry enrolment with the one after it, so the latest by a day is the one the next is after
enrolment AS (
    SELECT pp.patient_id, pp.date_enrolled, pp.date_completed,
           LEAD(pp.date_enrolled) OVER (PARTITION BY pp.patient_id ORDER BY pp.date_enrolled, pp.patient_program_id) AS next_enrolled
    FROM patient_program pp
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    WHERE pp.voided = 0
),
-- The latest enrolment by each point, and whether it is open then; not dead on the point, as the care cascade counts
registrant AS (
    SELECT pt.d, e.patient_id, (e.date_completed IS NULL OR DATE(e.date_completed) > pt.d) AS active
    FROM point pt
    JOIN enrolment e ON DATE(e.date_enrolled) <= pt.d AND (e.next_enrolled IS NULL OR DATE(e.next_enrolled) > pt.d)
    JOIN person p ON p.person_id = e.patient_id AND p.voided = 0
     AND NOT (p.dead = 1 AND (p.death_date IS NULL OR DATE(p.death_date) <= pt.d))
),
clinic_patient AS (
    SELECT DISTINCT r.d, l.uuid AS clinic_uuid, r.patient_id
    FROM registrant r
    JOIN person_attribute pa ON pa.person_id = r.patient_id AND pa.voided = 0
     AND pa.person_attribute_type_id IN (SELECT person_attribute_type_id FROM person_attribute_type
                                          WHERE uuid IN ('fe261119-2911-5b36-be40-8f9827826987',
                                                         '695f2990-236f-5d7c-b8aa-ddbdb22400f4'))
    JOIN location l ON l.location_id = pa.value
    UNION ALL
    SELECT r.d, NULL, r.patient_id FROM registrant r
),
-- Each Diagnosis group with a Category, not answered inactive or secondary, with the one after it
diagnosis_group AS (
    SELECT g.person_id, g.obs_id, g.obs_datetime,
           LEAD(g.obs_datetime) OVER (PARTITION BY g.person_id ORDER BY g.obs_datetime, g.obs_id) AS next_datetime
    FROM obs g
    WHERE g.voided = 0
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
-- Each active patient whose latest diagnosis by the point has the RHD category, as the care cascade takes it
rhd AS (
    SELECT r.d, r.patient_id
    FROM registrant r
    JOIN diagnosis_group dg ON dg.person_id = r.patient_id
     AND dg.obs_datetime < DATE_ADD(r.d, INTERVAL 1 DAY)
     AND (dg.next_datetime IS NULL OR dg.next_datetime >= DATE_ADD(r.d, INTERVAL 1 DAY))
    JOIN obs cat ON cat.obs_group_id = dg.obs_id AND cat.voided = 0
     AND cat.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1a5aa050-661d-5e89-95d7-c1eba476df22')
     AND cat.value_coded = (SELECT concept_id FROM concept WHERE uuid = '4e529463-2036-5327-ad69-7cbd39df86a1')
    WHERE r.active
),
-- Each regimen answer with the one after it, so the latest consultation recording one by a point is known
sap_obs AS (
    SELECT o.person_id, o.encounter_id, o.obs_datetime, o.obs_id,
           LEAD(o.obs_datetime) OVER (PARTITION BY o.person_id ORDER BY o.obs_datetime, o.obs_id) AS next_datetime
    FROM obs o
    WHERE o.voided = 0 AND o.value_coded IS NOT NULL
      AND o.concept_id = (SELECT concept_id FROM concept WHERE uuid = '668e0221-8b41-5669-9ad8-78e193d42494')
),
sap_encounter AS (
    SELECT r.d, r.patient_id, s.encounter_id
    FROM rhd r
    JOIN sap_obs s ON s.person_id = r.patient_id
     AND s.obs_datetime < DATE_ADD(r.d, INTERVAL 1 DAY)
     AND (s.next_datetime IS NULL OR s.next_datetime >= DATE_ADD(r.d, INTERVAL 1 DAY))
),
-- The regimens in that consultation without a Date Stopped, as the care cascade reads them
sap_in_force AS (
    SELECT s.d, s.patient_id AS person_id, ans.uuid AS regimen_uuid
    FROM sap_encounter s
    JOIN obs o ON o.person_id = s.patient_id AND o.encounter_id = s.encounter_id AND o.voided = 0 AND o.value_coded IS NOT NULL
     AND o.concept_id = (SELECT concept_id FROM concept WHERE uuid = '668e0221-8b41-5669-9ad8-78e193d42494')
    JOIN concept ans ON ans.concept_id = o.value_coded
    WHERE NOT EXISTS (SELECT 1 FROM obs st WHERE st.obs_group_id = o.obs_group_id AND st.voided = 0
                        AND st.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'd75edc42-3213-5a06-9228-4e5735b9594b'))
),
prescribed AS (
    SELECT DISTINCT d, person_id FROM sap_in_force
    WHERE regimen_uuid IN ('50be4b26-6c5b-5aaa-9254-3bfd313b4522','2f3ee632-dd14-51b0-a4ec-de10e7958019',
                           '91230c88-6a90-5d45-af50-fa6155fe5dd7','b9884219-358a-594b-94f5-f8a8863a25f3',
                           'f2e06eb2-5c25-5e53-9e01-246112d05976','fb8b6676-689b-5daa-83f7-1456210c587f',
                           'f6f25d63-bd1a-51cb-9596-e74a19759429','1af922b8-acee-56c8-b184-eaef4e58e23a')
),
bpg AS (
    SELECT DISTINCT d, person_id FROM sap_in_force
    WHERE regimen_uuid IN ('50be4b26-6c5b-5aaa-9254-3bfd313b4522','2f3ee632-dd14-51b0-a4ec-de10e7958019',
                           '91230c88-6a90-5d45-af50-fa6155fe5dd7')
),
-- Each interventional recommendation a consultation records, as rhd_medical_optimisation.sql counts it, with
-- whether it was marked completed with the consultation; a Procedure Type of None records that none is recommended
recommendation_group AS (
    SELECT g.encounter_id, g.obs_id, proc.value_coded AS procedure_concept,
           EXISTS (SELECT 1 FROM obs done
                   WHERE done.obs_group_id = g.obs_id AND done.voided = 0
                     AND done.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1632f8dc-195d-5d67-a52e-6c7a057cb536')
                     AND done.value_coded IN ((SELECT CAST(property_value AS UNSIGNED) FROM global_property WHERE property = 'concept.true'),
                                              (SELECT concept_id FROM concept WHERE uuid = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))) AS done
    FROM obs g
    -- The recommended procedure is the group's member with the group's concept
    LEFT JOIN obs proc ON proc.obs_group_id = g.obs_id AND proc.voided = 0 AND proc.concept_id = g.concept_id
    WHERE g.voided = 0 AND g.obs_group_id IS NULL
      AND g.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'ce93d393-1df5-587f-bf11-c373eac2ccf4')
      AND NOT EXISTS (SELECT 1 FROM obs typ
                      WHERE typ.obs_group_id = g.obs_id AND typ.voided = 0
                        AND typ.concept_id = (SELECT concept_id FROM concept WHERE uuid = '3a576b80-744a-59ee-9515-d9fdca06f3d7')
                        AND typ.value_coded = (SELECT concept_id FROM concept WHERE uuid = '1107AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))
),
-- Each consultation with the one after it, so the latest by a point is known, and whether an echo fell in the
-- 13 months to it and whether it records an interventional recommendation, which do not depend on the point
consultation_encounter AS (
    SELECT e.encounter_id, e.patient_id, e.encounter_datetime,
           LEAD(e.encounter_datetime) OVER (PARTITION BY e.patient_id ORDER BY e.encounter_datetime, e.encounter_id) AS next_datetime,
           EXISTS (SELECT 1 FROM encounter echo
                   JOIN encounter_type et ON et.encounter_type_id = echo.encounter_type AND et.uuid = '730f5ec2-7102-55d0-8602-2d792844f245'
                   WHERE echo.patient_id = e.patient_id AND echo.voided = 0
                     AND echo.encounter_datetime >= DATE_SUB(DATE(e.encounter_datetime), INTERVAL 394 DAY)
                     AND echo.encounter_datetime < DATE_ADD(DATE(e.encounter_datetime), INTERVAL 1 DAY)) AS with_echo,
           EXISTS (SELECT 1 FROM recommendation_group rg WHERE rg.encounter_id = e.encounter_id) AS with_recommendation
    FROM encounter e
    WHERE e.voided = 0
      AND e.encounter_type = (SELECT encounter_type_id FROM encounter_type WHERE uuid = 'c2503561-c00d-5460-8157-43d594472b4a')
),
-- The active patients' consultations each point counts: those in the 365 days to it, and the latest by it
all_consultation AS (
    SELECT r.d, c.encounter_id, c.patient_id, c.encounter_datetime, c.with_echo, c.with_recommendation,
           (c.next_datetime IS NULL OR c.next_datetime >= DATE_ADD(r.d, INTERVAL 1 DAY)) AS latest
    FROM registrant r
    JOIN consultation_encounter c ON c.patient_id = r.patient_id AND c.encounter_datetime < DATE_ADD(r.d, INTERVAL 1 DAY)
    WHERE r.active
      AND (c.encounter_datetime >= DATE_SUB(r.d, INTERVAL 365 DAY)
           OR c.next_datetime IS NULL OR c.next_datetime >= DATE_ADD(r.d, INTERVAL 1 DAY))
),
-- Each recommendation of a counted consultation, and whether it is completed by the point: only on a latest
-- consultation, as ACT 2.0 counted its recommendations, with the consultation or by a procedure recorded on
-- Procedures and Outcomes on or after the consultation's day and by the point (AR-162)
recommendation AS (
    SELECT c.d, c.encounter_id, c.patient_id, c.latest,
           (c.latest AND (rg.done OR EXISTS (
               SELECT 1 FROM obs pd
               JOIN encounter pd_e ON pd_e.encounter_id = pd.encounter_id AND pd_e.voided = 0
               LEFT JOIN obs pd_d ON pd_d.encounter_id = pd_e.encounter_id AND pd_d.voided = 0
                   AND pd_d.concept_id = (SELECT concept_id FROM concept WHERE uuid = '6cbb5176-144a-576b-9b3d-c9e9d6bc5f5a')
               WHERE pd.person_id = c.patient_id AND pd.voided = 0
                 AND pd.concept_id IN ((SELECT concept_id FROM concept WHERE uuid = '46f4af80-b783-59f4-beb1-81144ccf3084'),
                                       (SELECT concept_id FROM concept WHERE uuid = 'bb4a77ee-836a-57e7-a262-632fa22288d2'))
                 AND pd.value_coded = rg.procedure_concept
                 AND DATE(COALESCE(pd_d.value_datetime, pd_e.encounter_datetime)) >= DATE(c.encounter_datetime)
                 AND DATE(COALESCE(pd_d.value_datetime, pd_e.encounter_datetime)) <= c.d))) AS completed
    FROM all_consultation c
    JOIN recommendation_group rg ON rg.encounter_id = c.encounter_id
),
-- The consultations in the 365 days to each point
consultation AS (
    SELECT c.d, c.patient_id, c.with_echo, c.with_recommendation
    FROM all_consultation c
    WHERE c.encounter_datetime >= DATE_SUB(c.d, INTERVAL 365 DAY)
),
-- The active patients seen in the 210 days to each point: a consultation, or a screening date recorded, in them
seen AS (
    SELECT DISTINCT r.d, r.patient_id
    FROM registrant r
    JOIN consultation_encounter c ON c.patient_id = r.patient_id
     AND c.encounter_datetime >= DATE_SUB(r.d, INTERVAL 210 DAY) AND c.encounter_datetime < DATE_ADD(r.d, INTERVAL 1 DAY)
    WHERE r.active
    UNION
    SELECT DISTINCT r.d, r.patient_id
    FROM registrant r
    JOIN obs dt ON dt.person_id = r.patient_id AND dt.voided = 0
     AND dt.concept_id = (SELECT concept_id FROM concept WHERE uuid = '183fb30e-b861-5b7c-806f-7118a40f2b51')
     AND dt.value_datetime >= DATE_SUB(r.d, INTERVAL 210 DAY) AND dt.value_datetime < DATE_ADD(r.d, INTERVAL 1 DAY)
    WHERE r.active
),
completed AS (
    SELECT d, patient_id, COUNT(*) AS recommendations
    FROM recommendation WHERE latest AND completed
    GROUP BY d, patient_id
),
-- Each registrant's measures as of each point
measure AS (
    SELECT r.d, r.patient_id, r.active,
           (sn.patient_id IS NOT NULL) AS seen,
           (pr.person_id IS NOT NULL) AS prescribed,
           (b.person_id IS NOT NULL) AS on_bpg,
           COALESCE(cm.recommendations, 0) AS completed
    FROM registrant r
    LEFT JOIN seen sn ON sn.d = r.d AND sn.patient_id = r.patient_id
    LEFT JOIN prescribed pr ON pr.d = r.d AND pr.person_id = r.patient_id
    LEFT JOIN bpg b ON b.d = r.d AND b.person_id = r.patient_id
    LEFT JOIN completed cm ON cm.d = r.d AND cm.patient_id = r.patient_id
),
visits AS (
    SELECT d, patient_id, COUNT(*) AS total, SUM(with_echo) AS with_echo, SUM(with_recommendation) AS with_recommendation
    FROM consultation GROUP BY d, patient_id
)
SELECT cp.d                                     AS point_date,
       cp.clinic_uuid,
       COUNT(*)                                AS total_registrants,
       SUM(m.active)                           AS active_registrants,
       SUM(m.seen)                             AS active_registrants_seen_last_7_months,
       SUM(m.prescribed)                       AS active_registrants_prescribed_prophylaxis,
       COALESCE(SUM(v.total), 0)               AS consultation_visit_total,
       COALESCE(SUM(v.with_echo), 0)           AS consultation_visits_with_echocardiogram_resulted,
       COALESCE(SUM(v.with_recommendation), 0) AS consultation_visits_with_intervention,
       SUM(m.completed)                        AS interventions_completed,
       GROUP_CONCAT(DISTINCT CASE WHEN m.on_bpg THEN m.patient_id END ORDER BY m.patient_id SEPARATOR ',') AS bpg_patient_ids
FROM clinic_patient cp
JOIN measure m ON m.d = cp.d AND m.patient_id = cp.patient_id
LEFT JOIN visits v ON v.d = cp.d AND v.patient_id = cp.patient_id
GROUP BY cp.d, cp.clinic_uuid
ORDER BY cp.d, cp.clinic_uuid
