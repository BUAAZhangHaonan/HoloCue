"""Reject unrelated asset directories when comparing sealed scene fixtures."""

import pytest

from holocue.config import load_scene
from scene_contract_paths import fixture_asset_path, fixture_scene_paths


@pytest.mark.parametrize("selected", ["legacy", "reconstructed"])
def test_only_exact_selected_scene_prefix_is_normalized(selected):
    spec = load_scene("control_panel", selected)
    before = spec.model_dump(mode="json")
    normalized = fixture_scene_paths(spec).model_dump(mode="json")
    for group in ("objects", "environment"):
        for original, result in zip(before[group], normalized[group], strict=True):
            prefix = f"scenes/{selected}/control_panel/"
            assert result["asset"] == "scenes/control_panel/" + original["asset"][len(prefix) :]
            assert {key: value for key, value in result.items() if key != "asset"} == {
                key: value for key, value in original.items() if key != "asset"
            }
    assert {key: value for key, value in before.items() if key not in ("objects", "environment")} == {
        key: value for key, value in normalized.items() if key not in ("objects", "environment")
    }
    assert spec.model_dump(mode="json") == before
    assert (
        fixture_asset_path(f"scenes/{selected}/control_panel/meshes/renamed.glb", "control_panel", selected)
        == "scenes/control_panel/meshes/renamed.glb"
    )


@pytest.mark.parametrize(
    "asset, scene_id, selected",
    [
        ("scenes/legacy/control_panel/meshes/A.glb", "control_panel", "reconstructed"),
        ("scenes/reconstructed/connector/meshes/A.glb", "control_panel", "reconstructed"),
        ("scenes/control_panel/meshes/A.glb", "control_panel", "reconstructed"),
        ("scenes/unknown/control_panel/meshes/A.glb", "control_panel", "unknown"),
        ("scenes/reconstructed/control_panel/meshes/../other.glb", "control_panel", "reconstructed"),
        ("/scenes/reconstructed/control_panel/meshes/A.glb", "control_panel", "reconstructed"),
        ("scenes/reconstructed/control_panel/meshes//A.glb", "control_panel", "reconstructed"),
        ("scenes/reconstructed/control_panel/meshes/..\\other.glb", "control_panel", "reconstructed"),
        ("scenes/reconstructed/control_panel/other/A.glb", "control_panel", "reconstructed"),
    ],
)
def test_unrelated_or_noncanonical_directory_is_rejected(asset, scene_id, selected):
    with pytest.raises(AssertionError):
        fixture_asset_path(asset, scene_id, selected)
