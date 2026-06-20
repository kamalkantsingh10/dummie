#!/usr/bin/env python3
"""SO-101 servo bench helper — scan the Feetech bus and (optionally) set a servo ID.

Bench/assembly tool for Story 1.2. Human-readable output (not the JSON pipeline
contract — this is interactive setup, not a Claude-invoked step).

Usage:
  python scripts/setup_servos.py scan [--port /dev/ttyUSB0] [--baud 1000000]
  python scripts/setup_servos.py set-id --from 1 --to 3 [--port ...] [--baud ...]

STS3215 servos ship at ID 1 / baud 1,000,000. Assign IDs 1..6 ONE servo at a
time (plug one in, set its ID, unplug, next).
"""
from __future__ import annotations

import argparse
import sys

from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

# STS/SMS (STS3215) control-table addresses
ADDR_ID = 5
ADDR_TORQUE = 40
ADDR_ACC = 41
ADDR_GOAL_POS = 42       # 2 bytes, 0..4095 = 360deg
ADDR_GOAL_SPEED = 46     # 2 bytes
ADDR_LOCK = 55
ADDR_PRESENT_POS = 56    # 2 bytes
COMMON_BAUDS = [1000000, 500000, 250000, 115200]
# Feetech STS/SMS use protocol_end=0; SCS series use 1. Try 0 first.
PROTOCOL_ENDS = [0, 1]


def _open(port_name: str, baud: int) -> PortHandler:
    port = PortHandler(port_name)
    if not port.openPort():
        print(f"ERROR: could not open {port_name}", file=sys.stderr)
        sys.exit(1)
    if not port.setBaudRate(baud):
        print(f"ERROR: could not set baud {baud}", file=sys.stderr)
        sys.exit(1)
    return port


def scan(port_name: str, baud: int | None, id_range: range):
    bauds = [baud] if baud else COMMON_BAUDS
    for b in bauds:
        port = _open(port_name, b)
        for end in PROTOCOL_ENDS:
            ph = PacketHandler(end)
            found = []
            for sid in id_range:
                model, comm, err = ph.ping(port, sid)
                if comm == COMM_SUCCESS:
                    found.append((sid, model))
            if found:
                port.closePort()
                print(f"\n✅ baud {b} (protocol_end={end}): {len(found)} servo(s):")
                for sid, model in found:
                    print(f"     • ID {sid:<3} (model {model})")
                return b, end, found
        port.closePort()
        print(f"   baud {b}: no response")
    print("\n❌ no servos responded. Check: bus powered? exactly one servo cabled? "
          "correct port? data cable?", file=sys.stderr)
    return None


def set_id(port_name: str, baud: int, old: int, new: int, end: int = 0):
    port = _open(port_name, baud)
    ph = PacketHandler(end)
    model, comm, err = ph.ping(port, old)
    if comm != COMM_SUCCESS:
        print(f"ERROR: no servo answering at ID {old} (baud {baud})", file=sys.stderr)
        sys.exit(1)
    ph.write1ByteTxRx(port, old, ADDR_LOCK, 0)         # unlock EEPROM
    ph.write1ByteTxRx(port, old, ADDR_ID, new)         # write new ID (ack often times out — expected)
    ph.write1ByteTxRx(port, new, ADDR_LOCK, 1)         # re-lock (addressed at the NEW id)
    # Verify by pinging the NEW id rather than trusting the (often-dropped) ack.
    _, comm2, _ = ph.ping(port, new)
    old_still, comm_old, _ = ph.ping(port, old)
    port.closePort()
    if comm2 == COMM_SUCCESS and not (old != new and comm_old == COMM_SUCCESS):
        print(f"✅ servo ID {old} -> {new} (verified)")
    else:
        print(f"⚠️ ID change unverified: new={comm2==COMM_SUCCESS} old_gone={comm_old!=COMM_SUCCESS}",
              file=sys.stderr)


def test_move(port_name: str, baud: int, sid: int, end: int = 0, delta: int = 150):
    """Gently move the servo +delta then back, reading position to confirm motion."""
    import time
    port = _open(port_name, baud)
    ph = PacketHandler(end)
    model, comm, err = ph.ping(port, sid)
    if comm != COMM_SUCCESS:
        print(f"ERROR: no servo answering at ID {sid} (baud {baud})", file=sys.stderr)
        port.closePort(); sys.exit(1)

    # gentle motion profile
    ph.write1ByteTxRx(port, sid, ADDR_ACC, 20)
    ph.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, 600)
    ph.write1ByteTxRx(port, sid, ADDR_TORQUE, 1)        # enable torque

    p0, _, _ = ph.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
    # auto-pick direction toward mid-range so we never clamp into a limit
    step = -abs(delta) if p0 > 2048 else abs(delta)
    goal = max(50, min(4045, p0 + step))
    print(f"  start position: {p0}  ->  moving to {goal} ...")
    ph.write2ByteTxRx(port, sid, ADDR_GOAL_POS, goal)
    time.sleep(0.8)
    p1, _, _ = ph.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
    print(f"  moved to: {p1}")
    ph.write2ByteTxRx(port, sid, ADDR_GOAL_POS, p0)     # return
    time.sleep(0.8)
    p2, _, _ = ph.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
    print(f"  returned to: {p2}")
    ph.write1ByteTxRx(port, sid, ADDR_TORQUE, 0)        # release torque
    port.closePort()

    moved = abs(p1 - p0) > 20
    print(f"\n{'✅ SERVO MOVES — looks healthy' if moved else '❌ did NOT move (check power / horn / gearing)'}"
          f"   (Δ={abs(p1 - p0)} steps)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--port", default="/dev/ttyUSB0")
    s.add_argument("--baud", type=int, default=None)
    s.add_argument("--max-id", type=int, default=20)
    si = sub.add_parser("set-id")
    si.add_argument("--port", default="/dev/ttyUSB0")
    si.add_argument("--baud", type=int, default=1000000)
    si.add_argument("--end", type=int, default=0)
    si.add_argument("--from", dest="old", type=int, required=True)
    si.add_argument("--to", dest="new", type=int, required=True)
    t = sub.add_parser("test")
    t.add_argument("--port", default="/dev/ttyUSB0")
    t.add_argument("--baud", type=int, default=1000000)
    t.add_argument("--end", type=int, default=0)
    t.add_argument("--id", dest="sid", type=int, required=True)
    t.add_argument("--delta", type=int, default=150)
    a = ap.parse_args(argv)

    if a.cmd == "scan":
        scan(a.port, a.baud, range(0, a.max_id + 1))
    elif a.cmd == "set-id":
        set_id(a.port, a.baud, a.old, a.new, a.end)
    else:
        test_move(a.port, a.baud, a.sid, a.end, a.delta)


if __name__ == "__main__":
    main()
