# Rubik's Cube Race: three System-One decision models

Can a *decision model* solve a Rubik's cube? We gave each model the same
scrambled cube and let it pick one move per turn, then measured the truth.

## Setup

- **Same cube for everyone.** Scramble seed `20261002`, 25 random quarter/half turns.
  Start state: **13 of 54 stickers correct, 0 of 6 faces complete.**
- **Same question every turn.** One `choice` call over the 18 legal moves:
  *"Which single move best reduces the number of misplaced stickers?"*
  (`choice` with `criteria` = {move: description}, the shape strands-decider requires.)
- **Engines**
  | engine | where it runs | how it is called | warm latency / call |
  |---|---|---|---|
  | `laya-mlx` (Laya 421M, MLX) | local, Apple silicon | in-process `agent.predict` | **~101 ms** |
  | `strands-decider` (2B, torch/MPS) | local, HTTP | `POST /v1/systemone` | **~1.27 s** |
  | `gliner2.5-decide` (340M, DeBERTa-v3) | local, CPU | in-process `classify_text` | **~3.10 s** |
- **Two metrics.** Correct stickers (0–54, smooth) and complete faces (0–6, chunky).

## Finding 0: after 24 moves, all three land exactly where they started

| engine | moves | start /54 | final /54 | faces /6 | median ms/move |
|---|---|---|---|---|---|
| laya-mlx | 24 | 13 | **13** | 0 | 101.2 |
| strands-decider | 24 | 13 | **13** | 0 | 1270.6 |
| gliner2.5-decide | 24 | 13 | **13** | 0 | 3101.3 |

Three different architectures, three different latencies, the same non-result:
**zero net progress in 24 moves each, and not one face completed.**

## Finding 1: neither local model makes net progress

Argmax on a decision model collapses to one repeated move (strands kept picking
`R`, laya kept picking `U`), so the loop was run as a **stochastic policy**:
draw the move from the model's own distribution.

| engine | mode | moves | start /54 | final /54 | faces /6 | median ms/move |
|---|---|---|---|---|---|---|
| laya-mlx | greedy (argmax) | 12 | 13 | 10 | 0 | 101.9 |
| strands-decider | greedy (argmax) | 12 | 13 | 13 | 0 | 1264.2 |
| laya-mlx | greedy (sample) | 30 | 13 | 16 | 0 | 101.3 |
| strands-decider | greedy (sample) | 30 | 13 | 10 | 0 | 1269.5 |
| laya-mlx | staged (sample) | 60 | 13 | **17** | 0 | 116.7 |
| strands-decider | staged (sample) | 60 | 13 | **13** | 0 | 1279.6 |

After 60 moves of staged, subgoal-named play, the best result is **17/54** — and
the other engine is exactly back where it started. **Nobody solves it. No face is
ever completed.**

## Finding 2: the probability ranking carries no usable signal

Across 25 different states we computed the *true* change in correct stickers for
all 18 moves (by simulation) and compared it with the model's probability over
moves. Spearman rank correlation between probability and true move quality:

| engine | spearman (mean) | median | range | top move optimal | top move helps | mean regret |
|---|---|---|---|---|---|---|
| laya-mlx | **−0.183** | −0.146 | [−0.70, +0.35] | 20.0% | 40.0% | 3.56 |
| strands-decider | **−0.040** | −0.013 | [−0.56, +0.25] | 16.0% | 52.0% | 3.20 |

Chance baselines over the same states:

- random-move expected delta: **−0.18** stickers
- chance of picking an *optimal* move (tie-aware): **8.9%**
- chance of picking a move that *helps*: **34.4%**

So both models pick a helping move somewhat more often than chance (40% and 52%
vs 34.4%) and find an optimal move about 2× as often as chance (20% and 16% vs
8.9%). But the **ordering** of their probabilities is not usable: the rank
correlation is zero-to-negative. strands-decider is, if anything,
*anti*-correlated on some states (ρ = −0.56). And the mean regret is ~3.2–3.6
stickers: the model's single best move is usually several stickers short of the
move that was actually available.

## Finding 3: staging does not rescue it

Naming the beginner-method subgoal each turn (white cross → first layer → two
layers → solved) produced **no** improvement over the plain "reduce misplaced
stickers" prompt. A system-one model cannot act on a subgoal it cannot search
toward.

## Caveats (read these before quoting the numbers)

- **laya-mlx emits a calibration warning**: its `choice:11+` bucket ships a
  temperature of 0.1006, clamped to 0.5 at load. Confidence from that bucket is
  explicitly *uncalibrated*. Treat laya's confidence values with caution.
