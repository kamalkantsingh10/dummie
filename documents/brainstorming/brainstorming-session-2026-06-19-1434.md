---
stepsCompleted: [1, 2]
inputDocuments: []
session_topic: 'A reusable MCP server + agent + arm-control code that gives Claude the ability to act as a robotic demo videographer for any hardware project — chat-commanded camera/light arm(s) that frame, light, record, photograph subjects and stitch clips into a final video'
session_goals: 'Arrive at a single sharp product concept to commit to as the core of the project'
selected_approach: 'ai-recommended'
techniques_used: ['First Principles Thinking', 'Morphological Analysis', 'Resource Constraints']
ideas_generated: []
context_file: ''
---

# Brainstorming Session Results

**Facilitator:** Kamal
**Date:** 2026-06-19

---

## ⭐ COMMITTED CONCEPT — "Dum-E"

**Name:** **Dum-E** — after Tony Stark's clumsy robotic-arm workshop assistant in *Iron Man*. Thematic fit: a robotic camera-arm helper in a maker's lab, *endearingly imperfect* — which directly embodies the "it's a prototype, minor imperfection is acceptable" constraint. (Repo is already `dum-e`.)

**One-liner:** An autonomous robotic videographer for hardware projects, shipped as a drop-in MCP + agent package.

**Pitch:** Bolt Dum-E onto any hardware project's Claude setup. Give one line of intent — "make a short demo video of this." The agent surveys the scene with a vision model, invents a shot-by-shot plot, drives SO-101 camera arm(s) through vision-stabilized cinematic moves, records clips, and stitches a finished, shareable (YouTube/LinkedIn) video. Chat-driven; no puppeting; no manual framing. Human directs by *intent*, Dum-E directs the *camera*.

**Why it's sharp:**
- A **director**, not a remote-control camera (owns plot → plan → shoot → edit). ← the wow.
- **Horizontal** — reusable across every hardware project, via MCP.
- **Self-tuning engine** — hand-eye self-calibration + VLM-as-critic; no hand-tuning, no training data to start.
- **Designed to learn** — every shoot logs `(move, frame, VLM-score)`; v1 farms the dataset that lets v2 learn "what a good shot is," with zero extra data collection.

**Locked architecture:** 2 SO-101 camera arms (start on 1) · VLM perception · primitives (hold-center, push-in, orbit) · agent-driven plot + edit · MCP interface · deterministic-now-designed-for-learning.

**Roadmap:** v1 = one arm, director loop, fruit basket → ONE postable clip. v2 = second angle + cut-between, VLM critic loop, smart edit. v3 = learned policy from logged data.

## Session Overview

**Topic:** Converting an SO-101 robot arm (leader + follower in hand) into an agentic camera operator — a camera and light mounted on the arm that, on natural-language command ("focus on the apple"), moves to center/light the target object on screen, and can start/stop recording or take photos.

**Goals:** Land on a single sharp product concept to commit to as the core of this project.

### Session Setup

Hardware on hand: SO-101 leader + follower arms (to be assembled). Control: CHAT command (not voice — text is enough). Core loop: chat command → vision (find target) → arm motion (frame/center subject) → camera actions (record/photo) → stitch clips into a final video.

### Phase 1 — First Principles (findings)

**Job-to-be-done:** Produce demo videos of *hardware projects* for **YouTube + LinkedIn sharing** (social/portfolio). Audience = scroll-feed.

**Constraints locked:**
- Control via CHAT, not voice.
- **No lights** — drop the light-arm idea entirely.
- It's a **prototype** — minor imperfection is acceptable; don't over-engineer for cinematic polish. Bar = "clearly better than a static phone clip, and autonomous."

**Bedrock truths agreed:**
- Truth 1 — **Motion = production value.** The arm's reason to exist is *cinematic camera motion* (push-in, arc), not reaching the subject.
- Truth 2 — **The edit is the product.** Nobody shares raw clips; the deliverable is a tight 15–40s cut. The "stitch clips → final video" step is core, not an add-on. (Reinforced by prototype framing: tight editing rescues imperfect footage.)
- Truth 3 — **The hook matters** (autoplay feeds), but softened for prototype.
- Truth 4 — Lighting: REJECTED (no lights).
- Truth 5 — **Human directs by PROMPT; agent frames + moves autonomously via camera + computer vision. NO puppeting / teleop teaching.** Perception layer = classical object detection **or** a vision/VLM model (VLM lets you target by free-text description like "the gripper's fingertip" with no pre-trained classes). Agent's core skill = closed vision loop: prompt → detect/locate target → visual-servo arm to center subject → execute a parametric camera-move primitive (push-in / orbit / pan / hold-center) while vision keeps it framed → record → stitch. Cinematography = composition from a small library of vision-stabilized move primitives, not invented from scratch.

