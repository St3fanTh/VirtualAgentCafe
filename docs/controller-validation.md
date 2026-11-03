# Controller validation and workflow evidence

A completed model turn, passing CLI tests, a published worker commit, integrated
code and product acceptance are separate facts. The existing execution `status`,
`acceptance` and publication fields remain compatible. The additive `workflow`
object records the distinct dimensions:

| Dimension | Values and evidence |
| --- | --- |
| implementation | `RUNNING`, `IMPLEMENTATION_COMPLETE`, `FAILED`. A completed model turn can still have unresolved tests. |
| validation | `PENDING`, `VALIDATION_PASSED`, `VALIDATION_FAILED`, `VALIDATION_INFRA_ERROR`. Controller validation is identified separately from observed worker commands. |
| integration | `INTEGRATION_PENDING`, `INTEGRATION_FAILED`, `INTEGRATED`. Integration verifies required commit objects and ancestry; promotion verifies the actual remote tip. |
| acceptance | `UNVERIFIED`, `MANUAL_ACCEPTANCE_REQUIRED`, `ACCEPTED`. Automatic acceptance applies only to the authorized automated requirements checks. Explicit desktop/product review remains separate. |

Legacy histories have no retroactively fabricated evidence. They retain their old
fields until a new run supplies verified results. `agent_commit` records the model's
Git HEAD before the controller recap commit; `submitted_commit` pins the integration
revision after the recap, and `published.commit`/`promoted.commit` record actual
publication. The recap can therefore legitimately have a different SHA than the
agent-reported implementation commit. Workers also record their integration run
and integrated commit after successful promotion.

## Reproducible checks

The committed `validation/plan.json` remains the source of controller test commands.
Paths are relative to the integration repository; Godot scripts are relative to
`directory`. Example checks:

```json
[
  {"id": "backend", "kind": "pytest", "directory": "backend", "targets": ["tests"]},
  {"id": "protocol", "kind": "godot", "directory": "frontend", "script": "res://tests/test_protocol.gd"}
]
```

For pytest, `targets` is optional: without it, pytest collects normally from the
specified directory using that project's pytest configuration. Explicit targets
are file/directory paths, not arbitrary command options or shell expressions.
`script` is Godot-only; it is rejected for other tools rather than silently ignored.

Python defaults to the executable in the sandbox's fixed runtime PATH
(`/opt/venv/bin`, `/usr/local/bin`, `/usr/bin`, `/bin`), not an inaccessible host
controller virtualenv. A check can explicitly select `"python": "project-venv"`
to use `<directory>/.venv/bin/python`. Provision its dependencies before validating;
there is no implicit pip install, shell activation, credential forwarding or network.
Missing interpreters/dependencies are blockers, not proof that implementation code
is defective. Arbitrary host paths are not permitted.

Controller tests require the expected branch, exact submitted commit, committed
requirements/plan/scripts and a clean workspace before and after execution. Tests
cannot use the run-specific `.cafe` directory; it is masked in their namespace.
Existing mandatory requirements and publication checks remain active.

## Failure evidence and private output

`Executions` shows the workflow, implementation commit, selected revision, directory,
command, scope, cache use, diagnostic category and exact failed validation rule.
Categories distinguish `TEST_FAILURE`, `COLLECTION_ERROR`, `ENVIRONMENT_ERROR`,
`INTERRUPTED`, `TOOL_ERROR`, `CONFIGURATION_ERROR` and `UNCLASSIFIED_ERROR`.
An import failure can mean a missing dependency **or** an incorrect project import;
the category does not claim a confirmed underlying cause. Unknown nonzero exits
never become asserted implementation defects. Godot error markers fail a check
even if its process returns zero.

Complete controller stdout/stderr are persisted separately in the existing SQLite
store, accessible only through the authenticated management API:

- `GET /management/executions/{execution}/validation-output/{check}`: separate
  `stdout`, `stderr`, exit code and context. Each stream is bounded at 1 MiB;
  exceeding the limit explicitly fails and marks `truncated`, never passes silently.
- `GET /management/executions/{execution}/runtime-test-output`: original Codex
  test commands, available cwd, observed Git commit, exit code and combined output.
  Codex supplies aggregated output; separate streams/provider-side truncation are
  unknown. Up to 100 test-command records are retained per execution. A missing
  provider cwd is reported as unknown, not inferred from the shell command.

Raw output is private and may contain project data or secrets emitted by tests.
It is excluded from public WebSocket events, ordinary logs, overview responses and
repair prompts. Do not commit or share the runtime database. Sanitized causes and
safe test IDs remain in logs and bounded repair context. Historical executions
cannot recover output that the previous version discarded.

