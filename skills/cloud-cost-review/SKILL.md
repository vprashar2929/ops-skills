---
name: cloud-cost-review
description: Discover billing exports within confirmed profile projects and explain Google Cloud spend and period-over-period changes using a profile. Supports GKE allocation when export labels are available; does not estimate bills from kubectl usage or purchase commitments or resize resources.
license: Apache-2.0
---

# Cloud cost review

Read [operations](references/operations.md) first. Metadata discovery needs bq
and permission to list datasets/tables and read their metadata in selected projects;
gcloud can resolve a selected project's billing-account association. Analysis
needs export data access and permission to run jobs in the designated query project.
gcloud/kubectl are also used for an explicitly requested GKE allocation follow-up.
BigQuery SELECT jobs can incur cost despite not changing billing resources.

For a supplied offline extract, analyze its confirmed profile/project scope using
decimal arithmetic and state its period/coverage. No live export, credentials or
query budget is needed for that path. The following prerequisites apply to live
queries, not to reading supplied evidence.

## Discover billing scope before querying

Start from the selected profile and confirmed environment-to-project
mappings. A supplied profile directory can be used to locate that named
profile without reading unrelated profiles. Reuse explicit alias confirmations from
this session. Ask for missing or ambiguous mappings while continuing discovery
for resolved environments; do not guess production from a naming pattern.

When export details are missing, read [billing discovery](references/discovery.md)
and perform bounded metadata discovery in confirmed resource projects and any
explicitly mapped central export projects. Do not ask the user to supply table
IDs, dataset location or currency that can be discovered. Metadata reads do not
require a query project, review period or maximum-bytes-billed budget. Finding a
table does not authorize reading rows outside the confirmed project scope or
charging query jobs.

Before a query job, establish the full export table ID, dataset location, allowed
resource projects and designated query project. Resolve only remaining ambiguity
with the user, reusing any prior authorization. The query project can differ from
resource projects. A central export can contain projects outside the selected
profile; always filter the confirmed resource-project set. Discover currency in
the scoped result and keep currencies separate; no advance currency selection is required.

Honor supplied periods and basis. Otherwise state a default of the last seven
complete UTC usage days versus the preceding seven; do not block on confirmation
of that default. Report possible export latency even for complete calendar days.
Missing export/access is a prerequisite gap, not zero spend. Do not search all
billing accounts or enable an export to complete this review.

Inspect the named table's schema/partition metadata first. Distinguish standard,
detailed/resource and other export schemas; do not force GKE label queries onto
unsupported schemas. Establish usage dates versus invoice month; use comparable
periods with an explicit timezone and report partial periods/data latency.

## Query and reconcile

1. Build a SELECT-only query with explicit resource-project and time filters,
   grouping by currency and the requested dimensions. Choose gross cost, credits
   and net cost explicitly; do not silently omit taxes/adjustments.
2. Aggregate repeated credits inside each billing row before grouping. Do not
   cross-join credits/labels/tags and multiply base cost. Use the example and
   accounting checks in [billing queries](references/billing.md).
3. Dry-run with Standard SQL in the specified project/location. Use a confirmed
   maximum-bytes-billed budget for execution; if none was supplied, report the
   dry-run estimate and ask for a ceiling before executing a charged query.
   LIMIT caps returned rows, not scanned bytes. Respect tool-level approvals.
4. Execute a bounded query; keep job identity, final status, processed bytes,
   period and scope attached to the result. Compare totals with the same scoped
   breakdown. Do not mix currencies, invoice totals and usage-period estimates.
5. For an observed increase, separate usage quantity, SKU/unit-price, credits,
   one-off adjustments and allocation changes where the schema supports them.
   Show absolute and percentage changes; a zero baseline has no finite percent.
6. For GKE allocation only, consult the bundled
   [GKE cost guide](references/google-gke-cost/guide.md). Confirm cost-allocation
   labels and available history; preserve unattributed/shared costs. Label absence
   does not establish zero namespace cost. Live resource usage is supplementary
   context, never a substitute for billing export data.

## Output and limits

Return period/basis, currency, gross/credits/net, largest evidenced changes and
attribution limitations, with query/job provenance. Describe potential savings
only as explicitly modelled estimates with assumptions and coverage. Do not
claim realised savings, prescribe commitments or apply rightsizing changes.
Do not alter budgets, exports, labels, IAM, reservations or billing association.

Example: "Use this profile to review staging costs. Discover the export in its
project; compare the last two complete UTC weeks by service and credits. Use the
specified query project and maximum bytes billed when supplied."

## License

Copyright 2026 Vibhu Prashar. Original content in this skill is licensed under
[Apache-2.0](LICENSE). Bundled third-party references retain their own licenses
and copyright notices in their respective directories.
