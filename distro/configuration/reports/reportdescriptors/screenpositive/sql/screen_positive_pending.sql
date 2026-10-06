-- =============================================================================
-- Screen Positive, Pending Confirmation
-- One row per patient enrolled in the RHD Registry program now whose latest Screen + answer is Yes,
-- and who has no Category at Diagnosis recorded since: no confirmatory echo has categorised them yet.
-- =============================================================================
SELECT
    MAX(rhd_id.identifier)                                          AS rhd_id,
    MAX(CONCAT(pn.given_name, ' ', pn.family_name))                 AS full_name,
    TIMESTAMPDIFF(YEAR, p.birthdate, CURDATE())                     AS age_years,
    p.gender                                                        AS sex,
    MAX(cardiac_loc.name)                                           AS cardiac_clinic,
    MAX(primary_loc.name)                                           AS primary_care_clinic,
    -- The Date recorded under Screen +, else the date of the Screen + answer itself
    DATE(COALESCE((
        SELECT MAX(d.value_datetime)
        FROM obs d
        WHERE d.encounter_id = scr.encounter_id AND d.voided = 0
          AND d.concept_id = (SELECT concept_id FROM concept WHERE uuid = '96d6d328-87ba-5a2e-bb71-2d1cd73b3e90')
    ), scr.obs_datetime))                                           AS screen_date,
    -- The Screening Site, else the School Name of a school screening
    COALESCE((
        SELECT MAX(s.value_text)
        FROM obs s
        WHERE s.encounter_id = scr.encounter_id AND s.voided = 0
          AND s.concept_id = (SELECT concept_id FROM concept WHERE uuid = '36ccfed2-09e2-5224-9963-267ab3f891d2')
    ), (
        SELECT MAX(s.value_text)
        FROM obs s
        WHERE s.encounter_id = scr.encounter_id AND s.voided = 0
          AND s.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'cfd8f77a-a2b5-5836-96c1-d3e5fdd48e02')
    ))                                                              AS screening_site,
    -- The answer's short name, which is how the form labels it
    (
        SELECT MAX(COALESCE(sn.name, fn.name))
        FROM obs f
        JOIN concept_name fn ON fn.concept_id = f.value_coded AND fn.locale = 'en'
            AND fn.concept_name_type = 'FULLY_SPECIFIED' AND fn.voided = 0
        LEFT JOIN concept_name sn ON sn.concept_id = f.value_coded AND sn.locale = 'en'
            AND sn.concept_name_type = 'SHORT' AND sn.voided = 0
        WHERE f.encounter_id = scr.encounter_id AND f.voided = 0
          AND f.concept_id = (SELECT concept_id FROM concept WHERE uuid = '2d1b8bb8-fbca-5683-87d2-30972811c982')
    )                                                               AS follow_up_status,
    p.uuid                                                          AS patient_uuid

FROM obs scr
JOIN person p ON p.person_id = scr.person_id AND p.voided = 0 AND p.dead = 0
JOIN patient pat ON pat.patient_id = p.person_id AND pat.voided = 0

LEFT JOIN person_name pn ON pn.person_id = p.person_id AND pn.voided = 0 AND pn.preferred = 1
LEFT JOIN patient_identifier rhd_id
    ON rhd_id.patient_id = p.person_id AND rhd_id.voided = 0
    AND rhd_id.identifier_type = (SELECT patient_identifier_type_id FROM patient_identifier_type
                                   WHERE uuid = '240f85fa-46e1-540e-9234-2796c623f7ea')
LEFT JOIN person_attribute pa_primary
    ON pa_primary.person_id = p.person_id AND pa_primary.voided = 0
    AND pa_primary.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE name = 'Health Center' LIMIT 1)
LEFT JOIN person_attribute pa_cardiac
    ON pa_cardiac.person_id = p.person_id AND pa_cardiac.voided = 0
    AND pa_cardiac.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE uuid = 'fe261119-2911-5b36-be40-8f9827826987')
LEFT JOIN location cardiac_loc ON cardiac_loc.location_id = pa_cardiac.value
LEFT JOIN location primary_loc ON primary_loc.location_id = pa_primary.value

WHERE scr.voided = 0
    AND scr.concept_id = (SELECT concept_id FROM concept WHERE uuid = '82a5fbb5-038d-57b8-82d1-3fd0ac95673d')
    AND scr.value_coded = (SELECT concept_id FROM concept WHERE uuid = 'cf82933b-3f3f-45e7-a5ab-5d31aaee3da3')
    -- The patient's latest Screen + answer
    AND NOT EXISTS (
        SELECT 1 FROM obs later
        WHERE later.person_id = scr.person_id AND later.concept_id = scr.concept_id AND later.voided = 0
          AND (later.obs_datetime > scr.obs_datetime
               OR (later.obs_datetime = scr.obs_datetime AND later.obs_id > scr.obs_id))
    )
    -- No Category at Diagnosis recorded with or after the screen
    AND NOT EXISTS (
        SELECT 1 FROM obs cat
        WHERE cat.person_id = scr.person_id AND cat.voided = 0
          AND cat.concept_id = (SELECT concept_id FROM concept WHERE uuid = '1a5aa050-661d-5e89-95d7-c1eba476df22')
          AND cat.obs_datetime >= scr.obs_datetime
    )
    -- Enrolled in the RHD Registry now
    AND EXISTS (
        SELECT 1 FROM patient_program pp
        JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
        WHERE pp.patient_id = p.person_id AND pp.voided = 0 AND pp.date_completed IS NULL
    )

GROUP BY scr.obs_id, scr.encounter_id, scr.obs_datetime, p.person_id, p.birthdate, p.gender, p.uuid
