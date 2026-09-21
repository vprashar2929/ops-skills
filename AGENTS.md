# Skill maintenance requirements

Every skill change in this repository must follow the current
[Agent Skills specification](https://agentskills.io/specification). Check the
official specification and
[skill creation best practices](https://agentskills.io/skill-creation/best-practices)
when changing the format or workflow; distinguish requirements from recommendations.

Before declaring a skill change complete:

- Run the official `skills-ref validate` on the source and assembled skill.
  Keep the distributable leaf directory identical to the frontmatter name, e.g.
  `dist/validation-N/workload-triage/`. Agent-specific quick checks do not replace
  official validation.
- Check that packaged relative links resolve, operational resources are directly
  discoverable from SKILL.md, and detailed references load only when relevant.
- Keep SKILL.md below the recommended 500 lines / 5,000 tokens; document actual
  prerequisites. Do not add optional fields or infrastructure merely for appearance.
- Run tests appropriate to changed behavior and packaging. Report exactly what
  was tested; format validation does not establish operational or cross-agent
  correctness. Do not contact live infrastructure solely to validate formatting.
- Preserve the pinned upstream content and its attribution. Review upstream
  content and license changes before advancing a gitlink; passing format checks
  alone does not approve new instructions. Keep client profiles outside packages.
  Update shared operational guidance consistently across affected skills.
- When updating an installation, validate the final installed directory and
  verify it matches the tested bundle. Retain a recoverable previous bundle.

If validation cannot run, report the specific unverified check instead of claiming
compliance. These are maintenance requirements, not an automated CI enforcement
mechanism. Prefer changes supported by observed operational needs or test failures;
keep workload triage scoped to read-only inspection and diagnosis.
