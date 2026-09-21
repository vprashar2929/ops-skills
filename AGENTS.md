# Skill maintenance requirements

Every skill change in this repository must follow the current
[Agent Skills specification](https://agentskills.io/specification). Check the
official specification and relevant authoring guidance when changing the format
or workflow; distinguish required fields from optional recommendations.

Before declaring a skill change complete:

- Run the official `skills-ref validate` on the source and assembled skill.
  Keep the distributable leaf directory identical to the frontmatter name, e.g.
  `dist/validation-N/workload-triage/`. Codex quick validation alone is insufficient.
- Check that packaged relative links resolve, operational resources are directly
  discoverable from SKILL.md, and detailed references load only when relevant.
- Keep SKILL.md below the recommended 500 lines / 5,000 tokens; document actual
  prerequisites. Do not add optional fields or infrastructure merely for appearance.
- Run tests appropriate to changed behavior and packaging. Report exactly what
  was tested; format validation does not establish operational or cross-agent
  correctness. Do not contact live infrastructure solely to validate formatting.
- Preserve the pinned upstream content and its attribution. Keep client profiles
  outside the distributed skill. Local adapters/helpers remain our responsibility.
- When updating the installed pilot, validate the final installed directory and
  verify it matches the tested bundle. Retain a recoverable previous bundle.

If validation cannot run, report the specific unverified check instead of claiming
compliance. These are maintenance requirements, not an automated CI enforcement
mechanism. Prefer changes supported by observed operational needs or test failures;
keep workload triage scoped to read-only inspection and diagnosis.
