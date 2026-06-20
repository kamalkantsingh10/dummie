# Story 1.5: Arm safety module (`arm.py`) — sole servo path

Status: ready-for-dev

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

- [ ] Task 1: Define the safe-motion API (AC: 1)
  - [ ] Implement `arm.py` as the sole servo interface: `connect()`, `read_joints()` (reuse/relocate from 1.4), `move_to(joint_target)` / `step(joint_delta)`, `disconnect()`
  - [ ] Internally own the LeRobot/Feetech driver handle; expose NO driver object to callers
- [ ] Task 2: Limits & caps (AC: 2, 3, 5)
  - [ ] Load soft joint limits, workspace box, velocity/step caps from `config.yaml`
  - [ ] Clamp (or refuse) any target outside limits; enforce per-step velocity caps by subdividing moves
  - [ ] Log clamps/refusals to stderr with `E_OUT_OF_BOUNDS` context
- [ ] Task 3: Stop sentinel (AC: 4)
  - [ ] Implement `src/dum_e/safety.py`: stop-sentinel file path + check helper + set/clear helpers
  - [ ] Check the sentinel at every control tick inside `arm.py`; on presence, halt immediately and return `E_STOPPED`
- [ ] Task 4: Tests (AC: 6)
  - [ ] `tests/test_arm_safety.py` with a mocked driver: assert clamping, cap subdivision, and immediate stop on sentinel
- [ ] Task 5: Migrate read path
  - [ ] Ensure `bringup.py` (1.4) and any reader uses `arm.read_joints()` so there is exactly one connection/driver owner

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

### Debug Log References

### Completion Notes List

### File List
