"""Use the verified kit packer with the explicit frontend source extensions."""
import importlib.util
import json
import os
import sys
from pathlib import Path

root=Path(os.environ['HOLOCUE_ROOT'])
run=Path(os.environ['RUN_DIR'])
kit=Path(os.environ['RECORD_KIT'])
spec=importlib.util.spec_from_file_location('review_bundle',kit/'tools/review_bundle.py')
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
module.ALLOWED.update({'.cjs','.diff','.ts','.tsx'})
module.TEXT.update({'.cjs','.diff','.ts','.tsx'})
selection=module.Selection.model_validate_json((run/'review_selection.json').read_text())
print(json.dumps(module.pack(root,selection,run/'upload',47*1024*1024),ensure_ascii=False,indent=2))
