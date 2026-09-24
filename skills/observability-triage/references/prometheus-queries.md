# Prometheus alerts and metric queries

Use this procedure for a standalone Prometheus HTTP API. Apply the collection
limits and response checks in [backend queries](backend-queries.md). It also
supports analysis of supplied offline responses without connecting to a backend.

## Endpoint and access

Use the supplied base URL, preserving any reverse-proxy path prefix. Apply the
requested resource selectors; when the user selects the whole instance, an
instance-wide summary is appropriate. Discover actual labels rather than assuming
`cluster`, `namespace` or `service` exists. External labels need not appear on local
series. Use an established tenant mapping if the backend requires one; never guess.

Use existing authentication when required and preserve TLS verification. Do not
follow redirects to another host automatically. A login page (even HTTP 200),
401/403 or connection failure is an access gap, not an empty result. For an
explicit API smoke test, `vector(1)` checks access without reading stored series.

## Choose the smallest read

In addition to the backend guide's HTTP limits, set a server query timeout and
limit returned series (initially 100). A query `limit` does not bound computation
or samples per series. Metadata endpoints have their own filters and limits;
check support against the deployed version and inspect returned identities.

| Request | API and parameters | Interpretation |
| --- | --- | --- |
| Firing/pending alert instances for a resource | `/api/v1/query` with scoped `ALERTS{...}`; optionally `alertstate="firing"` or `"pending"` | Returns synthetic state series, not annotations or notification receipts |
| Current alert details | `/api/v1/alerts` | Instance-wide response; use only when that collection scope is selected, then project relevant fields locally |
| Exact alert definition and evaluation | `/api/v1/rules` with `type=alert`, `rule_name[]`, optionally `rule_group[]`, and `exclude_alerts=true` when only the definition is needed | Inspect expression, duration, state, health, last error/evaluation and group interval |
| Available metric names | `/api/v1/label/__name__/values` with scoped `match[]`, `start`, `end`, `limit` | Candidate names within the selected window; confirm actual samples separately |
| Labels on one candidate metric | `/api/v1/series` with a metric-specific scoped `match[]`, `start`, `end`, `limit` | Series metadata does not establish a fresh sample |
| Metric type/unit/help | `/api/v1/targets/metadata` with `match_target`, `metric`, `limit` | Only directly scraped target metadata; absent metadata does not prove absent remote-written data |
| One observation or trend | `/api/v1/query` with `time`, or `/api/v1/query_range` with `start`, `end`, `step` | Include the exact expression, time/window, warnings and coverage in the answer |

For metadata not available per target, `/api/v1/metadata?metric=<name>` can help,
but does not bind a definition to the selected target. Report conflicting types
or units. Choose a few relevant metric families before expanding discovery;
avoid an unscoped catalog or broad regex over every metric.

## Alerts: current state, history and notifications

`/alerts` has no documented label selector or pagination; `match[]` does not scope
it. Use scoped `ALERTS` series for a resource and report unavailable details when
instance-wide collection would exceed the selected scope or response bounds.

Resolve rules by name, group/file and labels. Rule API `match[]` filters configured
rule labels, not labels inherited from expression results. Use `exclude_alerts=true`
for definitions whose instances exceed the selected scope; a null or omitted
`alerts` field then means excluded details, not no active alerts. An unconsumed
`groupNextToken` means incomplete coverage; `group_limit` caps groups, not instances.

Report `ALERTS` counts as alert series, not unique incidents: federation/replication
can duplicate alerts. Check the deployed `for`, `keep_firing_for` and evaluation
health before explaining pending or firing state.

For past state, range-query retained `ALERTS` series. Report retention, gaps and
step resolution; coarse steps can miss brief transitions. Current `/alerts` and
`/rules` responses do not provide history. Notification delivery requires separate
Alertmanager/routing evidence; firing alone is insufficient.

## Choose useful metrics from observed instrumentation

For service traffic, prefer request rate, error fraction and latency. For resource
pressure, inspect CPU, memory, disk capacity/I/O and saturation signals that the
selected exporters actually provide. For Kubernetes health, discover restart,
readiness and pending-workload metrics only when kube-state-metrics or equivalent
instrumentation exists. Do not require Kubernetes API access for existing metrics.

The following are synthetic templates, valid only after discovery confirms these
metric types, seconds units and labels. Replace the example identifiers and add
all required tenant/cluster filters consistently. Do not widen scope when a
selector returns no data.

```promql
# Request rate (counter -> requests/second)
sum(rate(http_requests_total{cluster="example-apps",namespace="shop",service="orders"}[5m]))

# 5xx percentage; same population and time window in numerator and denominator
100 * sum(rate(http_requests_total{cluster="example-apps",namespace="shop",service="orders",status=~"5.."}[5m]))
  / sum(rate(http_requests_total{cluster="example-apps",namespace="shop",service="orders"}[5m]))

# P95 seconds for a classic histogram, preserving bucket boundaries
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{cluster="example-apps",namespace="shop",service="orders"}[5m])))

# Scrape health for the selected job; this is not application availability
up{cluster="example-apps",job="orders"}
```

Apply `rate` before aggregation so per-series counter resets are handled. Choose
a rate window with enough scrapes (typically at least four scrape intervals).
An absent 5xx series is not automatically a measured zero. Check exporter semantics
before filling missing values; a zero total request rate makes the fraction
undefined. Keep classic histogram `le` labels when aggregating buckets; native
histograms use a different query shape. Do not average instance percentiles or
combine duplicate HA/mesh observations. Use deployed recording rules only after
checking their expression, labels, units and evaluation health.

For a requested comparison, use equal-duration windows, the same selector,
aggregation and resolution, and report gaps in either window. Return available
metrics and missing instrumentation instead of inventing a universal dashboard.

Grafana `label_values(...)` and dashboard variables such as `$namespace` are not
direct PromQL API expressions; use the discovery endpoints and verified literal
selectors when querying Prometheus directly.

Sources checked 2026-09-24:
- [Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/)
- [Alerting rules and ALERTS series](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [PromQL functions](https://prometheus.io/docs/prometheus/latest/querying/functions/)
