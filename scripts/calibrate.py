#!/usr/bin/env python3
"""calibrate — Story 1.6 self-calibration.

Subcommands:
  sweep    Teach-by-hand joint RANGE capture. Releases torque so you can move
           the arm by hand, and records the FULL position trace of all joints to
           a JSONL file (so we can detect encoder wrap, not just min/max).
           Stop with Ctrl-C / kill; pass --hold-after to re-energize at the end.
  analyze  Load a sweep JSONL and report per-joint range + wrap analysis (JSON).
  range    Servo range calibration, MOTION-FREE (one joint per run): hand-sweep
           the joint to both stops, then re-zero on the measured midpoint by
           shifting the homing offset (a config write — no powered motion, so a
           gravity joint never strains). Wrap-aware (unwrap), so near-360 joints
           are fine. Emits real soft limits for config.yaml. Torque off throughout.
  handeye  Hand-eye self-calibration: command small joint deltas, measure how
           the image shifts, and fit + persist the joint->pixel mapping (image
           Jacobian) that hold_center (Story 2.4) consumes. Commands real motion
           through arm.py; respects soft limits + velocity cap + stop sentinel.

All motion routes through dum_e.arm (the driver chokepoint). Sweep is read-only.
Run with:  PYTHONPATH=src .venv/bin/python scripts/calibrate.py handeye ...
"""
import argparse
import json
import os
import signal
import sys
import time

from dum_e import arm, calibration, cli, config, rundir


def _sweep(args) -> int:
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    if args.pidfile:
        with open(args.pidfile, "w") as pf:
            pf.write(str(os.getpid()))
    stop = {"v": False}
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("v", True))
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("v", True))

    period = 1.0 / args.hz
    n = 0
    with arm.Arm() as a, open(args.out, "w", buffering=1) as f:
        free = [args.joint] if args.joint else list(a.motor_ids)
        if args.no_hold:
            a.relax()      # EVERYTHING limp (no joint energized → no heating); support by hand
        else:
            a.hold()       # hold the whole arm so it stays supported...
            a.relax(free)  # ...then free ONLY the joint(s) being swept
        f.write(json.dumps({"meta": {"motor_ids": a.motor_ids, "hz": args.hz,
                                     "free": (a.motor_ids if args.no_hold else free)}}) + "\n")
        cli.log(f"RECORDING -> {args.out}  (free joint(s) {free}; sweep through the "
                f"full safe range). Stop with Ctrl-C / kill.")
        t0 = time.monotonic()
        deadline = t0 + args.seconds
        while not stop["v"] and time.monotonic() < deadline:
            raw = a.read_joints()["raw_steps"]
            f.write(json.dumps([round(time.monotonic() - t0, 3), *raw]) + "\n")
            n += 1
            time.sleep(period)
        if args.hold_after and not args.no_hold:
            a.hold(free)   # re-energize the freed joint(s) at current pose
            cli.log(f"torque re-enabled on {free} (holding current pose)")
        elif args.no_hold:
            a.relax()      # leave everything limp (no heating)
            cli.log("left all joints relaxed (heat-safe)")
    if args.pidfile:
        try:
            os.remove(args.pidfile)
        except FileNotFoundError:
            pass
    cli.log(f"stopped after {n} samples")
    return 0


def _analyze(args) -> int:
    loaded = calibration.load_sweep(args.infile)
    summary = calibration.summarize_sweeps(loaded)
    return cli.ok(data={"joints": summary, "n_samples": len(loaded["t"])},
                  artifacts=[args.infile])


def _capture_range_steps(a, sid, seconds):
    """Timed capture of one joint's full step trace while it is swept by hand,
    then UNWRAP it (undo 0<->4095 rollovers) before taking min/max — so a sweep
    that crosses the encoder wrap (e.g. a near-360deg joint) yields the TRUE
    contiguous travel, not the misleading raw encoder extremes. Returns
    (min_steps, max_steps, n_samples, n_dropped) where min/max are CONTINUOUS
    (may fall outside [0,4095]). Tolerates transient dropped packets."""
    trace = []
    dropped = 0
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            trace.append(a._bus.read_steps(sid))
        except arm.ArmError:
            dropped += 1
            time.sleep(0.01)
            continue
        time.sleep(0.04)
    if not trace:
        return None, None, 0, dropped
    cont = calibration.unwrap_steps(trace)
    return min(cont), max(cont), len(trace), dropped


