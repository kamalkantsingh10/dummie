"""Self-calibration (FR-11) — measurement, NOT ML training.

Two parts (Story 1.6):
  1. Joint RANGE capture (teach-by-hand): record the full position trace while a
     joint is swept by hand, detect encoder wrap (the 4095<->0 rollover), and
     derive the true contiguous travel. This is what lets us set REAL soft limits
     and decide homing so position-mode moves never cross the wrap.
  2. Hand-eye joint->pixel mapping (image Jacobian) for hold_center — added next.

All motion goes through ``dum_e.arm`` (the driver chokepoint); this module never
imports the motor SDK. Range capture is read-only (torque off, human-driven).
"""

from __future__ import annotations

import json
import os

from dum_e import cli, safety

STEPS_PER_REV = 4096
_HALF = STEPS_PER_REV // 2          # 2048: a single-sample jump bigger than this = a wrap
_DEG_PER_STEP = 360.0 / STEPS_PER_REV


class CalibrationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def unwrap_steps(samples):
    """Undo 4095<->0 rollovers in a raw position trace.

    Returns a continuous trace (floats, may fall outside [0,4095]) starting at
    ``samples[0]``. A by-hand sweep can't physically move >180° between samples,
    so any single-step jump > 2048 is a wrap, not real motion.
    """
    if not samples:
        return []
    out = [float(samples[0])]
    for prev, cur in zip(samples, samples[1:]):
        d = cur - prev
        if d > _HALF:
            d -= STEPS_PER_REV
        elif d < -_HALF:
            d += STEPS_PER_REV
        out.append(out[-1] + d)
    return out


def analyze_sweep(samples, *, motor_id=None):
    """Summarize one joint's swept position trace.

    Returns raw min/max, whether the trace crossed the encoder wrap, and the
    TRUE contiguous travel (from the unwrapped trace).
    """
    raw = [int(s) for s in samples]
    if not raw:
        return {"motor_id": motor_id, "n_samples": 0, "wrapped": False}
    cont = unwrap_steps(raw)
    crossings = sum(1 for prev, cur in zip(raw, raw[1:]) if abs(cur - prev) > _HALF)
    cmin, cmax = min(cont), max(cont)
    travel = cmax - cmin
    return {
        "motor_id": motor_id,
        "n_samples": len(raw),
        "raw_min": min(raw),
        "raw_max": max(raw),
        "wrapped": crossings > 0,
        "wrap_crossings": crossings,
        "continuous_min": round(cmin, 1),
        "continuous_max": round(cmax, 1),
        "travel_steps": round(travel, 1),
        "travel_deg": round(travel * _DEG_PER_STEP, 1),
    }


def load_sweep(path):
    """Load a sweep JSONL file written by ``calibrate.py sweep``.

    Line 0 is ``{"meta": {"motor_ids": [...]}}``; each later line is
    ``[t, s1, s2, ...]``. Returns ``{"motor_ids", "t", "samples"}`` where
    ``samples[i]`` is the i-th joint's full trace.
    """
    motor_ids, times, rows = None, [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict) and "meta" in obj:
                motor_ids = obj["meta"]["motor_ids"]
                continue
            times.append(obj[0])
            rows.append(obj[1:])
    n = len(motor_ids or (rows[0] if rows else []))
    samples = [[row[j] for row in rows] for j in range(n)]
    return {"motor_ids": motor_ids, "t": times, "samples": samples}


def summarize_sweeps(loaded):
    """Per-joint :func:`analyze_sweep` over a loaded sweep."""
    ids = loaded.get("motor_ids") or list(range(len(loaded["samples"])))
    return [analyze_sweep(col, motor_id=ids[i]) for i, col in enumerate(loaded["samples"])]


# --- LeRobot-based joint-range calibration -> Dum-E soft limits ---------------
# arm.py drives LeRobot's homing + range-of-motion capture; these PURE helpers
# turn the recorded ranges into the config soft limits and a persisted profile.

DEFAULT_RANGE_MARGIN_DEG = 4.0      # shrink each joint's usable span inward for safety
# (4deg, not 3: at a 3deg margin the arm still grazed its own body at the extremes — 2026-06-21)
JOINT_CALIB_VERSION = 2
DEFAULT_JOINT_CALIB_PATH = "calibration/joints.json"


def limit_from_range(min_deg, max_deg, *, margin_deg=DEFAULT_RANGE_MARGIN_DEG):
    """One joint's ``[lo, hi]`` soft limit in degrees: the measured span shrunk
    inward by ``margin_deg`` on each side so commanded moves never reach the hard
    stop. Collapses to the midpoint if the margin exceeds the travel."""
    lo, hi = sorted((float(min_deg), float(max_deg)))
    lo, hi = lo + margin_deg, hi - margin_deg
    if hi < lo:
        lo = hi = (lo + hi) / 2
    return [round(lo, 1), round(hi, 1)]


