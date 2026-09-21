# Portable operational skills

Nine portable skills for scoped operational inspection and investigation. Client
profiles live separately. Native tools and existing monitoring APIs provide the
evidence; there is no observe dependency or collection framework. New skills are
pilots with focused offline and live DEV validation, not a claim of complete incident or
cross-agent coverage.

| Skill | Use it for | Inputs beyond the explicit client/environment |
| --- | --- | --- |
| workload-triage | Namespace/resource discovery, workload status/logs/config wiring | Cluster; namespace/workload for inspection |
| service-connectivity-triage | Service endpoints, network policies and Istio path failures | Cluster, source and destination, protocol/port/window |
| gke-cluster-triage | Nodes, capacity/autoscaler and volume failures | Cluster and relevant node/pool or PVC/Pod |
| observability-triage | Missing metrics/logs, scrape and alert evidence | Signal/resource/window and verified backend/scope |
| delivery-triage | Pipeline, Helm and Argo revision/ownership failures | Run/artifact, release or Application; actual management/destination mapping |
| cloud-sql-triage | Cloud SQL state, operations, connections and capacity evidence | Exact project/instance/window; no database session required |
| redis-triage | Memorystore/self-managed Redis connection/memory/replication evidence | Product type, resource/project/region or verified Kubernetes target |
| cloud-cost-review | Billing totals, change analysis and supported GKE allocation | Export table, projects, period/basis/location and execution byte ceiling for live queries |
| kafka-triage | Managed/self-managed Kafka, consumer lag and Connect/MirrorMaker | Cluster and affected topic/group/connector/task/window |

Each skill diagnoses and proposes next steps without changing the environment.
Profiles, permissions, network access and tool availability are still required
for live evidence. Supplied offline artifacts can be analyzed without live access.
Missing service identifiers, billing exports and monitoring/Argo endpoints are
requested when needed; they are not guessed or embedded in the public packages.

## Assemble and try it

Prerequisites: Git, Python 3.9+ for packaging; kubectl plus appropriate identity and
network access for use. GKE identity verification needs gcloud. Helm and jq are
optional, used only for relevant inspections. Runtime profile YAML is read by the
agent; no Python/YAML runtime package is required.
The optional compact configuration helper uses Python 3's standard library to
summarize named Secret/ConfigMap/ExternalSecret reads; it performs no API calls
and emits key/reference metadata rather than values.

```bash
git submodule update --init --recursive
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py dist/workload-triage
```

Run from this repository. The destination must not exist and its leaf must match
the skill name; for another build use e.g. dist/trial-2/workload-triage. Select a
different skill with `--skill`, or build the collection into a new versioned folder:

```bash
for skill in workload-triage service-connectivity-triage gke-cluster-triage \
  observability-triage delivery-triage cloud-sql-triage redis-triage \
  cloud-cost-review kafka-triage; do
  python3 scripts/package_skill.py --skill "$skill" "dist/my-trial/$skill" || exit 1
done
```

The packager copies each skill and its explicit selected upstream directories/files,
required resources, license and SHA. It rejects dirty/unrecorded upstream
revisions, unresolved local Markdown links and symlinks. It does not fetch anything
at runtime. Do not install the entire upstream skill catalog.
Included upstream entrypoints are packaged as `guide.md`, with unchanged contents
and a filename mapping in `UPSTREAM.json`. Reference-only selections instead list
their included files in that provenance record. Packaging rejects any additional `SKILL.md`
entrypoint so the reference is not independently discoverable as a skill.

To test without changing agent settings, paste a request like this into an agent
that can read local files and run the needed tools, replacing paths and workload:

```text
Read /absolute/path/ops-skills/dist/workload-triage/SKILL.md and use that skill.
Client profile: /absolute/path/client-contexts/ncnp/profile.yaml
Environment: test
Cluster: apps
Namespace: <actual namespace>
Workload: deployment/<actual name>

Show its images, requests/limits, readiness and rollout state. Read-only.
```

For incident testing, replace the last line with the symptom and UTC incident
window. Do not change a shared environment to manufacture an incident. The first
live case should be one named dev/test workload chosen by the operator.

Once installed, namespace discovery can be invoked without a namespace or workload:

```text
$workload-triage
Use the client profile at /absolute/path/client-contexts/ncnp/profile.yaml.
List namespaces in the dev Apps cluster, with their status.
```

This verifies the cluster and lists namespace names/phases only. It does not scan
workloads inside them. In a conversation where the profile was already supplied,
reuse that explicit profile selection.

To compare a Deployment's configured references with one running Pod:

```text
$workload-triage
Use the client profile at /absolute/path/client-contexts/ncnp/profile.yaml.
In dev Apps, namespace <namespace>, compare Deployment <name>'s configuration
with one running Pod. Show additional containers, mounts and config references.
Read-only; omit secret values.
```

The comparison verifies Deployment/ReplicaSet/Pod controller ownership by UID
and separates current-template versus parent-template differences from observed
Pod differences. It samples one Pod and compares wiring, not loaded values or a
complete Pod spec. It does not automatically attribute differences to an injector.

Misspelled namespaces, resource kinds (including custom resources), object names,
containers and requested keys/fields use scoped discovery to suggest real
candidates. The skill confirms a changed target before inspecting it; valid
unambiguous aliases work normally. It does not substitute names inside deployed
configuration or interpret access failures as typos. See
`skills/workload-triage/references/identifier-recovery.md` for the discovery rules.

