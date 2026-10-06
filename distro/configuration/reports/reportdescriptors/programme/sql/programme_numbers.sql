-- =============================================================================
-- Programme Numbers
-- One row: the RHD Registry's active patients, those due for BPG within 7 days, those overdue, and the
-- BPG on-time rate, the mean ACT Core adherence of patients on an injectable regimen.
-- Parameters: @location  (optional: only patients whose cardiac or primary care clinic is it, or under it)
-- =============================================================================
SELECT
    COUNT(*)                                                        AS active_patients,
    COALESCE(SUM(pt.bpg_status = 'Deadline approaching'), 0)        AS due_this_week,
    COALESCE(SUM(pt.bpg_status = 'Not covered'), 0)                 AS overdue,
    ROUND(AVG(CASE WHEN pt.injection_interval_days > 0 THEN pt.adherence END) * 100) AS bpg_on_time_rate

FROM (
    SELECT
        p.person_id,
        MAX(adh.injection_interval_days)                            AS injection_interval_days,
        MAX(adh.adherence)                                          AS adherence,
        -- The registry report's bpg_status, kept in step with rhd_patients.sql so the two agree
        CASE
            WHEN (MAX(adh.injection_interval_days) IS NULL
                  OR MAX(adh.regimen_concept_id) = (SELECT concept_id FROM concept WHERE uuid = '1107AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))
             AND NOT EXISTS (
                    SELECT 1
                    FROM obs o_rx
                    WHERE o_rx.voided = 0
                      AND o_rx.concept_id = (SELECT concept_id FROM concept WHERE uuid = '668e0221-8b41-5669-9ad8-78e193d42494')
                      AND o_rx.value_coded <> (SELECT concept_id FROM concept WHERE uuid = '1107AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA')
                      AND o_rx.encounter_id = (
                            SELECT o_last.encounter_id
                            FROM obs o_last
                            WHERE o_last.person_id = p.person_id AND o_last.voided = 0 AND o_last.value_coded IS NOT NULL
                              AND o_last.concept_id = (SELECT concept_id FROM concept WHERE uuid = '668e0221-8b41-5669-9ad8-78e193d42494')
                            ORDER BY o_last.obs_datetime DESC, o_last.obs_id DESC LIMIT 1
                          )
                      AND NOT EXISTS (
                            SELECT 1 FROM obs o_stop
                            WHERE o_stop.obs_group_id = o_rx.obs_group_id AND o_stop.voided = 0
                              AND o_stop.concept_id = (SELECT concept_id FROM concept WHERE uuid = 'd75edc42-3213-5a06-9228-4e5735b9594b')
                              AND DATE(o_stop.value_datetime) <= CURDATE()
                          )
                 ) THEN 'No prescription'
            WHEN MAX(adh.injection_interval_days) > 0 AND MAX(adh.next_due) IS NOT NULL THEN
                CASE WHEN DATEDIFF(MAX(adh.next_due), CURDATE()) < 0 THEN 'Not covered'
                     WHEN DATEDIFF(MAX(adh.next_due), CURDATE()) <= 7 THEN 'Deadline approaching'
                     ELSE 'Covered' END
        END                                                         AS bpg_status

    FROM patient_program pp
    JOIN program pw ON pw.program_id = pp.program_id AND pw.retired = 0
        AND pw.uuid = '7d73e143-a550-5a9d-aecd-dd771add098d'
    JOIN patient pat ON pat.patient_id = pp.patient_id AND pat.voided = 0
    JOIN person p    ON p.person_id    = pp.patient_id AND p.voided = 0
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
      -- ACT's locations are at most three levels deep: tertiary, district, community
      AND (@location IS NULL OR EXISTS (
            SELECT 1
            FROM person_attribute pa
            JOIN person_attribute_type pat_clinic ON pat_clinic.person_attribute_type_id = pa.person_attribute_type_id
                AND pat_clinic.uuid IN ('fe261119-2911-5b36-be40-8f9827826987',
                                        '695f2990-236f-5d7c-b8aa-ddbdb22400f4',
                                        '8d87236c-c2cc-11de-8d13-0010c6dffd0f')
            JOIN location l ON l.location_id = pa.value
            LEFT JOIN location l_parent ON l_parent.location_id = l.parent_location
            WHERE pa.person_id = p.person_id AND pa.voided = 0
              AND @location IN (l.location_id, l.parent_location, l_parent.parent_location)
          ))

    GROUP BY p.person_id
) pt
