#!/usr/bin/env python3
"""choreo — a SAFE servo choreography, recorded + timed (bench demo / video).

Unlike scripts/dance.py (which bypasses the safety layer), EVERY move here
routes through dum_e.arm, so soft joint limits, the per-tick velocity cap and
the STOP sentinel are all enforced.

Routine:
  1. center each joint to 0 deg, ONE AT A TIME (default order 6->1; the others
     stay energized/holding so the arm never collapses);
  2. move each joint to +<angle> deg, ONE AT A TIME (one direction);
  3. move ALL joints together back to center.

While it runs, the ARM-MOUNTED camera records a POV clip (background thread) for
exactly the length of the motion. A 3-2-1 countdown + a printed start timestamp
and total duration let you sync a second angle filmed on your phone; stitch the
two side-by-side afterward (see the ffmpeg hint printed at the end).

Usage:
  PYTHONPATH=src .venv/bin/python scripts/choreo.py
  PYTHONPATH=src .venv/bin/python scripts/choreo.py --angle 30 --order 6,5,4,3,2,1 \
        [--speed 500] [--acc 20] [--settle 0.4] [--countdown 5] [--no-record]

Stop at any time:  touch runs/STOP
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time

from dum_e import arm, camera, cli, config, rundir


class ArmCamRecorder(threading.Thread):
    """Records the arm-mounted camera to mp4 until stop() is called.

    Runs in its own thread so the main thread can drive the arm concurrently
    (camera is on /dev/video*, motors on the serial bus — independent devices).
    The clip length therefore tracks the motion length exactly.
    """

    def __init__(self, out_path: str, cam: camera.CamConfig):
        super().__init__(daemon=True)
        self.out_path, self.cam = out_path, cam
        self._stop_evt = threading.Event()
        self._ready = threading.Event()
        self._go = threading.Event()
        self.frames = 0
        self.frame_wh = None
        self.t_start = None
        self.t_end = None
        self.error = None

    def stop(self):
        self._stop_evt.set()

    def begin(self):
        """Cue the recorder to START writing frames (call at ACTION)."""
        self._go.set()

    def wait_ready(self, timeout=8.0) -> bool:
        return self._ready.wait(timeout)

    def run(self):
        import cv2
        cap = writer = None
        try:
            cap = camera.open_capture(self.cam)
            for _ in range(8):                 # warm up (exposure/AE settle)
                cap.read()
            self._ready.set()                  # tell main we can start on cue
            while not self._go.is_set() and not self._stop_evt.is_set():
                cap.read()                     # drain to keep frames fresh until ACTION
            while not self._stop_evt.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                frame = camera._rotate_frame(frame, self.cam.rotate)
                if writer is None:
                    h, w = frame.shape[:2]
                    self.frame_wh = [int(w), int(h)]
                    self.t_start = time.time()
                    writer = cv2.VideoWriter(
                        self.out_path, cv2.VideoWriter_fourcc(*"mp4v"),
                        self.cam.fps, (self.frame_wh[0], self.frame_wh[1]))
                writer.write(frame)
                self.frames += 1
            self.t_end = time.time()
        except Exception as e:                 # never let the recorder kill the run
            self.error = f"{type(e).__name__}: {e}"
            self._ready.set()
        finally:
            if writer is not None:
                writer.release()
            if cap is not None:
                cap.release()


def _positions(a):
    return a.read_joints()["joint_pos"]


def _log_pose(a, label):
    p = _positions(a)
    cli.log(f"{label:<24} {[round(x, 1) for x in p]}")
    return p


def _move_one(a, idx, target_deg, *, acc, speed):
    tgt = _positions(a)
    tgt[idx] = float(target_deg)
    return a.move_to(tgt, acc=acc, speed=speed)


def _run_choreo(a, order, idx, angle, acc, speed, settle):
    a.hold()
    _log_pose(a, "start")

    cli.log(f"PHASE 1 - center one-by-one ({'->'.join(map(str, order))})")
    for sid in order:
        r = _move_one(a, idx[sid], 0.0, acc=acc, speed=speed)
        time.sleep(settle)
        _log_pose(a, f"  j{sid} -> 0")
        if not r["ok"]:
            return r

    cli.log(f"PHASE 2 - +{angle:g} deg one-by-one ({'->'.join(map(str, order))})")
    for sid in order:
        r = _move_one(a, idx[sid], angle, acc=acc, speed=speed)
        time.sleep(settle)
        _log_pose(a, f"  j{sid} -> +{angle:g}")
        if not r["ok"]:
            return r

    cli.log("PHASE 3 - all together -> center")
    r = a.move_to([0.0] * len(a.motor_ids), acc=acc, speed=speed)
    time.sleep(settle + 0.2)
    _log_pose(a, "  all -> 0")
    return r


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="safe servo choreography, recorded + timed")
    ap.add_argument("--angle", type=float, default=30.0, help="one-direction angle in deg (default 30)")
    ap.add_argument("--order", default="6,5,4,3,2,1", help="motor-id order for the one-by-one phases")
    ap.add_argument("--speed", type=int, default=500, help="servo goal speed")
    ap.add_argument("--acc", type=int, default=20, help="servo acceleration")
    ap.add_argument("--settle", type=float, default=0.4, help="pause (s) after each step")
    ap.add_argument("--countdown", type=int, default=5, help="seconds of 3-2-1 before motion (phone sync)")
    ap.add_argument("--no-record", dest="record", action="store_false", help="skip arm-cam recording")
    ap.add_argument("--out", default=None, help="arm-cam clip path (default: runs/<ts>/choreo_armcam.mp4)")
    ap.add_argument("--config", default=None, help="path to config.yaml (default: auto-discover)")
    args = ap.parse_args(argv)

    cfg = config.load_config(args.config)
    try:
        order = [int(x) for x in args.order.split(",") if x.strip()]
    except ValueError:
        return cli.fail(cli.E_OUT_OF_BOUNDS, f"bad --order {args.order!r}; want e.g. 6,5,4,3,2,1")

    run_dir = rundir.new_run_dir()
    clip_path = args.out or os.path.join(run_dir, "choreo_armcam.mp4")

    rec = None
    if args.record:
        cam = camera.CamConfig.from_config(cfg)
        rec = ArmCamRecorder(clip_path, cam)
        rec.start()
        if not rec.wait_ready() or rec.error:
            cli.log(f"camera not ready ({rec.error}); continuing WITHOUT recording")
            rec.stop(); rec = None

    try:
        for n in range(args.countdown, 0, -1):
            cli.log(f"  filming in {n}... (start your phone)")
            time.sleep(1.0)
        if rec is not None:
            rec.begin()                        # arm-cam starts writing NOW (t=0 == ACTION)
        wall_start = time.time()
        cli.log(f">>> ACTION  (epoch {wall_start:.2f})")
        t0 = time.monotonic()

        with arm.Arm(cfg=cfg) as a:
            bad = [m for m in order if m not in a.motor_ids]
            if bad:
                return cli.fail(cli.E_OUT_OF_BOUNDS, f"unknown motor id(s) {bad}; have {a.motor_ids}")
            idx = {m: i for i, m in enumerate(a.motor_ids)}
            r = _run_choreo(a, order, idx, args.angle, args.acc, args.speed, args.settle)

        dur = time.monotonic() - t0
        cli.log(f">>> CUT  (motion took {dur:.2f}s)")
    except arm.ArmError as e:
        return cli.fail(e.code, e.message)
    finally:
        if rec is not None:
            rec.stop(); rec.join(timeout=5.0)

    data = {"motion_seconds": round(dur, 2), "wall_start_epoch": round(wall_start, 2),
            "ok": r["ok"], "warnings": r["warnings"]}
    artifacts = []
    if rec is not None and rec.frames:
        eff = rec.frames / dur if dur else 0.0
        data["clip"] = {"path": clip_path, "frames": rec.frames,
                        "frame_wh": rec.frame_wh, "effective_fps": round(eff, 1)}
        artifacts.append(clip_path)
        cli.log(f"arm-cam clip: {rec.frames} frames @ ~{eff:.1f} fps -> {clip_path}")
        cli.log("to stitch side-by-side with your phone clip (re-times both to match):")
        cli.log(f'  ffmpeg -i {clip_path} -i PHONE.mp4 -filter_complex \\')
        cli.log('    "[0:v]scale=-2:720[a];[1:v]scale=-2:720[b];[a][b]hstack" -y sidebyside.mp4')

    if not r["ok"]:
        return cli.fail(r["error"]["code"], r["error"]["message"])
    return cli.ok(data=data, artifacts=artifacts)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