Install the complete assembled `workload-triage` directory using the target
agent's supported skill installation mechanism when ready. Copying only SKILL.md
loses references. Direct file invocation is the pilot path; automatic discovery
and Claude/Codex behavioral parity still need testing. Instruction portability
does not supply cloud permissions, network access, or tool enforcement.

Install each additional assembled directory in the same way. For example, once
installed, an end user can invoke:

```text
$service-connectivity-triage
Use /absolute/path/client-contexts/example/profile.yaml, staging Apps.
Investigate 503s from deployment/frontend in shop to service/orders:8080 in shop
over the last 30 minutes. Read-only.
```

The same explicit profile selection can be reused within the conversation.
Each package has its own operational reference so it works independently of the
other installed skills. When changing common targeting/evidence rules, update
the affected copies together; avoid introducing a runtime profile registry.

## Client profiles

See `skills/workload-triage/references/targeting.md` for the small profile contract.
Maintain private mappings and conventions outside this repository and supply the
profile explicitly. Keep credentials and secret values out. No default client,
namespace, automatic environment detection, inheritance, or profile registry.

The separate local NCNP profile currently covers dev/test/nprd Apps and BFF;
production is deliberately absent from this initial pilot. Repository conventions
are hints verified against the actual workload/run before use. A different local
context alias can be supplied if it verifies against the same cluster endpoint.
New skills document their contract in `references/operations.md`. Managed GCP
skills accept provider gcp as well as a GKE client's project mapping; they do not
require a Kubernetes target when only cloud service evidence is needed. Backend,
billing and management-project mappings may be supplied explicitly in the request
or maintained private conventions. A fully qualified resource ID must agree with
that scope before a request is sent. No existing NCNP profile was broadened to
production or populated with guessed service/backend identifiers.

## Upstream maintenance

`upstream/google-skills` is an unmodified Git submodule of
[google/skills](https://github.com/google/skills), Apache-2.0.
`upstream/redis-skills` is an unmodified Git submodule of
[redis/agent-skills](https://github.com/redis/agent-skills), MIT.
`upstream/wshobson-agents` is an unmodified Git submodule of
[wshobson/agents](https://github.com/wshobson/agents), MIT; only its Istio traffic
and mesh-observability guides are packaged into the two existing triage skills.
`upstream/planetscale-database-skills` is an unmodified Git submodule of
[planetscale/database-skills](https://github.com/planetscale/database-skills), MIT;
five MySQL diagnostic references support only the MySQL branch of cloud-sql-triage.
Its provider-oriented entrypoint, schema-design material and other engines are
excluded.
Each commit is recorded by its parent gitlink; `branch = main` selects the update
source, not a floating runtime version. `scripts/package_skill.py` contains the
small explicit source/path selection for each skill. Google supports GKE,
monitoring and cost guidance; Redis supports three Redis diagnostic references.
Delivery/Kafka currently use locally authored procedures and linked primary docs.
Selected content is defined in the packager; adaptations live in each skill's
entrypoint and references. No extra skill entrypoints or community plugin runtime
are installed.

Operational adaptations live in our entrypoints/references; upstream bytes are
preserved. Their setup, active-context, mutation or automatic MCP configuration
instructions do not override our scope. The source review is not a promise that
upstream examples are universally correct or maintained for every model.

`renovate.json` enables weekly, non-automerge submodule PRs. The
[Renovate submodule manager](https://docs.renovatebot.com/modules/manager/git-submodules/)
is currently beta and opt-in. A hosted repository and configured Renovate service
are still required; this local config does not activate a bot.

For an update: review the selected skill/resources and license diff, reconcile
the adaptation notes, package the proposed gitlink, run packaging and relevant
behavior cases, then merge and distribute a new complete bundle. Update the
review baseline in the adaptation after actual review. A passing packaging test
does not approve changed instructions. To revert, restore the prior parent
revision and initialize its recorded submodule, then rebuild/reinstall its bundle.

## Validation status

Future changes follow the standing [skill maintenance requirements](AGENTS.md),
including official Agent Skills validation of source, assembled and updated
installed bundles. These checks are currently performed manually; no connected
CI release gate is claimed.

As of 2026-09-21, all 27 automated tests passed without skips. They cover packaging,
upstream preservation, reference resolution, command-failure propagation and
value-free configuration comparisons. Command tests require bash and jq; they
skip when those tools are unavailable. Official validation passed for all nine
source, assembled and installed skills, and installed contents matched fresh builds.

Reusable offline cases remain in [operational scenarios](tests/fixtures/operational-scenarios.md),
[mesh scenarios](tests/fixtures/community-mesh-scenarios.md) and
[MySQL scenarios](tests/fixtures/mysql-reference-scenarios.md).
[Workload behavior cases](tests/behavior-cases.md) cover further targeted checks.
Development reports, installation manifests and private live evidence are kept
outside this repository.

Scoped DEV trials exercised representative workload, network, cluster, monitoring,
delivery and managed-service paths. A matched-evidence comparison found equivalent
diagnostic conclusions with and without skills, with extra reading time in the
skill arm; it did not measure independent collection or incident-resolution time.

This remains a pilot. Broader incident coverage, teammate/Claude trials and live
MySQL behavior remain unverified. Renovate configuration has not been tested with
a connected bot. Passing format and packaging checks does not establish runtime
enforcement, cross-agent parity or diagnostic effectiveness.
