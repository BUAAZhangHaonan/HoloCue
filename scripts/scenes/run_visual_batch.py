"""Run one isolated native mesh-rendering process per scene and assemble evidence."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image

from holocue.config import root, list_scenes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--scenes", nargs="*")
    args = parser.parse_args()
    if not 1 <= args.workers <= 2:
        raise ValueError("use one or two CPU render workers")
    output = root() / "runs/simulation/rendered"
    output.mkdir(parents=True, exist_ok=True)
    available = [entry["scene_id"] for entry in list_scenes()]
    scenes = args.scenes or available
    if len(set(scenes)) != len(scenes) or not set(scenes).issubset(available):
        raise ValueError("scene selection must contain unique known identifiers")

    def run(sid):
        with (output / f"{sid}.log").open("w") as log:
            subprocess.run(
                [
                    sys.executable,
                    "scripts/scenes/validate_renderings.py",
                    "--scenes",
                    sid,
                    "--out",
                    str((output / sid).relative_to(root())),
                ],
                cwd=root(),
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        print(sid, "completed", flush=True)
        return json.loads((output / sid / f"{sid}_render.json").read_text())

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(run, scenes))
    (output / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    sheet = Image.new("RGB", (1920, 4 * 480), (239, 243, 246))
    for index, row in enumerate(results):
        image = Image.open(output / row["scene_id"] / row["overview"])
        image.thumbnail((640, 475))
        sheet.paste(image, ((index % 3) * 640, (index // 3) * 480))
    sheet.save(output / "twelve_scenes.png")


if __name__ == "__main__":
    main()