## Cache and retries

Only controller-verified passing checks are cached, after final commit/cleanliness
and environment checks. Keys include full commit, repository/cwd, complete plan,
requirements snapshot, test command/scope, timeout, isolation version and runtime
identity (tool binaries, installed package versions/file metadata and platform).
Changing code, configuration, dependencies or integration revision invalidates reuse.
Ignored non-controller files such as `.venv`, `node_modules` or generated Godot
artifacts disable reuse because Git cannot certify their contents. Failed results
are never cached as successes. A passing check can be reused while a different
check at the same revision is retried.

There is no automatic "affected tests" guessing: a full integration commit change
reruns all declared mandatory suites. Explicit pytest targets define a bounded
scope when the requirements permit it. Workers' self-reported successes are not
controller cache entries.

CLI failures are tracked by command/cwd scope. A passing frontend command cannot
clear a backend failure, nor can a successful subset clear a different full-suite
failure. Repeat the failed scope successfully to resolve it. Presentation-only pytest verbosity flags (such as `-q`) do not create a new
scope. Interpreter, directory, selectors and configuration remain significant;
other different command spellings are conservatively kept separate.

Known test failures can use the existing bounded repair budget. Infrastructure,
collection/configuration and unexplained failures stop speculative code-repair
loops and retain their evidence. Fix the environment/configuration or clarify the
blocker, then retry explicitly. Repeated identical repair evidence and exhausted
budgets still pause as `NEEDS_INPUT`; ordinary completion notifications do not
restart that failed attempt indefinitely.

## Manual product acceptance

A plan can add `"manual_acceptance": ["Check desktop input and rendering"]`.
This records product checks **after the previously authorized automated main
publication**. It is not permission to bypass a pre-publication approval policy;
projects needing such approval must not enable automatic main promotion.

After all automated gates and verified promotion, this execution and its workers
remain `MANUAL_ACCEPTANCE_REQUIRED` until reviewed through the existing execution
review API. Review updates the linked records, not newer independent executions.
Unrelated worker tasks may continue; a manual product check is not a global lock.
An accepted model response alone never satisfies controller tests or Git ancestry.

## Limits of the reported incident

Project commits `7f10fb7` and `063bd3f` were not present in the development environment.
Their actual test output, dependency set and integration/desktop acceptance cannot
be reconstructed here. The fixes were reproduced with local temporary Git
repositories, real sandboxed pytest/Godot executions and deterministic Codex events;
no claim is made that those two external commits have passed controller validation.

## Godot user data in managed runs

Both controller checks and Codex workers receive `XDG_DATA_HOME`, `XDG_CONFIG_HOME`
and `XDG_CACHE_HOME` under `/tmp/vac-user/` inside the per-process private tmpfs.
This lets Godot create `user://` logs and saves under its data directory, even inside
Codex's nested workspace-write policy. The data is ephemeral: separate runs start
with fresh user data. Keep durable project results in the assigned workspace.

Host home directories, credentials and other workspaces remain hidden; Git metadata
retains its existing read-only protections. No broader HOME write permission or
sandbox bypass is needed. If Godot reports `Error attempting to create data dir`,
the observer/controller classify an environment error rather than a code-test defect.
The observer also recognizes this specific startup failure through wrapper commands;
a completed model turn cannot clear the observed failure.

After updating, rebuild/restart the backend through the project starter, preserving
its project selection/options and volumes. Retry the affected frontend task; use
**Retry team integration** if the integration worker was blocked. The model's final
text is not controller publication evidence: inspect the execution's **Git: PUSHED**
and recorded branch/commit. Historical outputs are not retroactively reclassified.

### Rerun Godot after repairing its environment

A clean repeat of the same Godot command/cwd resolves earlier observed failures
when only leading XDG data/config/cache/runtime or Fontconfig assignments changed.
These variables repair runtime directories/fonts without selecting a different test.
The optional plain `env` launcher is normalized too. Other environment assignments,
executables, project paths, scripts, test arguments and cwd remain significant.
Complex shell setup is conservatively kept distinct rather than guessed equivalent.
This normalization only links observed attempts; controller validation/cache still
checks its exact revision, configuration and environment independently.

Earlier failed attempts remain in history as superseded. A zero-exit run containing
Godot ERROR/SCRIPT ERROR output is still unsuccessful, even when it also prints PASS.
A model's prose assertion does not resolve a failure: a clean observed rerun is required.
