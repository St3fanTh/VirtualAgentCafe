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
3. Run `python3 scripts/setup-project.py --privileged --no-godot` once to configure
   the selected project and save the local Godot connection. This also works when
   Godot is launched later manually. See [project setup](project-setup.md).
4. Open `game/project.godot` in Godot 4.4.1, press F5, then **Manage agents**.
   The connection is loaded automatically; no token entry is needed. If necessary,
   **Connection settings** exposes manual authorization. An explicit
   `VAC_MANAGEMENT_TOKEN` environment variable takes precedence. Keep the local
   `.runtime/setup/godot-connection.json` private; never add it to Git.
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

## Delete an agent

Open **Manage agents → Agents**, select an agent and click **Delete agent**.
Confirm the dialog to remove its active configuration and café character. Cancel
(or Escape) leaves the agent unchanged. Stop running agents first; team deletion
also requires all team workers and integration to be stopped.

Deletion survives restart. It preserves workspace files, Git branches and commits,
Markdown tasks and roles, execution history and logs. The configuration is archived
internally. An affected team's automatic integration is disabled; explicitly run
project setup again to restore a complete team. The built-in demo agents cannot
be deleted. Deletion does not remove files or remote branches.

Authenticated API clients can use `DELETE /management/agents/{id}` with JSON
`{"confirmed": true}`. Missing confirmation is rejected; active execution blocks
deletion. The refreshed WebSocket snapshot removes the character in connected clients.

## Remove workspaces and delete Markdown tasks

In **Agents**, select the workspace or task and use **Remove selected workspace** or
**Delete selected task**. Both actions ask for confirmation. A workspace can only be
removed after agents and Git settings are reassigned. If it is the source of an
abandoned managed project whose agents have all been deleted, confirmation also
archives that project registration. Existing project members or running integration
block removal; the button tooltip names known blockers. Removing it unregisters the workspace from VirtualAgentCafe; its
folder, files, repository and branches stay on disk. To make it available again, add
the workspace through **Workspaces**.

A task can only be deleted after every agent has been unassigned from it and its
configuration saved. Deleting it permanently removes the Markdown file. Existing
execution history remains available. Select the task in the agent form even when it
is not currently assigned; the delete request checks persisted assignments on the
backend, so an unsaved selection cannot bypass that guard.

Authenticated API clients can call `DELETE /management/workspaces/{id}` or
`DELETE /management/definitions/tasks/{filename}` with JSON `{"confirmed": true}`.
The API rejects missing confirmation, path traversal, and resources still referenced
by existing agents or projects with existing members or running integration.

## Inspect an agent's Git changes

Select the agent in **Agents**, then open **Workspaces**. Agent selection also
selects its assigned workspace for Git inspection. You can still choose another
workspace explicitly. Use the current worker worktree, not a disconnected project
folder from an older setup. **View diff** shows tracked changes against HEAD;
committed results appear in **Inspect repository** history instead. Errors replace
stale results in the Git panel and identify the requested workspace.

### Testfehler und Abschlussbericht lesen

Unter **Executions** den gewünschten Lauf auswählen und **Changelog & tests** öffnen.
Der Bericht zeigt das Laufzeitergebnis, vom Controller bestätigte Veröffentlichung
(Branch und Commit), beobachtete Testläufe und den Abschlussbericht des Agenten.
Der scrollbare Bericht ersetzt die früher auf 1.400 Zeichen gekürzte Statusanzeige.
Der Agentenbericht ist auf 6.000 Zeichen begrenzt und bleibt mit der Ausführung
in der Datenbank gespeichert, auch ohne aktivierten Push. Bei Veröffentlichung
bleibt zusätzlich `agent-changelogs/<agent-id>.md` im Repository verfügbar.

Neue Codex-Läufe speichern bis zu 100 Testaufrufe des letzten Laufzeitversuchs:
Werkzeug, Exit-Code, erkannte Fehlerklassen und bis zu 20 pytest-Testbezeichner.
Beispiel: `pytest (exit 2)` bedeutet einen unterbrochenen Testlauf, häufig durch
Sammlungs-/Importfehler; ein zusätzlich erkanntes `ModuleNotFoundError` weist auf
eine fehlende Abhängigkeit oder einen fehlerhaften Importpfad hin. Exit 5 bedeutet,
dass keine Tests gefunden wurden. Frühere fehlgeschlagene Aufrufe bleiben auch nach
erfolgreicher Wiederholung im Bericht sichtbar.

Kommandoargumente, Parameterwerte, Assertionsinhalte und vollständige Tool-Ausgaben
werden nicht veröffentlicht. Unbekannte Fehler erfordern weiterhin einen Blick in
die Testausgabe im Workspace; ältere Ausführungen erhalten keine rückwirkend
erfundenen Testdetails. Der Changelog ist der Bericht des Modells, kein Nachweis
für einen Push oder erfüllte Anforderungen: dafür gelten die separat angezeigten
Controller-Ergebnisse und die gemeinsame Requirements-Validierung.

