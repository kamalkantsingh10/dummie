# Story 1.6: Hand-eye self-calibration (`calibrate.py` / `calibration.py`)

Status: ready-for-dev

## Story

As the builder,
I want Dum-E to self-calibrate its joint→pixel mapping by moving and observing,
so that visual servoing is accurate without manual tuning (FR-11).

## Acceptance Criteria

1. `scripts/calibrate.py` drives the arm through known small moves (within safe bounds via `arm.py`), captures frames, and observes how image content shifts to derive a joint→pixel mapping (the hand-eye relationship / image Jacobian).
2. All calibration motion routes through `arm.py` (Story 1.5) and stays inside soft limits; the routine respects the stop sentinel.
3. The calibration profile is persisted to `calibration/` and reloads on the next run (no recalibration required each session).
4. The routine reports `ok:true` with a basic quality metric (e.g. mapping residual / fit confidence), or `ok:false` / `E_CALIB_REQUIRED` on failure.
5. Re-running calibration overwrites/updates the persisted profile deterministically.

## Tasks / Subtasks

- [ ] Task 1: Calibration math (`calibration.py`) (AC: 1, 4)
  - [ ] Implement the joint→pixel mapping estimation: command known small joint deltas via `arm.py`, capture before/after frames via `camera.py`, measure image shift (e.g. optical-flow / feature displacement using OpenCV), and fit the local mapping (image Jacobian) used by hold_center later
  - [ ] Compute a basic quality metric (residual of the fit) and a pass/fail threshold
- [ ] Task 2: Persistence (AC: 3, 5)
  - [ ] Save/load the calibration profile to `calibration/` (documented format, versioned); deterministic overwrite on re-run
- [ ] Task 3: CLI (`calibrate.py`) (AC: 1, 2, 4)
  - [ ] `scripts/calibrate.py` orchestrates the routine; emit JSON envelope with quality metric in `data`, profile path in `artifacts`; `E_CALIB_REQUIRED` on failure
- [ ] Task 4: Safety + tests (AC: 2)
  - [ ] Ensure every move goes through `arm.py`; verify stop-sentinel aborts calibration cleanly
  - [ ] Unit-test the mapping fit + persistence round-trip with synthetic/mocked frame shifts

## Dev Notes

- **Depends on:** Story 1.3 (`camera.py`), Story 1.5 (`arm.py` safe motion). This is the FIRST story that commands real motion — it must go entirely through `arm.py`; do not touch the driver directly.
- **What this is (and isn't):** this is *measurement*, not ML training. The architecture is explicit: hand-eye self-calibration learns the joint→pixel mapping so visual servoing is accurate without manual tuning. It is NOT the v2 learned policy (that's separate, GPU/ROCm, deferred). Keep it a deterministic geometric/optical fit.
- **Why it matters downstream:** `hold_center` (Story 2.4) uses this mapping to convert "target is N pixels off-center" → "move these joints." A good calibration is what makes the prototype servoing converge in few steps. The architecture notes calibration should make hold_center converge faster than uncalibrated.
- **Rigid camera mount assumption:** the mapping is only valid if the camera is fixed relative to the end effector (Story 1.2). If the mount moved, recalibration is required — surface `E_CALIB_REQUIRED` clearly.
- **Persistence:** profile lives in `calibration/`, persisted between sessions; include a version field so format changes are detectable. (Decision 2026-06-21: the reviewed calibration profiles `joints.json`/`handeye.json` are TRACKED in git for single-arm backup/reproducibility; only transient captures — sweep traces, logs, `.tmp`, patches — stay gitignored.) Reuse LeRobot's calibration facility where it fits, but the *hand-eye image-Jacobian* part is Dum-E-specific (LeRobot's own calibration is about joint zeroing/ranges; the joint→pixel mapping is ours).
- **Safety:** calibration moves are small and bounded; they still must respect `arm.py` limits + velocity caps + stop sentinel (AC 2). Keep deltas conservative.
- **Error code:** `E_CALIB_REQUIRED` (from §E) for failure/needed-recalibration.
- **Scope discipline:** produce the mapping + persistence + quality metric only. Do not build hold_center here (that's Story 2.4) — but design the persisted mapping format so 2.4 can consume it directly.

### Project Structure Notes

- NEW: `src/dum_e/calibration.py`, `scripts/calibrate.py`, persisted profile under `calibration/`. Tests for fit + persistence round-trip.

### References

- [Source: documents/planning-artifacts/architecture.md#Core Architectural Decisions (D5 — hold_center uses hand-eye visual servo; ① self-calibration)]
- [Source: documents/planning-artifacts/architecture.md#Truth 5 / The Engine (① Self-calibration: measurement, not policy training)]
- [Source: documents/planning-artifacts/architecture.md#Project Structure (calibration.py, scripts/calibrate.py, calibration/)]
- [Source: documents/planning-artifacts/prds/prd-dum-e-2026-06-19/prd.md#FR-11]
- [Source: documents/planning-artifacts/epics.md#Story 1.6]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
