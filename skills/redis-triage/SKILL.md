---
name: redis-triage
description: Investigate Redis connection failures, memory pressure, evictions and replication symptoms using an explicit client profile. Distinguishes Memorystore Redis instances, Memorystore Redis Cluster and self-managed Redis; performs metadata and bounded diagnostic reads without retrieving keys or changing Redis.
license: Apache-2.0
---

# Redis triage

Read [operations](references/operations.md) before collection. Requires gcloud
for Memorystore metadata or verified kubectl for self-managed workloads. Direct
Redis diagnostics additionally require an existing approved connection/client;
do not fetch credentials, start a tunnel or run exec to create one.

Resolve the exact client/environment/project/region/resource and incident window.
Establish product type from supplied context or scoped metadata; a Terraform
module name or redis-looking Pod is not proof of a Memorystore product. If type
is unknown, list names/types in the confirmed project/region, suggest actual
candidates and confirm the target before reading the selected resource.

## Start with product-specific evidence

For Memorystore for Redis instances:

```bash
gcloud redis instances describe "$instance" --region "$region" --project "$project" \
  --format='json(name,state,tier,redisVersion,memorySizeGb,replicaCount,readReplicasMode,transitEncryptionMode,authEnabled)'
```

For Memorystore for Redis Cluster:

```bash
gcloud redis clusters describe "$cluster" --region "$region" --project "$project" \
  --format='json(name,state,shardCount,replicaCount,authorizationMode,transitEncryptionMode)'
```

Check installed gcloud help if a command/field is unavailable; do not switch the
product to make a command work. Self-managed Kubernetes inspection uses actual
owners, Pod readiness/restarts, PVC/events and container identity; it does not
execute redis-cli inside a Pod. Never retrieve an auth string or key values.

## Investigate the reported symptom

1. Correlate control-plane state and available metric trends over the incident
   window. Discover actual metric descriptors/resource labels; Redis Cluster and
   Redis instance schemas differ. State any shard/replica sampling.
2. For connections, establish server rejection versus client timeout, pool
   exhaustion, TLS/auth mismatch or network failure from observed errors. Use
   [connection guidance](references/redis-connections/guide.md) conditionally;
   client/library version and application concurrency matter.
3. For memory/eviction, distinguish used memory, configured limit, RSS/fragmentation,
   eviction counter changes and application cache behaviour. An eviction is not
   necessarily a fault; compare with the configured policy and workload intent.
4. For replication/CROSSSLOT, establish topology, affected shard/client and exact
   error. Use [cluster guidance](references/redis-clustering/guide.md), but do not
   assume all client pipelines require one slot: client-aware pipelines and
   atomic multi-key operations have different constraints. Replica lag/read
   consistency needs evidence; don't redirect reads as an automatic fix.
5. With an explicitly supplied approved data-plane connection, use scoped INFO
   sections or other confirmed supported low-impact diagnostic reads only.
   [Observability guidance](references/redis-observability/guide.md) is a menu,
   not permission to execute every example. Prefer existing monitoring when
   direct access is absent. Report the boundary between those evidence sources.

## Adapt upstream examples

No SLOWLOG RESET, CONFIG SET, writes, eviction tests, failover, resharding, flush,
MONITOR, full key scans, key-value reads or FT.PROFILE workload execution. Do not
emit raw SLOWLOG command arguments or CLIENT LIST payloads. Use a pre-existing
sanitizing path for slowlog duration/count/command-name metadata, otherwise skip
that output and state the gap. Upstream example thresholds are not client SLOs.
Managed products may restrict commands; unsupported is not unhealthy.

Return verified product/topology, time-series evidence and counter intervals,
supported cause, unavailable signals and the smallest next step. A READY managed
resource or healthy Kubernetes Pod does not prove Redis request success.

Example: "Using this profile, inspect memory and rejected connections for this
named dev Memorystore instance over the last hour; do not read cache contents."

Sources:
- [Memorystore supported configurations](https://cloud.google.com/memorystore/docs/redis/supported-redis-configurations)
- [Redis Cluster monitoring](https://cloud.google.com/memorystore/docs/cluster/monitor-instances)

## License

Copyright 2026 Vibhu Prashar. Original content in this skill is licensed under
[Apache-2.0](LICENSE). Bundled third-party references retain their own licenses
and copyright notices in their respective directories.
