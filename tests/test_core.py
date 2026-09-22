"""Security and optical-execution contracts using actual project implementations."""

import importlib.util

import pytest

from holocue.adapters import require_optical_calibration
from holocue.config import root, load_scene, load_policy
from holocue.models import Session
from holocue.projection import packet


def test_physical_gpu_authorization():
    spec = importlib.util.spec_from_file_location(
        "resource_guard", root() / "scripts/guard/resource_guard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.parse_selection("1,2") == [1, 2]
    assert module.parse_selection("") == []
    for text in ("0", "1,3", "all", "1,1", "-1"):
        with pytest.raises(ValueError):
            module.parse_selection(text)


def test_physical_execution_requires_optical_calibration():
    spec = load_scene("control_panel")
    state = Session(session_id="calibration", scene_id=spec.scene_id, backend_mode="geometry_validation")
    display = packet(state, spec, load_policy())
    with pytest.raises(ValueError, match="calibration"):
        require_optical_calibration(display)
