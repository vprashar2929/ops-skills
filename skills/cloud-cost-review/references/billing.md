# Billing query construction

Inspect the schema first; this shape is for the standard usage export's cost and
credits fields. Substitute the verified table ID as an identifier, not shell
code. Pass values as query parameters. Keep currency separate and count rows
before attribution splits. This example reports usage time, not invoice totals.

```sql
SELECT project.id AS project_id, service.description AS service, currency,
       SUM(CAST(cost AS NUMERIC)) AS gross_cost,
       SUM(IFNULL((SELECT SUM(CAST(c.amount AS NUMERIC))
                   FROM UNNEST(credits) c), 0)) AS credits,
       SUM(CAST(cost AS NUMERIC))
         + SUM(IFNULL((SELECT SUM(CAST(c.amount AS NUMERIC))
                       FROM UNNEST(credits) c), 0)) AS net_cost
FROM `EXPORT_PROJECT.DATASET.TABLE`
WHERE project.id IN UNNEST(@resource_projects)
  AND usage_start_time >= @start_time AND usage_start_time < @end_time
GROUP BY project_id, service, currency
ORDER BY net_cost DESC
```

The placeholders are inputs, not an actual client table. Apply a correct
partition predicate for the discovered schema without silently dropping late
arrivals; dry-run if scan pruning is uncertain. For invoice reconciliation use
invoice.month intentionally and explain delayed corrections and projectless
charges outside a project-filtered scope. Do not promise an account invoice match
for a project subset. Preserve cost_type or clearly state which types are included.

For a verified ingestion-time partitioned table, an additional predicate can be:

```sql
  AND ((_PARTITIONTIME >= @ingestion_start AND _PARTITIONTIME < @ingestion_end)
       OR _PARTITIONTIME IS NULL)
```

Keep the usage-time predicate too. Establish the ingestion coverage separately:
late exports/corrections can land after the usage window. Do not set ingestion
end equal to usage end automatically. Include NULL partitions when streaming
rows are relevant, and state any excluded coverage. A smaller scan is not proof
of complete billing history. Dry-run the actual combined predicates.

Use `bq --project_id=... --location=... query --use_legacy_sql=false --dry_run ...`
with a query file and parameter flags supported by local bq help. Execute the
same query/parameters with `--maximum_bytes_billed` only after its ceiling is
established. Keep SQL out of interpolated shell strings containing backticks.
No dynamic EXECUTE IMMEDIATE, DDL/DML, remote functions or EXPORT DATA in this
review. Query failure or unavailable partitions is an evidence gap.

Accounting checks: net = gross + signed credits for each currency; breakdowns
reconcile to the same filtered scope; empty credits preserve the base row;
multiple credits do not duplicate cost; missing allocation remains visible.
Use decimal arithmetic for supplied offline extracts as well. Suppress raw labels
containing client-sensitive identifiers from shared reports.

Source: [Cloud Billing example queries](https://cloud.google.com/billing/docs/how-to/bq-examples),
[partition pruning](https://docs.cloud.google.com/bigquery/docs/querying-partitioned-tables),
checked 2026-09-21. The supplied template is not proof of live table compatibility.
