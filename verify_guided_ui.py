"""Verify the guided mode end-to-end through the UI, including live counters.

Waits for models, starts a guided run on the fast engine, watches the guided
counters tick up DURING the run (not just at the end), then screenshots the
finished run. Run with the Playwright python:

    /opt/anaconda3/bin/python3 verify_guided_ui.py
"""
from __future__ import annotations

import json
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8077"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def post(path: str, body: dict):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main() -> None:
    for _ in range(60):
        eng = get("/api/engines")["engines"]
        if not any(e["status"] == "loading" for e in eng):
            print("engines:", " | ".join(f"{e['key']}={e['status']}" for e in eng))
            break
        time.sleep(3)

    run_id = post("/api/run", {"seed": 20261002, "mode": "guided",
                               "policy": "sample", "moves": 80,
                               "engines": ["laya"]})["run_id"]
    print("run:", run_id)

    saw_live = False
    for _ in range(120):
        d = get(f"/api/run/{run_id}")
        p = d["panels"][0]
        counts = (p["hits"], p["accepted"], p["neutrals"], p["corrections"])
        print(f"  {p['status']:8s} moves={p['moves']:3d} optimal={p['optimal_distance']} "
              f"correct={p['facelets']}/54 hit/accepted/neutral/corrected={counts}")
        if d["status"] == "done":
            break
        if sum(counts) > 0:
            saw_live = True
        time.sleep(1)

    print("live counters ticked during the run:", saw_live)

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1900, "height": 900}, device_scale_factor=2)
        pg.goto(f"{BASE}/?run={run_id}", wait_until="load")
        pg.wait_for_selector(".panel .face3d .st", timeout=30000)
        pg.wait_for_timeout(1500)
        print("chips:", pg.eval_on_selector_all(".panel .chip", "e=>e.map(x=>x.textContent)"))
        pg.screenshot(path="results/ui_guided_laya.png", full_page=True)
        print("wrote results/ui_guided_laya.png")
        b.close()


if __name__ == "__main__":
    main()