**The Engine (refined — "smart hybrid"):** Move primitives are NOT blindly executed; they run inside two feedback layers:
- **① Self-calibration (hand-eye):** on startup the arm performs known wiggles and watches image shift → learns joint→pixel mapping → robust servoing with zero manual tuning. (Measurement, not policy training.)
- **② VLM-as-critic loop ("is it optimum now?"):** after each move the agent feeds the frame to the VLM to judge centering / focus / composition / cropping; if not optimal → nudge → re-check → accept, then record.
- **③ Learning — corrected taxonomy (puppeting is the only true blocker):**
  - **Imitation learning** (copy human demos) → needs puppeting → REJECTED.
  - **Self-supervised visual-motor model ("motor babbling")** → arm explores itself, image is the label, learns full-workspace joint→frame model → NO puppeting → viable.
  - **RL with VLM-as-reward** → arm explores, VLM critic score is the reward, policy learns "what a good shot is" autonomously → NO puppeting → viable & on-brand.

### Phase 2 — Morphological Analysis (LOCKED CONFIGURATION)

| # | Parameter | Decision |
|---|-----------|----------|
| 1 | Arm config | **TWO camera arms** (uses both leader+follower) → two simultaneous angles, agent cuts between A/B. Sync = timestamp alignment at edit time (no hardware genlock; prototype bar absorbs it). |
| 2 | Perception | **VLM** (text-targeted, e.g. "the gripper's fingertip") — no training, no fixed classes. |
| 3 | Move primitives | Start with **hold-center + push-in + orbit**; expand later. |
| 4 | Capture | **photo + clip**, both chat-triggered. |
| 5 | Editing/stitch | **Agent sequences + trims + cuts between angles** to a target length. "The edit is the product." |
| 6 | Deliverable form | **Reusable drop-in package** for any hardware project. |
| 7 | Interface | **MCP tools** called by Claude in chat. |

**DECISION — Engine identity: "Deterministic now, designed for learning."**
- **v1 = primitives + ① self-calibration + ② VLM critic loop.** Deterministic, works day one, fully agentic via the critic. No learned policy.
- **Architect for v2:** log every `(move, resulting frame, VLM score)` from day one. Normal v1 usage silently accumulates the dataset for v2's RL-from-VLM-reward learning loop → learned policy drops in later with no rewrite. The product generates its own training data through use.

### Phase 3 — Resource Constraints + KEYSTONE decision

**KEYSTONE — The agent is an AUTONOMOUS DIRECTOR, not a remote-control camera.** Human gives *intent only*; agent owns the full creative pipeline: **plot → plan → shoot → stitch.**

**Director loop (v1):**
1. Human prompt = high-level intent only ("make a short demo video of this fruit basket").
2. **Survey** — VLM sees the scene (what objects/subjects are present).
3. **Plot** — agent writes a shot-list / mini-story (e.g. wide → push-in on apple → hold on banana → pull-back reveal). Pure LLM reasoning = the magic, nearly free to build.
4. **Shoot** — per shot: pick target + primitive → run vision-servo engine → record clip.
5. **Stitch** — concatenate clips in plot order → final video.

**Why this is feasible for a prototype:** the *creative* layer (plot/plan) is just LLM text generation (cheap, Claude's strength); the *hard* layer (physical execution) was already scoped. Highest-impact capability rides nearly free on the engine.

**Stitch difficulty clarification:** concatenating 2 vs 10 clips = same code (ordered list + trim) — count is a parameter, not difficulty. The hard/v2 part is edit *intelligence* (agent-chosen order, trim-to-beat, cut-between-two-angles), independent of clip count.

**MVP "first light" (one weekend, end with ONE postable clip):**
- ONE arm + camera (prove the loop on one, clone to two later).
- Director loop above, with primitives **hold-center + push-in** only.
- Chat-triggered record; stitch = ordered concat + basic trim.
- First subject = **fruit basket** (zero dependency, guaranteed).
- **Deferred to roadmap (in architecture, not in weekend):** 2nd arm + cut-between-angles, orbit & more primitives, VLM critic loop, `(move,frame,score)` logging → learned policy, smart edit (order/trim/transitions).
