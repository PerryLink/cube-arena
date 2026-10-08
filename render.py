"""Render race results: a terminal board, a progress chart, and a summary table.

  python render.py results/race_greedy_seed20261002.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def summary_table(results: list[dict]) -> Table:
    t = Table(title="Cube arena", show_lines=False)
    t.add_column("engine", style="bold")
    t.add_column("mode")
    t.add_column("start /54")
    t.add_column("final /54", justify="right")
    t.add_column("faces /6", justify="right")
    t.add_column("moves", justify="right")
    t.add_column("invalid", justify="right")
    t.add_column("median ms", justify="right")
    for r in results:
        t.add_row(
            r["engine"], r["mode"], str(r["start"]["facelets"]),
            str(r["final_facelets"]), str(r["final_faces"]),
            str(r["moves_made"]), str(r["invalid"]),
            str(r["latency_ms_median"]),
        )
    return t


def progress_chart(results: list[dict], out_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 6))
    for r in results:
        xs, ys = [0], [r["start"]["facelets"]]
        for k, t in enumerate(r["trajectory"]):
            if t.get("applied"):
                xs.append(len(xs))
                ys.append(t["facelets"])
        ax.plot(xs, ys, marker="o", markersize=3, linewidth=2, label=f"{r['engine']} ({r['mode']})")
    ax.axhline(54, color="green", linestyle="--", linewidth=1, label="solved")
    ax.set_xlabel("move number")
    ax.set_ylabel("correct stickers (out of 54)")
    ax.set_title("Rubik's cube race: correct stickers over time")
    ax.set_ylim(0, 56)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    console.print(f"chart -> {out_png}")


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]] or sorted(Path("results").glob("race_*.json"))
    results = []
    for p in paths:
        results.extend(json.loads(p.read_text()))
    console.print(summary_table(results))
    if results:
        progress_chart(results, Path("results") / "progress.png")


if __name__ == "__main__":
    main()
