# VirtualAgentCafe — Required skills and working rules

This document describes the capabilities a Codex development agent needs for the
project. It is a competency/tool checklist, not an automatically installable Codex
skill package. A dedicated `SKILL.md` package can be added separately if needed.

## Required skills

| Skill | Technology / tool | Required capability | Evidence |
| --- | --- | --- | --- |
| Repository work | Git, SSH, GitHub | Inspect status, feature branches, commits, pushes and conflicts | `git status`, `git remote -v`, `git ls-remote origin HEAD` |
| Python backend | Python 3.12+, FastAPI, Pydantic | Typed event API and asynchronous WebSocket server | `pytest` |
| Concurrency | `asyncio` | Nonblocking event bus, bounded queues, reconnect and backpressure | Unit/integration tests |
| Game development | Godot 4, GDScript | Scenes, nodes, tilemap, animations, HUD and navigation | Headless import/smoke test |
| Event protocols | JSON, WebSockets | Versionable schema, sequences, correlation and errors | Schema/E2E tests |
| Test automation | pytest, pytest-asyncio, httpx, Godot CLI | Reproducible unit, API, integration and smoke tests | `scripts/check.sh` |
| Containers | Docker/Podman Compose, Linux | Bind mounts, permissions, ports, builds and startup | `compose config`, container smoke test |
| CI/CD | GitHub Actions | Checks on push and pull request | Successful CI run |
| Documentation | Markdown | README, architecture, setup and troubleshooting | Startup using README alone |
| Security | SSH agent, secret handling | No keys in image/repository; least privilege | `.gitignore` and secret review |

## Optional skills

- **Pixel art / 2D animation:** sprite sheets, simple placeholders, animation states and transitions.
- **Pathfinding:** Godot `NavigationAgent2D` when needed for the map.
- **Observability:** structured logs, event correlation and debug HUD.
- **Codex integration:** inspect event/tool interfaces available in the actual runtime and write adapters.
- **MCP:** consider only when file/editor automation and Godot CLI are insufficient; not required for the MVP.

## Container tools

The development container should provide at least:

```bash
python3 --version
node --version
npm --version
codex --version
godot --version
git --version
ssh -V
```

Python also needs `pytest`, `pytest-asyncio`, `httpx`, `fastapi`, `uvicorn`,
`websockets`, `pydantic` and `ruff`. Use a virtual environment or a properly
declared `pyproject.toml` installation.

## Git access from WSL / development container

1. Mount the WSL repository `/mnt/f/Workspace/VirtualAgentCafe` at `/workspace`.
2. Start an SSH agent in WSL and load an existing key:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
ssh-add -l
```

3. Register the public key `~/.ssh/id_ed25519.pub` as a write-enabled repository deploy key. Never upload the private key.
4. Use SSH remote `git@github.com:St3fanTh/VirtualAgentCafe.git`.
5. Check WSL access with `ssh -T git@github.com` and `git ls-remote origin HEAD`.
6. Configure SSH agent forwarding into the container; do not mount private keys. The socket mount depends on Docker Desktop/WSL integration versus native Docker/Podman. Explicitly test socket access and `known_hosts` in the container.
7. Give the agent identity only necessary privileges. Push to a feature branch.

Access to the SSH agent socket permits authentication with loaded keys. Prefer a
dedicated deploy key restricted to this repository for an automated agent.

## Required testing strategy

### Unit tests

- Event models accept valid payloads and reject invalid ones.
- Agent state machines map event types correctly.
- Sequence numbers and duplicates are handled deliberately.
- Queue limits prevent unbounded memory growth.

### API / WebSocket tests

- `/health` returns success.
- `/agents` returns current state.
- WebSocket events arrive in order.
- Disconnect and reconnect are handled.
- Oversized events are rejected.

### Godot tests

```bash
godot --headless --path game --editor --quit
godot --headless --path game --quit-after 120
```

- Automate state-mapping tests as well.
- Visually inspect two characters, movement, animations, speech bubbles and offline status in the Windows Godot editor.

### End-to-end test

- The demo simulator starts two agents.
- The backend distributes events.
- A test WebSocket client receives at least `agent.coding`, `agent.testing`, `agent.message` and `agent.finished`.
- No real LLM API keys are needed.

## Autonomous work rules

1. Inspect the project structure and existing files before changing them.
2. Make small changes and test each milestone.
3. Commit after passing tests; push to the feature branch with prior authorization.
4. No force-pushes, automatic merges or credential changes.
5. Do not hide failing tests; fix or document them.
6. Report test results, commit and push status after each milestone.
7. Without graphics/editor integration, use reproducible headless checks. Do not claim visual quality without inspection.

## Recommended learning and implementation order

Git/SSH and containers → Python event models → FastAPI/WebSockets → pytest →
Godot/GDScript → Godot headless → integration → CI → real Codex adapter → optional MCP.
