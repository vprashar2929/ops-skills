# ops-skills

Portable [Agent Skills](https://agentskills.io/) for Kubernetes and Google Cloud
operations. Inspect resources, investigate symptoms and return evidence with next
steps. Use explicit profiles and existing CLI/API access; profiles and
credentials stay outside the repository. The skills do not perform remediation.
For Prometheus HTTP queries, a supplied endpoint URL is sufficient; no profile is required.

## Quick start

New to this repo? Start with the [Codex local-lab walkthrough](examples/kind/README.md).
It takes you from prerequisites to a live diagnosis and cleanup without cloud
credentials. Use the installation below when you already have a target environment.

Requires Git and Node.js 22.20+. Install the validated distribution from `release`:

```bash
# Choose skills and agents interactively
npx skills@1.7.0 add https://github.com/vprashar2929/ops-skills/tree/release

# Browse available skills
npx skills@1.7.0 add https://github.com/vprashar2929/ops-skills/tree/release --list

# Install one skill for Codex and Claude Code
npx skills@1.7.0 add https://github.com/vprashar2929/ops-skills/tree/release \
  --skill workload-triage --agent codex claude-code
```

Installation defaults to the current project; add `--global` for personal use.
Choose either agent or both, and use `--skill '*'` to select all nine skills.
The [skills CLI](https://github.com/vercel-labs/skills) supports additional agents;
our installation checks cover Codex and Claude Code. Each published skill includes
its pinned upstream references. No build or submodule checkout is needed to
install or use the distribution. `main` contains build inputs: do not install its
skill directories directly, because upstream references are assembled during packaging.

Live inspection needs the skill's listed tools, authentication, permissions and
network access. Supplied offline artifacts can be analyzed without cloud access.

Create a private YAML profile using the [profile example and contract](skills/workload-triage/references/targeting.md).
Use `profile_version: 1`. The `profile` identity field names a set of target
mappings; profiles can be organized per user, cluster, environment, or a combination.
For complete copyable GKE and managed-GCP examples and a first lookup, see the
[profile starter guide](examples/profiles/README.md).
Replace the example project, location, cluster and context with your own mappings.
For managed GCP services, see the [cloud targeting contract](shared/operations.md).
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

Building local changes requires Python 3.9+ and initialized submodules:

```bash
git clone --recurse-submodules https://github.com/vprashar2929/ops-skills.git
cd ops-skills
python3 scripts/package_skill.py --all dist/bundle
npx skills@1.7.0 add ./dist/bundle --skill workload-triage --agent codex claude-code
```

Without Node.js, copy the assembled `dist/bundle/skills/workload-triage/` into a new
`$HOME/.agents/skills/workload-triage` directory (Codex), or
`$HOME/.claude/skills/workload-triage` (Claude Code). Back up an existing installation
before replacing it. For a fixed version or rollback, use
`https://github.com/vprashar2929/ops-skills/tree/<release-commit-sha>` as the install
source. Choose a commit from the `release` branch, not a source commit from `main`.
CI checks installer version `1.7.0`.

Build destinations must be new; the packager refuses overwrites.

</details>

## Skills

| Skill | Purpose |
| --- | --- |
| [workload-triage](skills/workload-triage/SKILL.md) | Namespaces, workload status, logs and configuration references |
| [service-connectivity-triage](skills/service-connectivity-triage/SKILL.md) | Service endpoints, network policies and Istio routing |
| [gke-cluster-triage](skills/gke-cluster-triage/SKILL.md) | Nodes, scheduling capacity, autoscaling and storage |
| [observability-triage](skills/observability-triage/SKILL.md) | Prometheus alert/metric queries, signal discovery, scrape failures and missing logs |
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
| [wshobson/agents](https://github.com/wshobson/agents) | Istio traffic, mesh observability, Prometheus and Grafana metric patterns | MIT |
| [planetscale/database-skills](https://github.com/planetscale/database-skills) | Selected MySQL diagnostics | MIT |

The submodule gitlinks pin the upstream revisions. Selections live in
[the packager](scripts/package_skill.py); delivery and Kafka use locally authored
procedures. Generated upstream references are not maintained in the source tree.
The packager copies selected content into each distribution's `references/`
directory. After reviewing an upstream content/license change and staging its
new gitlink, build and inspect the resulting skills:

```bash
git submodule update --init --recursive
python3 scripts/package_skill.py --all dist/upstream-review
```

The packager refuses dirty or unrecorded upstream revisions and preserves licenses,
file contents and provenance. It includes only the explicit selections and rejects
generated copies placed back in source. Required links must resolve inside each
assembled skill. Source `SKILL.md` links to shared and upstream resources resolve
after building.

Hosted Renovate schedules submodule and GitHub Actions updates weekly without
automerge. A submodule update needs no reference-refresh commit or post-upgrade
script: CI builds from its proposed pin. Review the upstream content and license
diffs and the CI bundle before merging; passing format checks does not approve new
instructions. Upstream moves or incompatible content can still require changes
to the selections or local procedures. Running the bot requires separate repository setup.

## Contributing

For a local end-user trial without GCP, use the [kind example](examples/kind/README.md).
It includes a synthetic profile and small Kubernetes failure scenarios.

Use synthetic examples and keep private operational data, credentials and
development reports out of changes. Include the affected skill, agent/tool versions, a sanitized
reproduction and expected versus observed behavior in issues or pull requests.
Follow [AGENTS.md](AGENTS.md) for format validation and upstream update checks.

```bash
git submodule update --init --recursive
python3 -m unittest discover -s tests -v
```

The suite requires Python 3.9+, Git and the initialized pinned submodules. It covers
packaging, publication against a local bare Git remote, and workload helpers;
command tests also require bash and jq. [Behavior cases](tests/behavior-cases.md)
and [Markdown fixtures](tests/fixtures/)
are separate agent-driven scenarios, not automatically executed unit tests.

The synthetic [PromQL query fixture](tests/fixtures/prometheus-queries.test.yml)
is executable with `promtool` (tested with 3.5.0), without a running server:

```bash
promtool test rules tests/fixtures/prometheus-queries.test.yml
```

This optional check covers query results and edge cases; it does not test HTTP
access or agent behavior and is not part of the Python suite or current CI job.

The project is experimental. Broad incident coverage and cross-agent behavioral
parity are not established. Format and installation checks do not prove diagnostic
accuracy, production readiness or time savings.

## Distribution

The source and distribution layouts have separate responsibilities:

| Location on `main` | Maintained content |
| --- | --- |
| `skills/<name>/` | Authored skill instructions, scripts and local references; build inputs |
| `shared/` | Authored references maintained once and copied into selected skills |
| `upstream/` | Git submodules pinned to exact upstream revisions |
| `scripts/package_skill.py` | Selection rules and assembly; creates complete skill directories |
| `scripts/publish_distribution.py` | Publishes the already validated bundle; does not assemble it |
| `tests/` | Unit, packaging, publication and installer checks, plus manual behavior scenarios |
| `.github/workflows/distribution.yml` | Coordinates validation and publication |
| `dist/` | Ignored local build output; never maintained by hand |

On `release`, `skills/<name>/` contains each complete skill, including its operational
scripts, shared guidance and selected upstream references. Repository build scripts,
tests and submodules are excluded. `SOURCE.json` identifies the source commit;
each upstream reference has `UPSTREAM.json` recording its origin and selection.
Edit sources on `main`; `release` is generated. The bare `owner/repo` installer
shorthand selects `main`, so use the explicit `/tree/release` URL.

Edit [the shared operational contract](shared/operations.md) once; the packager
includes it in each selected skill. Installed skills remain self-contained.
This publishing layout is our choice: the
[Agent Skills specification](https://agentskills.io/specification) defines the skill
format, without requiring a release branch or a particular installer.

[Skill distribution](.github/workflows/distribution.yml) builds from the pinned
sources on every PR and push to `main`. Its validation job has read-only repository
permissions. It runs offline tests, validates source and assembled formats with
official `skills-ref`, checks packaged links, and tests real CLI installations of
the bundle for Codex and Claude Code in copy and symlink modes. The archive retains
script permissions, upstream licenses and provenance. PR artifacts are available
for review; they are never published as releases.

After a successful `main` build, a separate job with `contents: write` publishes
that same validated artifact using [the publisher](scripts/publish_distribution.py).
It verifies the clean source revision and staged Git file contents, skips superseded
builds, and pushes without force. Git ignore rules cannot drop validated files;
Git attribute transformations cause publication to fail rather than alter them.
Previous distribution commits remain available for fixed installs and rollback.
Failed validation prevents publication; a rejected push leaves the previous release
intact. If a job fails after pushing, check `release`'s `SOURCE.json` before retrying.
Repository policy must allow the workflow token to push to `release`.

Use the workflow's manual trigger on `main` to retry publication. After deploying
the workflow, confirm that `release`'s `SOURCE.json` records the intended source
commit before installing it. Local development uses the same packager and installs
from `dist/bundle`; moving a checkout is not an installation update.

## License

Copyright 2026 Vibhu Prashar. Repository-authored code, skill instructions,
documentation and examples are licensed under [Apache-2.0](LICENSE).
Each installable skill includes a copy of the license.

Third-party content in `upstream/` and the published reference directories retains
its original license and copyright notices. See the [upstream references](#upstream-references)
table and each reference directory's `LICENSE` and `UPSTREAM.json` for details.
