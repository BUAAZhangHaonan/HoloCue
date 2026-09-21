"""Make clearly labelled real-time UI MP4s and real-page scene introductions.

Retains every raw WebM. The end-to-end video has no cuts or speed changes.
Introduction movies are explicitly slides of captured real Viser pages.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import textwrap


FONT = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
        '-of', 'json', str(path)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def decoded_probe(path, directory, name):
    """Decode the video and record every presented frame's actual timestamp."""
    command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_frames', '-show_streams', '-show_format',
        '-show_entries',
        'frame=best_effort_timestamp_time,pkt_duration_time:stream=index,time_base,start_time,duration,nb_read_frames,avg_frame_rate:format=start_time,duration',
        '-of', 'json', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    save(directory/(name+'.command.json'), {'command': command, 'returncode': result.returncode})
    (directory/(name+'.stderr.log')).write_text(result.stderr, encoding='utf-8')
    if result.returncode or result.stderr.strip():
        raise RuntimeError(f'{name}: frame decoder reported an error; original media retained')
    info = json.loads(result.stdout)
    save(directory/(name+'.json'), info)
    frames = info.get('frames', [])
    times = [Decimal(frame['best_effort_timestamp_time']) for frame in frames]
    if not times or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError(f'{name}: missing or non-increasing decoded frame timestamps')
    counted = int(info['streams'][0]['nb_read_frames'])
    if counted != len(times):
        raise ValueError(f'{name}: decoder frame count disagrees with frame records')
    last_duration = Decimal(frames[-1].get('pkt_duration_time', '0'))
    summary = {'decoded_frames': counted, 'first_frame_pts_s': str(times[0]),
        'last_frame_pts_s': str(times[-1]), 'frame_pts_span_s': str(times[-1]-times[0]),
        'last_frame_duration_s': str(last_duration),
        'presented_duration_s': str(times[-1]-times[0]+last_duration),
        'container_duration_s': info['format']['duration'],
        'time_base': info['streams'][0]['time_base'],
        'full_frame_record': str(directory/(name+'.json'))}
    return times, summary


def verify_frame_timing(raw_times, raw, output_times, output):
    # WebM input timestamps use millisecond quantization; allow 2 ms of
    # mux/timebase rounding, never missing/duplicated frames or speed changes.
    tolerance = Decimal('.002')
    if len(raw_times) != len(output_times):
        raise AssertionError('End-to-end transcode dropped or duplicated decoded frames')
    max_error = max(abs((a-raw_times[0])-(b-output_times[0]))
                    for a, b in zip(raw_times, output_times))
    if max_error > tolerance:
        raise AssertionError(f'End-to-end frame timestamps changed: {max_error}s')
    # The last packet's duration/container rounding can differ by one frame.
    # Frame count and every normalized timestamp are checked more strictly above.
    last_intervals = [Decimal(raw['last_frame_duration_s']), Decimal(output['last_frame_duration_s'])]
    if len(raw_times) > 1:
        last_intervals.extend([raw_times[-1]-raw_times[-2], output_times[-1]-output_times[-2]])
    duration_tolerance = max(Decimal('.020'), *last_intervals)+tolerance
    duration_error = abs(Decimal(raw['container_duration_s'])-Decimal(output['container_duration_s']))
    if duration_error > duration_tolerance:
        raise AssertionError('End-to-end container duration differs beyond one final-frame interval')
    return {'passed': True, 'exact_decoded_frame_count_match': True,
        'all_normalized_frame_timestamps_checked': True,
        'global_pts_shift_s': str(output_times[0]-raw_times[0]),
        'maximum_normalized_pts_error_s': str(max_error),
        'normalized_pts_tolerance_s': str(tolerance),
        'container_duration_error_s': str(duration_error),
        'container_duration_tolerance_s': str(duration_tolerance),
        'tolerance_reason': '2 ms timestamp quantization; container duration permits one final-frame interval, with exact frame count and every relative PTS separately checked'}


