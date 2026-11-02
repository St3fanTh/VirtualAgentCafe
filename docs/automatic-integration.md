# Automatic integration and shared requirements tests

## Automatic repair and agent chat

Integration runs up to `execution.repair_attempts` attempts per cycle (default **3**,
including the first; configurable from 1–5). After a repairable runtime or shared
validation failure, the next attempt receives diagnostics and continues in the
same worktree, preserving edits and conflict resolutions. Shared diagnostics include
failure categories, exit codes and recognized pytest test names. Raw assertions
and output are not included in public events. Infrastructure and unexplained failures
require attention rather than speculative code repairs; see [controller validation](controller-validation.md).

The team shows `REPAIRING` during retries. A repeated failure after repair, exhausted
budget or publication/promotion failure stops the cycle as `NEEDS_INPUT`. Duplicate
worker notifications do not restart it. All main-promotion checks remain mandatory.
Cancelling integration also ends the repair cycle.

Open **Management → Agent chat**, select the integrator and read its last response.
Use **Send instruction & continue** to save clarification and start another cycle.
Worker chat works the same way. **Ask question** only requests a read-only answer;
it does not restart work or trigger integration. Markdown tasks, roles and security
rules still apply. Messages persist in the private management database, not the
public event stream. The last 40 messages are retained; up to 12 work-context
messages enter subsequent executions.

Instructions are delivered between executions. `NEXT_ATTEMPT` means an instruction
sent during a run is saved for its next start. If no further attempt occurs, request
a follow-up with **Send instruction & continue** after completion. Replies appear
after execution. Additional cycles consume model usage. Mount, permission and login
failures may require environment repair.

The workflow does not require manual task acceptance in **Executions**:

```text
Backend commit + push ─┐
                      ├─ Integration feature branch ─ Requirements tests ─ main
Frontend commit + push┘
```

## Enable automation

```bash
python3 scripts/setup-project.py --publish-results --privileged
```

Use `--privileged` only when your local environment requires it for namespace
isolation. Check the existing project in Setup, enable **Integrate + requirements
tests + promote green result to main**, then click **Create backend + frontend team**.
This also enables worker publication. Existing tasks and worktrees are preserved.
Start backend and frontend under **Agents**. The additional **Integration & Tests**
worker starts automatically after both current tasks have been successfully pushed.

The starter forwards the Git remote configuration, SSH agent and `known_hosts`.
The remote needs a `main` branch with shared history. Write access is required for
agent branches and `main`. Server-side branch protection may reject direct main
pushes; the controller does not bypass it.

## Automatic steps

1. Wait for both worker publications and verify task, role and project snapshots.
   Failed or stale executions do not qualify.
2. Use an isolated worktree on `agent/<project-id>-integration/validation`. Merge
   current remote main and the exact published worker commits using ordinary merges.
3. Give the integrator immutable shared requirements from `AGENTS.md`, `PLANNING.md`
   and both tasks. It aligns interfaces and commits shared tests and requirements.
4. Run the declared tests through the controller without network, Codex credentials,
   SSH agent or Git write access. The Git helper is disabled for validation.
   Model-process completion alone is insufficient.
5. Publish the integration feature branch after passing validation. Only the tested
   commit may reach remote `main` as a fast-forward. Requirements and tasks must
   still match the snapshots. A concurrent remote-main change blocks promotion.
   The controller verifies remote tips and commit ancestry rather than assuming success.
6. Record `AUTO_VALIDATED`/`COMPLETED` and project status `PROMOTED`. No manual
   Accept/Reject click is needed for this authorized workflow. Explicit desktop/product
   acceptance remains separate and can be reported as `MANUAL_ACCEPTANCE_REQUIRED`.

The host source checkout is not overwritten. After promotion, the combined project
is on GitHub's `main`; update a clean local checkout normally with Git.

## Shared test base

The integrator must commit:

- `validation/requirements.md`: an exact copy of the shared requirements snapshot.
- `validation/plan.json`: requirement-to-test mapping and executable checks.
- Actual tests, for example `tests/test_contract.py`.

```json
{
  "source_sha256": "SHA256 of validation/requirements.md",
  "requirements": [
    {"id": "REQ-1", "description": "Frontend and backend use the same API contract",
     "checks": ["backend-tests", "frontend-tests"]}
  ],
  "checks": [
    {"id": "backend-tests", "kind": "pytest", "directory": "backend"},
    {"id": "frontend-tests", "kind": "npm", "directory": "frontend"}
  ]
}
```

The hash comes from the read-only `.cafe/instructions/requirements.md` snapshot.
The controller checks the hash and exact contents. Every requirement must reference
existing checks and every check must serve a requirement. Duplicate IDs, unsupported
check kinds, path traversal, symlinks and uncommitted test plans are rejected.

| Kind | Execution |
| --- | --- |
| `pytest` | Runtime Python `-m pytest -q -p no:cacheprovider` in the declared directory; explicit project interpreter/targets supported |
| `npm` | `npm test` with `CI=1` |
| `godot` | Godot headless with a committed test script, e.g. `"script": "tests/test_states.gd"` |

See [controller validation](controller-validation.md) for interpreter selection,
scopes and cache rules. Dependencies must exist in the test environment; isolated
validation does not install packages from the network. The integrator creates test
coverage. Passing checks demonstrate those tests, not formal proof of all prose requirements.

