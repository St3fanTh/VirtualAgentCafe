# Codex sandbox in the development container

The current session can authenticate to Codex and complete textual model tasks,
but `unshare -Ur true` fails with `Operation not permitted`. Seccomp filtering is
active. Consequently file edits and shell tests in Codex's workspace-write sandbox
fail. Changing the container user to root alone may not resolve host-side filters.

At the user's request, `compose.privileged.yaml` provides an **explicit opt-in**
for a dedicated local development container. It sets privileged: true on both the
interactive codex service and the backend service. The default Compose file keeps
ordinary confinement. The image still uses non-root node, and the application
still invokes Codex with workspace-write; no CLI sandbox bypass is added.

Privileged containers have broad host/device and kernel capabilities. This is a
local development choice, not a configuration for shared/public services. An outer
runtime or host policy can still block namespaces; successful rebuilding alone is
not proof of sandbox support.

## Rebuild the interactive development container (WSL host terminal)

First pull the pushed feature branch so the host has the new files. Stop the old
interactive session normally, then run:

```bash
git switch feat/virtual-agent-cafe-mvp
git pull --ff-only origin feat/virtual-agent-cafe-mvp
docker compose -f compose.yaml -f compose.privileged.yaml --profile dev run --rm --build codex bash
```

Inside the new container:

```bash
unshare -Ur true
codex login status
python3 scripts/codex_smoke.py
scripts/check.sh
```

If login is missing: `codex login --device-auth`. Authentication persists in the
named codex_home volume. Do not paste credentials into project files. A successful
unshare test is a prerequisite; the real smoke independently validates editing and
test execution. Then run `codex` to resume development in this repository.

## Run the live backend in its privileged container

```bash
VAC_MODE=codex docker compose -f compose.yaml -f compose.privileged.yaml up --build --force-recreate backend
```

Open game/project.godot in Windows Godot and run the game. The published port remains
127.0.0.1:8000. Final responses and generated files live in the runtime volume:

```bash
docker compose exec backend ls -la /workspace/.runtime/workspaces
docker compose cp backend:/workspace/.runtime/workspaces ./agent-results
```

To use normal container confinement again, omit compose.privileged.yaml and recreate
the service. Do not remove the named volumes; they contain login and task artifacts.

Alternative: run the Python backend directly in WSL with a functioning Codex sandbox.

References: [Docker seccomp](https://docs.docker.com/engine/security/seccomp/),
[Docker privileged containers](https://docs.docker.com/engine/containers/run/#runtime-privilege-and-linux-capabilities).
