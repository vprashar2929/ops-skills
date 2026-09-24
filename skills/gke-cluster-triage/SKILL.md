---
name: gke-cluster-triage
description: Investigate GKE node health, node-pool capacity, autoscaler blocks and persistent-volume failures with an explicit profile. Use for shared cluster infrastructure symptoms or a scoped cluster health check; does not resize, upgrade, drain or repair resources.
license: Apache-2.0
---

# GKE cluster triage

Read [operations](references/operations.md) first. Requires gcloud and kubectl
with read access and verified GKE context. Metrics/log access is conditional;
their absence must not prevent reporting observed node conditions.

Resolve profile, environment, cluster and issue/window. For a named node, pool or
PVC start there. A cluster health request permits a bounded node/pool overview,
not an inventory of all workloads and Secrets. For storage include the namespace,
PVC and affected Pod. Observe default last 30m unless a window was supplied.

## Select the relevant investigation

- **NotReady/Unknown:** inspect node conditions, transition times, events, leases
  and cloud maintenance/repair/upgrade operations. Determine whether evidence fits
  an ongoing lifecycle operation before diagnosing a persistent fault. Use the
  [node guide](references/google-node-notready/guide.md) for signatures.
- **Pressure/capacity:** compare node allocatable with scheduling requests,
  taints/tolerations, affinity/topology and recent evictions. Current `kubectl top`
  measures usage, not schedulable headroom or historical peaks. Missing metrics
  is a coverage gap. Establish whether failures are local to one pool/zone.
- **Autoscaling:** inspect configured pool bounds, events and autoscaler visibility
  logs for the actual unschedulable workload. Distinguish max-size, quota/stockout,
  IP exhaustion and scheduling incompatibility. For scale-down distinguish PDB,
  local storage, unmovable Pods and consolidation decisions. Use the
  [autoscaler guide](references/google-autoscaler/guide.md), especially its
  [debug reference](references/google-autoscaler/references/ca-debug.md).
- **Storage:** follow Pod → PVC → PV → StorageClass/CSI driver and applicable
  VolumeAttachment events. Check zone/topology, access mode, binding/expansion and
  attach/mount errors. WaitForFirstConsumer Pending is not by itself a failure.
  Use the [storage guide](references/google-storage/guide.md) for relevant branches.

Useful scoped reads after identity verification:

```bash
gcloud container node-pools list --cluster "$cluster" --location "$location" \
  --project "$project" --format='table(name,status,config.machineType,autoscaling.enabled,autoscaling.minNodeCount,autoscaling.maxNodeCount)'
kubectl --context "$context" --request-timeout=20s get nodes \
  -o 'jsonpath={range .items[*]}{.metadata.name}{"\n"}{range .status.conditions[*]}{.type}{"="}{.status}{" reason="}{.reason}{" changed="}{.lastTransitionTime}{"\n"}{end}{"\n"}{end}'
```

Keep each condition's type/status/reason associated. True is not universally a
fault: Ready=True and KubeletConfigChanged=True have different meanings.

For a narrow incident use the named node/pool rather than listing every Pod.
Inspect node-critical DaemonSets only on implicated nodes; record the sample and
missing permissions. Verify pool mode and regional/per-zone bounds before
calculating capacity. Do not assume Standard settings apply to Autopilot.

## Adapt upstream guidance

The local operational contract controls execution. Do not follow upstream active
context/project discovery, get-credentials, SSH, restart, drain, delete, resize,
upgrade, PVC edit or buffer-deployment instructions. Upstream helper scripts are
not pre-approved collectors; do not execute their imperative setup or inventory
scripts as a prerequisite, including in an offline case. Use scoped native reads
when live evidence is needed and authorized. Do not infer a cloud quota
failure from Pod Pending alone, or cloud disk health from successful PVC binding.

Return the affected scope, supported failure domain, event/metric chronology,
capacity/placement constraints and evidence gaps. Separate a recommended change
from its execution and include the owning source if established.

Example: "Use this profile, test Apps. Explain why the named node pool is
not scaling for the supplied Pending Pod; read-only, last 60 minutes."

## License

Copyright 2026 Vibhu Prashar. Original content in this skill is licensed under
[Apache-2.0](LICENSE). Bundled third-party references retain their own licenses
and copyright notices in their respective directories.