## Failures, retry and history

**Executions** shows worker/team status, requirements checks, feature publication
and main promotion. Selecting a worker run also shows current team status. The
integration run records the commit, requirements/plan hashes, mappings and check
results. Private prompts and raw tool output do not enter public events.

- `WAITING_FOR_WORKERS`: repair/rerun failed or stale workers; successful worktrees remain.
- `FAILED`: integration/conflict/validation failure; the failed revision does not replace main.
- `INTERRUPTED`: backend stopped during integration; working files remain.
- `NEEDS_INPUT`: automatic repair stopped and requires a concrete instruction or environment fix.
- `PROMOTED`: the tested combined commit reached remote main, with controller verification.

After correction, use **Retry team integration**. Merge conflicts are handed to the
integrator to resolve, stage and commit. Retry can resume an interrupted merge.
There is no automatic reset, clean, abort or force-push. A changed main is merged
and tested again. Team workers cannot restart while their integration is active.

State and results survive backend restarts. Interrupted integration is not success.
On restart in Codex mode, enabled teams are checked for eligible worker results.

## API and evidence

- Setup: `POST /management/setup/team` with `auto_integrate: true` (implies
  `publish_results: true`); remote Git must already be enabled.
- Retry: `POST /management/projects/{id}/integrate` with `{}`.
- Status: management overview (`projects`) and existing execution/log endpoints.
- `/executions/{id}/review` remains for older clients but is not required and cannot authorize main promotion.

`test_team_integration.py` uses temporary Git repositories and actual isolated
pytest runs to test promotion, worker/test/plan/merge failures, concurrent main
updates and changed requirements. No external Git hosting or model calls are required.

### Retry appears not to start

Under Executions, team status appears directly above **Retry team integration**.
A click immediately shows the request, followed by `QUEUED`, `PREPARING`, a specific
blocker or `PROMOTED` if those exact results were already integrated. An accepted
request is not completion.

Before queuing, the controller checks the latest worker runs. Messages identify
the agent and distinguish missing/running/failed executions, missing publication,
and changed tasks/project Markdown/roles. Earlier `COMPLETED`/`PUSHED` results do
not satisfy changed instructions. Automatic integration records the same blockers.

The copyable **LAST RETRY** field keeps the last response below the button. Log
polling only updates current team status above it. Responses belong to the selected
run and survive switching runs within the Godot session. Another retry replaces
the response; after restarting the client, request it again.

### Conflicts and team recreation

Merge conflicts no longer prevent the integrator from starting. It receives existing
files, the pending merge, current requirements and exact required main/worker commits.
Only this agent may use its Git helper to merge commits approved for the current
run. Other commits, branch switches and direct pushes remain unavailable there.

Before publication and requirements validation, the controller requires a clean
project tree, no pending merge and all required commits in HEAD history. A model's
success claim is insufficient. Unresolved conflicts retain files for another attempt;
contradictory requirements may still need human clarification.

Individually deleted workers are recreated during team setup. Matching worktrees,
branches and Markdown files are reused; recreation preserves local work.

## Godot validation paths and diagnostics

Each Godot check declares a project directory relative to the integration worktree.
Its script is relative to that project directory. These forms are equivalent:

```json
{"id": "godot-contract", "kind": "godot", "directory": "frontend", "script": "tests/test_contract.gd"}
{"id": "godot-contract", "kind": "godot", "directory": "frontend", "script": "res://tests/test_contract.gd"}
```

Do not repeat `frontend/` inside `script` when `directory` already selects it.
Absolute paths, parent traversal and symlinks remain forbidden. Scripts must still
be regular committed `.gd` files with filenames starting with `test`. A committed
`smoke.gd` is a **naming-rule violation**, not a missing Git file; rename it and
update/commit the declaration to comply. The controller does not waive this rule.

The old error `Godot validation requires a committed test script` combined file
existence, filename, suffix and Git tracking checks. In commit `e38dd63`, its exact
source was `management/validation.py:100`. A `res://` declaration was incorrectly
joined as a filesystem path (`frontend/res:/tests/...`) before also receiving a
second resource prefix in the execution command. The regression fixture confirms
that the old code passed relative paths on an integration-only branch but failed
the equivalent resource URIs; the absence of these files on main was not the cause.

Validation now freezes the integration worktree's HEAD SHA, inspects its tree and
blob objects, and compares declared files using Git's content normalization rules
(including CRLF checkout attributes). `git ls-files` is no longer treated as proof
of commitment: staged-only additions do not count. The plan's requirements hash,
branch, containment, clean-tree and post-execution HEAD checks remain enforced.
Reports start with `passed: false` on every invocation and are marked successful
only after all postconditions. Publication uses the validated SHA and rejects a
HEAD change; it does not push an untested replacement HEAD. Godot error output is
also a failure even if a script exits with code zero.

Inspect **Executions → Changelog & tests → VALIDATION SNAPSHOT** for the selected
ref, branch, commit, repository and failed rule. **Live logs** additionally contain
private `validation.diagnostic` JSON records with declared directory/script,
resolved path, repository-relative Git path, blob existence/OID and exact rule.
`blob_exists: null` means lookup was not completed (for example, a Git error),
not that Git proved absence. Full test output, credentials and private prompts
are not included. These diagnostics also enter the next automatic repair context.
