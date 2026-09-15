"""Read metadata and shard headers without loading weights into host/GPU memory."""
import argparse,json,struct
from pathlib import Path

def validate(path):
    path=Path(path).resolve()
    config=json.loads((path/'config.json').read_text())
    if config.get('model_type')!='qwen3_5':raise ValueError('Expected official Qwen3.5 dense multimodal configuration')
    for file in ['tokenizer_config.json','tokenizer.json']:
        if not (path/file).is_file():raise FileNotFoundError(file)
    index=path/'model.safetensors.index.json'
    names=sorted(set(json.loads(index.read_text())['weight_map'].values())) if index.exists() else [x.name for x in path.glob('*.safetensors')]
    if not names:raise ValueError('No safetensors shards found')
    size=0
    for name in names:
        f=(path/name).resolve()
        if not f.is_relative_to(path):raise ValueError('Shard path escapes the model directory')
        with f.open('rb') as stream:
            raw=stream.read(8)
            if len(raw)!=8:raise ValueError('Truncated shard: '+name)
            n=struct.unpack('<Q',raw)[0]
            if n>64*1024**2 or n<2:raise ValueError('Invalid safetensors header: '+name)
            h=json.loads(stream.read(n))
            ends=[v['data_offsets'][1] for k,v in h.items() if k!='__metadata__']
            if ends and f.stat().st_size < 8+n+max(ends):raise ValueError('Incomplete shard: '+name)
        size+=f.stat().st_size
    return {'path':str(path),'model_type':config['model_type'],'architectures':config.get('architectures'),
            'shards':len(names),'total_bytes':size,'validation':'metadata_and_lengths','content_hash_verified':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path');a=p.parse_args();print(json.dumps(validate(a.path),indent=2))
