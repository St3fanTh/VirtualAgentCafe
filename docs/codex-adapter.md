# Codex runtime integration

Live tasks invoke the installed CLI with the public machine-readable stream:

```text
codex exec --json --ephemeral --ignore-user-config --sandbox workspace-write -C <agent-workspace> --output-last-message <agent-workspace>/.cafe/last-response.md -
```

Prompts go through stdin, not shell interpolation or process arguments. The backend
never stores them in job history, logs or public frames. Stderr is discarded; raw
JSONL is parsed in memory and not retained. Reasoning content and agent response
content are not broadcast. The final response is saved privately to
`.cafe/last-response.md` in that agent’s workspace and can be read locally. Public bubbles identify an observed response; explicit
peer messages are public by design.

Source: [official non-interactive Codex documentation](https://developers.openai.com/codex/noninteractive/).
Flags were verified with the installed CLI **0.162.1**. Docker pins this same CLI
version. `--ignore-user-config` prevents loading unrelated MCP/plugin configuration;
saved CLI authentication is still used. No bypass flag is supplied.

## Event mapping

| Observed JSONL | Public event |
| --- | --- |
| Backend accepted a task | agent.started |
| turn.started | agent.thinking (model turn active) |
| file_change started/completed | agent.coding |
| command_execution started, recognized test invocation | agent.testing |
| Other command starts / successful command ends | agent.waiting |
| agent_message or collab_tool_call completed | agent.message (content private) |
| Runtime/tool/command failure | agent.error |
| Process exits 0 + turn.completed + no fatal/unresolved test/edit failure | agent.finished |

`Thinking` denotes a public **active model turn**, not inspection of thoughts or a
verified per-request API trace; the CLI does not expose an exact model-call lifecycle.
Reasoning items do not trigger animations or expose text. Unknown event types are
ignored; malformed/oversized JSONL fails the task. Tests are recognized from parsed
command tokens, including shell wrappers, rather than from arbitrary output text.
Editing via general shell commands is not labeled coding: only file_change evidence
produces that state. Nonzero tests require a subsequent observed successful test
run before success. Non-test command failures remain visible as error events and are
counted as warnings, but do not alone invalidate a completed model turn: discovery
commands such as `rg --files` can legitimately return 1 in a new empty workspace.
The success summary explicitly mentions command warnings. Successful unrelated
commands cannot clear failing tests, failed edits or fatal runtime errors. A known namespace/sandbox failure remains fatal even when Codex
finishes its turn with a polite explanation.

## Tasks, files and communication

- `POST /agents/ada/tasks` with JSON `{ "prompt": "..." }` returns 202, task_id and workspace.
- `GET /tasks/<task_id>` returns running/finished/error/cancelled and a safe summary.
- `POST /agents/ada/cancel` stops the process group and its children.
- `POST /agents/ada/messages` with `{ "recipient": "turing", "text": "Please review" }`
  emits an actual delivery event and receiving-agent event with shared correlation ID.
  Both must be idle. This is an explicit user message, not invented model dialogue.
  It does not automatically start another model turn.

Each agent has a persistent separate Git workspace: `.runtime/workspaces/ada` and
`.runtime/workspaces/turing`. New tasks on the same agent can build on earlier files;
there is one concurrent task per agent, two total. `VAC_TASK_ROOT` changes the parent
path and `VAC_TASK_TIMEOUT` changes the 300-second deadline. Results are files in
these workspaces; code is not automatically merged into the Café repository.
These directories may be seeded with a project to work on. Symlink escapes are
rejected. Job metadata is bounded to 100 entries and is not persisted across restart.

Task bodies are limited to 32 KiB, prompts to 8000 characters, messages to 256.
Browser Origin headers are rejected for mutation and WebSocket connections; trusted
Host headers and loopback-only published ports reduce accidental browser exposure.
This is a local native app for a trusted workstation, not a public multi-user service.

## Live setup

```bash
codex login
codex login status
scripts/demo.sh codex
# Another terminal:
godot --path game
```

For Compose, persist login in the shared named volume:

```bash
docker compose --profile dev run --rm codex codex login --device-auth
VAC_MODE=codex docker compose up --build backend
```

The workspace-write sandbox requires working Linux user namespaces. Check it with
an actual harmless Codex task. The original container rejected namespaces
with `bwrap: No permissions to create a new namespace`. The privileged rebuild
now passes the real editing/testing smoke with the corrected adapter. Configure your host/container to support Codex's sandbox, or run backend
in WSL directly where it is supported. No automatic sandbox bypass is provided.

Run the opt-in real smoke test after login and sandbox setup:

```bash
scripts/codex-smoke.sh
```

It asks the real CLI to create a Python function and unittest in a temporary Git
workspace, observes editing/testing/completion and independently reruns the created
tests. Normal CI uses a subprocess JSONL fixture for adapter behavior and performs
no billable model calls. Never present fixture/demo events as a completed live run.
