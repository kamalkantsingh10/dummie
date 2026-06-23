#!/usr/bin/env python3
"""perform — a fast, punchy 'wake up, show off, rest' routine, recorded.

Story: the arm WAKES from its parked rest pose, snaps up to the framed SHOOT
pose, performs a few fast, *noticeable* moves that keep the apple in frame
(framing-safe: roll / dolly / tilt / small counter-panned arc), then returns to
rest. Both poses come from calibration/poses.json (recorded live).

Motion is streamed as cosine-eased setpoints (smooth) but FAST — with P=16 on all
servos the speed kills the low-speed stick-slip. Endpoints honor the recorded
poses; the action beats are clamped to the config soft limits (union'd with the
recorded poses so a hand-set rest just past a limit is still honored).

Usage:
  PYTHONPATH=src .venv/bin/python scripts/perform.py [--scale 1.0] [--countdown 5]
        [--speed 3000] [--acc 80] [--no-record] [--config PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dum_e import camera, cli, config, rundir          # noqa: E402
from choreo import ArmCamRecorder                       # noqa: E402

A_TORQUE, A_ACC, A_GOAL, A_SPEED, A_POS = 40, 41, 42, 46, 56
DT = 0.02
POSES = "calibration/poses.json"


# ACTION beats: (label, duration_s, {motor_id: delta_deg_from_SHOOT}). Each beat
# is a single-direction eased sweep. Framing-safe moves keep the apple centered.
def action_beats(s):
    # Framing-safe only: dolly (j2/j3), dutch roll (j5), tilt-DOWN nod (j4).
    # j1 (base pan) and j6 (camera pan) stay at hero the WHOLE time, so the
    # camera never re-points off the apple — it can't drift out of frame.
    return [
        ("push in  (dolly)",   0.8, {2: +12 * s, 3: -14 * s}),
        ("dutch whip R",       0.7, {5: +38 * s}),
        ("dutch whip L",       1.1, {5: -38 * s}),
        ("roll level",         0.6, {5: 0}),
        ("pull back (reveal)", 0.9, {2: -8 * s, 3: +10 * s}),
        ("punch in close",     0.7, {2: +14 * s, 3: -16 * s}),
        ("nod down (tilt)",    0.6, {4: +16 * s}),
        ("nod level",          0.6, {4: 0}),
        ("dutch hold R",       0.7, {5: +26 * s}),
        ("settle to hero",     0.7, {2: 0, 3: 0, 4: 0, 5: 0}),
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fast wake/perform/rest routine, recorded")
    ap.add_argument("--scale", type=float, default=1.0, help="action amplitude multiplier")
    ap.add_argument("--speed", type=int, default=3000, help="servo goal speed (high = track our curve)")
    ap.add_argument("--acc", type=int, default=80)
    ap.add_argument("--wake", type=float, default=1.8, help="seconds for the wake lift rest->shoot")
    ap.add_argument("--countdown", type=int, default=5)
    ap.add_argument("--no-record", dest="record", action="store_false")
    ap.add_argument("--out", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)

    cfg = config.load_config(args.config)
    ids = list(cfg["arm"]["motor_ids"])
    port = cfg["arm"].get("port", "/dev/ttyUSB0")
    cfg_lim = cfg.get("safety", {}).get("joint_limits_deg") or [[-180, 180]] * len(ids)

    if not os.path.exists(POSES):
        return cli.fail("E_CALIB_REQUIRED", f"{POSES} missing — record shoot+rest poses first")
    poses = json.load(open(POSES))
    if "shoot" not in poses or "rest" not in poses:
        return cli.fail("E_CALIB_REQUIRED", "poses.json needs both 'shoot' and 'rest'")
    shoot = {sid: poses["shoot"]["deg"][i] for i, sid in enumerate(ids)}
    rest = {sid: poses["rest"]["deg"][i] for i, sid in enumerate(ids)}

    # effective limits = config soft limits, widened to include the recorded poses
    lim = {}
    for i, sid in enumerate(ids):
        lo, hi = cfg_lim[i]
        lim[sid] = (min(lo, shoot[sid], rest[sid]), max(hi, shoot[sid], rest[sid]))

    from scservo_sdk import PortHandler, PacketHandler
    porth = PortHandler(port)
    porth.openPort(); porth.setBaudRate(cfg["arm"].get("baud", 1000000))
    ph = PacketHandler(0)

    def raw(sid):
        for _ in range(6):
            try:
                v, c, _ = ph.read2ByteTxRx(porth, sid, A_POS)
                if c == 0:
                    raw.l[sid] = v
                    return v
            except Exception:
                pass
            time.sleep(0.002)
        return raw.l.get(sid, 2048)
    raw.l = {}

    def put(sid, d):
        lo, hi = lim[sid]
        d = max(lo, min(hi, d))
        ph.write2ByteTxRx(porth, sid, A_GOAL, round(2048 + d / 360.0 * 4096))

    # pin each joint at its ACTUAL present (unclamped) then torque on -> no snap
    for sid in ids:
        ph.write1ByteTxRx(porth, sid, A_ACC, args.acc)
        ph.write2ByteTxRx(porth, sid, A_SPEED, args.speed)
        ph.write2ByteTxRx(porth, sid, A_GOAL, raw(sid))
        ph.write1ByteTxRx(porth, sid, A_TORQUE, 1)
    cur = {sid: round((raw(sid) - 2048) * 360.0 / 4096, 2) for sid in ids}

    rec = None
    clip = args.out or os.path.join(rundir.new_run_dir(), "perform_armcam.mp4")
    if args.record:
        rec = ArmCamRecorder(clip, camera.CamConfig.from_config(cfg))
        rec.start()
        if not rec.wait_ready() or rec.error:
            cli.log(f"camera not ready ({rec.error}); continuing WITHOUT recording")
            rec.stop(); rec = None

    def stream(frm, to, dur):
        n = max(1, round(dur / DT))
        for i in range(1, n + 1):
            f = 0.5 - 0.5 * math.cos(math.pi * i / n)
            for sid in ids:
                put(sid, frm[sid] + (to[sid] - frm[sid]) * f)
            time.sleep(DT)
        return dict(to)

    try:
        for n in range(args.countdown, 0, -1):
            cli.log(f"  filming in {n}... (start your phone)")
            time.sleep(1.0)
        if rec is not None:
            rec.begin()
        wall = time.time(); t0 = time.monotonic()
        cli.log(f">>> ACTION (epoch {wall:.2f})")

        cli.log("WAKE  rest -> shoot")
        cur = stream(cur, shoot, args.wake)
        time.sleep(0.15)

        for label, dur, deltas in action_beats(args.scale):
            tgt = dict(cur)
            for sid, dd in deltas.items():
                tgt[sid] = shoot[sid] + dd
            cur = stream(cur, tgt, dur)
            cli.log(f"  {label:<20} t={time.monotonic()-t0:5.1f}s")

        cli.log("RETURN  shoot -> rest")
        cur = stream(cur, shoot, 0.5)
        cur = stream(cur, rest, args.wake)
        dur_total = time.monotonic() - t0
        cli.log(f">>> CUT ({dur_total:.2f}s)")
    finally:
        if rec is not None:
            rec.stop(); rec.join(timeout=5.0)
        # power down at rest (low-load pose) so it truly 'rests'
        for sid in ids:
            ph.write1ByteTxRx(porth, sid, A_TORQUE, 0)
        porth.closePort()

    data = {"seconds": round(dur_total, 2), "wall_start_epoch": round(wall, 2), "scale": args.scale}
    artifacts = []
    if rec is not None and rec.frames:
        data["clip"] = {"path": clip, "frames": rec.frames,
                        "effective_fps": round(rec.frames / dur_total, 1) if dur_total else 0}
        artifacts.append(clip)
        cli.log(f"arm-cam clip: {rec.frames} frames -> {clip}")
    return cli.ok(data=data, artifacts=artifacts)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
