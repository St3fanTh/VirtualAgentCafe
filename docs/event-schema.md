# Event protocol v1

WebSocket /ws/events sends JSON frames:

- `{ "kind": "snapshot", "version": 1, "sequence": 0, "agents": [...] }`
- `{ "kind": "event", "version": 1, "event": {...} }`

Each event has UUID event_id and correlation_id, agent_id (ada or turing), type,
UTC timestamp, consecutive global sequence and payload. Payload contains source
(demo/codex/system), bounded detail (256 characters), optional recipient (ada/turing).
Unknown fields, agents and event types are rejected. No raw prompts, commands,
reasoning or outputs are part of this public schema.

| Event | Presentation |
| --- | --- |
| agent.started | Starting / leaving waiting area |
| agent.thinking | Model turn active / thought indicator |
| agent.coding | File edit / programming desk |
| agent.testing | Observed test command / test station |
| agent.message | Message / conversation corner and speech bubble |
| agent.waiting | Waiting area / idle |
| agent.error | Error indication |
| agent.finished | Success celebration |

Clients discard duplicate/older sequences and reconnect on gaps. Snapshots always
replace state and reset the sequence baseline. A snapshot after overflow intentionally
skips intermediate animations. Status animations continue until the next observed event.

Snapshots additionally carry role: backend (Ada) or frontend (Turing). Activity
summaries identify test framework and exit result without publishing CLI arguments.
Peer delivery uses recipient and actual inbox/outbox evidence; model response events
without recipient are displayed as Response. agent.waiting represents Idle unless
detail starts CLI:, in which case a shell command is active. Completed tasks emit
Finished, then a system Waiting/Idle event when no CLI job is running.
