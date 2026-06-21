---
title: "Dum-E — Autonomous Robotic Videographer"
status: final
created: 2026-06-19
updated: 2026-06-19
---

# PRD: Dum-E — Autonomous Robotic Videographer
*Working title — confirm.*

## 0. Document Purpose

This PRD is for Kamal (builder + sole operator) and any future contributor, plus the downstream BMad workflows (architecture, epics/stories) that will consume it. It is scoped to a **personal prototype**: lean, FR-heavy, light on market/business concerns. Vocabulary is anchored in the Glossary (§3); features are grouped with globally-numbered FRs nested; inferred decisions are tagged inline `[ASSUMPTION: ...]` and indexed in §9. It builds on the brainstorming session at `documents/brainstorming/brainstorming-session-2026-06-19-1434.md` (concept origin) — that document is the source of the locked decisions; this PRD does not duplicate its rationale. Technical-how (control transport, libraries) lives in the addendum, not here.

## 1. Vision

**Dum-E** — named after Tony Stark's clumsy, endearing robotic-arm assistant in *Iron Man* — is an autonomous robotic videographer for hardware projects, packaged as a **Claude Code Skill**. You point a camera-equipped SO-101 arm at something on your bench, invoke the skill, and give one line of intent — *"make a short demo video of this fruit basket."* Dum-E does the rest: it looks at the scene, **invents a shot-by-shot plot, drives the arm through smooth cinematic moves while keeping the subject framed, records the clips, and stitches them into a finished, shareable video** for YouTube/LinkedIn. The human directs by *intent*; Dum-E directs the *camera*. The name is also the design philosophy: a helpful, *endearingly imperfect* lab assistant — minor imperfection is acceptable and on-brand, which sets a deliberately forgiving quality bar for a prototype.

