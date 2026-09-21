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
