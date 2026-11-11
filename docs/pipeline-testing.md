# Testing the complete Café pipeline

The deterministic pipeline test runs the Café's real management API, execution
controller, persistence, validation and Git publication against disposable local
repositories. A fixture produces agent implementation files instead of invoking a
paid model. Git pushes go to a temporary bare repository, never this project's
remote. This makes failure and retry behavior reproducible without credentials.

## Automated controller and regression tests

```bash
source scripts/environment.sh
python3 -m pytest backend/tests/test_pipeline_e2e.py -q
scripts/check.sh
```

The pipeline fixture exercises worker execution, integration, a failed validation
that must block promotion, a repaired retry, and an independent behavior check of
the published counter product. Assertions inspect persisted execution states and
actual Git refs, not just the agent's recap. Unit tests also protect the live smoke
runner from accepting failed execution or premature acceptance and check redacted
failure details.

## Rendered Café UI test

On Debian/Ubuntu, install the display dependencies once:

```bash
sudo apt-get update
sudo apt-get install -y xvfb xauth libxkbcommon-x11-0 libgl1-mesa-dri
```

Godot, Python dependencies and sandbox prerequisites must already be installed as
described in the main README. Run the rendered test separately:

```bash
xvfb-run -a env LIBGL_ALWAYS_SOFTWARE=1 scripts/check.sh pipeline-gui
```

With an existing usable X11 display, run `scripts/check.sh pipeline-gui` directly.
The stage fails when `DISPLAY` is missing; it does not silently fall back to
headless mode. It is opt-in locally so the normal check suite remains usable in
headless development containers. CI runs it explicitly after installing Xvfb.

The test opens the actual Café management UI and dispatches viewport mouse and
keyboard events. The UI talks over HTTP to a temporary real backend; the fixture
substitutes only agent code production and external Git transport. The runner
checks the published product independently after the GUI workflow. Godot runtime
errors or nonzero exit status fail the test.

Evidence is written under `.runtime/checks/pipeline-gui/`: rendered PNGs, Godot
output, GUI assertions, downloaded diagnostics and the final result with the
verified remote-main commit. Set `VAC_PIPELINE_ARTIFACTS` to choose another output
directory. CI uploads this directory as `cafe-pipeline-evidence` even when the test
fails. Review diagnostic contents before sharing; these are test artifacts, not
tracked project files.

## Optional real model smoke

The deterministic fixture does not prove model availability or model-generated
implementation quality. Exercise those separately with an authenticated local
Codex runtime and an explicitly selected model:

```bash
source scripts/environment.sh
python3 scripts/management_smoke.py --model gpt-5.6-luna --timeout 360
```

This opt-in command can consume model usage. It does not run in CI, does not
silently substitute a model, and never pushes to an external remote. It asks a
managed worker to implement a greeting function and unittest in a temporary
worktree. Independent checks verify behavior, tests and committed files before
acceptance. Redacted execution diagnostics are saved under
`.runtime/checks/managed-smoke/`, including on failures when a run was created.
Model access errors remain failures and must be reported as such.

## What these checks establish

A passing rendered run proves that the exercised Linux Café UI workflow reaches
the backend/controller, the declared validation gates execute, and the published
fixture product behaves as independently asserted. It does not establish full
coverage of every possible user requirement, Windows-specific window behavior,
physical display scaling, or visual quality on a real GPU. A passing live smoke
adds evidence for the selected model and small task only; it does not turn the
deterministic team fixture into a live multi-agent model test.
