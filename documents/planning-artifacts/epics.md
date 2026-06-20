---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - documents/planning-artifacts/prds/prd-dum-e-2026-06-19/prd.md
  - documents/planning-artifacts/architecture.md
---

# Dum-E - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Dum-E, decomposing the requirements from the PRD and Architecture into implementable stories. Dum-E is an autonomous robotic videographer built as a Claude Code Skill (Claude = director + vision brain) plus bundled Python control scripts over a `src/dum_e` library, driving an SO-101 arm.

## Requirements Inventory

### Functional Requirements

FR-1: Invoke the `dum-e` Skill in Claude Code with a single free-text line of Intent; session starts and drives off it (fails cleanly if no camera reachable).
FR-2: Scene Survey — identify the Subjects visible in the current camera frame and list them back (or report empty/unreadable frame).
FR-3: Generate an ordered Shot Plan (the "plot") from Intent + Scene Survey; each Shot names a Target + a Primitive (default 3–5 shots, 15–40s).
FR-4: Review the plan before shooting — Operator approves or edits in natural language; no arm motion until approved.
FR-5: Locate a named Target in the frame (return location/region, or "not found" → skip shot, surface miss).
FR-6: Hold-center the Target via visual servo — drive the Camera Arm so the Target is centered within tolerance; loop terminates bounded.
FR-7: Push-in Primitive — move the Camera Arm toward the Target over a few seconds while keeping it framed (smooth at prototype bar).
FR-8: Record a Clip — start/stop recording to produce one Clip per Shot; no corrupt clip on abort.
FR-9: Take a photo — capture a single still on request, independent of the video pipeline.
FR-10: Stitch Clips into a Final Video — ordered concat (+basic trim) into one playable file; count-agnostic.
FR-11: Hand-eye Self-Calibration — arm makes known moves, observes image shift, derives joint→pixel mapping; persisted; runs within safe bounds.
FR-12: Critic check before recording — evaluate the framed shot (centered/in-focus/cropped), accept or adjust+recheck (bounded retries); verdict logged.
FR-13: Training-grade Shot Log — per-Shot complete `(state → action → reward)` entry sufficient to train v2 with no extra data collection; versioned + schema-validated; non-blocking but failures surfaced; "is-it-trainable?" check.
FR-14: Safe motion bounds & stop — constrain arm motion to safe limits and halt on command (software stop).

### NonFunctional Requirements

NFR-1 (Latency/cost): The perception loop must minimize LLM round-trips — Claude is called only at semantic boundaries (survey, plan, target choice, critic); the real-time servo loop and acquire run locally on CPU.
NFR-2 (Motion safety): Bounded motion + prompt stop, enforced in the control layer independent of Claude; framing imperfection is acceptable, unsafe motion is not.
NFR-3 (Data-contract stability): The FR-13 shot-log is a versioned, LeRobotDataset-aligned schema (frozen v1.0.0); breaking it requires a schema-version bump.
NFR-4 (Determinism/repeatability): Primitives are deterministic and reproducible (and logged) so v2 can learn from them.
NFR-5 (Local/CPU): v1 runs locally; all v1 inference (acquire detector + CSRT tracker) runs on CPU. No cloud service. GPU/ROCm reserved for v2 training only.
NFR-6 (Prototype tolerance): Bar = "clearly better than a static phone clip, and autonomous"; minor framing imperfection acceptable.

### Additional Requirements

(From Architecture — technical/setup requirements affecting implementation)

