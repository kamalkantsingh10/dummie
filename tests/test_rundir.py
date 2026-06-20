"""Tests for the frozen run-dir layout + filename conventions (dum_e.rundir)."""

import os

from dum_e import rundir


def test_frame_name_convention():
    p = rundir.frame_path("runs/abc", "survey", 0)
    assert p == os.path.join("runs/abc", "frames/survey_0000.png")
    assert rundir.frame_path("runs/abc", "ep1", 42).endswith("frames/ep1_0042.png")


def test_clip_name_convention():
    assert rundir.clip_path("runs/abc", "ep1") == os.path.join("runs/abc", "clips/ep1.mp4")


def test_new_run_dir_creates_subdirs(tmp_path):
    run = rundir.new_run_dir(str(tmp_path), ts="20260620T204231Z")
    assert os.path.isdir(os.path.join(run, "frames"))
    assert os.path.isdir(os.path.join(run, "clips"))
    assert run.endswith("20260620T204231Z")


def test_compact_ts_is_filesystem_safe():
    ts = rundir.compact_ts()
    assert ts.endswith("Z") and "T" in ts and ":" not in ts
