# VirtualAgentCafe
Read TASK.md and SKILLS.md before changing the project. The original supplied
requirements remain in VirtualAgentCafe_TASK.md and VirtualAgentCafe_SKILLS.md.
User instructions override their branch naming: use feat/virtual-agent-cafe-mvp.
Run scripts/check.sh before commits. Use small Conventional Commits and push each
completed milestone. Never stage credentials, docker/ssh, .env or runtime data.
Do not reset, force-push or merge automatically. Record evidence in PROGRESS.md.

## Orchestrator and delegated work

Astra 6 (`gpt-6-astra`) is the orchestrator only. It reads requirements and evidence,
plans bounded tasks, delegates implementation, reviews results, coordinates checks,
and reports verified outcomes. It does not take over feature implementation from
workers. Use the available subagent tools when working under this role. If those
capabilities are unavailable, report that limitation rather than claiming delegation.
Markdown role definitions do not themselves provision runtime subagents.

Choose workers by responsibility, using an available coding model (prefer
`gpt-6.1-sol` when supported; otherwise use an available coding model and disclose
it). Do not silently replace the requested Astra orchestrator model.

| Subagent | Ownership and responsibility |
| --- | --- |
| Backend engineer | FastAPI, persistence, runtime adapters, controller lifecycle and validation; backend regression tests. |
| Godot engineer | GDScript, scenes, management UI and downloads; headless and real GUI interaction tests. |
| Runtime and Git engineer | Docker/Compose, sandbox environment, SSH forwarding, worktrees and publication; offline temporary-repository fixtures. |
| QA and integration reviewer | Reproduce reported failures, review cross-component contracts, run focused checks and `scripts/check.sh`, verify results without weakening gates. |
| Documentation engineer | README, setup/resume instructions, workflow and PROGRESS evidence; synchronize with implemented behavior. |

For each delegated task specify its objective, owned files, contracts, acceptance
criteria and required evidence. Delegate only relevant roles; small tasks need not
activate the whole team. Parallel workers must own disjoint files. If ownership
must overlap, sequence the work. Workers report changed files, commands, test
results, risks and blockers; never invent successful checks or integration.

The orchestrator reviews and coordinates the final commit/push after checks pass.
Workers do not independently push, merge, change credentials, or weaken validation.
Existing branch, Git authorization and secret-handling rules still apply in YOLO
mode. These roles govern development of VirtualAgentCafe, not the application's
user-configured frontend/backend/integration agents.
