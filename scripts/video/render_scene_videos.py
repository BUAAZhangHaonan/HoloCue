"""Per-scene perspective fly-through videos for the five v2 scenes.
Opens the official assets/blender/<scene>.blend (composed scene + lighting), animates a
new perspective camera along the scene's depth-story waypoints with a TRACK_TO target,
and encodes h264 directly via Blender's FFMPEG output. Captions are burned afterwards by
scripts/scene_videos_captions.sh (ffmpeg drawtext), not in 3D.

Run (resource-guarded, CPU):
  .venv/bin/python scripts/guard/resource_guard.py --rss-limit-gb 12 --execute -- \
    blender -b -t 4 --python scripts/scenes_v2/render_scene_videos.py -- --scene server_rack
"""
import bpy, sys, json, argparse
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument('--scene', required=True)
p.add_argument('--frames', type=int, default=0, help='override frame count (smoke test)')
p.add_argument('--samples', type=int, default=24)
p.add_argument('--res', nargs=2, type=int, default=(1280, 720))
p.add_argument('--device', choices=('CPU', 'CUDA', 'OPTIX'), default='CPU',
               help='GPU render requires resource_guard --gpus 1|2 masking (AGENTS.md)')
a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

FPS = 24
# waypoints: (t_seconds, cam_pos, look_at). Each scene starts and ends on its official view.
WAYPOINTS = {
 'server_rack': (15.0, [
   (0.0, (1.12, -1.02, 1.30), (-0.35, 0.02, 1.03)),
   (3.0, (-1.05, -0.85, 1.15), (-0.75, -0.35, 0.95)),
   (6.0, (0.65, -0.75, 1.35), (0.0, 0.28, 1.02)),
   (8.7, (0.95, 0.10, 0.85), (0.0, 0.33, 0.55)),
   (10.6, (1.25, 0.45, 2.30), (0.2, 0.5, 1.0)),
   (12.4, (0.60, 0.92, 2.35), (0.0, 0.33, 0.60)),
   (15.0, (1.12, -1.02, 1.30), (-0.35, 0.02, 1.03)),
 ]),
 'drone_bench': (15.0, [
   (0.0, (0.55, -0.95, 0.62), (0.0, 0.05, 0.12)),
   (3.0, (0.18, -0.55, 0.48), (0.02, 0.0, 0.13)),
   (6.0, (0.30, -0.35, 0.42), (0.02, 0.0, 0.16)),
   (9.0, (-0.38, 0.28, 0.24), (-0.21, 0.21, 0.08)),
   (10.8, (0.0, 0.05, 0.70), (0.0, 0.4, 0.18)),
   (12.4, (0.28, 0.42, 0.58), (0.0, 0.58, 0.20)),
   (15.0, (0.55, -0.95, 0.62), (0.0, 0.05, 0.12)),
 ]),
 'shelf_picking': (15.0, [
   (0.0, (0.35, -1.15, 1.05), (0.56, 0.62, 0.62)),
   (3.0, (0.15, -0.55, 1.18), (0.0, 0.35, 0.85)),
   (6.0, (0.10, -0.40, 0.85), (0.0, 0.38, 0.50)),
   (9.0, (0.05, -0.80, 0.45), (0.0, -0.35, 0.12)),
   (10.8, (0.35, -0.20, 0.90), (0.8, 0.5, 0.6)),
   (12.4, (0.35, 0.10, 1.35), (1.45, 1.30, 0.80)),
   (15.0, (0.35, -1.15, 1.05), (0.56, 0.62, 0.62)),
 ]),
 'optical_bench': (15.0, [
   (0.0, (0.50, -0.85, 0.55), (0.0, 0.45, 0.15)),
   (3.0, (0.25, -0.55, 0.38), (0.0, -0.30, 0.12)),
   (5.8, (0.18, -0.30, 0.35), (0.0, 0.15, 0.10)),
   (8.6, (0.32, 0.35, 0.32), (0.0, 0.55, 0.12)),
   (11.2, (0.12, 0.72, 0.40), (0.0, 1.15, 0.12)),
   (13.0, (0.40, 0.55, 0.30), (0.0, 0.55, 0.13)),
   (15.0, (0.50, -0.85, 0.55), (0.0, 0.45, 0.15)),
 ]),
 'dig_site': (16.0, [
   (0.0, (1.35, -1.35, 1.05), (-0.49, 0.85, 0.17)),
   (3.0, (0.45, -0.55, 0.35), (0.0, 0.71, -0.25)),
   (5.8, (0.35, -0.50, -0.05), (0.18, -0.10, -0.42)),
   (8.6, (0.55, -0.60, 0.75), (0.18, -0.18, -0.40)),
   (11.2, (0.95, 0.30, 0.95), (0.0, 1.22, 0.95)),
   (13.4, (1.35, -0.75, 1.35), (0.0, 0.2, -0.35)),
   (16.0, (1.35, -1.35, 1.05), (-0.49, 0.85, 0.17)),
 ]),
 'engine_bay': (16.0, [
   # official view (engine_bay.json camera): front-left-top over the bay
   (0.0, (-0.85, 1.55, 1.55), (-0.1143, 0.0612, 0.8316)),
   # near layer: push in over the intake hose / CLAMP
   (3.0, (-0.38, 0.92, 1.42), (-0.18, 0.35, 1.02)),
   (7.0, (-0.30, 0.78, 1.36), (-0.18, 0.35, 1.02)),
   # middle layer: translate + descend to the plug well / valve-cover top (PLUGPORT)
   (10.0, (0.02, 0.72, 1.30), (0.12, 0.10, 0.98)),
   # right end: belt-drive tensioner
   (13.0, (0.92, 0.62, 1.22), (0.48, 0.30, 0.85)),
   # far layer: swing behind-right to CONN, then pull back to the official view
   (14.5, (1.10, -0.02, 1.35), (0.55, -0.15, 0.88)),
   (16.0, (-0.85, 1.55, 1.55), (-0.1143, 0.0612, 0.8316)),
 ]),
}