- **STAGE-0 hardware prerequisite (gates everything):** assemble SO-101 per HF "Assemble SO-101" guide, mount camera, install LeRobot, `bringup.py` verifies motor comms + camera capture on this host. v1 uses ONE arm.
- **Foundation stack:** LeRobot (HF) Python for SO-101 control; Claude Code Skill format; Python (conda/mamba env); OpenCV (camera/tracker); ffmpeg (stitch).
- **Project structure:** `src/dum_e` control library (testable) · `scripts/` thin CLI adapters · `schemas/shot_log.v1.json` · `tests/` · `.claude/skills/dum-e/SKILL.md` (director).
- **Pluggable acquire backend (D5, all CPU):** `claude_box` (zero-dep default for first-light), `yoloe` (primary detector), `yolo_world` (alt). Closed-vocab models ruled out.
- **Frozen contracts (consistency rules):** script I/O = one JSON object to stdout, logs to stderr; coordinate/units conventions; shot-log writes only via `shotlog.py` against `schemas/shot_log.v1.json`.
- **Safety chokepoint:** `arm.py` is the SOLE path to servos — soft limits, velocity caps, stop-sentinel each tick.
- **Run artifacts:** `runs/<ts>/{clips,frames,shots.jsonl,plan.json}`; persisted `calibration/` profile.
- **Control-layer interface:** v1 = scripts via Bash; promote to MCP server (`mcp_server.py`, thin wrapper) when `yoloe` model-reload becomes the bottleneck (deferred).
- **Engineering spikes to resolve:** (a) Cartesian control for `push_in` — IK vs calibrated dolly-direction; (b) CPU acquire latency for `yoloe`.
- **v2 exit-criteria link:** v2 (learned cinematography policy) targeted week of 2026-06-26 → v1 must produce trainable shot logs and validate the AMD/ROCm toolchain.
- **Deferred to v2 (explicitly out of these epics):** second arm + multi-angle cutting; `orbit` & extra primitives; VLM-critic→reward learned policy; MCP wrapper; SAM2 mask-tracking.

### UX Design Requirements

N/A — Dum-E is chat-driven (Claude Code) with a single operator; no UI surface. No UX spec.

### FR Coverage Map

FR-1: Epic 4 — invoke with one-line Intent
FR-2: Epic 2 — scene survey
FR-3: Epic 4 — generate shot plan
FR-4: Epic 4 — plan review/approval
FR-5: Epic 2 — locate/acquire target
FR-6: Epic 2 — hold-center visual servo
FR-7: Epic 3 — push-in primitive
FR-8: Epic 3 — record clip
FR-9: Epic 3 — photo
FR-10: Epic 4 — stitch final video
FR-11: Epic 1 — hand-eye calibration
FR-12: Epic 2 — critic framing check
FR-13: Epic 3 — training-grade shot log
FR-14: Epic 1 — motion safety + stop

## Epic List

### Epic 1: Safe, Calibrated Camera Arm (Hardware Foundation)
A physically assembled SO-101 with a mounted camera that can be commanded safely within bounds, capture frames, and self-calibrate its hand-eye mapping — the bedrock for everything else. Includes stage-0 assembly + bring-up, project scaffolding, the `arm.py` safety chokepoint, and `camera.py`.
**FRs covered:** FR-11, FR-14

### Epic 2: Talk-to-Target Framing
You name a target in chat → Dum-E surveys the scene, locates it, drives the arm to center it in frame, and a critic confirms the framing. The "focus on the apple" milestone.
**FRs covered:** FR-2, FR-5, FR-6, FR-12

### Epic 3: Cinematic Shots — Capture & Training Logs
Dum-E performs a cinematic push-in on a framed target, records a clip (or photo), and writes a training-grade shot log of the whole thing. Opens with the Cartesian-`push_in` spike; the v1→v2 trainable-log exit criterion lands here.
**FRs covered:** FR-7, FR-8, FR-9, FR-13

### Epic 4: The Autonomous Director (End-to-End Video)
One line of intent → Dum-E invents a multi-shot plot, gets approval, shoots each shot, and stitches a finished, postable video. The actual product.
**FRs covered:** FR-1, FR-3, FR-4, FR-10

---

## Epic 1: Safe, Calibrated Camera Arm (Hardware Foundation)

A physically assembled SO-101 with a mounted camera that can be commanded safely within bounds, capture frames, and self-calibrate its hand-eye mapping.

### Story 1.1: Project scaffold & dev environment

As the builder,
I want the Dum-E repo scaffolded with its package, scripts, schemas, tests, and Python environment,
So that all later work has a consistent, importable home following the architecture.

**Acceptance Criteria:**

**Given** a fresh clone of the repo
**When** I follow the README setup
**Then** the structure exists: `src/dum_e/`, `scripts/`, `schemas/`, `tests/`, `config.yaml`, `pyproject.toml`, and `.claude/skills/dum-e/SKILL.md` (skeleton)
**And** a conda/mamba (or venv) environment installs LeRobot, opencv-python, ffmpeg, and jsonschema without error
**And** `import dum_e` succeeds and `pytest` runs (even with zero/placeholder tests)

### Story 1.2: Assemble SO-101 + mount camera (stage-0 physical)

