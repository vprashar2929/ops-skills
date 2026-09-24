# Discover an existing billing export

Use this path when the client and at least one resource project are confirmed but
the export is unknown. Reuse supplied export settings instead of rediscovering
them. Discovery is metadata-only: no SELECT, table preview, row reads, resource
creation, API enablement or credential changes. Use existing authentication,
explicit project flags, finite command timeouts and bounded listings. Record
commands, collection times, status and incomplete pagination per operations.

## Resolve the selected project's billing link

```bash
gcloud billing projects describe "$resource_project" \
  --format='json(projectId,billingAccountName,billingEnabled)' --quiet
```

Check the returned project ID. The linked account is evidence for matching export
table names, not authority to enumerate every project on that account. Account
metadata is optional: a denied account describe must not prevent independently
permitted BigQuery metadata reads. Currency can be derived later from scoped
billing rows. An account association is current metadata, not proof that all
historical usage was billed to that account.

## Find and inspect candidates

Within each confirmed resource project and explicitly mapped export project:

```bash
bq --project_id="$export_project" --format=json ls --max_results=100
bq --project_id="$export_project" --format=json ls --max_results=100 \
  "$export_project:$dataset"
bq --project_id="$export_project" --format=json show \
  "$export_project:$dataset.$table"
```

List dataset and table identifiers, types and locations; project only schema,
partition, size and modification metadata from table inspection. Do not dump
dataset ACLs or arbitrary descriptions/labels. Check the installed bq help for
pagination flags; continue within a declared bound or report incomplete discovery.
Use relevant dataset names as hints, not proof of billing content. A linked
dataset or view referring outside the selected projects needs an explicit client
mapping before following that reference or querying it.

Recognize standard `gcp_billing_export_v1_*` and detailed
`gcp_billing_export_resource_v1_*` candidates; match the billing-account suffix
when available and inspect the actual schema. Other schemas, including FOCUS,
need their own verified accounting mapping; do not apply the standard query
template solely because a table name looks plausible.

When standard and detailed exports for the same account coexist, prefer standard
for project/service totals and detailed for resource/GKE attribution. Never add
both exports together. Multiple accounts, historical copies or export migrations
can require a selection or coverage reconciliation; present remaining candidates
without claiming a uniquely verified source. A schema and recent modification
time do not establish period coverage or the presence of a particular project.

No visible candidate means only that none was found in the inspected scope with
current permissions. Exports can live in a central project. Ask for that project's
client mapping or the existing destination shown in Cloud Billing's Billing
export page; do not scan all accessible projects/accounts. If access is unavailable,
offer analysis of a user-supplied billing extract with confirmed scope/coverage.

## Hand off to analysis

Return discovered table IDs, location, schema type, partitioning and access gaps.
Reuse a designated query project from the profile/session. If absent, propose a
confirmed client project and ask which project should pay for jobs; the export's
location or the active gcloud default does not establish that choice. Combine
this with unresolved target/source questions instead of repeated prerequisites.

Use the supplied period or the SKILL.md default. Derive currency by grouping the
resource- and time-filtered result; do not run an unfiltered distinct-currency or
project-inventory query. Then follow the billing reference: dry-run the actual
query in the designated project/location and reuse an existing bytes ceiling or
request one with the estimate before executing. Keep discovered client details
outside the reusable package; only update a private profile when requested.

Sources checked 2026-09-24: [project billing info](https://docs.cloud.google.com/sdk/gcloud/reference/billing/projects/describe),
[bq metadata commands](https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference),
[export schemas](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-tables),
[export destination settings](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-setup).
