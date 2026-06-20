#!/usr/bin/env python3
"""bringup — the green-light gate before any motion work (Story 1.4).

READ-ONLY: reads all 6 joint positions (NO motion) and captures one camera
frame, then emits a single JSON envelope. ``ok`` is the logical AND — true only
when BOTH the motors respond AND the camera captures. Each leg runs independently
so the report shows exactly which half is unhealthy.
"""
import argparse
import sys

from dum_e import arm, camera, cli, config, rundir


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="read-only motor + camera health check")
    ap.add_argument("--run-dir", default=None, help="reuse an existing run dir (default: new)")
    ap.add_argument("--config", default=None, help="path to config.yaml (default: auto-discover)")
    args = ap.parse_args(argv)

    cfg = config.load_config(args.config)
    data: dict = {}
    artifacts: list[str] = []
    errors: list[dict] = []

    # --- Motors (read-only) --------------------------------------------------
    try:
        j = arm.read_joints(cfg=cfg)
        data["joint_pos"] = j["joint_pos"]
        data["joint_units"] = j["joint_units"]
        data["motor_ids"] = j["motor_ids"]
        data["raw_steps"] = j["raw_steps"]
        cli.log(f"motors OK: {j['joint_pos']} {j['joint_units']}")
    except arm.ArmError as e:
        errors.append({"code": e.code, "message": e.message})
        cli.log(f"motors FAIL: {e.code}: {e.message}")

    # --- Camera --------------------------------------------------------------
    try:
        cam = camera.CamConfig.from_config(cfg)
        run_dir = args.run_dir or rundir.new_run_dir()
        out_path = rundir.frame_path(run_dir, "bringup", 0)
        res = camera.capture_frame(out_path, cam)
        data["frame_wh"] = res["frame_wh"]
        data["run_dir"] = run_dir
        artifacts.append(res["path"])
        cli.log(f"camera OK: {res['frame_wh']} -> {res['path']}")
    except camera.CameraError as e:
        errors.append({"code": e.code, "message": e.message})
        cli.log(f"camera FAIL: {e.code}: {e.message}")

    ok = not errors
    error = None if ok else {
        "code": errors[0]["code"],
        "message": "; ".join(f"{e['code']}: {e['message']}" for e in errors),
    }
    return cli.emit(cli.envelope(ok, data=data, error=error, artifacts=artifacts))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