def _range(args) -> int:
    """Servo joint-range calibration, MOTION-FREE (one joint per run):
      1. free the target joint (torque off) — no holding load, so it can't overheat;
      2. timed hand-sweep firmly to BOTH safe extremes -> measure true range
         (wrap-aware via unwrap, so near-360 joints are fine);
      3. re-zero on the measured midpoint by SHIFTING THE HOMING OFFSET — a config
         write, no powered motion, so a gravity-loaded joint never strains;
      4. derive a symmetric soft limit and merge into the calibration profile.
    Support/prop the arm by hand during the sweep. (This replaces the old powered
    re-center, which overloaded the gravity joints.)"""
    cfg = config.load_config(args.config)
    sid = args.joint
    motor_ids = list(cfg.get("arm", {}).get("motor_ids", [1, 2, 3, 4, 5, 6]))
    try:
        with arm.Arm(cfg=cfg) as a:
            if sid not in a.motor_ids:
                return cli.fail(cli.E_OUT_OF_BOUNDS, f"motor {sid} not in {a.motor_ids}")
            a.relax([sid])                             # free target; torque off -> no load

            cli.log(f">>> SWEEP motor {sid} firmly to BOTH safe extremes NOW — capturing "
                    f"{args.seconds:.0f}s (support the arm; hand motion only, no torque)...")
            lo, hi, n, dropped = _capture_range_steps(a, sid, args.seconds)
            if lo is None:
                return cli.fail(cli.E_CALIB_REQUIRED, f"motor {sid}: no samples")
            travel_steps = hi - lo
            travel_deg = travel_steps * arm._DEG_PER_STEP
            cli.log(f"  measured travel {travel_deg:.1f} deg (n={n}, dropped={dropped})")
            if travel_deg < args.min_travel:
                return cli.fail(cli.E_CALIB_REQUIRED,
                                f"motor {sid}: only {travel_deg:.0f} deg swept (< {args.min_travel:.0f}); "
                                f"sweep firmly to BOTH stops")
            if travel_deg > 350:
                cli.log(f"  WARN: near-360 travel ({travel_deg:.0f} deg) — wrap will sit in the dead zone")

            mid_raw = round((lo + hi) / 2)             # continuous midpoint (current frame)
            offset = a.recenter(sid, mid_raw)          # MOTION-FREE re-zero on the midpoint
            half_deg = travel_deg / 2
            limit = calibration.limit_from_range(-half_deg, half_deg, margin_deg=args.margin)
            half_steps = round(travel_steps / 2)
            prof = calibration.merge_joint_result(
                sid, homing_offset=offset, range_min=arm._CENTER - half_steps,
                range_max=arm._CENTER + half_steps, limit_deg=limit, path=args.out)
    except arm.ArmError as e:
        return cli.fail(e.code, e.message)

    ordered = calibration.joint_limits_for(prof, motor_ids)
    cli.log(f"\nmotor {sid} -> soft limit {limit}  (travel {travel_deg:.1f} deg, motion-free re-center).")
    cli.log("config.yaml safety.joint_limits_deg so far:")
    for mid, lim in zip(motor_ids, ordered):
        cli.log(f"    - [{lim[0]}, {lim[1]}]    # motor {mid}")

    return cli.ok(
        data={"motor_id": sid, "limit_deg": limit, "travel_deg": round(travel_deg, 1),
              "joint_limits_deg": ordered},
        artifacts=[args.out],
    )


