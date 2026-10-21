-- =============================================================================
-- RHD Dashboard Registrants
-- ACT 2.0's dashboard registrants and demographics (dashboard_query.py get_basic_stats, get_demographics_stats):
-- one row per status, age band, sex, diagnosis category and RHD details, with its number of patients.
-- Parameters: @endDate; @cardiacClinic and @primaryCareClinic, location uuids, each counting only its patients when set
-- =============================================================================
WITH enrolment AS (
    SELECT pp.patient_program_id, pp.patient_id, pp.date_completed
    FROM patient_program pp
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    JOIN person p ON p.person_id = pp.patient_id AND p.voided = 0
    WHERE pp.voided = 0
      AND DATE(pp.date_enrolled) <= DATE(@endDate)
      -- The latest enrolment by the end date, as the registry lists one row per patient
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
),
-- Active while the enrolment is open on the end date; otherwise the reason is the terminal state it was completed with.
status AS (
    SELECT e.patient_id,
           CASE WHEN e.date_completed IS NULL OR DATE(e.date_completed) > DATE(@endDate) THEN 'Active'
                ELSE COALESCE((
                    SELECT cn.name
                    FROM patient_state ps
                    JOIN program_workflow_state pws ON pws.program_workflow_state_id = ps.state AND pws.terminal = 1
                    JOIN concept_name cn ON cn.concept_id = pws.concept_id AND cn.locale = 'en' AND cn.locale_preferred = 1
                     AND cn.voided = 0
                    WHERE ps.patient_program_id = e.patient_program_id AND ps.voided = 0
                    ORDER BY ps.start_date DESC, ps.patient_state_id DESC LIMIT 1
                ), 'No reason recorded') END AS status
    FROM enrolment e
),
-- Each patient's latest Diagnosis group by the end date with a Category and not answered inactive or secondary, as the
-- care cascade and the registry take it.
diagnosis AS (
    SELECT g.person_id, g.obs_id, g.obs_datetime
    FROM obs g
    JOIN enrolment e ON e.patient_id = g.person_id
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
-- The category's name, and for Rheumatic Heart Disease/Rheumatic Fever its details (RHD A, RHD B and so on), as ACT 2.0's
-- disease chart splits RHD by its details.
category AS (
    SELECT ld.person_id, cat_name.name AS category,
           CASE WHEN cat.value_coded = (SELECT concept_id FROM concept WHERE uuid = '4e529463-2036-5327-ad69-7cbd39df86a1') THEN (
               SELECT GROUP_CONCAT(det_name.name ORDER BY det_name.name SEPARATOR ', ')
               FROM obs det
               JOIN concept_name det_name ON det_name.concept_id = det.value_coded AND det_name.locale = 'en'
                AND det_name.locale_preferred = 1 AND det_name.voided = 0
               WHERE det.obs_group_id = ld.obs_id AND det.voided = 0
                 AND det.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'cfe17bb5-4a76-5f3a-9e1c-7b1e9b84a8e3')
           ) END AS details
    FROM latest_diagnosis ld
    JOIN obs cat ON cat.obs_group_id = ld.obs_id AND cat.voided = 0
     AND cat.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1a5aa050-661d-5e89-95d7-c1eba476df22')
    JOIN concept_name cat_name ON cat_name.concept_id = cat.value_coded AND cat_name.locale = 'en'
     AND cat_name.locale_preferred = 1 AND cat_name.voided = 0
)
SELECT s.status,
       -- ACT 2.0's age bands, in whole years on the end date
       CASE WHEN p.birthdate IS NULL THEN NULL
            WHEN TIMESTAMPDIFF(YEAR, p.birthdate, DATE(@endDate)) < 10 THEN '0-9'
            WHEN TIMESTAMPDIFF(YEAR, p.birthdate, DATE(@endDate)) < 20 THEN '10-19'
            WHEN TIMESTAMPDIFF(YEAR, p.birthdate, DATE(@endDate)) < 40 THEN '20-39'
            ELSE '40+' END AS age_band,
       p.gender AS sex,
       c.category,
       c.details,
       COUNT(*) AS patients
FROM status s
JOIN person p ON p.person_id = s.patient_id
LEFT JOIN category c ON c.person_id = s.patient_id
GROUP BY s.status, age_band, p.gender, c.category, c.details
ORDER BY s.status, age_band, p.gender, c.category, c.details
