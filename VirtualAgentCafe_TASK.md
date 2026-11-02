# VirtualAgentCafe — Development task for Codex

> **Role:** Lead software engineer for an event-driven 2D game displaying real activities of multiple AI agents. Read `AGENTS.md` and `SKILLS.md` first, if present. Implement incrementally; never claim to have run tests you did not run.

## Context

- WSL host repository: `/mnt/f/Workspace/VirtualAgentCafe`
- Development container repository: `/workspace`
- Git remote: `git@github.com:St3fanTh/VirtualAgentCafe.git` (the user must configure SSH access first).
- The Godot editor can run on Windows; Godot CLI runs headless inside the container.
- Goal: an observer world, not a simulation claiming access to private LLM thoughts.

## MVP vision

A small, working pixel-art café with two agent avatars. Observable model calls,
file edits, tests, messages, waiting and completion update each character's position,
animation, status and speech bubble. Start with a deterministic demo simulator,
then add an adapter for real agent events.

## Technology

- **Python 3.12+**: FastAPI, Pydantic, asynchronous WebSockets, event bus, simulator and adapters.
- **Godot 4.x / GDScript**: tilemap, characters, animations, pathfinding, HUD and WebSocket client.
- **pytest + pytest-asyncio + httpx**: unit, API, integration and smoke tests.
- **Godot Headless CLI**: project import and runtime tests; additional GDScript tests with a small runner, or a maintained framework only if reliably installable.
- **Ruff** for Python formatting/linting; **GitHub Actions** for CI.
- Unity, React, TypeScript, MCP and external LLM access are not required for the MVP.

## Desired layout (respect the existing structure)

```text
VirtualAgentCafe/
├── AGENTS.md
├── TASK.md
├── SKILLS.md
├── README.md
├── compose.yaml
├── Dockerfile
├── .gitignore
├── backend/
│   ├── pyproject.toml
│   ├── virtual_agent_cafe/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── bus.py
│   │   ├── simulator.py
│   │   └── adapters/
│   └── tests/
├── game/
│   ├── project.godot
│   ├── scenes/
│   ├── scripts/
│   ├── assets/
│   └── tests/
├── scripts/
│   ├── check.sh
│   └── demo.sh
├── docs/
│   ├── architecture.md
│   └── event-schema.md
└── .github/workflows/ci.yml
```

## Requirements

1. Backend endpoints `GET /health`, `GET /agents`, `WS /ws/events`; optional event ingestion must be local and validated.
2. Typed events with `event_id`, `agent_id`, `type`, `timestamp`, `sequence`, `correlation_id`, `payload`. Types: `agent.started`, `agent.thinking`, `agent.coding`, `agent.testing`, `agent.message`, `agent.waiting`, `agent.error`, `agent.finished`.
3. A two-agent demo simulator with reproducible events and configurable speed, requiring no API key.
4. A Godot world with two characters, desks, test station, conversation area, status displays and speech bubbles.
5. Event-to-animation mapping; visual characters may catch up but must never block backend events.
6. WebSocket reconnect with backoff, bounded queues, a reconnect snapshot and visible offline indicator.
7. No logging of secrets, private prompts or full tool output by default. Validate and bound input sizes.
8. Runnable README instructions for WSL, Compose and Windows Godot; document port exposure on `127.0.0.1` only.
9. Optional real Codex adapter only after a stable MVP, using available/captured runtime events without invented thoughts.

## Milestones and acceptance criteria

### M0 — Inventory

- Check `pwd`, `git status`, `git remote -v`, branch and tool versions.
- Read existing files and plan changes; never overwrite blindly.
- Check whether pushing is possible without forcing a test push.

### M1 — Backend and tests

- Implement event models, bus, API and simulator.
- Test event validation, transitions, ordering, queue limits, `/health`, `/agents`, WebSocket delivery and invalid payloads.

### M2 — Godot world

- Main scene, two agents, HUD, animations and network client.
- Test import, headless startup and event-to-state mapping; show the demo in the editor.

### M3 — Integration and CI

- `scripts/demo.sh` starts the backend and simulator reproducibly.
- `scripts/check.sh` runs Ruff, pytest and Godot headless checks, returning nonzero on failure.
- E2E smoke test: simulator → WebSocket → expected events.
- GitHub Actions runs the same checks on pushes and PRs.

### M4 — Real agent activity

- Implement the adapter interface, then connect events actually available in the selected Codex runtime.
- An inter-agent message produces a speech bubble and conversation animation; “thinking” means only an active model call.

### M5 — Polish

- Improve pixel art, smooth animation changes, visualize errors and test performance.

## Git rules

- The original task named `feat/agent-cafe-mvp`; current `AGENTS.md` and user instructions override this with `feat/virtual-agent-cafe-mvp`. Never develop directly on `main`.
- Before every commit: `git status`, `git diff --check` and relevant tests. Never stage secrets.
- Use small Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`).
- Push each fully tested milestone when authorized and SSH authentication works. No force-push, automatic merge or overwriting others' changes.
- Do not change SSH keys, credentials, remote URLs or branch protection without asking.
- Report push failures; never bypass protections.
- `AGENTS.md` and this file are not schedulers; scheduled runs require separate orchestration.

## Definition of done

- A fresh checkout can be installed and tested with documented commands.
- Demo mode shows two characters, transitions and at least one message.
- Backend/Godot checks pass, CI runs and README is current.
- Each milestone reports changed files, test commands/results, commit hash, push status and open issues.

## Original starting instruction

Begin with M0, present a short implementation plan, then complete M1. Do not skip tests or invent results.