Because Dum-E is a Skill, it is **inherently reusable** — you invoke it on whatever hardware project is on the bench; that horizontal "drop it onto any project" use is the point, and is available from v1. (What's deferred to later is *packaging it for distribution to other people* — see §6.2.) *Provenance note: the originating brainstorm framed the deliverable as an "MCP server"; the decision to build it as a Claude Code Skill — making Claude itself the agent and vision brain, with no separate model or API — supersedes that earlier framing. An MCP/server wrapper for distribution remains a later option.*

The reason it exists: maker demos usually die at "shaky phone footage on a tripod." A *moving* camera reads as production value, and a *tight edit* is what actually gets shared — but doing both by hand is tedious. Dum-E automates the entire path from raw scene to postable clip, and because it's a Skill, the agent and the "vision brain" are **Claude itself** — no separate model, no API integration to build.

Architecturally, Dum-E is **"deterministic now, designed for learning."** v1 frames and moves via deterministic, vision-stabilized primitives plus a self-critique loop — no trained policy, works day one. But every shot logs `(move, resulting frame, critic score)`, so ordinary use silently accumulates the dataset a future v2 could use to *learn* better cinematography, with zero separate data-collection effort.

## 2. Target User

### 2.1 Jobs To Be Done
- **(Functional)** Turn a finished/in-progress hardware project into a short, watchable demo video without manual filming or editing.
- **(Functional)** Get *camera motion* and *tight cuts* — the two things that separate a "pro" maker clip from a phone clip — without a camera operator or video-editing skills.
- **(Emotional)** "I built a thing; I want to show it off and feel proud of how it looks" — fast, low-friction, repeatable.
- **(Contextual)** Works from the same Claude Code chat the builder already uses; no new tool to learn.
- This is explicitly **for me, the builder**, first. (Single-operator hobby project.)

### 2.2 Non-Users (v1)
- Anyone needing broadcast/commercial-grade cinematography (Dum-E is a prototype; minor imperfection is acceptable by design).
- Subjects that don't fit an arm-mounted camera's reach/scale (large installations, outdoor scenes, anything the arm can't physically frame).
- Users without Claude Code and the SO-101 hardware on hand.

### 2.3 Key User Journey

- **UJ-1. Kamal makes a fruit-basket demo in one prompt.**
  Kamal, the builder, has the SO-101 camera arm assembled and a fruit basket (apple, banana, avocado) on the bench. In Claude Code he invokes the `dum-e` skill and types *"make a short demo video of this fruit basket."* Dum-E runs a quick **scene survey** (Claude looks through the camera and notes the subjects), proposes a short **shot plan** ("wide → push-in on the apple → hold on the banana → pull back"), and on his go-ahead executes it: for each shot it locates the subject, drives the arm to frame it, runs the camera move, and records a **clip**. It stitches the clips into a 15–40s **final video** saved to disk. Kamal watches it, and posts it to LinkedIn. **Edge case:** if Dum-E can't find a named subject in frame, it says so and asks Kamal to reposition the basket or rename the subject rather than recording a bad shot.

## 3. Glossary

- **Dum-E** — The product: a Claude Code Skill plus bundled hardware-control code that operates SO-101 camera arm(s) to autonomously produce demo videos.
- **Skill** — The Claude Code Skill packaging of Dum-E; the unit the Operator invokes.
- **Operator** — The human (Kamal) who invokes Dum-E and gives Intent. Single role in v1.
- **Intent** — The Operator's one-line, high-level request (e.g. "make a short demo video of this fruit basket"). Dum-E owns everything downstream of Intent.
- **Camera Arm** — An assembled SO-101 arm with a camera mounted on it. v1 uses one; v2 adds a second.
- **Scene Survey** — Dum-E's initial look through the camera (via Claude's vision) to identify the Subjects present.
- **Subject** — A thing in the scene that can be filmed (e.g. the apple, the whole basket).
- **Target** — The specific Subject a given Shot is framed on.
- **Shot Plan** — The ordered list of Shots Dum-E invents from Intent + Scene Survey. The "plot."
- **Shot** — One planned camera action: a Target + a Primitive + capture. Produces one Clip.
- **Primitive** — A parameterized, vision-stabilized camera motion. v1: **hold-center**, **push-in**. v2: **orbit** and others.
- **Hold-center** — A Primitive that drives the Camera Arm so the Target stays centered in frame.
- **Push-in** — A Primitive that moves the Camera Arm slowly toward the Target while keeping it framed.
- **Visual servo** — The closed loop (locate Target → compute arm move → move → re-check) that powers Primitives.
- **Hand-eye Calibration** — A startup routine where the arm makes known moves and observes the resulting image shift to learn its joint→pixel mapping. Measurement, not training.
- **Critic** — Dum-E using Claude's vision to judge a framed shot (centered? in focus? cropped?) and accept or adjust before recording.
- **Clip** — A recorded video segment produced by one Shot.
- **Final Video** — The stitched, ordered assembly of Clips delivered to the Operator.
- **Shot Log** — The per-Shot record of `(move, resulting frame, Critic score)` written for future learning.

## 4. Features

### 4.1 Intent Intake & Scene Survey
**Description:** The Operator invokes the Skill in Claude Code and provides a single line of Intent. Dum-E performs a Scene Survey using Claude's native vision over the Camera Arm's live frame and produces a short list of Subjects it can see. Realizes UJ-1. No voice, no manual framing.

**Functional Requirements:**

#### FR-1: Invoke with one-line Intent
The Operator can start a session by invoking the `dum-e` Skill in Claude Code and giving one line of Intent.
**Consequences (testable):**
- A free-text Intent string is accepted and drives the session; no structured form is required.
- If no camera is reachable, Dum-E reports the failure and stops before planning.

#### FR-2: Scene Survey
Dum-E can identify the Subjects visible in the current camera frame and list them back to the Operator.
**Consequences (testable):**
- Given the fruit-basket scene, the survey names the distinguishable Subjects (e.g. apple, banana, avocado, whole basket). `[ASSUMPTION: a single still frame from the arm's resting pose is sufficient for survey; no pre-scan sweep in v1.]`
- If the frame is empty/unreadable, Dum-E says so and asks the Operator to reposition rather than inventing Subjects.

### 4.2 Shot Planning (the director)
**Description:** From the Intent plus the Scene Survey, Dum-E invents a Shot Plan — an ordered sequence of Shots that tells a short visual story. This is pure Claude reasoning. The Operator can approve or nudge it. Realizes UJ-1.

**Functional Requirements:**

#### FR-3: Generate a Shot Plan
Dum-E can produce an ordered Shot Plan from Intent + Scene Survey, where each Shot names a Target and a Primitive.
**Consequences (testable):**
- Each Shot in the plan references a Subject from the Scene Survey and a v1 Primitive (hold-center or push-in).
- The plan targets a short Final Video. `[ASSUMPTION: default target length 15–40s; default 3–5 Shots.]`

#### FR-4: Review the plan before shooting
The Operator can see the proposed Shot Plan and either approve it or request changes before any arm motion occurs.
**Consequences (testable):**
- No Camera Arm motion happens until the Operator approves the plan.
- The Operator can edit/reorder/drop Shots in natural language and Dum-E regenerates the plan. `[ASSUMPTION: an explicit approval step is wanted in v1 for safety/trust; auto-proceed is a later convenience.]`

### 4.3 Targeting & Framing
**Description:** For each Shot, Dum-E locates the Target in frame using Claude's vision and drives the Camera Arm via Visual servo until the Target is framed (hold-center). This is the atomic capability — the original "move so the apple is centered on screen." Realizes UJ-1.

**Functional Requirements:**

#### FR-5: Locate a named Target in frame
Dum-E can determine where a named Target is within the current frame.
**Consequences (testable):**
- Given "the apple," Dum-E returns the apple's location/region in the frame, or reports "not found."
- On "not found," the Shot is not executed; Dum-E surfaces the miss to the Operator (UJ-1 edge case).

#### FR-6: Hold-center the Target (Visual servo)
Dum-E can drive the Camera Arm so the Target is brought to and held near frame center.
**Consequences (testable):**
- After hold-center completes, the Target's centroid is within a center tolerance band of the frame. `[ASSUMPTION: "centered" = within the central ~20% region; exact tolerance tunable.]`
- The servo loop terminates (success or give-up) within a bounded number of steps/time rather than looping forever.

### 4.4 Camera Move Primitives
**Description:** On top of a held frame, Dum-E executes a cinematic Primitive while vision keeps the Target framed. v1 ships hold-center + push-in. Realizes UJ-1.

**Functional Requirements:**

#### FR-7: Push-in Primitive
Dum-E can perform a push-in: move the Camera Arm toward the Target over a few seconds while keeping it framed.
**Consequences (testable):**
- During the push-in the Target remains within the center tolerance band throughout the move.
- The move is smooth enough to be watchable at the prototype bar (no large jerks that ruin the clip). `[ASSUMPTION: smoothness judged by eye, not a quantitative jerk metric, for v1.]`
- **Out of Scope:** orbit and other Primitives — deferred to v2.

### 4.5 Capture
**Description:** Dum-E records a Clip per Shot and can take stills on request. Capture is triggered by Dum-E during Shot execution (and by the Operator on demand). Realizes UJ-1.

**Functional Requirements:**

#### FR-8: Record a Clip
Dum-E can start and stop recording to produce one Clip per Shot.
**Consequences (testable):**
- Each executed Shot yields exactly one saved Clip file with timestamp metadata. `[ASSUMPTION: clips saved locally as standard video files; ~1080p.]`
- A failed/aborted Shot does not leave a corrupt Clip in the set to be stitched.

#### FR-9: Take a photo
The Operator can ask Dum-E to capture a still photo of the current (optionally framed) Target.
**Consequences (testable):**
- A single image file is saved on request, independent of the video pipeline.

### 4.6 Final Video Assembly
**Description:** Dum-E stitches the recorded Clips into a single Final Video in Shot-Plan order. v1 is a straight ordered concatenation with basic per-clip trim; intelligent editing is v2. Realizes UJ-1.

**Functional Requirements:**

#### FR-10: Stitch Clips into a Final Video
Dum-E can assemble the session's Clips into one Final Video in Shot-Plan order.
**Consequences (testable):**
- The Final Video contains the Clips in plan order and is a single playable file. `[ASSUMPTION: ffmpeg-based concat; basic head/tail trim per clip.]`
- Stitching is count-agnostic: 2 or 10 Clips assemble by the same path.
- **Out of Scope:** agent-chosen ordering, trim-to-action-beat, transitions, multi-angle cutting — all v2.

### 4.7 Hand-eye Self-Calibration
**Description:** Before shooting (e.g. on first run or on demand), Dum-E performs Hand-eye Calibration so Visual servo is accurate without manual tuning. Foundational, not user-facing.

**Functional Requirements:**

#### FR-11: Self-calibration routine
Dum-E can run a calibration routine where the Camera Arm makes known moves, observes image shift, and derives its joint→pixel mapping.
**Consequences (testable):**
- After calibration, hold-center converges in fewer steps than uncalibrated. `[ASSUMPTION: calibration is a short startup/one-time routine, persisted between sessions.]`
- Calibration runs within the arm's safe movement bounds (see FR-14).

### 4.8 Shot Critic
**Description:** Before committing a Clip, Dum-E uses Claude's vision as a Critic to judge the framed shot (centered? in focus? cropped?) and nudges or accepts. This is the "is it optimum now?" loop and is part of the v1 engine.

**Functional Requirements:**

#### FR-12: Critic check before recording
Dum-E can evaluate a framed shot and either accept it for recording or adjust and re-check.
**Consequences (testable):**
- A shot the Critic rejects triggers at least one adjustment attempt before recording or giving up.
- The Critic verdict and score are written to the Shot Log (FR-13). `[ASSUMPTION: a small bounded number of adjust retries to avoid stalls.]`

### 4.9 Shot Logging (training data for v2)
**Description:** Every Shot writes a **training-grade** Shot Log entry. This is not incidental debug output — **v2 (the learned cinematography policy) is targeted for the week of 2026-06-26**, so the v1 log schema is on the critical path and must be designed once, correctly, to be directly trainable. The log must capture the full `(state → action → reward)` tuple a self-supervised / RL-from-Critic-reward pipeline needs, with no separate data-collection phase ever required.

**Functional Requirements:**

#### FR-13: Write a training-grade Shot Log
Dum-E records, per Shot, a complete and machine-readable entry sufficient to train a v2 policy without any additional data collection.
**Consequences (testable):**
- Each entry captures, at minimum: the **state** (camera frame(s) and arm pose/joint state before the move), the **action** (the move/command issued, with Primitive and parameters), the **outcome** (resulting frame and arm pose), the **reward signal** (Critic score/verdict), the Target, and timestamps — enough to reconstruct `(state, action, reward)` tuples.
- The schema is **versioned and stable**; a documented schema version is written with every entry so v2 training can rely on it. `[ASSUMPTION: stored as files/rows alongside Clips, e.g. JSONL + referenced frame images.]`
- Each written entry is **schema-validated**; an entry that cannot be completed is flagged/quarantined rather than written partial, so the training set is never silently corrupted.
- Logging is **non-blocking to the shoot** (a logging failure must not abort the video) but a logging failure is surfaced to the Operator, not swallowed.
- A trivial **"is the log trainable?" check** can validate a session's logs against the v2 schema (sanity gate before training week).

**Note on "trainable" being verifiable now:** the v2 *approach* is deliberately undecided (Open Q7), but the full `(state → action → reward)` tuple is a **superset** that satisfies both candidate approaches (self-supervised needs `state → action → outcome`; RL needs `state → action → reward`). So "trainable" is verifiable today by validating logs against this fixed superset schema — independent of which approach is chosen at training time. This superset *is* the concrete v1 schema; only the schema version string is locked, not the eventual training method.

### 4.10 Movement Safety
**Description:** Because the Camera Arm physically moves on a bench near objects and people, Dum-E operates within safe motion limits and can be stopped. Cross-cutting but specified as FRs because it gates every motion feature.

**Functional Requirements:**

#### FR-14: Safe motion bounds & stop
Dum-E can constrain Camera Arm motion to safe limits and halt motion on command.
**Consequences (testable):**
- Arm motion stays within configured joint/workspace limits; commands outside limits are clamped or refused.
- The Operator can issue a stop that halts arm motion promptly. `[ASSUMPTION: software stop via chat/keyboard in v1; hardware e-stop is out of scope but recommended.]`

## 5. Non-Goals (Explicit)
- **Not** voice-controlled — chat/text only.
- **Not** teleoperated/puppeted — no human demonstrates moves; no imitation-learning data collection in v1.
- **Not** a trained-policy system in v1 — deterministic primitives + critic only (learning is v2, fed by Shot Logs).
- **Not** a lighting rig — no controllable lights; ambient light only.
- **Not** a general video editor — no timeline UI, manual editing, music, or effects.
- **Not** broadcast quality — prototype bar; minor imperfection is acceptable by design.
- **Not** a standalone app or hosted service — it is a Claude Code Skill that runs locally.

## 6. MVP Scope ("first light")

### 6.1 In Scope
- One Camera Arm (single SO-101 with camera).
- Intent intake + Scene Survey (FR-1, FR-2).
- Shot Plan generation + Operator approval (FR-3, FR-4).
- Targeting + hold-center + push-in (FR-5, FR-6, FR-7).
- Clip recording + photo (FR-8, FR-9).
- Ordered-concat stitch into a Final Video (FR-10).
- Hand-eye self-calibration (FR-11).
- Critic check (FR-12).
- Shot logging (FR-13).
- Safe motion bounds + stop (FR-14).
- First subject: a fruit basket. Success = one postable clip from one prompt.

**v1 exit criteria (gating v2, which starts week of 2026-06-26):**
- A session's Shot Logs pass the "is the log trainable?" check against the locked superset schema (FR-13).
- AMD/ROCm training toolchain validated as viable for the intended v2 approach (Open Q6) — confirmed *before* v1 is considered done, not after.

### 6.2 Out of Scope for MVP (deferred)
- **Second Camera Arm + multi-angle cutting** → v2. `[NOTE FOR PM: this is the headline v2 feature and the reason both SO-101 arms were chosen; revisit early once v1 loop is proven.]`
- **Orbit and additional Primitives** → v2.
- **Intelligent editing** (agent-chosen order, trim-to-beat, transitions, music) → v2.
- **Learned cinematography policy** from Shot Logs (self-supervised / RL-from-Critic-reward) → **v2, targeted week of 2026-06-26**. Out of v1 *build* scope, but v1 is explicitly responsible for producing trainable Shot Logs (FR-13) and validating the AMD/ROCm toolchain (Open Q6) so v2 can start on schedule. `[NOTE FOR PM: v2 is ~1 week out — the FR-13 schema and ROCm check are effectively v1 exit criteria, not far-future concerns.]`
- **Auto-proceed without approval** (skip FR-4 gate) → later convenience.
- **Packaging as a reusable MCP/server** for distribution → later; v1 is a local Skill for the builder.

## 7. Success Metrics

**Primary**
- **SM-1**: *First postable clip.* Dum-E produces a 15–40s Final Video of the fruit basket from a single Intent, with no manual framing or editing, that Kamal judges good enough to post. Validates FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-10. Target: achieved at least once = MVP success.

**Secondary**
- **SM-2**: *Autonomy.* Share of a shoot completed without manual intervention beyond Intent + plan approval. Validates FR-5, FR-6, FR-7, FR-12. Target: most shoots need no mid-shoot manual correction.
- **SM-3**: *Reuse.* Kamal uses Dum-E to make demos for ≥2 *different* projects (beyond the fruit basket) within the first month. Validates the "drop-in for any project" thesis.

**Counter-metrics (do not optimize)**
- **SM-C1**: *Don't chase cinematic polish.* Time spent tuning smoothness/composition beyond "clearly better than a phone clip" is wasted at the prototype bar. Counterbalances SM-1 — ship the clip, don't perfect it.
- **SM-C2**: *Don't over-engineer the plan.* More Shots / longer videos is not better; a tight 3–5 shot clip beats an elaborate one. Counterbalances SM-2.

## 8. Open Questions
1. Camera choice and mounting on the SO-101 — model, resolution, FOV, cabling. (Hardware concern; confirm in architecture.)
2. SO-101 control stack — LeRobot vs direct Feetech servo control; what's already working on Kamal's bench? `[ASSUMPTION: LeRobot/Feetech Python.]` **RESOLVED (Story 1.5/1.6 build):** lean on LeRobot — `arm.py`'s driver sits on `lerobot.motors.feetech.FeetechMotorsBus` (raw encoder steps), and joint-range calibration (FR-11) uses LeRobot's calibration facility. The `SOFollower` robot class is deliberately deferred to v2 (see architecture "LeRobot adoption boundary").
3. How does Claude get the live camera frame inside a Skill run — captured stills on demand vs a stream? (Drives FR-2/FR-5 latency.)
4. Calibration persistence — re-run every session or only when the rig changes?
5. Workspace/safe-bounds definition — how are joint/workspace limits configured for FR-14?
6. **(Urgent)** ROCm viability for the v2 learning loop on the AMD GPU — validate *during v1*, since v2 is targeted week of 2026-06-26. What training framework runs on this AMD GPU under ROCm, and does it support the intended policy/RL approach?
7. v2 training approach — self-supervised visual-motor model vs RL-from-Critic-reward. **DECIDED: undecided-by-design** — v1 logs the *full* `(state → action → reward)` tuple (FR-13) so either approach is supported and the choice can be made at training time (week of 2026-06-26) without re-instrumenting. Slightly heavier to build; accepted to preserve optionality given the short runway.

## 9. Assumptions Index
- §4.1 FR-2 — a single resting-pose still is enough for Scene Survey; no pre-scan sweep in v1.
- §4.2 FR-3 — default Final Video 15–40s, 3–5 Shots.
- §4.2 FR-4 — explicit Operator approval of the plan is wanted in v1.
- §4.3 FR-6 — "centered" ≈ within central ~20% of frame; tolerance tunable.
- §4.4 FR-7 — smoothness judged by eye, not a quantitative metric, for v1.
- §4.5 FR-8 — Clips saved locally as standard ~1080p video files.
- §4.6 FR-10 — ffmpeg-based ordered concat with basic per-clip trim.
- §4.7 FR-11 — calibration is a short routine, persisted between sessions.
- §4.8 FR-12 — bounded number of Critic adjust-retries.
- §4.9 FR-13 — Shot Logs stored alongside Clips (e.g. JSONL + frame images) with a versioned, training-grade schema; v2 training targeted week of 2026-06-26, so schema is design-once-correctly.
- §4.10 FR-14 — software stop in v1; hardware e-stop out of scope but recommended.
- Hardware Constraints — arm-mounted camera is a USB webcam.
- Global — control transport = plain scripts invoked via Bash (addendum); SO-101 via LeRobot/Feetech Python.

---

## Hardware Constraints *(Adapt-In)*
- **Compute:** Desktop with an **AMD GPU**. v1 requires no GPU (Claude is the vision/agent brain). The GPU is reserved for the v2 learning loop. **Risk:** AMD ⇒ ROCm, not CUDA; most ML tooling assumes NVIDIA/CUDA, so the v2 on-device training path carries portability risk and must be validated before commitment (Open Q6).
- **Arm:** SO-101 (leader + follower on hand). v1 uses one as the Camera Arm; the second is reserved for v2 multi-angle.
- **Camera:** Arm-mounted camera `[ASSUMPTION: USB webcam]`; reach and scale of the arm bound what can be filmed (see Non-Users).
- **Form factor:** Bench-top rig in the maker's workspace; runs locally, no cloud service.

## Constraints & Guardrails — Safety *(Adapt-In)*
- The Camera Arm moves physically near objects, the second arm, and possibly people. All motion is bounded (FR-14), calibration moves stay in-bounds (FR-11), and a software stop is always available.
- Prototype framing does **not** extend to safety: imperfect *framing* is acceptable; uncontrolled *motion* is not.
- `[NOTE FOR PM: a physical e-stop is out of v1 scope but strongly recommended before unattended operation.]`
