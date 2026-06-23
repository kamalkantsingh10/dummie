#!/usr/bin/env python3
"""cinema — a smooth, cinematic camera move around a subject (the apple), recorded.

The arm-mounted camera films a subject the operator has framed up. With no IK
yet, the choreography is built from moves that keep a CENTERED subject in frame:
  * roll       (wrist_roll j5)         — subject stays centered, frame rolls (dutch)
  * dolly      (shoulder j2 + elbow j3)— push in / pull out along the look axis
  * parallax   (base j1 + camera_pan j6 counter) — arc AROUND the subject
  * tilt       (wrist_flex j4)         — gentle reveal

Motion is streamed as cosine-eased setpoints (glassy, single-direction per beat),
clamped to the config soft limits, with a stiction-breaking pre-roll BEFORE the
record cue so the on-camera motion starts already smooth. The arm-mounted camera
records a clip exactly as long as the move; a 3-2-1 countdown + printed timing let
you sync a second angle on your phone.

This is a BENCH cinematography tool: it streams low-level goals (clamped to the
same soft limits arm.py enforces) for smoothness. Runtime automation still uses
dum_e.arm.

Usage:
  PYTHONPATH=src .venv/bin/python scripts/cinema.py [--scale 1.0] [--countdown 5]
        [--speed 2200] [--acc 50] [--no-record] [--config PATH]

Stop: Ctrl-C (or touch runs/STOP is NOT honored here — this is low-level; use Ctrl-C).
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time

# allow importing the recorder that lives alongside this script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dum_e import camera, cli, config, rundir          # noqa: E402
from choreo import ArmCamRecorder                       # noqa: E402

A_TORQUE, A_ACC, A_GOAL, A_SPEED, A_POS = 40, 41, 42, 46, 56
DT = 0.02


def deg2raw(d: float) -> int:
    return round(2048 + d / 360.0 * 4096)


def raw2deg(r: int) -> float:
    return (r - 2048) * 360.0 / 4096.0


# --- the choreography ------------------------------------------------------
# Each BEAT is (label, duration_s, {motor_id: delta_deg_from_HERO}). Deltas are
# relative to the starting (framed) hero pose; joints not listed hold their value
# from the previous beat. Single-direction within a beat = smooth (no lash cross).
def beats(scale: float):
    s = scale
    return [
        ("breath in   (dolly)",      3.0, {2: +5 * s, 3: -6 * s}),
        ("dutch right (roll)",       3.5, {5: +24 * s}),
        ("orbit left  (parallax)",   6.0, {1: -16 * s, 6: +16 * s}),
        ("crane up    (reveal)",     4.0, {2: -10 * s, 4: +9 * s}),
        ("orbit right (parallax)",   7.0, {1: +18 * s, 6: -18 * s, 5: -24 * s}),
        ("dutch left  (roll)",       3.5, {5: -10 * s}),
        ("settle hero (return)",     4.5, {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}),
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="smooth cinematic camera move, recorded")
    ap.add_argument("--scale", type=float, default=1.0, help="amplitude multiplier (dial framing)")
    ap.add_argument("--speed", type=int, default=2200, help="servo goal speed (high = track our streamed curve)")
    ap.add_argument("--acc", type=int, default=50, help="servo acceleration")
    ap.add_argument("--countdown", type=int, default=5, help="seconds before motion (phone sync)")
    ap.add_argument("--no-record", dest="record", action="store_false")
    ap.add_argument("--out", default=None, help="clip path (default runs/<ts>/cinema_armcam.mp4)")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)

    cfg = config.load_config(args.config)
    ids = list(cfg.get("arm", {}).get("motor_ids", [1, 2, 3, 4, 5, 6]))
    port = cfg.get("arm", {}).get("port", "/dev/ttyUSB0")
    limits = cfg.get("safety", {}).get("joint_limits_deg") or [[-180, 180]] * len(ids)
    lim = {sid: tuple(limits[i]) for i, sid in enumerate(ids)}

    from scservo_sdk import PortHandler, PacketHandler
    porth = PortHandler(port)
    if not porth.openPort() or not porth.setBaudRate(cfg.get("arm", {}).get("baud", 1000000)):
        return cli.fail(cli.E_NO_MOTORS if hasattr(cli, "E_NO_MOTORS") else "E_NO_MOTORS",
                        f"could not open {port}")
    ph = PacketHandler(0)

    def pos(sid):
        for _ in range(6):
            try:
                v, c, _ = ph.read2ByteTxRx(porth, sid, A_POS)
                if c == 0:
                    pos.l[sid] = v
                    return v
            except Exception:
                pass
            time.sleep(0.002)
        return pos.l.get(sid, 2048)
    pos.l = {}

    def put(sid, d):
        lo, hi = lim[sid]
        d = max(lo, min(hi, d))
        ph.write2ByteTxRx(porth, sid, A_GOAL, deg2raw(d))

    # energize + read hero pose
    for sid in ids:
        ph.write1ByteTxRx(porth, sid, A_ACC, args.acc)
        ph.write2ByteTxRx(porth, sid, A_SPEED, args.speed)
        ph.write2ByteTxRx(porth, sid, A_GOAL, pos(sid))     # pin present before torque (no jerk)
        ph.write1ByteTxRx(porth, sid, A_TORQUE, 1)
    hero = {sid: round(raw2deg(pos(sid)), 2) for sid in ids}
    cli.log(f"hero pose: {[round(hero[s],1) for s in ids]}")

    rec = None
    clip = args.out or os.path.join(rundir.new_run_dir(), "cinema_armcam.mp4")
    if args.record:
        rec = ArmCamRecorder(clip, camera.CamConfig.from_config(cfg))
        rec.start()
        if not rec.wait_ready() or rec.error:
            cli.log(f"camera not ready ({rec.error}); continuing WITHOUT recording")
            rec.stop(); rec = None

    def stream(cur, tgt, dur):
        n = max(1, round(dur / DT))
        for i in range(1, n + 1):
            f = 0.5 - 0.5 * math.cos(math.pi * i / n)        # ease in/out, 0 vel at ends
            for sid in ids:
                put(sid, cur[sid] + (tgt[sid] - cur[sid]) * f)
            time.sleep(DT)

    try:
        # stiction-breaking pre-roll (OFF camera) on the joints that lead the move
        for _ in range(5):
            for sid in (1, 5, 6):
                put(sid, hero[sid] + 1.2)
            time.sleep(0.05)
            for sid in (1, 5, 6):
                put(sid, hero[sid] - 1.2)
            time.sleep(0.05)
        for sid in ids:
            put(sid, hero[sid])
        time.sleep(0.3)

        for n in range(args.countdown, 0, -1):
            cli.log(f"  filming in {n}... (start your phone)")
            time.sleep(1.0)
        if rec is not None:
            rec.begin()
        wall = time.time()
        cli.log(f">>> ACTION  (epoch {wall:.2f})")
        t0 = time.monotonic()

        cur = dict(hero)
        for label, dur, deltas in beats(args.scale):
            tgt = dict(cur)
            for sid, dd in deltas.items():
                tgt[sid] = hero[sid] + dd          # deltas are from HERO
            stream(cur, tgt, dur)
            cur = tgt
            cli.log(f"  {label:<24} t={time.monotonic()-t0:5.1f}s")
        dur_total = time.monotonic() - t0
        cli.log(f">>> CUT  (move took {dur_total:.2f}s)")
    finally:
        if rec is not None:
            rec.stop(); rec.join(timeout=5.0)
        porth.closePort()

    data = {"move_seconds": round(dur_total, 2), "wall_start_epoch": round(wall, 2), "scale": args.scale}
    artifacts = []
    if rec is not None and rec.frames:
        eff = rec.frames / dur_total if dur_total else 0.0
        data["clip"] = {"path": clip, "frames": rec.frames, "effective_fps": round(eff, 1)}
        artifacts.append(clip)
        cli.log(f"arm-cam clip: {rec.frames} frames @ ~{eff:.1f} fps -> {clip}")
    return cli.ok(data=data, artifacts=artifacts)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