As the builder,
I want the SO-101 (single arm) assembled with the camera mounted and motors addressed,
So that there is real hardware for the software to drive.

**Acceptance Criteria:**

**Given** the SO-101 kit and a USB camera
**When** I assemble it per the HF "Assemble SO-101" guide and set motor IDs 1–6
**Then** the arm is mechanically complete with the camera rigidly mounted to the end effector
**And** the arm and camera are connected to the host over USB and powered
**And** all 6 servos and the camera enumerate on the host (ports identified)

### Story 1.3: Camera capture API (`camera.py`)

As a developer,
I want a `camera.py` that captures a still frame to disk and reports its resolution,
So that survey, calibration, and critic steps have frames to work from.

**Acceptance Criteria:**

**Given** the mounted USB camera is connected
**When** I call the capture function (or `scripts/survey.py` in capture mode)
**Then** a frame image is saved under the run dir and `frame_wh = [w,h]` is returned
**And** the result follows the JSON-stdout contract (`ok`, `data`, `artifacts`)
**And** an unreachable camera returns `ok:false` with `E_NO_CAMERA`

### Story 1.4: Hardware bring-up verification (`bringup.py`)

As the builder,
I want `bringup.py` to verify motor comms and camera capture in one command,
So that I can confirm the rig is healthy before any motion work.

**Acceptance Criteria:**

**Given** the assembled, connected rig
**When** I run `scripts/bringup.py`
**Then** it reads all 6 joint positions (no motion) and captures one frame, emitting a single JSON status
**And** it reports `ok:true` only when both motors and camera respond
**And** a missing motor or camera yields `ok:false` with the appropriate `E_*` code

### Story 1.5: Arm safety module (`arm.py`) — sole servo path

As a developer,
I want a single `arm.py` module that is the only path to the servos and enforces limits + stop,
So that no motion can ever exceed safe bounds (FR-14).

**Acceptance Criteria:**

**Given** any motion command routed through `arm.py`
**When** the command would exceed configured soft joint limits or the workspace box
**Then** it is clamped (or refused) and a warning is logged to stderr
**And** every move respects the configured velocity/step caps
**And** when the stop-sentinel file is present, motion halts immediately and returns `ok:false` / `E_STOPPED`
**And** unit tests in `tests/test_arm_safety.py` cover bounds clamping and stop behavior

### Story 1.6: Hand-eye self-calibration (`calibrate.py` / `calibration.py`)

As the builder,
I want Dum-E to self-calibrate its joint→pixel mapping by moving and observing,
So that visual servoing is accurate without manual tuning (FR-11).

**Acceptance Criteria:**

**Given** a healthy rig (1.4) and the arm safety module (1.5)
**When** I run `scripts/calibrate.py`
**Then** the arm performs known moves (within safe bounds), observes image shift, and derives a joint→pixel mapping
**And** the calibration profile is persisted to `calibration/` and reloads on next run
**And** the routine reports `ok:true` with a basic quality metric, or `E_CALIB_REQUIRED` on failure

---

## Epic 2: Talk-to-Target Framing

You name a target in chat → Dum-E surveys the scene, locates it, drives the arm to center it, and a critic confirms the framing.

### Story 2.1: Acquire backend interface + `claude_box`

As a developer,
I want a pluggable acquire interface with a `claude_box` backend,
So that a named target can be turned into a bounding box with zero extra dependencies (FR-5, default path).

**Acceptance Criteria:**

**Given** a captured frame and a target phrase + a Claude-provided box
**When** `scripts/acquire.py --backend claude_box` runs
**Then** it returns `box = [x1,y1,x2,y2]` (abs pixels) with `frame_wh`, per the frozen coordinate convention
**And** the backend is selected via `config.yaml` `acquire_backend` through a common `AcquireBackend` interface
**And** a target that cannot be located returns `ok:false` with `E_TARGET_NOT_FOUND`

### Story 2.2: Scene survey

As the operator,
I want Dum-E to look at the scene and list the subjects it can see,
So that planning has a grounded inventory of what is filmable (FR-2).

**Acceptance Criteria:**

**Given** the camera is pointed at a populated scene (e.g. a fruit basket)
**When** the SKILL runs the survey step (via `survey.py` + Claude reading the frame)
**Then** Dum-E lists the distinguishable subjects back to the operator
**And** an empty/unreadable frame is reported as such (no invented subjects)

### Story 2.3: CSRT tracker wrapper (`tracker.py`)

