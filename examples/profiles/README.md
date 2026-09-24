# Start with one explicit target

Use [gke.yaml](gke.yaml) for GKE workload inspection or [gcp.yaml](gcp.yaml) for a
managed service such as Cloud SQL. Copy the chosen template to a private directory
outside this repository and replace all example identifiers. Never put credentials
in a profile. For local Kubernetes, the [kind lab profile](../kind/profile.yaml)
provides a complete example of the generic Kubernetes contract.

Set `profile` to a non-empty identifier meaningful to you. Organize profiles per
user (for example, `alex`), cluster (`apps-eu`), environment (`staging`), or a
combination (`alex-staging-apps`). Each file supplies `profile_version: 1`,
`provider` and explicit `environments` mappings. The identifier does not select
credentials, imply ownership, or grant access.

These are mappings, not authentication or authorization. Before live GKE use,
configure kubectl authentication separately and ensure gcloud can describe the
selected cluster. The skill verifies the context endpoint against that cluster.
A context name alone does not establish identity. For a generic cluster, maintain
the expected API server independently rather than copying the active context
during diagnosis. Use exact environment keys; `stage` does not select `staging`.

After installing workload-triage, start Codex and ask a narrow question:

```text
$workload-triage
Profile: /absolute/path/to/private/profile.yaml
Environment: staging
Cluster: apps
Namespace: shop
Workload: deployment/orders-api
Show images, requests/limits, readiness and configuration reference names/keys.
Read-only; do not show values.
```

Reuse that explicit selection for follow-up questions in the same session. Supply
a different selection when switching profiles, clusters or environments. The
namespace and workload belong in the request; avoid putting a catch-all default
namespace in the profile. The agent should ask only for genuinely missing selections.

For managed Cloud SQL, use the GCP profile and supply the exact instance and time
window instead of a Kubernetes cluster/namespace:

```text
$cloud-sql-triage
Profile: /absolute/path/to/private/gcp-profile.yaml
Environment: staging
Instance: example-orders-db
Investigate connection failures during 2026-09-23 11:00–12:00 UTC.
Inspect metadata and existing telemetry only.
```

This example has not been exercised against a live Cloud SQL instance. Access to
telemetry in another project requires its explicit profile mapping. Do not invent
that mapping from the resource's project.

## What a useful answer looks like

The following illustrates a response to synthetic offline evidence for the local
lab's healthy workload. It is not a current cluster report:

> At the supplied snapshot time, `skill-lab/deployment/orders-api` has one ready
> and available replica. Container `web` uses the recorded busybox image digest,
> CPU request/limit `10m/100m` and memory `16Mi/32Mi`. It references ConfigMap
> `web-settings` (`APP_MODE`) and Secret `web-credentials` (`API_TOKEN`).
> The snapshot does not establish current cluster state or Secret/key existence;
> no payload values were collected.

For a real inspection, expect the exact image/digest, observation time and source.
For an incident, expect a supported explanation, alternatives that remain open,
and the smallest useful next check. A blocked read should produce an access gap,
not an empty inventory or a health claim.

Full contracts: [Kubernetes targeting](../../skills/workload-triage/references/targeting.md)
and [managed-service operations](../../shared/operations.md).
