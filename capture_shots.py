"""Start a real UI race, then screenshot the live page mid-run and at the end.

Uses headless Chrome (which, unlike the agent browser tool, can reach localhost).
Writes results/ui_midrun.png and results/ui_final.png.
"""
import json
import subprocess
import time
import urllib.request

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE = "http://127.0.0.1:8077"
SHOTS = "/Users/shk/cube-arena/results"


def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r:
        return json.load(r)


def post(p, body):
    req = urllib.request.Request(BASE + p, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def shot(run_id, out):
    url = f"{BASE}/?run={run_id}"
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=1", "--window-size=1900,1150",
           f"--user-data-dir=/tmp/chrome-shot-{out}",
           "--virtual-time-budget=8000",
           f"--screenshot={out}", url]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print(f"  chrome rc={p.returncode} -> {out}")
    if p.returncode != 0:
        print("  stderr:", p.stderr[-500:])


# wait for models
for i in range(80):
    eng = get("/api/engines")["engines"]
    if not any(e["status"] == "loading" for e in eng):
        break
    time.sleep(5)
print("engines:", [(e["key"], e["status"]) for e in eng])

rid = post("/api/run", {"seed": 20261002, "mode": "greedy", "policy": "sample", "moves": 24})["run_id"]
print("run:", rid)

print("waiting 32s for a mid-run spread…")
time.sleep(32)
mid = get(f"/api/run/{rid}")
print("  mid:", [(p["key"], p["status"], p["moves"], p["facelets"]) for p in mid["panels"]])
shot(rid, f"{SHOTS}/ui_midrun.png")

for i in range(40):
    run = get(f"/api/run/{rid}")
    if run["status"] == "done":
        break
    time.sleep(5)
print("final:", [(p["key"], p["status"], p["moves"], p.get("final_facelets")) for p in run["panels"]])
shot(rid, f"{SHOTS}/ui_final.png")
print("done")
