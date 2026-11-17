-- =============================================================================
-- RHD Dashboard Screening
-- The Dashboard's screening figures from registrations: the patients whose registry enrolment started in the period,
-- as the RHD Patient List lists them for it. It counts registered patients, not people screened.
-- Patient Information asks "Where the patient was screened" (Case Detected By) only when Screen + is Yes, so a patient
-- with no answer is Not recorded only when screen-positive; anyone else was never asked and is Not screen-positive (AR-203).
-- Rows: breakdown (total, female, screen, age, detected), label, patients.
-- Parameters: @startDate, @endDate; @cardiacClinic and @primaryCareClinic, location uuids, each counting only its
-- patients when set; @clinics, location uuids separated by commas, counting only the patients either of whose clinics
-- is one of them.
-- =============================================================================
WITH registered AS (
    -- Each patient's latest RHD Registry enrolment, when it started in the period, as the RHD Patient List reads it
    SELECT pp.patient_id, pp.date_enrolled, p.gender, p.birthdate
    FROM patient_program pp
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    JOIN patient pat ON pat.patient_id = pp.patient_id AND pat.voided = 0
    JOIN person p ON p.person_id = pp.patient_id AND p.voided = 0
    WHERE pp.voided = 0
      AND DATE(pp.date_enrolled) >= DATE(@startDate)
      AND DATE(pp.date_enrolled) <= DATE(@endDate)
      AND NOT EXISTS (
          SELECT 1 FROM patient_program later
          WHERE later.patient_id = pp.patient_id AND later.program_id = pp.program_id AND later.voided = 0
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
labelled AS (
    SELECT r.patient_id, r.gender,
           -- The latest Screen +, as recorded now like Case Detected By: CIEL Yes or No, or core's True or False on
           -- answers saved before the form used CIEL; anything else, or none, is Not recorded.
           (SELECT CASE
                       WHEN s.value_coded IN ((SELECT concept_id FROM concept WHERE uuid = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'),
                                              (SELECT CAST(property_value AS UNSIGNED) FROM global_property WHERE property = 'concept.true'))
                       THEN 'Yes'
                       WHEN s.value_coded IN ((SELECT concept_id FROM concept WHERE uuid = '1066AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'),
                                              (SELECT CAST(property_value AS UNSIGNED) FROM global_property WHERE property = 'concept.false'))
                       THEN 'No'
                   END
            FROM obs s
            WHERE s.person_id = r.patient_id AND s.voided = 0
              AND s.concept_id = (SELECT concept_id FROM concept WHERE uuid = '82a5fbb5-038d-57b8-82d1-3fd0ac95673d')
            ORDER BY s.obs_datetime DESC, s.obs_id DESC LIMIT 1) AS screen,
           CASE
               WHEN r.birthdate IS NULL THEN 'Age unknown'
               WHEN TIMESTAMPDIFF(YEAR, r.birthdate, DATE(r.date_enrolled)) < 10 THEN 'Children 0-9'
               WHEN TIMESTAMPDIFF(YEAR, r.birthdate, DATE(r.date_enrolled)) < 20 THEN 'Adolescents 10-19'
               ELSE 'Adults 20+'
           END AS age,
           -- The earliest Case Detected By, as the registry's case_detected_by reads it, named as the form offers it.
           -- ACT 2.0 asked it of every patient, so a migrated answer counts whatever Screen + says.
           (SELECT CASE c.uuid
                       WHEN '5b7d5eb4-4c6a-52cb-95f3-ac5033708fc9' THEN 'School'
                       WHEN '24b5320c-bf9b-5c3b-a43c-d700cc1134e1' THEN 'Community'
                       WHEN '9e861499-cebe-5371-a893-5747f365da73' THEN 'Health facility'
                       WHEN '28452410-f2a2-5ad7-9590-43e47df1d254' THEN 'Clinical presentation'
                       WHEN '06d80315-eaf9-5c71-a4c7-cb9759f93fe1' THEN 'Pregnancy / labor'
                       WHEN 'fdecbe0d-8c8d-545d-a3b8-b2fd31704db1' THEN 'Coincidental finding'
                       WHEN '00e06a31-9d6f-5045-a6f8-62cf96fcd526' THEN 'Post-mortem'
                       ELSE 'Other'
                   END
            FROM obs d
            JOIN concept c ON c.concept_id = d.value_coded
            WHERE d.person_id = r.patient_id AND d.voided = 0
              AND d.concept_id = (SELECT concept_id FROM concept WHERE uuid = '955632a1-82f7-5b84-a341-de85f95588d1')
            ORDER BY d.obs_datetime ASC LIMIT 1) AS detected
    FROM registered r
)
SELECT 'total' AS breakdown, 'Registered' AS label, COUNT(*) AS patients FROM labelled
UNION ALL
SELECT 'female', 'Female', COUNT(*) FROM labelled WHERE gender = 'F'
UNION ALL
SELECT 'screen', COALESCE(screen, 'Not recorded'), COUNT(*) FROM labelled GROUP BY 2
UNION ALL
SELECT 'age', age, COUNT(*) FROM labelled GROUP BY 2
UNION ALL
SELECT 'detected', COALESCE(detected, CASE WHEN screen = 'Yes' THEN 'Not recorded' ELSE 'Not screen-positive' END), COUNT(*)
  FROM labelled GROUP BY 2
