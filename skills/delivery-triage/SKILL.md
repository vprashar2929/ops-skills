---
name: delivery-triage
description: Diagnose a failed pipeline, Helm release or Argo CD reconciliation by tracing the actual run, chart, values and deployed revision with an explicit profile. Use for delivery provenance and rollout ownership; does not sync, roll back or redeploy.
license: Apache-2.0
---

# Delivery triage

Read [operations](references/operations.md) first. Requires Git/file access for
source review; kubectl/gcloud for verified live cluster reads; Helm or Argo CLI/API
and pipeline read access only for the selected delivery path; jq for the projected
Helm examples below. A local checkout is
not evidence of the pipeline's actual revision or the deployed release.

Resolve profile/environment and either pipeline run/artifact identity, Helm
release+namespace+cluster, or Argo Application+management cluster+namespace.
Obtain the affected workload and time window when needed to connect delivery to
runtime. Do not invent an Argo management context from the destination cluster.

## Establish delivery ownership

1. Read supplied repository conventions as hints. Establish the actual consuming
   application run, source commit and tool path. A platform Argo Application does
   not prove the application workload is managed by Argo.
2. For direct Helm, inspect release status/history and recorded chart/app versions
   with explicit kube-context and namespace. Correlate timestamps with the actual
   run. Trace chart dependency/revision, values artifact and CLI overrides; current
   local values may differ. Do not dump `helm get all`, rendered Secret manifests
   or raw values. Use value-free paths/reference names and changed field names.
3. For Argo, verify management and destination mappings independently. Inspect the
   named Application's sources/revisions, sync/health and operation state, resource
   conditions, automated-sync/prune settings and relevant hooks/waves. Synced and
   Healthy answer different questions; OutOfSync alone does not prove downtime.
4. Inspect a bounded failed step's logs and existing artifacts. Jobs/migrations,
   hooks or a rollback can leave effects beyond the final release status. A
   currently healthy previous revision does not establish the attempted revision
   succeeded. Read collection errors; an artifact filename is not proof of coverage.
5. Establish who owns each proposed correction: consuming app, shared pipeline,
   chart, environment values, separately managed ExternalSecret, or Argo source.
   If actual run/chart/artifact evidence is missing, state the ambiguity rather
   than recommend editing whichever local file looks similar.

Scoped Helm examples after target verification:

```bash
set -o pipefail
helm status "$release" --kube-context "$context" --namespace "$namespace" -o json |
  jq '{name,namespace,version,status:.info.status,lastDeployed:.info.last_deployed}'
```

```bash
set -o pipefail
helm history "$release" --kube-context "$context" --namespace "$namespace" --max 10 -o json |
  jq '[.[] | {revision,updated,status,chart,app_version}]'
```

Project status fields before output: Helm status can include notes with arbitrary
content. Use native Kubernetes Application reads when an Argo CLI context cannot
be verified; no global context switch. Treat manifests/diffs as potentially
sensitive, particularly Secret and ConfigMap literal data.

## Boundaries and output

Do not run repo cleanup/must-gather scripts blindly: they can rotate artifacts,
collect secrets, change contexts or modify releases. Existing artifacts may be
reviewed with value exclusion. Do not invoke hooks, rerun pipelines, sync/refresh
Argo operations, roll back/uninstall releases or change GitOps sync policies.

Return a revision timeline, failed stage/resource and evidence, intended versus
observed deployment, correction owner and smallest next step. Separate offline
source review from live state. Propose remediation only after considering
migration/data effects; rollback is not automatically safe.

Example: "Using this profile, inspect failed run 123 and release orders in test
Apps/shop. Explain whether rollback occurred and which source owns the failure."

Sources:
- [Helm status](https://helm.sh/docs/helm/helm_status/)
- [Argo Application specification](https://argo-cd.readthedocs.io/en/stable/user-guide/application-specification/)
- [Argo resource health](https://argo-cd.readthedocs.io/en/stable/operator-manual/health/)

## License

Copyright 2026 Vibhu Prashar. Original content in this skill is licensed under
[Apache-2.0](LICENSE). Bundled third-party references retain their own licenses
and copyright notices in their respective directories.