def _handeye(args) -> int:
    import cv2

    from dum_e import camera

    cfg = config.load_config(args.config)
    cam = camera.CamConfig.from_config(cfg)
    deltas = tuple(args.deltas) if args.deltas else calibration.DEFAULT_DELTAS_DEG
    joints = args.joint or None  # default: all of arm.motor_ids

    run_dir = rundir.new_run_dir() if args.save_frames else None
    saved = []

    def frame_sink(label, gray):
        if run_dir is None:
            return
        p = rundir.frame_path(run_dir, f"calib_{label}", 0)
        cv2.imwrite(p, gray)
        saved.append(p)

    cap = camera.open_capture(cam)

    def grab():
        ok, frame = cap.read()
        if not ok or frame is None:
            raise camera.CameraError(cli.E_NO_CAMERA, "frame read failed during calibration")
        frame = camera._rotate_frame(frame, cam.rotate)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    cli.log(f"hand-eye calibration: joints={joints or 'all'} deltas={list(deltas)} deg")
    try:
        with arm.Arm(cfg=cfg) as a:
            profile = calibration.calibrate(
                a, grab, joints=joints, deltas_deg=deltas,
                settle_s=args.settle, created=rundir.compact_ts(),
                min_gain=args.min_gain, min_r2=args.min_r2,
                frame_sink=frame_sink if args.save_frames else None,
            )
    finally:
        cap.release()

    path = calibration.save_profile(profile, args.out)
    artifacts = [path] + saved

    err = profile.get("error")
    if err:
        return cli.fail(err["code"], err["message"])
    if not profile["ok"]:
        cov = profile["axis_coverage"]
        return cli.fail(
            cli.E_CALIB_REQUIRED,
            f"fit too weak to centre on both axes (x<-{cov['x']}, y<-{cov['y']}); "
            f"check the scene has texture and the mount is rigid, then recalibrate",
        )
    return cli.ok(
        data={
            "quality": profile["quality"],
            "axis_coverage": profile["axis_coverage"],
            "joints": profile["joints"],
            "frame_wh": profile["frame_wh"],
        },
        artifacts=artifacts,
    )


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="Dum-E self-calibration (Story 1.6)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sweep", help="teach-by-hand joint range capture (torque off)")
    s.add_argument("--out", default="calibration/sweep.jsonl")
    s.add_argument("--joint", type=int, default=None, help="free ONLY this motor id (others stay held)")
    s.add_argument("--no-hold", action="store_true", help="heat-safe: keep ALL joints torque-off (support by hand)")
    s.add_argument("--pidfile", default="calibration/sweep.pid", help="write PID here for clean stop")
    s.add_argument("--hz", type=float, default=50.0, help="sample rate")
    s.add_argument("--seconds", type=float, default=600.0, help="max duration (stop early with kill)")
    s.add_argument("--hold-after", action="store_true", default=True)
    s.add_argument("--no-hold-after", dest="hold_after", action="store_false")

    a = sub.add_parser("analyze", help="report range + wrap analysis from a sweep file")
    a.add_argument("infile")

    r = sub.add_parser("range", help="hand-sweep -> real joint soft limit, motion-free (one joint)")
    r.add_argument("--joint", type=int, required=True, help="motor id to calibrate")
    r.add_argument("--seconds", type=float, default=20.0, help="hand-sweep capture window")
    r.add_argument("--margin", type=float, default=calibration.DEFAULT_RANGE_MARGIN_DEG,
                   help="degrees to shrink the range inward for safety")
    r.add_argument("--min-travel", type=float, default=40.0,
                   help="reject sweeps shorter than this (deg) as incomplete")
    r.add_argument("--out", default=calibration.DEFAULT_JOINT_CALIB_PATH, help="calibration profile path")
    r.add_argument("--config", default=None, help="path to config.yaml (default: auto-discover)")

    h = sub.add_parser("handeye", help="fit + persist the joint->pixel image Jacobian")
    h.add_argument("--out", default=calibration.DEFAULT_PROFILE_PATH, help="profile path")
    h.add_argument("--joint", type=int, action="append", default=None,
                   help="motor id to excite (repeatable; default: all joints)")
    h.add_argument("--deltas", type=float, nargs="+", default=None,
                   help=f"excitation angles in deg (default {list(calibration.DEFAULT_DELTAS_DEG)})")
    h.add_argument("--settle", type=float, default=calibration.DEFAULT_SETTLE_S,
                   help="settle seconds after each move before grabbing a frame")
    h.add_argument("--min-gain", type=float, default=calibration.DEFAULT_MIN_GAIN_PX_PER_DEG,
                   help="min px/deg for a joint to count as a usable framing axis")
    h.add_argument("--min-r2", type=float, default=calibration.DEFAULT_MIN_R2,
                   help="min fit R^2 for a usable framing axis")
    h.add_argument("--save-frames", action="store_true",
                   help="also save captured frames to a run dir (debugging)")
    h.add_argument("--config", default=None, help="path to config.yaml (default: auto-discover)")

    args = ap.parse_args(argv)
    if args.cmd == "sweep":
        return _sweep(args)
    if args.cmd == "analyze":
        return _analyze(args)
    if args.cmd == "range":
        return _range(args)
    return _handeye(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
