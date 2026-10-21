-- =============================================================================
-- RHD Dashboard Care
-- ACT 2.0's dashboard procedural waitlist and medical optimisation (dashboard_query.py get_basic_stats), one row per
-- measure, label and grouping with its count:
--   waitlist             open recommendations of the latest consultation, by procedure and urgency
--   performed            procedures recorded completed, mitral balloon valvuloplasty and all
--   medicalOptimisation  active patients answering Yes or No to each of ACT 2.0's medical optimisation questions
-- Parameters: @endDate; @cardiacClinic and @primaryCareClinic, location uuids, each counting only its patients when set
-- =============================================================================
WITH active AS (
    SELECT DISTINCT pp.patient_id
    FROM patient_program pp
    -- Enrolled in the RHD Registry on the end date and not completed by then, as the care cascade counts Active
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    JOIN person p ON p.person_id = pp.patient_id AND p.voided = 0
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
),
-- Each active patient's latest RHD Consultation Visit by the end date
latest_consultation AS (
    SELECT e.patient_id, e.encounter_id
    FROM encounter e
    JOIN form f ON f.form_id = e.form_id AND f.uuid = '4b063fc7-996f-3001-8500-8940e201be8f'
    JOIN active a ON a.patient_id = e.patient_id
    WHERE e.voided = 0 AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
      AND NOT EXISTS (
          SELECT 1 FROM encounter later
          WHERE later.patient_id = e.patient_id AND later.form_id = e.form_id AND later.voided = 0
            AND later.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
            AND (later.encounter_datetime > e.encounter_datetime
                 OR (later.encounter_datetime = e.encounter_datetime AND later.encounter_id > e.encounter_id))
      )
),
-- A recommendation is completed when its Completed answer is CIEL Yes, or core's True on answers saved before the form
-- used CIEL, as the Procedural Waiting List reads it.
recommendation AS (
    SELECT g.person_id AS patient_id, g.obs_id, g.encounter_id, proc_concept.uuid AS procedure_uuid, urg.value_coded AS urgency_id,
           EXISTS (
               SELECT 1 FROM obs done
               WHERE done.obs_group_id = g.obs_id AND done.voided = 0
                 AND done.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1632f8dc-195d-5d67-a52e-6c7a057cb536')
                 AND done.value_coded IN ((SELECT CAST(property_value AS UNSIGNED) FROM global_property WHERE property = 'concept.true'),
                                          (SELECT concept_id FROM concept WHERE uuid = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))
           ) AS completed
    FROM obs g
    JOIN active a ON a.patient_id = g.person_id
    JOIN encounter e ON e.encounter_id = g.encounter_id AND e.voided = 0
     AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
    LEFT JOIN obs proc ON proc.obs_group_id = g.obs_id AND proc.voided = 0 AND proc.concept_id = g.concept_id
    LEFT JOIN concept proc_concept ON proc_concept.concept_id = proc.value_coded
    LEFT JOIN obs urg ON urg.obs_group_id = g.obs_id AND urg.voided = 0
     AND urg.concept_id = (SELECT concept_id FROM concept WHERE uuid = '7b8eda07-34b6-55f2-ab6c-1b295f41918b')
    WHERE g.voided = 0 AND g.obs_group_id IS NULL
      AND g.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'ce93d393-1df5-587f-bf11-c373eac2ccf4')
),
-- The Procedural Waiting List's rows: open recommendations of the latest consultation, of patients who have not died
waitlist AS (
    SELECT r.patient_id, r.procedure_uuid, r.urgency_id
    FROM recommendation r
    JOIN latest_consultation lc ON lc.encounter_id = r.encounter_id
    JOIN person p ON p.person_id = r.patient_id AND p.dead = 0
    WHERE NOT r.completed
),
-- Each procedure a patient has had recorded completed, once
performed AS (
    SELECT DISTINCT patient_id, procedure_uuid FROM recommendation WHERE completed
),
-- On warfarin: the latest consultation recording a Cardiac Medication lists Warfarin, as ACT 2.0's Prescribed Warfarin
warfarin AS (
    SELECT DISTINCT w.person_id AS patient_id
    FROM obs w
    WHERE w.voided = 0
      AND w.concept_id = (SELECT concept_id FROM concept WHERE uuid = '0734567e-4f0a-5090-9d74-b953921a30e6')
      AND w.value_coded = (SELECT concept_id FROM concept WHERE uuid = '5e97fe35-58df-4925-bba7-7c49d75268a1')
      AND w.encounter_id = (
          SELECT m.encounter_id FROM obs m
          JOIN active a ON a.patient_id = m.person_id
          WHERE m.person_id = w.person_id AND m.voided = 0
            AND m.concept_id = w.concept_id AND m.obs_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
          ORDER BY m.obs_datetime DESC, m.obs_id DESC LIMIT 1
      )
),
-- ACT 2.0's windows: seen in 7 months (210 days) by a consultation or a BPG injection, an echo in 13 months (395 days)
-- and an INR in 3 months (90 days), each up to the end date
optimisation AS (
    SELECT a.patient_id,
           (EXISTS (SELECT 1 FROM encounter e
                    JOIN encounter_type et ON et.encounter_type_id = e.encounter_type AND et.uuid = 'c2503561-c00d-5460-8157-43d594472b4a'
                    WHERE e.patient_id = a.patient_id AND e.voided = 0
                      AND e.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 209 DAY)
                      AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY))
            OR EXISTS (SELECT 1 FROM obs d
                       WHERE d.person_id = a.patient_id AND d.voided = 0
                         AND d.concept_id = (SELECT concept_id FROM concept WHERE uuid = '183fb30e-b861-5b7c-806f-7118a40f2b51')
                         AND d.value_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 209 DAY)
                         AND d.value_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY))) AS retained,
           EXISTS (SELECT 1 FROM encounter e
                   JOIN encounter_type et ON et.encounter_type_id = e.encounter_type AND et.uuid = '730f5ec2-7102-55d0-8602-2d792844f245'
                   WHERE e.patient_id = a.patient_id AND e.voided = 0
                     AND e.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 394 DAY)
                     AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)) AS echo,
           EXISTS (SELECT 1 FROM waitlist w WHERE w.patient_id = a.patient_id) AS recommended,
           CASE WHEN EXISTS (SELECT 1 FROM warfarin w WHERE w.patient_id = a.patient_id) THEN
               EXISTS (SELECT 1 FROM encounter e
                       JOIN encounter_type et ON et.encounter_type_id = e.encounter_type AND et.uuid = 'b4bb88a3-9a04-5142-85bd-bb63c270f632'
                       WHERE e.patient_id = a.patient_id AND e.voided = 0
                         AND e.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 89 DAY)
                         AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)) END AS inr
    FROM active a
)
SELECT 'waitlist' AS measure,
       CASE WHEN w.procedure_uuid IN ('af9429ff-1b76-55f3-81ca-a9f775d93fb4','aca1be99-d090-5078-be63-81353ae89195')
                THEN 'Mitral balloon valvuloplasty'
            WHEN w.procedure_uuid IN ('7af8595d-407e-5705-bd8a-812735e2f188','efc4d7fc-eae5-5f81-be72-750c616c82b0',
                                      '3b1bec9d-85f2-50aa-ad74-5b7bf920e8de','a76e4d83-18c0-5ed8-b039-03d137ed70ea')
                THEN 'Mitral valve surgery'
            WHEN w.procedure_uuid IN ('cd9c582a-71f9-5441-97a8-6d50d7dc15c8','32bababb-a833-5bab-8cb7-5c5a5644c590',
                                      'f7e76d81-d3ce-5759-bf0d-6fda118cac70','6ba15d4b-921d-52f4-9d56-aaed9df33239')
                THEN 'Aortic valve surgery'
            ELSE 'Other' END AS label,
       urg_name.name AS grouping,
       COUNT(*) AS patients
