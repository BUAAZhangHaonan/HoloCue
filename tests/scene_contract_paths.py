"""Compare current scene paths with immutable pre-scene-set contract fixtures."""

from pathlib import PurePosixPath

from holocue.config import SCENE_SETS


def fixture_asset_path(asset, scene_id, selected_set):
    """Remove only the validated scene-set directory; retain the complete suffix."""
    assert selected_set in SCENE_SETS, selected_set
    assert scene_id.replace("_", "").isalnum(), scene_id
    prefix = f"scenes/{selected_set}/{scene_id}/meshes/"
    path = PurePosixPath(asset)
    assert asset.startswith(prefix), asset
    assert path.as_posix() == asset and ".." not in path.parts and "\\" not in asset, asset
    suffix = asset[len(prefix) :]
    assert suffix, asset
    return f"scenes/{scene_id}/meshes/{suffix}"


def fixture_scene_paths(spec):
    """Return a deep copy with only object/environment asset paths normalized."""
    result = spec.model_copy(deep=True)
    for item in [*result.objects, *result.environment]:
        item.asset = fixture_asset_path(item.asset, result.scene_id, result.scene_set)
    return result
