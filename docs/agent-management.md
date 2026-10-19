# Agent management

The existing demo, Ada/Turing task interface, Codex observer, event bus and Godot
café remain available. **Manage agents** opens the new native Godot interface.
Managed agents have configurable Markdown tasks, multiple Markdown roles,
approved workspaces, Git worktrees and persistent execution records.

## Guided project setup

Use the [project setup assistant](project-setup.md) for folder selection, automatic
local connection, readiness checks and a two-agent frontend/backend team. The
manual configuration below remains available. Project-wide AGENTS.md and PLANNING.md
can be loaded, imported through a native file chooser and saved in Setup. Every
managed run receives read-only snapshots from its source repository; see the setup
guide for conflict handling and lowercase filename support.

## Storage and configuration

The backend uses Python's built-in SQLite, without an external database server.
The database, configuration exports, definitions, control token and execution logs
live under `VAC_MANAGEMENT_ROOT` (default `.runtime/management`). Compose persists
this directory in the existing `runtime` volume. Managed project files live in the
new `agent_workspaces` volume mounted at `/workspaces`.

| Setting | Default outside Compose | Purpose |
| --- | --- | --- |
| `VAC_MANAGEMENT_ROOT` | `.runtime/management` | SQLite, JSON configs, control token |
| `VAC_WORKSPACE_ROOT` | management root + `/workspaces` | Only approved project root |
| `VAC_TASKS_ROOT` | management root + `/tasks` | Editable task Markdown |
| `VAC_ROLES_ROOT` | management root + `/roles` | Editable role Markdown |
| `VAC_ALLOW_REMOTE_GIT` | `0` | Explicit server opt-in to remote Git |
| `VAC_MANAGEMENT_TOKEN` | private generated `control-token` file | Native client authorization |

Configuration references workspace IDs and Markdown filenames within these roots;
API clients cannot choose arbitrary absolute host paths. To connect an existing
project, mount/copy it into the approved workspace root first, then create/register
its directory ID. The directory must not contain symlink components. Nested task
references are intentionally disallowed; custom definitions use configurable roots.
Do not mount the Docker socket, private keys or unrelated host directories.

JSON uses the existing Pydantic technology, is human-readable and introduces no
YAML dependency. [Complete example](../examples/backend-agent.json):

```json
{
  "id": "backend-agent",
  "name": "Backend Developer",
  "provider": "codex",
  "workspace": "backend",
  "task": "implement-api.md",
  "roles": ["backend-developer.md", "security-guidelines.md"],
  "git": {
    "enabled": true,
    "repository": "project",
    "branch": "agent/backend-agent/implement-api",
    "worktree": true,
    "allow_push": false
  },
  "execution": {"timeout_seconds": 900, "max_retries": 0}
}
```

Definitions are source files, not database instruction caches. Edits made in the
Markdown editor or on disk apply to the next execution. Each execution receives read-only task/role snapshots under
`.cafe/instructions/` and records SHA-256 hashes of the exact task, roles and combined context it received. Changing
an agent's configuration requires stopping it first. The same task definition can
be reused; assignment and task state belong to each agent/execution.

## Start and configure using Godot

1. Start the backend in Codex mode with a functioning Linux namespace sandbox:
   `VAC_MODE=codex docker compose -f compose.yaml -f compose.privileged.yaml up --build --force-recreate backend`.
   The privileged override remains an explicit local development option, not a
   production recommendation. Managed agents still start inside restricted mounts.
   On Linux/WSL with user namespaces available: `scripts/demo.sh codex`.
2. Log Codex in using the existing `codex_home` volume or local installation.
3. Retrieve the generated management token **locally**:
   `docker compose exec backend cat /workspace/.runtime/management/control-token`.
   For local execution, read `.runtime/management/control-token`. Do not paste it
   into chat, logs, configuration files, task Markdown or Git.
4. Open `game/project.godot` in Godot 4.4.1, press F5, then **Manage agents**.
   Enter the token and choose **Connect / Refresh**. Alternatively set
   `VAC_MANAGEMENT_TOKEN` in the Godot process environment. The UI keeps it in memory.
