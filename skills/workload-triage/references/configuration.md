# Configuration and secret wiring

Trace the configuration the specific container consumes: `env`, `envFrom`,
Secret/ConfigMap key references, projected volumes and mounts (including subPath),
CSI volumes when present, service account, and imagePullSecrets. Report reference
names, key names, optional flags, and mount paths. For literal env/command/header
values, inspect only an explicitly relevant, non-sensitive field; omit the rest.

Inspect ConfigMap metadata and key names first too: ConfigMaps may contain
credentials despite their resource type. Query a named Secret's metadata and
key names without printing its payload:

```bash
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get secret "$secret" \
  -o go-template='{{.metadata.name}}{{"\n"}}{{.metadata.uid}}{{"\n"}}{{.metadata.resourceVersion}}{{"\n"}}{{range $key, $value := .data}}{{$key}}{{"\n"}}{{end}}'
```

This avoids emitting values; it still requires permission to read the Secret
object from the API. Do not claim it is a metadata-only API permission. Never
dump Secret JSON/YAML, decode values, retrieve GSM payloads, or use last-applied
annotations as a shortcut. Do not claim a value is correct merely because the key
exists. An optional missing reference has different effects from a required one.

Explicit `env` entries override values imported by `envFrom`; competing `envFrom`
sources can also shadow a key. Identify the winning reference without disclosing
values. Secret/ConfigMap-backed environment variables are captured when the
container starts. Mounted data updates have different behavior; subPath mounts
do not receive those updates and applications may cache config. A changed API
object does not prove that an existing process loaded the new content.

## Compact key and synchronization summary

For repeated key/supplier checks, use the bundled Python 3 helper
`scripts/config_summary.py` (path relative to the skill directory). It accepts
only Secret, ConfigMap, ExternalSecret, or a List of those named objects on stdin;
it makes no network calls. Pipe API output directly into it without printing or
saving raw objects. Like kubectl's key-only template, it receives the object
including data locally but emits only allowlisted reference metadata and key
names. It is not a metadata-only API permission or a general log redactor.

```bash
set -o pipefail
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get "secret/$secret" -o json | python3 "$skill_dir/scripts/config_summary.py"
```

Follow the Secret's ExternalSecret owner reference first, verifying the owner UID
when supplied. If no such owner exists, do not assume the supplier shares its
name: use known delivery metadata, or a namespace-scoped projection of supplier
names and target names only. Once the supplier is identified and its API served,
summarize the two named resources together:

```bash
set -o pipefail
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get "secret/$secret" "externalsecrets.external-secrets.io/$external_secret" \
  -o json | python3 "$skill_dir/scripts/config_summary.py"
```

The summary counts all keys, samples at most 20 names per set and 20 distinct
stores (including per-key overrides), and compares explicit output keys with the matching target
Secret in the same namespace. Missing/extra sets are computed before sampling;
`omitted` reports hidden names. Use `--key "$key"` for one requested key's source
reference/version and presence. An absent remote version is reported as null,
not inferred to be a verified current source version. `dataFrom` or target
templating makes the expected key set indeterminate; the helper skips that
comparison. Extra keys alone do not establish failure (for example Merge policy).
Do not mistake the declared supplier mapping for proof of last successful sync.
For offline Secret manifests, `stringData` key names are included; manifest keys
are declarations, not evidence of what exists in a cluster. Sampled lists do not
establish absence or lack of overlap: use full-set counts/comparisons or an exact
`--key` query for omitted names.

This summary does not trace container precedence, mounted values, provider auth,
or actual process configuration. Inspect only the additional references needed
for the question. Label Deployment-template observations explicitly; they do not
cover admission-injected Pod configuration. If the helper fails, preserve its
failure and narrow the query; never fall back to printing the raw input.

## Deployment-template versus running-Pod configuration

Use this comparison when asked about effective/deployed Pod configuration or
injected containers/mounts, or when diagnosis needs that distinction. A simple
Deployment spec lookup does not need Pod sampling. This workflow initially
supports Deployment → ReplicaSet → Pod; do not invent that chain for other kinds.

1. Resolve and verify the target using targeting.md. Read Deployment identity,
   selector and revision using projections. Select a small Pod sample using the
   actual selector (including matchExpressions). Prefer one non-terminating
   Running Pod from the current ReplicaSet; if the operator names a Pod, use it.
   List only identity, controller owner references, phase/start/deletion times for
   selection. If none is Running, report that gap; do not call a pending/terminated
   Pod a running sample. Mixed revisions may warrant one sample per relevant
   ReplicaSet, separately labelled. One Pod is not evidence for every replica.
