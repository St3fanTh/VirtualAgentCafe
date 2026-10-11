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
