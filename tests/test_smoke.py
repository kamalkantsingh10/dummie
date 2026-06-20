"""Smoke test: the package and all stub modules import without heavy deps."""

import importlib

import dum_e


def test_package_imports_and_has_version():
    assert isinstance(dum_e.__version__, str)


def test_stub_modules_import():
    # Importing must not require hardware or optional deps (lazy imports inside).
    for mod in (
        "dum_e.cli",
        "dum_e.config",
        "dum_e.rundir",
        "dum_e.arm",
        "dum_e.camera",
        "dum_e.calibration",
        "dum_e.tracker",
        "dum_e.primitives",
        "dum_e.shotlog",
        "dum_e.stitch",
        "dum_e.safety",
        "dum_e.acquire",
        "dum_e.acquire.base",
    ):
        importlib.import_module(mod)
