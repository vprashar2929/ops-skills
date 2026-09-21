# Operational skills pilot

One portable `workload-triage` skill for scoped Kubernetes inspection and incident
investigation. Client profiles live separately. Native kubectl/gcloud/Helm provide
the evidence; there is no observe dependency or collection framework.

## Assemble and try it

Prerequisites: Git, Python 3.9+ for packaging; kubectl plus appropriate identity and
network access for use. GKE identity verification needs gcloud. Helm and jq are
optional, used only for relevant inspections. Runtime profile YAML is read by the
agent; no Python/YAML runtime package is required.

```bash
git submodule update --init --recursive
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py dist/workload-triage
```

Run from this repository. The destination must not exist; for another build choose
a new output directory. The packager copies only our skill and the selected Google
workload skill with its required resources, license and SHA. It refuses a dirty
or unrecorded upstream revision. Do not install the entire upstream skill catalog.

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

Install the complete assembled `workload-triage` directory using the target
agent's supported skill installation mechanism when ready. Copying only SKILL.md
loses references. Direct file invocation is the pilot path; automatic discovery
and Claude/Codex behavioral parity still need testing. Instruction portability
does not supply cloud permissions, network access, or tool enforcement.

## Client profiles

See `skills/workload-triage/references/targeting.md` for the small profile contract.
Maintain private mappings and conventions outside this repository and supply the
profile explicitly. Keep credentials and secret values out. No default client,
namespace, automatic environment detection, inheritance, or profile registry.

The separate local NCNP profile currently covers dev/test/nprd Apps and BFF;
production is deliberately absent from this initial pilot. Repository conventions
are hints verified against the actual workload/run before use. A different local
context alias can be supplied if it verifies against the same cluster endpoint.

## Upstream maintenance

`upstream/google-skills` is an unmodified Git submodule of
[google/skills](https://github.com/google/skills), Apache-2.0. The only selected
skill is `skills/cloud/gke-workload-troubleshooting`. Its commit is recorded by
the parent gitlink; `branch = main` selects the update source, not a floating
runtime version. Local adaptations live in `references/gke-adaptation.md`.

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

Packaging tests exercise a self-contained bundle, preserved upstream content,
refusal of local upstream edits/revision mismatch, and no destination overwrite.
On 2026-09-21 both packaging tests passed; the assembled skill passed the
skill-creator frontmatter validator and its local Markdown references resolved.
Profile YAML and local kubeconfig mappings were checked separately. Renovate
configuration has been checked for JSON syntax, not tested with a connected bot.
`tests/behavior-cases.md` defines the next behavioral checks. Frontmatter and
packaging checks are preparation, not evidence of live diagnostic effectiveness.
Keep this a pilot until real workload and cross-agent results support release.
