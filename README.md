# VirtualAgentCafe

A Godot 4 pixel café that shows observable activity from two agents. Click Ada or
Turing to give a task to Codex. Animation state follows backend events, never a
random timer. Demo mode is deterministic and clearly marked **DEMO (simulated)**.
Live mode shows **CODEX (live)**. No private reasoning is exposed.

## Graphics

The café now uses a **1920×1280** reference canvas, sharper labels and a larger
styled task panel. Warm lighting, reflective windows, subtle wooden flooring and
illuminated monitors use four Compatibility shaders. The **Atmosphere** button
lets you toggle effects. [Rendering details and preview](docs/graphics.md).

## Local setup (WSL/Linux)

Requirements: Python **3.12+**, Godot **4.4.1**, Git; Codex CLI for live mode.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.lock
python -m pip install --no-deps -e backend
scripts/check.sh
scripts/demo.sh demo
```

In a second terminal:

```bash
godot --path game
```

`VAC_DEMO_INTERVAL=0.25 scripts/demo.sh demo` speeds up the demo. It loops through
start, thinking, coding, tests, communication and completion for both characters.
`GET http://127.0.0.1:8000/health` reports mode; `/agents` is a current snapshot.
`VAC_PORT=8001` changes the backend port; set `VAC_BACKEND_URL=http://127.0.0.1:8001`
for the Godot process. Native Godot clients are supported; browser exports are not.

## WSL + Compose + Windows Godot

Run Compose from the repository in WSL with Docker Desktop WSL integration enabled:

```bash
docker compose up --build backend
```

Open `game/project.godot` with Godot 4.4.1 on Windows, then press **F5** to run.
The demo shows Ada and Turing working, testing, messaging and finishing. Click a
character to open the task panel; submitting real tasks requires Codex mode.
Windows reaches the forwarded backend at `127.0.0.1:8000`. Only loopback is published;
the backend binds 0.0.0.0 **inside** its container. Do not publish it to the LAN.
Project files are mounted with `.:/workspace`; no host-specific drive path required.
The named `runtime` volume keeps agent workspaces writable inside the container.

## Live Codex tasks

Install Codex CLI 0.162.1 and log in, then start live mode:

```bash
codex login
scripts/demo.sh codex
```

Click an agent, enter a task and choose **Run with Codex**. Each agent works in its
own persistent Git directory under `.runtime/workspaces/`; the two can work in
parallel. **Cancel running task** terminates its process group. **Message other
agent** sends the text as an explicit public message when both agents are idle.
Task prompts and raw model/tool responses stay private; results are workspace files.
The final response is saved to `.cafe/last-response.md` within that workspace; the
game shows its path. With Compose, inspect it via `docker compose exec backend`
or copy results to the host with `docker compose cp backend:/workspace/.runtime/workspaces ./agent-results`.
The sandbox must support Linux user namespaces. The opt-in privileged development
configuration was verified with a real Codex edit/test smoke run. Check your own
runtime with `unshare -Ur true` and `scripts/codex-smoke.sh`.
See [Codex adapter](docs/codex-adapter.md) for exact event mapping and limits.
For the requested opt-in privileged container rebuild, see
[container sandbox setup](docs/container-sandbox.md).

## Git and credentials

Use `feat/virtual-agent-cafe-mvp`. Private keys and `.env` files are excluded from
Git and Docker builds. No SSH key is copied into the image. The optional
`compose.ssh.yaml` forwards an existing host agent and known_hosts to the dev
service; it does not change keys or credentials:

```bash
docker compose -f compose.yaml -f compose.ssh.yaml --profile dev run --rm codex
```

Ensure your SSH agent is running and `SSH_AUTH_SOCK` exists. Codex login data lives
in `codex_home`, never in the repository. Do not commit `.runtime`, login files or
raw JSONL traces. A private key was present in the original local Docker context;
it remains local and is excluded from both Git and builds.

## Tests and development

Project shell entrypoints select the local `.venv` or the container's `/opt/venv`
and import the current mounted backend source, so a pull takes effect without a
stale image-installed package. `scripts/codex-smoke.sh` validates a real Codex run.

`scripts/check.sh` runs Ruff, pytest, Godot import, all state mappings, a headless
launch and a live Uvicorn→WebSocket→Godot smoke test on a temporary port. It fails
on Godot parse/runtime errors even when Godot returns exit code zero. CI runs the
same checks plus Compose validation and a container health smoke test. Live LLM
calls are opt-in, not part of ordinary tests. No API key is needed for demo/tests.

Architecture: [docs/architecture.md](docs/architecture.md).
Protocol: [docs/event-schema.md](docs/event-schema.md).
Milestone evidence: [PROGRESS.md](PROGRESS.md).

## Troubleshooting

- **Offline:** start the backend, check `/health` and port; the game retries with
  exponential backoff and refreshes authoritative state after reconnect.
- **Missing Python:** install Python 3.12+ (or use Compose); the original running
  dev container may still contain Python 3.11 until rebuilt.
- **Missing Godot:** install the Linux headless-compatible binary for local checks;
  the Windows editor alone does not satisfy `scripts/check.sh` in WSL.
- **No Docker daemon:** enable Docker Desktop integration with your WSL distro.
- **Visual validation:** headless tests validate behavior; inspect layout, movement
  and bubbles in the Windows editor before declaring visual acceptance.

MVP state is in memory and resets on restart. Run one backend worker. Current
snapshots recover state; transient animation history is deliberately bounded.
