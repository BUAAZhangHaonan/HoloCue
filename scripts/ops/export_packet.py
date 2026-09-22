import argparse, json, os, urllib.request
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("session_id")
p.add_argument("--api", default="http://127.0.0.1:8750")
p.add_argument("--out", required=True)
a = p.parse_args()
headers = {}
if os.getenv("HOLOCUE_API_KEY"):
    headers["Authorization"] = "Bearer " + os.environ["HOLOCUE_API_KEY"]
with urllib.request.urlopen(
    urllib.request.Request(a.api + "/api/v1/sessions/" + a.session_id + "/display", headers=headers),
    timeout=5,
) as r:
    data = json.load(r)
Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