2. Follow the selected Pod's controller owner to the named ReplicaSet, then verify
   that ReplicaSet's controller owner against the Deployment. Compare names,
   UIDs, API versions and namespace; selectors or matching names alone are not
   proof. Do not silently substitute a different Pod after deletion/owner mismatch.
3. Pipe the three **named API objects** directly into the bundled Python 3 helper:

```bash
set -o pipefail
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get "deployment/$deployment" "replicaset/$replica_set" "pod/$pod" -o json | \
  python3 "$skill_dir/scripts/pod_config_compare.py"
```

For offline evidence, check the input shape before choosing the helper: it expects
a Kubernetes `List` containing exactly one Deployment, ReplicaSet and Pod, each
with API version and metadata name, namespace, UID and resourceVersion. An incident
report envelope is not that List. If the supplied objects lack required metadata,
do not invent it, repeatedly retry the helper, or bypass its validation through
internal functions. Compare only the supplied reference fields directly and state
the missing coverage. Check available controller names, UIDs, kinds/API versions
and namespace; without matching owner identities, do not claim verified ownership.

Never display or persist the raw objects: templates/Pods may hold literal secrets.
The helper performs no API calls, validates the controller owner chain, and emits
only projected reference differences. It compares containers, init containers
(including restartPolicy=Always sidecars), ephemeral containers, ordered env and
envFrom references/prefixes, mounts/subPath, configuration volumes, service
account and imagePullSecret names. It includes projected Secret/ConfigMap,
service-account-token and downward-API references, plus CSI driver,
nodePublishSecretRef and secretProviderClass. Unsupported volume/source kinds are
marked detailsNotCompared and listed in coverageGaps even when their markers
match. Always report material coverage gaps alongside zero-difference results.
Token contents, arbitrary CSI attributes, literal env
values, arguments, annotations, image/resources and process state are excluded.

Read the two results separately: deploymentToReplicaSet describes differences
from the **current** desired template to this Pod's parent template;
replicaSetToPod describes differences between that parent and the actual Pod.
Use returned revision/identity/timestamps to contextualize an older rollout.
Neither diff proves which webhook/injector caused a change; defaults, admission,
controller behavior and later Pod updates can contribute. Describe new containers
as observed additions; attribute Istio or another injector only with supporting
evidence. Exact ConfigMap/Secret dependencies discovered here may be inspected
with the existing key/supplier workflow when relevant, without retrieving values.

Output defaults to 50 leaf changes **per comparison** and 50 coverage-gap paths
per object, with exact count and
remaining. For omitted differences, repeat with --offset and --limit (maximum
200); record the returned resourceVersions and do not combine pages as one
snapshot if objects changed. No differences means only that the projected wiring
matches; it does not prove literal values, mounted content or the process's
configuration match. No exec, debug container or mutation is part of this check.

## External Secrets Operator, when present

Discover served `external-secrets.io` resources rather than hardcoding `v1` or
`v1beta1`. Inspect the named ExternalSecret's conditions, refresh time,
refresh policy/interval when supported, target name/creation policy, referenced
store kind/name, and remote key/version metadata. Avoid its template values and
raw provider payloads. Follow namespaced SecretStore versus cluster-scoped
ClusterSecretStore correctly; do not add a namespace flag to cluster-scoped reads.

Inspect store conditions and the actual provider project/authentication reference.
Do not assume Workload Identity: a store may reference a Kubernetes credentials
Secret. Read the reference, not its contents. A provider project differing from
the workload project needs an explicit profile/request mapping before cloud reads.

For a known Google Secret Manager project/secret/version, state can be inspected
without payload access, for example:

```bash
gcloud secrets versions describe "$version" \
  --secret "$remote_secret" --project "$secret_project" \
  --format='json(name,state,createTime,destroyTime)'
```

Readiness and refresh status plus source-version state establish synchronization
evidence; they do not expose or prove the exact value used by a running process.
Failed synchronization can leave an older Kubernetes Secret in place, depending
on the policies. Do not infer a missing Secret or recommend broad IAM changes
solely from an application permission error. Trace the sync error, source version,
target reference, and container start/refresh timeline before proposing a fix.

Keep the source of any proposed correction clear: application-owned values,
pipeline-owned shared ExternalSecret, store/auth configuration, or the external
secret's version lifecycle may have different owners. Return the smallest
evidence-supported correction and its validation steps; do not rotate, force-sync,
or restart as part of inspection.
