# Target and profile contract

The profile is plain YAML read by the agent, not a new executable configuration
system. Require `profile_version: 1`, `client`, `provider` (`gke` or `kubernetes`),
and `environments`. Each environment maps cluster roles to their names and local
kubectl contexts. GKE additionally needs the exact project and location. Generic
Kubernetes needs an operator-maintained `expected_api_server` per cluster.

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
references:
  - conventions.md
```

Environment names are exact keys: do not silently translate `stage`, `nprod`,
`nprd`, or `prod`. Do not infer an environment from a Git branch. The request
chooses the namespace and workload; profiles should not default every workload
to one namespace. Unknown profile versions require clarification, not guessing.
Missing optional conventions do not prevent ordinary Kubernetes inspection.

## Identity verification

Use local kubeconfig metadata first. Set shell variables only from the resolved
profile/request, quote them, and never evaluate profile text as shell code.

```bash
kubectl --context "$context" config view --minify \
  -o jsonpath='{.contexts[0].context.cluster}{"\n"}{.clusters[0].cluster.server}{"\n"}'
```

Do not use `--raw` or print user credentials. For GKE, compare that server host
with the intended cluster's endpoints returned by:

```bash
gcloud container clusters describe "$cluster" \
  --project "$project" --location "$location" \
  --format='json(name,location,endpoint,privateClusterConfig.privateEndpoint,privateClusterConfig.publicEndpoint,controlPlaneEndpointsConfig.dnsEndpointConfig.endpoint,controlPlaneEndpointsConfig.ipEndpointsConfig.privateEndpoint,controlPlaneEndpointsConfig.ipEndpointsConfig.publicEndpoint)'
```

Accept a matching IP or DNS endpoint after normalizing an optional `https://`
prefix and default port. The expected project, name, and location must match;
a matching context name alone proves nothing. For generic Kubernetes compare
the server URL to `expected_api_server`; it must come from maintained client
context, not be copied from the active context during this investigation.

If the target uses an approved proxy/Connect Gateway endpoint, ask for its
documented mapping rather than accepting an unexplained mismatch. If cloud
access fails or the endpoint differs, stop live workload reads and explain the
identity/access gap. Supplied offline artifacts can still be analyzed, explicitly
as historical/offline evidence. Never fall back to another cluster or project.

The operator may supply a different local context alias: accept it only after
the same endpoint verification. Credential setup is a separate task; neither
`get-credentials` nor `config use-context` is part of this investigation.

Use `--request-timeout=20s` on Kubernetes API reads. For logs use finite
`--pod-running-timeout=10s`, a finite request timeout, and no follow mode.
Use the execution tool's timeout for cloud calls. Do not replace a failed read
with a wider all-project/all-namespace scan.

## Preserve command failures

Shell pipelines can return the filter's success status even when collection
fails. Set pipefail in the same shell invocation as the pipeline; setting it in
an earlier tool call does not carry over. For example, after resolving the target:

```bash
set -o pipefail
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get "$workload" -o json |
  jq '{name: .metadata.name, readyReplicas: .status.readyReplicas}'
```

Inspect that command's exit status and stderr before interpreting the result.
Do not append a successful command that hides the pipeline's status, suppress
errors with `|| true`, or merge stderr into JSON input. A shell without pipefail
needs separate collection/processing with an explicit collection-status check.
Authentication failures, timeouts and NotFound must remain failed reads even if
the filter accepts empty input. An empty successful list is a different result;
state its actual query scope before drawing conclusions.
