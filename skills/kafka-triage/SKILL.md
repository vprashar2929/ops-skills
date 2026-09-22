---
name: kafka-triage
description: Investigate Kafka cluster, consumer-lag and Kafka Connect or MirrorMaker failures using an explicit client profile. Starts with GCP managed Kafka or verified self-managed metadata and telemetry; does not consume messages, reset offsets, restart connectors or change topics.
---

# Kafka triage

Read [operations](references/operations.md) first. Requires gcloud for GCP managed
Kafka or kubectl for a verified self-managed cluster. Monitoring access and an
existing approved Kafka/Connect diagnostic client are conditional. Do not install
a client, retrieve credentials or start a tunnel to manufacture access.

Resolve client/environment, project/location and exact Kafka cluster; include
Connect cluster/connector, consumer group and topic only when implicated. Identify
managed Kafka, managed Connect or self-managed Kafka/Connect separately. A Kafka UI
Deployment is a client, not evidence that the brokers run in its Kubernetes cluster.

## Start with scoped control-plane evidence

```bash
gcloud managed-kafka clusters describe "$cluster" --location "$location" \
  --project "$project" --format='json(name,state,createTime,updateTime)'
```

Use local `gcloud managed-kafka --help` and command-group help to verify installed
Connect/connector read commands and output fields. Do not guess a REST endpoint
or substitute a Confluent Cloud CLI workflow. API unavailability is a coverage gap.
Project status/identities only; connector configurations and task errors can carry
credentials, connection strings and message contents.

## Select the relevant branch

- **Cluster/connectivity:** correlate state/operations, service metrics and client
  errors with the incident window. Distinguish bootstrap DNS/TLS/IAM/network path
  failures from broker resource pressure. Managed-service READY is not proof of
  client authentication or successful produce/fetch.
- **Consumer lag:** establish group/topic/partition, committed offset versus
  log-end offset definitions, units and timestamps. Compare lag with throughput.
  For GCP, verify descriptor semantics: `managedkafka.googleapis.com/consumer_lag`
  describes follower-replica lag, while `managedkafka.googleapis.com/offset_lag`
  measures messages not yet committed by a consumer group. Do not substitute one
  for the other based on its name.
  Correlate processing errors, membership and rebalances over time. No committed offset or
  missing series is unknown, not zero lag. A quiet partition can have old sample
  timestamps; message-count lag alone does not establish time-to-recover.
- **Connect:** inspect named connector AND task states/errors. RUNNING at the
  connector level does not prove every task works or records flow. Separate
  converter/schema/authentication, source/sink connectivity, quotas and record
  errors using bounded redacted evidence. No config or raw error payload dump.
  If the managed Connector API exposes only connector state, use existing task
  telemetry or supplied sanitized diagnostics. Missing per-task API fields are
  a coverage gap, not a reason to guess a task-status CLI or retrieve configs.
- **MirrorMaker:** identify source/destination clusters and actual connector/task
  type. Verify any second project/client mapping separately. Check replication,
  checkpoints/offset-sync evidence separately; topic existence does not establish
  current replication or failover readiness.
- **Self-managed:** inspect actual owner, Pod/node/storage events and exposed
  operator status after Kubernetes identity verification. Discover the installed
  CRD/operator; do not assume Strimzi, ZooKeeper or KRaft from generic examples.

For data-plane evidence, use only an already approved scoped diagnostic client
and describe/status operations. Consumer-group describe requires explicit group
scope; do not subscribe a consumer or join a group to test it. Prefer existing
telemetry when direct data-plane access is absent. Discover metric descriptors
and monitored resource labels instead of inventing lag/throughput metric names.
Default to a 30m window and 200 redacted log entries, then expand only on evidence.

## Boundaries and result

No topic/config/ACL changes, partition increases, message reads/writes, group
offset resets, connector pause/resume/restart/delete, or failover. Do not apply a
generic "add consumers" fix without considering partition count and processing
constraints. Proposed actions must name the owning service and trade-off.

Return product/topology, affected group/partitions/tasks, event/metric chronology,
supported failure domain, missing evidence and next diagnostic step. Scope health
claims to observed control-plane/task/traffic evidence separately.

Example: "Use this profile to explain rising lag for this group/topic and a failed
named Connect task in dev. Inspect status and telemetry without reading records."

Sources, checked 2026-09-21:
- [GCP Kafka cluster troubleshooting](https://docs.cloud.google.com/managed-service-for-apache-kafka/docs/troubleshooting/troubleshoot-clusters)
- [Connect monitoring](https://docs.cloud.google.com/managed-service-for-apache-kafka/docs/connect-cluster/monitor-connect-cluster)
- [Kafka client monitoring](https://docs.cloud.google.com/managed-service-for-apache-kafka/docs/monitor-clients)
