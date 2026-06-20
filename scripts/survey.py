#!/usr/bin/env python3
"""survey — capture a frame (Story 1.3) and list scene subjects (Story 2.2).

Capture mode grabs one still into the run dir's ``frames/`` and emits the
canonical JSON envelope: ``artifacts=[frame_path]``, ``data={frame_wh, ...}``.
The Story 2.2 "list subjects" behavior extends this thin wrapper later.
"""
import argparse
import sys

from dum_e import cli, config, rundir
from dum_e.camera import CamConfig, CameraError, capture_frame


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="capture a frame from the arm camera")
    ap.add_argument("--mode", default="capture", choices=["capture"])
    ap.add_argument("--episode-id", default="survey", help="frame name prefix")
    ap.add_argument("--step", type=int, default=0, help="step index (frames/<ep>_<step:04d>.png)")
    ap.add_argument("--run-dir", default=None, help="reuse an existing run dir (default: new one)")
    ap.add_argument("--config", default=None, help="path to config.yaml (default: auto-discover)")
    args = ap.parse_args(argv)

    try:
        cam = CamConfig.from_config(config.load_config(args.config))
    except CameraError as e:
        return cli.fail(e.code, e.message)

    run_dir = args.run_dir or rundir.new_run_dir()
    out_path = rundir.frame_path(run_dir, args.episode_id, args.step)
    cli.log(f"capturing {cam.device} -> {out_path} (rotate={cam.rotate})")

    try:
        res = capture_frame(out_path, cam)
    except CameraError as e:
        return cli.fail(e.code, e.message)

    return cli.ok(
        data={"frame_wh": res["frame_wh"], "run_dir": run_dir, "rotate": cam.rotate},
        artifacts=[res["path"]],
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
