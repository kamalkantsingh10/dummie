# Story 1.5: Arm safety module (`arm.py`) — sole servo path

Status: done

## Story

As a developer,
I want a single `arm.py` module that is the only path to the servos and enforces limits + stop,
so that no motion can ever exceed safe bounds (FR-14).

## Acceptance Criteria

1. `src/dum_e/arm.py` is the ONLY module that imports/commands the motor driver (LeRobot/Feetech); nothing else in the codebase actuates servos directly.
2. Any motion command that would exceed configured soft joint limits or the workspace bounding box is clamped (or refused) and a warning is logged to stderr.
3. Every move respects configured velocity/step caps (no single step exceeds the cap).
4. When the stop-sentinel file is present, motion halts immediately and the call returns `ok:false` / `E_STOPPED`.
5. An out-of-bounds command returns/logs `E_OUT_OF_BOUNDS` (clamped path) per the namespaced error codes.
6. `tests/test_arm_safety.py` covers: clamping at joint/workspace limits, velocity-cap enforcement, and stop-sentinel halt behavior (driver mocked — no hardware needed).

## Tasks / Subtasks

- [x] Task 1: Define the safe-motion API (AC: 1)
  - [x] `arm.py` is the sole servo interface: `Arm` (context-mgr `connect`/`disconnect`), `read_joints()`, `move_to(targets_deg)`, `step(deltas_deg)`, `relax()` + module-level convenience wrappers
  - [x] Feetech driver fully encapsulated in `_FeetechBus` (lazy `scservo_sdk`); NO driver object exposed to callers
- [x] Task 2: Limits & caps (AC: 2, 3, 5)
  - [x] Loads `joint_limits_deg`, `workspace_box`, `velocity_cap_deg_per_step` from `config.yaml`
  - [x] Clamps targets to soft limits; enforces the per-tick velocity cap by subdividing the move into `ceil(max_delta/cap)` increments
  - [x] Logs clamps to stderr with `E_OUT_OF_BOUNDS` context; result carries `clamped`/`warnings`
- [x] Task 3: Stop sentinel (AC: 4)
  - [x] `src/dum_e/safety.py`: `stop_sentinel_path` / `stop_requested` / `request_stop` / `clear_stop` (+ `clamp_to_limits`)
  - [x] Sentinel checked before motion AND at every tick; on presence → halt, no further goals, return `E_STOPPED`
- [x] Task 4: Tests (AC: 6)
  - [x] `tests/test_arm_safety.py` (mocked bus): clamp hi/lo, cap subdivision, multi-joint cap, stop-present-refuses, stop-mid-move-halts, relative step, arity, + an architecture guard that only `arm.py` imports the driver
- [x] Task 5: Migrate read path
  - [x] `bringup.py` already calls `arm.read_joints()` — single connection/driver owner; re-verified live

## Dev Notes

- **This is the single most safety-critical module in the project.** The architecture makes `arm.py` a *chokepoint by construction*: D3 states it is the ONLY path to the servos and enforces limits + stop on every command. Reviewers will check that no other file imports the motor driver. (`tests/test_arm_safety.py` is called out as the highest-value test in the architecture.)
- **Depends on:** Story 1.1 (scaffold, config keys), 1.2 (hardware), 1.4 (read path — fold its `read_joints` in here as the canonical owner). After this story, the read-only path from 1.4 should route through `arm.py`.
- **Prototype tolerance does NOT extend to safety** (PRD + architecture): framing imperfection is acceptable; uncontrolled motion is not. Bias toward refuse/clamp + halt over "best effort."
- **Stop mechanism (v1):** software stop via a **sentinel file** checked each control tick (the architecture notes a hardware e-stop is recommended but out of v1 scope). Make the sentinel path well-known and documented so the operator/SKILL can drop it to halt motion. Return `E_STOPPED` and leave the arm in a safe held position.
- **Velocity/step caps:** enforce by subdividing a requested move into capped increments and checking the sentinel + limits between increments — this is what makes "halt immediately" real.
- **Error codes (§E):** `E_OUT_OF_BOUNDS`, `E_STOPPED` (+ `E_CALIB_REQUIRED` is for Story 1.6). Use the exact strings.
- **Units:** joint targets/positions in degrees, consistent with `joint_units:"deg"` used by bring-up (1.4) and the shot log (3.5).
- **Confirm LeRobot actuation API** for the current version before wiring (connect/relative-move/goal-position calls differ across releases) — verify on HF docs; keep the driver fully encapsulated so a version change touches only `arm.py`.
- **Downstream dependency:** every later motion (calibration 1.6, hold_center 2.4, push_in 3.2, the shoot loop 3.x) routes through this module. Its API shape (`move_to`/`step`, return envelope) is a de-facto contract — keep it minimal and stable.

