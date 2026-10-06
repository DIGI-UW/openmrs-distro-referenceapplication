-- =============================================================================
-- Programme Numbers, by facility
-- One row per primary care clinic: a community clinic, or any clinic an active patient is assigned to.
-- Its active RHD Registry patients, their mean ACT Core adherence, and a data status: Duplicates when one
-- of them shares a name and birth date with another patient, else Review when one has an open critical
-- data flag, else Complete.
-- Parameters: @location  (optional: only clinics that are it, or under it)
-- =============================================================================
SELECT
    fac.name                                                        AS facility,
    COUNT(pt.person_id)                                             AS patients,
    ROUND(AVG(pt.adherence) * 100)                                  AS adherence,
    CASE
        WHEN SUM(pt.has_duplicate) > 0 THEN 'Duplicates'
        WHEN SUM(pt.has_critical_flag) > 0 THEN 'Review'
        ELSE 'Complete'
    END                                                             AS data_status,
    fac.uuid                                                        AS facility_uuid

FROM location fac
LEFT JOIN location fac_parent ON fac_parent.location_id = fac.parent_location

LEFT JOIN (
    SELECT
        p.person_id,
        -- Registration records the Primary Care Clinic; patients registered before it have a Health Center
        COALESCE(MAX(pa_pcc.value), MAX(pa_hc.value))               AS clinic_id,
        MAX(adh.adherence)                                          AS adherence,
        EXISTS (
            SELECT 1
            FROM person dup
            JOIN person_name dup_name ON dup_name.person_id = dup.person_id AND dup_name.voided = 0
            JOIN patient dup_pat ON dup_pat.patient_id = dup.person_id AND dup_pat.voided = 0
            WHERE dup.person_id <> p.person_id AND dup.voided = 0
              AND dup.birthdate = p.birthdate
              AND dup_name.given_name = MAX(pn.given_name)
              AND dup_name.family_name = MAX(pn.family_name)
        )                                                           AS has_duplicate,
        -- ACT Core gives each flag's patient list the flag's uuid
        EXISTS (
            SELECT 1
            FROM cohort_member cm
            JOIN cohort c ON c.cohort_id = cm.cohort_id AND c.voided = 0
            JOIN patientflags_flag f ON f.uuid = c.uuid AND f.retired = 0
            JOIN patientflags_flag_tag ft ON ft.flag_id = f.flag_id
            JOIN patientflags_tag t ON t.tag_id = ft.tag_id AND t.name = 'Critical data'
            WHERE cm.patient_id = p.person_id AND cm.voided = 0 AND cm.end_date IS NULL
        )                                                           AS has_critical_flag

    FROM patient_program pp
    JOIN program pw ON pw.program_id = pp.program_id AND pw.retired = 0
        AND pw.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    JOIN patient pat ON pat.patient_id = pp.patient_id AND pat.voided = 0
    JOIN person p    ON p.person_id    = pp.patient_id AND p.voided = 0
    LEFT JOIN person_name pn ON pn.person_id = p.person_id AND pn.voided = 0 AND pn.preferred = 1
    LEFT JOIN person_attribute pa_pcc
        ON pa_pcc.person_id = p.person_id AND pa_pcc.voided = 0
        AND pa_pcc.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                                WHERE uuid = '695f2990-236f-5d7c-b8aa-ddbdb22400f4')
    LEFT JOIN person_attribute pa_hc
        ON pa_hc.person_id = p.person_id AND pa_hc.voided = 0
        AND pa_hc.person_attribute_type_id = (SELECT person_attribute_type_id FROM person_attribute_type
                                               WHERE uuid = '8d87236c-c2cc-11de-8d13-0010c6dffd0f')
    LEFT JOIN actcore_prophylaxis_adherence adh ON adh.patient_id = p.person_id

    WHERE pp.voided = 0
      AND pp.date_completed IS NULL
      -- The patient's latest enrolment, as the registry report takes it
      AND NOT EXISTS (
            SELECT 1 FROM patient_program later
            WHERE later.patient_id = pp.patient_id AND later.program_id = pp.program_id AND later.voided = 0
              AND (later.date_enrolled > pp.date_enrolled
                   OR (later.date_enrolled = pp.date_enrolled AND later.patient_program_id > pp.patient_program_id))
          )

    GROUP BY p.person_id, p.birthdate
) pt ON pt.clinic_id = fac.location_id

WHERE fac.retired = 0
  AND (pt.person_id IS NOT NULL OR EXISTS (
        SELECT 1
        FROM location_tag_map ltm
        JOIN location_tag lt ON lt.location_tag_id = ltm.location_tag_id
            AND lt.uuid = '7194a06d-fbf9-5c15-b88a-893f4587bb47'
        WHERE ltm.location_id = fac.location_id
      ))
  -- ACT's locations are at most three levels deep: tertiary, district, community
  AND (@location IS NULL OR @location IN (fac.location_id, fac.parent_location, fac_parent.parent_location))

GROUP BY fac.location_id, fac.name, fac.uuid

ORDER BY fac.name
