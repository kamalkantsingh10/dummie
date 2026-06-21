---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - documents/planning-artifacts/prds/prd-dum-e-2026-06-19/prd.md
  - documents/brainstorming/brainstorming-session-2026-06-19-1434.md
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-06-19'
project_name: 'dum-e'
user_name: 'Kamal'
date: '2026-06-19'
---

# Dum-E — Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (14):** Group into pipeline stages — intake/survey (FR-1,2), planning (FR-3,4), targeting/framing (FR-5,6), move primitives (FR-7), capture (FR-8,9), assembly/stitch (FR-10), calibration (FR-11), critic (FR-12), training-grade logging (FR-13), safety (FR-14). The FRs map almost 1:1 to a linear director pipeline: Survey → Plan → (per shot: Locate → Frame → Move → Critic → Record → Log) → Stitch.

**Non-Functional Requirements (architecture-driving):**
- **Latency/cost of the perception loop** is the dominant NFR — every "Claude sees a frame" is a round-trip; loop ownership must minimize these.
- **Motion safety** — bounded motion + prompt stop, enforced in the control layer independent of Claude.
- **Data contract stability** — FR-13 log is a versioned schema consumed by v2 (week of 2026-06-26); breaking it later is expensive.
- **Determinism/repeatability** — primitives must be reproducible (and logged) for v2 to learn from.
- **Prototype tolerance** — framing imperfection acceptable; motion safety is not.

### Scale & Complexity
- Primary domain: robotics control + agentic Claude-Code Skill orchestration.
- Complexity level: medium (unusual shape; low data/no compliance, but real-time control + human-safety + forward ML data contract).
- Estimated architectural components: ~6-8 control scripts + 1 Skill instruction set + 2 persistent stores (calibration, shot log).

### Technical Constraints & Dependencies
- Runtime brain = Claude Code (no separate VLM, no Anthropic API).
- Control = Python/CLI scripts invoked via Bash (MCP-wrappable later).
- SO-101 arm control via LeRobot/Feetech Python [ASSUMPTION]; camera via USB webcam; stitch via ffmpeg.
- Host = desktop with AMD GPU → ROCm (not CUDA). NOT needed for v1 (all v1 inference — acquire detector + CSRT tracker — runs on CPU). ROCm needed only for v2 training; toolchain risk deferred to v2.
- STAGE-0 PREREQUISITE: SO-101 arms (leader+follower) not yet assembled; assembly + camera mount + USB bring-up gates all software.
- v1 = ONE camera arm; second arm + multi-angle cutting deferred to v2.

### Cross-Cutting Concerns Identified
- **Perception-loop ownership** (Claude-per-step vs script-autonomous servo) — the pivotal decision; drives latency, cost, and the safety model.
- **Motion safety** — enforced in control layer, every motion command.
- **Persistent state** — calibration profile + shot log survive across runs.
- **Claude↔script interface contract** — how Claude passes intent/targets to scripts and reads structured results back (incl. frames).
- **FR-13 log schema** — single source of truth shared by v1 capture and v2 training.

## Foundation / "Starter" Evaluation

### Primary Technology Domain
Robotics control + agentic Claude-Code Skill — NOT a web/mobile/API app, so conventional web starters (Next.js/Vite/etc.) do not apply. Foundations are chosen per layer instead.

### Foundations Selected (per layer)