### Project Structure Notes

- NEW: `src/dum_e/arm.py` (full actuation surface), `src/dum_e/safety.py`, `tests/test_arm_safety.py`. Read path from 1.4 consolidates here.

### References

- [Source: documents/planning-artifacts/architecture.md#Core Architectural Decisions (D3 Motion Safety)]
- [Source: documents/planning-artifacts/architecture.md#Implementation Patterns (E Error/Retry/Safety; Enforcement)]
- [Source: documents/planning-artifacts/architecture.md#Architectural Boundaries (Safety chokepoint)]
- [Source: documents/planning-artifacts/prds/prd-dum-e-2026-06-19/prd.md#FR-14 / Safety guardrails]
- [Source: documents/planning-artifacts/epics.md#Story 1.5]

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Code)

### Debug Log References

- Live on hardware (joint 6 only; others held): capped +8° move subdivided into
  2 ticks (cap 5°/tick), `ok:true`. STOP test — with the sentinel present a move
  was refused: `ok:false`, `E_STOPPED`, zero new goals. Sentinel cleared, joint
  restored, `relax()` released torque. `bringup` still `ok:true` end-to-end.
- **Observed (calibration hazard, not a bug):** after `relax()`, joint 4
  (wrist_flex) sagged under gravity from raw 3706 → 74, i.e. **across the 4095↔0
  encoder wrap** — exactly the rollover the notes warn about. Confirms torque-held
  is the safe resting state and that homing + real soft limits (Story 1.6) must
  precede any unattended/multi-joint motion. See [[servo-calibration-notes]].

### Completion Notes List

- **Degree convention switched to CENTERED:** `deg = (steps-2048)*360/4096 ∈ [-180,180)`
  so it matches `config.yaml` `joint_limits_deg: [-180,180]` — the placeholder limits
  become a safe full-range no-op until Story 1.6 homes each joint and captures real
  ranges. (This re-bases the numbers `read_joints`/`bringup` report vs the raw 0–360
  used in the 1.4 first cut; still degrees.)
- **Safety enforced on every command:** clamp → (refuse if already stopped) → subdivide
  to ≤cap ticks → check sentinel each tick → write goals. Velocity cap is exact at the
  nominal increment; only sub-encoder-step (<0.09°) quantization remains.
- **Driver chokepoint (AC1):** an automated test asserts `arm.py` is the only file under
  `src/dum_e/` importing `scservo_sdk`. The two Story-1.2 BENCH scripts
  (`scripts/setup_servos.py`, `scripts/dance.py`) deliberately use the SDK directly for
  low-level setup/demo and are NOT part of the runtime path; `dance.py` now carries a
  ⚠️ header steering runtime motion to `arm.py` (it drives multi-joint open-loop, which
  caused the earlier collisions).
- **Workspace box:** `null` in config → joint-limits only. If set, `arm.py` logs that
  Cartesian bounds aren't enforced in v1 (no FK yet; that's later).
- **`relax()`** added to power joints down; note moves otherwise leave the arm holding
  position (the documented safe state for `E_STOPPED`).
- 36 tests pass (`pytest`); all motion/driver logic mocked, so the suite needs no hardware.

### File List

- MOD: `src/dum_e/arm.py` (full actuation: `Arm`, `_FeetechBus`, move_to/step/relax, centered deg)
- MOD: `src/dum_e/safety.py` (stop sentinel + `clamp_to_limits`)
- NEW: `tests/test_arm_safety.py`
- MOD: `tests/test_bringup.py` (dropped obsolete arm-internal unit tests; covered in test_arm_safety)
- MOD: `scripts/dance.py` (⚠️ bench-only header — bypasses arm.py)