def build_joint_limits(ranges, motor_ids, *, margin_deg=DEFAULT_RANGE_MARGIN_DEG):
    """Per-joint ``[lo, hi]`` degrees, ordered by ``motor_ids`` (each entry via
    :func:`limit_from_range`). ``ranges`` is the list of dicts from
    ``Arm.record_ranges`` (each has ``motor_id``, ``min_deg``, ``max_deg``)."""
    by_id = {r["motor_id"]: r for r in ranges}
    return [limit_from_range(by_id[s]["min_deg"], by_id[s]["max_deg"],
                             margin_deg=margin_deg) for s in motor_ids]


def build_calibration(ranges, homing_offsets, motor_ids):
    """Assemble the per-motor calibration dict consumed by ``Arm.write_calibration``.

    ``homing_offsets`` maps motor id -> offset (from ``Arm.home``). Returns
    ``{motor_id: {drive_mode, homing_offset, range_min, range_max}}`` in RAW steps."""
    by_id = {r["motor_id"]: r for r in ranges}
    cal = {}
    for sid in motor_ids:
        r = by_id[sid]
        lo, hi = sorted((r["min_steps"], r["max_steps"]))
        cal[sid] = {"drive_mode": 0, "homing_offset": int(homing_offsets[sid]),
                    "range_min": int(lo), "range_max": int(hi)}
    return cal


# Persistence accumulates ONE joint at a time (joints are calibrated separately),
# keyed by motor id, so re-running for a single joint updates just its entry.

def _write_joint_profile(profile, path):
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(profile, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)
    return path


def load_joint_calibration(path=DEFAULT_JOINT_CALIB_PATH):
    """Load the joint calibration profile, or raise ``E_CALIB_REQUIRED``."""
    try:
        with open(path) as f:
            prof = json.load(f)
    except FileNotFoundError as e:
        raise CalibrationError(cli.E_CALIB_REQUIRED, f"no joint calibration at {path}") from e
    if prof.get("version") != JOINT_CALIB_VERSION:
        raise CalibrationError(cli.E_CALIB_REQUIRED,
                               f"joint calibration {path} is v{prof.get('version')}; "
                               f"expected v{JOINT_CALIB_VERSION} — recalibrate")
    return prof


def merge_joint_result(motor_id, *, homing_offset, range_min, range_max,
                       limit_deg, path=DEFAULT_JOINT_CALIB_PATH):
    """Add/replace one joint's result in the profile (creating it if absent) and
    persist. Lets joints be calibrated one at a time and accumulate."""
    try:
        prof = load_joint_calibration(path)
    except CalibrationError:
        prof = {"version": JOINT_CALIB_VERSION, "kind": "joint_range_calibration", "motors": {}}
    prof.setdefault("motors", {})[str(motor_id)] = {
        "drive_mode": 0,
        "homing_offset": int(homing_offset),
        "range_min": int(range_min),
        "range_max": int(range_max),
        "limit_deg": [round(float(limit_deg[0]), 1), round(float(limit_deg[1]), 1)],
    }
    _write_joint_profile(prof, path)
    return prof


def joint_limits_for(profile, motor_ids, *, default=(-180.0, 180.0)):
    """Ordered ``joint_limits_deg`` list for ``motor_ids`` from a profile, using
    each calibrated joint's ``limit_deg`` and ``default`` for any not yet done.
    This is the block that goes into ``config.yaml``."""
    motors = (profile or {}).get("motors", {})
    out = []
    for sid in motor_ids:
        entry = motors.get(str(sid))
        out.append(list(entry["limit_deg"]) if entry else list(default))
    return out


# ============================================================================
# Part 2: hand-eye joint->pixel mapping (the image Jacobian for hold_center).
#
# For each joint we command small angular deltas (through dum_e.arm only) and
# measure how the whole image translates (phase correlation gives a subpixel,
# global shift). Pixel shift is linear in joint angle for small moves, so the
# slope (px per degree) of each axis IS that joint's column of the image
# Jacobian J. hold_center (Story 2.4) inverts J to turn "target is N px off
# centre" into a corrective joint move. This is geometric *measurement*, not
# policy training.
# ============================================================================

HANDEYE_VERSION = 2
HANDEYE_KIND = "handeye_image_jacobian"
DEFAULT_PROFILE_PATH = "calibration/handeye.json"

# Small, safe excitation angles per joint (degrees), measured vs the start pose.
DEFAULT_DELTAS_DEG = (-2.0, -1.0, 1.0, 2.0)
# A joint must shift the image at least this much to count as a usable framing
# axis; its linear fit must explain at least this fraction of the shift.
DEFAULT_MIN_GAIN_PX_PER_DEG = 2.0
DEFAULT_MIN_R2 = 0.90
DEFAULT_SETTLE_S = 0.25


