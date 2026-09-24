# Workload state, rollout, and logs

## Start with the requested resource

Inspect only needed controller fields: generation/observedGeneration, desired and
ready replicas, conditions, selector, update strategy, Pod-template images,
resources, probe settings, service account, and configuration references.
Avoid full YAML/describe dumps: literal environment values, annotations, command
arguments, and probe headers can contain credentials. For a resource-limit lookup:

```bash
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get "$workload" -o jsonpath='{range .spec.template.spec.containers[*]}{.name}{"\t"}{.resources}{"\n"}{end}'
```

That path is for controllers with a Pod template. Adapt to `.spec.containers`
for a Pod and `.spec.jobTemplate.spec.template.spec` for a CronJob. Inspect init
containers as well when relevant. Discover the resource kind instead of assuming
everything is a Deployment.

For controller diagnosis, retrieve its selector and ownership metadata, then find
matching Pods. Account for `matchExpressions`, not only `matchLabels`; verify
ownerReferences so overlapping selectors do not mix workloads. A Deployment's
Pods normally belong to ReplicaSets. Check both current and previous ReplicaSets
when rollout state matters. Follow the appropriate owner chain for Jobs,
CronJobs, StatefulSets, and DaemonSets.

For selected Pods inspect readiness, scheduling conditions, deletion timestamp,
node, container/init-container state and lastState, restart count, images and
imageIDs. Ready is an observation, not proof of successful application requests.
Exit 137 alone is not proof of OOM; exit 128 is not a unique diagnosis. A completed
Job and an unexpectedly exiting long-running server have different meanings.

Query events for the relevant object's UID so recreated names do not conflate
incidents. Include controller and Pod events as needed:

```bash
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get events --field-selector "involvedObject.uid=$uid" \
  --sort-by=.metadata.creationTimestamp
```

Inspect last/event/series timestamps and counts, not only creation time. Events
have limited retention; no events does not establish no incident. Fetch node/PVC
status only if scheduling, storage, eviction, or node evidence makes it relevant.

## Logs

Discover container names first; distinguish application, init, and sidecar logs.
For current incidents, use selected Pods and named containers, for example:

```bash
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  logs "$pod" --container "$container" --since=30m --tail=200 \
  --timestamps=true --pod-running-timeout=10s
```

For restarting containers retrieve a separate bounded `--previous` sample early,
before suggesting anything that destroys evidence. Previous logs cover only the
retained previous container instance. Absence can mean rotation/retention, a
replaced Pod, no prior instance, or lack of access; report the actual result.
Avoid `--all-containers` as a default and never run `env`, `printenv`, or dump
mounted files inside Pods to investigate secrets.

For a historical start use `--since-time` instead of `--since`; kubectl logs does
not provide an end-time filter. State any truncation and prefer the configured
log backend for precise historical windows. Redact sensitive excerpts before
including them in a report; raw log collection can itself expose sensitive data
to the agent, so avoid unrelated streams and use an existing filtered backend
when the selected profile requires one.

Cloud Logging is an optional GKE fallback, not assumed to contain all Pod logs.
Use the verified log project/bucket/view when provided. Otherwise a bounded query
in the workload project is only a check of that scope. Example filter:

```text
resource.type="k8s_container"
resource.labels.project_id="PROJECT"
resource.labels.location="LOCATION"
resource.labels.cluster_name="CLUSTER"
resource.labels.namespace_name="NAMESPACE"
resource.labels.pod_name="POD"
resource.labels.container_name="CONTAINER"
timestamp>="START_UTC"
timestamp<="END_UTC"
```

Pass the composed filter as one quoted argument to `gcloud logging read`, with
explicit `--project`, `--limit=200`, `--order=asc`, and projected fields appropriate
to the question. Timestamps belong in the filter; do not use unsupported
`--start-time`/`--end-time` flags. Do not interpret an empty result as proof that
the application produced no logs; routing, exclusions, retention, permissions,
and sampling can explain it.

## Rollout and dependencies

Correlate controller generations, revisions, actual imageIDs, Pod start times,
conditions and observed symptoms. Establish delivery ownership from live
metadata and relevant source/run evidence. A Helm label does not establish that
the newest local chart or values were deployed. If relevant, use scoped
`helm --kube-context "$context" --namespace "$namespace" history "$release"`;
avoid `helm get all`/unfiltered values. For Argo, inspect the identified
Application's source revision and effective sync policy using its explicit
management context/namespace from profile context; never guess those or sync it.

A failed pipeline may already have rolled back or uninstalled a release. Existing
failure artifacts can describe a different revision than current Pods. Inspect
the actual run/artifact before blaming the live revision. Do not execute cleanup
scripts. For jobs/migrations report active/completed/failed state before proposing
rollback; application rollback may not reverse database side effects.

If logs implicate another service, inspect the named Service, selector,
EndpointSlices, endpoint readiness/ports, and applicable policies first. Empty
endpoints can reflect selector mismatch, readiness, intentional external service
configuration, or a missing backend. Endpoints existing does not prove
connectivity; timeout does not prove NetworkPolicy denial. Inspect Istio objects
or managed-service status only when the evidence calls for it. Cross-namespace,
cluster, or project targets need an explicit verified mapping before reads.
