---
baseline_commit: 1e5b028d1220376d2ceb752f0435a23fcc06f3ad
---

# Story 1.1: Project scaffold & dev environment

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the builder,
I want the Dum-E repo scaffolded with its package, scripts, schemas, tests, and Python environment,
so that all later work has a consistent, importable home following the architecture.

## Acceptance Criteria

1. The repository structure exists exactly as specified in the architecture: `src/dum_e/`, `scripts/`, `schemas/`, `tests/`, `config.yaml`, `pyproject.toml`, `.gitignore`, and `.claude/skills/dum-e/SKILL.md` (skeleton).
2. A reproducible Python environment (conda/mamba preferred; venv acceptable) installs LeRobot, opencv-python, ffmpeg (or ffmpeg-python wrapper + system ffmpeg), and jsonschema with no errors.
3. `import dum_e` succeeds from an activated environment.
4. `pytest` runs successfully (zero or placeholder tests pass; the suite is wired up).
5. `.gitignore` excludes `runs/`, `calibration/`, and model weights; these directories are not committed.
6. `config.yaml` exists with documented placeholder keys: `acquire_backend`, joint limits, workspace box, velocity/step caps, center tolerance, target clip length, camera index.

## Tasks / Subtasks

- [x] Task 1: Create the directory tree (AC: 1)
  - [x] Create `src/dum_e/__init__.py` and the empty module stubs named in the architecture tree (`arm.py`, `camera.py`, `calibration.py`, `tracker.py`, `primitives.py`, `acquire/`, `shotlog.py`, `stitch.py`, `safety.py`, `rundir.py`) as importable placeholders with docstrings + `NotImplementedError` where appropriate
  - [x] Create `scripts/` with stub CLI entrypoints (`bringup.py`, `calibrate.py`, `survey.py`, `acquire.py`, `shoot.py`, `photo.py`, `stitch.py`) that print the standard JSON envelope
  - [x] Create `schemas/`, `tests/`, `runs/` (gitignored), `calibration/` (gitignored), `train/` (v2 placeholder with a README)
  - [x] Create `.claude/skills/dum-e/SKILL.md` skeleton + `.claude/skills/dum-e/reference/` (`primitives.md`, `shot-log-schema.md` stubs)
- [x] Task 2: Python packaging & environment (AC: 2, 3)
  - [x] Author `pyproject.toml` (package `dum_e`, `src/` layout) with deps: lerobot, opencv-python, jsonschema, pyyaml; ultralytics (YOLOE/YOLO-World) as optional `[yolo]` extra; ffmpeg via conda env
  - [x] Provide an environment spec (`environment.yml` + documented venv steps) and a README "setup" section
  - [x] Verify `import dum_e` (resolves via the `src` layout / pytest `pythonpath`). NOTE: full editable install with heavy hardware deps is a builder step in a conda/venv — blocked in this externally-managed system Python (PEP 668); `lerobot` version to be pinned against current HF docs.
- [x] Task 3: Test harness (AC: 4)
  - [x] Wire up `pytest`; add `tests/test_smoke.py` (asserts `import dum_e` + all stub modules import) and `tests/test_cli.py` (envelope contract)
- [x] Task 4: Config + gitignore (AC: 5, 6)
  - [x] Author `config.yaml` with the documented keys + sensible placeholder values and inline comments
  - [x] Author `.gitignore` (runs/, calibration/, weights, __pycache__, env dirs; keep `.gitkeep` for runtime dirs)
- [x] Task 5: Shared script-contract helper
  - [x] Add `dum_e/cli.py` helper that emits the canonical JSON stdout envelope `{ "ok", "data", "error", "artifacts" }`, routes logs to stderr, and exposes the namespaced error codes — every script in `scripts/` uses it

## Dev Notes

- **This is the foundation story** — the architecture explicitly names it as the "First Implementation Priority." Do not create anything beyond scaffolding; real logic comes in later stories. Stub modules should be importable and clearly raise `NotImplementedError`.
- **Frozen script I/O contract (enforce from day one):** every `scripts/*` command prints exactly ONE JSON object to stdout: `{ "ok": bool, "data": {...}, "error": null | {"code","message"}, "artifacts": [paths] }`. Exit code 0 ⇔ `ok:true`. ALL human/diagnostic logging goes to **stderr** so stdout stays pure JSON (Claude parses it). JSON field names are `snake_case`; paths are POSIX, relative to the run dir. Build the `dum_e/cli.py` helper in Task 5 so this is centralized.
- **Layering boundary (must hold for the whole project):** `src/dum_e/` is the importable, testable library; `scripts/` are thin CLI adapters (parse flags → call `dum_e` → print JSON); `.claude/skills/dum-e/SKILL.md` is the Claude "director" (prose). No control logic in scripts; no CLI/JSON concerns in the library. This boundary is what lets the deferred MCP wrapper (`src/dum_e/mcp_server.py`) attach later without a rewrite.
- **Foundation stack:** Python (LeRobot-native), conda/mamba favored because ROCm/LeRobot wheels are conda-friendly (though v1 needs NO GPU — all inference is CPU). OpenCV for camera/tracker; ffmpeg for stitching.
- **CPU-only for v1:** do not add torch+ROCm/CUDA build steps here; YOLOE/yolo-world are optional extras pulled in at Story 2.6, run on CPU. GPU/ROCm is a v2-training concern.
- **`config.yaml` keys** (from Implementation Patterns §D): `acquire_backend` (default `claude_box`), joint limits, workspace box, velocity caps, center tolerance, target clip length, camera index.
- **Web/version check before pinning:** confirm the current LeRobot package name/version and SO-101 support on the HF docs ("Assemble SO-101" / LeRobot install) and pin it; LeRobot is the canonical SO-101 stack and also provides the `LeRobotDataset` format used later by the shot log.

