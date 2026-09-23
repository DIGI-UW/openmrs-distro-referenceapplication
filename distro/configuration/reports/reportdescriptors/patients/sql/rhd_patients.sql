-- =============================================================================
-- RHD Patient List
-- One row per patient enrolled in the RHD program.
-- Parameters: @startDate, @endDate  (program enrollment date range)
-- =============================================================================
SELECT
    -- Identifiers
    rhd_id.identifier                                               AS rhd_id,
    ext_id.identifier                                               AS external_id,
    nat_id.identifier                                               AS national_id,

    -- Demographics
    CONCAT(pn.given_name, ' ', pn.family_name)                      AS full_name,
    p.gender                                                        AS sex,
    p.birthdate                                                     AS date_of_birth,
    TIMESTAMPDIFF(YEAR, p.birthdate, CURDATE())                     AS age_years,
    pa_phone.value                                                  AS phone_number,
    pa_village.value                                                AS village,

    -- Program enrollment
    DATE(pp.date_enrolled)                                          AS date_enrolled,
    DATE(pp.date_completed)                                         AS date_completed,
    CASE WHEN pp.date_completed IS NULL THEN 'Active' ELSE 'Completed' END AS enrollment_status,

    -- Current workflow state (program stage)
    (
        SELECT cn.name
        FROM patient_state ps2
        JOIN program_workflow_state pws2 ON pws2.program_workflow_state_id = ps2.state
        JOIN concept_name cn ON cn.concept_id = pws2.concept_id AND cn.locale = 'en' AND cn.locale_preferred = 1 AND cn.voided = 0
        WHERE ps2.patient_program_id = pp.patient_program_id
          AND ps2.voided = 0 AND ps2.end_date IS NULL
        LIMIT 1
    )                                                               AS current_state,

    -- Diagnosis category (most recent)
    (
        SELECT cn2.name
        FROM obs cat_obs
        JOIN concept_name cn2 ON cn2.concept_id = cat_obs.value_coded
            AND cn2.locale = 'en' AND cn2.locale_preferred = 1 AND cn2.voided = 0
        WHERE cat_obs.person_id = p.person_id
          AND cat_obs.voided = 0
          AND cat_obs.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1a5aa050-661d-5e89-95d7-c1eba476df22')
        ORDER BY cat_obs.obs_datetime DESC, cat_obs.obs_id DESC
        LIMIT 1
    )                                                               AS diagnosis_category,

    -- Case detection method
    (
        SELECT cn3.name
        FROM obs det_obs
        JOIN concept_name cn3 ON cn3.concept_id = det_obs.value_coded
            AND cn3.locale = 'en' AND cn3.locale_preferred = 1 AND cn3.voided = 0
        WHERE det_obs.person_id = p.person_id
          AND det_obs.voided = 0
          AND det_obs.concept_id = (SELECT concept_id FROM concept WHERE uuid = '955632a1-82f7-5b84-a341-de85f95588d1')
        ORDER BY det_obs.obs_datetime ASC LIMIT 1
    )                                                               AS case_detected_by,

    -- Penicillin allergy
    (
        SELECT cn_pen.name
        FROM obs o_pen
        JOIN concept_name cn_pen ON cn_pen.concept_id = o_pen.value_coded
            AND cn_pen.locale = 'en' AND cn_pen.locale_preferred = 1 AND cn_pen.voided = 0
        WHERE o_pen.person_id = p.person_id AND o_pen.voided = 0
          AND o_pen.concept_id = (SELECT concept_id FROM concept WHERE uuid = '5cc3b707-b8ea-52ee-8e82-ea4de393a4a5')
        ORDER BY o_pen.obs_datetime DESC LIMIT 1
    )                                                               AS penicillin_allergy,

    -- Date of last consultation encounter
    (
        SELECT DATE(MAX(e_last.encounter_datetime))
        FROM encounter e_last
        JOIN encounter_type et_last ON et_last.encounter_type_id = e_last.encounter_type
            AND et_last.uuid = 'c2503561-c00d-5460-8157-43d594472b4a'
        WHERE e_last.patient_id = p.person_id AND e_last.voided = 0
    )                                                               AS last_consultation_date,

    p.uuid                                                          AS patient_uuid

FROM patient_program pp

-- Only the RHD program (identified by the active workflow state concept used throughout the module)
JOIN patient_state ps ON ps.patient_program_id = pp.patient_program_id
    AND ps.voided = 0
JOIN program_workflow_state pws ON pws.program_workflow_state_id = ps.state
JOIN program pw ON pw.program_id = pp.program_id AND pw.retired = 0

JOIN patient pat ON pat.patient_id = pp.patient_id AND pat.voided = 0
JOIN person p    ON p.person_id    = pp.patient_id  AND p.voided = 0

LEFT JOIN person_name pn ON pn.person_id = p.person_id AND pn.voided = 0 AND pn.preferred = 1

-- RHD ID
LEFT JOIN patient_identifier rhd_id
    ON rhd_id.patient_id = p.person_id AND rhd_id.voided = 0
    AND rhd_id.identifier_type = (SELECT patient_identifier_type_id FROM patient_identifier_type
                                   WHERE uuid = '240f85fa-46e1-540e-9234-2796c623f7ea')
-- External ID
LEFT JOIN patient_identifier ext_id
    ON ext_id.patient_id = p.person_id AND ext_id.voided = 0
    AND ext_id.identifier_type = (SELECT patient_identifier_type_id FROM patient_identifier_type
                                   WHERE uuid = '810bfaee-85de-5a81-b79c-954774076594')
-- National ID
LEFT JOIN patient_identifier nat_id
    ON nat_id.patient_id = p.person_id AND nat_id.voided = 0
    AND nat_id.identifier_type = (SELECT patient_identifier_type_id FROM patient_identifier_type
                                   WHERE uuid = 'fdd6f720-743b-57fc-915a-87c0f571097b')

-- Person attributes
LEFT JOIN person_attribute pa_phone
    ON pa_phone.person_id = p.person_id AND pa_phone.voided = 0
    AND pa_phone.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                              WHERE name = 'Telephone Number' LIMIT 1)
LEFT JOIN person_attribute pa_village
    ON pa_village.person_id = p.person_id AND pa_village.voided = 0
    AND pa_village.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE name = 'Health Center' LIMIT 1)

WHERE
    pp.voided = 0
    AND DATE(pp.date_enrolled) >= @startDate
    AND DATE(pp.date_enrolled) <= @endDate

GROUP BY pp.patient_program_id

ORDER BY rhd_id.identifier, pn.family_name, pn.given_name