As a developer,
I want a `tracker.py` that seeds a CSRT tracker from an acquire box and follows the target across frames,
So that the servo loop has a real-time, CPU-only target position (no LLM in the loop).

**Acceptance Criteria:**

**Given** an acquire box and a live camera feed
**When** the tracker is seeded and stepped
**Then** it returns the target's current center/box per frame at interactive rate on CPU
**And** on lost lock it reports the loss so the caller can re-acquire (bounded)

### Story 2.4: Hold-center visual servo (`primitives.py: hold_center`)

As the operator,
I want Dum-E to drive the arm so the named target is centered in frame,
So that the camera "covers" what I asked for (FR-6) — the focus-on-the-apple moment.

**Acceptance Criteria:**

**Given** calibration (1.6), the tracker (2.3), and the arm safety module (1.5)
**When** `hold_center(target)` runs after acquire
**Then** the target's centroid is driven to within the configured center tolerance band
**And** the loop terminates within a bounded number of steps/time (success or give-up), never infinite
**And** all motion routes through `arm.py` and respects limits/stop

### Story 2.5: Framing critic (FR-12)

As the operator,
I want Dum-E to judge whether a framed shot is actually good before committing,
So that bad framings are corrected, not recorded (FR-12).

**Acceptance Criteria:**

**Given** a held frame
**When** the SKILL critic step evaluates it (Claude reads the frame: centered? in focus? cropped?)
**Then** a verdict + score is produced, and on "not optimal" at least one bounded adjust→recheck occurs
**And** the verdict and score are captured for logging (consumed in Epic 3)
**And** retries are bounded (no stalls)

### Story 2.6: `yoloe` acquire backend + CPU-latency spike

As the builder,
I want a `yoloe` acquire backend running on CPU and its latency measured,
So that precise targeting works for hard subjects without ROCm (FR-5, precision).

**Acceptance Criteria:**

**Given** the acquire interface (2.1)
**When** I select `acquire_backend: yoloe` and run acquire on CPU
**Then** YOLOE returns a precise box for an open-vocabulary phrase with no retraining
**And** the per-acquire CPU latency is measured and recorded (acceptable = a few seconds, once per shot)
**And** if latency/integration is unacceptable, `claude_box` remains the documented default

---

## Epic 3: Cinematic Shots — Capture & Training Logs

Dum-E performs a cinematic push-in, records a clip/photo, and writes a training-grade shot log.

### Story 3.1: Cartesian-motion spike for `push_in`

As the builder,
I want to resolve how to move the camera *toward* a target while keeping it framed,
So that `push_in` has a proven control approach (IK vs calibrated dolly-direction).

**Acceptance Criteria:**

**Given** the calibrated arm and tracker
**When** I prototype a "move toward target, stay centered" motion
**Then** a working approach is chosen and documented (full IK, or a calibrated dolly-direction approximation acceptable at the prototype bar)
**And** the prototype demonstrably moves the camera closer while the target stays within the center tolerance
**And** the decision + method is recorded for Story 3.2

### Story 3.2: Push-in primitive (`primitives.py: push_in`)

As the operator,
I want a smooth push-in move on a framed target,
So that shots have cinematic motion, not a static view (FR-7).

**Acceptance Criteria:**

**Given** the approach from 3.1 and a held target
**When** `push_in(target, amount)` runs
**Then** the camera moves toward the target over a few seconds while the target stays within the center tolerance throughout
**And** the motion is smooth enough at the prototype bar (no jarring jerks) and routes through `arm.py`
**And** the move terminates cleanly and reports `ok`

### Story 3.3: Clip recording (`camera.py` recorder + `shoot.py`)

As the operator,
I want each shot recorded to a clip file,
So that there is footage to assemble (FR-8).

**Acceptance Criteria:**

**Given** a shot executing (hold_center or push_in)
**When** `shoot.py` starts the background recorder and stops it at shot end
**Then** exactly one clip file is produced per shot under `runs/<ts>/clips/` with timestamp metadata (~1080p)
**And** an aborted/failed shot leaves no corrupt clip in the set
**And** recording runs concurrently with motion without blocking the servo loop

### Story 3.4: Photo capture (`photo.py`)

As the operator,
I want to ask Dum-E for a still photo of the current/framed target,
So that I can grab stills independent of the video pipeline (FR-9).

**Acceptance Criteria:**

