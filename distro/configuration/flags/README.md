# RHD flags

Initializer loads `rhd_flags.csv` and ignores this file.

## Each criteria runs two ways

A flag's `criteria` is evaluated:

- **For every patient**, as written, by ACT Core's nightly flag refresh.
- **For one patient**: by patientflags when an encounter is saved, and by ACT Core once an encounter save, void or purge commits. Both build that query from the text the way patientflags 3.0.10 does (`SQLFlagEvaluator`). It finds the first `<alias>.patient_id` and appends ` and <alias>.patient_id = <id>`, or ` where ...` when the text contains no `where` at all.

The check for `where` is a plain text match: it counts a `where` anywhere in the text, even inside a subquery, a quoted value or a longer word.

A criteria that works for every patient can still be wrong for one. Then the flag is raised or cleared wrongly on every save, and stays wrong until the next nightly refresh.

## Rules for a new flag

- Select the outer patient first, with an alias: `SELECT pat.patient_id ...`. The first `<alias>.patient_id` anywhere in the text is the one that gets filtered.
- Give the outer query a `WHERE`. Otherwise any other `where` in the text makes patientflags append `and ...` to the end of the text.
- No top-level `UNION`. The condition lands on the last branch only, so the other branches still return every patient they match, and the flag is raised for each of them when any of their encounters is saved. Wrap the `UNION` in a subquery and select from that.
- End the outer query with its `WHERE` conditions. A top-level `ORDER BY`, `GROUP BY`, `HAVING` or `LIMIT` breaks the appended condition. Put them in a subquery.
- Wrap any top-level `OR` in parentheses: `WHERE a OR b and pat.patient_id = 7` filters only `b`.
- No trailing line comment (`--` or `#`). The appended condition would end up inside it.

To check a new flag, run its criteria as written, then once per patient with the condition appended, and compare the results.

When `patientflags.version` in `distro/pom.xml` changes, check that `SQLFlagEvaluator` still builds the one-patient query this way.
