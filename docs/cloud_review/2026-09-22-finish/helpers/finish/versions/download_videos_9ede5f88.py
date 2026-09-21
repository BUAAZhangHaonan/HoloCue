"""Download verified complete HoloCue UI videos; remote access is read-only.

Prepare-only until explicitly invoked. Requires Python 3.11+, OpenSSH ssh/scp.
Existing matching files are reused; existing differing files are never replaced.
Raw WebM originals have no size cap. Run only after all twelve productions and
the twelve-scene introduction collection have completed.
"""
import argparse
import hashlib
import html
import json
import shlex
import subprocess
import uuid
from pathlib import Path
from urllib.parse import quote

REMOTE_RUN = '/home/hdd3/zhanghaonan/projects/holocue/runs/simulation/cloud_finish90_20260921_e67b574'
DESTINATION = Path('C:/Users/zhn19/Downloads/2/HoloCue_Final_20260921/videos')

# Sent to remote python over stdin; it only opens/stats/hashes existing files.
REMOTE_PROGRAM = r'''
import hashlib,json,sys
from pathlib import Path
run=Path(sys.argv[1]).resolve(strict=True)
scenes=('blocks','cnc_toolchange','connector','control_panel','dig_site','dive_fillstation',
        'drone_bench','engine_bay','infusion_ward','optical_bench','server_rack','shelf_picking')
read=lambda path:json.loads(path.read_text(encoding='utf-8'))
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def require(ok,message):
    if not ok:raise RuntimeError(message)
def safe(path,within):
    path=Path(path)
    require(path.is_absolute() and path.is_relative_to(within),'Remote path outside expected evidence directory')
    require(not any(p.is_symlink() for p in [path,*path.parents]),'Symlink evidence is not accepted')
    require(path.is_file(),'Missing evidence: '+str(path))
    return path
def check(path,sha,within,size=None):
    path=safe(path,within)
    require(digest(path)==sha,'Remote hash mismatch: '+str(path))
    require(size is None or path.stat().st_size==size,'Remote size mismatch: '+str(path))
    return path
def arg(argv,flag):return argv[argv.index(flag)+1] if flag in argv else None
def requested(argv):
    if '--scenes' not in argv:return set(scenes)
    values=[]
    for value in argv[argv.index('--scenes')+1:]:
        if value.startswith('--'):break
        values.append(value)
    return set(values)
def acceptance_entries(path, root, scene_ids):
    """Explicit reviewed choices, bound to exact production bytes; never latest."""
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    def checked(value):
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        if ('..' in candidate.parts or not candidate.is_relative_to(root)
                or any(x.is_symlink() for x in [candidate, *candidate.parents])
                or not candidate.is_file()):
            raise ValueError('Invalid acceptance evidence path: ' + str(candidate))
        return candidate
    def hashed(candidate):
        with candidate.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    path = checked(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('VIDEO_ACCEPTANCE requires schema_version 1')
    accepted, rejected, seen = {}, {}, set()
    for group, decision in [('accepted', 'accepted'), ('rejected', 'rejected')]:
        for supplied in data[group]:
            row = dict(supplied)
            scene = row['scene_id']
            manifest = checked(row['production_manifest'])
            if (scene not in scene_ids or row['decision'] != decision
                    or not isinstance(row.get('reason'), str) or not row['reason'].strip()
                    or str(manifest) in seen):
                raise ValueError('Invalid or duplicate explicit visual decision')
            if hashed(manifest) != row['production_manifest_sha256']:
                raise ValueError('Accepted/rejected production manifest changed')
            product = json.loads(manifest.read_text(encoding='utf-8'))
            if product['scene_id'] != scene or product['session_id'] != row['session_id']:
                raise ValueError('Visual decision scene/session differs from production')
            row['production_manifest'] = str(manifest)
            seen.add(str(manifest))
            if decision == 'accepted':
                if scene in accepted:
                    raise ValueError('More than one accepted production for scene')
                accepted[scene] = row
            else:
                rejected[str(manifest)] = row
    if set(accepted) != set(scene_ids) or len(accepted) != 12:
        raise ValueError('Exactly twelve explicitly visually accepted scenes are required')
    return {'path': str(path), 'sha256': hashed(path), 'accepted': accepted, 'rejected': rejected}


def load_source_phases(root, run):
    """Read the explicit two-phase boundary without upgrading historical evidence."""
    def checked(value):
        path = Path(value)
        path = path if path.is_absolute() else root / path
        if ('..' in path.parts or not path.is_relative_to(root)
                or any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file()):
            raise ValueError('Unsafe phase snapshot path')
        return path
    manifest_path = checked(run / 'SOURCE_PHASES.json')
    manifest = read(manifest_path)
    if manifest.get('schema_version') != 1 or len(manifest['phases']) != 2:
        raise ValueError('Exactly two explicit source phases are required')
    phases = {}
    for phase in manifest['phases']:
        path = checked(phase['source_snapshot'])
        if digest(path) != phase['source_snapshot_sha256']:
            raise ValueError('Phase snapshot file hash mismatch')
        snapshot = read(path)
        source_digest = phase['source_digest']
        if snapshot['digest'] != source_digest or not snapshot['files'] or source_digest in phases:
            raise ValueError('Invalid or duplicate source phase snapshot')
        phases[source_digest] = {**phase, 'snapshot_path': path, 'snapshot': snapshot}
    if ({x['phase_id'] for x in phases.values()} != {'before_camera_atomic', 'camera_atomic'}
            or manifest['current_source_digest'] not in phases
            or phases[manifest['current_source_digest']]['phase_id'] != 'camera_atomic'):
        raise ValueError('Source phase boundary/current identity differs')
    old = next(x['snapshot'] for x in phases.values() if x['phase_id'] == 'before_camera_atomic')
    new = phases[manifest['current_source_digest']]['snapshot']
    old_files = {x['path']: x for x in old['files']}
    new_files = {x['path']: x for x in new['files']}
    changed = sorted(path for path in old_files.keys() | new_files.keys() if old_files.get(path) != new_files.get(path))
    if changed != manifest['changed_source_paths'] or changed != ['src/holocue/viewer_scene.py']:
        raise ValueError('Camera phase modifies more than the explicit viewer_scene boundary')
    previous = checked(manifest['previous_file'])
    expected = old_files[changed[0]]
    if digest(previous) != expected['sha256'] or previous.stat().st_size != expected['bytes']:
        raise ValueError('Preserved original camera source differs from the old snapshot')
    return manifest, phases

root=run.parents[2]
phase_manifest,source_phases=load_source_phases(root,run)
for item in source_phases[phase_manifest['current_source_digest']]['snapshot']['files']:
    check(root/item['path'],item['sha256'],root,item['bytes'])
acceptance=acceptance_entries(Path(sys.argv[2]) if len(sys.argv)>2 else run/'VIDEO_ACCEPTANCE.json', root, scenes)
commands=[]
for path in sorted(run.glob('*_command/execution.json')):
    record=read(path)
    commands.append((path,record))
def owner(script,flag,directory,scene=None,media_name=None,required=True,successful=True):
    matches=[]
    for path,record in commands:
        argv=record['command']
        if not any(Path(x).name==script for x in argv):continue
        value=arg(argv,flag)
        if value is None:continue
        target=Path(value)
        if not target.is_absolute():target=Path(record['cwd'])/target
        if target.resolve()!=directory:continue
        if scene is not None and scene not in requested(argv):continue
        if media_name is not None and (arg(argv,'--media-dir-name') or 'produced')!=media_name:continue
        if 'finished_at' in record and (not successful or record.get('returncode')==0):matches.append((path,record))
    if not required and not matches:return None
    require(len(matches)==1,'Require exactly one completed successful '+script+' owner: '+str(directory))
    return matches[0]
def current_identity(record,source,assets):
    require(source in source_phases and assets==phase_manifest['asset_digest'],'Unapproved source/assets phase')
    require(record['source_before']['digest']==record['source_after']['digest']==source,
            'Command/capture source identity mismatch')
    require(record['assets_before']['digest']==record['assets_after']['digest']==assets,
            'Command/capture asset identity mismatch')
files=[]
def add(path,local,kind,scene=None):
    path=safe(path,run)
    require(local not in {row['relative_path'] for row in files},'Duplicate local evidence filename')
    row={'remote_path':str(path),'relative_path':local,'bytes':path.stat().st_size,
         'sha256':digest(path),'kind':kind}
    if scene:row['scene_id']=scene
    files.append(row)
manifests=[Path(acceptance['accepted'][scene]['production_manifest']) for scene in scenes]
items=[];seen=set();identities=set();intro_map={};selected_raw=set();selected_media=set()
for manifest in manifests:
    product=read(manifest);scene=product['scene_id'];directory=manifest.parent.parent;attempt=directory.parent
    require(scene in scenes and scene not in seen,'Unexpected or duplicate successful scene')
    require(directory.name==scene,'Manifest scene differs from directory')
    seen.add(scene)
    capture=read(directory/'manifest.json');batch=read(attempt/'manifest.json')
    require(capture.get('passed') is True,'Incomplete capture cannot be downloaded as complete: '+scene)
    require([x for x in batch['scenes'] if x['scene_id']==scene]==[capture],'Capture batch/per-scene manifest mismatch')
    before=read(attempt/'provenance_before.json');after=read(attempt/'provenance_after.json')
    source=capture['source_digest'];assets=capture['asset_digest'];identities.add((source,assets))
    for phase in (before,after):
        require(phase['source']['digest']==source and phase['assets']['digest']==assets,'Capture provenance drift')
        require(phase['capture_script_sha256']==capture['capture_script_sha256'],'Capture tool provenance drift')
    for key in ('scene_id','session_id','source_digest','asset_digest','capture_script_sha256'):
        require(product[key]==capture[key],'Product/capture identity mismatch: '+key)
    require(capture['context_closed_before_manifest'] is True and capture['time_compression_applied'] is False,
            'Unflushed or retimed capture')
    capture_record,capture_command=owner('capture_ui_videos.py','--out',attempt,scene)
    production_record,production_command=owner('produce_videos.py','--capture-root',attempt,scene,manifest.parent.name)
    current_identity(capture_command,source,assets);current_identity(production_command,source,assets)
    raw=check(capture['raw_video'],capture['raw_video_sha256'],directory/'raw_video',capture['raw_video_bytes'])
    require(product['raw_video']['path']==str(raw) and product['raw_video']['sha256']==capture['raw_video_sha256'],
            'Product original recording differs')
    workflow=product['workflow_mp4'];intro=product['introduction_mp4']
    require(workflow['speed']==1 and workflow['cuts']==0,'Workflow changed playback speed or contains cuts')
    proof=read(manifest.parent/'frame_timing_verification.json')
    require(proof['verification']['passed'] is True and proof['verification']==workflow['frame_timing_verification'],
            'Missing successful complete-frame timing proof')
    for key,filename in (('input','raw_decoded_frames.json'),('output','workflow_decoded_frames.json')):
        decoded=read(manifest.parent/filename)
        require(len(decoded['frames'])==int(decoded['streams'][0]['nb_read_frames'])==proof[key]['decoded_frames'],
                'Complete frame evidence count differs from proof')
    require(proof['input']['decoded_frames']==proof['output']['decoded_frames'],'Decoded input/output frame count differs')
    check(workflow['path'],workflow['sha256'],manifest.parent)
    check(intro['path'],intro['sha256'],manifest.parent)
    introductions=read(directory/'introduction.json')
    require(introductions and introductions==intro['image_sources'],'Introduction real-image sources differ')
    for image in introductions:check(image['image'],image['image_sha256'],directory)
    contract_path=check(directory/'scene_contract.json',capture['scene_contract_sha256'],directory)
    contract=read(contract_path)
    require(contract['scene_id']==scene,'Scene contract identity mismatch')
    add(raw,scene+'/raw_original.webm','original_webm',scene)
    selected_raw.add(str(raw));selected_media.add(str(manifest.parent))
    add(Path(workflow['path']),scene+'/workflow_realtime.mp4','complete_realtime_ui',scene)
    add(Path(intro['path']),scene+'/scene_introduction.mp4','real_page_screenshot_introduction',scene)
    add(manifest,scene+'/production_manifest.json','provenance',scene)
    for filename in ('frame_timing_verification.json','raw_decoded_frames.json','workflow_decoded_frames.json'):
        add(manifest.parent/filename,scene+'/'+filename,'frame_proof',scene)
    for filename in ('manifest.json','scene_contract.json','introduction.json','events.json','api_reads.jsonl'):
        add(directory/filename,scene+'/'+('capture_manifest.json' if filename=='manifest.json' else filename),'capture_evidence',scene)
    for filename in ('provenance_before.json','provenance_after.json'):
        add(attempt/filename,scene+'/'+filename,'provenance',scene)
    add(capture_record,scene+'/capture_execution.json','command_record',scene)
    add(production_record,scene+'/production_execution.json','command_record',scene)
    runtime_hash=capture.get('viser_client_build_sha256')
    if runtime_hash:
        require(before.get('viser_client_build_sha256')==after.get('viser_client_build_sha256')==runtime_hash,'Capture client runtime changed')
        served=read(directory/'served_client.json');documents=served['documents']
        require(served['installed_build_sha256']==runtime_hash and len(documents)==1 and documents[0]['status']==200 and documents[0]['sha256']==runtime_hash,
                'Actual served client identity differs')
        add(directory/'served_client.json',scene+'/served_client.json','actual_runtime_client',scene)
        canvas_paths=[directory/'canvas_initial.json']
        capture_dirs=[Path(row['directory']) for row in capture['stages']]+[Path(row['image']).parent for row in introductions]
        for capture_dir in capture_dirs:
            require(capture_dir.is_relative_to(directory),'Canvas evidence outside capture scene')
            canvas_paths.extend(capture_dir/name for name in ('canvas_before.json','canvas_after.json'))
        for path in dict.fromkeys(canvas_paths):
            canvas=read(path);last=canvas['observations'][-1]['canvases']
            require(canvas.get('passed') is True and last and all(float(c['opacity'])==1 and all(float(a)==1 for a in c['ancestor_opacities']) for c in last),
                    'Accepted new capture lacks full-opacity canvas proof')
            add(path,scene+'/'+path.relative_to(directory).as_posix(),'actual_canvas_opacity',scene)
    items.append({'scene_id':scene,'title':contract['title'],'instruction':contract['initial_instruction'],
                  'visual_decision':'accepted','visual_reason':acceptance['accepted'][scene]['reason'],
                  'viser_client_build_sha256':capture.get('viser_client_build_sha256'),
                  'session_id':capture['session_id'],'source_digest':source,'asset_digest':assets})
    intro_map[str(Path(intro['path']))]=(scene,intro['sha256'])
require(seen==set(scenes) and len(identities)==1,'Video set lacks exact 12 scenes or has mixed source/assets')
source,assets=next(iter(identities))
require(source_phases[source]['phase_id']=='before_camera_atomic','Accepted media must retain the pre-camera source phase')
additional_attempts=[]
for directory in sorted((run/'videos').glob('*/*/raw_video')):
    raws=sorted(directory.glob('*.webm'))
    unselected=[raw for raw in raws if str(raw) not in selected_raw]
    if not unselected:continue
    scene_directory=directory.parent;scene=scene_directory.name;attempt=scene_directory.parent
    require(scene in scenes,'Unexpected scene in additional raw recordings')
    command_path,command=owner('capture_ui_videos.py','--out',attempt,scene,successful=False)
    current_identity(command,source,assets)
    capture_path=scene_directory/'manifest.json';capture=read(capture_path) if capture_path.is_file() else None
    if capture:
        require(capture['scene_id']==scene and capture['source_digest']==source and capture['asset_digest']==assets,
                'Additional capture manifest identity mismatch')
        check(capture['raw_video'],capture['raw_video_sha256'],directory,capture['raw_video_bytes'])
    status=('interrupted_before_manifest' if capture is None else
            'failed_capture' if not capture.get('passed') else 'successful_capture_without_selected_product')
    rejected_here=any(Path(row['production_manifest']).parent.parent==scene_directory for row in acceptance['rejected'].values())
    status='visually_rejected' if rejected_here else status
    local=('rejected_attempts/' if rejected_here else 'retained_attempts/')+attempt.name+'/'+scene
    raw_rows=[]
    for raw in unselected:
        relative=local+'/'+raw.name
        add(raw,relative,'additional_original_webm_not_complete',scene)
        raw_rows.append({'relative_path':relative,'remote_path':str(raw),'bytes':raw.stat().st_size,'sha256':digest(raw)})
    for filename in ('manifest.json','failure.json','failure_page.png','events_on_failure.json','events_unavailable.json',
                     'api_reads.jsonl','scene_contract.json','introduction.json','stages.json','ui_timeline.json','served_client.json','canvas_initial.json'):
        path=scene_directory/filename
        if path.is_file():add(path,local+'/'+filename,'additional_attempt_evidence',scene)
    for filename in ('provenance_before.json','provenance_after.json'):
        path=attempt/filename
        if path.is_file():add(path,local+'/'+filename,'additional_attempt_provenance',scene)
    add(command_path,local+'/capture_execution.json','additional_attempt_command',scene)
    additional_attempts.append({'scene_id':scene,'attempt':attempt.name,'status':status,'complete_demonstration':False,
                               'session_id':capture.get('session_id') if capture else None,
                               'command_returncode':command['returncode'],'raw_files':raw_rows})
incomplete_productions=[]
for command_path,command in commands:
    argv=command['command']
    if not any(Path(x).name=='produce_videos.py' for x in argv):continue
    attempt=Path(arg(argv,'--capture-root'))
    if not attempt.is_absolute():attempt=Path(command['cwd'])/attempt
    media_name=arg(argv,'--media-dir-name') or 'produced'
    for scene in sorted(requested(argv)):
        media=attempt/scene/media_name
        if str(media) in selected_media or not media.exists():continue
        require('finished_at' in command,'Unfinished production cannot be frozen for delivery')
        current_identity(command,source,assets)
        rejected=acceptance['rejected'].get(str(media/'manifest.json'))
        local=('rejected_attempts/' if rejected else 'retained_attempts/')+attempt.name+'/'+scene+'/'+media_name
        add(command_path,local+'/production_execution.json','incomplete_production_command',scene)
        for filename in ('manifest.json','frame_timing_verification.json','workflow_encode.command.json',
                         'workflow_encode.stderr.log','workflow_encode.stdout.log'):
            path=media/filename
            if path.is_file():add(path,local+'/'+filename,'incomplete_production_evidence',scene)
        for path in sorted(media.glob('*.mp4')):
            add(path,local+'/'+path.name,'rejected_or_retained_production_media',scene)
        for filename in ('raw_decoded_frames.json','workflow_decoded_frames.json'):
            path=media/filename
            if path.is_file():add(path,local+'/'+filename,'retained_frame_proof',scene)
        incomplete_productions.append({'visual_decision':'rejected' if rejected else 'retained_unselected','scene_id':scene,'directory':str(media),'returncode':command['returncode'],
                                       'manifest_exists':(media/'manifest.json').is_file(),
                                       'status':'failed_or_unselected_production','complete_demonstration':False,
                                       'raw_recordings':[str(path) for path in sorted((attempt/scene/'raw_video').glob('*.webm'))]})
add(Path(acceptance['path']),'VIDEO_ACCEPTANCE.json','explicit_visual_acceptance')
collection_dir=run/'videos/all_scenes_introduction';collection_path=collection_dir/'manifest.json';collection=read(collection_path)
require(collection.get('passed') is True and len(collection['outputs'])==1,'Incomplete introduction collection')
require(collection.get('acceptance_manifest_sha256')==acceptance['sha256'],'Collection visual acceptance differs')
output=collection['outputs'][0];sources=output['sources']
require(len(sources)==12 and {x['scene_id'] for x in sources}==set(scenes),'Collection does not cover exactly 12 scenes')
for row in sources:require(intro_map.get(row['path'])==(row['scene_id'],row['sha256']),'Collection source mismatch')
require(collection['decoded_input_frames']==collection['decoded_output_frames']==sum(x['decoded_frames'] for x in sources),
        'Collection frame count proof differs')
require(abs(collection['actual_duration_s']-collection['expected_duration_s'])<=.05,'Collection duration proof failed')
movie=check(output['path'],output['sha256'],collection_dir)
command_path=safe(output['command_record'],run);command=read(command_path)
require(command.get('returncode')==0 and 'finished_at' in command,'Collection command did not complete successfully')
require(any(Path(x).name=='combine_introductions.py' for x in command['command']),'Incorrect collection command owner')
collection_source=command['source_before']['digest']
current_identity(command,collection_source,assets)
require(collection.get('source_digest')==source and collection.get('asset_digest')==assets,
        'Collection input media source/assets differ')
require(collection.get('execution_source_digest')==collection_source
        and collection.get('source_phase_manifest_sha256')==digest(run/'SOURCE_PHASES.json'),
        'Collection execution source phase is not explicitly bound')
for row in sources:require(row.get('source_digest')==source and row.get('asset_digest')==assets,'Collection per-input phase mismatch')
collection_execution={'command_record':str(command_path),'source_before':collection_source,
    'source_after':command['source_after']['digest'],'asset_digest':assets}
add(movie,'all_scenes_introduction/twelve_scenes_introduction.mp4','twelve_scene_screenshot_introduction')
add(collection_path,'all_scenes_introduction/manifest.json','provenance')
add(command_path,'all_scenes_introduction/production_execution.json','command_record')
additional_large_originals=[]
already={row['remote_path'] for row in files}
for path in sorted(run.rglob('*')):
    if not path.is_file() or path.suffix.lower() not in {'.webm','.mp4'} or path.stat().st_size<47*1048576:continue
    relative=path.relative_to(run)
    if relative.parts[0]=='review_videos' or relative.parts[0].startswith('upload') or str(path) in already:continue
    local='additional_large_originals/'+relative.as_posix()
    add(path,local,'additional_large_original_media_not_complete_demo')
    additional_large_originals.append({'remote_path':str(path),'relative_path':local,'bytes':path.stat().st_size,
                                      'sha256':digest(path),'complete_demonstration':False,
                                      'scope':'Additional preserved original; actual success/failure remains in its command evidence'})
incomplete=[str(p) for p in sorted((run/'videos').glob('*/*/produced*')) if p.is_dir() and not (p/'manifest.json').is_file()]
print(json.dumps({'remote_run':str(run),'scenes':sorted(items,key=lambda x:scenes.index(x['scene_id'])),
                  'current_source_digest':phase_manifest['current_source_digest'],
                  'current_source_identity_basis':'Explicit SOURCE_PHASES camera phase; every listed current source file verified by size/SHA256',
                  'source_phases':{'path':str(run/'SOURCE_PHASES.json'),'sha256':digest(run/'SOURCE_PHASES.json')},
                  'collection_execution':collection_execution,
                  'visual_acceptance':acceptance, 'source_digest':source,'asset_digest':assets,'files':sorted(files,key=lambda x:x['relative_path']),
                  'additional_recording_attempts':additional_attempts,'failed_or_incomplete_productions':incomplete_productions,
                  'additional_large_originals':additional_large_originals,
                  'excluded_incomplete_production_directories':incomplete},ensure_ascii=False))
'''


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch_inventory(host, acceptance_manifest):
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', host,
                             'python3 - ' + shlex.quote(REMOTE_RUN) + ' ' + shlex.quote(acceptance_manifest)],
                            input=REMOTE_PROGRAM, text=True, encoding='utf-8',
                            capture_output=True, check=True)
    return json.loads(result.stdout)


