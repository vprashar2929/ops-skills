# Istio evidence for an established communication path

Discover the served networking/security APIs and installed mesh mode/version.
Native sidecars can be initContainers with restartPolicy Always; lack of a normal
istio-proxy container alone does not mean no mesh. Ambient traffic needs the
actual ztunnel/waypoint path; do not force sidecar commands onto it.

For the specific host/port, inspect applicable VirtualService hosts/gateways,
match order and destination host/subset/port. Compare DestinationRule subset
labels against ready endpoints. Establish visibility (exportTo), namespace and
short-host resolution. A VirtualService can exist without governing this source.
Inspect relevant ServiceEntry/Sidecar restrictions only when the path uses them.

For ingress, distinguish Kubernetes Gateway/HTTPRoute attachment/status from
Istio Gateway/VirtualService configuration. Inspect parent conditions and backend
references for Gateway API; do not infer acceptance solely from object creation.

For TLS/authentication failures correlate server PeerAuthentication scope with
client DestinationRule TLS settings and applicable AuthorizationPolicies. Policy
existence alone is not proof of a deny. Check the selected workload, port, principal
and the request evidence. Read certificate identity/expiry metadata only; never
dump private keys, credentials or full proxy secret/config dumps.

Live `istioctl proxy-config` reads can internally port-forward to Envoy's admin
endpoint. They are outside this skill's no-port-forwarding boundary; do not use
them as a workaround. Analyze an already supplied, sanitized proxy artifact
offline if available, using a compatible CLI and its supported file-input flags.
Otherwise report that effective proxy configuration remains unverified.
Use a finite execution timeout. `istioctl analyze` can reveal configuration issues,
but scope to the target namespace and state if inaccessible dependencies limit it.
Do not pass `proxy-config log --level`: that changes runtime logging.

Use the community guide's routing/resilience examples to interpret the deployed
configuration, not as assumed defaults or remediation to execute. Verify example
fields against the served API/version. Its simplified path is not proof that
every request traverses a Gateway or that every ServiceEntry is mesh-wide.
Routing weights, retry budgets, connection limits and outlier thresholds must
come from actual configuration; never introduce fault injection or mirroring to
validate a hypothesis. Our scope and the verified mesh mode take precedence.

Correlate response flags/details with the actual proxy version and timestamps.
Do not equate every upstream connection failure with mTLS, or every 503 with an
empty Service. Mesh-wide PromQL can mix reporters/namespaces/clusters: select the
actual labels and reporter before interpreting error rates.

Sources, checked 2026-09-21:
- [Istio 1.29.2 Envoy request transport](https://github.com/istio/istio/blob/1.29.2/pkg/kube/client.go)
- [Istio proxy diagnostics](https://istio.io/latest/docs/ops/diagnostic-tools/proxy-cmd/)
- [Traffic management troubleshooting](https://istio.io/latest/docs/ops/common-problems/network-issues/)
- [Security troubleshooting](https://istio.io/latest/docs/ops/common-problems/security-issues/)
