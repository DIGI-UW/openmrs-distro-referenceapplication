-- =============================================================================
-- RHD Dashboard Screening
-- ACT 2.0's dashboard screening section (dashboard_query.py get_screening_stats) counted its monthly screening
-- counts per clinic, which ACT 3.0 does not record (#184). This counts the registry's patients instead: one row per
-- Screen + answer, case detection, age band and sex, of the patients whose latest enrolment by the end date began in the period.
-- Parameters: @startDate, @endDate; @cardiacClinic and @primaryCareClinic, location uuids, each counting only its
-- patients when set
-- =============================================================================
WITH enrolled AS (
    SELECT pp.patient_id, pp.date_enrolled
    FROM patient_program pp
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    JOIN person p ON p.person_id = pp.patient_id AND p.voided = 0
    WHERE pp.voided = 0
      AND DATE(pp.date_enrolled) >= DATE(@startDate)
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
)
SELECT
    -- The latest Screen + answer by the end date
    (SELECT CASE ans.uuid WHEN '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' THEN 'Yes' WHEN '1066AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' THEN 'No' END
       FROM obs s JOIN concept ans ON ans.concept_id = s.value_coded
      WHERE s.person_id = e.patient_id AND s.voided = 0 AND s.obs_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
        AND s.concept_id = (SELECT concept_id FROM concept WHERE uuid = '82a5fbb5-038d-57b8-82d1-3fd0ac95673d')
      ORDER BY s.obs_datetime DESC, s.obs_id DESC LIMIT 1)                AS screen_positive,
    -- The first Case Detected By, as the registry reads it: School, Community or Facility for ACT 2.0's three
    -- screening types, and Other for the rest
    (SELECT CASE ans.uuid
                WHEN '5b7d5eb4-4c6a-52cb-95f3-ac5033708fc9' THEN 'School'
                WHEN '24b5320c-bf9b-5c3b-a43c-d700cc1134e1' THEN 'Community'
                WHEN '9e861499-cebe-5371-a893-5747f365da73' THEN 'Facility'
                ELSE 'Other' END
       FROM obs d JOIN concept ans ON ans.concept_id = d.value_coded
      WHERE d.person_id = e.patient_id AND d.voided = 0
        AND d.concept_id = (SELECT concept_id FROM concept WHERE uuid = '955632a1-82f7-5b84-a341-de85f95588d1')
      ORDER BY d.obs_datetime, d.obs_id LIMIT 1)                          AS detected_by,
    -- ACT 2.0's screening age groups, in whole years on enrolment
    CASE WHEN p.birthdate IS NULL THEN NULL
         WHEN TIMESTAMPDIFF(YEAR, p.birthdate, e.date_enrolled) < 10 THEN '0-9'
         WHEN TIMESTAMPDIFF(YEAR, p.birthdate, e.date_enrolled) < 20 THEN '10-19'
         ELSE '20+' END                                                    AS age_band,
    p.gender                                                               AS sex,
    COUNT(*)                                                               AS patients
FROM enrolled e
JOIN person p ON p.person_id = e.patient_id
GROUP BY screen_positive, detected_by, age_band, p.gender
ORDER BY screen_positive, detected_by, age_band, p.gender
