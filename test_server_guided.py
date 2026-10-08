"""Exercise server.py's own guided code path with one fast engine.

The UI server reloads all models on restart (~50 s), so this validates the
_one_engine path cheaply before paying that cost.

Run: python test_server_guided.py
"""
from __future__ import annotations

import time

import server
from cube import facelet_rows, scramble, solved_facelets, solved_faces


def make_panel(cube) -> dict:
    return {
        "key": "laya", "label": "Laya", "runtime": "laya-mlx",
        "status": "ready", "error": None,
        "moves": 0,
        "facelets": solved_facelets(cube), "faces": solved_faces(cube),
        "start_facelets": solved_facelets(cube), "start_faces": solved_faces(cube),
        "median_ms": None, "net": facelet_rows(cube), "move_log": [], "solved": False,
        "last_confidence": None, "last_latency": None,
        "hits": 0, "accepted": 0, "neutrals": 0, "corrections": 0,
        "optimal_distance": None,
    }


def main() -> None:
    hub = server.Hub()
    hub.engines["laya"].update(status="ready", engine=server.LayaEngine())

    cube, seq = scramble(20261002)
    panel = make_panel(cube)
    run = {
        "id": "t", "status": "running",
        "config": {"seed": 20261002, "mode": "guided", "policy": "sample",
                   "moves": 80, "engines": ["laya"]},
        "seed": 20261002, "scramble": seq, "panels": [panel],
    }

    t0 = time.perf_counter()
    hub._one_engine(run, panel)
    wall = time.perf_counter() - t0

    print(f"status        : {panel['status']}")
    print(f"solved        : {panel['solved']}")
    print(f"moves         : {panel['moves']}  (optimal {panel['optimal_distance']})")
    print(f"hits          : {panel['hits']}")
    print(f"accepted      : {panel['accepted']}")
    print(f"neutral       : {panel['neutrals']}")
    print(f"solver correct: {panel['corrections']}")
    print(f"median ms     : {panel['median_ms']}")
    print(f"wall          : {wall:.1f}s")
    print(f"error         : {(panel['error'] or 'none')[:400]}")
    assert panel["status"] == "done", panel["status"]
    assert panel["solved"] is True, "cube did not solve"
    print("\nPASS: server guided path solves the cube")


if __name__ == "__main__":
    main()
