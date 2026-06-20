# Story 1.4: Hardware bring-up verification (`bringup.py`)

Status: done

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

- [x] Task 1: Read-only motor comms (AC: 1, 2, 3)
  - [x] Implemented read-only `arm.read_joints()` (NO motion) via the Feetech `scservo_sdk` bus; exposes `joint_pos` (6 floats), `raw_steps`, `motor_ids`, `joint_units="deg"`
  - [x] Missing/timed-out motor or unopenable bus → `ArmError("E_NO_MOTORS")`
- [x] Task 2: Compose bring-up check (AC: 1, 2, 4)
  - [x] Implemented `scripts/bringup.py`: read joints + `camera.capture_frame`; one JSON envelope; `ok` = AND of both legs (legs run independently so partial data is reported)
- [x] Task 3: Tests
  - [x] `tests/test_bringup.py` covers both-ok / motor-fail / camera-fail / both-fail aggregation + `arm` step→deg and bus-resolution units (motor-read + camera mocked, no hardware)

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

claude-opus-4-8[1m] (Claude Code)

### Debug Log References

- Live read-only run on hardware (motor power ON):
  `ok:true`, `joint_pos=[120.15, 176.31, 65.57, 325.72, 159.08, 151.7] deg`,
  `frame_wh=[1080,1920]`. All 6 motors responded + camera captured.
- Earlier "won't move" symptom during the 5/6 jog test was the **motor power supply
  being off** — STS3215 logic is bus-powered so reads succeed without motor power.
  See [[servo-calibration-notes]].

### Completion Notes List

- **Driver decision:** used the Feetech `scservo_sdk` bus directly (NOT LeRobot —
  lerobot isn't installed; the bench tooling already uses `scservo_sdk`). The AC
  permits either; `arm.read_joints()` is a pure read with no actuation path.
- **`joint_pos` are uncalibrated raw degrees** (steps × 360/4096, 0–360). Zero/home
  and clean soft limits come in Story 1.6; bringup only needs "motors alive + position".
- **Env consolidation:** `bringup.py` needs both `cv2` (system python) and
  `scservo_sdk` (project `.venv`). Set `.venv/pyvenv.cfg`
  `include-system-site-packages = true` so `.venv/bin/python` sees the system cv2/numpy/yaml
  plus the venv's SDK. Run live with `PYTHONPATH=src .venv/bin/python scripts/bringup.py`.
- READ-ONLY honored: no `move_to` path touched; `arm.move_to` stays a Story 1.5 stub.
- 25 tests pass (`pytest`); motor + camera mocked, so the suite needs no hardware/SDK.

### File List

- MOD: `src/dum_e/arm.py` (read-only `read_joints` via scservo_sdk, `ArmError`, step→deg)
- MOD: `scripts/bringup.py` (read joints + capture → one envelope, `ok` = AND)
- NEW: `tests/test_bringup.py`
- MOD: `.venv/pyvenv.cfg` (include-system-site-packages = true — local env, not committed)
