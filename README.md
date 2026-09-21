# ops-skills

Portable [Agent Skills](https://agentskills.io/) for Kubernetes and Google Cloud
operations. Inspect resources, investigate symptoms and return evidence with next
steps. Use explicit client profiles and existing CLI/API access; profiles and
credentials stay outside the repository. The skills do not perform remediation.

## Skills

| Skill | Purpose |
| --- | --- |
| [workload-triage](skills/workload-triage/SKILL.md) | Namespaces, workload status, logs and configuration references |
| [service-connectivity-triage](skills/service-connectivity-triage/SKILL.md) | Service endpoints, network policies and Istio routing |
| [gke-cluster-triage](skills/gke-cluster-triage/SKILL.md) | Nodes, scheduling capacity, autoscaling and storage |
| [observability-triage](skills/observability-triage/SKILL.md) | Missing metrics/logs, scrape failures and alerts |
| [delivery-triage](skills/delivery-triage/SKILL.md) | Pipeline failures, Helm releases and Argo CD reconciliation |
| [cloud-sql-triage](skills/cloud-sql-triage/SKILL.md) | Managed database availability, connections and resource pressure |
| [redis-triage](skills/redis-triage/SKILL.md) | Redis connections, memory, evictions and replication |
| [kafka-triage](skills/kafka-triage/SKILL.md) | Brokers, consumer lag and Connect/MirrorMaker failures |
| [cloud-cost-review](skills/cloud-cost-review/SKILL.md) | Billing export totals, changes and supported cost allocation |

## Quick start

Building requires Git and Python 3.9+. Live inspection also needs the relevant
tools, authentication, permissions and network access. Each skill lists its
prerequisites; Kubernetes on GKE requires kubectl and gcloud. Supplied offline
artifacts can be analyzed without cloud access.

```bash
git clone --recurse-submodules https://github.com/vprashar2929/ops-skills.git
cd ops-skills
```

For an existing clone, initialize dependencies with `git submodule update --init --recursive`.

Build directly into your agent's personal skill directory. Run the command for
your agent (macOS/Linux):

```bash
# Codex CLI / IDE
python3 scripts/package_skill.py --skill workload-triage "$HOME/.agents/skills/workload-triage"

# Claude Code
python3 scripts/package_skill.py --skill workload-triage "$HOME/.claude/skills/workload-triage"
```

This installs the complete skill, including its pinned upstream references.
Choose another skill by changing both `--skill` and the final directory name.
Existing installations are never overwritten. For a reviewable build or update,
use a new destination such as `dist/build-2/workload-triage`, then replace the
installed folder after reviewing it and keeping a backup.

Create a private YAML profile using the [profile example and contract](skills/workload-triage/references/targeting.md).
Replace the example project, location, cluster and context with your own mappings.
For managed GCP services, see the [cloud targeting contract](skills/cloud-sql-triage/references/operations.md).
Open your agent, select the skill and supply your task:

| Agent | Invoke the installed skill |
| --- | --- |
| [Codex CLI / IDE](https://learn.chatgpt.com/docs/build-skills) | Type `$workload-triage`, or select it using `/skills` |
| [Claude Code](https://code.claude.com/docs/en/skills) | Type `/workload-triage` |

For example, in Codex (replace the first line with `/workload-triage` in Claude Code):

```text
$workload-triage
Profile: /path/to/private/profile.yaml
Environment: staging
Cluster: apps
Namespace: shop
Workload: deployment/orders-api
Show images, requests/limits, readiness and rollout state. Read-only.
```

If the skill does not appear, restart the agent. Other Agent Skills-compatible
agents have their own discovery paths and invocation syntax; `/skills` is not a
universal command. Install the complete assembled directory, not the source folder.
Skill instructions do not enforce permissions or redact tool output; use
appropriately scoped access. Billing queries may incur charges.

## Upstream references

Packages include only selected content, preserving its license and pinned commit
in `UPSTREAM.json`. Upstream setup or mutation examples do not override the local
skill's operational boundaries.

| Repository | Included guidance | License |
| --- | --- | --- |
| [google/skills](https://github.com/google/skills) | GKE, Monitoring, Logging and cost | Apache-2.0 |
| [redis/agent-skills](https://github.com/redis/agent-skills) | Connections, observability and clustering | MIT |
| [wshobson/agents](https://github.com/wshobson/agents) | Istio traffic and mesh observability | MIT |
| [planetscale/database-skills](https://github.com/planetscale/database-skills) | Selected MySQL diagnostics | MIT |

Selections live in [the packager](scripts/package_skill.py). Delivery and Kafka
use locally authored procedures. Renovate is configured for weekly submodule
updates without automerge; running the bot requires separate repository setup.

## Contributing

Use synthetic examples and keep client data, credentials and development reports
out of changes. Include the affected skill, agent/tool versions, a sanitized
reproduction and expected versus observed behavior in issues or pull requests.
Follow [AGENTS.md](AGENTS.md) for format validation and upstream update checks.

```bash
python3 -m unittest discover -s tests -v
```

The suite covers packaging and workload helpers; command tests also require bash
and jq. [Behavior cases](tests/behavior-cases.md) and [fixtures](tests/fixtures/)
are separate agent-driven scenarios, not automatically executed unit tests.

The project is experimental. Representative live and offline cases have been
exercised; broad incident coverage and cross-agent parity are not established.
Format validation is not proof of diagnostic accuracy or time savings.

## License

A license for repository-authored code and documentation has not yet been chosen.
Third-party content retains the upstream licenses listed above.
