-- =============================================================================
-- RHD Dashboard Waitlist
-- The Dashboard's procedural waitlist and the procedures performed in the year to the end date, as counts.
-- Rows: breakdown, procedure, urgency, patients, recommendations.
--   open: the recommendations not yet completed on the end date by procedure and urgency, from the latest consultation
--         by then of each patient alive and enrolled then, each counted once under its own procedure; on today's date,
--         the Procedural Waiting List
--   total: procedure 'All', the patients waiting and their open recommendations
--   performed: recommendations completed in the 365 days to the end date, as Mitral balloon valvuloplasty (mitral
--              balloon valvuloplasty or mitral valvuloplasty) or Surgery (procedure type Surgery), including those of
--              patients who have since died or whose enrolment has since ended
-- A recommendation is completed on its consultation's date when its Completed Yes was saved with the consultation, and
-- otherwise when a later edit of the consultation saved it, as the waiting list's row action does.
-- A Completed answer written over a minute after its consultation, as by a bulk import, is dated when it was written.
-- Parameters: @endDate; @cardiacClinic and @primaryCareClinic, location uuids, each counting only its patients when
-- set; @clinics, location uuids separated by commas, counting only the patients either of whose clinics is one of them.
-- =============================================================================
WITH RECURSIVE clinic_patient AS (
    -- Patients at the clinics chosen
    SELECT p.person_id, p.dead, p.death_date
    FROM person p
    JOIN patient pat ON pat.patient_id = p.person_id AND pat.voided = 0
    WHERE p.voided = 0
      AND (@cardiacClinic IS NULL OR @cardiacClinic = '' OR EXISTS (
          SELECT 1 FROM person_attribute pa
          JOIN location l ON l.location_id = pa.value AND l.uuid = @cardiacClinic
          WHERE pa.person_id = p.person_id AND pa.voided = 0
            AND pa.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE uuid = 'fe261119-2911-5b36-be40-8f9827826987')
      ))
      AND (@primaryCareClinic IS NULL OR @primaryCareClinic = '' OR EXISTS (
          SELECT 1 FROM person_attribute pa
          JOIN location l ON l.location_id = pa.value AND l.uuid = @primaryCareClinic
          WHERE pa.person_id = p.person_id AND pa.voided = 0
            AND pa.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE uuid = '695f2990-236f-5d7c-b8aa-ddbdb22400f4')
      ))
      AND (@clinics IS NULL OR @clinics = '' OR EXISTS (
          SELECT 1 FROM person_attribute pa
          JOIN location l ON l.location_id = pa.value AND FIND_IN_SET(l.uuid, @clinics) > 0
          WHERE pa.person_id = p.person_id AND pa.voided = 0
            AND pa.person_attribute_type_id IN (SELECT person_attribute_type_id FROM person_attribute_type
                                                 WHERE uuid IN ('fe261119-2911-5b36-be40-8f9827826987',
                                                                '695f2990-236f-5d7c-b8aa-ddbdb22400f4'))
      ))
),
-- Of them, those alive on the end date and enrolled in the RHD Registry then
patient_at AS (
    SELECT cp.person_id
    FROM clinic_patient cp
    WHERE NOT (cp.dead = 1 AND (cp.death_date IS NULL OR DATE(cp.death_date) <= DATE(@endDate)))
      AND EXISTS (
          SELECT 1 FROM patient_program pp
          JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
          WHERE pp.patient_id = cp.person_id AND pp.voided = 0
            AND DATE(pp.date_enrolled) <= DATE(@endDate)
            AND (pp.date_completed IS NULL OR DATE(pp.date_completed) > DATE(@endDate))
      )
),
consultation AS (
    SELECT e.encounter_id, e.patient_id, e.encounter_datetime, e.date_created
    FROM encounter e
    JOIN form f ON f.form_id = e.form_id AND f.uuid = '4b063fc7-996f-3001-8500-8940e201be8f'
    JOIN clinic_patient cp ON cp.person_id = e.patient_id
    WHERE e.voided = 0 AND e.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
),
-- A Completed answer of Yes (CIEL Yes, or core's True on answers saved before the form used CIEL), with the earlier
-- versions of it that also said Yes: moving a consultation's date saves each of its answers again unchanged.
completed_yes AS (
    SELECT done.obs_group_id, done.previous_version, done.date_created
    FROM obs done
    WHERE done.voided = 0
      AND done.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1632f8dc-195d-5d67-a52e-6c7a057cb536')
      AND done.value_coded IN ((SELECT CAST(property_value AS UNSIGNED) FROM global_property WHERE property = 'concept.true'),
                               (SELECT concept_id FROM concept WHERE uuid = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))
    UNION ALL
    SELECT y.obs_group_id, earlier.previous_version, earlier.date_created
    FROM completed_yes y
    JOIN obs earlier ON earlier.obs_id = y.previous_version
        AND earlier.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1632f8dc-195d-5d67-a52e-6c7a057cb536')
        AND earlier.value_coded IN ((SELECT CAST(property_value AS UNSIGNED) FROM global_property WHERE property = 'concept.true'),
                                    (SELECT concept_id FROM concept WHERE uuid = '1065AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))
),
-- Each recommendation is an obs group of Interventional Recommendation(s) whose procedure member has the same concept
recommendation AS (
    SELECT c.encounter_id, c.patient_id, c.encounter_datetime, g.obs_id,
           COALESCE(proc_name.name, 'Not given') AS procedure_name,
           proc_concept.uuid AS procedure_uuid,
           type_concept.uuid AS procedure_type_uuid,
           COALESCE(urg_name.name, 'Not given') AS urgency,
           CASE WHEN yes.saved <= DATE_ADD(c.date_created, INTERVAL 1 MINUTE) THEN c.encounter_datetime
                ELSE yes.saved END AS completed_on
    FROM consultation c
    JOIN obs g ON g.encounter_id = c.encounter_id AND g.voided = 0 AND g.obs_group_id IS NULL
        AND g.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'ce93d393-1df5-587f-bf11-c373eac2ccf4')
    LEFT JOIN obs proc ON proc.obs_group_id = g.obs_id AND proc.voided = 0 AND proc.concept_id = g.concept_id
    LEFT JOIN concept proc_concept ON proc_concept.concept_id = proc.value_coded
    LEFT JOIN concept_name proc_name ON proc_name.concept_id = proc.value_coded
        AND proc_name.locale = 'en' AND proc_name.locale_preferred = 1 AND proc_name.voided = 0
    LEFT JOIN obs urg ON urg.obs_group_id = g.obs_id AND urg.voided = 0
        AND urg.concept_id = (SELECT concept_id FROM concept WHERE uuid = '7b8eda07-34b6-55f2-ab6c-1b295f41918b')
    LEFT JOIN concept_name urg_name ON urg_name.concept_id = urg.value_coded
        AND urg_name.locale = 'en' AND urg_name.locale_preferred = 1 AND urg_name.voided = 0
    LEFT JOIN obs typ ON typ.obs_group_id = g.obs_id AND typ.voided = 0
        AND typ.concept_id = (SELECT concept_id FROM concept WHERE uuid = '3a576b80-744a-59ee-9515-d9fdca06f3d7')
    LEFT JOIN concept type_concept ON type_concept.concept_id = typ.value_coded
    LEFT JOIN (SELECT obs_group_id, MIN(date_created) AS saved FROM completed_yes GROUP BY obs_group_id) yes
        ON yes.obs_group_id = g.obs_id
),
-- The recommendations in the latest consultation by the end date of each patient alive and enrolled then, not completed
-- by then
open_recommendation AS (
    SELECT r.* FROM recommendation r
    JOIN patient_at pa ON pa.person_id = r.patient_id
    WHERE (r.completed_on IS NULL OR r.completed_on >= DATE_ADD(DATE(@endDate), INTERVAL 1 DAY))
      AND NOT EXISTS (
          SELECT 1 FROM encounter later
          JOIN form lf ON lf.form_id = later.form_id AND lf.uuid = '4b063fc7-996f-3001-8500-8940e201be8f'
          WHERE later.patient_id = r.patient_id AND later.voided = 0
            AND later.encounter_datetime < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
            AND (later.encounter_datetime > r.encounter_datetime
                 OR (later.encounter_datetime = r.encounter_datetime AND later.encounter_id > r.encounter_id))
      )
)
SELECT 'open' AS breakdown, procedure_name AS `procedure`, urgency,
       COUNT(DISTINCT patient_id) AS patients, COUNT(*) AS recommendations
FROM open_recommendation
GROUP BY procedure_name, urgency
UNION ALL
SELECT 'total', 'All', NULL, COUNT(DISTINCT patient_id), COUNT(*)
FROM open_recommendation
UNION ALL
SELECT 'performed', kind.label, NULL, COALESCE(done.patients, 0), COALESCE(done.recommendations, 0)
FROM (SELECT 'Mitral balloon valvuloplasty' AS label UNION ALL SELECT 'Surgery') kind
LEFT JOIN (
    SELECT CASE WHEN procedure_uuid IN ('af9429ff-1b76-55f3-81ca-a9f775d93fb4', 'aca1be99-d090-5078-be63-81353ae89195')
                THEN 'Mitral balloon valvuloplasty'
                WHEN procedure_type_uuid = 'aa5fefb0-cf61-5f36-82e6-31dbbdf3f616' THEN 'Surgery' END AS label,
           COUNT(DISTINCT patient_id) AS patients, COUNT(*) AS recommendations
    FROM recommendation
    WHERE completed_on >= DATE_SUB(DATE(@endDate), INTERVAL 364 DAY)
      AND completed_on < DATE_ADD(DATE(@endDate), INTERVAL 1 DAY)
    GROUP BY 1
) done ON done.label = kind.label