def measure_shift(ref_gray, cur_gray):
    """Global translation (dx, dy) in pixels taking ``ref_gray`` -> ``cur_gray``.

    Uses phase correlation (subpixel, robust to lighting). Returns
    ``(dx, dy, response)`` where ``response`` in [0,1] is the peak confidence
    (a per-measurement quality signal). cv2 is imported lazily so the pure fit
    helpers below stay importable without it.
    """
    import cv2
    import numpy as np

    a = np.asarray(ref_gray, dtype=np.float32)
    b = np.asarray(cur_gray, dtype=np.float32)
    win = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a, b, win)
    return float(dx), float(dy), float(response)


def fit_axis(deltas_deg, shifts_px):
    """Least-squares slope of ``px = m * deg`` (forced through the origin) + R^2.

    Through-origin is physically exact: zero joint motion => zero image shift.
    R^2 is the no-intercept form ``1 - SS_res/sum(px^2)`` (1.0 = perfectly
    linear, ~0 = no linear relation). A joint that doesn't move the image has
    ~0 shift everywhere => slope 0, R^2 0 (reported, not an error).
    """
    import numpy as np

    x = np.asarray(deltas_deg, dtype=float)
    y = np.asarray(shifts_px, dtype=float)
    denom = float((x * x).sum())
    if denom == 0.0:
        return 0.0, 0.0
    m = float((x * y).sum() / denom)
    ss_res = float(((y - m * x) ** 2).sum())
    ss_tot0 = float((y * y).sum())
    if ss_tot0 <= 1e-9:
        return m, 0.0
    return m, max(0.0, 1.0 - ss_res / ss_tot0)


def fit_joint(motor_id, deltas_deg, shifts):
    """Fit one joint's Jacobian column from aligned (delta, (dx,dy)) samples.

    ``shifts`` is a list of ``(dx, dy)`` pixel shifts, one per delta. Returns the
    px/deg gains on each image axis, their R^2, and which axis the joint drives
    most (its "primary" axis for centring).
    """
    dxs = [s[0] for s in shifts]
    dys = [s[1] for s in shifts]
    gx, r2x = fit_axis(deltas_deg, dxs)
    gy, r2y = fit_axis(deltas_deg, dys)
    primary = "x" if abs(gx) >= abs(gy) else "y"
    return {
        "motor_id": motor_id,
        "px_per_deg": [round(gx, 4), round(gy, 4)],
        "r2": [round(r2x, 4), round(r2y, 4)],
        "primary_axis": primary,
        "gain": round(abs(gx) if primary == "x" else abs(gy), 4),
        "primary_r2": round(r2x if primary == "x" else r2y, 4),
        "n": len(deltas_deg),
    }


def assemble_profile(joint_fits, *, frame_wh, deltas_deg, created,
                     min_gain=DEFAULT_MIN_GAIN_PX_PER_DEG, min_r2=DEFAULT_MIN_R2):
    """Build the persisted profile + pass/fail from per-joint fits (pure).

    ``ok`` requires a usable joint covering BOTH image axes — that is the
    minimum for hold_center to recentre in x and y. A joint is usable if it
    moves the image >= ``min_gain`` px/deg with fit R^2 >= ``min_r2``.
    """
    joints = []
    coverage = {"x": None, "y": None}
    for jf in joint_fits:
        usable = jf["gain"] >= min_gain and jf["primary_r2"] >= min_r2
        rec = {**jf, "usable": usable}
        joints.append(rec)
        if usable and coverage[jf["primary_axis"]] is None:
            coverage[jf["primary_axis"]] = jf["motor_id"]
    usable_r2 = [j["primary_r2"] for j in joints if j["usable"]]
    ok = coverage["x"] is not None and coverage["y"] is not None
    return {
        "version": HANDEYE_VERSION,
        "kind": HANDEYE_KIND,
        "created": created,
        "frame_wh": list(frame_wh),
        "deltas_deg": list(deltas_deg),
        "units": {"jacobian": "px_per_deg", "image_axes": "x=right, y=down"},
        "joints": joints,
        "axis_coverage": coverage,
        "thresholds": {"min_gain_px_per_deg": min_gain, "min_r2": min_r2},
        "quality": {
            "n_usable": len(usable_r2),
            "min_usable_r2": round(min(usable_r2), 4) if usable_r2 else 0.0,
        },
        "ok": ok,
    }


def save_profile(profile, path=DEFAULT_PROFILE_PATH):
    """Persist the profile to ``path`` (atomic, deterministic overwrite).

    ``sort_keys`` + fixed indent + ``os.replace`` mean re-running calibration
    with the same inputs reproduces byte-identical output and never leaves a
    half-written file (AC 5).
    """
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(profile, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)
    return path


