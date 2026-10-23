-- =============================================================================
-- RHD Medical Optimisation Patients
-- The patients (or consultations or recommendations) behind one figure of rhd_medical_optimisation.sql, one row each, from
-- the same CTEs, so a figure's rows equal its count; tests/reports/dashboard_totals.py checks that they do.
-- Parameters: those of rhd_medical_optimisation.sql, and @measure, @done
-- =============================================================================
WITH active AS (
    SELECT DISTINCT pp.patient_id
    FROM patient_program pp
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    JOIN person p ON p.person_id = pp.patient_id AND p.voided = 0 AND p.dead = 0
    WHERE pp.voided = 0
      AND DATE(pp.date_enrolled) <= DATE(@endDate)
      AND (pp.date_completed IS NULL OR DATE(pp.date_completed) > DATE(@endDate))
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
consultation AS (
    SELECT e.encounter_id, e.patient_id, e.encounter_datetime
    FROM encounter e
    JOIN active a ON a.patient_id = e.patient_id
    WHERE e.voided = 0
      AND e.encounter_type = (SELECT encounter_type_id FROM encounter_type WHERE uuid = 'c2503561-c00d-5460-8157-43d594472b4a')
      AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
),
latest_consultation AS (
    SELECT c.encounter_id, c.patient_id
    FROM consultation c
    WHERE NOT EXISTS (SELECT 1 FROM consultation later
                      WHERE later.patient_id = c.patient_id
                        AND (later.encounter_datetime > c.encounter_datetime
                             OR (later.encounter_datetime = c.encounter_datetime AND later.encounter_id > c.encounter_id)))
),
-- Each interventional recommendation in a latest consultation, and whether it is answered Completed: CIEL Yes, or
-- core's True on answers saved before the form used CIEL, as the Procedural Waiting List reads it.
recommendation AS (
    SELECT lc.patient_id, g.obs_id,
           EXISTS (SELECT 1 FROM obs done
                   WHERE done.obs_group_id = g.obs_id AND done.voided = 0
                     AND done.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1632f8dc-195d-5d67-a52e-6c7a057cb536')
                     AND done.value_coded IN ((SELECT CAST(property_value AS UNSIGNED) FROM global_property WHERE property = 'concept.true'),
                                              (SELECT concept_id FROM concept WHERE uuid = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))) AS completed
    FROM latest_consultation lc
    JOIN obs g ON g.encounter_id = lc.encounter_id AND g.voided = 0 AND g.obs_group_id IS NULL
     AND g.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'ce93d393-1df5-587f-bf11-c373eac2ccf4')
),
echo_done AS (
    SELECT DISTINCT e.patient_id
    FROM encounter e
    JOIN active a ON a.patient_id = e.patient_id
    JOIN form f ON f.form_id = e.form_id AND f.uuid = '88e54fb0-1243-3f7a-b925-f64648ca6635'
    WHERE e.voided = 0
      AND e.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 395 DAY)
      AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
),
retained AS (
    SELECT a.patient_id
    FROM active a
    WHERE EXISTS (SELECT 1 FROM consultation c WHERE c.patient_id = a.patient_id
                    AND c.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 210 DAY))
       OR EXISTS (SELECT 1 FROM actcore_prophylaxis_adherence adh WHERE adh.patient_id = a.patient_id
                    AND DATE(adh.last_given) >= DATE_SUB(DATE(@endDate), INTERVAL 210 DAY)
                    AND DATE(adh.last_given) <= DATE(@endDate))
),
-- The latest medication answer, as RHD INR review due reads it: warfarin or the other vitamin K antagonist, not stopped.
warfarin AS (
    SELECT DISTINCT w.person_id AS patient_id
    FROM obs w
    JOIN active a ON a.patient_id = w.person_id
    WHERE w.voided = 0 AND w.obs_group_id IS NOT NULL
      AND w.concept_id = (SELECT concept_id FROM concept WHERE uuid = '0734567e-4f0a-5090-9d74-b953921a30e6')
      AND w.obs_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
      AND w.value_coded IN ((SELECT concept_id FROM concept WHERE uuid = '5e97fe35-58df-4925-bba7-7c49d75268a1'),
                            (SELECT concept_id FROM concept WHERE uuid = '3c7f8916-3ab5-5678-83c5-be7c7bb1f5e7'))
      AND NOT EXISTS (SELECT 1 FROM obs ws WHERE ws.obs_group_id = w.obs_group_id AND ws.voided = 0
                        AND ws.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'd75edc42-3213-5a06-9228-4e5735b9594b'))
      AND NOT EXISTS (SELECT 1 FROM obs w2 WHERE w2.person_id = w.person_id AND w2.voided = 0 AND w2.concept_id = w.concept_id
                        AND w2.value_coded IS NOT NULL AND w2.obs_group_id IS NOT NULL
                        AND w2.obs_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
                        AND (w2.obs_datetime > w.obs_datetime OR (w2.obs_datetime = w.obs_datetime AND w2.encounter_id > w.encounter_id)))
),
inr_done AS (
    SELECT DISTINCT e.patient_id
    FROM encounter e
    JOIN warfarin w ON w.patient_id = e.patient_id
    WHERE e.voided = 0
      AND e.encounter_type = (SELECT encounter_type_id FROM encounter_type WHERE uuid = 'b4bb88a3-9a04-5142-85bd-bb63c270f632')
      AND e.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 90 DAY)
      AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
),
-- The rows behind @measure's done (@done = 'done') or not done ('notDone'), both when @done is empty: consultations
-- one row per consultation, interventions one per recommendation, every other measure one per patient
done_or_not AS (
    SELECT 'echocardiogram' AS measure, a.patient_id, e.patient_id IS NOT NULL AS done, NULL AS date
    FROM active a LEFT JOIN echo_done e ON e.patient_id = a.patient_id
    UNION ALL
    SELECT 'retainedInCare', a.patient_id, r.patient_id IS NOT NULL, NULL
    FROM active a LEFT JOIN retained r ON r.patient_id = a.patient_id
    UNION ALL
    SELECT 'interventionAssigned', a.patient_id, x.patient_id IS NOT NULL, NULL
    FROM active a LEFT JOIN (SELECT DISTINCT patient_id FROM recommendation WHERE completed = 0) x ON x.patient_id = a.patient_id
    UNION ALL
    SELECT 'interventions', r.patient_id, r.completed = 1, NULL FROM recommendation r
    UNION ALL
    SELECT 'warfarin', w.patient_id, i.patient_id IS NOT NULL, NULL
    FROM warfarin w LEFT JOIN inr_done i ON i.patient_id = w.patient_id
    UNION ALL
    SELECT 'consultations', c.patient_id, 1, c.encounter_datetime FROM consultation c
    WHERE c.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 365 DAY)
),
figure AS (
    SELECT patient_id, IF(done, 'Done', 'Not done') AS value, date
    FROM done_or_not
    WHERE measure = @measure
      AND (@done IS NULL OR @done = '' OR (@done = 'done') = done)
)
SELECT p.uuid AS patient_uuid,
       (SELECT pi.identifier FROM patient_identifier pi
        WHERE pi.patient_id = p.person_id AND pi.voided = 0
          AND pi.identifier_type = (SELECT patient_identifier_type_id FROM patient_identifier_type
                                    WHERE uuid = '240f85fa-46e1-540e-9234-2796c623f7ea')
        ORDER BY pi.preferred DESC, pi.patient_identifier_id LIMIT 1) AS rhd_id,
       (SELECT CONCAT(pn.given_name, ' ', pn.family_name) FROM person_name pn
        WHERE pn.person_id = p.person_id AND pn.voided = 0
        ORDER BY pn.preferred DESC, pn.person_name_id LIMIT 1) AS full_name,
       p.gender AS sex,
       TIMESTAMPDIFF(YEAR, p.birthdate, DATE(@endDate)) AS age_years,
       (SELECT l.name FROM person_attribute pa JOIN location l ON l.location_id = pa.value
        WHERE pa.person_id = p.person_id AND pa.voided = 0
          AND pa.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                              WHERE uuid = 'fe261119-2911-5b36-be40-8f9827826987')
        LIMIT 1) AS cardiac_clinic,
       (SELECT l.name FROM person_attribute pa JOIN location l ON l.location_id = pa.value
        WHERE pa.person_id = p.person_id AND pa.voided = 0
          AND pa.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                              WHERE uuid = '695f2990-236f-5d7c-b8aa-ddbdb22400f4')
        LIMIT 1) AS primary_care_clinic,
       f.value AS figure_value,
       DATE(f.date) AS figure_date
FROM figure f
JOIN person p ON p.person_id = f.patient_id
ORDER BY full_name, figure_date