5. Create a `project` workspace in **Workspaces and Git**. Copy your existing
   project there or initialize Git, stage a reviewed file and make an initial commit.
   A worktree needs a real initial commit; the platform never commits to main for you.
6. Create an empty `backend` workspace for the agent's worktree. Create task and
   role definitions in **Markdown tasks and roles** (examples are under `examples/`).
7. Choose **New agent**, give it an ID/name, select `backend`, a task and roles.
   Enable Git, choose `project` as source repository and select an independent
   branch, or leave the branch empty for `agent/ID/task-name`. Save the configuration.
8. Select the saved agent and click **Start agent**. Its character appears in the
   café and receives real observed runtime states. **Stop** cancels and reaps its
   process tree; **Restart** stops the active run and reloads current Markdown.
9. Inspect execution history, live activity logs, private workspace output,
   modified files, diffs and commits. Automatic requirements validation replaces
   manual acceptance buttons. Model completion alone never validates the project.

Two agents can use the same source repository with separate workspace/worktree IDs
and branches. Uncheck **Separate Git worktree** to use an ordinary repository workspace; select
the same ID for source repository and workspace. Agents sharing an ordinary
workspace run sequentially; the controller
rejects concurrent claims. Persistent worktrees are kept for review and subsequent
runs, rather than deleted with uncommitted work. Optional automatic feature integration and tested main promotion are described in [automatic integration](automatic-integration.md).

## HTTP API

Management endpoints require `Authorization: Bearer <token>`. JSON mutations reuse
the original 32 KiB body limit and reject browser Origin headers. Never put tokens
in URLs. The public activity WebSocket contains summaries, not definitions or tokens.

| Endpoint | Operation |
| --- | --- |
| `GET /management` | Configs, definitions, workspaces, latest execution records |
| `POST /management/workspaces` | Create/register `{ "id": "project" }` under approved root |
| `PUT /management/definitions/tasks/{filename}` | Save `{ "content": "# Task…" }` |
| `PUT /management/definitions/roles/{filename}` | Save role Markdown |
| `POST /management/agents` | Create validated JSON configuration |
| `PUT /management/agents/{id}` | Update configuration / replace assigned task and roles |
| `POST /management/agents/{id}/start` | Validate, prepare worktree, execute; body `{}` |
| `POST /management/agents/{id}/stop` | Cancel; body `{}` |
| `POST /management/agents/{id}/restart` | Stop active execution then start; body `{}` |
| `GET /management/executions/{id}` | Runtime status and separate acceptance |
| `GET /management/executions/{id}/logs?after=N` | Up to 200 sanitized entries after sequence N |
| `POST /management/executions/{id}/review` | `{ "accepted": true, "note": "Reviewed tests and diff" }` |
| `GET /management/workspaces/{id}/git` | Repository, branch, changed files, latest 20 commits |
| `GET /management/workspaces/{id}/diff` | Tracked-file diff against HEAD |
| `POST /management/workspaces/{id}/git` | Typed operation, never raw shell commands |