FROM waitlist w
LEFT JOIN concept_name urg_name ON urg_name.concept_id = w.urgency_id AND urg_name.locale = 'en'
 AND urg_name.locale_preferred = 1 AND urg_name.voided = 0
GROUP BY label, grouping
UNION ALL
SELECT 'performed', 'Mitral balloon valvuloplasty', NULL, COUNT(*) FROM performed
 WHERE procedure_uuid IN ('af9429ff-1b76-55f3-81ca-a9f775d93fb4','aca1be99-d090-5078-be63-81353ae89195')
UNION ALL
SELECT 'performed', 'All procedures', NULL, COUNT(*) FROM performed
UNION ALL
SELECT 'medicalOptimisation', 'Retained in care', IF(retained, 'Yes', 'No'), COUNT(*) FROM optimisation GROUP BY retained
UNION ALL
SELECT 'medicalOptimisation', 'Echocardiogram', IF(echo, 'Yes', 'No'), COUNT(*) FROM optimisation GROUP BY echo
UNION ALL
SELECT 'medicalOptimisation', 'Procedural recommendation', IF(recommended, 'Yes', 'No'), COUNT(*) FROM optimisation GROUP BY recommended
UNION ALL
SELECT 'medicalOptimisation', 'Procedures completed', 'Yes', COUNT(*) FROM performed
UNION ALL
SELECT 'medicalOptimisation', 'Procedures completed', 'No', COUNT(*) FROM waitlist
UNION ALL
SELECT 'medicalOptimisation', 'INR within 3 months', IF(inr, 'Yes', 'No'), COUNT(*) FROM optimisation
 WHERE inr IS NOT NULL GROUP BY inr
