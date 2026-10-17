# RHD flags

Initializer loads `rhd_flags.csv` and ignores this file.

## Each criteria runs two ways

A flag's `criteria` is evaluated:

- **For every patient**, as written, by ACT Core's nightly flag refresh.
- **For one patient**, on every encounter save, by patientflags and then by ACT Core once the save commits. patientflags builds that query from the text: it finds the first `<alias>.patient_id` and appends ` and <alias>.patient_id = <id>`, or ` where ...` when the text contains no `where` at all.

A criteria that works for every patient can still be wrong for one. Then the flag is raised or cleared wrongly on every save, and stays wrong until the next nightly refresh.

## Rules for a new flag

- Select the outer patient first, with an alias: `SELECT pat.patient_id ...`. The first `<alias>.patient_id` anywhere in the text is the one that gets filtered.
- Give the outer query a `WHERE`. Otherwise a `where` inside a subquery makes patientflags append `and ...` to the end of the text.
- End the outer query with its `WHERE` conditions. A top-level `ORDER BY`, `GROUP BY`, `HAVING` or `LIMIT` breaks the appended condition. Put them in a subquery.
- Wrap any top-level `OR` in parentheses: `WHERE a OR b and pat.patient_id = 7` filters only `b`.
- No trailing comment. The appended condition would end up inside it.

To check a new flag, run its criteria as written, then once per patient with the condition appended, and compare the results.
