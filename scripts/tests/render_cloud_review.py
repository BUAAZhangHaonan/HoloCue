"""Render real scene assets with an explicit software EGL validation backend."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import vtk
from vtk.util.numpy_support import vtk_to_numpy

from holocue.assets import world_scene, load_asset
from holocue.camera import corners, fit, workspace_points, project
from holocue.annotations import annotation_margin, border_annotations
from holocue.config import load_scene, list_scenes, root
from holocue.models import Pose
from holocue.render_validation import actor, studio_texture
from holocue.spatial import transform_points


def render_meshes(scene, position, look, up, fov, destination, size=(1152, 900)):
    if os.environ.get('LIBGL_ALWAYS_SOFTWARE') != '1' or os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise RuntimeError('This cloud renderer requires explicit software OpenGL and empty CUDA')
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(.90, .93, .95)
    renderer.SetBackground2(.99, .99, .985)
    renderer.GradientBackgroundOn()
    renderer.UseImageBasedLightingOn()
    renderer.UseSphericalHarmonicsOn()
    renderer.SetEnvironmentTexture(studio_texture(), False)
    renderer.GetEnvMapPrefiltered().SetPrefilterLevels(4)
    renderer.GetEnvMapPrefiltered().SetPrefilterMaxSamples(32)
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(transform)
        item = actor(mesh)
        material = mesh.visual.material
        if not getattr(material, 'doubleSided', False):
            item.GetProperty().BackfaceCullingOn()
        renderer.AddActor(item)
    camera = renderer.GetActiveCamera()
    camera.SetPosition(*position); camera.SetFocalPoint(*look)
    camera.SetViewUp(*up); camera.SetViewAngle(fov)
    camera.SetClippingRange(.002, 100.)
    aim = np.asarray(look)
    distance = max(float(np.linalg.norm(np.asarray(position)-aim)), .5)
    for offset, intensity, color in [((1, -1.3, 2), .85, (1., .97, .91)),
                                    ((-1, -.3, 1.2), .65, (.85, .93, 1.)),
                                    ((0, 1, 1.8), .7, (1., 1., 1.))]:
        light = vtk.vtkLight(); light.SetLightTypeToSceneLight()
        light.SetPosition(*(aim+np.asarray(offset)*distance)); light.SetFocalPoint(*aim)
        light.SetIntensity(intensity); light.SetColor(*color); renderer.AddLight(light)
    window = vtk.vtkEGLRenderWindow()
    window.SetOffScreenRendering(1); window.SetSize(*size); window.SetMultiSamples(0)
    window.AddRenderer(renderer); window.Render()
    capabilities = window.ReportCapabilities()
    if 'llvmpipe' not in capabilities.lower() and 'softpipe' not in capabilities.lower():
        window.Finalize()
        raise RuntimeError('Software renderer verification failed: '+capabilities)
    capture = vtk.vtkWindowToImageFilter(); capture.SetInput(window)
    capture.SetInputBufferTypeToRGB(); capture.ReadFrontBufferOff(); capture.Update()
    image = capture.GetOutput(); width, height, _ = image.GetDimensions()
    pixels = vtk_to_numpy(image.GetPointData().GetScalars()).reshape(height, width, 3)[::-1].copy()
    window.Finalize()
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(destination)
    return capabilities


def annotate(image_path, layout, position, look, up, fov, aspect):
    image = Image.open(image_path).convert('RGB')
    width, height = image.size
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('DejaVuSans.ttf', round(height*.015))
    for label in layout:
        screen, _ = project(label.leader, position, look, fov, aspect, up)
        xy = np.column_stack(((screen[:, 0]+1)*width/2, (1-screen[:, 1])*height/2))
        draw.line([tuple(xy[0]), tuple(xy[1])], fill=(92, 111, 125), width=1)
        x0, y0, x1, y1 = label.rectangle_ndc
        anchor='rm' if label.anchor=='center-right' else 'lm'
        cx=((x1 if anchor=='rm' else x0)+1)*width/2
        cx+=-7 if anchor=='rm' else 7
        cy=(2-y0-y1)*height/4
        bounds = draw.textbbox((cx, cy), label.object_id, font=font, anchor=anchor)
        draw.rounded_rectangle((bounds[0]-6, bounds[1]-4, bounds[2]+6, bounds[3]+4),
                               radius=4, fill=(246, 249, 250), outline=(139, 157, 168))
        draw.text((cx, cy), label.object_id, font=font, anchor=anchor, fill=(30, 49, 64))
    image.save(image_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--capture-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cases', choices=['surfaces', 'overview', 'all'], default='all')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    if args.cases in ('surfaces', 'all'):
        cases = [('engine_bay', 'object_CLAMP_detail'),
                 ('shelf_picking', '03_temporary_inspection'),
                 ('shelf_picking', '05_endpoint_receiver')]
        for sid, stage in cases:
            directory = args.capture_root/'bridge'/sid/stage
            view = json.loads((directory/'view_state.json').read_text())
            snapshot = json.loads((directory/'snapshot.json').read_text())
            poses = {key: Pose.model_validate(value) for key, value in snapshot['display']['object_poses'].items()}
            spec = load_scene(sid)
            selected = view['selected_id']
            if view['view_mode'] == 'inspection':
                spec = spec.model_copy(update={
                    'objects': [obj for obj in spec.objects if obj.object_id == selected], 'environment': []})
            for name, project in [('reference', args.reference_root), ('candidate', root())]:
                destination = args.out/f'{sid}_{stage}_{name}.png'
                capability = render_meshes(world_scene(project, spec, poses), view['position_m'],
                    view['look_at_m'], view['up_direction'], np.rad2deg(view['fov_rad']), destination,
                    (round(900*view['aspect']), 900))
                records.append({'scene_id': sid, 'stage': stage, 'asset_set': name,
                    'image': destination.name, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                    'geometry_source': str(project), 'camera_source': str(directory/'view_state.json'),
                    'view_mode': view['view_mode'], 'renderer': capability})
                print(destination.name, flush=True)
    if args.cases in ('overview', 'all'):
        for item in list_scenes():
            spec = load_scene(item['scene_id']); anchors = {}; points = []
            for obj in spec.objects:
                asset = load_asset(str(root()/obj.asset), spec.asset_axes)
                points.extend(transform_points(obj.pose, corners(asset.bounds)))
                anchor = (asset.bounds[0]+asset.bounds[1])/2
                anchor[2] = asset.bounds[1, 2]+.018
                anchor = obj.anchors.get('label', anchor)
                anchors[obj.object_id] = transform_points(obj.pose, np.asarray([anchor]))[0]
            aspect = 1.6
            position, look = fit(workspace_points(spec, points),
                np.asarray(spec.camera_position_m)-spec.camera_look_at_m,
                spec.render_hints.fov_y_deg, aspect,
                annotation_margin(list(anchors), aspect, spec.render_hints.viewport_margin))
            destination = args.out/(spec.scene_id+'_workspace.png')
            capability = render_meshes(world_scene(root(), spec), position, look, (0, 0, 1),
                spec.render_hints.fov_y_deg, destination, (1440, 900))
            layout = border_annotations(anchors, position, look, spec.render_hints.fov_y_deg, aspect)
            if len(layout) != len(spec.objects):
                raise AssertionError('workspace omitted an object annotation')
            annotate(destination, layout, position, look, (0, 0, 1), spec.render_hints.fov_y_deg, aspect)
            records.append({'scene_id': spec.scene_id, 'stage': 'workspace',
                'image': destination.name, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                'renderer': capability, 'annotation_rendering': 'Pillow from production layout coordinates',
                'label_rectangles_ndc': {a.object_id: a.rectangle_ndc for a in layout}})
            print(destination.name, flush=True)
    (args.out/'report.json').write_text(json.dumps({'backend': 'VTK EGL software mesh rendering',
        'live_model_exercised': False, 'native_viser_exercised': False, 'native_blender_exercised': False,
        'records': records}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