def load_profile(path=DEFAULT_PROFILE_PATH):
    """Load a persisted profile, or raise ``E_CALIB_REQUIRED``.

    A missing file or a version/kind mismatch (format changed, or the camera
    mount moved and a fresh calibration is needed) surfaces as
    ``E_CALIB_REQUIRED`` so callers can prompt a recalibration.
    """
    try:
        with open(path) as f:
            prof = json.load(f)
    except FileNotFoundError as e:
        raise CalibrationError(cli.E_CALIB_REQUIRED, f"no calibration profile at {path}") from e
    if prof.get("version") != HANDEYE_VERSION or prof.get("kind") != HANDEYE_KIND:
        raise CalibrationError(
            cli.E_CALIB_REQUIRED,
            f"calibration profile {path} is v{prof.get('version')} "
            f"({prof.get('kind')}); expected v{HANDEYE_VERSION} {HANDEYE_KIND} — recalibrate",
        )
    return prof


def _delta_vector(n, index, value):
    v = [0.0] * n
    v[index] = value
    return v


def calibrate(arm, grab, *, joints=None, deltas_deg=DEFAULT_DELTAS_DEG,
              settle_s=DEFAULT_SETTLE_S, measure=measure_shift, sleep=None,
              stop_path=None, min_gain=DEFAULT_MIN_GAIN_PX_PER_DEG,
              min_r2=DEFAULT_MIN_R2, created=None, frame_sink=None):
    """Drive each joint through small deltas and fit the joint->pixel Jacobian.

    Args:
      arm: a connected ``dum_e.arm.Arm`` — the SOLE motion path (AC 2). Every
        move here goes through ``arm.step``, which clamps to soft limits, caps
        velocity, and aborts on the stop sentinel.
      grab: ``callable() -> 2D grayscale ndarray`` returning the current frame.
      measure: ``callable(ref, cur) -> (dx, dy, response)`` (injectable for tests).
      joints: motor ids to excite (default: all of ``arm.motor_ids``).

    Returns a profile dict (the same object that gets persisted). On a stop
    request it returns early with ``ok=False`` and ``error.code=E_STOPPED``;
    the arm is left holding position.
    """
    import numpy as np

    sleep = sleep if sleep is not None else __import__("time").sleep
    ids = list(arm.motor_ids)
    targets = list(joints) if joints else list(ids)
    n = len(ids)

    def _stopped():
        return safety.stop_requested(path=stop_path)

    ref = np.asarray(grab())
    frame_wh = [int(ref.shape[1]), int(ref.shape[0])]
    if frame_sink:
        frame_sink("ref", ref)

    joint_fits = []
    for mid in targets:
        if mid not in ids:
            cli.log(f"WARN: motor {mid} not in arm.motor_ids {ids}; skipped")
            continue
        idx = ids.index(mid)
        if _stopped():
            return _stopped_profile(frame_wh, deltas_deg, created, joint_fits)

        deltas, shifts, responses, offset = [], [], [], 0.0
        for d in sorted(deltas_deg):
            if _stopped():
                arm.step(_delta_vector(n, idx, -offset))  # best-effort return to start
                return _stopped_profile(frame_wh, deltas_deg, created, joint_fits)
            res = arm.step(_delta_vector(n, idx, d - offset), stop_path=stop_path)
            if not res.get("ok"):
                if res.get("stopped"):
                    return _stopped_profile(frame_wh, deltas_deg, created, joint_fits)
                cli.log(f"WARN: motor {mid} step to {d:+.1f} deg not ok: {res.get('error')}")
            offset = d
            if settle_s:
                sleep(settle_s)
            cur = np.asarray(grab())
            dx, dy, response = measure(ref, cur)
            deltas.append(d)
            shifts.append((dx, dy))
            responses.append(response)
            if frame_sink:
                frame_sink(f"m{mid}_{d:+.1f}", cur)

        arm.step(_delta_vector(n, idx, -offset), stop_path=stop_path)  # back to start
        jf = fit_joint(mid, deltas, shifts)
        jf["mean_response"] = round(float(np.mean(responses)) if responses else 0.0, 4)
        joint_fits.append(jf)
        cli.log(f"motor {mid}: {jf['gain']:.2f} px/deg on {jf['primary_axis']} "
                f"(R^2={jf['primary_r2']:.3f}, conf={jf['mean_response']:.2f})")

    profile = assemble_profile(joint_fits, frame_wh=frame_wh, deltas_deg=deltas_deg,
                               created=created, min_gain=min_gain, min_r2=min_r2)
    return profile


def _stopped_profile(frame_wh, deltas_deg, created, joint_fits):
    prof = assemble_profile(joint_fits, frame_wh=frame_wh, deltas_deg=deltas_deg,
                            created=created)
    prof["ok"] = False
    prof["error"] = {"code": cli.E_STOPPED, "message": "stop sentinel present; calibration aborted"}
    return prof
