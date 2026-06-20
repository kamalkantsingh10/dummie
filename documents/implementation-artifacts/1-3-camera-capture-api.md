# Story 1.3: Camera capture API (`camera.py`)

Status: ready-for-dev

## Story

As a developer,
I want a `camera.py` that captures a still frame to disk and reports its resolution,
so that survey, calibration, and critic steps have frames to work from.

## Acceptance Criteria

1. A capture function in `src/dum_e/camera.py` grabs a single frame from the configured camera and saves it under the current run dir's `frames/`, returning the saved path and `frame_wh = [w, h]`.
2. `scripts/survey.py` (capture mode) wraps the function and emits the standard JSON envelope with the frame path in `artifacts` and `frame_wh` in `data`.
3. An unreachable/unopenable camera returns `ok:false` with error code `E_NO_CAMERA` (no traceback to stdout).
4. Saved frame filenames follow the convention `frames/<episode_id>_<step:04d>.png` (a survey capture may use a survey/episode id with step 0).
5. Frame size + path are reported using the frozen coordinate convention (absolute pixels; `frame_wh` always paired with any future box).
6. A custom camera mount is designed, 3D-printed, and rigidly attached to the wrist-roll (motor 5) output, with the lens pointing **outward along the roll axis** (so motor 5 rotates the image landscape↔portrait), and the USB cable strain-relieved with a service loop for 90°+ roll.

## Tasks / Subtasks

- [ ] Task 1: Run-dir helper (AC: 1, 4)
  - [ ] Implement `src/dum_e/rundir.py`: create/return `runs/<UTC-compact-ts>/` with `clips/`, `frames/` subdirs; provide path helpers for frame/clip filenames
- [ ] Task 2: Camera capture (AC: 1, 3, 5)
  - [ ] Implement `camera.py` capture using OpenCV (`VideoCapture(camera_index)` from `config.yaml`); read one frame, write PNG to `frames/`, return `{path, frame_wh}`
  - [ ] Handle open/read failure → raise a typed error mapped to `E_NO_CAMERA`
  - [ ] Release the device handle cleanly (context manager) — no leaked captures
- [ ] Task 3: CLI wrapper (AC: 2, 3)
  - [ ] Implement `scripts/survey.py` capture mode using the `dum_e/cli.py` JSON envelope helper; `artifacts=[frame_path]`, `data={frame_wh, ...}`
- [ ] Task 4: Tests
  - [ ] `tests/` unit test for filename convention + envelope shape (mock the camera read so tests don't need hardware)
- [ ] Task 5: Camera mount — design, print, attach (AC: 6) [PHYSICAL]
  - [ ] CAD a mount for the Image+ Fic760x camera that bolts to the wrist-roll (motor 5) output horn; lens points outward **along the roll axis** so motor 5 = landscape↔portrait
  - [ ] Make it **rigid** (no flex/wobble — hand-eye calibration in Story 1.6 assumes the camera is fixed relative to the wrist) and **lightweight**
  - [ ] Add a USB cable strain-relief / service loop so a 90°+ roll never tugs or unplugs the cable
  - [ ] (Optional hedge) leave a small flat boss + 2× M2/M3 holes near the camera for a future IMU, per the sensor discussion — do NOT wire anything now
  - [ ] 3D-print it, attach the camera, and mount to the arm; re-verify a capture (`scripts/survey.py`) is upright/clear (set the `rotate` option if the mount orientation needs it)

## Dev Notes

- **Depends on:** Story 1.1 (scaffold, `cli.py`, `config.yaml`, `rundir`) and Story 1.2 (a real camera + recorded `camera_index`). Tests should mock the device so they run without hardware.
- **Frozen conventions (Implementation Patterns §B, §D):** frame images saved as `frames/<ep>_<step:04d>.png`; `frame_wh=[w,h]`; this `frame_wh` is the pairing partner for any bounding box returned later (boxes are absolute integer pixels, origin top-left). Establish it here so acquire/critic stay consistent.
- **Script I/O contract (§A):** one JSON object to stdout; logs to stderr; use the `dum_e/cli.py` helper. Error code on failure: **`E_NO_CAMERA`** (from the namespaced error-code list).
- **This module also owns the background recorder later** (Story 3.3 adds clip recording to `camera.py`). Keep the capture path and any device-open logic factored so the recorder can reuse it. Don't build the recorder now — capture-still only.
- **How Claude "sees":** downstream, Claude reads these saved frame images via its Read tool (survey/critic). So the saved frame must be a normal, readable image file (PNG) at a path returned in `artifacts`.
- **Recommended `survey.py` shape:** it will gain the Claude-driven "list subjects" behavior in Story 2.2; for now it only needs a capture mode that returns a frame. Keep the script thin so 2.2 can extend it.
- **Camera mount (Task 5) requirements:** rigid + lightweight; bolts to the wrist-roll (motor 5) output; lens **outward along the roll axis** so motor 5 gives landscape↔portrait; cable service loop for 90°+ roll. Rigidity is non-negotiable — Story 1.6 hand-eye calibration assumes a fixed camera-to-wrist transform. Camera = Image+ Fic760x (USB UVC, /dev/video0). v1 is a 5-DoF camera arm (gripper/motor 6 omitted; camera takes its place) — see [[dum-e-concept]].
- **Add a `rotate` option to `camera.py` + `config.yaml`:** bench captures came out rotated ~90° (sideways mount). camera.py should apply a configurable rotation (0/90/180/270) on capture so frames are upright regardless of physical mount orientation. (Settings already partly implemented from bench bring-up — see [[camera-hardware]].)

### Project Structure Notes

- NEW: `src/dum_e/camera.py`, `src/dum_e/rundir.py`, `scripts/survey.py` (capture mode). All paths per the architecture tree.

### References

- [Source: documents/planning-artifacts/architecture.md#Implementation Patterns (A Script I/O, B Coordinate/Units, D Naming & run-dir layout)]
- [Source: documents/planning-artifacts/architecture.md#Project Structure (camera.py, rundir.py, scripts/survey.py)]
- [Source: documents/planning-artifacts/prds/prd-dum-e-2026-06-19/prd.md#FR-2 / FR-8 (capture)]
- [Source: documents/planning-artifacts/epics.md#Story 1.3]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
