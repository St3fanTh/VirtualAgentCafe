# VirtualAgentCafe

VirtualAgentCafe displays real Codex agents as characters in a Godot café.
Backend and frontend agents work on your project in separate Git worktrees.
An integration agent combines their results and validates them before optional
publication to `main`. Animations follow actual runtime events such as coding,
testing, waiting and completion.

## Prerequisites

For normal use, you run **the Python setup script and Godot**. The script builds
and starts the backend through Docker Compose. Python packages, Codex CLI, Git
and the agents' test tools are installed inside the container.

| Requirement on your computer | Purpose |
| --- | --- |
| Linux or Windows with WSL2 | Run the setup script on the Linux/WSL host. |
| Python **3.10+** | Runs `scripts/setup-project.py`; no additional Python packages needed. |
| Docker with Compose V2 supporting `up --wait` | Builds and runs the backend. On Windows, start Docker Desktop and enable WSL integration. |
| Godot **4.4.1 Standard** | Opens the café interface. The Windows version works from WSL. |
| Git and a VirtualAgentCafe checkout | Downloads and updates this application. |
| A separate project with a real `.git` directory and at least one commit | The folder agents will develop; select the main repository, not an existing worktree or VirtualAgentCafe itself. |
| Codex access | The starter opens login inside the container when needed. Agents share this login; model usage may incur costs. |
| A Git remote and SSH write access, for publishing results | Your project's `origin` must point to its repository. The starter forwards a loaded SSH agent and verified `~/.ssh/known_hosts`. |

WSL uses Windows PowerShell for folder selection. On Linux, Python Tk with a
graphical session is optional; otherwise the script prompts for a path.
Agents require working Linux namespaces/Bubblewrap. The starter checks this.
For local environments that require extra container permissions, explicitly use
`--privileged`.

## Getting started

### 1. Download VirtualAgentCafe

In a Linux/WSL terminal:

```bash
git clone https://github.com/St3fanTh/VirtualAgentCafe.git
cd VirtualAgentCafe
```

For an existing checkout, save your changes before switching to and updating `main`:

```bash
git switch main
git pull --ff-only origin main
```

### 2. Prepare your project

You will select the main folder of your own Git project, for example
`/mnt/f/Workspace/SimulationWorld`. Put these files there:

- **AGENTS.md:** shared rules, architecture conventions and restrictions.
- **PLANNING.md:** objectives, next tasks and verifiable acceptance criteria.

The wizard can load and edit existing files and provides templates for missing
ones. Lowercase `agents.md` and `planning.md` are also recognized. Each project
Markdown file may contain up to **64 KiB UTF-8**; a heading is optional.
Commit your intended starting point: new worktrees start at `HEAD`; uncommitted
files are not copied automatically.

For publishing, load your existing SSH key into your SSH agent and verify Git
access on the host. Register the public key with your Git provider. Keep private
keys out of the GUI and repository. See [Git access and setup](docs/project-setup.md).

### 3. Run setup and select the project folder

Run this from the **VirtualAgentCafe directory on the host**, not inside the container:

```bash
python3 scripts/setup-project.py --publish-results
```

Select your project containing `.git` in the folder dialog. The starter:

1. Mounts that project folder and uses its Git repository.
2. Builds/starts the backend and checks the sandbox.
3. Opens Codex login if needed and persists it in the container volume.
4. Saves the local Godot connection without requiring you to enter a token.
5. Launches Godot if `godot` or `godot4` is available on PATH.

`--publish-results` enables remote Git for later publication. Setup alone does not
start agents, push or merge. Without it, local development is available; the
automatic workflow through remote `main` requires remote access to be enabled.

You can specify Windows Godot explicitly:

```bash
python3 scripts/setup-project.py --publish-results \
  --godot '/mnt/c/Tools/Godot/Godot_v4.4.1-stable_win64.exe'
```

If your local environment needs the namespace override, add `--privileged`:

```bash
python3 scripts/setup-project.py --publish-results --privileged
```

Alternatively, open **`game/project.godot`** from this checkout in Godot and press
**F5**. F5 is unnecessary when the starter launches the game directly.
Use `--no-godot` to start only the backend or `--login` to reopen login.

### 4. Set up the team in the café

1. Open **Manage agents → Setup project** and select the mounted project.
2. Click **Load project documents**. Review `AGENTS.md` and `PLANNING.md`;
   **Import Markdown file** selects additional local content.
   **Save project document** saves changes in the project folder.
3. Describe the objective or use the loaded plan. Run **Check project** and
   resolve any **FIX** messages.
4. For the complete workflow, enable **Push successful results to each agent's own Git branch**
   and **Integrate + requirements tests + promote green result to main**.
5. Click **Create backend + frontend team**. Enabling integration also creates
   the integration/test agent. Creating the team does not start model tasks.
6. Under **Agents**, optionally choose each agent's **Model** and click
   **Save configuration**. Then use **Start agent** for the backend and frontend workers.

## Workflow

### Develop → integrate → test → publish

1. **Backend and frontend work in parallel.** Each agent has its own worktree,
   task, roles and branch. The café and Live Logs show progress and actual CLI tests.
2. **Successful workers publish to their agent branches.** `Done`/`Completed`
   does not mean the combined project is on `main`. Also check for **Pushed**.
3. **The integrator starts automatically** when team automation is enabled and
   both required worker results have been published. It merges their exact commits
   on an integration branch and creates or updates shared requirements tests.
4. **The controller validates the submitted revision.** Only after successful
   shared validation can the tested commit reach remote `main`, without force-push.
   Failures block promotion. Passing tests still do not replace your product review.
