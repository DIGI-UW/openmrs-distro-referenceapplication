-- =============================================================================
-- RHD Instance KPIs
-- One row of counts for the Instance dashboard, so the page downloads no patient rows to show them.
-- Parameters: @startDate, @endDate (the forms' own dates, as the RHD Encounters Export filters them)
-- =============================================================================
WITH on_registry AS (
    -- On the registry now, as the RHD Patient List and ACT's lists count it: the patient's latest RHD Registry
    -- enrolment, not completed, and alive.
    SELECT pp.patient_id
    FROM patient_program pp
    JOIN program pr ON pr.program_id = pp.program_id AND pr.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    JOIN patient pat ON pat.patient_id = pp.patient_id AND pat.voided = 0
    JOIN person p ON p.person_id = pp.patient_id AND p.voided = 0 AND p.dead = 0
    WHERE pp.voided = 0
      AND pp.date_completed IS NULL
      AND DATE(pp.date_enrolled) <= @endDate
      AND NOT EXISTS (
          SELECT 1 FROM patient_program later
          WHERE later.patient_id = pp.patient_id AND later.program_id = pp.program_id AND later.voided = 0
            AND (later.date_enrolled > pp.date_enrolled
                 OR (later.date_enrolled = pp.date_enrolled AND later.patient_program_id > pp.patient_program_id))
      )
),
missing_data AS (
    -- On the patient list of a flag tagged Critical data now, which are the flags the registry and the chart show as
    -- missing data. ACT Core gives each flag's list the flag's uuid.
    SELECT DISTINCT cm.patient_id
    FROM cohort_member cm
    JOIN cohort c ON c.cohort_id = cm.cohort_id AND c.voided = 0
    JOIN patientflags_flag f ON f.uuid = c.uuid AND f.retired = 0
    JOIN patientflags_flag_tag ft ON ft.flag_id = f.flag_id
    JOIN patientflags_tag t ON t.tag_id = ft.tag_id AND t.uuid = 'b1f7a2c0-0008-4a00-9000-000000000008'
    WHERE cm.voided = 0 AND cm.end_date IS NULL
)
SELECT
    -- The rows the RHD Encounters Export would return for the period: the same encounter types and filters.
    (
        SELECT COUNT(*)
        FROM encounter e
        JOIN encounter_type et ON et.encounter_type_id = e.encounter_type
            AND et.retired = 0
            AND et.uuid IN (
                'c2503561-c00d-5460-8157-43d594472b4a',
                'ffdc883f-f99f-496a-83f9-2c3c581e1af0',
                'f064aaf0-bd36-43c5-9f35-00077457a569',
                '04cf03db-3b8e-5020-84b0-50b06338767a',
                '730f5ec2-7102-55d0-8602-2d792844f245',
                '64c3f35f-a3ec-59d6-8178-0ca9f068cda8',
                '181e0106-35d3-537a-a25e-18d3ebf61883',
                'ce6b111e-9beb-5a91-91ad-ec5043976fd5',
                '55271793-ef37-58da-9d86-1d9092a5a809',
                '8a51f352-5f1b-4836-a669-536e276a21db',
                'e3f1b6a8-5c2d-4f7e-9a41-6d8b2c0e7f53',
                'c9b87090-8768-50be-987e-8ca0a8983429',
                'b4bb88a3-9a04-5142-85bd-bb63c270f632'
            )
        JOIN patient pat ON pat.patient_id = e.patient_id AND pat.voided = 0
        JOIN person p ON p.person_id = e.patient_id AND p.voided = 0
        WHERE e.voided = 0
          AND e.encounter_datetime >= @startDate
          AND e.encounter_datetime < DATE_ADD(@endDate, INTERVAL 1 DAY)
    )                                                                       AS encounters,
    (SELECT COUNT(*) FROM on_registry)                                      AS active_patients,
    (
        SELECT COUNT(*) FROM on_registry r
        WHERE NOT EXISTS (SELECT 1 FROM missing_data m WHERE m.patient_id = r.patient_id)
    )                                                                       AS active_complete
