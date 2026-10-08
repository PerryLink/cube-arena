"""The cube race: three engines, one scrambled cube each, same rules.

Two modes:
  greedy : every turn asks for the single move that reduces misplaced stickers
  staged : walks the beginner-method ladder (white cross -> first layer ->
           two layers -> solved), naming the current subgoal each turn

Run:  python arena.py --engines laya,strands --mode greedy --moves 60
      python arena.py --engines laya,strands --mode staged --moves 80
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import time
from typing import Any

from cube import (MOVES, STAGES, apply_move, facelet_rows, scramble,
                  solved_faces, solved_facelets, state_text)
from engines import (ClefEngine, Engine, GlinerEngine, KevEngine, LayaEngine,
                     StrandsEngine, move_question)
from solver import distance, is_solved, optimal_move, solution, solver_name

RESULTS = pathlib.Path(__file__).parent / "results"
RESULTS.mkdir(exist_ok=True)

GREEDY_Q = (
    "Which single move best reduces the number of misplaced stickers, moving the "
    "cube closest to solved? Pick exactly one move."
)


def pick_move(d, policy: str, rng: random.Random) -> str:
    """argmax -> the model's top choice. sample -> draw from its distribution.

    A decision model used in a loop is a policy, not a one-shot classifier, so
    sampling from the returned distribution is the honest way to run it (and it
    is what stops the loop from collapsing onto one repeated move).
    """
    if policy == "sample" and d.probabilities:
        opts = [(m, v) for m, v in d.probabilities.items() if m in MOVES and v > 0]
        if opts:
            total = sum(v for _, v in opts)
            r = rng.random() * total
            acc = 0.0
            for m, v in opts:
                acc += v
                if r <= acc:
                    return m
            return opts[-1][0]
    return d.choice


def build_engines(which: list[str]) -> list[Engine]:
    engines: list[Engine] = []
    if "laya" in which:
        engines.append(LayaEngine())
    if "strands" in which:
        engines.append(StrandsEngine())
    if "gliner" in which:
        engines.append(GlinerEngine())
    if "clef-flash" in which:
        engines.append(ClefEngine("clef-flash"))
    if "clef" in which:
        engines.append(ClefEngine("clef"))
    if "kev" in which:
        engines.append(KevEngine())
    return engines


def _valid(choice: str) -> bool:
    return choice in MOVES


def run_race(engine: Engine, seed: int, mode: str, max_moves: int,
             policy: str = "sample", on_move=None) -> dict[str, Any]:
    cube, seq = scramble(seed)
    rng = random.Random(f"{seed}:{engine.name}:{mode}:{policy}")
    start = {"facelets": solved_facelets(cube), "faces": solved_faces(cube)}
    traj: list[dict[str, Any]] = []
    stage_idx = 0
    invalid = 0

    def _emit(i, stage_name, mv, argmax, applied, d):
        if on_move:
            on_move({
                "i": i, "stage": stage_name, "chosen": mv, "argmax": argmax,
                "applied": applied, "facelets": solved_facelets(cube),
                "faces": solved_faces(cube), "net": facelet_rows(cube),
                "latency_ms": round(d.latency_ms, 2), "confidence": d.confidence,
                "error": d.error,
            })

    for i in range(max_moves):
        if mode == "greedy":
            q = GREEDY_Q
            stage_name = "greedy"
        else:
            stage_name, desc, metric, target = STAGES[min(stage_idx, len(STAGES) - 1)]
            q = f"Which single move best progresses this subgoal: {desc}? Pick exactly one move."

        d = engine.decide(state_text(cube), move_question(q))
        mv = pick_move(d, policy, rng)

        if not _valid(mv):
            invalid += 1
            traj.append({
                "i": i, "stage": stage_name, "chosen": mv, "argmax": d.choice, "applied": None,
                "facelets": solved_facelets(cube), "faces": solved_faces(cube),
                "latency_ms": round(d.latency_ms, 2), "confidence": d.confidence,
                "probabilities": d.probabilities, "error": d.error or "invalid move",
            })
            _emit(i, stage_name, mv, d.choice, None, d)
            continue

        apply_move(cube, mv)
        f, fc = solved_facelets(cube), solved_faces(cube)
        traj.append({
            "i": i, "stage": stage_name, "chosen": mv, "argmax": d.choice, "applied": mv,
            "facelets": f, "faces": fc,
            "latency_ms": round(d.latency_ms, 2), "confidence": d.confidence,
            "probabilities": d.probabilities, "error": d.error,
        })
        _emit(i, stage_name, mv, d.choice, mv, d)

        if mode == "staged":
            _, _, metric_fn, target = STAGES[min(stage_idx, len(STAGES) - 1)]
            if metric_fn(cube) >= target and stage_idx < len(STAGES) - 1:
                stage_idx += 1
        if fc == 6:
            break

    lats = [t["latency_ms"] for t in traj if t.get("applied")]
    return {
        "engine": engine.name,
        "mode": mode,
        "policy": policy,
        "seed": seed,
        "scramble": seq,
        "start": start,
        "moves_made": sum(1 for t in traj if t.get("applied")),
        "invalid": invalid,
        "final_facelets": solved_facelets(cube),
        "final_faces": solved_faces(cube),
        "solved": solved_faces(cube) == 6,
        "latency_ms_median": round(sorted(lats)[len(lats) // 2], 2) if lats else None,
        "latency_ms_mean": round(sum(lats) / len(lats), 2) if lats else None,
        "trajectory": traj,
    }


GUIDED_CAP_EXTRA = 6  # turns a model may waste on neutral moves before the solver forces the finish


def run_guided(engine: Engine, seed: int, policy: str = "sample", on_move=None,
               cap_extra: int = GUIDED_CAP_EXTRA, max_moves: int = 200) -> dict[str, Any]:
    """Solver-guided race: the solver knows the optimal move, the model decides.

    Each turn the model gets the SAME 18-move question as the unaided race, so the
    two are directly comparable. The harness scores the model's pick against the
    solver:

      hit        the model's move strictly reduces the optimal distance
      neutral    same distance (a wasted turn); allowed only early on
      corrected  the model's move would make things worse, so the solver plays its
                 own optimal move instead. Counted honestly as a miss.

    Distance never increases, and after the cap every move must strictly reduce
    it, so the cube is guaranteed to finish.
    """
    cube, seq = scramble(seed)
    rng = random.Random(f"{seed}:{engine.name}:guided:{policy}")
    start = {"facelets": solved_facelets(cube), "faces": solved_faces(cube)}
    # A concrete, known-good solution from here. We follow it, so the cube is
    # guaranteed to finish: whenever the solver overrides, it plays plan[0] and
    # advances the plan; whenever the model's move is honoured, we re-plan from
    # the resulting state. Either way a valid plan always exists.
    plan = solution(cube)
    d0 = len(plan)
    traj: list[dict[str, Any]] = []
    hits = accepted = neutrals = corrections = unusable = 0
    neutral_budget = cap_extra

    def _emit(i, chosen, applied, tag, d):
        if on_move:
            on_move({
                "i": i, "stage": "guided", "chosen": chosen, "argmax": d.choice,
                "applied": applied, "tag": tag, "optimal_distance": d0,
                "solver": solver_name(),
                "facelets": solved_facelets(cube), "faces": solved_faces(cube),
                "net": facelet_rows(cube),
                "latency_ms": round(d.latency_ms, 2), "confidence": d.confidence,
                "error": d.error,
            })

    i = 0
    while not is_solved(cube) and i < max_moves:
        if not plan:
            plan = solution(cube)
            if not plan:
                break
        correct = plan[0]
        d = engine.decide(state_text(cube), move_question(GREEDY_Q))
        mv = pick_move(d, policy, rng)

        play, tag, replan = correct, "corrected", False
        if mv == correct:
            tag, hits = "hit", hits + 1
        elif mv in MOVES:
            probe = cube.copy()
            apply_move(probe, mv)
            d_m = len(solution(probe))
            if d_m < len(plan):
                play, tag, replan = mv, "accepted", True
                accepted += 1
            elif d_m == len(plan) and neutral_budget > 0:
                play, tag, replan = mv, "neutral", True
                neutrals += 1
                neutral_budget -= 1
            else:
                corrections += 1
        else:
            unusable += 1
            corrections += 1

        apply_move(cube, play)
        plan = solution(cube) if replan else plan[1:]
        f, fc = solved_facelets(cube), solved_faces(cube)
        traj.append({
            "i": i, "stage": "guided", "chosen": mv, "argmax": d.choice,
            "applied": play, "tag": tag, "facelets": f, "faces": fc,
            "latency_ms": round(d.latency_ms, 2), "confidence": d.confidence,
            "probabilities": d.probabilities, "error": d.error,
        })
        _emit(i, mv, play, tag, d)
        i += 1
        if fc == 6 or is_solved(cube):
            break

    lats = [t["latency_ms"] for t in traj if t.get("applied")]
    return {
        "engine": engine.name,
        "mode": "guided",
        "policy": policy,
        "seed": seed,
        "scramble": seq,
        "start": start,
        "optimal_distance": d0,
        "solver": solver_name(),
        "moves_made": sum(1 for t in traj if t.get("applied")),
        "hits": hits,
        "accepted": accepted,
        "neutrals": neutrals,
        "corrections": corrections,
        "unusable": unusable,
        "invalid": unusable,
        "final_facelets": solved_facelets(cube),
        "final_faces": solved_faces(cube),
        "solved": is_solved(cube),
        "latency_ms_median": round(sorted(lats)[len(lats) // 2], 2) if lats else None,
        "latency_ms_mean": round(sum(lats) / len(lats), 2) if lats else None,
        "trajectory": traj,
    }


def run(engine: Engine, seed: int, mode: str, max_moves: int,
        policy: str = "sample", on_move=None) -> dict[str, Any]:
    """Dispatch: guided -> solver-guided, anything else -> the unaided race."""
    if mode == "guided":
        return run_guided(engine, seed, policy=policy, on_move=on_move, max_moves=max_moves)
    return run_race(engine, seed, mode, max_moves, policy=policy, on_move=on_move)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="laya,strands,gliner")
    ap.add_argument("--mode", default="greedy", choices=["greedy", "staged", "guided"])
    ap.add_argument("--policy", default="sample", choices=["sample", "argmax"])
    ap.add_argument("--moves", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20261002)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    which = [e.strip() for e in args.engines.split(",") if e.strip()]
    engines = build_engines(which)
    out = []
    for eng in engines:
        print(f"\n=== {eng.name} | {args.mode} | {args.policy} | seed {args.seed} ===", flush=True)
        t0 = time.perf_counter()
        res = run(eng, args.seed, args.mode, args.moves, args.policy)
        res["wall_seconds"] = round(time.perf_counter() - t0, 2)
        out.append(res)
        if args.mode == "guided":
            n = res["moves_made"]
            print(f"  SOLVED: {res['solved']}  {res['final_facelets']}/54 stickers, "
                  f"{n} moves (optimal {res['optimal_distance']}), "
                  f"hits {res['hits']} / neutral {res['neutrals']} / corrected {res['corrections']}, "
                  f"median {res['latency_ms_median']} ms/move, "
                  f"wall {res['wall_seconds']}s", flush=True)
        else:
            print(f"  final: {res['final_facelets']}/54 stickers, "
                  f"{res['final_faces']}/6 faces, {res['moves_made']} moves, "
                  f"median {res['latency_ms_median']} ms/move", flush=True)
        eng.close()

    name = args.out or f"race_{args.mode}_{args.policy}_seed{args.seed}.json"
    path = RESULTS / name
    path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
