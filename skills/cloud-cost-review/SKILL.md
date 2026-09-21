---
name: cloud-cost-review
description: Explain Google Cloud spend and period-over-period changes from an explicitly scoped billing export using a client profile. Supports GKE allocation when export labels are available; does not estimate bills from kubectl usage or purchase commitments or resize resources.
---

# Cloud cost review

Read [operations](references/operations.md) first. Requires bq and permission to
read the named export and run bounded query jobs in the designated query project.
gcloud/kubectl are optional for an explicitly requested GKE allocation follow-up.
BigQuery SELECT jobs can incur cost despite not changing billing resources.

For a supplied offline extract, analyze its confirmed client/project scope using
decimal arithmetic and state its period/coverage. No live export, credentials or
query budget is needed for that path. The following prerequisites apply to live
queries, not to reading supplied evidence.

## Establish billing scope before querying

Require the explicit client profile, allowed resource project IDs, full billing
table ID, query/billing project, dataset location, period/basis and currency.
The query project can differ from resource projects. A central billing export can
contain other clients; always filter the confirmed resource-project set. Missing
export/access is a prerequisite gap, not zero spend. Do not search all billing
accounts or enable an export to complete this review.

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

Example: "Use this profile and billing table to compare these two complete UTC
weeks for this project. Query project/location and maximum bytes billed are
supplied. Explain the change by service and credits."
