"""Verify required review artifacts, not whether an AI's observations are scientifically correct."""

import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRECTORIES = (
    "src",
    "scripts",
    "configs",
    "scenes",
    "prompts",
    "tests",
    "assets",
    "docs",
    "schemas",
    "scene_agent",
    ".claude",
)
SOURCE_FILES = (
    "pyproject.toml",
    "requirements-simulation.txt",
    "README.md",
    "AGENTS.md",
    "GOAL_EXECUTION_PROMPT.md",
    "CLAUDE.md",
    ".env.example",
    ".gitignore",
)


def source_digest():
    h = hashlib.sha256()
    for folder in SOURCE_DIRECTORIES:
        for p in sorted((ROOT / folder).rglob("*")):
            if p.is_file() and "__pycache__" not in str(p) and p.suffix != ".pyc":
                h.update(str(p.relative_to(ROOT)).encode())
                h.update(p.read_bytes())
    for name in SOURCE_FILES:
        p = ROOT / name
        h.update(name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def validate(directory):
    required = {"scene_visual", "state_tasks", "architecture_safety"}
    records = [json.loads(p.read_text()) for p in directory.glob("*.json")]
    if len(records) < 3:
        raise ValueError("At least three independent SubAgent reviews are required")
    if not required.issubset({x["scope"] for x in records}):
        raise ValueError("Missing a required review scope")
    if len({x["independent_session_id"] for x in records}) < 3:
        raise ValueError("Review sessions must be distinct")
    for x in records:
        if x["status"] != "passed":
            raise ValueError("Unresolved review findings")
        if x["source_sha256"] != source_digest():
            raise ValueError("Code changed since review; rerun reviews")
        if not x.get("observations") or not x.get("evidence"):
            raise ValueError("Empty review")
        for e in x["evidence"]:
            p = (ROOT / e["path"]).resolve()
            if not p.is_relative_to(ROOT) or not p.is_file() or not p.stat().st_size:
                raise ValueError("Missing evidence")
            if hashlib.sha256(p.read_bytes()).hexdigest() != e["sha256"]:
                raise ValueError("Evidence hash mismatch")
    visual = [x for x in records if x["scope"] == "scene_visual"]
    if not any(x.get("visually_inspected") is True for x in visual):
        raise ValueError("Visual inspection required")
    print("Review artifact gate passed. Read the reviews and evidence before accepting claims.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="runs/reviews")
    p.add_argument("--digest", action="store_true")
    a = p.parse_args()
    if a.digest:
        print(source_digest())
    else:
        validate(ROOT / a.dir)
