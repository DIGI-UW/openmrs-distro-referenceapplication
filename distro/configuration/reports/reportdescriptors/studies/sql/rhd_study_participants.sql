-- =============================================================================
-- RHD Study Participants
-- One row per enrolment in a research study. A study is a program with a workflow on the
-- Research Study Status concept; the retired template program has none enrolled.
-- =============================================================================
SELECT
    p.uuid                                                          AS patient_uuid,
    MAX(rhd_id.identifier)                                          AS rhd_id,
    MAX(CONCAT(pn.given_name, ' ', pn.family_name))                 AS full_name,
    pr.uuid                                                         AS study_uuid,
    pr.name                                                         AS study,
    pp.uuid                                                         AS enrollment_uuid,
    MAX(study_id.value_reference)                                   AS study_id,
    DATE(pp.date_enrolled)                                          AS date_enrolled,
    DATE(pp.date_completed)                                         AS date_completed,

    -- The current Study status state: the one still open, else the one that started last
    (
        SELECT cn.name
        FROM patient_state ps
        JOIN program_workflow_state pws ON pws.program_workflow_state_id = ps.state
        JOIN concept_name cn ON cn.concept_id = pws.concept_id
            AND cn.locale = 'en' AND cn.concept_name_type = 'FULLY_SPECIFIED' AND cn.voided = 0
        WHERE ps.patient_program_id = pp.patient_program_id AND ps.voided = 0
        ORDER BY ps.end_date IS NULL DESC, ps.start_date DESC, ps.patient_state_id DESC
        LIMIT 1
    )                                                               AS status,
    (
        SELECT pws.uuid
        FROM patient_state ps
        JOIN program_workflow_state pws ON pws.program_workflow_state_id = ps.state
        WHERE ps.patient_program_id = pp.patient_program_id AND ps.voided = 0
        ORDER BY ps.end_date IS NULL DESC, ps.start_date DESC, ps.patient_state_id DESC
        LIMIT 1
    )                                                               AS status_uuid,
    -- Active until the enrolment is completed or its status is a terminal (Inactive) one
    CASE WHEN pp.date_completed IS NULL AND NOT EXISTS (
        SELECT 1
        FROM patient_state ps
        JOIN program_workflow_state pws ON pws.program_workflow_state_id = ps.state AND pws.terminal = 1
        WHERE ps.patient_program_id = pp.patient_program_id AND ps.voided = 0 AND ps.end_date IS NULL
    ) THEN 1 ELSE 0 END                                             AS active,

    MAX(primary_loc.name)                                           AS primary_care_clinic,
    MAX(cardiac_loc.name)                                           AS cardiac_clinic

FROM patient_program pp
JOIN program pr ON pr.program_id = pp.program_id AND pr.retired = 0
JOIN patient pat ON pat.patient_id = pp.patient_id AND pat.voided = 0
JOIN person p    ON p.person_id    = pp.patient_id  AND p.voided = 0

LEFT JOIN person_name pn ON pn.person_id = p.person_id AND pn.voided = 0 AND pn.preferred = 1
LEFT JOIN patient_identifier rhd_id
    ON rhd_id.patient_id = p.person_id AND rhd_id.voided = 0
    AND rhd_id.identifier_type = (SELECT patient_identifier_type_id FROM patient_identifier_type
                                   WHERE uuid = '240f85fa-46e1-540e-9234-2796c623f7ea')
-- Study Participant ID, on the enrolment
LEFT JOIN patient_program_attribute study_id
    ON study_id.patient_program_id = pp.patient_program_id AND study_id.voided = 0
    AND study_id.attribute_type_id = (SELECT program_attribute_type_id FROM program_attribute_type
                                       WHERE uuid = '7840ba5d-d927-52d6-907b-dd070bea6626')
LEFT JOIN person_attribute pa_primary
    ON pa_primary.person_id = p.person_id AND pa_primary.voided = 0
    AND pa_primary.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE uuid = '695f2990-236f-5d7c-b8aa-ddbdb22400f4')
LEFT JOIN person_attribute pa_cardiac
    ON pa_cardiac.person_id = p.person_id AND pa_cardiac.voided = 0
    AND pa_cardiac.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE uuid = 'fe261119-2911-5b36-be40-8f9827826987')
LEFT JOIN location primary_loc ON primary_loc.location_id = pa_primary.value
LEFT JOIN location cardiac_loc ON cardiac_loc.location_id = pa_cardiac.value

WHERE
    pp.voided = 0
    AND EXISTS (
        SELECT 1 FROM program_workflow pw
        WHERE pw.program_id = pr.program_id AND pw.retired = 0
          AND pw.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'b26193da-7eee-5f89-9909-95d20f4726aa')
    )

GROUP BY pp.patient_program_id, pp.uuid, pp.date_enrolled, pp.date_completed, pr.uuid, pr.name, p.uuid

ORDER BY study, date_enrolled DESC, rhd_id
