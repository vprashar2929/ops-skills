---
name: service-connectivity-triage
description: Diagnose Kubernetes service reachability, timeouts and HTTP routing failures using Service, EndpointSlice, network policy and Istio evidence with an explicit client profile. Use for a named source-to-destination path; does not provision networking or run traffic probes.
---

# Service connectivity triage

Read [operations](references/operations.md) before collection. Requires kubectl
and cluster access; gcloud for GKE identity; compatible istioctl only for offline
proxy inspection or namespace-scoped analysis. HTTP logs/metrics are optional.

## Establish the path

Resolve client profile, environment, cluster, source workload/namespace,
destination namespace and Service or explicit hostname:port, protocol, symptom
and incident window. Source can be an external client for ingress incidents.
If the request is only a Service lookup, return its requested configuration;
do not require a source or claim end-to-end reachability.

Verify cluster identity first. An external destination is not permission to scan
its network; inspect only explicitly implicated resources. For another cluster,
verify its identity and client scope separately before reading it.

## Trace the smallest implicated path

1. Read the named Service's type, selector, port/targetPort/protocol and
   publishNotReadyAddresses. Then query its EndpointSlices in the same namespace
   using `kubernetes.io/service-name=<service>`. Discover served APIs first.
   Preserve ready/serving/terminating conditions and targetRef identities.
2. Compare the selector with Pod labels and readiness. Resolve a named targetPort
   against the selected container ports; a declared port does not prove a listener.
   A Service without a selector may have manually managed endpoints; ExternalName
   and headless Services require their actual DNS semantics, not a ClusterIP test.
   Empty endpoints, terminating endpoints and failed API reads are different.
3. If DNS is implicated, inspect source dnsPolicy/dnsConfig and established
   cluster DNS configuration/logs. Do not assume the cluster domain or infer DNS
   success from a Service object's existence. Distinguish NXDOMAIN from timeout.
4. Inspect applicable source egress and destination ingress NetworkPolicies,
   namespace/Pod selectors, ports and the installed CNI's support. Across clusters
   or external endpoints, Kubernetes selectors alone cannot establish the path.
5. For an evidenced Istio path, use [Istio inspection](references/istio.md).
   When interpreting route matches, subsets, retries or outlier detection, consult
   the [community traffic guide](references/community-istio/guide.md) as needed.
   Its templates and debug commands do not override the inspection boundaries.
   Do not assume every Pod is injected, or that a named Gateway is an Istio CR
   rather than a Kubernetes Gateway API object. Discover kind/group/version.
6. Inspect cloud load-balancer, DNS, firewall or PSC metadata only when implicated
   and mapped to this target. For GKE network context consult the bundled
   [Google networking guide](references/google-gke-networking/guide.md).
   Its setup commands are reference material, not an execution plan.

Example bounded collection after target verification:

```bash
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get service "$service" \
  -o 'custom-columns=NAME:.metadata.name,TYPE:.spec.type,SELECTOR:.spec.selector,PORTS:.spec.ports[*].port,TARGETPORTS:.spec.ports[*].targetPort'
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get endpointslices.discovery.k8s.io -l "kubernetes.io/service-name=$service" \
  -o 'custom-columns=NAME:.metadata.name,ADDRESSES:.endpoints[*].addresses,READY:.endpoints[*].conditions.ready,SERVING:.endpoints[*].conditions.serving,TERMINATING:.endpoints[*].conditions.terminating,TARGETS:.endpoints[*].targetRef.name,PORTS:.ports[*].port'
```

Project needed fields before emitting full Service/configuration objects; exclude
arbitrary annotations. Inspect a small named Pod sample and at most 200 log lines
per container for the requested window, default last 30 minutes.
For multiple endpoints, use a per-endpoint projection that preserves address,
conditions and targetRef kind/namespace/name/UID associations; the compact table
is an overview and must not be used to zip independent wildcard arrays together.

## Boundaries and result

No exec/debug Pods, port-forwarding, packet capture, active curl/DNS probes from
workloads, log-level changes, apply/patch, routing changes or Connectivity Test
creation/reruns. Propose a separately scoped probe if configuration cannot decide.

Return the observed path and failure evidence, time/window and sample, likely
cause versus alternatives, and the first unverified hop. A valid route or ready
endpoint is configuration evidence, not proof of a successful request. A 503 alone
does not identify whether the application, gateway or proxy generated it.

Example: "Use this client profile in dev Apps to investigate HTTP 503 from source
deployment/frontend to Service orders:8080 in namespace shop over the last 30m."
