# VirtualAgentCafe — Progress

The historical entries through October 28 below are condensed English translations.
They preserve milestone outcomes, test evidence and limitations; the complete original
wording and file-level changes remain in Git history (before the English documentation
release). Historical constraints describe the application at that milestone, not
necessarily its current behavior. Commit subjects can be located with `git log --grep`.
Unless stated otherwise, “full check” means `scripts/check.sh`: Ruff/format, pytest,
Godot import/state/headless checks and the live WebSocket smoke test. Repeated
Starlette/httpx deprecation warnings were pre-existing, not test failures.

## Disabled deletion for orphaned projects — 2026-10-25

- Both UI and backend blocked every project source, even after all its agents were
  deleted. Confirmed removal now atomically archives orphaned registrations while
  preserving files, worktrees, branches and history, including missing source folders.
- Existing members, workspace/Git assignments and active integration remain protected;
  button tooltips identify blockers. No user-host data was changed during development.
- Files: `management/execution.py`, `test_agent_deletion.py`, `management.gd`,
  `test_gui_input.gd`, management guide and progress record.
- Full check: **174 pytest passed**, including restart/file-preservation/API guards
  and GUI button/tooltip tests. Commit subject: `remove orphaned project workspace registrations`.
- Next: confirm removal in the updated client.

## Remove stale workspace registrations — 2026-10-25

- Unused registrations can be removed even when their directory is missing;
  `Workspace is unavailable` previously prevented this cleanup. Assignment and path
  checks remain; only management records are removed.
- Files: `management/execution.py`, `test_agent_deletion.py`, progress record.
- Full check: **172 pytest passed**, covering HTTP deletion, refreshed overview and
  restart persistence. Commit: `allow unregistering missing workspace directories`.
- The three user-host entries were not inspected; saved assignments may still block removal.

## Delete projects after individual agent deletion — 2026-10-21

- Historical membership survived agent deletion, but project deletion required active
  registry entries and failed with “Management resource not found”. Active and archived
  members are now handled separately; archived configurations guide retained-worktree
  cleanup. Source repository, branches and history remain.
- Godot refreshes workspace lists even when agents were removed earlier.
- Files: `management/execution.py`, `test_project_deletion.py`, `management.gd`, progress.
- Six focused tests passed (zero/one/two archived members, restart and dirty-file guards).
  Full check: **171 pytest passed**. Commit: `delete projects after agents were archived`.
- Dirty worktrees and active executions still block cleanup; no user projects were deleted.

## M0 — Inventory and secure foundation

- SSH, remote access and a test push succeeded at `12b356acabd9dc1451240487de1eb7ccc75c5a60`.
  The user made main the default and removed the test branch, confirmed with ls-remote.
  Created `feat/virtual-agent-cafe-mvp` while preserving existing files.
- Read requirements, added TASK/SKILLS aliases and AGENTS instructions. Keys remain
  local and excluded from Git/Docker; Dockerfile no longer copies them. Switched
  the base to Debian Trixie for Python ≥3.12 and added Ruff.
- Files: AGENTS/TASK/SKILLS and original requirements, Dockerfile, Compose,
  entrypoint and ignore files. Godot 4.4.1 and Codex 0.162.1 available; initial
  Python 3.11 needed a separate 3.12 environment. No application tests applicable yet.
- No Docker daemon/CLI locally; container verification deferred. Commit **c42aac3**,
  `initialize secure project foundation`, pushed. A commit cannot contain its own hash.
- Next: typed event model, bounded bus, REST/WebSocket and simulator tests.

## M1 — Backend, events and demo

- Added immutable validated events, eight states, two agents, global sequences,
  duplicate guards, bounded fan-out, overflow/connect snapshots, health/agents/events
  endpoints and deterministic configurable simulator.
- Files: backend pyproject, models/bus/main/simulator, package initialization,
  `test_backend.py`, architecture and event-schema docs.
- Python 3.12.15: Ruff and **19 pytest passed**, including API/reconnect and simulator
  integration. Fixed test bus access to use the server loop via `portal.call`.
- Godot project followed in M2; Docker unavailable; upstream httpx warning remained.
  Commit **6c74e56**, `implement typed agent event backend`, pushed.

## M2 — Godot café and live connection

- Added procedural tilemap, characters, desks/test/conversation/waiting areas,
  eight event-driven animations, bubbles, HUD, offline display and task dialog.
  Real tasks are enabled only in Codex mode. Reconnect uses 0.5–15s backoff,
  bounded packets, snapshots, duplicate rejection and sequence-gap resync.