def run(command, directory, name):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    (directory/(name+'.stdout.log')).write_text(result.stdout, encoding='utf-8')
    (directory/(name+'.stderr.log')).write_text(result.stderr, encoding='utf-8')
    save(directory/(name+'.command.json'), {'command': command, 'returncode': result.returncode})
    if result.returncode:
        raise RuntimeError(f'{name} failed with code {result.returncode}; original media retained')


def filter_path(path):
    # Paths originate from this tool's output directory, never from scene text.
    # FFmpeg's filter parser has separate escaping from subprocess argv.
    return str(Path(path).resolve()).replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")


def caption_filter(title_file, description_file):
    return (
        'scale=1600:1000:force_original_aspect_ratio=decrease,'
        'pad=1600:1240:(ow-iw)/2:0:color=0x111827,'
        f"drawtext=fontfile='{filter_path(FONT)}':textfile='{filter_path(title_file)}':"
        'expansion=none:fontcolor=white:fontsize=38:x=32:y=1020,'
        f"drawtext=fontfile='{filter_path(FONT)}':textfile='{filter_path(description_file)}':"
        'expansion=none:fontcolor=0xdbeafe:fontsize=26:line_spacing=9:x=32:y=1080'
    )


def caption_files(directory, name, title, description):
    title_file = directory/(name+'_title.txt')
    description_file = directory/(name+'_description.txt')
    # Caption text is passed as UTF-8 data, never inserted in a shell/filter.
    title_file.write_text(title, encoding='utf-8')
    description_file.write_text('\n'.join(textwrap.wrap(description, width=58)), encoding='utf-8')
    return title_file, description_file


