"""Format every Git-visible source file, or check it without changing files."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = ROOT / "tools/formatting"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    tracked = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    )
    paths = sorted({ROOT / name.decode() for name in tracked.split(b"\0") if name})
    paths = [path for path in paths if path.is_file()]
    python = [str(path) for path in paths if path.suffix in {".py", ".pyi"}]
    frontend = [str(path) for path in paths if path.suffix in {".js", ".cjs", ".mjs", ".ts", ".tsx", ".sh"}]
    if python:
        command = [sys.executable, "-m", "ruff", "format"]
        if args.check:
            command.append("--check")
        subprocess.run([*command, *python], cwd=ROOT, check=True)
    if frontend:
        subprocess.run(
            [
                "node",
                str(TOOLCHAIN / "node_modules/prettier/bin/prettier.cjs"),
                "--config",
                str(ROOT / ".prettierrc.json"),
                "--check" if args.check else "--write",
                *frontend,
            ],
            cwd=TOOLCHAIN,
            check=True,
        )
    print(
        f"{'Checked' if args.check else 'Formatted'} {len(python)} Python and {len(frontend)} frontend/Shell files."
    )


if __name__ == "__main__":
    main()
