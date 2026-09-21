"""Official Khronos validation and the project's dense accessor contract."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from .config import root


def validate_glb(path: Path | str) -> dict:
    source = Path(path).resolve(strict=True)
    if source.suffix.lower() != '.glb':
        raise ValueError('Expected a GLB asset')
    script = root()/'tools/gltf_validation/validate.cjs'
    result = subprocess.run(['node', str(script), str(source)],
        cwd=script.parent, check=True, capture_output=True, text=True, timeout=60)
    decoded = json.loads(result.stdout)
    report = decoded['report']
    if report['issues']['numErrors']:
        raise ValueError(json.dumps(decoded, ensure_ascii=False))
    return decoded


def require_dense_accessors(document) -> None:
    for index, accessor in enumerate(document.accessors):
        if accessor.sparse is not None:
            raise ValueError(f'HoloCue exported accessor {index} must be dense')
