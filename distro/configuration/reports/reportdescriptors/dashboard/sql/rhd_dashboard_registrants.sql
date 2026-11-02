-- =============================================================================
-- RHD Dashboard Registrants
-- The Dashboard's registrant status, and the sex, age band and disease of the active registrants, as counts.
-- Rows: breakdown (status, sex, age, disease), label, patients.
-- Parameters: @endDate; @cardiacClinic and @primaryCareClinic, location uuids, each counting only its patients when
-- set; @clinics, location uuids separated by commas, counting only the patients either of whose clinics is one of them.
-- =============================================================================
WITH registrant AS (
    -- Each patient's latest RHD Registry enrolment by the end date, as the RHD Patient List lists one row per patient
    SELECT pp.patient_program_id, pp.patient_id, pp.date_completed, p.gender, p.birthdate, p.dead, p.death_date
    FROM patient_program pp
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    JOIN patient pat ON pat.patient_id = pp.patient_id AND pat.voided = 0
    JOIN person p ON p.person_id = pp.patient_id AND p.voided = 0
    WHERE pp.voided = 0
      AND DATE(pp.date_enrolled) <= DATE(@endDate)
      AND NOT EXISTS (
          SELECT 1 FROM patient_program later
          WHERE later.patient_id = pp.patient_id AND later.program_id = pp.program_id AND later.voided = 0
            AND DATE(later.date_enrolled) <= DATE(@endDate)
            AND (later.date_enrolled > pp.date_enrolled
                 OR (later.date_enrolled = pp.date_enrolled AND later.patient_program_id > pp.patient_program_id))
      )
      AND (@cardiacClinic IS NULL OR @cardiacClinic = '' OR EXISTS (
          SELECT 1 FROM person_attribute pa
          JOIN location l ON l.location_id = pa.value AND l.uuid = @cardiacClinic
          WHERE pa.person_id = pp.patient_id AND pa.voided = 0
            AND pa.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE uuid = 'fe261119-2911-5b36-be40-8f9827826987')
      ))
      AND (@primaryCareClinic IS NULL OR @primaryCareClinic = '' OR EXISTS (
          SELECT 1 FROM person_attribute pa
          JOIN location l ON l.location_id = pa.value AND l.uuid = @primaryCareClinic
          WHERE pa.person_id = pp.patient_id AND pa.voided = 0
            AND pa.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE uuid = '695f2990-236f-5d7c-b8aa-ddbdb22400f4')
      ))
      AND (@clinics IS NULL OR @clinics = '' OR EXISTS (
          SELECT 1 FROM person_attribute pa
          JOIN location l ON l.location_id = pa.value AND FIND_IN_SET(l.uuid, @clinics) > 0
          WHERE pa.person_id = pp.patient_id AND pa.voided = 0
            AND pa.person_attribute_type_id IN (SELECT person_attribute_type_id FROM person_attribute_type
                                                 WHERE uuid IN ('fe261119-2911-5b36-be40-8f9827826987',
                                                                '695f2990-236f-5d7c-b8aa-ddbdb22400f4'))
      ))
),
-- Enrolled on the end date and alive then, as the registry's lists count a patient to act on.
active AS (
    SELECT r.* FROM registrant r
    WHERE (r.date_completed IS NULL OR DATE(r.date_completed) > DATE(@endDate))
      AND NOT (r.dead = 1 AND (r.death_date IS NULL OR DATE(r.death_date) <= DATE(@endDate)))
),
-- The terminal state an enrolment ended in by the end date: O3 closes every state when an enrolment completes, so
-- the open state is never the ended one. The workflow's initial Active state is not terminal and is never read here.
ended_state AS (
    SELECT ps.patient_program_id, cn.name
    FROM patient_state ps
    JOIN program_workflow_state pws ON pws.program_workflow_state_id = ps.state AND pws.terminal = 1
    JOIN concept_name cn ON cn.concept_id = pws.concept_id AND cn.locale = 'en' AND cn.locale_preferred = 1 AND cn.voided = 0
    WHERE ps.voided = 0 AND DATE(ps.start_date) <= DATE(@endDate)
      AND NOT EXISTS (
          SELECT 1 FROM patient_state later
          JOIN program_workflow_state lws ON lws.program_workflow_state_id = later.state AND lws.terminal = 1
          WHERE later.patient_program_id = ps.patient_program_id AND later.voided = 0
            AND DATE(later.start_date) <= DATE(@endDate)
            AND (later.start_date > ps.start_date OR (later.start_date = ps.start_date AND later.patient_state_id > ps.patient_state_id))
      )
),
-- Each patient's latest Diagnosis group by the end date with a Category and not answered inactive or secondary, as
-- the care cascade reads it.
diagnosis AS (
    SELECT g.person_id, g.obs_id, g.obs_datetime
    FROM obs g
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
latest_diagnosis AS (
    SELECT d.person_id, d.obs_id FROM diagnosis d
    WHERE NOT EXISTS (SELECT 1 FROM diagnosis later
                      WHERE later.person_id = d.person_id
                        AND (later.obs_datetime > d.obs_datetime OR (later.obs_datetime = d.obs_datetime AND later.obs_id > d.obs_id)))
),
-- The category, and for Rheumatic Heart Disease/Rheumatic Fever its details in name order, one label per patient.
disease AS (
    SELECT a.patient_id,
           CASE
               WHEN cat.value_coded IS NULL THEN 'No diagnosis yet'
               WHEN cat_concept.uuid <> '4e529463-2036-5327-ad69-7cbd39df86a1' THEN cat_name.name
               ELSE COALESCE((
                   SELECT GROUP_CONCAT(dn.name ORDER BY dn.name SEPARATOR ', ')
                   FROM obs det
                   JOIN concept_name dn ON dn.concept_id = det.value_coded
                       AND dn.locale = 'en' AND dn.locale_preferred = 1 AND dn.voided = 0
                   WHERE det.obs_group_id = ld.obs_id AND det.voided = 0
                     AND det.concept_id IN ((SELECT concept_id FROM concept WHERE uuid = 'cfe17bb5-4a76-5f3a-9e1c-7b1e9b84a8e3'),
                                            (SELECT concept_id FROM concept WHERE uuid = 'd3f6e1a2-9c5b-5e84-8f2d-1a6c7b9e0d4f'),
                                            (SELECT concept_id FROM concept WHERE uuid = 'b7a2c4d8-5e91-5f3a-8c6d-2b9e4f7a1c0d'),
                                            (SELECT concept_id FROM concept WHERE uuid = 'e9f3a5c7-6b82-5d4e-9f1a-3c7d8e2b5f4a'))
                     -- Acute rheumatic fever beside an RHD stage counts under the stage.
                     AND NOT (det.value_coded = (SELECT concept_id FROM concept WHERE uuid = 'cbfcf051-bee3-549d-b233-e5be0e7d691a')
                              AND EXISTS (SELECT 1 FROM obs stage WHERE stage.obs_group_id = det.obs_group_id AND stage.voided = 0
                                          AND stage.concept_id = det.concept_id AND stage.value_coded <> det.value_coded))
               ), 'RHD, details not recorded')
           END AS label
    FROM active a
    LEFT JOIN latest_diagnosis ld ON ld.person_id = a.patient_id
    LEFT JOIN obs cat ON cat.obs_group_id = ld.obs_id AND cat.voided = 0
        AND cat.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1a5aa050-661d-5e89-95d7-c1eba476df22')
    LEFT JOIN concept cat_concept ON cat_concept.concept_id = cat.value_coded
    LEFT JOIN concept_name cat_name ON cat_name.concept_id = cat.value_coded
        AND cat_name.locale = 'en' AND cat_name.locale_preferred = 1 AND cat_name.voided = 0
)
SELECT 'status' AS breakdown,
       CASE
           WHEN a.patient_id IS NOT NULL THEN 'Active'
           WHEN es.name IS NOT NULL THEN es.name
           -- A death the enrolment does not record, under the name of the workflow's own terminal state for one
           WHEN r.dead = 1 AND (r.death_date IS NULL OR DATE(r.death_date) <= DATE(@endDate)) THEN 'Deceased'
           ELSE 'No status recorded'
       END AS label,
       COUNT(*) AS patients
FROM registrant r
LEFT JOIN active a ON a.patient_program_id = r.patient_program_id
LEFT JOIN ended_state es ON es.patient_program_id = r.patient_program_id
GROUP BY label
UNION ALL
SELECT 'sex', CASE gender WHEN 'F' THEN 'Female' WHEN 'M' THEN 'Male' WHEN 'O' THEN 'Other' ELSE 'Not recorded' END,
       COUNT(*)
FROM active
GROUP BY 2
UNION ALL
-- Age on the end date; a missing birth date is Age unknown, where ACT 2.0 counted it 40+.
SELECT 'age',
       CASE
           WHEN birthdate IS NULL THEN 'Age unknown'
           WHEN TIMESTAMPDIFF(YEAR, birthdate, DATE(@endDate)) < 10 THEN '0-9'
           WHEN TIMESTAMPDIFF(YEAR, birthdate, DATE(@endDate)) < 20 THEN '10-19'
           WHEN TIMESTAMPDIFF(YEAR, birthdate, DATE(@endDate)) < 40 THEN '20-39'
           ELSE '40+'
       END,
       COUNT(*)
FROM active
GROUP BY 2
UNION ALL
SELECT 'disease', label, COUNT(*)
FROM disease
GROUP BY label
