"""A real-LLM interruption/restoration acceptance; writes partial evidence even on failure."""

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_client import make_client, req, send, state, control, new_session

p = argparse.ArgumentParser()
p.add_argument("--api", default="http://127.0.0.1:8750")
p.add_argument("--out", default="runs/live_interrupt.json")
a = p.parse_args()
client = make_client(a.api)
report = {"backend_mode": "live", "status": "running", "events": []}
path = Path(a.out)
path.parent.mkdir(parents=True, exist_ok=True)


def save():
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


def say(text):
    j, s, elapsed = send(client, sid, text, timeout=100, poll=0.25)
    report["events"].append({"input": text, "job": j, "elapsed_s": elapsed, "state": s})
    save()
    assert j["status"] == "done", j
    return state(client, sid)


try:
    assert req(client, "GET", "/health")["backend_mode"] == "live", "Live endpoint required"
    sid = new_session(client, "control_panel")
    report["session_id"] = sid
    s = say("把 B 逆时针转 30 度，接着检查 C 的背面。")
    original = s["queue"][0]
    assert original["semantic"]["target_id"] == "B" and original["semantic"]["angle_deg"] == 30
    s = say("先别管 B，看看 C 的背面，保留 B 的角度。")
    assert s["queue"][0]["semantic"]["target_id"] == "C" and s["suspended"][-1][0] == original
    s = control(client, sid, "complete")
    s = say("继续刚才 B 的任务。")
    assert s["queue"][0] == original
    before = s["queue"]
    s = control(client, sid, "pause")
    assert s["execution"] == "paused" and s["queue"] == before
    s = control(client, sid, "resume")
    assert s["execution"] == "running" and s["queue"] == before
    report["status"] = "passed"
except Exception as e:
    report["status"] = "failed"
    report["error"] = repr(e)
    save()
    raise
finally:
    save()
    client.close()
print(path)
