# How the Google reference is used

For GKE failure diagnosis, read the relevant symptom sections in
[Google's workload troubleshooting guide](google-gke-workload/guide.md).
The upstream content is unchanged; its packaged filename is `guide.md` to avoid
registering a second skill. It carries its upstream license and revision in
`google-gke-workload/`. It is supporting reference material for this skill, not
a second automatically invoked workflow. Read this adaptation before its steps.

Review baseline: google/skills commit
`28094838f3069420a17303213faa9297f5c6e84d`, 2026-09-21. A packaged newer SHA is not
automatically reviewed: compare it with this baseline and rerun relevant cases
before team release. Packaging does not perform a semantic instruction review.

Apply these specific adaptations:

| Upstream behavior | Behavior in workload-triage |
| --- | --- |
| Infer active project/context and default namespace | Resolve explicit client/environment/cluster/namespace and verify endpoint first |
| Fetch cluster credentials | Use an existing verified context; report setup gaps |
| On failed access, synthesize a cause and fix | Separate hypotheses from facts; no asserted cause or patch without evidence |
| Diagnose exit codes as unique causes | Correlate termination reason, events, logs and metrics; exit 137 or 128 alone is insufficient |
| Pending implies unschedulable; empty endpoints imply failed backend | Inspect conditions, selector, readiness and service type before attributing cause |
| Whole specs/describe output and all-container logs | Project needed fields; sample named containers; handle config/log sensitivity |
| Logging time flags and broad node/event queries | Use timestamp filter predicates, explicit scope, limits and actual log routing |
| Directly propose a NetworkPolicy or IAM fix from a timeout/error | Establish denied path, identity and policy evidence first |
| Create/update a branch and PR as the last step | Return a recommendation; source changes/PRs require a separate requested change task |

The upstream skill supplies useful symptom branches and official reference links.
Our additions cover client targeting, delivery ownership, configuration provenance,
and evidence handling. Neither instruction layer enforces tool permissions.
