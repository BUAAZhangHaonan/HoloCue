"""Verify every shipped file against MANIFEST.sha256 before making local edits."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
manifest = ROOT / "MANIFEST.sha256"
errors = []
count = 0
for line in manifest.read_text(encoding="utf-8").splitlines():
    expected, relative = line.split("  ", 1)
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Manifest path escapes project root")
    if not path.is_file():
        errors.append("missing " + relative)
    elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        errors.append("changed " + relative)
    count += 1
if errors:
    raise SystemExit("\n".join(errors))
print(f"Package integrity verified: {count} files")