- **strands-decider's own response reported `latency_ms: 18690` on the first
  call** (cold compile). Warm wall-clock is ~1.27 s; the figures above use
  measured wall-clock, not the server's self-report.
- **n = 25 states, one scramble seed.** Enough to separate "no signal" from
  "strong signal", not enough to make fine-grained claims between the two models.
- **"Optimal" is tie-inflated**: when several moves share the best delta, a
  random pick hits one 8.9% of the time, not 5.6%.

## What this actually shows

These are **system-one** models: fast, calibrated, closed-set judgments *inside* a
workflow (route this, gate this, score this). A Rubik's cube is a **system-two**
problem: it needs lookahead and search. A greedy decision model has no way to see
that a locally-neutral move sets up a good one three turns later, and the data
says so plainly. The interesting result is not "which model wins" — it is that
*confident, well-calibrated judgment about the current state is not the same thing
as planning*, and you can measure the gap.

## Reproduce

```bash
cd ~/cube-arena && source .venv/bin/activate
python arena.py --engines laya,strands --mode greedy --policy sample --moves 30
python arena.py --engines laya,strands --mode staged --policy sample --moves 60
python probe.py --engines laya,strands --states 25
python render.py            # summary table + results/progress.png
```

---

# Expansion: six models

Four more models were requested (clef, clef-flash, diffusiongemma-26B-A4B-it,
kev-9b). All four repositories exist and were verified; the constraint here is
hardware, not availability. This machine is an **Apple M2 Mac mini with 8 GB
RAM**, which decides what can run locally.

| model | what it is | local on 8 GB? | how it is reached |
|---|---|---|---|
| `Cloudflare/clef` | 27B multimodal **decision** model, SystemOne-compatible | **no** (~54 GB bf16, ~14 GB 4-bit) | Workers AI `@cf/cloudflare/clef` |
| `Cloudflare/clef-flash` | 9B multimodal **decision** model, SystemOne-compatible | marginal (~18 GB bf16, ~5 GB 4-bit) | Workers AI `@cf/cloudflare/clef-flash` |
| `jaredpalmer/kev-9b` | 9B **decision** model (LoRA r=16 + pointer head on Qwen3.5-9B-Base) | marginal; card says ~32 GB for bf16, "slow on MPS" | local `kev.serve` on `:8008` |

Two of the four are cloud-callable with **no local RAM at all**, because Clef and
Clef-Flash speak the same SystemOne contract as everything else here. Those two
are the real additions.

**Dropped at the user's request:** Jev (cloud, needed a paid key) and
DiffusionGemma (25.2B, needs a GPU box). Both adapters were deleted from the code,
not just hidden from the UI. For the record, DiffusionGemma can be served as a
Jev-style decision model via `openjev` or vLLM structured reads on `:8011`, but
not on 8 GB.

## What was implemented

- `ClefEngine` (Workers AI, both sizes) and `KevEngine` (local server) are
  drop-in `HttpEngine` subclasses: both contracts already match.
- All six engines register in one list. A model that cannot run shows
  `unavailable` with the exact reason instead of failing silently.
- A reachability probe was added, so a local server that is down (Kev, strands)
  reads as unavailable rather than falsely "ready".

## Measured state on this machine

| panel | status | reason shown in the UI |
|---|---|---|
| Laya 421M | ready | - |
| Strands Decider 2B | ready | - |
| GLiNER2.5-Decide 340M | ready | - |
| Clef-Flash 9B | unavailable | needs `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_AUTH_TOKEN` |
| Clef 27B | unavailable | same |
| Kev-9B | unavailable | `no server at http://127.0.0.1:8008/v1/models` |

A guided run with the six panels in place: the three ready models all solved 54/54
(Laya 28 moves, Strands 28, GLiNER 27, solver plan 22). The other three panels
stayed `unavailable` and contributed no numbers, which is the point of showing
them rather than hiding them.

## To light the new panels up

- **Clef + Clef-Flash**: add `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_AUTH_TOKEN`
  (scope *Workers AI: Read*) to `.env`. No download, no RAM. Billed per token
  ($0.24/M for Clef, $0.09/M for Clef-Flash).
- **Kev-9B**: run `uv run --extra serve python -m kev.serve --run jaredpalmer/kev-9b --port 8008`
  on a machine with ~32 GB. On 8 GB, use a smaller Kev variant (the family ships
  0.5B and 4B, and 0.5B is documented as running on a MacBook Pro).

## Charts

`charts.py` renders a four-panel dark scorecard from any run JSON: progress per
move, median latency (log scale), how each guided pick was resolved, and the
final score. Served at `/api/chart/<run_id>` and shown automatically under the
panels once a run finishes.
