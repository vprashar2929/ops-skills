# Resolve identifiers from actual available names

Help the operator correct misspellings without silently changing the target.
This applies to namespaces, built-in and custom resource types, resource object
names, containers, referenced key names and requested Kubernetes schema fields.
Use client profile keys for environment/cluster-role suggestions. It does not
turn a missing dependency or a value in a deployed specification into a typo.

## Establish what failed

- Try exact supplied identifiers and supported aliases first. Kubernetes kind,
  singular/plural resource names and short names may identify the same resource;
  resolving a known unambiguous alias is not a target change requiring approval.
- Recover on an explicit namespace/object NotFound, unsupported resource type,
  missing container/key, or unavailable requested schema field. Read the error:
  a missing Deployment does not establish a missing namespace. A failed API path
  may mean an unserved version, not a missing object.
- Authentication failures, Forbidden, DNS failures and timeouts are access gaps,
  not spelling evidence. An empty selector result is not proof of a typo either.
  Do not retry with guessed identities, wider permissions or different clusters.
- Verify the cluster identity before Kubernetes discovery. If a client/environment/
  cluster-role identifier is unknown, suggest only keys in the explicitly supplied
  profile and obtain a selection before contacting the proposed cluster. Do not
  search other client profiles or guess project IDs, endpoints or profile paths.

## Discover within the smallest relevant scope

Resolve API type and namespace independently when both are wrong. You may gather
API discovery information and namespace names on the verified cluster together,
then ask one question identifying both proposed corrections. Do not list objects
inside a proposed namespace or of a proposed different type until confirmed.

| Identifier | Source of candidates | Boundary |
| --- | --- | --- |
| Namespace | Namespace names on the verified cluster | No workload reads in candidate namespaces |
| Resource kind, plural, short name or API group | API discovery on the verified cluster | Include served built-in and custom resources; retain group/version and scope |
| Namespaced resource name | Names of that resolved resource type in the confirmed namespace | No all-namespace scan or other-kind search |
| Cluster-scoped resource name, including a CRD definition | Names of that resolved type on the verified cluster | No namespace flag; no searching other clusters |
| Container/init-container name | Container names from the confirmed Pod/workload | Do not fetch logs for a suggested container until confirmed |
| ConfigMap/Secret key | Key names in the confirmed referenced object | No values or decoded data; missing deployed references remain findings |
| Kubernetes/CR schema field | Published schema for the resolved resource and served API version | No invented field names or schema assumptions when discovery is unavailable |

Discover supported types, including CRDs and aggregated APIs, using:

```bash
kubectl --context "$context" --request-timeout=20s \
  api-resources --cached=false -o wide
```

Read NAME, SHORTNAMES, APIVERSION, NAMESPACED and KIND. Use the fully qualified
resource name (`plural.group`) when different groups expose the same kind or
alias. Ask which group the operator intends if ambiguous. An explicitly requested
unserved API version is a compatibility gap: show served versions and ask before
substituting one. Do not install a CRD or assume an operator is installed based on
documentation. A CustomResourceDefinition is a cluster-scoped definition; its
custom-resource instances can be namespaced or cluster-scoped. Follow discovery.
API discovery does not guarantee permission to list instances. If discovery fails
partially, qualify the candidate set; absence is not conclusive.

For namespace candidates use the namespace listing in targeting.md. For object
names, set `resource` to the resolved canonical type and use names-only output:

```bash
kubectl --context "$context" --namespace "$namespace" --request-timeout=20s \
  get "$resource" -o name
```

For a discovered cluster-scoped type omit `--namespace`:

```bash
kubectl --context "$context" --request-timeout=20s get "$resource" -o name
```

Do not use custom-resource default tables to find names: additional printer
columns may expose arbitrary fields. Names-only output avoids emitting object
payloads, but listing still needs API list permission and is not a metadata-only
authorization guarantee. Preserve command failures and report truncated or
incomplete results; do not claim exhaustive matches from a partial list.

For a misspelled field, inspect the nearest valid parent path in the published
schema (rather than dumping whole custom resources), for example:

```bash
kubectl --context "$context" --request-timeout=20s \
  explain "$resource.spec" --api-version="$api_version"
```

Use the configuration reference's value-free projection for key names. Do not
fuzzy-match image tags, credential values, external hosts or arbitrary application
configuration. No dedicated matcher, inventory service or persistent alias table
is required for this workflow.

## Suggest, confirm, then inspect

Compare the input with discovered candidates, prioritizing similar spelling and
word segments. Show at most three plausible candidates with their namespace and
API group when relevant. Do not assert the closest string is the intended object.
If none is plausible, say so; for a small set offer the actual names, otherwise
ask for a distinguishing prefix. Do not cycle through guessed object reads.

Example: “Deployment `ces-disclosur` was not found in `compliance-assessment-dev`.
That namespace contains Deployment `ces-disclosure`. Should I inspect it?”

Even one plausible match needs confirmation before changing the target. If the
user's current request already explicitly selects the exact corrected target,
proceed without asking again. After confirmation, reuse that selection within
this conversation and target; do not carry it across clients or clusters. A later
NotFound may reflect deletion or replacement, not another spelling error.

If the wrong name comes from a deployed reference, report the broken reference
and any plausible candidate as evidence for a proposed correction. Never silently
substitute the candidate and report that the original reference is valid. Any
change to manifests, resources or configuration remains a separate change task.
