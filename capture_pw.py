"""Capture the live cube-arena UI with Playwright (can reach localhost).

Starts a real race, screenshots the page mid-run, then again when it finishes.
Run with the python that has Playwright:  /opt/anaconda3/bin/python3 capture_pw.py
"""
import json
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

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


def launch(pw):
    for kw in ({}, {"channel": "chrome"}):
        try:
            return pw.chromium.launch(**kw)
        except Exception as e:  # noqa: BLE001
            print("  launch fallback:", type(e).__name__, e)
    raise RuntimeError("could not launch chromium")


with sync_playwright() as pw:
    browser = launch(pw)
    page = browser.new_page(viewport={"width": 1920, "height": 1180},
                            device_scale_factor=2)

    def snap(run_id, out):
        page.goto(f"{BASE}/?run={run_id}", wait_until="load")
        page.wait_for_selector(".panel .face3d .st", timeout=30000)
        page.wait_for_function("document.querySelectorAll('.panel').length === 4", timeout=30000)
        page.wait_for_timeout(1500)  # let the async fetch render
        n = page.eval_on_selector_all(".panel", "els => els.length")
        cells = page.eval_on_selector_all(".panel .face3d .st", "els => els.length")
        labels = page.eval_on_selector_all(".plabel", "els => els.map(e => e.textContent)")
        print(f"  panels={n} cells={cells} labels={labels}")
        page.screenshot(path=out, full_page=True)
        print(f"  wrote {out}")

    # wait for models
    for _ in range(80):
        eng = get("/api/engines")["engines"]
        if not any(e["status"] == "loading" for e in eng):
            break
        time.sleep(5)
    print("engines:", [(e["key"], e["status"]) for e in eng])

    rid = None
    for _ in range(60):  # wait out any run still in progress (409)
        try:
            rid = post("/api/run", {"seed": 20261002, "mode": "guided",
                                    "policy": "sample", "moves": 80})["run_id"]
            break
        except urllib.error.HTTPError as e:
            if e.code != 409:
                raise
            print("  server busy, waiting…")
            time.sleep(10)
    print("run:", rid)

    print("mid-run capture after 30s…")
    time.sleep(30)
    mid = get(f"/api/run/{rid}")
    print("  mid:", [(p["key"], p["status"], p["moves"]) for p in mid["panels"]])
    snap(rid, f"{SHOTS}/ui_midrun.png")

    for _ in range(40):
        run = get(f"/api/run/{rid}")
        if run["status"] == "done":
            break
        time.sleep(5)
    print("final:", [(p["key"], p["status"], p["moves"], p.get("final_facelets")) for p in run["panels"]])
    snap(rid, f"{SHOTS}/ui_final.png")

    browser.close()
print("done")
