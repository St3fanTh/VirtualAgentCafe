# Architecture

FastAPI owns one in-memory EventBus on its asyncio event loop. Events receive a
global monotonic sequence. State is updated synchronously before fan-out; producers
never wait for animation or network I/O. Each subscriber has a bounded queue.
Overflow replaces obsolete history with a current snapshot. A new WebSocket always
starts with a snapshot, so reconnect needs no unbounded replay log. Restart resets
sequence; snapshots are authoritative. Recent duplicate UUIDs are ignored; out-of-order
new events are rejected. Run one Uvicorn worker; horizontal scaling is outside this MVP.

Demo and Codex are separate modes, visibly identified in every event. The deterministic
demo is illustrative. Real activities come exclusively from observed CLI JSONL events.
The Godot client owns presentation, movement and local animation time, never agent state.
Tasks are submitted separately from the activity stream; private prompts and raw tool
outputs are never broadcast. State and job history are ephemeral.

Presentation uses a separate bounded queue (16 observed states per character) and
0.65 s minimum dwell so short edits/test invocations remain visible. Overflow
collapses stale presentation to recent evidence. The HUD continues to show current
backend state. Snapshots immediately clear pending animations and replace state.
Final Codex responses are written privately into the workspace, never broadcast.

## Persistent management extension

The legacy JobManager keeps its compatibility behavior. The separate management
coordinator reuses CodexAdapter and EventBus, adds validated JSON agent configurations,
Markdown managers, an approved WorkspaceManager, GitService and SQLite persistence.
Its native Godot panel uses authenticated HTTP for administration; observed managed
activity joins the existing WebSocket stream and dynamically creates café characters.

Managed executions validate actual mount-namespace isolation before preparation,
claim a workspace, prepare an independent Git worktree and freeze Markdown context.
The Codex namespace exposes only runtime files, model authentication and assigned
workspace/instruction mounts. Git metadata is read-only there. Scoped file requests
let the controller perform authorized Git operations without giving workers controller
API credentials or SSH agent access. Runtime completion and task acceptance are
separate durable fields. See [agent management](agent-management.md) for boundaries,
configuration, APIs, startup and operational limits.

## Automatic team integration

`management/integration.py` coordinates published worker results using persisted
project records and per-project asynchronous jobs. `ExecutionManager` retains
runtime ownership, workspace claims, immutable instruction snapshots and event
streaming. `management/validation.py` validates the requirements-to-check manifest
and executes fixed pytest/npm/Godot checks in an unauthenticated, offline sandbox.
`GitService` owns all merge, feature publication and tested-commit main-promotion
operations. Configuration opt-in authorizes the team workflow; Markdown cannot
expand its permissions. See [automatic integration](automatic-integration.md).
