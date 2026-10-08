"""Poll a UI run and print its final state. Usage: python check_run.py <run_id> [port]"""
import json
import sys
import time
import urllib.request

rid = sys.argv[1]
port = sys.argv[2] if len(sys.argv) > 2 else "8077"
base = f"http://127.0.0.1:{port}"


def get(path):
    with urllib.request.urlopen(base + path, timeout=30) as r:
        return json.load(r)


for i in range(60):
    run = get(f"/api/run/{rid}")
    print(f"t={i}: run={run['status']} " + " ".join(
        f"{p['key']}={p['status']}({p['moves']})" for p in run["panels"]))
    if run["status"] == "done":
        break
    time.sleep(5)

run = get(f"/api/run/{rid}")
print(f"\nrun {run['id']} {run['status']} | seed {run['seed']} | start {run['start']}")
for p in run["panels"]:
    print(f"  {p['key']:8} {p['status']:8} moves={p['moves']:3} "
          f"final={p.get('final_facelets')}/54 faces={p.get('final_faces')} "
          f"median={p.get('median_ms')}ms solved={p['solved']}")
    print("           log:", " ".join(m["move"] for m in p["move_log"][:10]))
