"""End-to-end check of the UI server: waits for models, starts a run, verifies 4 sections."""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8077"


def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r:
        return json.load(r)


def post(p, body):
    req = urllib.request.Request(BASE + p, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


for i in range(80):
    eng = get("/api/engines")["engines"]
    if not any(e["status"] == "loading" for e in eng):
        break
    time.sleep(5)
print("engines:", [(e["key"], e["status"]) for e in eng])

run_id = post("/api/run", {"seed": 20261002, "mode": "greedy", "policy": "sample", "moves": 3})["run_id"]
print("started run", run_id)
for i in range(40):
    run = get(f"/api/run/{run_id}")
    if run["status"] == "done":
        break
    time.sleep(4)

print(f"run status: {run['status']}")
print(f"PANELS IN VIEW: {len(run['panels'])}  (expected 4)")
for p in run["panels"]:
    print(f"  {p['key']:8} status={p['status']:11} moves={p['moves']} "
          f"facelets={p.get('final_facelets') or p['facelets']}/54 net={'yes' if p['net'] else 'NO'}")
assert len(run["panels"]) == 4, "expected exactly 4 sections"
print("OK: four sections, one per model")
