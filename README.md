# ops-skills

Portable [Agent Skills](https://agentskills.io/) for Kubernetes and Google Cloud
operations. Inspect resources, investigate symptoms and return evidence with next
steps. Use explicit client profiles and existing CLI/API access; profiles and
credentials stay outside the repository. The skills do not perform remediation.

## Quick start

New to this repo? Start with the [Codex local-lab walkthrough](examples/kind/README.md).
It takes you from prerequisites to a live diagnosis and cleanup without cloud
credentials. Use the installation below when you already have a target environment.

Requires Git and Node.js 22.20+. Install directly from the default branch:

```bash
# Choose skills and agents interactively
npx skills@1.7.0 add vprashar2929/ops-skills

# Browse available skills
npx skills@1.7.0 add vprashar2929/ops-skills --list

# Install one skill for Codex and Claude Code
npx skills@1.7.0 add vprashar2929/ops-skills \
  --skill workload-triage --agent codex claude-code
```

Installation defaults to the current project; add `--global` for personal use.
Choose either agent or both, and use `--skill '*'` to select all nine skills.
The [skills CLI](https://github.com/vercel-labs/skills) supports additional agents;
our installation checks cover Codex and Claude Code. Each directory under `skills/`
is ready to install, including its pinned upstream references. No build or submodule
checkout is needed to install or use a skill.

Live inspection needs the skill's listed tools, authentication, permissions and
network access. Supplied offline artifacts can be analyzed without cloud access.

Create a private YAML profile using the [profile example and contract](skills/workload-triage/references/targeting.md).
For complete copyable GKE and managed-GCP examples and a first lookup, see the
[profile starter guide](examples/profiles/README.md).
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
universal command. Keep the complete skill directory, including its references and scripts.
Skill instructions do not enforce permissions or redact tool output; use
appropriately scoped access. Billing queries may incur charges.

<details>
<summary>Local development, manual installation and fixed revisions</summary>

Install from a plain clone:

```bash
git clone https://github.com/vprashar2929/ops-skills.git
cd ops-skills
npx skills@1.7.0 add . --skill workload-triage --agent codex claude-code
```

Without Node.js, copy `skills/workload-triage/` into a new
`$HOME/.agents/skills/workload-triage` directory (Codex), or
`$HOME/.claude/skills/workload-triage` (Claude Code). Back up an existing installation
before replacing it. For a fixed revision, use
`https://github.com/vprashar2929/ops-skills/tree/<commit-sha>` as the install source.
CI checks installer version `1.7.0`.

An optional archive build requires Python 3.9+ and Git:

```bash
python3 scripts/package_skill.py --all dist/bundle
```

Build destinations must be new; the packager refuses overwrites.

</details>

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

Selected references are committed under each skill's `references/` directory.
Selections live in [the packager](scripts/package_skill.py); delivery and Kafka
use locally authored procedures. Submodules are only needed to refresh or verify
these copies. After reviewing an upstream content/license change and staging its
new gitlink, refresh references in the same pull request:

```bash
git submodule update --init --recursive
python3 scripts/sync_upstream.py
python3 scripts/sync_upstream.py --check
```

The sync refuses dirty or unrecorded upstream revisions and preserves licenses,
file contents and provenance. It only refreshes the explicit selections. If removing
a selection, remove its committed reference directory in the same change. Review
the resulting diff before committing it.
Renovate schedules submodule and GitHub Actions updates weekly without automerge;
its upstream update PRs also need the reviewed reference refresh. Running the bot
requires separate repository setup.

## Contributing

For a local end-user trial without GCP, use the [kind example](examples/kind/README.md).
It includes a synthetic profile and small Kubernetes failure scenarios.

Use synthetic examples and keep client data, credentials and development reports
out of changes. Include the affected skill, agent/tool versions, a sanitized
reproduction and expected versus observed behavior in issues or pull requests.
Follow [AGENTS.md](AGENTS.md) for format validation and upstream update checks.

```bash
git submodule update --init --recursive
python3 -m unittest discover -s tests -v
```

The suite requires Python 3.9+, Git and the initialized pinned submodules. It covers
packaging, reference sync and workload helpers; command tests also require bash
and jq. [Behavior cases](tests/behavior-cases.md) and [fixtures](tests/fixtures/)
are separate agent-driven scenarios, not automatically executed unit tests.

The project is experimental. Representative live and offline cases have been
exercised; broad incident coverage and cross-agent parity are not established.
Format validation is not proof of diagnostic accuracy or time savings.
The local lab demonstrates evidence collection and diagnosis, not production
readiness, automatic remediation, or an accuracy advantage over an agent alone.

## Distribution

Skills are distributed directly from `main`, following the repository installation
pattern used by [Vercel](https://github.com/vercel-labs/agent-skills),
[PlanetScale](https://github.com/planetscale/database-skills), and
[Redis](https://github.com/redis/agent-skills). This is a distribution convention;
the [Agent Skills specification](https://agentskills.io/specification) defines
the skill format, without requiring a release branch or a particular installer.
Our reference-sync helper supports this repo's pinned third-party content; it is
not part of the standard. Merge a validated change to make it available to new
installations. There is no release branch,
publication job, npm package or marketplace registration to maintain.

[Skill distribution](.github/workflows/distribution.yml) runs with read-only
repository permissions on pull requests and pushes to `main`. It checks committed
references against the pinned submodules, runs offline tests, validates source and
assembled skills with the official `skills-ref` tool, and tests real CLI installs
from both the repository and optional bundle for Codex and Claude Code. Its archive
artifact retains script permissions, upstream licenses and revision records.

For an installation previously sourced from `/tree/release`, retain a backup and
reinstall using the default-branch command above to switch its update source.

## License

Copyright 2026 Vibhu Prashar. Repository-authored code, skill instructions,
documentation and examples are licensed under [Apache-2.0](LICENSE).
Each installable skill includes a copy of the license.

Third-party content in `upstream/` and the bundled reference directories retains
its original license and copyright notices. See the [upstream references](#upstream-references)
table and each reference directory's `LICENSE` and `UPSTREAM.json` for details.
