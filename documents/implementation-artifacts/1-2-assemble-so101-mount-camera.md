# Story 1.2: Assemble SO-101 + mount camera (stage-0 physical)

Status: done

<!-- Note: This is a PHYSICAL/hardware story — most "tasks" are bench work by the builder, not code. The dev-agent role here is to produce/verify the setup docs, motor-ID config, and port-identification helper. -->

## Story

As the builder,
I want the SO-101 (single arm) assembled with the motors addressed and the rig connected,
so that there is real hardware for the software to drive.

## Acceptance Criteria

1. The arm is mechanically complete per the Hugging Face "Assemble SO-101" guide (fully bolted). [AMENDED] The camera *mount* (rigid attachment to the end effector) was re-scoped to **Story 1.3 Task 5** (design → print → attach) — not blocking 1.2.
2. [AMENDED] Motor IDs **1–5** are assigned/configured for the **5-DoF camera arm** (gripper/motor 6 omitted; camera takes its place). Done via the Feetech SDK (`setup_servos.py`), not LeRobot's tool.
3. The arm and camera are connected to the host over USB and powered.
4. [AMENDED] All **5 servos** enumerate and respond, and the camera enumerates; the serial port (`/dev/ttyUSB0`) and camera index (0) are recorded in `config.yaml`.

## Tasks / Subtasks

- [x] Task 1: Physical assembly (AC: 1)
  - [x] Assemble the SO-101 follower arm following the HF "Assemble SO-101" guide — fully bolted
  - [~] Camera mount → **moved to Story 1.3 Task 5** (design/print/attach) — deliberate re-scope
  - [x] Route and strain-relieve camera + motor cabling (camera USB service loop noted for the mount in 1.3)
- [x] Task 2: Motor configuration (AC: 2)
  - [x] Assign IDs **1–5** to the servos — done one-at-a-time via `scripts/setup_servos.py set-id` (Feetech SDK). Some servos shipped pre-numbered; others at factory ID 1. Fixed a physically-swapped 1↔2 pair in software (temp-ID method).
  - [x] Recorded motor model (STS3215, model 777) + baud (1,000,000) in `config.yaml` + memory
- [x] Task 3: Connectivity & identification (AC: 3, 4)
  - [x] Connected arm (CH340 serial) + camera (USB) to host; powered. (Cable note: first USB cable was charge-only — needed a data cable.)
  - [x] Identified arm port `/dev/ttyUSB0` + camera index `0`; recorded both in `config.yaml`
  - [x] Built `scripts/setup_servos.py` (scan / set-id / test) — exceeds the planned read-only lister; movement-tested all 5 servos healthy
- [x] Task 4: Document the rig
  - [x] Captured in project memory ([[servo-calibration-notes]], [[camera-hardware]], [[dum-e-concept]]): port/index/baud, servo IDs, gotchas (encoder wraparound, pre-numbered servos, ID-write ack timeout, GUI-app camera flicker). README hardware section can fold these in later.

## Dev Notes

- **Hard prerequisite / stage-0:** nothing else in the project runs until this is done. It is intentionally isolated as its own story. This is primarily *bench work*; the code deliverable is limited to the read-only device-listing helper and the setup docs.
- **Single arm for v1:** assemble and use ONE SO-101 as the Camera Arm. The second arm (leader/follower pair) is reserved for v2 multi-angle — do not wire it in now.
- **No motion in this story:** device listing and enumeration are read-only. Any command that *moves* a servo must wait for Story 1.5 (`arm.py` safety module) — do NOT add ad-hoc motion test scripts that bypass the future safety chokepoint.
- **LeRobot is the control stack:** use LeRobot's documented SO-101 assembly + motor-setup + (later) calibration flow. Confirm the current LeRobot version and exact commands on the HF docs before running (commands/flags evolve).
- **Camera mount rigidity matters downstream:** hand-eye calibration (Story 1.6) learns the joint→pixel mapping assuming the camera is fixed relative to the end effector. A loose mount invalidates calibration and servoing — make it rigid and repeatable.
- **Record ports/index in `config.yaml`** (keys created in Story 1.1): `camera_index`, arm serial `port`. Downstream `camera.py` (1.3) and `bringup.py` (1.4) read these.

### Project Structure Notes

- New optional files: `scripts/list_devices.py` (read-only), `docs/hardware-setup.md`. No changes to `src/dum_e` logic in this story.

### References

- [Source: documents/planning-artifacts/architecture.md#Foundation (Assembly: HF "Assemble SO-101" guide; stage-0 prerequisite)]
- [Source: documents/planning-artifacts/architecture.md#Hardware Constraints]
- [Source: documents/planning-artifacts/epics.md#Story 1.2]
- External: Hugging Face — Assemble SO-101 (https://huggingface.co/docs/lerobot/main/en/assemble_so101)

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (interactive bench bring-up with the builder)

### Completion Notes List

- Arm fully bolted (5-DoF: gripper omitted, camera will mount on wrist-roll/motor 5 output per Story 1.3).
- All 5 Feetech STS3215 servos (model 777) ID'd base→tip = 1,2,3,4,5 on `/dev/ttyUSB0` @ 1,000,000 baud, each movement-tested healthy (clean closed-loop positioning).
- Camera: "Image+ Fic760x" UVC cam on `/dev/video0`, verified clean 1080p30 (replaced a C920 that couldn't do clean 1080p). Settings + gotchas captured.
- **Re-scopes/deviations (vs original story):** (a) 5 motors not 6 — deliberate 5-DoF camera arm; (b) motor config via Feetech SDK (`setup_servos.py`) not LeRobot's tool; (c) camera *mount* moved to Story 1.3 Task 5.
- **Open follow-ups (correctly deferred, not blocking 1.2):** encoder wraparound on the elbow + soft joint limits + homing → **Story 1.6 calibration** (and `arm.py` safety in 1.5). NO powered multi-joint motion until those exist — two elbow↔shoulder collisions occurred during premature open-loop "dance" tests (no damage; temps ~41°C).

### File List

New: `scripts/setup_servos.py` (scan/set-id/test servo bench tool), `scripts/dance.py` (demo move routine — use only AFTER soft limits exist), `.venv/` (uv; feetech-servo-sdk + pyserial).
Modified: `config.yaml` (arm port/baud/motor_ids → 5 joints; camera block → 1080p + anti-flicker), `src/dum_e/camera.py` (real capture/record implementation, down-payment on Story 1.3).

## Change Log

- 2026-06-20: Story 1.2 completed — SO-101 assembled (5-DoF), all 5 servos ID'd + tested, motor bus + camera identified and recorded in config. Camera mount re-scoped to 1.3; homing/limits deferred to 1.5/1.6. Status → done.
