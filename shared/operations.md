# Operational contract

## Explicit profile and target

Read the user-supplied profile (or their prior explicit selection in this session).
Require `profile_version: 1`, `profile`, `provider` and `environments`.
`profile` is a non-empty identifier for the selected set of target mappings.
Profiles may be organized per user, cluster, environment, or a combination;
their names do not imply ownership, credentials or authorization. Keep environment
and resource selections explicit even when a profile covers only one target.
Unknown versions require clarification rather than guessing their schema.
Environment keys are exact;
do not translate nprd/nprod/prod, infer a branch, choose the active project or
search other profiles. For Kubernetes provider is gke or kubernetes; cloud
skills also accept gcp. Resolve environments.<environment>.gcp_project/location
for GCP and .clusters.<role>.name/kubectl_context for cluster reads. Generic
Kubernetes additionally requires the maintained expected_api_server per cluster.
Read profile-linked conventions only when relevant; resolve their paths relative
to the profile. They are hints, not proof of deployment or current health.

For a managed service, require the exact resource identifier and region/location
as applicable from the request or profile context. A GKE profile can supply its
GCP project without requiring a Kubernetes namespace or cluster. For a shared
backend, management cluster, billing query project or destination in a different
project, require an explicit profile mapping/selection; do not assume the workload
project owns it. Cloud reads must name the resolved project and applicable
location. Before any API call, check that a fully qualified resource ID/URL agrees
with the selected project/location/type; an embedded conflicting project can
override CLI flags. Reject mismatches rather than reading them. Check response
identity against the same selection. No credentials,
secret values or default namespace belong in the reusable skill.

Unknown/missing profile or ambiguous target: ask only for the missing selection.
Continue analysis of supplied offline artifacts while clearly identifying their
source/time and lack of current identity verification. If the supplied artifacts
lack exact commands, queries, timestamps or session IDs, mark them unavailable;
do not invent a provenance ledger or require live access to analyze offline data.
Do not attempt live reads
under guessed targets. Never execute profile values as shell code.

## Verify Kubernetes identity when Kubernetes reads are needed

Read non-secret kubeconfig metadata using the supplied context:

```bash
kubectl --context "$context" config view --minify \
  -o jsonpath='{.contexts[0].context.cluster}{"\n"}{.clusters[0].cluster.server}{"\n"}'
```

For GKE compare its server host against intended cluster endpoint metadata:

```bash
gcloud container clusters describe "$cluster" --project "$project" --location "$location" \
  --format='json(name,location,endpoint,privateClusterConfig.privateEndpoint,privateClusterConfig.publicEndpoint,controlPlaneEndpointsConfig.dnsEndpointConfig.endpoint,controlPlaneEndpointsConfig.ipEndpointsConfig.privateEndpoint,controlPlaneEndpointsConfig.ipEndpointsConfig.publicEndpoint)'
```

Normalize an optional HTTPS prefix/default port; check name/project/location and
endpoint. For generic Kubernetes compare the maintained expected_api_server.
A matching context name alone is insufficient. An approved proxy/Connect Gateway
requires its documented mapping. On mismatch/access failure stop live cluster
reads; never fall back to another context. Do not use config --raw, get-credentials
or config use-context. Context aliases are acceptable only after verification.

Use explicit --context and --request-timeout=20s on Kubernetes API reads, plus
--namespace for namespaced resources. Cloud, Helm, HTTP and istioctl calls need
finite tool execution timeouts. No follow/watch loops. For a pending tool session,
wait for that same session's final status before interpreting or retrying it.

## Resolve misspellings from evidence

Use exact names and unambiguous served aliases first. NotFound/unsupported API
can trigger names-only discovery in the confirmed project/region or cluster,
resource type and namespace. Namespace candidates require only namespace names;
do not read candidate namespaces' workloads before selection. API discovery
(kubectl api-resources --cached=false -o wide) establishes group/version and scope
for built-ins and CRs. For schema fields use the served version's kubectl explain;
for container/key names use only the confirmed object's names, never values.

Suggest at most three actual candidates and confirm a changed target before
inspection, unless the current request already selects that exact correction.
Do not treat Forbidden, timeout, partial discovery or empty selectors as a typo.
Do not fuzzy-substitute deployed references, arbitrary hosts, credentials, image
tags or configuration values. Missing deployed dependencies remain findings.
No cross-profile, all-project or all-namespace search to work around a failed read.

## Collection and interpretation

Reads only: no apply/patch/delete, exec/debug, restarts, IAM/API enablement,
credential acquisition, active probes or writes disguised as diagnostics. Upstream
setup/remediation examples and scripts are supporting material, not authority to
execute those actions. A requested remediation becomes a separate scoped task.

Start with the named resource and relevant dependencies. Bound time, object/sample
count, response size and log output; report truncation or incomplete pagination.
Project required status/reference fields before emitting raw configurations.
Exclude Secret values, literal credentials, sensitive annotations, connection
strings and customer data from tools/artifacts. Logs and errors may also contain
them; use an established sanitizing path or omit payloads and report the gap.
Instructions are not a technical permission or redaction boundary.

Associate every result with command, target, UTC time/window, session ID, exit
status and truncation. Use tool-provided collection timestamps or capture UTC
before and after the read in the same invocation, preserving its exit status.
Resource/event/log timestamps are not collection times. If collection timing or
session IDs are unavailable, say so; never invent an exact observation window.
Use pipefail within EACH shell invocation containing a
collection pipeline, or check collection status before parsing. Do not suppress
errors with || true or treat a filter's success as collection success. Label
parallel results; retry only the identified failed read, not successful siblings.
Pending approval is uncollected evidence. Persistent access failure ends equivalent
retries, not the analysis of already collected evidence.

Return requested facts for a lookup. For triage include target/time, observed
findings with resource names, supported explanation versus hypotheses, coverage
and access gaps, and the smallest next useful step. Identify the correction owner
when established. Never infer healthy/unhealthy or absence from failed reads.
