"""Scorecard charts for a finished run.

Renders one dark-themed figure with four panels from a run JSON:
  1. progress   - correct stickers over moves, one line per model
  2. latency    - median ms per move, log scale, one bar per model
  3. guided     - how each model's picks were resolved (hit/accepted/neutral/corrected)
  4. final      - correct stickers at the end, with solved models marked

Used by the UI (`/api/chart/<run_id>`) and by the CLI. Dark palette matches
ui/index.html so the charts drop straight into a video.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

BG = "#0b0d12"
PANEL = "#141821"
LINE = "#262d3d"
TXT = "#e8ecf4"
DIM = "#8b94a7"
ACC = "#5eead4"
GOOD = "#34d399"
WARN = "#fbbf24"
BAD = "#f87171"

# One stable colour per engine key, so a model keeps its colour across charts.
PALETTE = {
    "laya": "#5eead4",
    "strands": "#38bdf8",
    "gliner": "#a78bfa",
    "clef-flash": "#facc15",
    "clef": "#4ade80",
    "kev": "#f472b6",
}
FALLBACK = "#8b94a7"


def colour_for(key: str) -> str:
    return PALETTE.get(key, FALLBACK)


def _style(ax, title: str) -> None:
    ax.set_facecolor(PANEL)
    ax.set_title(title, color=TXT, fontsize=11, pad=8, loc="left")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(LINE)
    ax.tick_params(colors=DIM, labelsize=8.5)
    ax.grid(True, color=LINE, alpha=0.45, linewidth=0.6)
    ax.set_axisbelow(True)


def _label(panel: dict) -> str:
    """Short label for a legend: drop the parameter count noise."""
    return panel.get("label") or panel.get("key", "?")


def build_scorecard(run: dict[str, Any], out_path: pathlib.Path, dpi: int = 150) -> pathlib.Path:
    """Render the four-panel scorecard for one run. Returns the written path."""
    panels = run.get("panels", [])
    live = [p for p in panels if p.get("status") in ("done", "running") and p.get("moves")]

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.2), dpi=dpi)
    fig.patch.set_facecolor(BG)
    ax_prog, ax_lat, ax_guided, ax_final = axes.flat

    mode = run.get("config", {}).get("mode", "?")
    seed = run.get("seed", "?")
    fig.suptitle(
        f"Rubik's Cube Decision Arena   ·   mode {mode}   ·   seed {seed}   ·   "
        f"{len(live)} model{'s' if len(live) != 1 else ''} with data",
        color=TXT, fontsize=13.5, x=0.012, ha="left", y=0.975,
    )

    # ---- 1. progress ---------------------------------------------------- #
    _style(ax_prog, "Progress: correct stickers after each move (of 54)")
    for p in live:
        pts = [m for m in p.get("move_log", []) if m.get("facelets") is not None]
        if not pts:
            continue
        xs = list(range(1, len(pts) + 1))
        ys = [m["facelets"] for m in pts]
        ax_prog.plot(xs, ys, color=colour_for(p["key"]), linewidth=1.9,
                     label=_label(p), alpha=0.95)
    start = run.get("start", {}).get("facelets")
    if start is not None:
        ax_prog.axhline(start, color=DIM, linewidth=1.0, linestyle=(0, (4, 3)))
        ax_prog.annotate(f"start {start}/54", (0.99, start), xycoords=("axes fraction", "data"),
                         color=DIM, fontsize=8, ha="right", va="bottom")
    ax_prog.set_xlabel("move", color=DIM, fontsize=9)
    ax_prog.set_ylabel("stickers correct", color=DIM, fontsize=9)
    ax_prog.set_ylim(0, 58)
    if live:
        ax_prog.legend(facecolor=PANEL, edgecolor=LINE, labelcolor=TXT,
                       fontsize=7.5, loc="upper left", ncol=2, framealpha=0.92)

    # ---- 2. latency ----------------------------------------------------- #
    _style(ax_lat, "Latency per move, median (ms) - log scale")
    lat = [(p, p.get("median_ms")) for p in live if p.get("median_ms")]
    if lat:
        names = [_label(p) for p, _ in lat]
        vals = [v for _, v in lat]
        cols = [colour_for(p["key"]) for p, _ in lat]
        ypos = range(len(lat))
        ax_lat.barh(list(ypos), vals, color=cols, alpha=0.9, height=0.62)
        ax_lat.set_yticks(list(ypos), names, color=DIM, fontsize=8.5)
        ax_lat.invert_yaxis()
        ax_lat.set_xscale("log")
        for y, v in zip(ypos, vals):
            ax_lat.annotate(f"{v:,.0f}", (v, y), xytext=(5, 0), textcoords="offset points",
                            color=TXT, fontsize=8, va="center")
        ax_lat.set_xlabel("median ms per move (log)", color=DIM, fontsize=9)
        # Headroom so the value labels never press against the right spine.
        ax_lat.set_xlim(right=max(vals) * 2.6)
    else:
        ax_lat.text(0.5, 0.5, "no latency data", color=DIM, ha="center", va="center")

    # ---- 3. guided resolution ------------------------------------------- #
    _style(ax_guided, "Guided mode: how each model's picks were resolved")
    guided = [p for p in live if p.get("optimal_distance") is not None]
    if guided:
        keys = [("hits", "model hit", GOOD),
                ("accepted", "accepted", ACC),
                ("neutrals", "neutral (wasted)", WARN),
                ("corrections", "solver corrected", BAD)]
        names = [_label(p) for p in guided]
        ypos = list(range(len(guided)))
        left = [0] * len(guided)
        for field, label, col in keys:
            vals = [p.get(field, 0) or 0 for p in guided]
            ax_guided.barh(ypos, vals, left=left, color=col, alpha=0.92,
                           height=0.62, label=label)
            for y, v, l in zip(ypos, vals, left):
                if v:
                    ax_guided.annotate(str(v), (l + v / 2, y), color="#04211c",
                                       fontsize=8, ha="center", va="center", weight="bold")
            left = [a + b for a, b in zip(left, vals)]
        ax_guided.set_yticks(ypos, names, color=DIM, fontsize=8.5)
        ax_guided.invert_yaxis()
        ax_guided.set_xlabel("moves", color=DIM, fontsize=9)
        # Reserve empty space to the right for the legend, so it can sit inside
        # the axes without covering a bar or colliding with the title.
        ax_guided.set_xlim(right=max(left or [1]) * 2.05)
        ax_guided.legend(facecolor=PANEL, edgecolor=LINE, labelcolor=TXT,
                         fontsize=7.5, ncol=1, loc="center right",
                         framealpha=0.92)
    else:
        ax_guided.text(0.5, 0.5, "guided mode not run\n(no solver data)",
                       color=DIM, ha="center", va="center", fontsize=10)

    # ---- 4. final -------------------------------------------------------- #
    _style(ax_final, "Final: correct stickers (of 54)")
    if live:
        names = [_label(p) for p in live]
        vals = [p.get("facelets", 0) for p in live]
        cols = [GOOD if p.get("solved") else colour_for(p["key"]) for p in live]
        xpos = range(len(live))
        ax_final.bar(list(xpos), vals, color=cols, alpha=0.92, width=0.6)
        ax_final.set_xticks(list(xpos), names, color=DIM, fontsize=8, rotation=18, ha="right")
        ax_final.set_ylim(0, 58)
        for x, (v, p) in enumerate(zip(vals, live)):
            mark = " solved" if p.get("solved") else ""
            ax_final.annotate(f"{v}{mark}", (x, v), xytext=(0, 4), textcoords="offset points",
                              color=TXT, fontsize=8, ha="center")
        if start is not None:
            ax_final.axhline(start, color=DIM, linewidth=1.0, linestyle=(0, (4, 3)))
            ax_final.annotate(f"start {start}/54", (0.99, start),
                              xycoords=("axes fraction", "data"),
                              color=DIM, fontsize=8, ha="right", va="bottom")
        ax_final.set_ylabel("stickers correct", color=DIM, fontsize=9)

    # ---- footer ---------------------------------------------------------- #
    notes = []
    if any(p.get("generative") for p in panels):
        notes.append("grey = generative model, not a like-for-like decision model")
    unavailable = [p for p in panels if p.get("status") == "unavailable"]
    if unavailable:
        notes.append("no data: " + ", ".join(p.get("label", p["key"]) for p in unavailable))
    if notes:
        fig.text(0.012, 0.012, "  ·  ".join(notes), color=DIM, fontsize=8.5, ha="left")

    fig.tight_layout(rect=(0, 0.028, 1, 0.955))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=BG)
    plt.close(fig)
    return out_path


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Render the scorecard chart for a run JSON.")
    ap.add_argument("run_json", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    run = json.loads(args.run_json.read_text())
    out = args.out or args.run_json.with_name(args.run_json.stem + "_chart.png")
    path = build_scorecard(run, out)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()