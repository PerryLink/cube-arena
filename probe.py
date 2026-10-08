"""Does a decision model's probability distribution carry signal about move quality?

For each state we compute the TRUE change in correct stickers for all 18 moves
(by simulation), then compare the model's probability over moves with that truth.

Metrics per engine, averaged over many states:
  spearman        rank correlation between model probability and true quality
  top1_delta      true quality of the model's highest-probability move
  regret          best available delta minus top1_delta
  argmax_optimal  share of states where the top move is the best move
  argmax_helps    share of states where the top move improves the cube

Run: python probe.py --engines laya,strands --states 25
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import statistics

from cube import MOVES, apply_move, scramble, solved_facelets, state_text
from engines import (ClefEngine, GlinerEngine, KevEngine, LayaEngine, StrandsEngine,
                     move_question)

RESULTS = pathlib.Path(__file__).parent / "results"
RESULTS.mkdir(exist_ok=True)

PROBE_Q = (
    "Which single move best reduces the number of misplaced stickers, moving the "
    "cube closest to solved? Pick exactly one move."
)


def _rank(x: list[float]) -> list[int]:
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0] * len(x)
    for pos, i in enumerate(order):
        r[i] = pos
    return r


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = _rank(a), _rank(b)
    n = len(a)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    den = (sum((ra[i] - ma) ** 2 for i in range(n)) * sum((rb[i] - mb) ** 2 for i in range(n))) ** 0.5
    return num / den if den else 0.0


def build(which: list[str]):
    out = []
    if "laya" in which:
        out.append(LayaEngine())
    if "strands" in which:
        out.append(StrandsEngine())
    if "gliner" in which:
        out.append(GlinerEngine())
    if "clef-flash" in which:
        out.append(ClefEngine("clef-flash"))
    if "clef" in which:
        out.append(ClefEngine("clef"))
    if "kev" in which:
        out.append(KevEngine())
    return out


def probe_engine(engine, n_states: int, seed: int) -> dict:
    rng = random.Random(seed)
    cube, _ = scramble(seed)
    q = move_question(PROBE_Q)
    rows = []
    for k in range(n_states):
        if k > 0:  # random walk so we see many different states
            apply_move(cube, rng.choice(MOVES))
        base = solved_facelets(cube)
        truth = {}
        for m in MOVES:
            cc = cube.copy()
            apply_move(cc, m)
            truth[m] = solved_facelets(cc) - base

        d = engine.decide(state_text(cube), q)
        probs = [d.probabilities.get(m, 0.0) for m in MOVES]
        deltas = [truth[m] for m in MOVES]
        rho = spearman(probs, deltas) if any(probs) else None

        top = max(MOVES, key=lambda m: d.probabilities.get(m, 0.0))
        best_delta = max(deltas)
        rows.append({
            "state": k, "base": base, "argmax": d.choice, "sampled_top": top,
            "top1_delta": truth[top], "best_delta": best_delta,
            "regret": best_delta - truth[top],
            "optimal": truth[top] == best_delta,
            "helps": truth[top] > 0,
            "spearman": rho, "confidence": d.confidence,
            "latency_ms": round(d.latency_ms, 2),
        })

    rhos = [r["spearman"] for r in rows if r["spearman"] is not None]
    return {
        "engine": engine.name,
        "states": n_states,
        "seed": seed,
        "spearman_mean": round(statistics.mean(rhos), 3) if rhos else None,
        "spearman_median": round(statistics.median(rhos), 3) if rhos else None,
        "spearman_min": round(min(rhos), 3) if rhos else None,
        "spearman_max": round(max(rhos), 3) if rhos else None,
        "argmax_optimal_pct": round(100 * sum(r["optimal"] for r in rows) / len(rows), 1),
        "argmax_helps_pct": round(100 * sum(r["helps"] for r in rows) / len(rows), 1),
        "mean_regret": round(statistics.mean(r["regret"] for r in rows), 2),
        "mean_top1_delta": round(statistics.mean(r["top1_delta"] for r in rows), 2),
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="laya,strands")
    ap.add_argument("--states", type=int, default=25)
    ap.add_argument("--seed", type=int, default=20261002)
    ap.add_argument("--out", default="probe.json")
    args = ap.parse_args()

    which = [e.strip() for e in args.engines.split(",") if e.strip()]
    out = []
    for eng in build(which):
        print(f"\n=== probe {eng.name} over {args.states} states ===", flush=True)
        res = probe_engine(eng, args.states, args.seed)
        out.append(res)
        print(f"  spearman(prob,quality): mean {res['spearman_mean']:+.3f} "
              f"median {res['spearman_median']:+.3f} "
              f"[{res['spearman_min']:+.2f}, {res['spearman_max']:+.2f}]", flush=True)
        print(f"  top move optimal {res['argmax_optimal_pct']}% | "
              f"improves cube {res['argmax_helps_pct']}% | mean regret {res['mean_regret']}", flush=True)
        eng.close()

    path = RESULTS / args.out
    path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
