# Backend and frontend agents

**Ada = backend**, **Turing = frontend**. Roles are included in `/agents` snapshots,
job metadata and the actual prompt sent to Codex. Each has its own persistent Git
workspace; the model is asked to implement its assigned task, use file-edit tools
and run relevant tests. Role colors, desks, avatar captions and activity cards agree.

## Observed actions

- **Coding:** public CLI file-change items and observed code-file writes through shell tools,
  including a safe change count; keyboard animation. Cache and helper files excluded.
- **CLI tests:** parsed test invocation, framework name, RUNNING and PASS/FAIL + exit code;
  test-station animation. Arguments, raw commands and outputs stay private.
- **CLI command:** other actual shell commands; distinct from Idle.
- **Communication:** an explicitly public peer message was delivered; conversation corner,
  speech bubble and events for both sender and recipient.
- **Response:** a model message with no peer recipient; not claimed as peer dialogue.
- **Idle:** no running task, initially or after a completed task's 3-second celebration.
  It is an actual backend state transition, not a random animation.

The cards show current authoritative state and up to five recent observed entries.
On reconnect, history starts from the snapshot rather than inventing lost events.
Avatars can briefly lag behind while presenting short observed states.

## Real peer exchange

Every task workspace receives a standard-library helper:

```bash
python3 .cafe/send_message.py turing 'API contract: GET /health returns status ok'
```

The backend watches the local outbox (works without network in the Codex sandbox),
validates task/message UUIDs, recipient and text limit, and delivers the message to
`.cafe/inbox.jsonl`. Explicit public text is shown; private model responses are not.
A reply task that publishes no public reply fails explicitly rather than claiming
an exchange took place. A request starts one Codex reply task on the other agent. If busy, the recipient
queues it (up to four requests). That helper defaults to reply mode, so the reply
cannot recursively start another conversation. A manually generated reply can use
`--reply`. At most four outbox messages are processed per task. Inboxes keep 32
messages, outboxes are bounded/rotated at task boundaries; symlink escapes are rejected.

The native **Ask other agent** button sends an explicit public question and requests
one actual model reply. API clients can use:

```json
{"recipient": "turing", "text": "Which UI fields do you need?", "request_reply": true}
```

Without request_reply, `POST /agents/ada/messages` only delivers the public message.
This preserves the non-billable default for API consumers and ordinary tests. Each
requested model reply uses the current Codex account. Cancelling an agent clears
queued replies for it. Shutdown cancels running work and idle timers.

## Validation

`scripts/check.sh` uses an explicit adapter fixture to execute the real helper,
check delivery and a bounded reply, validate roles and verify idle transitions.
`scripts/collaboration-smoke.sh` is opt-in and invokes **two real Codex runs**. It
checks backend→frontend and frontend→backend delivery, actual inbox files and
successful job completion. It has been executed successfully, separately from CI.
