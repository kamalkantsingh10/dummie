#!/usr/bin/env python3
"""Gentle 'dance' for the 5-DoF SO-101 camera arm — every move capped to a
max angle (default 45 deg) to ONE side of each joint's rest position.

⚠️  BENCH TOOL ONLY — bypasses the arm.py safety chokepoint (Story 1.5) and
drives multiple joints OPEN-LOOP with no soft limits. This caused elbow↔shoulder
collisions before limits existed (see servo-calibration-notes). Do NOT use for
runtime motion. Runtime/automation must route through dum_e.arm (move_to/step).
Kept only as a manual bring-up demo; prefer arm.py once Story 1.6 homing lands.

Usage: python scripts/dance.py [--max-deg 45] [--speed 380] [--port /dev/ttyUSB0]
"""
from __future__ import annotations

import argparse
import time

from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

A_TORQUE, A_ACC, A_GOAL, A_SPEED, A_POS = 40, 41, 42, 46, 56
IDS = [1, 2, 3, 4, 5]
STEPS_PER_DEG = 4096 / 360.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=1000000)
    ap.add_argument("--max-deg", type=float, default=45.0)
    ap.add_argument("--speed", type=int, default=380)   # gentle
    a = ap.parse_args()
    cap = int(a.max_deg * STEPS_PER_DEG)                 # max steps to one side

    port = PortHandler(a.port); port.openPort(); port.setBaudRate(a.baud)
    ph = PacketHandler(0)

    start, sign = {}, {}
    for i in IDS:
        p, comm, _ = ph.read2ByteTxRx(port, i, A_POS)
        if comm != COMM_SUCCESS:
            print(f"servo {i} not responding"); port.closePort(); return
        start[i] = p
        sign[i] = -1 if p > 2048 else 1                  # safe inward direction
        ph.write1ByteTxRx(port, i, A_ACC, 12)
        ph.write2ByteTxRx(port, i, A_SPEED, a.speed)
        ph.write1ByteTxRx(port, i, A_TORQUE, 1)

    def go(i, frac, dwell):
        """Move joint i to start + sign*frac*cap (frac in 0..1)."""
        off = int(sign[i] * frac * cap)
        goal = max(60, min(4035, start[i] + off))
        ph.write2ByteTxRx(port, i, A_GOAL, goal)
        time.sleep(dwell)

    def home(ids, dwell=0.4):
        for i in ids:
            ph.write2ByteTxRx(port, i, A_GOAL, start[i])
        time.sleep(dwell)

    try:
        print("🤖 dance: wave up the arm")
        for i in IDS:
            go(i, 1.0, 0.30)
        time.sleep(0.2); home(reversed(IDS))

        print("🤖 base sweep")
        go(1, 1.0, 0.6); go(1, 0.0, 0.6)

        print("🤖 nod (tilt)")
        for _ in range(2):
            go(4, 0.9, 0.35); go(4, 0.0, 0.35)

        print("🤖 portrait <-> landscape twist")
        go(5, 1.0, 0.7); go(5, 0.0, 0.7)

        print("🤖 bow (shoulder + elbow together)")
        ph.write2ByteTxRx(port, 2, A_GOAL, max(60, min(4035, start[2] + int(sign[2] * 0.85 * cap))))
        ph.write2ByteTxRx(port, 3, A_GOAL, max(60, min(4035, start[3] + int(sign[3] * 0.85 * cap))))
        time.sleep(0.7); home([2, 3], 0.7)

        print("🤖 shimmy finale")
        for _ in range(3):
            for i in IDS: go(i, 0.4, 0.10)
            for i in IDS: go(i, 0.0, 0.10)
    finally:
        home(IDS, 0.6)
        for i in IDS:
            ph.write1ByteTxRx(port, i, A_TORQUE, 0)  # release
        port.closePort()
        print("✅ dance complete — back home, torque released")


if __name__ == "__main__":
    main()