def encode(command):
    return [*command, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
            '-threads', '4', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-root', type=Path, required=True)
    parser.add_argument('--scenes', nargs='+')
    parser.add_argument('--intro-seconds', type=float, default=6)
    parser.add_argument('--media-dir-name', default='produced',
                        help='Fresh production directory; use produced_attempt02 to preserve an interrupted attempt')
    args = parser.parse_args()
    if (args.media_dir_name != 'produced' and
            not (args.media_dir_name.startswith('produced_attempt') and
                 args.media_dir_name.removeprefix('produced_attempt').isdigit())):
        raise ValueError('Production directory must be produced or produced_attempt<number>')
    if not 4 <= args.intro_seconds <= 12:
        raise ValueError('Introduction slide duration must be 4 to 12 seconds')
    if not FONT.is_file():
        raise FileNotFoundError(FONT)
    root = args.capture_root.resolve()
    batch = json.loads((root/'manifest.json').read_text())
    before = json.loads((root/'provenance_before.json').read_text())
    after = json.loads((root/'provenance_after.json').read_text())
    if (before['source']['digest'] != after['source']['digest']
            or before['assets']['digest'] != after['assets']['digest']
            or before['capture_script_sha256'] != after['capture_script_sha256']):
        raise ValueError('Capture source/assets/tool changed; retain evidence without a success film')
    requested = set(args.scenes) if args.scenes else None
    scenes = [item for item in batch['scenes'] if requested is None or item['scene_id'] in requested]
    if requested is not None and {item['scene_id'] for item in scenes} != requested:
        raise ValueError('Requested scene is absent from capture manifest')
    products = []
    for item in scenes:
        scene = item['scene_id']
        if not item['passed']:
            raise ValueError(f'{scene}: incomplete workflow cannot produce a completed demonstration')
        expected_identity = {'source_digest': before['source']['digest'],
                             'asset_digest': before['assets']['digest'],
                             'capture_script_sha256': before['capture_script_sha256']}
        if any(item.get(key) != value for key, value in expected_identity.items()):
            raise ValueError(f'{scene}: scene manifest differs from capture batch provenance')
        directory = root/scene
        contract = json.loads((directory/'scene_contract.json').read_text())
        if digest(directory/'scene_contract.json') != item['scene_contract_sha256']:
            raise ValueError('Scene contract changed since recording')
        raw = Path(item['raw_video']).resolve(strict=True)
        if not raw.is_relative_to(directory.resolve()) or digest(raw) != item['raw_video_sha256']:
            raise ValueError('Raw video provenance mismatch')
        media = directory/args.media_dir_name
        media.mkdir(exist_ok=False)
        raw_probe = probe(raw)
        raw_times, raw_decoded = decoded_probe(raw, media, 'raw_decoded_frames')
        raw_duration = float(raw_probe['format']['duration'])
        if raw_duration <= 0:
            raise ValueError('Raw video has no valid duration')
        title, text = caption_files(media, 'workflow', contract['title']+' · 真实页面完整流程',
            '原始录像等速转码；保留模型等待、暂停、临时检查、恢复与确认操作。任务：'+contract['initial_instruction'])
        workflow = media/'workflow_realtime.mp4'
        command = encode(['ffmpeg', '-nostdin', '-n', '-filter_threads', '4',
                          '-copyts', '-start_at_zero', '-i', str(raw), '-map', '0:v:0',
                          '-vf', caption_filter(title, text), '-an',
                          '-vsync', '0', '-enc_time_base', '-1', '-video_track_timescale', '1000000'])
        run([*command, str(workflow)], media, 'workflow_encode')
        workflow_probe = probe(workflow)
        output_times, output_decoded = decoded_probe(workflow, media, 'workflow_decoded_frames')
        timing = verify_frame_timing(raw_times, raw_decoded, output_times, output_decoded)
        save(media/'frame_timing_verification.json',
             {'input': raw_decoded, 'output': output_decoded, 'verification': timing})
        introductions = json.loads((directory/'introduction.json').read_text())
        pieces = []
        for index, row in enumerate(introductions):
            source = Path(row['image']).resolve(strict=True)
            if not source.is_relative_to(directory.resolve()) or digest(source) != row['image_sha256']:
                raise ValueError('Introduction image provenance mismatch')
            title, text = caption_files(media, f'intro_{index:02d}', row['title']+' · 场景介绍',
                row['description']+' 任务：'+row['task_instruction'])
            piece = media/f'intro_piece_{index:02d}.mp4'
            command = encode(['ffmpeg', '-nostdin', '-n', '-filter_threads', '4', '-loop', '1', '-framerate', '25',
                '-i', str(source), '-t', str(args.intro_seconds),
                '-vf', caption_filter(title, text), '-an'])
            run([*command, str(piece)], media, f'intro_{index:02d}_encode')
            pieces.append(piece)
        if not pieces:
            raise ValueError('No real-page introduction captures')
        concat = media/'intro_concat.txt'
        concat.write_text(''.join(f"file '{piece.name}'\n" for piece in pieces), encoding='utf-8')
        intro = media/'scene_introduction.mp4'
        run(['ffmpeg', '-nostdin', '-n', '-f', 'concat', '-safe', '1', '-i', str(concat),
             '-c', 'copy', '-movflags', '+faststart', str(intro)], media, 'introduction_concat')
        product = {'scene_id': scene, 'session_id': item['session_id'],
            'source_digest': item['source_digest'], 'asset_digest': item['asset_digest'],
            'capture_script_sha256': item['capture_script_sha256'],
            'production_script_sha256': digest(__file__),
            'raw_video': {'path': str(raw), 'sha256': digest(raw), 'probe': raw_probe},
            'workflow_mp4': {'path': str(workflow), 'sha256': digest(workflow),
                'probe': workflow_probe, 'speed': 1.0, 'cuts': 0,
                'decoded_input': raw_decoded, 'decoded_output': output_decoded,
                'frame_timing_verification': timing,
                'scope': 'Complete real Viser recording; no native Blender claim'},
            'introduction_mp4': {'path': str(intro), 'sha256': digest(intro),
                'probe': probe(intro), 'scope': 'Slides of real initial Viser page captures',
                'seconds_per_page': args.intro_seconds,
                'image_sources': introductions, 'caption_source': 'captured scene_contract.json'},
            'caption_placement': 'Added below the entire page; no UI area covered or cropped'}
        save(media/'manifest.json', product)
        products.append(product)
        # Unique per selected batch; never mutate capture/runtime evidence.
    index = root/(args.media_dir_name+'_index_'+('_'.join(args.scenes) if args.scenes else 'all')+'.json')
    if index.exists():
        raise FileExistsError(index)
    save(index, products)
    print(json.dumps({'produced_scenes': [item['scene_id'] for item in products]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