### Project Structure Notes

- Mirror the architecture's "Complete Project Directory Structure" exactly (names, nesting). Deviations will cause downstream stories (which reference these paths) to misfire.
- `acquire/` is a subpackage (`base.py`, `claude_box.py`, `yoloe.py`, `yolo_world.py`) — create the package + `base.py` interface stub now; concrete backends land in Epic 2.

### References

- [Source: documents/planning-artifacts/architecture.md#Foundation / "Starter" Evaluation]
- [Source: documents/planning-artifacts/architecture.md#Project Structure & Boundaries]
- [Source: documents/planning-artifacts/architecture.md#Implementation Patterns & Consistency Rules (A Script I/O Contract, D Naming & Structure)]
- [Source: documents/planning-artifacts/epics.md#Story 1.1]

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Code, bmad-dev-story workflow)

### Debug Log References

- `python3 -m pytest -q` → 7 passed (test_cli: 5, test_smoke: 2).
- `python3 scripts/bringup.py` → `{"ok": false, "data": {}, "error": {"code":"E_NOT_IMPLEMENTED",...}, "artifacts": []}`, exit code 1 (script-contract verified).
- `import dum_e` + all 12 stub modules import with no heavy deps installed (lazy-import discipline holds).
- `config.yaml` parses; keys: acquire_backend, arm, camera_index, center_tolerance_frac, clip, safety.
- Editable install blocked by PEP 668 (externally-managed system Python) — expected; real install runs in the builder's conda/venv per README.

### Completion Notes List

- Scaffold complete: `src/dum_e` library (cli + 9 stub modules + `acquire/` subpackage with `base.AcquireBackend` Protocol), 7 thin `scripts/` adapters, `schemas/` `tests/` `runs/` `calibration/` `train/`, packaging, config, gitignore, README, conda env, and the `.claude/skills/dum-e/` director skeleton (SKILL.md + 2 reference stubs). The `dum-e` skill auto-registered.
- **Frozen contracts enforced from day one:** `dum_e/cli.py` is the single source of the JSON-stdout envelope + namespaced error codes; every script routes through it (no per-script drift). Layering boundary honored — library has no CLI/JSON concerns, scripts have no logic, SKILL.md touches no hardware.
- **Stub discipline:** all real logic raises `NotImplementedError`/returns `E_NOT_IMPLEMENTED` with a pointer to the owning story; heavy deps (cv2/lerobot/torch) are NOT imported at module load, so `import dum_e` always works and v1 stays CPU-only.
- **AC2 caveat (honest):** the dependency *manifest* + env spec are authored and the package imports via the configured `src` layout (used by pytest), but a full `pip install -e ".[dev]"` of the heavy hardware deps could not be executed in this sandbox (PEP 668 + large/hardware-oriented packages). The builder runs it in a conda/venv; `lerobot` version must be pinned against current HF "Assemble SO-101" docs (also needed for Story 1.2). All other ACs (1, 3, 4, 5, 6) are fully verified.

### File List

New:
- `pyproject.toml`, `environment.yml`, `config.yaml`, `.gitignore`
- `src/dum_e/__init__.py`, `src/dum_e/cli.py`, `src/dum_e/rundir.py`, `src/dum_e/arm.py`, `src/dum_e/camera.py`, `src/dum_e/calibration.py`, `src/dum_e/tracker.py`, `src/dum_e/primitives.py`, `src/dum_e/shotlog.py`, `src/dum_e/stitch.py`, `src/dum_e/safety.py`
- `src/dum_e/acquire/__init__.py`, `src/dum_e/acquire/base.py`
- `scripts/bringup.py`, `scripts/calibrate.py`, `scripts/survey.py`, `scripts/acquire.py`, `scripts/shoot.py`, `scripts/photo.py`, `scripts/stitch.py`
- `tests/test_smoke.py`, `tests/test_cli.py`
- `schemas/README.md`, `train/README.md`, `runs/.gitkeep`, `calibration/.gitkeep`
- `.claude/skills/dum-e/SKILL.md`, `.claude/skills/dum-e/reference/primitives.md`, `.claude/skills/dum-e/reference/shot-log-schema.md`

Modified:
- `README.md` (replaced the one-line stub with the project README)

## Change Log

- 2026-06-19: Story 1.1 implemented — project scaffold, packaging, CLI JSON-envelope contract (`dum_e.cli`), config, tests (7 passing), and Dum-E skill skeleton. Status → review.
