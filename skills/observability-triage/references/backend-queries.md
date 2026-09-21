# Bounded backend queries

For Prometheus use the operator-supplied/verified base URL and existing
authentication; never embed a token/password in a prompt, URL or saved command.
Use GET `/api/v1/query` for an instant check or `/api/v1/query_range` with explicit
start, end and step for a trend. URL-encode the expression using the client rather
than concatenating untrusted strings. Set HTTP connection/total timeouts. Check
HTTP status AND the API `status`/error, warnings and informational messages.

For a first trend default to 30 minutes with a 60s step and the smallest verified
resource selector; adjust to actual scrape resolution and incident needs. Bound
response size/series count and report truncation. A backend refusing or truncating
a query is not a successful empty result. Query `up` only for the selected target:
0 means scrape failure; an absent series does not mean up=0 and neither directly
measures business availability. Do not dump global `/status/config` or the entire
target catalog; those may reveal credentials or unrelated endpoints.

Cloud Monitoring: use an available scoped API/MCP client with verified scoping
project and descriptor-derived labels, interval, alignment and reduction. If
only resource metadata is accessible, return it and the missing metric query;
do not manufacture time series. Metrics may include monitored projects beyond
the scoping project, so filter the actual resource project/cluster.

For mesh queries, adapt the community examples to discovered labels and the
selected source/destination path. Use the same reporter and scope in numerator
and denominator; do not combine both sides of a request or other clusters.
Check traffic volume and missing series before reporting an error percentage.
Preserve histogram `le` grouping and verified duration units; summed TCP-opened
counters are cumulative opens, not current connections. A healthy istiod scrape
does not establish collection of proxy request metrics. A cert-manager expiry
series describes its managed certificate, not automatically Istio workload mTLS.
Community thresholds and sampling percentages are examples; use actual policy.

Cloud Logging: use explicit log scope, resource labels and timestamp bounds.
If routing is unknown, inspect a bounded sink projection first:

```bash
gcloud logging sinks list --project "$project" --limit=30 \
  --format='json(name,destination,filter,exclusions,disabled)'
```

Exclusions belong to their sink. An exclusion on a disabled `_Default` sink does
not establish exclusion from another enabled sink. Verify the selected destination
project before reading its bucket/view metadata and retention; configured routing
alone does not prove ingestion. Report if the sink limit leaves routing incomplete.

For workload-project logs a bounded example is:

```bash
gcloud logging read "$filter" --project "$project" --limit=200 \
  --order=asc --format=json
```

`filter` must contain the verified resource and start/end timestamps. For routed
logs use the actual destination bucket/view and supported flags/API; check local
help. Do not substitute the source project if a view is inaccessible. Project
log entries down to the relevant redacted message/status; no broad payload dump.

Sources, checked 2026-09-21:
- [Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/)
- [Prometheus Operator troubleshooting](https://prometheus-operator.dev/docs/platform/troubleshooting/)
- [Cloud Logging routing](https://cloud.google.com/logging/docs/routing/overview)