**Given** a live camera (optionally a framed target)
**When** I run `scripts/photo.py`
**Then** a single image file is saved and its path returned via the JSON contract
**And** it works independently of any active recording

### Story 3.5: Shot-log schema + validator (`schemas/shot_log.v1.json` + `shotlog.py`)

As the v2 trainer,
I want a frozen, validated, LeRobotDataset-aligned shot-log schema,
So that v1 capture produces directly trainable data (FR-13, the v1→v2 contract).

**Acceptance Criteria:**

**Given** the frozen schema v1.0.0 in `schemas/shot_log.v1.json`
**When** any entry is written through `shotlog.py`
**Then** it is validated against the schema and written to `runs/<ts>/shots.jsonl`, or quarantined if invalid (never partial)
**And** each entry carries `schema_version` and the full `(state → action → reward)` superset (frame ref, joint_pos, action+params+joint_target, target, critic reward, timestamps)
**And** `tests/test_shotlog_schema.py` validates good/bad entries and the LeRobot field mapping

### Story 3.6: Wire shot logging into the shoot loop + trainable check

As the builder,
I want every shot to emit a complete shot-log and pass an "is-it-trainable?" check,
So that running v1 silently accumulates the v2 dataset (FR-13 integration; v1 exit criterion).

**Acceptance Criteria:**

**Given** the validator (3.5) and a running shot
**When** `shoot.py` executes a shot
**Then** it appends one schema-valid log entry per servo tick (state+action), with the critic score (2.5) backfilled as reward at shot end
**And** logging never aborts a shoot, but any logging failure is surfaced (not swallowed)
**And** a `shots.jsonl` from a session passes a documented "is-it-trainable?" check against the v2 schema

---

## Epic 4: The Autonomous Director (End-to-End Video)

One line of intent → Dum-E plots, shoots, and stitches a finished video.

### Story 4.1: Intent intake & skill invocation (FR-1)

As the operator,
I want to invoke the `dum-e` skill in Claude Code with one line of intent,
So that I can direct by intent alone (FR-1).

**Acceptance Criteria:**

**Given** the rig is healthy
**When** I invoke the skill with a free-text intent ("make a short demo video of this fruit basket")
**Then** the session starts and drives off that intent (no structured form required)
**And** if no camera is reachable, Dum-E reports it and stops before any planning/motion

### Story 4.2: Shot-plan generation (FR-3)

As the operator,
I want Dum-E to invent an ordered shot plan from my intent and the scene,
So that the video has a deliberate plot, not random shots (FR-3).

**Acceptance Criteria:**

**Given** an intent and a completed survey (2.2)
**When** the SKILL director generates the plan
**Then** it writes `plan.json` with an ordered list of shots, each naming a surveyed subject + a v1 primitive (hold_center/push_in)
**And** the plan targets ~15–40s and ~3–5 shots by default

### Story 4.3: Plan review & approval (FR-4)

As the operator,
I want to approve or tweak the plan before the arm moves,
So that I stay in control and nothing unsafe runs unattended (FR-4).

**Acceptance Criteria:**

**Given** a generated plan
**When** Dum-E presents it
**Then** no arm motion occurs until I approve
**And** I can edit/reorder/drop shots in natural language and Dum-E regenerates the plan
**And** approval is explicit before shooting begins

### Story 4.4: Stitch final video (`stitch.py`, FR-10)

As the operator,
I want the recorded clips assembled into one finished video,
So that I get a single shareable file (FR-10).

**Acceptance Criteria:**

**Given** a set of clips from a session
**When** `scripts/stitch.py` runs
**Then** it concatenates the clips in plan order (+ basic per-clip trim) into one playable file via ffmpeg
**And** the process is count-agnostic (2 or 10 clips assemble identically)
**And** the final video path is returned via the JSON contract

### Story 4.5: End-to-end director pass (the fruit-basket video)

As the operator,
I want one intent to drive the entire pipeline to a finished clip,
So that Dum-E delivers its core promise (SM-1).

**Acceptance Criteria:**

**Given** all prior stories complete and a fruit basket in view
**When** I give one intent and approve the plan
**Then** Dum-E runs survey → plan → (per shot: acquire → hold_center/push_in → critic → record → log) → stitch with no manual framing or editing
**And** it produces a 15–40s final video I judge good enough to post
**And** the session's `shots.jsonl` is present and passes the trainable check (3.6)
