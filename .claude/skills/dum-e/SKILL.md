---
name: dum-e
description: Direct the Dum-E robotic camera arm to plot, shoot, and stitch a short demo video of whatever hardware is in front of it. Use when the user wants to film/record a demo, take a shot, or make a video of a project on the bench.
---

# Dum-E — Autonomous Robotic Videographer (director)

> SKELETON — orchestration logic is filled in across Epics 2–4. This file is the
> **director**: it does the thinking (survey, plot, target choice, critic) and
> invokes the `scripts/*` adapters for all hardware actions. It must NEVER touch
> hardware directly — only Bash-invoke the scripts and read their JSON + saved frames.

## Operating contract

- Every `scripts/*` call returns ONE JSON object on stdout: `{ok, data, error, artifacts}`.
  Parse it; treat `ok:false` + `error.code` as the failure signal. Logs are on stderr.
- "See" the scene by **reading the saved frame image** (path in `artifacts`) with the Read tool.
- All motion is bounded by `arm.py`; if a `runs/STOP` sentinel exists, motion halts.

## Director loop (target end state — built incrementally)

1. **Intake** — take the user's one-line intent (Story 4.1).
2. **Survey** — `scripts/survey.py`, read the frame, list subjects (Story 2.2).
3. **Plot** — write an ordered shot plan (`plan.json`): each shot = subject + primitive (Story 4.2).
4. **Review** — show the plan; do not move the arm until the user approves (Story 4.3).
5. **Shoot each shot** — `scripts/acquire.py` → `scripts/shoot.py` (hold_center/push_in →
   record → log); judge the framing as critic before committing (Stories 2.x, 3.x).
6. **Stitch** — `scripts/stitch.py` → final video (Story 4.4).

## Status

Scaffold only (Story 1.1). Hardware bring-up (Epic 1) must complete before this loop runs.

## Reference

- `reference/primitives.md` — camera-move primitive catalog.
- `reference/shot-log-schema.md` — the frozen FR-13 shot-log schema.
