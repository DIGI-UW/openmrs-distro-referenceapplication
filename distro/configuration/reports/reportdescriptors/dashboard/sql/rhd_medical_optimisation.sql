-- =============================================================================
-- RHD Medical Optimisation
-- ACT 2.0's dashboard medical optimisation (dashboard_query.py get_basic_stats, medicalOptimization), for the patients
-- active on the end date: enrolled in the RHD Registry and not completed, and alive.
-- One row per measure, with the patients for whom it is done and those for whom it is not:
--   consultations  RHD Consultation Visits in the 365 days to the end date (done only)
--   echocardiogram an RHD Echocardiogram in the 395 days (13 months) to the end date
--   retainedInCare a consultation, or a prophylaxis dose ACT Core knows of, in the 210 days (7 months) to the end date
--   interventionAssigned an interventional recommendation in the patient's latest consultation not answered Completed
--   interventions  the recommendations in active patients' latest consultations, completed or not
--   warfarin       of the patients whose latest medication answer is warfarin or another vitamin K antagonist without a
--                  Date Stopped (as the INR flags read it), those with an RHD INR Monitoring in the 90 days to the end date
-- Parameters: @endDate; @cardiacClinic and @primaryCareClinic, location uuids, each counting only its patients when set
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
    SELECT c.encounter_id, c.patient_id, c.encounter_datetime
    FROM consultation c
    WHERE NOT EXISTS (SELECT 1 FROM consultation later
                      WHERE later.patient_id = c.patient_id
                        AND (later.encounter_datetime > c.encounter_datetime
                             OR (later.encounter_datetime = c.encounter_datetime AND later.encounter_id > c.encounter_id)))
),
-- Each interventional recommendation in a latest consultation, and whether it is answered Completed: CIEL Yes, or
-- core's True on answers saved before the form used CIEL, as the Procedural Waiting List reads it. A group whose
-- Procedure Type is None records that no intervention is recommended, so it is not a recommendation.
recommendation AS (
    SELECT lc.patient_id, g.obs_id,
           EXISTS (SELECT 1 FROM obs done
                   WHERE done.obs_group_id = g.obs_id AND done.voided = 0
                     AND done.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1632f8dc-195d-5d67-a52e-6c7a057cb536')
                     AND done.value_coded IN ((SELECT CAST(property_value AS UNSIGNED) FROM global_property WHERE property = 'concept.true'),
                                              (SELECT concept_id FROM concept WHERE uuid = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA')))
           -- or the procedure recorded on Procedures and Outcomes on or after the consultation's day (AR-162)
           OR EXISTS (
               SELECT 1 FROM obs pd
               JOIN encounter pd_e ON pd_e.encounter_id = pd.encounter_id AND pd_e.voided = 0
               LEFT JOIN obs pd_d ON pd_d.encounter_id = pd_e.encounter_id AND pd_d.voided = 0
                   AND pd_d.concept_id = (SELECT concept_id FROM concept WHERE uuid = '6cbb5176-144a-576b-9b3d-c9e9d6bc5f5a')
               WHERE pd.person_id = lc.patient_id AND pd.voided = 0
                 AND pd.concept_id IN ((SELECT concept_id FROM concept WHERE uuid = '46f4af80-b783-59f4-beb1-81144ccf3084'),
                                           (SELECT concept_id FROM concept WHERE uuid = 'bb4a77ee-836a-57e7-a262-632fa22288d2'))
                 AND pd.value_coded = proc.value_coded
                 AND DATE(COALESCE(pd_d.value_datetime, pd_e.encounter_datetime)) >= DATE(lc.encounter_datetime)
                 AND DATE(COALESCE(pd_d.value_datetime, pd_e.encounter_datetime)) <= DATE(@endDate)
           ) AS completed
    FROM latest_consultation lc
    JOIN obs g ON g.encounter_id = lc.encounter_id AND g.voided = 0 AND g.obs_group_id IS NULL
     AND g.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'ce93d393-1df5-587f-bf11-c373eac2ccf4')
    -- The recommended procedure: the group's member with the group's concept
    LEFT JOIN obs proc ON proc.obs_group_id = g.obs_id AND proc.voided = 0 AND proc.concept_id = g.concept_id
    -- A Procedure Type of None records that no intervention is recommended
    WHERE NOT EXISTS (SELECT 1 FROM obs typ
                      WHERE typ.obs_group_id = g.obs_id AND typ.voided = 0
                        AND typ.concept_id = (SELECT concept_id FROM concept WHERE uuid = '3a576b80-744a-59ee-9515-d9fdca06f3d7')
                        AND typ.value_coded = (SELECT concept_id FROM concept WHERE uuid = '1107AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))
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
)
SELECT 1 AS measure_order, 'consultations' AS measure,
       (SELECT COUNT(*) FROM consultation c WHERE c.encounter_datetime >= DATE_SUB(DATE(@endDate), INTERVAL 365 DAY)) AS done,
       NULL AS not_done
UNION ALL
SELECT 2, 'echocardiogram', (SELECT COUNT(*) FROM echo_done),
       (SELECT COUNT(*) FROM active) - (SELECT COUNT(*) FROM echo_done)
UNION ALL
SELECT 3, 'retainedInCare', (SELECT COUNT(*) FROM retained),
       (SELECT COUNT(*) FROM active) - (SELECT COUNT(*) FROM retained)
UNION ALL
SELECT 4, 'interventionAssigned', (SELECT COUNT(DISTINCT patient_id) FROM recommendation WHERE completed = 0),
       (SELECT COUNT(*) FROM active) - (SELECT COUNT(DISTINCT patient_id) FROM recommendation WHERE completed = 0)
UNION ALL
SELECT 5, 'interventions', (SELECT COUNT(*) FROM recommendation WHERE completed = 1),
       (SELECT COUNT(*) FROM recommendation WHERE completed = 0)
UNION ALL
SELECT 6, 'warfarin', (SELECT COUNT(*) FROM inr_done),
       (SELECT COUNT(*) FROM warfarin) - (SELECT COUNT(*) FROM inr_done)
ORDER BY measure_order