Git operations: `init`, `connect`, `clone` + remote, `branch`/`switch` + branch,
`stage` + individual files, `commit` + message, `remote` + credential-free URL and
`remote_name` (local configuration only); optional `fetch`, `pull` (fast-forward only),
`push` (only the configured agent's own branch namespace). Agents select `git.remote_name` (default `origin`).
Manual network remote operations require server opt-in, an applicable
agent permission and an explicit `confirmed: true` request. Automatic publication
requires the additional persisted `git.push_on_success` authorization. Clone requires server
opt-in and confirmation. Use the SSH Compose override to forward an existing agent
socket and read-only known_hosts to the backend. Workers never receive this socket.
Unknown SSH host keys fail closed; host key verification is never disabled.

Destructive commands (`reset`, `clean`, forced pushes, deleting branches/worktrees,
merges) are **not exposed** by the API/helper. If needed, stop the agent and review
and authorize such work outside the platform. Credential and runtime files cannot
be staged or committed through GitService.

## Runtime and security boundaries

Logical components live under `backend/virtual_agent_cafe/management/`:
registry, Markdown/workspace managers, GitService, execution coordinator, SQLite
store, management authorization and a namespace wrapper around CodexAdapter.

[Bubblewrap](https://github.com/containers/bubblewrap) creates an empty mount
namespace with read-only system runtime directories, fresh `/tmp`, private PID/IPC/
UTS namespaces and a writable mount of the assigned workspace. It does not expose
controller configuration/database, the repository checkout, other project files,
host home directories or runtime sockets. Git metadata is read-only to the model.
The Codex process also retains its existing workspace-write sandbox. No unsandboxed
fallback exists: namespace failures reject managed starts. Install `bubblewrap`
locally; the rebuilt image and CI install it explicitly.

The authenticated Codex process needs its read-only `auth.json`; treat the chosen
runtime and tasks as trusted users of that model credential. Network access is
retained for model requests; this is filesystem/process isolation, not an egress
firewall. Use a dedicated low-privilege model account and isolated container/network
for untrusted tenants. Read-only `/usr` and `/opt/venv` must contain trusted runtime
libraries, not unrelated private project files.

Workers request authorized Git actions with `python3 .cafe/git.py status`, `diff`,
`history`, `stage FILE...`, `commit 'message'`, or `branch`/`switch agent/ID/NAME`.
File requests are scoped to one execution and workspace, validated and bounded;
remote operations and destructive actions are unavailable. If an agent explicitly
switches to another allowed branch, monitoring records that branch; update its
configured branch before the next start. An existing worktree with a mismatched
branch is rejected instead of silently discarding or moving work. Private diffs return
inside that workspace. GitService itself executes Git in restricted mount namespaces,
with hooks/external diff/fsmonitor/global config disabled and argument-based commands.
Git helper requests have separate bounded directories for each execution.
Raw CLI output, prompts, reasoning and credentials never enter persistent activity logs.

Precedence: system security > validated configuration > roles (first listed has highest priority) > project AGENTS.md > project PLANNING.md > task.
Timeouts/cancellation terminate processes. Failed runtimes can retry at most twice;
retries preserve files for inspection and are explicit configuration. A controller
restart marks interrupted executions FAILED, rather than pretending they finished.

## States and limits

Agent lifecycle: CREATED (configuration being entered), CONFIGURED, READY (validated),
RUNNING, COMPLETED/FAILED/CANCELLED. Task state: PENDING (no assignment), ASSIGNED,
RUNNING, FAILED/CANCELLED and COMPLETED after automatic shared validation.
A standalone runtime remains UNVERIFIED. An enabled team's worker results wait
for shared integration; successful main promotion records AUTO_VALIDATED.
The GUI has no manual acceptance gate. See [automatic integration](automatic-integration.md).

Run **one Uvicorn worker/controller**. An exclusive filesystem lock rejects a second
controller sharing the same management store before restart recovery. In-process
workspace locks plus Git's index/ref locks protect active work; multi-host orchestration is outside this release.
Up to 62 managed IDs coexist with the two original café characters. Their detailed
monitoring is in the management panel; the original two station cards remain fixed.
Additional characters reuse café stations, so a small team is visually clearest.
Legacy Ada/Turing execution remains a trusted-user compatibility path and does not
claim the stronger managed isolation. While managed executions run, legacy mutation
endpoints also require the management token, preventing workers using them as a bypass.

## Validation

`scripts/check.sh` runs backend pytest, lint/format, Godot import/state/headless
checks and actual HTTP/WebSocket/Godot integration. Management tests cover persisted
configs/definitions/logs, path rejection, real namespace isolation, temporary Git
repositories/branches/worktrees/commits, workspace concurrency, failures, timeout,
restart recovery, acceptance review and native Godot management actions. Normal
checks use deterministic CLI fixtures and never invoke paid model tasks.


An opt-in probe using the real model is available as `scripts/management-smoke.sh`.
It creates a temporary source repository and agent worktree, executes a Markdown
Python task, independently reruns its unittest and verifies a commit on the assigned
branch. It makes no remote Git calls. It requires Codex login and uses model quota;
it is deliberately excluded from ordinary tests.

## Files in this extension

| File | Change |
| --- | --- |
| `.github/workflows/ci.yml` | Modified |
| `Dockerfile` | Modified |
| `PROGRESS.md` | Modified |
| `README.md` | Modified |
| `backend/tests/fixtures/managed_runtime_app.py` | Created |
| `backend/tests/test_game_management.py` | Created |
| `backend/tests/test_management_definitions.py` | Created |
| `backend/tests/test_management_execution.py` | Created |
| `backend/tests/test_management_git.py` | Created |
| `backend/virtual_agent_cafe/main.py` | Modified |
| `backend/virtual_agent_cafe/management/__init__.py` | Created |
| `backend/virtual_agent_cafe/management/api.py` | Created |
| `backend/virtual_agent_cafe/management/config.py` | Created |
| `backend/virtual_agent_cafe/management/execution.py` | Created |
| `backend/virtual_agent_cafe/management/files.py` | Created |
| `backend/virtual_agent_cafe/management/git.py` | Created |
| `backend/virtual_agent_cafe/management/git_helper.py` | Created |
| `backend/virtual_agent_cafe/management/registry.py` | Created |
| `backend/virtual_agent_cafe/management/sandbox.py` | Created |
| `backend/virtual_agent_cafe/management/security.py` | Created |
| `backend/virtual_agent_cafe/management/storage.py` | Created |
| `compose.ssh.yaml` | Modified |
| `compose.yaml` | Modified |
| `docs/agent-management.md` | Created |
| `docs/architecture.md` | Modified |
| `docs/event-schema.md` | Modified |
| `examples/backend-agent.json` | Created |
| `examples/roles/backend-developer.md` | Created |
| `examples/roles/frontend-developer.md` | Created |
| `examples/roles/security-guidelines.md` | Created |
| `examples/roles/test-engineer.md` | Created |
| `examples/tasks/implement-api.md` | Created |
| `game/scripts/cafe.gd` | Modified |
| `game/scripts/character.gd` | Modified |
| `game/scripts/event_state.gd` | Modified |
| `game/scripts/management.gd` | Created |
| `game/scripts/management.gd.uid` | Created |
| `game/tests/test_management.gd` | Created |
| `game/tests/test_management.gd.uid` | Created |
| `game/tests/test_states.gd` | Modified |
| `scripts/management-smoke.sh` | Created |
| `scripts/management_smoke.py` | Created |

The pre-existing local scene UID changes in `game/scenes/cafe.tscn` were preserved and excluded.

## Interface and input regression coverage

The management surface now uses separately scrolling cards and a fixed agent action
bar. Refresh retains selection and unsaved text; delayed HTTP actions are queued,
and duplicate clicks are blocked. New agents become selected when saved. Embedded
4K dropdowns, local validation and server-derived action states improve operation.
See [GUI design, screenshots and actual mouse/keyboard tests](gui-testing.md).

## Optional publication after execution

Enable server remote Git (`setup-project.py --publish-results`), then configure:

```json
{
  "enabled": true,
  "repository": "project",
  "branch": "agent/backend-agent/implement-api",
  "worktree": true,
  "remote_name": "origin",
  "allow_push": true,
  "push_on_success": true
}
```

This is the agent configuration's `git` object. The worker commits reviewed files
using the existing private helper; the controller pushes after runtime success.
Only that agent's `agent/<id>/…` namespace is allowed. A dirty project tree blocks
publication (`.cafe` runtime files are excluded). The configured push destination
must be one credential-free HTTPS or SSH URL. No force, tags, mirror or merge.
Publication status and the pushed commit are persisted separately from runtime
success and task acceptance. See [setup instructions](project-setup.md#ergebnisse-automatisch-auf-github-hochladen).

Automatic shared integration and main promotion are an additional explicit team opt-in;
see [workflow, requirements manifest and safeguards](automatic-integration.md).
