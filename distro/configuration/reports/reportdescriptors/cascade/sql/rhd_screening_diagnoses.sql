-- =============================================================================
-- RHD Screening Diagnoses
-- The diagnoses of the screen-detected, as ACT 2.0's dashboard broke its screening cascade down
-- (dashboard_query.py screeningDiagnosisDetails and screeningRHDDetails): among the patients the RHD Screening Cascade
-- counts as screened positive and diagnosed, how many have each diagnosis category, and, for Rheumatic Heart Disease,
-- each set of diagnosis details. The CTEs are the cascade's, so the two reports count the same patients.
-- One row per category (details blank) and per RHD details (category RHD).
-- -----------------------------------------------------------------------------
-- (from the RHD Screening Cascade)
-- ACT 2.0's screening cascade (dashboard_query.py): Active as the care cascade counts it, then the patients who
-- screened positive (Screen + is Yes), those of them diagnosed, and those diagnosed with heart disease.
-- Parameters: @endDate; @cardiacClinic and @primaryCareClinic, location uuids, each counting only its patients when set
-- =============================================================================
WITH scr_active AS (
    SELECT DISTINCT pp.patient_id
    FROM patient_program pp
    -- Enrolled in the RHD Registry on the end date and not completed by then, as the registry report counts
    -- an enrolment active. O3 records no workflow state on enrolment, and entering a terminal state completes it.
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
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
-- Each patient's latest Diagnosis group by the end date with a Category and not answered inactive or secondary, as ACT 2.0
-- took the active primary diagnosis (unanswered counts, as those questions did not load before 2026-10-07).
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
category AS (
    SELECT d.person_id, d.obs_id, ans.uuid AS cat_uuid, ans.concept_id AS cat_concept
    FROM diagnosis d
    JOIN obs cat ON cat.obs_group_id = d.obs_id AND cat.voided = 0 AND cat.value_coded IS NOT NULL
     AND cat.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1a5aa050-661d-5e89-95d7-c1eba476df22')
    JOIN concept ans ON ans.concept_id = cat.value_coded
    WHERE NOT EXISTS (SELECT 1 FROM diagnosis later
                      WHERE later.person_id = d.person_id
                        AND (later.obs_datetime > d.obs_datetime OR (later.obs_datetime = d.obs_datetime AND later.obs_id > d.obs_id)))
),
-- The patient's latest Screen + answer by the end date is Yes.
screened_positive AS (
    SELECT a.patient_id
    FROM scr_active a
    JOIN obs s ON s.person_id = a.patient_id AND s.voided = 0 AND s.obs_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
     AND s.concept_id = (SELECT concept_id FROM concept WHERE uuid = '82a5fbb5-038d-57b8-82d1-3fd0ac95673d')
     AND s.value_coded = (SELECT concept_id FROM concept WHERE uuid = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA')
    WHERE NOT EXISTS (SELECT 1 FROM obs later
                      WHERE later.person_id = s.person_id AND later.concept_id = s.concept_id AND later.voided = 0
                        AND later.obs_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
                        AND (later.obs_datetime > s.obs_datetime OR (later.obs_datetime = s.obs_datetime AND later.obs_id > s.obs_id)))
),
-- The details recorded in each screen-detected patient's latest Diagnosis, joined in name order as the registry shows them
details AS (
    SELECT c.person_id,
           GROUP_CONCAT(cn.name ORDER BY cn.name SEPARATOR ', ') AS details
    FROM screened_positive s
    JOIN category c ON c.person_id = s.patient_id AND c.cat_uuid = '4e529463-2036-5327-ad69-7cbd39df86a1'
    JOIN obs det ON det.obs_group_id = c.obs_id AND det.voided = 0 AND det.value_coded IS NOT NULL
     AND det.concept_id IN ((SELECT concept_id FROM concept WHERE uuid = 'cfe17bb5-4a76-5f3a-9e1c-7b1e9b84a8e3'),
                            (SELECT concept_id FROM concept WHERE uuid = 'd3f6e1a2-9c5b-5e84-8f2d-1a6c7b9e0d4f'),
                            (SELECT concept_id FROM concept WHERE uuid = 'b7a2c4d8-5e91-5f3a-8c6d-2b9e4f7a1c0d'),
                            (SELECT concept_id FROM concept WHERE uuid = 'e9f3a5c7-6b82-5d4e-9f1a-3c7d8e2b5f4a'))
    JOIN concept_name cn ON cn.concept_id = det.value_coded AND cn.locale = 'en' AND cn.locale_preferred = 1 AND cn.voided = 0
    GROUP BY c.person_id
)
SELECT 'category' AS breakdown, cn.name AS category, NULL AS details, COUNT(*) AS patients
  FROM screened_positive s
  JOIN category c ON c.person_id = s.patient_id
  JOIN concept_name cn ON cn.concept_id = c.cat_concept AND cn.locale = 'en' AND cn.locale_preferred = 1 AND cn.voided = 0
 GROUP BY cn.name
UNION ALL
SELECT 'rhdDetails', 'Rheumatic Heart Disease/Rheumatic Fever', d.details, COUNT(*)
  FROM details d
 GROUP BY d.details
ORDER BY breakdown, patients DESC
