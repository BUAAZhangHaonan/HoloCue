"""Acceptance against an actually running local model. Never substitutes replay for a failed model."""

import argparse, json, time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_client import make_client, req, send, new_session, display

p = argparse.ArgumentParser()
p.add_argument("--api", default="http://127.0.0.1:8750")
p.add_argument("--out", default="runs/live_smoke.json")
a = p.parse_args()
client = make_client(a.api)
assert req(client, "GET", "/health")["backend_mode"] == "live", "Acceptance requires a live local model"
report = {"backend_mode": "live", "cases": []}
for scene, text in [
    ("control_panel", "把 B 逆时针转 30 度，接着检查 C 的背面。"),
    ("connector", "演示把 P 插进 S，插好后再检查 C。"),
    ("blocks", "先把 A 放到底板 BASE 上，然后检查 B 的背面。"),
]:
    sid = new_session(client, scene)
    j, s, elapsed = send(client, sid, text, timeout=100, poll=0.25)
    assert j["status"] == "done", j
    out = display(client, sid)
    expected = {"control_panel": "B", "connector": "P", "blocks": "A"}[scene]
    assert out["cues"][0]["target_id"] == expected, out
    assert sum(c["n_gaussians"] for c in out["cues"]) <= out["budget_total"]
    report["cases"].append(
        {"scene_id": scene, "session_id": sid, "latency_s": elapsed, "job": j, "packet": out}
    )
client.close()
path = Path(a.out)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(path)