**Hardware / control layer → LeRobot (Hugging Face), Python.**
- Provides: SO-101 motor config, hand-eye/arm calibration, teleop, synchronized camera + trajectory recording, and the `LeRobotDataset` format + training stack.
- Rationale: it is the canonical SO-101 stack; reusing it avoids reinventing motor control, calibration, capture, AND the training data format.
- Assembly: follow HF "Assemble SO-101" guide (stage-0 prerequisite).
- **LeRobot adoption boundary (v1) — bus + calibration, NOT the follower robot.** `arm.py`'s driver sits on LeRobot's `lerobot.motors.feetech.FeetechMotorsBus` (which wraps `scservo_sdk`) for wire protocol + torque control, exchanging RAW encoder steps (`normalize=False`) so Dum-E's own centered-degrees math and soft limits need no LeRobot calibration dict. The servo joint-range calibration (FR-11 / Story 1.6) leans on LeRobot's calibration facility (homing offsets + range-of-motion). We deliberately do **NOT** adopt the `SOFollower` robot class in v1: it bundles camera ownership (conflicts with our tuned `camera.py`), ships only a coarse `max_relative_target` safety clamp (weaker than the FR-14 chokepoint, which we'd have to wrap it in anyway), and assumes a gripper on motor 6 (ours is a camera-pan half-leader). Its real payoff — normalized observation/action spaces for dataset recording + policy rollout — lands in v2; adopt `SOFollower` then.

**Director layer → Claude Code Skill format.**
- The repo already uses the Skill convention (`.claude/skills/*`). Dum-E ships as a skill: instruction set (director logic) + bundled Python control scripts.

**Language / runtime → Python (LeRobot-native).**
- Env management: conda/mamba favored (ROCm wheels are conda-friendly) [ASSUMPTION].
- Camera: OpenCV [ASSUMPTION]; video stitch: ffmpeg.

### KEY DECISION: FR-13 Shot Log aligns to `LeRobotDataset`
The training-grade Shot Log (FR-13) will conform to / wrap the `LeRobotDataset` episode format (synchronized frames + arm state + action + extra fields for target & critic-score reward). This makes v2 training (already supported on ROCm via LeRobot) close to drop-in, directly de-risking the 2026-06-26 v2 target.

### ROCm note (Open Q6)
LeRobot + ROCm training is demonstrated by AMD — but on Instinct-class GPUs. Consumer Radeon ROCm support must be validated on Kamal's specific GPU before committing v2 to on-device training (carry as a stage-0/early spike).

### First implementation story
Stage-0 hardware bring-up: assemble SO-101 (HF guide), install LeRobot, verify motor comms + a teleop/record round-trip + camera capture on this host.

**Sources:** [Assemble SO-101 (HF)](https://huggingface.co/docs/lerobot/main/en/assemble_so101) · [AMD ROCm + LeRobot fine-tuning](https://rocm.blogs.amd.com/artificial-intelligence/rocm-lerobot/README.html) · [SO-101 RL on AMD ROCm](https://ggando.com/blog/so101-rl-lift/) · [Edge-to-Cloud Robotics with ROCm](https://rocm.blogs.amd.com/artificial-intelligence/rocm-blogsblogsartificial-in/README.html)

## Core Architectural Decisions

### Decision Priority Analysis
**Critical (block implementation):** D1 perception-loop ownership (supervised split); D2 Claude↔script interface; D3 motion safety; D4 shot-log = `LeRobotDataset`-aligned.
**Important (shape architecture):** D5 acquire = pluggable backend; D6 process/concurrency; D7 script decomposition + run-dir layout.
**Deferred (v2):** second arm + multi-angle cutting; orbit & extra primitives; learned policy (consumes `LeRobotDataset` logs); MCP wrapper; SAM2 mask-tracking; GroundingDINO/OWLv2 precision-acquire.

### D1 — Perception-Loop Ownership: SUPERVISED SPLIT (Option B) — CONFIRMED
Claude owns semantics + taste (survey, plot, target selection, critic); a local Python script owns the real-time servo loop (no LLM in the hot loop). Satisfies the dominant latency/cost NFR; smooth motion at the prototype bar. Affects FR-5,6,7,12.

### D5 — Acquire = PLUGGABLE BACKEND (research-informed)
The acquire step (named target → bounding box that seeds the tracker) is implemented as a **pluggable backend interface** with three selectable implementations.

**KEY INSIGHT — acquire runs ONCE per shot, so it runs on CPU.** Acquire is NOT in the hot loop (the real-time loop is the CSRT tracker, D6, already CPU). The detector fires once per shot, between moves, to seed the box — a brief setup pause the viewer never sees. So it need not be real-time: a ~0.5–3 s CPU inference is fine. **This removes ROCm from the entire v1 critical path; GPU/ROCm is reserved for v2 training only.**

- **`claude_box` (zero-dependency default for first-light):** Claude reads the frame (Read tool) and returns an approximate `[x1,y1,x2,y2]`. Anthropic docs confirm this works but is *approximate* — fine to seed a tracker for large/distinct subjects (the fruit MVP), not for small/precise targets. Lets the end-to-end loop work before any model is installed.
- **`yoloe` (PRIMARY "real" detector, CPU):** open-vocab, **+3.5 AP & 1.4× faster** than YOLO-World-v2-S, plus a *visual-prompt* mode (good for hard targets like "the gripper's fingertip"). License = **AGPL-3.0** — a NON-ISSUE: project ceiling is **personal → at most open-source** (decided 2026-06-19), AGPL-compatible. Runs on CPU (PyTorch-CPU or ONNX-Runtime-CPU); precomputed text embeddings ("prompt-then-detect") mean CPU inference is just a CNN forward pass. Chosen as primary on raw capability now that license is not a constraint.
- **`yolo_world` (alternative, CPU):** functionally-equivalent open-vocab detector (GPL-v3); known ONNX export path. Fallback if YOLOE is harder to run.
- **Ruled out:** YOLOv12, RF-DETR (closed-vocabulary — can't do phrase→box without retraining); NanoOWL (fast but NVIDIA-TensorRT only, unavailable on AMD).
- **Acquire chain:** Claude picks the Target *phrase* (semantics) → selected backend returns the *box* (CPU) → CSRT tracker holds it real-time (D6) → Claude critic judges (FR-12). Re-acquire on lost lock (bounded retries).
- **Low-risk spike (replaces the ROCm blocker):** confirm a small YOLOE/YOLO-World variant returns a box in an acceptable few-seconds on Kamal's CPU. (ROCm validation, Open Q6, is now a v2-training concern, not a v1 blocker.)

### D2 — Claude↔Script Interface Contract
Control layer = CLI scripts invoked via Bash; each prints a single structured **JSON result to stdout** (status, measured values, output paths). Frames/clips written as files into the run dir; **Claude reads frame images with its Read tool** to "see" (survey, acquire-phrase, critic). No server in v1; MCP wrapper deferred.

### D3 — Motion Safety (FR-14)
A single `arm` control module is the ONLY path to the servos. Every command passes through it; it enforces soft joint limits, a workspace bounding box, and velocity/step caps, and checks a **stop sentinel file** each control tick. Calibration moves (FR-11) run inside the same bounds. Prototype tolerance applies to framing, NOT motion safety.

### D6 — Process / Concurrency Model
One active Camera Arm. A **shoot** runs: acquire → start background recorder (OpenCV/ffmpeg writer) → run servo+primitive (logging each tick) → stop recorder → critic. Primitives are blocking; calibrate/stitch are one-shot. **Tracker = CSRT (OpenCV, CPU)** for v1 — no ROCm dependency, keeps the hot loop robust regardless of detector backend. **SAM2 mask-tracking** noted as a v2 upgrade (heavier; ROCm feasibility TBD).

### D4/D7 — Persistence & Script Decomposition
Per-session `runs/<timestamp>/`: `clips/`, `frames/`, `shots.jsonl` (`LeRobotDataset`-aligned: synced frame refs + arm state + action + Target + critic-score reward + schema_version + timestamps). Validated on write (FR-13). Persistent `calibration/` profile (reuse LeRobot calibration). Bundled scripts: `bringup`/`calibrate`, `survey`, `acquire` (pluggable backend), `shoot` (track+servo+primitive+record+log), `photo`, `stitch`. Skill instruction file = the director that orchestrates them.

### Decision Impact Analysis
**Implementation sequence:** stage-0 hardware bring-up + calibration → arm safety module → acquire (`claude_box` first; swap to `yoloe` on CPU after the CPU-latency spike) → tracker+servo (hold-center) → push-in → record → shot-log (`LeRobotDataset`) → critic → stitch → end-to-end director pass. (GPU/ROCm not on the v1 path — reserved for v2 training.)
**Cross-component dependencies:** the `arm` module underpins all motion; the tracker depends on the acquire seed; the shot-log schema is shared by capture (v1) and training (v2) and must be frozen before first real shoots.

### References / Further Reading (from research + paper hunt)
**Decision evidence (deep-research, adversarially verified):** [YOLOE docs](https://docs.ultralytics.com/models/yoloe) · [YOLOE repo](https://github.com/THU-MIG/yoloe) · [YOLO-World docs](https://docs.ultralytics.com/models/yolo-world) · [YOLO-World repo](https://github.com/ailab-cvc/yolo-world) · [Ultralytics license (AGPL-3.0)](https://www.ultralytics.com/license) · [RF-DETR](https://github.com/roboflow/rf-detr) · [Jetson open-vocab speed study (Frontiers)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12583037/) · [ONNX YOLO-World path](https://ibaigorordo.github.io/posts/ONNX-YOLO-World-Open-Vocabulary-Object-Detection/) · [Anthropic vision (approx boxes)](https://docs.anthropic.com/en/docs/build-with-claude/vision) · [ROCm on consumer GPUs (2026 guide)](https://dev.to/kunal_d6a8fea2309e1571ee7/amd-rocm-on-consumer-gpus-the-open-source-cuda-alternative-that-actually-works-now-2026-guide-1cn5)
**Key papers:** YOLO-World (arXiv:2401.17270) · YOLOE (arXiv:2503.07465) · Grounding DINO (arXiv:2303.05499) · OWLv2 (arXiv:2306.09683) · SAM 2 (arXiv:2408.00714) · CLIP (arXiv:2103.00020) · OVD survey (arXiv:2307.09220) · HiFi-CS robotic grounding (arXiv:2409.10419)

## Implementation Patterns & Consistency Rules

### A. Script I/O Contract (every control script)
- Each control script is a CLI command; args via `--flags`.
- Writes **exactly one JSON object to stdout**, nothing else: `{ "ok": bool, "data": {…}, "error": null | {"code","message"}, "artifacts": [paths] }`
- Exit code 0 ⇔ `ok:true`. ALL human/diagnostic logging goes to **stderr** (stdout stays pure JSON so Claude can parse it).
- JSON field names = `snake_case`. Paths = POSIX, relative to the run dir.

### B. Coordinate & Units Conventions (frozen)
- Bounding box = `[x1, y1, x2, y2]`, absolute integer pixels, origin top-left. Always paired with `frame_wh = [w, h]` (never bare normalized coords).
- Arm pose = fixed-order 6-element array `joint_pos`, unit `deg`, recorded with `joint_units` (matches LeRobot reporting; document if it differs).
- Time = both `t_iso` (ISO-8601 UTC) and `t_ms` (monotonic ms since shot start).

### C. FR-13 Shot-Log Schema — FROZEN v1.0.0 (shared by v1 capture + v2 training)
One JSONL line per servo tick in `runs/<ts>/shots.jsonl`. LeRobotDataset-aligned:
```json
{
  "schema_version": "1.0.0",
  "episode_id": "<shot id>",
  "step": 0,
  "t_iso": "2026-06-19T…Z", "t_ms": 0,
  "observation": { "frame": "frames/<ep>_0000.png", "frame_wh": [w,h],
                   "joint_pos": [f,f,f,f,f,f], "joint_units": "deg" },
  "action": { "primitive": "push_in", "params": {…},
              "joint_target": [f,f,f,f,f,f] },
  "target": { "phrase": "the apple", "box": [x1,y1,x2,y2],
              "backend": "claude_box|yoloe|yolo_world" },
  "reward": { "critic_score": null|float, "critic_verdict": null|"…",
              "source": "vlm_critic" },
  "meta": { "intent": "…", "plan_id": "…" }
}
```
- LeRobot mapping: `observation.frame`→camera, `observation.joint_pos`→`observation.state`, `action.joint_target`→action, `reward.critic_score`→reward.
- Rules: every line validates against the schema or is quarantined (FR-13); `reward.critic_score` may be null per-tick and backfilled at shot end; bumping the schema REQUIRES incrementing `schema_version` (never silently reshape).

### D. Naming & Structure
- Python: files/functions `snake_case`, classes `PascalCase`.
- Run dir: `runs/<UTC-compact-ts>/` → `clips/`, `frames/`, `shots.jsonl`, `plan.json`, `session.json`. Frames `frames/<ep>_<step:04d>.png`; clips `clips/<ep>.mp4`.
- Single `config.yaml`: `acquire_backend`, joint+workspace limits, velocity caps, center tolerance, target clip length, camera index.

### E. Error, Retry & Safety Conventions
- Namespaced error codes: `E_NO_CAMERA`, `E_TARGET_NOT_FOUND`, `E_LOST_LOCK`, `E_OUT_OF_BOUNDS`, `E_STOPPED`, `E_CALIB_REQUIRED`.
- Bounded retries (no infinite loops): acquire re-tries ≤2; critic adjust loops ≤N; tracker lost-lock → re-acquire ≤2 then abort shot (no corrupt clip in the stitch set).
- Safety is absolute: out-of-bounds command → clamp + warn; stop sentinel present → halt motion immediately, return `ok:false` / `E_STOPPED`. Framing imperfection is tolerable; unsafe motion is never.

### Enforcement — All implementers MUST
- Keep stdout = one JSON object; logs to stderr.
- Route every servo command through the single `arm` safety module.
- Write shot-log lines only via the schema validator; bump `schema_version` on any change.
- Use the frozen box/pose/time conventions verbatim.

## Project Structure & Boundaries

### Control-Layer Interface Decision (v1 = scripts, MCP deferred)
v1 control layer = **CLI scripts invoked by Claude via Bash** (simplest, debuggable, deadline-friendly). A whole shoot runs in ONE process (`shoot.py`), so process/model startup is paid once per shot, not per servo tick; the `claude_box` default loads no model. **Promotion trigger:** when switching to the `yoloe` backend and the per-call model reload becomes the bottleneck, promote `src/dum_e/` to an MCP server (`src/dum_e/mcp_server.py`, a thin wrapper over the same library) — NOT a rewrite. Persistent-daemon hybrid considered and set aside (more moving parts, less standard than MCP).

### Complete Project Directory Structure
```
dum-e/                              # repo root
├── README.md
├── pyproject.toml                   # deps: lerobot, opencv-python, ffmpeg, jsonschema,
│                                    #       ultralytics(yoloe)/yolo-world (optional, CPU)
├── config.yaml                      # acquire_backend, joint+workspace limits, velocity
│                                    #   caps, center tolerance, clip length, camera index
├── .gitignore                       # ignores runs/, calibration/, model weights
├── src/dum_e/                       # CONTROL LIBRARY (importable, unit-tested)
│   ├── __init__.py
│   ├── arm.py                       # D3: SOLE path to servos — limits, caps, stop sentinel  → FR-14
│   ├── camera.py                    # frame capture + background recorder                     → FR-8,9
│   ├── calibration.py               # hand-eye calibration + persisted profile                → FR-11
│   ├── tracker.py                   # CSRT wrapper (CPU)                                       → FR-6,7
│   ├── primitives.py                # hold_center, push_in (orbit = v2)                        → FR-6,7
│   ├── acquire/                     # D5: pluggable backend (all CPU)
│   │   ├── base.py                  #   AcquireBackend interface (phrase -> box)
│   │   ├── claude_box.py            #   default: consume Claude-provided box                   → FR-5
│   │   ├── yoloe.py                 #   PRIMARY detector (CPU)                                  → FR-5
│   │   └── yolo_world.py            #   alternative                                            → FR-5
│   ├── shotlog.py                   # FR-13 validate+write, frozen v1.0.0, LeRobot mapping     → FR-13
│   ├── stitch.py                    # ffmpeg ordered concat                                    → FR-10
│   ├── safety.py                    # stop sentinel + bounds helpers                           → FR-14
│   ├── rundir.py                    # runs/<ts>/ layout helpers
│   └── mcp_server.py                # (DEFERRED) thin MCP wrapper over the above — v1.x
├── scripts/                         # CLI ADAPTERS (JSON-stdout contract) — what SKILL calls
│   ├── bringup.py                   # detect arm+camera, sanity check (stage-0)
│   ├── calibrate.py                 # → FR-11
│   ├── survey.py                    # capture frame for Claude to read → FR-2
│   ├── acquire.py                   # phrase -> box via selected backend → FR-5
│   ├── shoot.py                     # track+servo+primitive+record+log → FR-6,7,8,13
│   ├── photo.py                     # → FR-9
│   └── stitch.py                    # → FR-10
├── schemas/
│   └── shot_log.v1.json             # JSON Schema = validation source of truth for FR-13
├── calibration/                     # calibration profiles TRACKED (joints.json, handeye.json); transient captures gitignored
├── runs/                            # session outputs: <ts>/{clips,frames,shots.jsonl,plan.json} (gitignored)
├── train/                           # v2 PLACEHOLDER — consumes runs/ as LeRobotDataset (ROCm)
├── tests/
│   ├── test_arm_safety.py           # bounds + stop enforcement (highest-value test)
│   ├── test_shotlog_schema.py       # schema validation + "is-it-trainable?" check
│   ├── test_acquire_backends.py
│   └── test_stitch.py
└── .claude/skills/dum-e/            # THE SKILL (director)
    ├── SKILL.md                     # orchestration: survey→plan→shoot→critic→stitch → FR-1,3,4,12
    └── reference/
        ├── primitives.md            # primitive catalog + when to use each
        └── shot-log-schema.md       # frozen FR-13 schema, human-readable
```

### Architectural Boundaries
- **Brain ↔ Muscle:** SKILL.md (Claude) NEVER touches hardware directly — it only invokes `scripts/*` via Bash and reads their JSON + saved frames. All cognition (plot, target choice, critic) is in the skill; all actuation is in scripts/lib.
- **Scripts ↔ Library:** scripts/ are thin — parse flags, call `dum_e`, print JSON. No control logic in scripts; no CLI/JSON concerns in the library. (Same boundary lets the deferred MCP server wrap the library without disturbing scripts.)
- **Safety chokepoint:** `arm.py` is the ONLY module that commands servos. Nothing else imports the motor driver — the driver (LeRobot's `FeetechMotorsBus`, encapsulated in `arm._FeetechBus` as a raw-steps surface) and the raw `scservo_sdk` are both forbidden outside `arm.py` (enforced by a test guard). `arm.py` exposes `move_to` / `step` (limit-clamped, velocity-capped, stop-sentinel-checked motion) plus `hold` / `relax` (per-joint torque on/off, e.g. to hand-sweep a joint's range during calibration). Enforces D3 by construction.
- **Schema chokepoint:** all shot-log writes go through `shotlog.py` against `schemas/shot_log.v1.json`. Nothing hand-writes JSONL.

### Requirements → Structure Mapping
- Survey/intake (FR-1,2): SKILL.md + scripts/survey.py + camera.py
- Plan + critic (FR-3,4,12): SKILL.md (Claude)
- Acquire (FR-5): scripts/acquire.py + acquire/*
- Frame+move (FR-6,7): shoot.py + primitives.py + tracker.py + arm.py
- Capture (FR-8,9): shoot.py/photo.py + camera.py
- Stitch (FR-10): stitch.py
- Calibration (FR-11): calibrate.py + calibration.py
- Shot log (FR-13): shotlog.py + schemas/shot_log.v1.json
- Safety (FR-14): arm.py + safety.py

### Data Flow
Intent → SKILL survey (survey.py → frame) → SKILL plan (plan.json) → per shot: acquire.py (box) → shoot.py (tracker+servo+primitive+record → clip + shots.jsonl) → SKILL critic (reads frame) → next shot → stitch.py (final video). `runs/<ts>/` is the single session artifact; v2 `train/` reads it as a LeRobotDataset.

## Architecture Validation Results

### Coherence Validation ✅
Decisions reinforce one another: supervised split (D1) + CPU acquire (D5) + CSRT tracker (D6) keep the real-time loop local and ROCm-free; script/library/skill boundaries are consistent and let the deferred MCP wrapper attach without rewrite; frozen shot-log schema + `shotlog.py` chokepoint serve both v1 capture and v2 training. No contradictory decisions found.

### Requirements Coverage Validation ✅
All 14 FRs map to concrete components (see Requirements → Structure Mapping). NFRs addressed: latency (D1 split + CPU once-per-shot acquire), safety (D3 arm chokepoint + FR-14), training-data contract (frozen schema C), determinism (deterministic primitives + logging).

### Implementation Readiness Validation ✅ (with tracked gaps)
Decisions, patterns, structure, and the frozen contracts are documented and specific enough for consistent implementation. Tracked gaps below.

### Gap Analysis Results
- **IMPORTANT — Cartesian primitive control:** `hold_center` works via hand-eye visual servo (no IK); `push_in` (and v2 `orbit`) are Cartesian and may need IK or a calibrated dolly-direction approximation. RESOLVE in the first `primitives` spike.
- **IMPORTANT — Stage-0 hardware not assembled:** execution prerequisite (first story).
- **MINOR — `yoloe` CPU acquire latency unmeasured:** `claude_box` default de-risks until a cheap CPU spike confirms acceptable seconds-per-acquire.
- **MINOR — hand-eye calibration method (FR-11)** left to implementation (acceptable).

### Architecture Completeness Checklist
**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**
- [x] Critical decisions documented (with model/license/CPU specifics)
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed (latency via D1+CPU acquire)

**Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified (script JSON contract)
- [x] Process patterns documented (error/retry/safety)

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment
**Overall Status:** READY WITH MINOR GAPS
**Confidence Level:** high
**Key Strengths:** Claude-as-brain skill keeps cognition free of bespoke ML; CPU acquire removes ROCm from v1; frozen LeRobot-aligned schema makes v2 near-drop-in; single arm-safety chokepoint; clean brain/muscle/library boundaries.
**Areas for Future Enhancement:** Cartesian primitive control (IK), second-arm multi-angle, SAM2 mask-tracking, MCP promotion, learned policy (v2).

### Implementation Handoff
**AI Agent Guidelines:** Follow decisions and the frozen contracts (script JSON I/O, coordinate/units, shot-log schema) exactly; route all motion through `arm.py`; all shot-log writes through `shotlog.py`.
**First Implementation Priority:** Stage-0 — assemble SO-101 (HF guide), install LeRobot, `bringup.py` verifies motor comms + camera capture on this host.