def main():
    scene_id = a.scene
    duration, wps = WAYPOINTS[scene_id]
    blend = ROOT/'assets/blender'/f'{scene_id}.blend'
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.samples = a.samples
    sc.cycles.use_denoising = True
    if a.device != 'CPU':
        # GPU path requires resource_guard --gpus 1|2 (UUID mask => exactly one visible
        # device, i.e. the remapped cuda:0). AGENTS.md allows physical GPUs 1 and 2 only.
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = a.device
        try:
            prefs.get_devices()
        except Exception:
            pass
        for d in prefs.devices:
            d.use = d.type == a.device
        sc.cycles.device = 'GPU'
    else:
        sc.cycles.device = 'CPU'
    sc.render.threads_mode = 'FIXED'; sc.render.threads = 4
    sc.render.resolution_x, sc.render.resolution_y = a.res
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = a.frames if a.frames else int(duration*FPS)
    # Perspective fly camera tracking a moving target empty (smooth look_at animation).
    cam = bpy.data.objects.new('FLY_CAM', bpy.data.cameras.new('FLY_CAM_DATA'))
    cam.data.type = 'PERSP'; cam.data.lens = 46
    sc.collection.objects.link(cam)
    target = bpy.data.objects.new('FLY_TARGET', None)
    sc.collection.objects.link(target)
    con = cam.constraints.new('TRACK_TO')
    con.target = target; con.track_axis = 'TRACK_NEGATIVE_Z'; con.up_axis = 'UP_Y'
    for t, pos, look in wps:
        f = max(1, round(t*FPS) + 1)
        cam.location = Vector(pos); cam.keyframe_insert('location', frame=f)
        target.location = Vector(look); target.keyframe_insert('location', frame=f)
    sc.camera = cam
    sc.render.image_settings.file_format = 'FFMPEG'
    sc.render.ffmpeg.format = 'MPEG4'; sc.render.ffmpeg.codec = 'H264'
    sc.render.ffmpeg.constant_rate_factor = 'HIGH'
    sc.render.ffmpeg.audio_codec = 'NONE'
    out_dir = ROOT/'runs/scene_v2/videos'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir/f'{scene_id}_flythrough_raw.mp4'
    sc.render.filepath = str(out)
    sc.render.use_overwrite = True
    bpy.ops.render.render(animation=True)
    print(json.dumps({'video': str(out), 'frames': sc.frame_end, 'fps': FPS,
                      'scene': scene_id, 'res': list(a.res), 'samples': a.samples}))

main()
