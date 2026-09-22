---
name: cloud-sql-triage
description: Inspect a named Google Cloud SQL instance and investigate availability, connection, capacity or replication symptoms using an explicit client profile. Use for managed MySQL, PostgreSQL or SQL Server operations; does not execute application SQL or change the instance.
---

# Cloud SQL triage

Read [operations](references/operations.md) first. Requires gcloud, jq for the
projected example below, and Cloud SQL
read access; Cloud Monitoring/Logging access only for relevant evidence. The
initial workflow is control-plane and telemetry inspection, without DB credentials
or application-data queries. No proxy installation or direct database session.

Resolve client/profile, environment, exact project, instance and incident window.
Get the instance's actual region and databaseVersion from its scoped metadata;
do not infer engine from its name or choose a cluster to find a managed database.
For an application connection problem also establish the source workload's
identity/network/auth method without printing its connection string/password.

## Collect and correlate

```bash
set -o pipefail
gcloud sql instances describe "$instance" --project "$project" \
  --format='json(name,project,region,databaseVersion,state,settings.tier,settings.availabilityType,settings.dataDiskSizeGb,settings.storageAutoResize,settings.activationPolicy,replicaNames,masterInstanceName)' \
  | jq '{name,project,region,databaseVersion,state,settings:(.settings | {tier,availabilityType,dataDiskSizeGb,storageAutoResize,activationPolicy}),replicaNames,masterInstanceName}'
gcloud sql operations list --instance "$instance" --project "$project" \
  --limit=20 --sort-by='~insertTime' \
  --format='json(name,operationType,status,insertTime,startTime,endTime,error.errors.code)'
```

Check operation error presence separately from DONE. Treat RUNNABLE as instance
control-plane state, not proof of SQL connectivity or application health.
The downstream allowlist prevents gcloud transforms from emitting extra fields
such as userLabels. For an incident, constrain operation history to its window
and relevant preceding maintenance; the 20-row example is only a bounded overview.
Do not broadly list DB users, flags containing secrets, certificates or backups.

Select the branch supported by the symptom:

- **Availability:** correlate operations, maintenance/failover history and errors
  with outage timestamps. No failover/restart/restore to "test" availability.
- **Connections:** distinguish DNS/route/firewall/private-IP/PSC path, TLS/auth
  error, connector/proxy identity and server-side connection exhaustion. Check
  actual connection errors and limits/metrics; no assumption that public and
  private connections use the same path or IAM database authentication model.
- **Capacity/latency:** query descriptor-verified CPU, memory, storage and
  connection trends for the actual engine/resource. Use the bundled
  [metric discovery guide](references/google-metrics/guide.md). Treat its mandatory
  live-call and MCP configuration-edit instructions as inapplicable: use only
  existing scoped access, or analyze supplied offline evidence without live calls.
  Prefer exact metric descriptors or narrow metric prefixes for the symptom;
  a full product metric catalog is not a prerequisite.
  Current utilization
  alone does not establish a sizing recommendation or a historical bottleneck.
- **Replication:** identify primary/replica roles and engine-specific lag/error
  signals. Null/missing lag is not zero; lag=0 alone does not prove all replication
  threads or application reads are healthy. Compare timestamps and coverage.
- **Query/lock symptoms:** use already enabled Query Insights or approved redacted
  diagnostics when accessible. Query text and parameters can contain customer
  data. Do not enable instrumentation, run EXPLAIN ANALYZE, terminate sessions or
  execute SQL through this skill. Offer the exact missing diagnostic as a next step.

If backend/log routing is unknown, establish it from client context or return
the evidence gap. Never silently query a different project. Do not apply upstream
creation/tuning guidance, change flags, resize, promote replicas or alter access.

Return engine/version/region and observed state, operation/metric chronology,
connection-path evidence, supported cause versus hypotheses and coverage gaps.
Use [engine distinctions](references/engines.md) only for the selected engine.

For confirmed MySQL only, first read the MySQL adaptation notes in that file.
Then load the relevant pinned diagnostic reference as needed:
[connections](references/planetscale-mysql/references/connection-management.md),
[deadlocks](references/planetscale-mysql/references/deadlocks.md),
[row locks](references/planetscale-mysql/references/row-locking-gotchas.md),
[supplied query plans](references/planetscale-mysql/references/explain-analysis.md),
or [replication](references/planetscale-mysql/references/replication-lag.md).
Use these to interpret existing telemetry or supplied sanitized diagnostics;
their SQL/tuning examples do not authorize sessions, queries or changes.

Example: "Using this profile, investigate connection failures to the named dev
Cloud SQL instance during this UTC window. Inspect metadata and metrics only."
