# Story 1.4: Hardware bring-up verification (`bringup.py`)

Status: ready-for-dev

## Story

As the builder,
I want `bringup.py` to verify motor comms and camera capture in one command,
so that I can confirm the rig is healthy before any motion work.

## Acceptance Criteria

1. `scripts/bringup.py` reads all 6 joint positions from the SO-101 (read-only, NO motion) and captures one frame, emitting a single JSON status object.
2. It reports `ok:true` only when BOTH the 6 motors respond AND the camera captures successfully.
3. A missing/unresponsive motor yields `ok:false` with an appropriate error code; an unreachable camera yields `ok:false` / `E_NO_CAMERA`.
4. The JSON `data` includes the read joint positions (with `joint_units`) and the captured frame's `frame_wh`; the frame path is in `artifacts`.

## Tasks / Subtasks

- [ ] Task 1: Read-only motor comms (AC: 1, 2, 3)
  - [ ] Implement a read-only joint-read in `src/dum_e/arm.py` interface surface (a `read_joints()` that does NOT command motion) OR a minimal LeRobot connection read; expose `joint_pos` (6 floats) + `joint_units` ("deg")
  - [ ] Map a missing/timed-out motor to a typed error (e.g. `E_NO_MOTORS` / appropriate `E_*`)
- [ ] Task 2: Compose bring-up check (AC: 1, 2, 4)
  - [ ] Implement `scripts/bringup.py`: read joints + call `camera.py` capture; combine into one JSON envelope; `ok` is the AND of both
- [ ] Task 3: Tests
  - [ ] Unit test the envelope/aggregation logic with mocked motor-read + camera (no hardware needed)

## Dev Notes

- **Depends on:** Story 1.2 (hardware + ports), Story 1.3 (`camera.py` capture). 
- **READ-ONLY — no motion in this story.** `bringup.py` must only *read* joint positions and *capture* a frame. Do NOT command any movement; motion is gated on the `arm.py` safety module (Story 1.5). If a `read_joints()` helper is added to `arm.py` now, it must be a pure read with no actuation path.
- **Connection ownership:** use LeRobot's SO-101 connection to read joint state; pull the serial `port` from `config.yaml` (set in 1.2). Confirm the exact LeRobot read API for the current version (verify on HF docs) — the method names for connecting/reading follower state evolve across LeRobot releases.
- **Script I/O contract (§A):** single JSON object to stdout; logs to stderr; use `dum_e/cli.py`. `ok:true` ONLY when motors AND camera both succeed (logical AND). Reuse `E_NO_CAMERA` for the camera leg.
- **`joint_units`:** report in degrees and include `joint_units: "deg"` to match the frozen coordinate/units convention used by the shot log later (Story 3.5). If LeRobot reports a different unit, document it and convert (or set `joint_units` accordingly) — consistency with the shot-log schema matters.
- **Purpose:** this is the green-light gate for all motion work. Keep it fast and unambiguous so the builder can re-run it after any re-cabling.

### Project Structure Notes

- NEW: `scripts/bringup.py`; minimal read-only addition to `src/dum_e/arm.py` (`read_joints`). The actuation surface of `arm.py` (limits, stop, move) is built in Story 1.5 — keep the read path separable.

### References

- [Source: documents/planning-artifacts/architecture.md#Project Structure (scripts/bringup.py, arm.py)]
- [Source: documents/planning-artifacts/architecture.md#Implementation Patterns (A Script I/O, B units, E error codes)]
- [Source: documents/planning-artifacts/epics.md#Story 1.4]
- External: LeRobot SO-101 docs (https://huggingface.co/docs/lerobot/main/en/assemble_so101)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