def matching(path, row):
    return path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256']


def write_no_replace(path, data):
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise FileExistsError('Existing differing file preserved: ' + str(path))
        return
    with path.open('xb') as stream:
        stream.write(data)


def index_html(inventory):
    esc = html.escape
    cards = []
    for item in inventory['scenes']:
        scene = quote(item['scene_id'], safe='')
        cards.append(f'''<article><h2>{esc(item['title'])}</h2>
<p class="task">任务：{esc(item['instruction'])}</p>
<h3>场景介绍 · 真实页面截图</h3>
<video controls preload="none" src="{scene}/scene_introduction.mp4"></video>
<h3>真实 UI 完整流程 · 全程等速</h3>
<video controls preload="none" src="{scene}/workflow_realtime.mp4"></video>
<p><a href="{scene}/raw_original.webm">原始 WebM</a> ·
<a href="{scene}/production_manifest.json">制作来源</a> ·
<a href="{scene}/frame_timing_verification.json">帧与时间核验</a></p>
<p class="meta">场景 {esc(item['scene_id'])} · 真实会话 {esc(item['session_id'])}</p></article>''')
    failure_links = []
    for attempt in inventory['additional_recording_attempts']:
        links = ' · '.join('<a href="' + quote(row['relative_path'], safe='/') + '">原始 WebM</a>'
                           for row in attempt['raw_files'])
        failure_links.append('<p>' + esc(attempt['scene_id'] + ' / ' + attempt['attempt'] + ' / ' + attempt['status']) +
                             '：' + links + '</p>')
    failed_section = ('<section><h2>视觉拒绝、失败与其他保留尝试</h2><p>以下原件独立保留，不属于上方完整通过演示。'
                      '制作中断但原始采集成功的尝试，详见文件清单；共用的原始 WebM 已在对应场景交付。</p>' +
                      ''.join(failure_links) + '</section>') if failure_links or inventory['failed_or_incomplete_productions'] else ''
    return ('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>HoloCue · 12 场真实页面视频</title>
<style>body{max-width:1200px;margin:32px auto;padding:0 20px;font:16px/1.7 system-ui,sans-serif;color:#e5edf8;background:#101827}
h1,h2,h3{line-height:1.3}h1{font-size:30px}h2{margin-top:0}h3{font-size:17px}
article,section{padding:24px;margin:24px 0;border:1px solid #35465e;border-radius:12px;background:#182438}
video{display:block;width:100%;max-height:78vh;background:#080d15}a{color:#8ec8ff}.meta{font-size:13px;color:#b1c1d5;overflow-wrap:anywhere}.task{color:#d9e6f5}</style>
<h1>HoloCue · 12 场真实页面视频</h1>
<p>场景介绍使用实际 Viser 页面的全景与细节截图制作，为静态截图介绍视频。完整演示保留真实模型等待、暂停、检查、恢复与确认，全程等速，无删帧或剪切。</p>
<p>原始全流程持续时间是真实记录；其中包含自动验收的截图稳定与取证等待，不能作为人工操作耗时或模型纯推理延迟的测量，也不能把全部等待归于 Qwen。</p>
<p>这些视频证明真实 UI 流程，仅属 UI 证据；不代替 native / Blender 验收。每场同时交付完整原始 WebM。视频不会自动播放或预加载。</p>
<p><a href="VIDEO_FILES.json">本地文件清单与 SHA256</a></p>
<section><h2>12 场介绍合集 · 真实页面截图</h2>
<video controls preload="none" src="all_scenes_introduction/twelve_scenes_introduction.mp4"></video>
<p><a href="all_scenes_introduction/manifest.json">合集来源与帧数核验</a></p></section>
''' + '\n'.join(cards) + failed_section + '</html>\n').encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='4029')
    parser.add_argument('--destination', type=Path, default=DESTINATION)
    parser.add_argument('--acceptance-manifest', default=REMOTE_RUN+'/VIDEO_ACCEPTANCE.json', help='Remote explicit visual acceptance manifest')
    args = parser.parse_args()
    if args.host.startswith('-') or any(x.isspace() for x in args.host):
        raise ValueError('Host must be an SSH configuration alias')
    inventory = fetch_inventory(args.host, args.acceptance_manifest)
    destination = args.destination.resolve()
    # Inspect every final destination before copying anything. Existing mismatches
    # require human handling; neither the originals nor completed local files move.
    for row in inventory['files']:
        path = destination / row['relative_path']
        if not path.is_relative_to(destination) or '..' in Path(row['relative_path']).parts:
            raise ValueError('Invalid relative delivery path')
        if path.exists() and not matching(path, row):
            raise FileExistsError('Existing differing file preserved: ' + str(path))
    destination.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(inventory['files'], 1):
        path = destination / row['relative_path']
        if matching(path, row):
            print(f'[{index}/{len(inventory["files"])}] 已核验复用 {row["relative_path"]}')
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.part')
        # Remote paths are observed manifest paths, not shell commands. All current
        # evidence names are ASCII without whitespace/quoting characters.
        if any(char in row['remote_path'] for char in "\n\r'\" "):
            raise ValueError('Unexpected remote pathname; refuse ambiguous scp quoting')
        subprocess.run(['scp', '-p', '-o', 'BatchMode=yes',
                        args.host + ':' + row['remote_path'], str(temporary)], check=True)
        if not matching(temporary, row):
            raise RuntimeError('Downloaded size/SHA mismatch; partial preserved: ' + str(temporary))
        if path.exists():
            raise FileExistsError('Destination appeared during download; both files preserved: ' + str(path))
        # Windows rename does not replace an existing destination.
        temporary.rename(path)
        print(f'[{index}/{len(inventory["files"])}] 已下载并核验 {row["relative_path"]}')
    # Read-only second pass catches remote changes during a long download.
    if fetch_inventory(args.host, args.acceptance_manifest) != inventory:
        raise RuntimeError('Remote media/provenance changed during download; local files retained, no success index written')
    rows = []
    for row in inventory['files']:
        path = destination / row['relative_path']
        if not matching(path, row):
            raise RuntimeError('Final local verification failed: ' + str(path))
        rows.append({**row, 'absolute_path': str(path), 'verified_size_and_sha256': True})
    html_path = destination / 'VIDEO_INDEX.html'
    html_bytes = index_html(inventory)
    write_no_replace(html_path, html_bytes)
    rows.append({'absolute_path': str(html_path), 'relative_path': html_path.name,
                 'bytes': len(html_bytes), 'sha256': hashlib.sha256(html_bytes).hexdigest(),
                 'kind': 'local_playback_index'})
    report = {'passed': True, 'remote_run': inventory['remote_run'], 'source_digest': inventory['source_digest'],
              'current_source_digest': inventory['current_source_digest'],
              'current_source_identity_basis': inventory['current_source_identity_basis'],
              'source_phases': inventory['source_phases'], 'collection_execution': inventory['collection_execution'],
              'asset_digest': inventory['asset_digest'], 'scene_count': 12, 'complete_scene_original_webm_count': 12,
              'original_webm_count': sum(row['kind'] in {'original_webm','additional_original_webm_not_complete'} for row in rows),
              'workflow_mp4_count': 12, 'scene_introduction_mp4_count': 12, 'collection_mp4_count': 1,
              'scope': '真实 UI 完整等速录像与真实页面静态截图介绍；不是 native / Blender 验收',
              'timing_scope': '真实全流程持续时间包含自动验收的截图稳定与取证等待；不是人工操作耗时或模型纯推理延迟，不能将全部等待归于 Qwen。',
              'visual_acceptance':inventory['visual_acceptance'],
              'scenes': inventory['scenes'], 'files': rows,
              'additional_recording_attempts': inventory['additional_recording_attempts'],
              'failed_or_incomplete_productions': inventory['failed_or_incomplete_productions'],
              'additional_large_originals': inventory['additional_large_originals'],
              'excluded_incomplete_production_directories': inventory['excluded_incomplete_production_directories'],
              'note': 'All original WebM bytes retained regardless of size. This inventory excludes its own recursive hash.'}
    write_no_replace(destination / 'VIDEO_FILES.json',
                     (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'passed': True, 'files': len(rows), 'index': str(html_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
