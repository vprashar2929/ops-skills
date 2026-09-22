---
name: observability-triage
description: Investigate missing metrics, Prometheus scrape failures, alert behaviour and missing historical Cloud Logging data using an explicit client profile. Use to validate a monitoring signal or collection path; does not install monitoring or change alert rules.
license: Apache-2.0
---

# Observability triage

Read [operations](references/operations.md) before collection. Requires the
backend's existing read access: kubectl/gcloud for discovery as applicable and
an approved authenticated HTTP/API client for actual queries. Do not install an
MCP server, start a port-forward or print access tokens to obtain access.

Resolve the client/environment, affected resource, signal and UTC window. Obtain
the actual backend endpoint or Cloud Monitoring scoping project / Logging view
from supplied client context or verified resource configuration. A Kubernetes
namespace named prometheus or gmp-system does not establish the query backend.
Monitoring, logging and traces may use different projects and systems.

## Follow the signal

1. Establish collection and query scope: source cluster/project, labels, metrics
   scope or log bucket/view, and caller access. Backend access failure is distinct
   from an empty successful query and a stale last sample.
2. **Prometheus:** inspect the named target's scrape status, last scrape/error,
   discovered labels and applicable ServiceMonitor/PodMonitor/selector wiring.
   Identify the actual Prometheus instance and namespace-selection rules. A
   ServiceMonitor can exist without being selected. Use
   [backend queries](references/backend-queries.md) for bounded API requests.
3. **Cloud Monitoring:** discover metric descriptors and monitored resource labels
   using the [metric guide](references/google-metrics/guide.md). Only then use
   [Cloud Monitoring PromQL](references/google-promql/guide.md); its translation
   conventions must not be applied blindly to a standalone Prometheus server.
4. **Alert:** inspect the exact rule/policy, evaluation interval, pending `for`
   period, label matching, missing-data behaviour and firing/pending/inactive
   state. If notification failure is the issue, inspect relevant routing,
   inhibition/silence metadata and delivery errors. Do not create a test alert,
   silence, notification or incident. Firing does not prove notification delivery.
5. **Logs:** inspect established sink/filter/exclusion and destination/view scope
   before querying historical data. Query the named resource and window, default
   30m / 200 entries. The [Logging query guide](references/google-logging/guide.md)
   supplies syntax, not proof that the selected project retains the logs.
6. For traces, use only an explicitly available trace backend and supplied trace
   identity. Do not claim Prometheus stores traces or infer an incident from a
   missing trace whose sampling/retention is unknown.
7. For a mesh request/error/latency signal, use the mesh notes in
   [backend queries](references/backend-queries.md), then consult the
   [community mesh guide](references/community-mesh-observability/guide.md) and
   [query examples](references/community-mesh-observability/references/details.md)
   only when relevant. Their installation, dashboard, tap/watch and sampling
   examples are not diagnostic prerequisites or permission to change the mesh.

Use metric type, unit, kind and labels from discovery. Apply rates to appropriate
counters and histogram handling to the actual schema; do not aggregate across
clients/clusters accidentally. Investigate stale series and resets before
attributing a trend. Alert thresholds come from the deployed policy or user SLO,
not an upstream example's arbitrary percentage.

## Upstream boundaries and output

Do not apply upstream setup/alert/retention changes, enable APIs/exports, grant
permissions or run helper scripts without inspecting their actual behaviour.
Bundled guides may mention optional Google MCP tools; use them only if available
and scoped correctly, otherwise native APIs. No external tool is assumed installed.
Do not follow the metric guide's mandatory live calls or automatic MCP configuration
edits. Supplied offline evidence can be analyzed without either prerequisite.
The Logging guide's query-only output instruction applies to query construction,
not this investigation: return the diagnostic findings and gaps below.

Return the exact query when available, backend/resource scope, time range and sample coverage,
the first broken collection/evaluation/delivery link, and known access/retention
gaps. Distinguish "no matching data" from "zero errors" or "healthy application".

Example: "Using this profile and Prometheus endpoint, explain why ServiceMonitor
payments in test Apps has no series during the last hour. Do not change it."

## License

Copyright 2026 Vibhu Prashar. Original content in this skill is licensed under
[Apache-2.0](LICENSE). Bundled third-party references retain their own licenses
and copyright notices in their respective directories.
