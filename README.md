# ops-skills distribution

Generated skills with pinned upstream references. Edit the source branch, not this distribution. SOURCE.json records the source commit and whether it included uncommitted changes.

Install with Node.js 22.20+ and Git:

```bash
npx skills@1.7.0 add https://github.com/vprashar2929/ops-skills/tree/release --skill workload-triage --agent codex claude-code
```

Installation defaults to the current project; add --global for personal use. Use --list to inspect the catalog or --skill '*' to select all skills.

Invoke $workload-triage in Codex or /workload-triage in Claude Code. Supply your own private profile using the [targeting contract](skills/workload-triage/references/targeting.md), plus the environment and resource to inspect. Live inspection requires the relevant CLIs, authentication, permissions and network access.

Repository-authored content is licensed under [Apache-2.0](LICENSE). Each upstream reference retains its license and UPSTREAM.json provenance. See the [source repository](https://github.com/vprashar2929/ops-skills) for maintenance instructions.
