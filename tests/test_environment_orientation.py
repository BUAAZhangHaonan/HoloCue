import numpy as np
import pytest
from pydantic import ValidationError
from holocue.config import list_scenes, load_scene
from holocue.models import RenderHints


@pytest.mark.parametrize(
    "quaternion", [(0, 0, 0, 0), (2, 0, 0, 0), (float("nan"), 0, 0, 0), (float("inf"), 0, 0, 0)]
)
def test_environment_requires_finite_unit_quaternion(quaternion):
    with pytest.raises(ValidationError):
        RenderHints(environment_wxyz=quaternion)


def test_only_optical_scene_rotates_environment():
    for entry in list_scenes():
        spec = load_scene(entry["scene_id"])
        expected = (
            (0.594394087626887, 0.1712372678360988, -0.2126979877009283, 0.7563947598484568)
            if spec.scene_id == "optical_bench"
            else (1, 0, 0, 0)
        )
        np.testing.assert_allclose(spec.render_hints.environment_wxyz, expected, atol=1e-12)