### Falschen Projektordner aus dem Setup entfernen

Unter **Setup** den falschen Eintrag in **Approved Git project** auswählen und
**Remove folder from setup** bestätigen. Das funktioniert auch vor einem
 erfolgreichen **Check project**, ohne angelegtes Team. Die Workspace-Registrierung
wird entfernt und der Ordner dauerhaft aus der Setup-Suche ausgeblendet; Dateien,
Git-Daten und Docker-Mounts bleiben unverändert. **Find projects** und Backend-
Neustarts blenden ihn nicht wieder ein. **Restore removed folders** stellt die
entfernten Ordner in der Suche wieder her.

Ein zugeordnetes Team zuerst mit **Delete selected project** entfernen; bei einzeln
zugeordneten Agenten deren Workspace ändern oder die Agenten löschen. Laufende
Arbeit bleibt geschützt. Einen anderen Host-Ordner weiterhin über
`scripts/setup-project.py` auswählen und mounten.

### Team nach dem Löschen erneut anlegen

Das Setup verwendet vorhandene Markdown-Aufgaben und Rollen für dieselben
Agenten-IDs erneut, auch für Integration & Tests. Nicht mehr zugeordnete Dateien können nach dem
Löschen eines Teams erhalten bleiben. Die frühere Meldung „Team Markdown already
exists“ blockiert die Wiederanlage nicht mehr. Vorhandene Inhalte werden validiert
und niemals durch die Vorlagen oder ein neues Setup-Ziel überschrieben. Vor dem
Start unter Agents/Markdown prüfen, ob die Aufgaben noch zum aktuellen Ziel passen.
Ungültige Markdown-Dateien müssen dort korrigiert werden. Nichtleere fremde
Arbeitsverzeichnisse und bereits belegte Agenten-IDs bleiben geschützt.

### Vorhandene Worktrees bei erneuter Einrichtung

Setup kann vorhandene Backend-, Frontend- und Integrations-Worktrees wiederverwenden,
wenn sie zum ausgewählten Repository und zum erwarteten Agentenbranch gehören.
Uncommittete Dateien bleiben erhalten. Fremde Repositories, andere Branches und
Ordner ohne gültige Worktree-Verknüpfung werden weiterhin abgelehnt.

Beim Löschen eines verwalteten Projekts werden auch fehlende Worker-Verzeichnisse
behandelt. Die Bereinigung entfernt nur veraltete, ungesperrte Git-Registrierungen
für die betroffenen Workspaces. Andere Worktree-Registrierungen und Agentenbranches
bleiben erhalten; es findet kein pauschales Prune mit unvollständiger Mount-Sicht
statt. Das Entfernen eines Ordners nur aus der Setup-Auswahl löscht weiterhin
keine Arbeitsdateien.

## Modell pro Agent auswählen

Unter **Management → Agents** einen Agenten auswählen, im Dropdown **Model (next
execution)** das Modell wählen und **Save configuration** drücken. Die Auswahl
wird je Agent gespeichert und gilt ab dem nächsten Start, auch für Chat-Folgeläufe
und Integrationsreparaturen. Laufende Ausführungen behalten ihren bisherigen Start-
Snapshot. Agentenliste und Detailansicht zeigen die konfigurierte Auswahl;
**Executions → Changelog & tests → Requested model** zeigt die Auswahl dieses Laufs.

**Codex default (automatic)** entspricht `model: null`: Es wird kein Modellflag
übergeben. Das erhält das bisherige Verhalten; es behauptet keinen konkreten
aufgelösten Modellnamen. Die isolierte Runtime übernimmt weiterhin keine privaten
Codex-Konfigurationsdateien vom Host. Eine konkrete Auswahl setzt `--model <ID>`.

Die authentifizierte API `GET /management/models` liest den Modellkatalog über
`codex debug models`. Bei Fehler/Timeout wird der mit der CLI ausgelieferte Katalog
(`--bundled`) versucht und als solcher gekennzeichnet. **Refresh models** erzwingt
über `?refresh=true` eine neue Abfrage; normale Aufrufe werden 60 Sekunden gecacht.
Es werden keine Agenten gestartet. Zugang zu einem Katalogmodell ist nicht für
jedes Konto garantiert. Bei fehlendem Katalog bleiben gespeicherte Auswahlen
sichtbar; sie werden nicht stillschweigend ersetzt. Nicht unterstützte Modell-IDs
führen zu einem Codex-Fehler statt zu einem automatischen Modellwechsel.

Konfigurationsausschnitt (Modell-ID aus dem Dropdown übernehmen):

```json
{"provider": "codex", "model": "gpt-6.1-sol"}
```

Die Umsetzung verwendet die dokumentierten Flags für
[Codex-Modellauswahl und Modellkatalog](https://learn.chatgpt.com/docs/cli/reference).
Der Katalogexport wird begrenzt gelesen; nur validierte, sichtbare Modell-IDs werden
an die GUI weitergegeben, keine Modellinstruktionen oder privaten Diagnoseausgaben.
