"""The collision audit must account for actual solid obstacles."""
import pytest
import trimesh

from holocue.config import load_scene
from scripts.tests.audit_geometry import parts


def test_blocks_support_surfaces_are_collision_obstacles():
    spec=load_scene('blocks')
    obstacles,coverage=parts(spec,spec.environment)
    included={name for _,name,_,_ in obstacles}
    for suffix in ('_worktop','_work_mat','_left_parts_tray','_right_parts_tray'):
        records=[row for row in coverage if row['part'].endswith(suffix)]
        assert len(records)==1
        assert records[0]['status']=='included_closed_solid'
        assert records[0]['part'] in included
    assert not any(row['status']=='invalid_solid_topology' for row in coverage)
    assert any(row['status']=='excluded_textured_label_surface' for row in coverage)


@pytest.mark.parametrize('node_name',['open_part','label_untextured_open_part'])
def test_open_solid_is_reported_as_uncovered_not_silently_ignored(tmp_path,monkeypatch,node_name):
    spec=load_scene('blocks')
    mesh=trimesh.creation.box()
    mesh.update_faces(range(len(mesh.faces)-1))
    path=tmp_path/'open-solid.glb'
    asset=trimesh.Scene()
    asset.add_geometry(mesh,node_name=node_name)
    asset.export(path)
    monkeypatch.setenv('HOLOCUE_ROOT',str(tmp_path))
    obj=spec.objects[0].model_copy(update={'asset':'open-solid.glb'})
    obstacles,coverage=parts(spec,[obj])
    assert not obstacles
    assert len(coverage)==1
    assert coverage[0]['status']=='invalid_solid_topology'
