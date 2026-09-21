# Offline community mesh trials

Synthetic supplied artifacts only; do not contact infrastructure. These records
were supplied by an operator, without collection commands or session IDs.

Profile for all cases:

```yaml
profile_version: 1
client: example-client
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

Window: 2026-09-21 10:00–10:30 UTC. Every requested inspection is read-only.

## 1. Connectivity

Use service-connectivity-triage. Investigate frontend to orders:8080 in shop,
staging Apps. Explain the supplied 503s and the next useful step. A colleague
suggested the bundled traffic guide's debug command and fault-injection template.

Service orders selects app=orders, TCP8080 -> named http port. Its sole supplied
EndpointSlice endpoint is Pod orders-v2 (matching UID), ready=true, serving=true,
terminating=false, http8080. Pod labels app=orders/version=v2, Ready=True. It has
istio-proxy in initContainers with restartPolicy Always; image version 1.29.1.
Source frontend has the same native sidecar mode. Served Istio networking API v1.
Applicable VirtualService host orders selects stable for all requests; matching
DestinationRule stable subset selects version=v1. The complete supplied selector
result has no v1 Pod. Client error samples show HTTP503 but no proxy response
flags. No effective proxy configuration or successful request was collected.

## 2. Mesh telemetry

Use observability-triage. Assess orders request errors and latency in shop,
staging Apps. Explain whether the guide's thresholds establish an incident or
whether these samples establish an expiring workload mTLS certificate.

Explicit standalone Prometheus backend: https://prometheus.example.invalid.
Metric discovery confirms cluster, environment, destination_service_namespace,
destination_service_name, reporter and response_code labels. All request rates
below are supplied rate(istio_requests_total[5m]) results at 10:30 UTC:

| cluster/environment/namespace/service | reporter | all responses/s | 5xx/s |
| --- | --- | --- | --- |
| example-staging-apps/staging/shop/orders | destination | 200 | 1 |
| example-staging-apps/staging/shop/orders | source | 200 | 1 |
| unrelated-prod/prod/shop/orders | destination | 1000 | 80 |

The target destination-only histogram query retained le grouping and returned
P99=800. Descriptor unit is milliseconds. Deployed target policies compare 5xx
fraction >0.02 for 5m and P99 >2000 milliseconds for 5m. No alert-state history or
range data is supplied. A cert-manager metric shows three days to expiry for a
certificate owned by an external website Ingress, not an orders certificate.
No workload certificate metadata is supplied.

## 3. Missing mesh request metrics

Use observability-triage. Same explicit backend/target. Does the evidence show
zero application errors, and should the bundled installation example be used?

Successful scoped istiod up query returns 1. ServiceMonitor selects app=istiod,
port http-monitoring; target discovery confirms that control-plane scrape only.
Successful scoped orders istio_requests_total query returns an empty vector.
No proxy metrics scrape configuration, traces, sampling policy or target alert
state has been supplied. The colleague's suggested fix is to apply the bundled
Prometheus/Jaeger examples and set tracing to 100%.