- Files: game project/scene/scripts, `test_states.gd`, `test_live.gd`, backend main.
- Ruff/**19 pytest**, import, 120-frame headless startup and state tests passed.
  Actual Uvicorn→WebSocket→Godot test passed, including selection and activity events.
  Fixed ASGI cancellation subscriber cleanup discovered during repeated tests.
- No display server/Docker; visual acceptance and Codex endpoint still pending.
  Commit **33b37f4**, `implement Godot cafe and event animations`, pushed.

## M3 — Reproducible integration and CI

- Added check/demo/live scripts, hashed dependency lock, GitHub Actions, healthcheck,
  safe Compose startup and optional SSH forwarding. Build installs backend; runtime
  volume keeps task areas writable without startup writes to source.
- Files: scripts, CI, requirements.lock, Dockerfile/Compose/SSH override, Ruff config,
  README and Codex adapter guide.
- Full check: **19 pytest passed**; standalone Compose CLI validated configuration.
  Docker build/health, live Codex and graphical checks were not yet locally available.
  Commit **0805673**, `add reproducible integration checks and CI`, pushed.

## M3 correction — Executable permissions in Git

- First CI failed with exit 126: the mount did not preserve chmod in the index.
  Set executable Git modes on check.sh, demo.sh and entrypoint.sh.
- Full check passed again (**19 pytest**). Files: those three modes and progress.
  Commit **d061319**, `preserve executable script permissions`, pushed.
- An authenticated real Codex turn started, but all shell tools failed at Bubblewrap
  namespaces and produced no files. No sandbox bypass was used.

## M4 — Codex adapter; live code acceptance initially blocked

- CI for d061319 passed including Docker build/health:
  https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/38177618970
- Added adapter interface, JSONL observer, stdin prompts, persistent agent Git areas,
  task/status/cancel API, bounded history, timeouts/process-group cleanup and correlated
  acknowledged peer messages. Godot can submit/cancel/message and show safe result paths.
- CLI pinned to 0.162.1. Public events exclude raw reasoning, commands, prompts/output;
  thinking denotes an observed model turn, coding a file change, testing a parsed test.
- Files: adapters, jobs/main/models, fixtures/tests, café/task tests, codex_smoke.py,
  Dockerfile and docs. Full check **50 pytest passed**; Godot→HTTP→CLI fixture→events
  task/edit/test/finish/message/cancel integration passed.
- Real Codex smoke failed because namespaces blocked tools; correctly emitted error,
  never finished. Requested a sandbox-capable environment; no claim of live code success.
  Commit **f30069f**, `integrate Codex tasks and observed runtime events`, pushed.
- Next: presentation/load/reconnect while awaiting environment repair.

## M5 — Presentation, load and recovery

- f30069f CI passed: https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/38177963295
- Added bounded visual queue (16 states/character, 0.65s minimum display), independent
  HUD/backend and immediate snapshot replacement. Actual model reply persists privately
  in `.cafe/last-response.md`; no raw reply in public events.
- A real text-only Codex task and saved response passed independent verification;
  this did not establish code/tool acceptance while namespaces remained blocked.
- Full check **52 pytest passed**, including 5,000-event/four-queue load, real backend
  restart/Godot reconnect, visual duration/queue/resync and task/message/cancel E2E.
- Added user-requested explicit `compose.privileged.yaml`; defaults, non-root user
  and workspace-write remain. Parsed Compose; no local Docker daemon or host changes.
- Files: character/café/state/reconnect tests, backend/reconnect tests, adapter/jobs,
  Compose override and architecture/Codex/container docs. Commit **fe19dd3**,
  `polish event presentation and container sandbox setup`, pushed; its CI passed.
- Next: recreate user container, run unshare/real smoke and inspect Windows visuals.

## M4 live correction — Helper commands as warnings

- The user's privileged container could now edit/run tests. Adapter incorrectly
  made every failed helper command permanently fatal (e.g. search exit 1 in an empty
  directory). Such warnings now permit completed turns; failing tests/file changes,
  runtime and sandbox errors still block success. Expanded bwrap detection and
  per-turn completion; failure categories are explicit.
- Files: Codex adapter/tests, guide and progress. Full check **59 pytest passed**,
  including seven regressions for helper-warning recovery and genuinely blocking errors.
  SSH/remote rechecked; credentials unchanged.
- Local environment was still nonprivileged at this step; no successful code smoke
  claimed. User rerun command: `PYTHONPATH=/workspace/backend python3 scripts/codex_smoke.py`.
  Commit **28a1be9**, `allow completed Codex turns after helper command warnings`.

## Live acceptance — Actual Codex edits and tests pass

- After user restart, `unshare -Ur true`, SSH authentication and ls-remote passed.
  Ran `PYTHONPATH=/workspace/backend /opt/venv/bin/python scripts/codex_smoke.py`
  against authenticated Codex 0.162.1: **Real Codex smoke PASS**. Generated
  greeting.py/test_greeting.py and independently reran unittest successfully.
  Workspace-write remained enabled; no CLI sandbox bypass.
- Fixed shell choosing system Python without Pydantic: environment.sh selects usable
  local/container venv and current source; check/demo/codex-smoke scripts share it.
- Files: environment/codex-smoke/check/demo scripts, README and Codex/container docs.
  Full check on Python 3.13.5 **59 pytest passed**, with Godot/task/message/cancel/reconnect.
- Commit: `validate live Codex execution and select project environment`.
  Windows visual inspection and this completion commit's CI were next steps.

## Graphics milestone — Higher resolution and atmospheric shaders

- Added 1920×1280 canvas/1440×960 window, larger text and improved task-dialog
  spacing/contrast/focus. Four Compatibility shaders: wood, window skyline/rain,
  monitor scanlines and warm lighting/vignette; Atmosphere toggle. State-driven monitors,
  input-transparent effects and richer furniture/shadows kept event flow intact.
- Files: game project/world/café/character, shaders, render preview, CI, graphics docs,
  README and preview PNG. Existing scene UID changes remained unstaged.
- Full check **59 pytest passed**. Actual Mesa llvmpipe/Xvfb OpenGL previews with/without
  effects/dialog were rendered and inspected; corrected coarse floor and overlapping labels.
  Temporary display libraries stayed under /tmp; no host policy changes. No shader/script
  errors; virtual VSync warnings harmless. Windows GPU performance not measured.
- Commit **b69b353**, `enhance cafe resolution and atmospheric shaders`, pushed.
  CI including screenshots/Compose/container passed:
  https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/38303574178
- Next: restart Godot/F5 and compare Atmosphere; no backend rebuild needed for graphics alone.

## Roles/activity milestone — Real backend/frontend collaboration

- Ada Backend/Turing Frontend roles now enter snapshots/jobs/prompts. Safe CLI framework,
  RUNNING/PASS/FAIL/exit data and bounded shell-file metadata detection were added.
  Failed frameworks were tracked independently; no raw paths/content/commands published.
- Public helper validates correlated outbox/inbox delivery and one actual peer reply;
  queue capacity four, no recursive reply loop, bounded artifacts and symlink rejection.
  API request_reply defaults false; UI requests replies. Idle follows completion after 3s.
- Files: models/bus/jobs/API/observer, messaging/simulator, tests, collaboration smoke
  scripts and protocol/roles docs. Full check **68 pytest passed**.
- Two real Codex collaboration turns passed, verifying both inboxes/completions.
  Real code/unittest smoke also passed. Commit **1800b93**, `implement agent roles and real CLI collaboration`.
- Follow-up serialized concurrent delivery; full queue returns HTTP 429 without losing
  earlier questions. Files: jobs/main/messaging tests/roles docs. Full check **69 pytest
  passed**; commit **b9db572**, `preserve queued peer requests under concurrent delivery`.

## 4K/activity milestone — UHD and visible agent actions

- Fixed 3840×2160 viewport, 1920×1080 initial window, F11 fullscreen. Role labels,
  coding/test/command/chat/response/idle/done/error badges and station paths. Private
  responses are distinct from peer chat. Two authoritative activity cards show five
  actual recent events; reconnect begins from snapshot rather than fabricated history.
- Added distance-field UI font, plant/brass/shelf details and steam shader; test
  monitor follows actual activity. All five effects respect Atmosphere.
- Files: project, café/activity_card/character/event_state/world, steam shader, state
  tests, CI render size, README/graphics docs/4K preview. Existing scene UID preserved.
- Full check **69 pytest passed** and actual 4K OpenGL renders inspected with/without
  effects/dialog. Corrected font spacing; no shader/script errors. Prior real Codex
  code and two-agent collaboration smokes passed; Windows GPU not benchmarked.
- Commit **651c788**, `render cafe in 4K with visible role-based agent actions`, pushed.
  Final CI passed: https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/38310655093
- Next: update backend for role logic, restart Godot and optionally use F11.

## Management M1 — Persistent configuration, Markdown tasks and roles

- Reused FastAPI/EventBus/Codex/Godot. Added standard-library SQLite registry/states/logs
  because prior metadata was volatile; readable JSON configuration and Markdown source
  instructions. Validated configuration, replaceable tasks, multiple roles and approved
  workspace roots with symlink/traversal rejection.
- Files: management config/storage/files/registry/init and `test_management_definitions.py`.
  Full check **80 pytest passed**. Commit **84748a7**, `persist agent configurations and Markdown definitions`.
- Not pushed under then-current user instruction. Modules were not connected yet;
  GitService, isolation, lifecycle, API and UI followed.

## Management M2 — Isolated workspaces, GitService and persistent execution

- Dedicated Git service supports init/connect/clone, branches, stage/commit, diffs/history
  and worktrees through argument-based isolated commands; no hooks/destructive actions.
  Remote operations require opt-in and explicit confirmation.
- Bubblewrap mount/PID/IPC/UTS isolation adds read-only metadata/instruction snapshots.
  Workers cannot see other workspaces/controller data/SSH sockets. Per-execution Git
  helper permits local stage/commit without unrestricted metadata/remote access.
- Persistent lifecycle/task/review/log/hash/timeout/cancel/retry/recovery, locks, private
  management token and legacy bypass guards. Process success is not task acceptance.
- Files: management git/sandbox/execution/api/security/git_helper, main/config, Git and
  execution tests, Docker/Compose/SSH/CI. Full check **91 pytest passed, no skips**,
  including prepared M3 native management tests and actual namespace protections.
- Real Codex Markdown/Python/unittest/helper commit smoke passed independent checks;
  only agent branch changed, no remote operation. YAML parsed; no local Docker build.
- Commit **84abb98**, `isolate managed agents and coordinate Git worktree execution`.
  No push under then-current instruction; native management followed.

## Management M3 — Native management and verified workflow

- Added Godot create/edit/workspace/task/roles/Git/timeout/retry/Markdown management,
  start/stop/restart/log/history and separate review UI. Extra characters share real
  events; existing demo and task UI remain.
- Added exclusive controller lock before recovery, hidden management credentials,
  individual-path staging (excluding .env/.cafe), read-only snapshots, revision-bound
  acceptance, post-completion restart and offline remote configuration.
- Files: management.gd, test_management.gd/UIDs, native fixture/harness,
  `test_game_management.py`, management docs, JSON/role/task examples, management smoke
  scripts; café/character/event_state/state tests, README/architecture and backend modules.
- Full check **93 pytest passed, no skips**. Repeated real isolated Codex code/unittest/
  helper-stage/commit smoke passed independent checks, two agent-branch commits and no remote calls.
  YAML parsed; local Docker rebuild and new GPU rendering unavailable.
- Commits **84748a7**, **84abb98**, **360127b** (`add native agent management and verified execution workflow`).
  No push/merge/credential changes; previous scene UID stayed local. At this milestone:
  Linux namespaces and one controller required; no automatic review/merges, remote default off,
  legacy Ada/Turing retained a trusted compatibility path.
- Follow-up bounded start-time role summaries to 120 characters while retaining all
  16 roles. Regression covered snapshot size/persistence: full check **94 pytest passed**.
  Commit: `bound managed role summaries in realtime snapshots`; no push.

## GUI M1 — Clearer interface and actual input tests

- Improved cards/actions/labels/scroll areas, fixed action bar and 4K dropdowns.
  Fixed dropped clicks during polling, selection resets, disappearing errors, late-save
  overwrites, duplicate submits and post-create selection. Actions reflect capabilities/lifecycle.
  Café uses event click coordinates, pending/offline state, modal backdrop and Escape.
- Real mouse/keyboard scenarios cover delayed HTTP, dropdowns/tabs, Markdown/roles,
  create/edit/start/stop/log/review/Git operations and original character/task/message/cancel clicks.
- Files: management/café/character/project, API capabilities, GUI/input/render scripts,
  fixture/harness, CI, gui-testing docs/preview. Full check **96 pytest passed**.
  Actual OpenGL 4K GUI test and inspected four-page/dropdown/task previews passed;
  corrected clipped popup fonts. No paid models needed.
- Commit: `polish cafe management and test real GUI input`. No push under user instruction;
  Windows DPI/GPU and hosted CI remained untested; previous scene UID preserved.

## Setup M1 — Local starter and team wizard

- Reused registry/Markdown/GitService/sandbox/SQLite; protected project/check/team APIs,
  no arbitrary-host-path API. Starter adds folder chooser/fallback, explicit mounts/IDs,
  SSH-agent/known_hosts forwarding without private keys, login, health and Godot/WSL launch.
  Privileged/remote options remain explicit; token initially passed only in process memory.
- Godot setup shows objective/check report/fixed actions and selected project. Team
  creation preserves interrupted work/tasks/roles/configuration and creates real branches/
  worktrees without starting models, committing initial files, pushing or merging.
- Files: management setup/api/git, setup-project.py, management/setup input/render GUI,
  backend setup/launcher/GUI fixtures/tests, CI, README/setup/management docs and PNG.
- Full check **105 pytest passed**; actual OpenGL setup input/4K visual inspection passed.
  Temporary Git and fixture login avoid model/external Git costs. Host Docker/native chooser/
  Windows handoff still needed target testing; one committed main source repository per launch.
- Commit: `add guided project and agent setup`. No push then; user project/scene changes preserved.

## Setup M2 — Native selection and shared project Markdown

- WSL Windows chooser uses constant PowerShell, UTF-8 and argument-based wslpath.
  Added AGENTS/PLANNING editors/import/save/templates; import previews content only.
  Dropped requested SSH-key selection after user correction; retained forwarding.
- Fixed document names/lowercase aliases, initial 12-KiB limit, BOM support,
  symlink/path checks, expected-SHA conflict protection and active-agent write guard.
  Every run snapshots current source files read-only, including uncommitted source
  instructions despite older worktrees; security/configuration still take precedence.
- Files: starter, project_documents/api/execution/setup, management GUI, input/render/
  backend/launcher tests, docs/preview. Full check **113 pytest passed**, plus rendered
  setup test; covered chooser/import-no-write/save/reload/namespace/conflict/alias/BOM.
- Commit: `add project instruction editors and native file selection`. Feature push
  authorized; no further main merge. Native Windows/full Docker host launch unverified.

## Setup M3 — Visible checks and plan-derived objectives

- Reproduced missing immediate check feedback and hidden HTTP errors. Added persistent
  Checking/status/report/error/timeout messages and reasons for disabled team creation,
  without losing edits. Empty objectives use the loaded plan's next open milestone;
  short explicit objectives and sandbox/login/Git gates still validate.
- Reproduced foreign-ownership Git rejection; per-process safe.directory trusts only
  the validated workspace. Whole check limited to 30s; Git errors become structured FIX.
- Files: management GUI/setup input, setup/git, backend tests/fixture, setup guide.
- Full check **116 pytest passed** and OpenGL setup GUI passed (delayed check, real 409,
  retry and plan-only creation). User-host cause not independently established.
- Commit: `fix project setup feedback and plan-based team creation`; feature only.

## Setup M4 — Sandbox diagnostics and skipped dependent checks

- Shared bounded isolation self-test classifies namespace rights/limits, mounts,
  missing runtime and timeout; no auth/model call or raw stderr in public APIs/logs.
  Setup marks login/Git SKIP after sandbox failure, rather than recommending login.
- Starter probes selected workspace after health and stops before login/Godot on
  failure. No privilege escalation/fallback; added shareable sandbox-diagnostics.py.
- Files: sandbox/setup, starter/diagnostics, management/blocked GUI test/UID,
  backend sandbox/launcher/setup tests/fixture and guide.
- Full check **128 pytest passed**, rendered blocked-GUI passed, actual local probe
  `ready`; all 12 launcher/setup tests passed again after argument refinement.
- Commit: `diagnose sandbox startup and skip dependent checks`; feature only.
  User Docker/WSL policies remained unknown; local ready does not establish host readiness.

## Setup M5 — Correct Codex login-status command

- Reproduced with CLI 0.162.1: `codex --ignore-user-config login status` failed parser
  validation before checking credentials; that option belongs to exec. Now uses
  `codex login status` in the same auth sandbox, with no user config mount.
- Actual pinned offline CLI tests with/without fictitious auth reproduced then passed.
  CI installs the same CLI instead of skipping this regression.
- Files: setup.py, test_project_setup.py, CI, setup docs/progress. Full check **129 pytest passed**.
- Commit: `use supported Codex login status command`; feature only. Checks stored
  login, not server-side entitlement; user credentials untouched.

## Worker M6 — Visible activity, Git errors and preserved results

- Short centered role/name labels (18-character fallback), managed-worker cards/desks,
  hidden unused demo placeholders; unchanged snapshots no longer reset animation.
  STARTING animates; persisted completion/error states restore after restart.
- Git preparation errors reach status/events. Team config is saved before preparation
  for recoverable partial failures. Safe errors name operation/category rather than raw stderr.
  Execution dialog/guide clarify worktree result locations and copying.
- Files: git/execution/setup and tests, café/character/management and state/management
  tests, setup guide. Full check **131 pytest passed**; 13 setup tests reran after
  persistence changes, including a fresh controller on the same database.
- Commit **cd27365**, `preserve worker setup and show managed activity`.
  User-host Git cause still required new diagnostics; publication followed separately.

## Worker M7 — Publish results to agent branches

- Explicit starter/setup/agent opt-ins (`--publish-results`, publish_results,
  allow_push + push_on_success). Existing teams preserve work, tasks, roles/history.
  Worker commits through private helper; controller publishes only clean committed work.
- Validated own agent branch and one approved credential-free SSH/HTTPS URL; explicit
  single refspec, no force/mirror/tags/submodule push. Publication and remote/branch/SHA
  persist separately from runtime/review. Failures preserve files and report FAILED.
- Refined permission/SSH/divergence diagnostics; demo/managed role cards coexist.
- Files: management api/config/execution/git/registry/setup, starter, management/café,
  worker-publication/Git/setup/GUI tests, docs/examples/progress.
- Full check **141 pytest passed**; additional OpenGL setup and demo-switch tests passed.
  Real temporary bare remote tested commit transfer, dirty-tree guard and concurrent
  remote history without external services/models.
- Commit: `publish successful worker results to agent branches`; feature only.
  User SimulationWorld access unverified; automatic integration not yet implemented here.

## Presentation M8 — Unobstructed test-station label

- Moved CLI TEST LAB to a dedicated dark sign above its monitor, centered using
  measured font width, clear of candle/decor/steam. Files: world.gd and progress.
- Inspected real OpenGL previews with/without effects; runtime screenshots not committed.
  Full check **141 pytest passed**. Commit **000d79b**, `keep test lab title clear of cafe decorations`.
- No remaining label issue or workflow change.

## Team M9 — Automatic integration, requirements tests and main promotion

- User authorized feature integration followed by green main promotion. Removed
  manual accept/reject requirement. auto_integrate adds persistent integration worker
  and worker publishing, retaining existing worktrees/tasks.
- Coordinator waits for current successful worker publications, merges exact commits
  and remote main into its own worktree, and invokes the existing Codex runtime.
  Immutable AGENTS/PLANNING/task requirements hash binds committed requirements,
  tests and validation/plan.json mappings.
- Controller reruns pytest/npm/Godot isolated without network/auth/SSH/Git writes/helper.
  Only unchanged tested commit can publish; snapshots and remote-main baseline must
  still match. Normal fast-forward only; source checkout remains untouched.
- Persisted team/check/promotion status and hashes; restart records interruption and
  rechecks eligible teams. Failures retain files; Retry triggers another attempt.
  Fixed Git SSH detection after global -c options and preserved sanitized API errors.
- Files: new integration/validation, management api/config/execution/git/setup/main,
  management UI/three GUI tests, team/execution/publication tests, README and guides.
- Initial full run **143 passed/6 failed**: four fixture timeouts during parallel OpenGL,
  a fixed-delay race and a real false conflict diagnosis from a directory name. Used
  actual runtime synchronization and genuine Git conflict markers; rendered setup passed separately.
- Final sequential full check **149 pytest passed**, plus concurrency regression ensuring
  duplicate completion notifications do not repeat a failed integration.
- Commit: `automate requirements-tested team integration to main`; development pushed
  only to feature. Requirements tests are evidence, not formal proof; dependencies must
  exist. At this point unresolved merges stopped integration; remote protections remain respected.

## Safe agent deletion — 2026-10-19

- Added Delete agent confirmation/Escape/Enter and real snapshot character removal.
  Authenticated DELETE requires confirmation, blocks active agents/teams, atomically
  archives config and disables affected automation. Restart does not resurrect agents.
- Files/branches/commits/tasks/roles/history persist; demo agents protected.
  Files: api/execution/storage, management/café, deletion backend/Godot tests,
  management harness/GUI tests and guide.
- Three focused backend tests, native GUI and rendered OpenGL input passed; full
  check **154 pytest passed**. Commit: `add safe agent deletion`.
- Next: updated-client review; incomplete teams require explicit setup again.

## Fix SSH user mapping inside sandbox — 2026-10-19

- User evidence: host/container SSH and worktree push dry-run passed, isolated SSH
  failed “No user exists for uid 1000”. Missing passwd mapping blocked getpwuid before auth.
- Read-only /etc/passwd and /etc/group now mounted only for SSH-capable Git; no
  shadow/private keys/host homes. Added precise diagnostic.
- Files: sandbox/git, test_management_git.py and setup guide. Real offline OpenSSH -G
  under UID 1000 checks user lookup and absent sensitive mounts. Initial **11 passed/1 failed**
  due to expected error wording; verified read-only via statvfs instead. Blocking calls
  moved to asyncio.to_thread. Full check **156 pytest passed**.
- Commit: `resolve SSH users inside Git sandbox`. No claim of user GitHub push;
  rebuild/start with loaded agent, resume workers, then integrate.

## Inspect the selected agent's workspace — 2026-10-19

- load_agent changed config but left the separate Git selector stale. Selection now
  updates Git workspace; manual overrides remain. Missing workspace and Git errors
  replace stale panel results; missing .git points to current worktrees, without auto-init.
- Files: git.py, management.gd, Git/GUI tests and guide. **14 focused tests passed**,
  including empty old mount→diff error→agent selection→successful inspection.
  Full check **157 pytest passed**.
- Commit: `inspect Git in the selected agent workspace`. Diff is against HEAD;
  committed work is in history. Next: update client/backend and inspect current worker.

## Restore mounts for existing worktrees — 2026-10-19

- User .git links referenced the original project ID, but source .git was absent
  after choosing a temporary Docker Desktop mount under a different ID.
- Added validated `--workspace-id` to reconnect the real host source to its saved ID;
  defaults unchanged. Dry-run tests check exact source/destination and reject invalid IDs.
- Files: starter, test_project_setup.py, setup guide/progress. **17 setup tests passed**;
  full check **159 pytest passed**. Commit: `restore existing worktree mounts`.
- Next: remount actual SimulationWorld without deleting worker data/branches.

## Project management, publication and recaps — 2026-10-19

- Repository-origin identity reuses projects across host/WSL paths, saving only hash→ID.
  Added confirmed selected/all-project deletion with active/dirty guards, preserving
  source/branches/history; shared metadata cleaned after worktree removal.
- Executions show recap and branch/SHA evidence; controller commits agent-changelogs
  and publishes to worker branch only. Enabled integrator can promote tested combined work.
  Setup defaults select integration/publication, but starter still requires remote opt-in.
- Files: starter/tests, API/execution/git/storage, setup UI/input tests and guide.
  Full check **163 pytest passed**; **16 focused integration/publication/deletion tests passed**.
- Commit: `reuse selected repositories and publish agent recaps`. No known implementation
  gap at this milestone; Windows/WSL visual review still required.

## Refresh assigned workspaces after deletion — 2026-10-20

- Backend removed worktrees but Godot cache retained them. Success now removes
  project/team/worker entries locally and refreshes views, preserving source workspace.
- Files: management GUI/setup tests, backend deletion tests; CI/check script diagnostic
  stages and progress. Native GUI plus full check **163 pytest passed**, repeated after split.
- Older main **a0954cd** passed its **113-test** local check, while hosted run #17 failed
  only the combined step with no public traceback. Node20/migration warnings did not explain it.
  **94de70b** failed the same old step, not evidence against this cache fix.
- Split lint/pytest/Godot/import/state/headless/WebSocket CI stages to locate failures.
  Commit: `remove deleted worker workspaces from setup UI`.

## Narrow hosted pytest failures — 2026-10-20

- Run **39489840780** passed lint but failed combined pytest. Split runtime/management/
  Git-team/GUI groups, then individual failing files; all test files remained covered.
- Initially allowed namespace_denied in the diagnostic test; this was later reverted
  because isolation is a required test prerequisite (see next entry). Further failures
  appeared in management. Added safe test-ID/exception/source-line annotations and job
  summaries without exposing assertion values/private tracebacks.
- Files: CI, check.sh, progress and diagnostic test during investigation.
  Repeated full checks **163 pytest passed**; focused diagnostics **10/10 passed**.
  Anonymous hosted logs still lacked detailed pytest output; next hosted run needed.

## Require a real CI sandbox — 2026-10-20

- Corrected earlier inference: feature test names did not prove the historical main
  failure. Reverted relaxed namespace test. CI now probes isolation before testing;
  only a confirmed AppArmor userns restriction installs a profile for /usr/bin/bwrap
  on the ephemeral runner, then requires the probe to pass. No production-host changes.
- Local full check **163 pytest passed**, shell syntax passed. Commit **e0280be**,
  `prepare real namespace isolation on CI runners`.
- Hosted run **39494719463** confirmed namespace_denied, then passed sandbox/workspace/
  deletion/definition/document/setup tests after the profile. Three shared pytest checks
  still failed because setup-python's `/opt/hostedtoolcache` interpreter was outside
  sandbox mounts. CI switched to system Python 3.12 in `/opt/venv` on Ubuntu 24.04.
- Full check again **163 pytest passed**. Commit **00f7bec**, `align CI Python with the sandbox runtime`.

## CI fully green — Confirmed result

- **00f7bec** includes **e0280be**. Complete hosted success:
  https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/39495521850
- Backend/Git/team/native GUI/Godot/WebSocket/shader/render/input/Compose/container
  build-health all passed. AppArmor and interpreter-location prerequisites were confirmed
  for this runner. Historical main traceback still unavailable; main not automatically merged then.
- Documentation-only follow-up; same code as green CI/local **163-test** suite.

## Automatic local management connection — 2026-10-21

- Starter atomically saves private connection JSON with mode 0600, including --no-godot and
  missing-Godot cases. No token printing; runtime remains Git/Docker-excluded and outside
  worker mounts. Godot loads on manual restart/Connect Refresh; hidden token field,
  explicit environment precedence and backend-URL binding preserve authentication.
- Files: starter, local_connection.gd/UID, management UI, launcher/Godot/GUI tests/guides.
  Full check **165 pytest passed**; native test connects without token env, checks permissions,
  backend binding and malformed JSON. Commit: `connect Godot automatically after project setup`.
- Next: rerun setup/reopen Godot; exports can use VAC_CONNECTION_FILE. Main unchanged then.

## Workspace and task deletion — 2026-10-21

- Confirmed workspace unregister preserves disk/Git; task deletion permanently removes
  unassigned Markdown. API checks paths/assignments/project sources under management lock.
  UI restores saved selections and removes deleted agents from its cache.
- Files: api/execution/files, API/GUI tests, management.gd and guide.
  Full check **168 pytest passed**. Commit **14bdf55**, `feat: add safe workspace and task deletion`,
  pushed to feature. Physical workspace folders intentionally remain to prevent data loss.

## Precise test failures and readable completion reports — 2026-10-26

- Added tool/exit/category/pytest explanations and bounded private test identifiers,
  without public paths/parameter/assertion values. Persisted invocations include reruns.
  Scrollable Changelog & tests separates model report from confirmed branch/SHA publication;
  removed extra 1,400-character truncation.
- Files: adapters base/codex/new diagnostics, execution, management GUI, Codex/lifecycle/
  native tests and guide. Full check **176 pytest passed**.
- Commit: `explain test failures and expose execution changelogs`.
  New runs only, ≤100 invocations of last attempt, ≤6,000-character model report;
  no complete public tool logs and no conflation with requirements acceptance.
- Next: rebuild backend/reopen Godot and inspect a new run; no automatic main merge.

## Remove incorrect setup folders — 2026-10-26

- Filesystem discovery rediscovered unregistered sources; project deletion required
  a created team. Added confirmed removal even before check/team, with persistent
  hiding and Restore removed folders. Files/Git/mounts remain; assignments/teams protected.
- Files: setup/api, management GUI/setup input, project setup tests and guide.
  Full check **178 pytest passed**, including restart, paths, protection and real clicks.
- Commit: `remove unwanted folders from project setup`; feature only.
  New host paths still require starter; next: rebuild/reopen/remove incorrect entry.

## Empty project-search feedback — 2026-10-26

- Find projects now shows searching/count/empty status and distinguishes restoring
  hidden folders from mounting a new host directory. Search never silently restores removal.
- Files: management.gd, test_setup_input.gd, progress. Native regression and full check
  **178 pytest passed**. Commit: `explain empty project discovery results`.
- Next: update feature checkout and reopen Godot.

## Recreate teams with preserved Markdown — 2026-10-26

- Orphan tasks/roles previously blocked recreation. Worker/integration setup validates
  and reuses them byte-for-byte; only missing files get templates. Occupied IDs and
  unrelated nonempty destinations remain protected. UI asks users to review preserved tasks.
- Files: setup.py/tests, management.gd, guide/progress. Tests create/delete/recreate,
  reject invalid Markdown and resume interrupted setup. Corrected fixture assumptions
  about assigned-file deletion; full check **180 pytest passed**.
- Commit: `reuse preserved team markdown during setup`. No migration/deletion needed;
  next: update/retry setup and review task objectives.

## Diagnose blocked worktree recreation — 2026-10-27

- Real Git reproduction: missing directory with retained registration rejects creation.
  Added separate stale/locked/storage diagnostics without raw paths/credentials.
  Metadata/files preserved; no auto-prune/unlock/force.
- Files: git.py, test_management_git.py, progress. Full check **181 pytest passed**.
- Commit: `diagnose stale and locked worktree registrations`. User's actual worktree
  list was requested; local reproduction alone did not establish their cause.

## Reuse worktrees and target deleted registrations — 2026-10-27

- Setup accepts matching repository/branch worktrees with existing files, preserving
  dirty changes. Deletion tolerates missing directories and removes only their unlocked
  stale administrative entries; no blanket prune from a restricted mount view.
- Files: git/execution/setup, Git/setup tests, guide/progress. **46 focused tests passed**,
  covering dirty reuse, wrong branches and preservation of unrelated live/stale entries.
  Full check **184 pytest passed**.
- Commit: `reuse matching worktrees and prune only deleted registrations`.
  Broken links/unrelated destinations are not overwritten; hiding is not physical deletion.
  Next: update backend and rerun team setup to reuse matching integration worktree.

## Visible integration retry status — 2026-10-28

- Generic queued/action-completed messages hid missing worker inputs. Retry now checks
  latest runs/publication/task/project/role snapshots before queuing and identifies blockers;
  identical promoted results report PROMOTED. Dedicated UI status includes PREPARING;
  automatic runs persist the same waiting reasons.
- Files: api/integration, management GUI/test, new test_integration_retry.py and guide.
  Five focused API tests and full check **189 pytest passed**.
- Commit: `show actionable integration retry status`. User project blocker remains
  to be read after update/retry; no claim their integration already started.

## Preserve retry response across polling — 2026-10-28

- Log polling overwrote retry errors. Added copyable read-only timestamped LAST RETRY
  per selected run, separate from live status; switching runs shows only its response.
- Files: management.gd/test_management.gd, integration guide/progress. Actual failed
  fixture retry followed by log polling/run switching passes; full check **189 pytest passed**.
- Commit: `keep integration retry responses visible across polling`.
  LAST RETRY is session-local; team status persists. Next: reopen client and inspect it.

## Agent conflict resolution and team recreation — 2026-10-28

- Integrator can start with pending merges/retained edits and exact input commits.
  Helper permits only this run's approved merges, no branch switches. Before publication:
  clean tree, completed merge and main/worker ancestry are mandatory; validation and
  concurrent-main guards remain. Individually deleted workers can be recreated using retained worktrees.
- Files: git/git_helper/integration/execution/setup, team/setup tests and guide.
  Add/add conflict resolved through real helper, validated/promoted; unresolved success
  blocked. Retry/worker-recreation/local-file tests included. Full check **192 pytest passed**.
- Commit: `let integration agents resolve preserved merge conflicts`.
  Contradictory requirements may need clarification; no forced side/reset/abort/force-push.
  Next: rebuild and Retry team integration without deleting user work.

## Preserve live-log scroll position — 2026-10-28

- Replacing TextEdit on every poll reset scrolling. Append batches only when new;
  preserve horizontal/vertical position, follow only at bottom, trim whole oldest lines
  at 48,000 characters and adjust reading position.
- Files: management.gd, new test_log_scrolling.gd, management harness/progress.
  Native empty/new/duplicate/follow/trim regression and full check **193 pytest passed**.
- Commit: `preserve live log scroll position during updates`. Removed bounded-display
  lines cannot remain visible; backend history unchanged. Client restart suffices.

## Bounded integration repair and private chat — 2026-10-28

- Default three total attempts pass failed runtime/shared-test diagnostics to next run
  in the same worktree. Repeated failures/budget exhaustion become NEEDS_INPUT;
  publication/promotion failures stop immediately. Duplicate worker events do not restart
  stopped cycles; cancellation/restart remain explicit.
- Persistent private API/Godot chat resumes workers/integration; active-run messages
  apply at the next start. Final agent/controller results remain visible. Shared validation
  shows bounded sanitized pytest diagnostics; only exact validated commit can reach main.
- Files: api/config/execution/integration/validation/new conversations, management UI,
  execution/team/Godot tests, README/integration guide/progress.
- **23 integration/execution**, **20 backend/native**, extra restart tests passed.
  Full check **199 pytest passed**; restart recovery regression and Ruff repeated after
  recovery refinement. Covers successful repair, unchanged-main stall, chat resume/auth/
  privacy/persistence, no duplicate execution, UI messages and preserved drafts.
- Commit: `add bounded integration repair and agent chat`. No live prompt interruption;
  40 retained/12 context messages, extra model cost, infrastructure may need human repair.
  Deterministic runtimes/local remotes only, no paid model runs in these tests.
- Next: rebuild/reopen and use Agent chat when NEEDS_INPUT.

## Per-agent model selection — 2026-10-28

- Optional validated bounded AgentConfig.model persists; null retains automatic Codex
  default. Explicit selections pass separate --model argument and freeze in execution
  history. Added authenticated bounded catalog with cleanup, labeled bundled fallback,
  cache/refresh; no hardcoded UI catalog or raw model instructions/diagnostics.
- Godot dropdown/refresh/list/details/requested-model report preserve saved and draft
  choices across missing/changing catalogs. Save applies next run, including chat/integration.
- Files: api/config/execution/sandbox/new model_catalog, Codex adapter, new
  test_agent_models.py, managed fixture, management UI/test, README/guide/progress.
- **19 focused backend/native tests passed**; actual read-only CLI catalog returned
  eight visible models (source codex), no paid model execution. Final full check after
  environment restart on 2026-10-29: **212 pytest passed**, SSH/remote rechecked.
- Commit: `add per-agent Codex model selection`. Catalog visibility does not guarantee
  entitlement; runtime enforces it. No resolved model claimed for automatic default;
  host config.toml remains unmounted. Next: rebuild/reopen, select/save/start.

## Godot controller validation diagnosis — 2026-10-29

- Exact original error: management/validation.py:100 at e38dd63. One guard conflated
  existence, test filename prefix, .gd suffix and membership in git ls-files.
- Confirmed reproduction against the original implementation: main has no scripts;
  integration worktree contains three committed Godot tests. Project-relative
  declarations pass all three; equivalent res:// declarations fail with the exact
  reported error. Pathlib treated the resource URI as frontend/res:/tests/..., and
  the Godot argument would prefix res:// again. No main-selection bug reproduced.
  The user's failing manifest was not available locally; its checks were requested
  to distinguish URI misuse from the independently misleading filename error.
- Fixed canonical project-relative/resource-URI resolution without relaxing the
  existing test filename, suffix, containment, symlink or commitment rules.
- Validation pins HEAD SHA and branch, checks the commit tree and actual blobs,
  compares workspace contents with Git-normalized blobs (CRLF supported), rejects
  staged-only tests and stale requirements, and checks cleanliness/HEAD afterward.
  It clears old reports first and only sets passed after all postconditions.
- Git publication accepts the validated expected SHA, rejects changed HEAD and
  pushes that exact SHA. Existing promotion/remote-main guards remain intact.
- Private diagnostics include selected ref, branch, SHA, repository root, declared
  directory/script, resolved path, Git blob status/OID and distinct failed rule.
  GUI report displays snapshot/rule; full metadata goes to authenticated logs and
  repair context, not public events. Godot error output cannot pass merely because
  the process exits zero. No test requirement was bypassed.
- Files: management/{validation,git,execution,integration}.py;
  game/scripts/management.gd; new backend/tests/test_godot_validation.py;
  backend/tests/test_team_integration.py; docs/automatic-integration.md; PROGRESS.md.
- Focused integration/publication/validation run: 35 PASS. Additional CRLF regression
  PASS after refreshing the fixture's index stat data (no staged content changes).
  Final focused and complete check results recorded below on completion.
- Commit-ID: git log --grep='validate Godot scripts against the integration commit'.
- Next step: rebuild backend and restart Godot; retry integration. For remaining
  failures inspect validation.diagnostic rather than inferring missing files from
  a generic message. No real external model calls or remote-hosted fixtures used.
- Final evidence: focused test_godot_validation.py 19 PASS; full scripts/check.sh
  PASS with 231 pytest, Godot import/state/headless and WebSocket smoke PASS.
  After naming the combined exit/output rule check.result, the two affected Godot
  execution-error cases were rerun: 2 PASS. Final Ruff/format and diff checks PASS.
  Existing Starlette/httpx warning unchanged. Reproduction logs confirmed the old
  relative-path control passes three checks while equivalent resource URIs fail.


## Reviewed next iterations and distinct integration workstation

- Request: remove the unexpectedly small planning limit, let a user review main,
  submit the next requirements in one place, and separate the integration avatar.
- Project Markdown now permits 64 KiB UTF-8 end to end. Only document/iteration
  API request limits are expanded for JSON escaping; other request limits remain.
  Shared requirements snapshot limit accommodates both larger documents.
- Setup adds a requirements editor and Start next iteration. The controller uses
  existing Git/runtime/integration modules, fetches exact remote main, preserves
  worker changes, saves current requirements and starts both workers. Persistent
  round IDs prevent stale worker results from triggering integration. Existing
  publication permissions and controller tests remain mandatory.
- Integration has an explicit role, separate destination/desk and activity card;
  workers and integrator no longer occupy the same desk due to role-name matching.
- Files: management project_documents/api/integration/execution/validation,
  main request parsing; Godot management/cafe/character/activity_card/world;
  tests test_iterations/test_project_documents/test_states/test_setup_input;
  docs/project-setup.md and this log.
- Evidence so far: 8 document tests pass; real temporary Git two-round workflow
  passes, including stale planning/dirty worker/duplicate-start rejection and
  a second tested main promotion. Full checks recorded below when complete.
- Limitations: preparation conflicts preserve files and require resolution;
  explicit Start next iteration is required after human review (no file watcher).
  No rendered screenshot available in this environment; native GUI checks used.
- Commit locator: `git log --oneline --grep='feat: start reviewed team iterations'`.

- Focused suite: 16 PASS (two-round Git workflow, project-document bounds/API,
  native Godot management/input tests). Full check: Ruff PASS; pytest 216 PASS,
  17 FAIL after namespace exhaustion. Direct Sandbox().command(... git init)
  reproduces `bwrap: Creating new namespace failed ... max_*_namespaces exceeded
  (ENOSPC)`. More than 31,000 zombie bwrap processes are parented by PID 1 (node).
  Disk space and inodes are available. This is an environment resource failure;
  the Git error classifier misleadingly calls ENOSPC insufficient storage.
- Added Compose init:true for codex/backend so a container init reaps orphaned
  sandbox processes in newly created containers. Existing zombies require this
  development container to restart. No namespace/isolation checks were bypassed.
- Milestone remains UNCOMMITTED / UNPUSHED until the complete check succeeds after
  restart. Resume with scripts/check.sh, inspect results, then commit and push.
- Independent post-failure checks: Godot import, state tests, headless startup,
  and live WebSocket/selection smoke PASS. git diff --check PASS. Docker CLI is
  unavailable here, so Compose runtime validation remains for a Docker host.


### Follow-up: next iteration rejected by transient team status

- Removed the PROMOTED-only start gate. It incorrectly prevented an initial round
  in an existing repository and a later round after a planning edit changed the
  team status to WAITING_FOR_WORKERS. Starting a round does not approve old runs.
- Retained live-run exclusion, current planning hash, clean worker checks, exact
  remote-main fetch/merge, per-round source matching and all publication tests.
- Regression now starts the initial round through the iteration entrypoint and
  reproduces the planning-edit/status transition before starting a second round.
- Namespace probe succeeds in the current session; rerunning required checks.
- Follow-up verification: Ruff/format/diff checks PASS; 4 isolated preflight
  regressions PASS (READY/WAITING_FOR_WORKERS/FAILED/NEEDS_INPUT are not treated
  as missing human review; stale input remains rejected and history unchanged).
  Two-round integration test starts and publishes both initial workers but then
  fails preparing integration. Direct sandbox true/git-remote probes again show
  namespace ENOSPC. The development container still needs a restart; full check,
  commit and push remain pending. No failed execution was marked accepted.
- Restart verification: PID 1 is now docker-init, zombie count is zero during
  tests, and a real isolated sandbox probe succeeds. Remote feature branch is
  reachable at parent 21a358a. Full scripts/check.sh rerun is in progress.
- Final result after container restart: complete scripts/check.sh PASS.
  Ruff/format PASS; 237 pytest PASS (one existing Starlette/httpx deprecation
  warning); Godot import/state/headless PASS; live WebSocket/selection PASS.
  This supersedes the environment-blocked results above. No validation bypasses.
  The completed milestone is ready for commit and feature-branch publication.


## Project Markdown heading/save error

- Report: "Project Markdown needs a heading and at most 64 KiB" remained after
  the size increase. Confirmed load/save mismatch: existing Markdown beginning
  with paragraphs/lists loads, then save_document rejects it (also during a new
  iteration). That generic message cannot distinguish content from size errors.
- Project AGENTS.md/PLANNING.md now accept non-empty Markdown without a leading
  hash heading, preserving the text verbatim. Task/role definition rules unchanged.
  UTF-8 size stays bounded at 65,536 bytes. Separate errors identify empty content,
  non-file paths, or actual oversized byte counts. API parsing allows the bounded
  oversize case to reach the specific storage validator; saved limits unchanged.
- Iteration validates the combined plan before schema construction/Git mutations,
  avoiding an unrelated verbose schema error when history exceeds the byte limit.
- Godot import/save accepts headingless project Markdown, shows the byte count,
  validates empty/oversized edits locally, and preserves editor/saved contents.
- Regression tests: paragraph/list/comment/BOM roundtrips, exact UTF-8 boundary,
  API oversize preservation, a complete iteration with headingless planning,
  native chooser/editor/save/byte-counter/error-preservation GUI interactions.
- Files: management project_documents/integration; Godot management; tests
  test_project_documents/test_iterations/test_game_management/test_setup_input;
  docs/project-setup.md and this progress record.
- Commit locator: git log --oneline --grep='fix: accept project Markdown without headings'.
- Verification: focused regression/API/native GUI set 20 PASS; complete
  scripts/check.sh PASS with 243 pytest, Ruff/format, Godot import/state/headless
  and live WebSocket/selection smoke. Existing Starlette/httpx warning unchanged.
  UTF-8 size limits, path confinement, conflict detection and publication checks
  remain active. A genuinely oversized file still needs shortening/archiving.


## Separate read-only questions from development instructions

- Request: asking "where is the script?" must answer without restarting development
  or triggering integration. Integrator idle position overlapped PEER EXCHANGE.
- Added separate question/instruction fields and actions to Agent chat. Messages
  carry a mode; questions never enter subsequent work instructions. The safe API
  default is question; explicit legacy resume behavior remains compatible.
- Added questions.py using the existing Codex adapter/model/auth with disposable
  scratch space and a read-only project mount. Hide .cafe Git RPC and .git data;
  no normal execution, Git watcher, recap/publication, bus status mutation or
  integration scheduler. Private question state/history persist; close cancels
  tasks and interrupted responses are marked on restart. Original work status and
  latest execution remain intact. One question per agent; work may run concurrently.
- Integrator idle destination moved from (193,145) to (193,85), above the exchange
  label. Native state regression checks the distinct position.
- Tests cover real namespace read/write prevention and hidden Git helper data,
  answer/instruction separation, unchanged worker/integration/publication history,
  safe API default, failures/cancellation, and actual GUI clicks/draft preservation.
- Changed: management conversations/questions/api/execution; Godot management/
  character; question tests, GUI fixture/input/management/state tests; management
  documentation and this progress log.
- Commit locator: git log --oneline --grep='feat: separate agent questions from work instructions'.
- Verification: focused question/native GUI tests 11 PASS. Full scripts/check.sh
  PASS: 247 pytest, Ruff/format, Godot import/state/headless, live WebSocket and
  selection smoke. Existing Starlette/httpx deprecation warning unchanged.
  Preserved the existing project-deletion error prefix required by regression
  tests while adding the active-answer guard. Tests use isolated fixture runtimes;
  no paid model calls or rendered visual inspection were performed.
- Next: update the feature branch deployment, rebuild backend and reopen Godot;
  verify real-model answers using the existing Codex login.

## Main release and streamlined getting started

- User explicitly requested publishing the tested feature work to main and a README
  centered on prerequisites, the Python starter, Godot and the day-to-day workflow.
- Rewrote README in German: host/container prerequisites, existing Git folder,
  AGENTS.md/PLANNING.md, native chooser, SSH/login, setup options, exact GUI actions,
  worker publication, integration/controller checks, changelogs, question/instruction
  separation and next iterations. Local backend setup is now developer-only.
- Replaced CI's fixed test-file subsets with the complete pytest suite so model,
  Godot validation, iteration, retry and question regressions cannot be omitted.
  Rendered UI, Compose validation and container smoke checks remain required.
- Remote main is an ancestor of this feature branch; planned publication is a
  normal fast-forward preserving all history. No force-push or credential changes.
- Files: README.md, .github/workflows/ci.yml, PROGRESS.md.
- README local links and starter --help verified. Prior feature CI 745bc15 passed
  on GitHub (run 41350169955). Final local/release results follow below.
- Commit locator: git log --oneline --grep='docs: streamline setup and publish complete CI coverage'.
- Final local verification: scripts/check.sh PASS, 247 pytest in 287.33s, Ruff and
  formatting, Godot import/state/headless and live WebSocket/selection smoke PASS.
  One pre-existing Starlette/httpx warning. Hosted rendered UI/Compose/container
  verification will run on the published commit; no local Docker daemon available.

## Reliable controller validation and workflow evidence

- Requested: investigate mismatched backend/frontend test reports, preserve exact
  validation evidence, distinguish infrastructure from defects, bound retries,
  recognize commits/integration/acceptance and reuse unchanged successful checks.
- Incident limit: 7f10fb7 and 063bd3f are not available locally; no project mounts
  containing them were present. Their 71-test/Godot claims and desktop acceptance
  remain unverified, not attributed to a controller bug without their evidence.
- Reproduced against the prior observer: backend pytest exit 2 followed by frontend
  pytest exit 0 incorrectly reported success (baseline true, fixed false). Failure
  bookkeeping keyed only by framework; now command/cwd scopes and superseded
  attempts are explicit. Godot script errors also fail zero-exit CLI invocations.
- Controller previously used sys.executable (potentially host-only), discarded all
  but a merged output tail, reported all shared failures alike, and sent environment
  errors into speculative repair. Added sandbox-runtime/explicit project-venv
  selection, declared pytest paths, separate bounded private stdout/stderr/context,
  exact submitted SHA checks, evidence-based categories and infrastructure stops.
- Passing check cache includes commit/plan/requirements/scope/environment; ignored
  dependencies disable reuse. Commit/dirty/environment checks still apply on hits.
  No arbitrary affected-test skipping or worker-claim-as-validation shortcut.
- Commit existence and ancestry remain required. Push/promotion now read back the
  remote tip. Additive workflow dimensions preserve existing API states and track
  implementation, validation, integration and manual product acceptance separately.
  Manual post-publication product review does not globally block independent work.
- Files: adapters base/codex/diagnostics; management validation/execution/integration/
  git/sandbox/api; Godot execution report; test_validation_reliability and local
  publication fixtures; docs/controller-validation.md, PROGRESS.md.
- Initial focused run: 75 passed; two publication fixtures lacked local ls-remote
  transport after adding remote verification. Updated those fixtures (actual Git
  verification retained). First new regression/publication set: 20 passed.
  Container restart interrupted the subsequent run; final verification follows.
- Commit locator: git log --oneline --grep='fix: preserve controller validation evidence and workflow states'.
- Focused controller/runtime/Godot/team/publication suite: 99 PASS. Final new
  reliability suite after timeout/controller-error diagnostics: 24 PASS. The full
  check run started before the last two added diagnostic cases, so those have
  separate focused evidence rather than an inflated full-suite count.
- Remaining limits: no access to the two incident commits; provider CLI streams
  are combined and may already be truncated by Codex. Controller streams retain
  up to 1 MiB each and fail explicitly on overflow. Full-commit integration checks
  are conservative; ignored dependency/build trees disable cache reuse. Manual
  product acceptance is recorded/reviewed via the existing authenticated API;
  automatic main promotion remains opt-in and is not a desktop-acceptance claim.
- Full regression initially found one old observer test assuming pytest executable
  entrypoints imply the same interpreter. Strengthened it: another interpreter
  cannot clear the failure; a successful same-scope rerun can. Presentation-only
  pytest verbosity flags normalize to the same scope, selectors/config do not.
  Observer + reliability suite 65 PASS; final roles + reliability suite 33 PASS.
- Additional files: test_roles_messaging (stronger interpreter/scope assertion),
  README documentation link. Final full check rerun is recorded below.
- Final scripts/check.sh PASS on the completed code: 272 pytest passed in 349.09s;
  Ruff/format, Godot import/state/headless and live WebSocket/selection smoke PASS.
  Existing Starlette/httpx deprecation warning only. Documentation links and
  git diff --check PASS. No external model calls or incident-project acceptance
  were asserted. Publishing this milestone to the feature branch, not main.

## English documentation and main publication — 2026-11-02

- User requested the latest implementation on main and English throughout the project.
  Controller milestone `493f35d` was already green on GitHub:
  https://github.com/St3fanTh/VirtualAgentCafe/actions/runs/41482951524
- Translated README, setup/management/integration guides, TASK/SKILLS and their
  original-name copies. Consolidated older progress entries into English while
  retaining historical outcomes, test counts, commit references and limitations.
  The original detailed wording remains available in Git history.
- Translated all starter help, folder-dialog labels, prompts and error messages.
  Updated two existing error-message assertions and one Markdown fixture phrase;
  multibyte Unicode samples remain intentionally present to test UTF-8 byte limits.
  Setup behavior, authentication, isolation and controller checks are unchanged.
- Files: README.md, TASK.md, SKILLS.md, VirtualAgentCafe_TASK.md,
  VirtualAgentCafe_SKILLS.md, PROGRESS.md, docs/project-setup.md,
  docs/agent-management.md, docs/automatic-integration.md, scripts/setup-project.py,
  backend/tests/test_project_setup.py and backend/tests/test_project_documents.py.
- First full run: 270 passed / 2 failed because tests still matched German error
  messages. Updated assertions to English without changing their safety checks.
  Final full-check result is recorded below.
- Verified English starter --help, local Markdown link targets, matching requirements
  copies and git diff --check. Language scan found only deliberate Unicode fixtures.
  SSH authentication, remote read access and feature/main ancestry were verified.
- Commit locator: `git log --grep='standardize documentation and setup in English'`.
  Main publication is explicitly authorized by the user; use a normal fast-forward,
  without force, preserving the existing feature branch.
- Final local verification: `scripts/check.sh` PASS; **272 pytest passed in 355.97s**,
  Ruff/format, Godot import/state/headless and live WebSocket/selection smoke PASS.
  Only the existing Starlette/httpx deprecation warning remains. The two earlier
  failures were resolved by matching the translated messages; safety assertions remain.
- Next: push the release commit to the feature branch and fast-forward main, then
  verify hosted CI, including rendered GUI, Compose and container build/health.
  User-project commits and desktop acceptance remain outside this release verification.

## Godot user-data startup failure in nested Codex sandbox — 2026-11-02

- Reproduced with actual Godot 4.4.1 and offline Codex CLI 0.162.1: the outer Sandbox
  succeeds, but nested `codex sandbox -c sandbox_mode="workspace-write"` fails to
  create `/home/agent/.local`, reports `Error attempting to create data dir`, crashes
  with signal 11 and exits 134. Existing controller-only Godot tests did not exercise
  this second filesystem policy. No model calls or user credentials were needed.
- Sandbox now sets XDG data/config/cache homes inside its private `/tmp` tmpfs;
  HOME/auth/Git permissions are unchanged. Each process receives fresh user data.
  Incremented validation cache version so old environment results are not reused.
- Precise Godot startup evidence remains ENVIRONMENT_ERROR in controller and observer,
  including wrapped commands and zero-exit error output. Added godot4 command recognition.
  No assertion that the user's past run used any particular wrapper: its raw command
  events are unavailable. Publication must be checked in controller records, not prose.
- Files: management/sandbox.py and validation.py, adapters/codex.py and diagnostics.py,
  new tests/test_godot_sandbox.py, docs/controller-validation.md and PROGRESS.md.
- Regressions run real Godot directly and inside Codex isolation, verify user:// write/
  read, fresh data across runs, hidden host/auth/SSH paths and read-only Git metadata.
  Observer/controller tests assert infrastructure classification, failed completion
  and redaction. Test results and commit evidence follow below.
- New focused regressions: 9 PASS. Broader Godot/controller suite: 51 PASS / 1 FAIL
  from an existing test assuming controller sys.executable equals runtime Python:
  launching pytest as `python` instead of `python3` exposed the differing aliases.
  Corrected the recorded-context expectation to the selected runtime interpreter;
  separate host-only interpreter regressions continue to enforce runtime selection.
- Final `scripts/check.sh` PASS: **281 pytest passed in 385.26s**, Ruff/format,
  Godot import/state/headless and live WebSocket/selection smoke PASS. Only the
  existing Starlette/httpx deprecation warning remains. `git diff --check` PASS.
- Commit locator: `git log --grep='provide private Godot user data in agent sandboxes'`.
  Publishing to the feature branch and authorized main by fast-forward. Next: rebuild
  the user's backend with the existing starter options, preserve all volumes/worktrees,
  retry frontend tests and inspect controller publication separately from model prose.

## Resolve equivalent Godot reruns after environment repair — 2026-11-02

- Reproduced two unresolved zero-exit Godot errors followed by a clean identical test
  with XDG/Fontconfig assignments: observer still returned unsuccessful with two open
  failures. Scope hashes included the supporting environment prefixes verbatim.
- Normalize only leading Godot XDG/Fontconfig assignments and plain env launchers
  for observed rerun matching. Keep executable, cwd, project/script, selectors and
  other environment settings significant. Controller cache/validation gates unchanged.
- Retain failed history as superseded after a clean matching rerun. Godot errors at
  exit zero remain blocking; PASS text alone never overrides engine/script errors.
- Files: adapters/codex.py, new tests/test_godot_reruns.py,
  docs/controller-validation.md, PROGRESS.md. The user's actual raw command events
  and project commit are unavailable; this confirms the reported sequence's matching
  bug, not that every historical runtime error was merely a warning.
- Commit locator: git log --grep='match Godot reruns after runtime environment repairs'.
- Focused observer/Codex/roles regression suite: **57 PASS** (including nine new
  cases). Environment restart interrupted the initial full-check evidence; rerunning
  the required full suite on 2026-11-03 with an ignored persistent check log.
- Final verification on 2026-11-03: `scripts/check.sh` PASS, **290 pytest passed in
  355.85s**, Ruff/format, Godot import/state/headless and live WebSocket/selection
  smoke PASS. Only the existing Starlette/httpx deprecation warning remains.
  `git diff --check` PASS. Publishing the tested fix to feature and authorized main.
- Next: update/rebuild the backend using the existing starter configuration and run
  the frontend task again. Old execution reports remain historical; no worktree or
  project reset is needed. Verify publication from controller branch/commit records.