5. **Review the result.** **Executions** contains reports, tests and changelogs;
   Git views show branches, commits and diffs. Agent recaps also live in
   `agent-changelogs/` in the result repository. Run `git pull --ff-only origin main`
   in your local target-project checkout before testing. The controller does not
   overwrite your source checkout automatically.

See [automatic integration](docs/automatic-integration.md) for the complete rules
and [controller validation](docs/controller-validation.md) for diagnostic and acceptance states.

### Requirement changelog

Click **Changelog** beside **Manage agents** in the café toolbar. Select an agent
on the left to see its saved execution recaps, newest first. Each entry separates
requirement IDs such as **1.1** from the implementation description and shows the
branch/commit plus controller validation, publication and integration status.
The view refreshes automatically while open and preserves selection/scroll position.

Use explicit IDs in your task or PLANNING.md, for example:

```markdown
## Requirement 1.1 — Login form
Implement validation and display API errors.
## Requirement 1.2 — Authentication endpoint
Implement the endpoint and cover invalid credentials with tests.
```

New worker instructions request a final recap under those same IDs, including
implemented changes, files, tests and remaining work. These descriptions are
**agent-reported**, not automatic acceptance. Older unstructured recaps remain
available as general summaries; the UI does not invent requirement mappings.
Question-only chat messages do not become changelog entries. Reports use the
existing persistent execution storage and private management authentication.

### When an agent needs help

Integration failures receive a bounded number of automatic repair attempts.
Repeated failure or an exhausted budget pauses the team as **NEEDS_INPUT**.
**Manage agents → Agent chat** provides two separate actions:

- **Ask question:** for example, “Where is the startup script?” The agent reads
  the project through a read-only mount and answers without starting development
  or integration. Its existing work status is preserved.
- **Send instruction & continue:** for example, “Fix this test using this requirement.”
  Resumes work and may subsequently trigger team integration. Instructions saved
  during an active task apply to the next attempt.

Answers appear in chat; active work also has Live Logs and execution reports.
**Retry team integration** requests another integration attempt. For a requirements
blocker, provide a concrete instruction first. Questions and work instructions
use the configured model.

### Recover a Godot socket-blocked worker

If a completed worker is blocked by Godot `_sock == -1`, select it under
**Manage agents** and click **Retry validation**. The controller checks the saved
commit in an isolated environment with private loopback, without another model
turn. Keep the worker/workspace and committed files intact. A changed commit or
dirty workspace must be handled as a new agent run.

New eligible runs are rechecked automatically. Only clean controller results clear
the blocker; real script/runtime errors and unrelated failures remain blocking.
Configured worker publication and automatic team integration then continue normally.
Inspect **Executions → Changelog & tests → Controller worker recheck** for evidence.
This does not waive shared requirements tests or manual desktop acceptance.

### Start the next round after reviewing

Keep the agents and worktrees; no new team or setup is needed:

1. Select the existing project in **Setup project** and click **Load project documents**.
2. Enter new requirements and acceptance criteria under **NEXT ITERATION**.
3. Click **Start next iteration**.

The controller merges current remote `main` into clean worker branches, appends
the plan and starts both workers. Integration, shared tests and authorized main
publication follow. Editing `PLANNING.md` alone does not start a round. For changes
made on GitHub, update the local project folder and reload documents first.

## Restart, connection and troubleshooting

- **After updating VirtualAgentCafe:** run `git pull --ff-only origin main` in
  its checkout, rerun the starter with the same required options and reopen Godot.
  Select the same real project folder.
- **Connection settings:** manual backend address/authentication for special cases.
  Normal setup loads settings automatically; **Connect / Refresh** reloads them.
  A locally stored token continues to protect the API.
- **No visible git project:** rerun the starter on the host and select the main
  folder containing `.git`. **Find projects** searches approved mounts only; it
  cannot mount arbitrary host directories.
- **Namespace sandbox unavailable:** follow the starter's diagnostics; use
  `--privileged` when required for your local environment. Isolation remains mandatory.
- **Missing Codex login:** rerun the starter with `--login`.
- **Git push failed:** the remote and SSH access must also be available to the
  backend. Run the starter in a terminal with a loaded SSH agent and `known_hosts`.
- **Port reachable but no café page:** the interface is a native Godot application.
  `http://127.0.0.1:8000/health` is a backend health check only.
- **Keep your data:** configuration, history and worktrees persist. Keep `.runtime`
  and Docker volumes if you want to continue working.

The backend listens locally on `127.0.0.1:8000`. Use one backend process for
management; browser exports are unsupported. Keep credentials, tokens and
`.runtime` out of Git.

## Developing and testing VirtualAgentCafe

Normal use does not require a local backend installation. Contributors also need
Python **3.12+**, packages from `backend/requirements.lock`, Linux Godot and
Bubblewrap with working namespaces.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.lock
python -m pip install --no-deps -e backend
scripts/check.sh
```

Checks cover Ruff, pytest including API/Git/sandbox/GUI tests, Godot import,
state tests, headless startup and a live WebSocket smoke test. GitHub Actions
also checks rendered interfaces, Compose and container startup. Normal tests use
deterministic runtime fixtures and do not require paid model calls. A real Codex
smoke test is available separately through `scripts/codex-smoke.sh`.
`scripts/demo.sh demo` starts an explicitly simulated demo without Codex access.

## Further documentation

- [Detailed setup wizard](docs/project-setup.md)
- [Agent management, models and chat](docs/agent-management.md)
- [Automatic integration and requirements tests](docs/automatic-integration.md)
- [Controller validation, diagnostics and acceptance](docs/controller-validation.md)
- [Container sandbox](docs/container-sandbox.md)
- [Architecture](docs/architecture.md) and [event protocol](docs/event-schema.md)
- [Graphics and 4K rendering](docs/graphics.md)
- [Changes and test evidence](PROGRESS.md)
