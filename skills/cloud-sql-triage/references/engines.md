# Engine distinctions

Use databaseVersion and actual metadata to choose the engine. Inspect descriptors
before choosing metric names, units and labels; guidance for one engine does not
establish availability or semantics for another.

For MySQL separate connection saturation, query latency/locks, storage pressure
and replica apply/receiver failures. Existing Query Insights may help correlate
load with a query fingerprint. Avoid treating a large buffer allocation as proof
of an OOM or suggesting SET GLOBAL from a generic pooling guide.

### MySQL reference adaptations

The selected PlanetScale references provide engine background, not Cloud SQL
defaults or a collection script. Verify MySQL version, observed limits and actual
pool topology; do not assume Vitess/vtgate, recommend a provider migration or size
pools from a CPU formula alone. Read the bundled files rather than fetching an
upstream main-branch guide. SQL Server/PostgreSQL do not use these references.

Interpret supplied plans in context: ALL, filesort, a row-count threshold or an
unused-index sample alone does not justify index changes. EXPLAIN ANALYZE executes
the query; neither it, ANALYZE TABLE, SET GLOBAL, isolation changes, GTID waits nor
replication controls run through this skill. Query text, lock_data and deadlock
reports can contain customer values; use supplied sanitized evidence only.

Known limitations of the pinned examples, checked against MySQL 8.0 documentation:
- The deadlocks guide's wait-join uses incorrect lock-ID column names. Validate
  any proposed diagnostic against the version's schema; documented names include
  REQUESTING_ENGINE_LOCK_ID/BLOCKING_ENGINE_LOCK_ID and ENGINE_LOCK_ID.
- Do not assume an open transaction exempts an inactive session from wait_timeout.
  Check the session timeout, client type and disconnect evidence; network read/write
  timeouts are not general query execution deadlines.
- Seconds_Behind_Source=0 does not prove receipt of all source transactions;
  NULL is undefined/unknown. Correlate receiver/applier state, errors and positions
  or GTIDs. Do not import the upstream five-second alert threshold as client policy.

### Other engines

For PostgreSQL distinguish active/idle sessions, locks/long transactions, storage
or WAL/replication pressure. No VACUUM, ALTER SYSTEM, pg_terminate_backend or slot
changes during triage. Missing optional diagnostic extensions limit conclusions.

For SQL Server distinguish session/worker pressure, blocking, storage/IO and
availability/replication evidence. MySQL process lists, PostgreSQL catalog queries
and their configuration knobs are not applicable. Diagnostics from an existing
approved SQL session can be reviewed as supplied offline evidence, with literals
and customer data omitted.

Cloud SQL state, operation success and query readiness are separate. Recommend a
database-level diagnostic only after metadata/telemetry identifies the gap; the
first version of this skill does not open database sessions.

Sources, checked 2026-09-21:
- [MySQL troubleshooting](https://cloud.google.com/sql/docs/mysql/troubleshooting)
- [PostgreSQL troubleshooting](https://cloud.google.com/sql/docs/postgres/troubleshooting)
- [SQL Server troubleshooting](https://cloud.google.com/sql/docs/sqlserver/troubleshooting)
- [MySQL Query Insights](https://cloud.google.com/sql/docs/mysql/using-query-insights)
- [MySQL lock-wait columns](https://dev.mysql.com/doc/refman/8.0/en/performance-schema-data-lock-waits-table.html)
- [MySQL session timeouts](https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_wait_timeout)
- [MySQL replica status semantics](https://dev.mysql.com/doc/refman/8.0/en/show-replica-status.html)
