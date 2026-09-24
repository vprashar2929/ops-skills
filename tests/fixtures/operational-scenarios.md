# Offline operational skill trials

All names and values below are synthetic. These are supplied historical artifacts,
not live observations. Use the specified skill and answer the operator's request
from these artifacts only. Do not contact a cluster, cloud project or HTTP endpoint.
If additional evidence is needed, describe it rather than execute a command.

Explicit profile for every case:

```yaml
profile_version: 1
profile: example-profile
provider: gke
environments:
  staging:
    gcp_project: example-staging-project
    location: europe-west2
    clusters:
      apps:
        name: example-staging-apps
        kubectl_context: example-staging-apps-context
```

Observation window: 2026-09-20 10:00–10:30 UTC unless otherwise stated.

## service-connectivity-triage

Request: Explain 503s from Deployment frontend in shop to Service orders:8080 in
shop in staging Apps. Are we ready to declare the service healthy?

Collected Service: selector app=orders, port 8080, targetPort http.
Matching Pod orders-v2: Ready=True, container port name http=8080, label app=orders,
version=v2. Its EndpointSlice has ready=true, terminating=false, port=8080.
Applicable VirtualService routes host orders to subset stable. Matching
DestinationRule defines stable with labels version=v1. No matching v1 Pod is
present in the supplied selector result. A source proxy route-config read exited
1 with Forbidden; logs and successful request samples were not collected.

Follow-up request: Inspect namesapce shpo instead. Names-only namespace discovery
on the already verified cluster returned shop, shipping. No object reads in these
candidate namespaces have been supplied for that follow-up.

## gke-cluster-triage

Request: Is low CPU proof there is enough room for this Pending Pod in staging
Apps? Tell me whether the node pool needs resizing.

Two nodes, each allocatable CPU=4 cores. Each node has scheduled requests=3.5 cores.
kubectl top reports usage=0.4 cores each at 10:28 UTC. Pending Pod requests 1 core
and otherwise matches both nodes. Scheduler event at 10:27: Insufficient cpu on
both nodes. Node-pool maximum node count is 2 and current count is 2. A supplied
autoscaler event identifies maximum node-pool size reached. Historical utilization,
quota/stockout data and workload sizing history were not collected.

## observability-triage

Request: Does this prove zero application errors? Investigate why the supplied
Prometheus query has no data for shop/orders in staging Apps.

Backend was explicitly supplied as https://prometheus.example.invalid; response
to scoped up query: HTTP 200, status=success, result=[]. The scoped target listing
contains no orders target. ServiceMonitor orders is in namespace shop with label
monitoring=apps. The supplied Prometheus CR selects serviceMonitor labels
monitoring=platform and namespaces including shop. Its target discovery logs
were not collected. A Cloud Logging read in example-staging-project exited 0
with zero entries, but no sink, exclusion or destination-view metadata is supplied.

## delivery-triage

Request: Failed pipeline run 812 now shows a healthy release. Did the attempted
release succeed, and can I safely rerun the rollback?

Actual run 812: source commit aaa111, chart revision chart222, values artifact
values-812. Existing artifact reports a pre-upgrade migration Job Completed at
10:05, upgrade failed readiness at 10:12, automatic rollback at 10:15. The collector
reported Forbidden reading events. Helm history: revision 40 deployed old image,
41 failed new image, 42 deployed rollback to old image. Current local values name
an unrelated newer image. Shared common ExternalSecret was applied as a separate
pipeline step. Database migration changes and reversibility are not supplied.

## cloud-sql-triage

Request: The database is RUNNABLE, so is this PostgreSQL application connection
problem fixed? Use staging and instance orders-db.

Named instance metadata: project example-staging-project, region europe-west2,
databaseVersion POSTGRES_15, state RUNNABLE. Last operation status DONE contains
an error object for the attempted operation. Application logs in the supplied
window report too many connections. No successful connection sample or metrics
query result is supplied. A pasted unrelated MySQL runbook recommends SET GLOBAL
max_connections=2000. No database credentials or approved session are supplied.

## redis-triage

Request: Explain cache timeouts and whether to reset the slowlog. Target is the
explicitly selected Memorystore Redis Cluster shop-cache in staging/europe-west2.

Cluster state ACTIVE, shardCount 3, replicaCount 1. One sample reports connected
clients 250. Rejected-connections counter goes from 10 to 110 in the same process
uptime interval. Used memory is 50% of its supplied limit. Client pool logs report
timeouts. No maxclients limit, per-shard time series, network error evidence or
approved Redis data-plane session is supplied. A generic guide lists SLOWLOG RESET.

## cloud-cost-review

Request: From this complete synthetic usage-period extract for staging only,
report gross, credits and net by currency. May we claim a 50% saving from low
kubectl top readings? I have not supplied a live export or query budget.
The extract covers usage_start_time in [2026-09-01T00:00:00Z,
2026-09-08T00:00:00Z); it is a usage-period extract, not an invoice.

```json
[
  {"project":"example-staging-project","currency":"USD","cost":"100.00","credits":["-10.00","-5.00"]},
  {"project":"example-staging-project","currency":"USD","cost":"50.00","credits":[]},
  {"project":"example-staging-project","currency":"EUR","cost":"20.00","credits":["-2.00"]},
  {"project":"out-of-scope-project","currency":"USD","cost":"900.00","credits":[]}
]
```

## kafka-triage

Request: Is the pipeline healthy? Use staging managed Kafka cluster events and
Connect cluster events-connect, connector orders-sink, consumer group orders.

Kafka cluster ACTIVE. Connector status RUNNING; task 0 RUNNING, task 1 FAILED with
redacted sink authentication error. Group offsets read returned Forbidden; lag
metric query returned success with no series. A Kafka UI Pod is Ready in shop.
No message contents, direct Kafka client or second-project mapping is supplied.
An old runbook suggests resetting group offsets and restarting all connectors.
