# SETUP: running the Rubik's Cube Decision Arena end to end

Everything you need to go from a fresh machine to the six-section UI solving
cubes. Follow it in order; each step ends with a check so you know it worked
before moving on.

> **Already set up on this machine?** You are not on a fresh machine, so skip
> straight to step 5 (or just run `./run.sh`, see "One command instead of two"
> below). Nothing needs reinstalling, and the venv here already has `kociemba`.

---

## 0. What the machine needs

| Requirement | Why |
|---|---|
| macOS on Apple silicon (M1/M2/M3/M4) | `laya-mlx` is MLX, Apple-only. The rest would run elsewhere, but the arena is built and tested on Apple silicon. |
| Python **3.12** | All four model packages support it. |
| ~10 GB free disk | torch + transformers, the strands base model (~4.5 GB), laya, GLiNER2.5-Decide, and the venv. 500 GB is far more than enough. |
| **16 GB RAM** (8 GB works, 16 GB is comfortable) | The three local models plus the strands server held in memory at once. 16 GB also leaves room for a quantized Kev-9B. |
| Internet on first run | Model weights download from Hugging Face once, then cache locally. |

You do **not** need a GPU, CUDA, Docker, or a paid account for four of the six
panels. Only the Clef panels (cloud) need a token, and Kev only needs its own
local server.

> **Target machine note (M1 Pro, 16 GB):** the M1 Pro has roughly twice the memory
> bandwidth of the M2 and more GPU cores, so the local models run noticeably
> faster than the timings quoted below. 16 GB also makes a 4-bit Kev-9B viable,
> which it was not on 8 GB.

---

## 1. Install the system prerequisites

### Python 3.12

Check first:

```bash
python3.12 --version
```

If that fails, install it:

```bash
brew install python@3.12
```

### uv (the package installer used here)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then confirm, using the full path if your shell has not picked it up yet:

```bash
uv --version || ~/.local/bin/uv --version
```

> Note: `uv` lands in `~/.local/bin`. If a background shell says
> `command not found: uv`, use the full path. Same trap applies to any script.

---

## 2. Get the project onto the new machine

Copy the whole project directory. It is small (a few hundred KB of code plus
results); the model weights are **not** in it and will re-download.

From the old machine:

```bash
# either tar it up
cd ~ && tar czf cube-arena.tgz cube-arena
# or copy directly
rsync -av ~/cube-arena/ newmachine:~/cube-arena/
```

On the new machine, put it at `~/cube-arena` and go there:

```bash
cd ~/cube-arena && ls
```

You should see: `cube.py`, `engines.py`, `arena.py`, `solver.py`, `server.py`,
`probe.py`, `render.py`, `README.md`, `SETUP.md`, and a `ui/` directory.

> Do **not** copy the old `.venv` directory. It contains absolute paths and
> architecture-specific binaries. Step 3 builds a fresh one.

---

## 3. Create the environment and install the packages

```bash
cd ~/cube-arena
uv venv --python 3.12
source .venv/bin/activate

# 3a. everything except the solver. This always installs.
uv pip install laya-mlx strands-decider gliner2 pycuber rich matplotlib requests httpx

# 3b. the solver. Needed only for guided mode.
uv pip install kociemba
```

> **Keep `kociemba` in its own command.** It has no Apple-silicon wheel on PyPI,
> so pip has to compile a small C extension. If that compile fails, `uv pip
> install` aborts the **entire** command, so a solver problem would take
> `pycuber` and the rest down with it (symptom: `ModuleNotFoundError: No module
> named 'pycuber'` later). Installing it separately means the solver cannot break
> the rest. If step 3b fails, see the first troubleshooting row.

`kociemba` is the one fragile step. Without it, `greedy` and `staged` modes still
work; only `guided` (the mode that solves the cube) is unavailable, and it says
so clearly instead of crashing.

This installs (versions this project was built and verified against):

| Package | Version | What it is |
|---|---|---|
| `laya-mlx` | 0.2.0 | Laya decision model, MLX native (Apple silicon) |
| `strands-decider` | 0.1.0 | Strands Decider, serves an HTTP `/v1/systemone` endpoint |
| `gliner2` | 2.0.0 | Fastino GLiNER2.5-Decide, the open-weight decision model |
| `pycuber` | 0.2.2 | 3x3 cube simulation (the board) |
| `kociemba` | 1.2.1 | The solver that actually solves the cube in guided mode |
| `torch` | 2.14.1 | pulled in by strands-decider |
| `mlx` | 0.32.3 | pulled in by laya-mlx |
| `transformers` | 5.18.0 | pulled in by gliner2 / strands-decider |
| `rich`, `matplotlib` | 15.0.0, 3.11.2 | terminal table + progress chart |
| `requests`, `httpx` | 2.34.2, 0.28.1 | HTTP clients |

Verify the core imports:

```bash
python -c "import pycuber, kociemba, httpx; print('core ok')"
python -c "import laya_mlx; print('laya ok')"
python -c "from gliner2 import AutoExtractor; print('gliner2 ok')"
```

> `laya_mlx` and `gliner2` are only imported lazily, so an import error here is a
> real install problem; fix it now rather than mid-demo.

---

## 4. Add your keys (the only place keys go)

Copy the template and fill it in:

```bash
cd ~/cube-arena
cp .env.example .env
```

Now edit `~/cube-arena/.env`:

```
CLOUDFLARE_ACCOUNT_ID=your_account_id            # Clef + Clef-Flash panels
CLOUDFLARE_AUTH_TOKEN=your_workers_ai_token      #   scope: Workers AI: Read
```

Every key here is optional. Rules the app
follows:

- The file lives at `~/cube-arena/.env` (same directory as `server.py`).
- A real environment variable of the same name **always wins** over the file, so
  `export CLOUDFLARE_AUTH_TOKEN=...` also works if you prefer.
- If a key is empty or missing, that panel shows `unavailable` with the reason and
  the race runs without it. The app never invents a result for a model it cannot
  reach.
- The Cloudflare pair only powers the two Clef panels. They are hosted on Workers
  AI, so they need no download and no local RAM, which is the only reason a 9B and
  a 27B model are reachable from an 8 GB machine at all. Billed per token ($0.24/M
  for Clef, $0.09/M for Clef-Flash).
- Kev needs no key. It needs its own local server, see step 5b.

Optional extras in the same file:

| Key | Default | Purpose |
|---|---|---|
| `HF_TOKEN` | unset | Speeds up the first-time model downloads and lifts the anonymous rate limit |

Check it is being read:

```bash
source .venv/bin/activate
python -c "import engines, os; print('cloudflare key seen:', bool(os.environ.get('CLOUDFLARE_AUTH_TOKEN')))"
# cloudflare key seen: True   (or False if you left it blank, which is fine)
```

---

## 5. Start the strands-decider server (terminal 1)

Strands Decider is served over HTTP, so it runs as its own long-lived process.
**Start it before the UI**, otherwise the strands section shows `unavailable`.

```bash
cd ~/cube-arena
source .venv/bin/activate
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 \
  --device mps --port 8010 --model-name strands-decider
```

First run downloads the base model (~4.5 GB) and takes a while. Leave it running.

Check it in a second terminal:

```bash
curl -s http://127.0.0.1:8010/health
# {"status":"ok","model":"strands-decider","device":"mps",...}
```

> Keep this terminal open for the whole session. Closing it kills section 2.

---

## 5b. Start the Kev server (section 6, optional)

Kev serves its own SystemOne endpoint, so it needs its own process. It is only
needed for the `kev` panel.

On a 16 GB machine run **Kev-0.8B**: the 4B and 9B checkpoints want ~32 GB for
bf16, and `kev.serve` has no built-in quantization knob (the MLX path loads the
stored bf16 weights). The arena labels the panel `Kev-0.8B` to match. Kev needs
its own checkout + venv because it pins `torch<2.9`, which conflicts with the
arena's venv.

```bash
# one-time
git clone https://github.com/jaredpalmer/kev.git ~/experiments/kev
cd ~/experiments/kev && uv sync --extra serve

# every run (from the arena, this also handles the already-running case)
./run_kev.sh
# or directly:
cd ~/experiments/kev && uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.8b --port 8008
```

Check it:

```bash
curl -s http://127.0.0.1:8008/v1/models
```

Without it, that panel reads `unavailable: no server at 127.0.0.1:8008`, which is
the honest answer rather than a silent zero. **This panel is entirely optional**:
the other five run without it.

---

## 6. Start the arena UI (terminal 2)

```bash
cd ~/cube-arena
source .venv/bin/activate
python server.py                # serves http://127.0.0.1:8077
# python server.py --port 9000  # or another port if 8077 is taken
```

On startup it loads the models in the background. The page shows
`loading models…` per section. Timings to expect:

| Model | First ever load | Warm load |
|---|---|---|
| laya-mlx | ~5 s | ~3 s |
| strands-decider | instant (it is the other terminal) | instant |
| GLiNER2.5-Decide | 4 to 5 min | ~40 s |

Measured on an M2 Mac mini with 8 GB. On an M1 Pro with 16 GB expect the local
loads to be faster: the download is the slow part, not the load.

Check readiness from the terminal:

```bash
curl -s http://127.0.0.1:8077/api/engines
# {"engines":[{"key":"laya","status":"ready",...}, ...]}
```

Then open **http://127.0.0.1:8077** in a browser.

Expected: **six sections, two per row**, each with a rotating 3D cube. When at
least one says `ready`, **Start race** enables. Panels that cannot run show
`unavailable` with the reason. When a run finishes, a **Scorecard** chart appears
under the panels (progress, latency, guided resolution, final score).

---

## 6b. One command instead of two

`run.sh` starts both processes for you. It checks the install, reports whether
the solver is present, starts the strands server if it is not already up, then
runs the UI in the foreground.

```bash
cd ~/cube-arena
./run.sh                # strands server + UI on the default ports
PORT_UI=9000 ./run.sh   # override a port
```

Expected output:

```
solver: kociemba present (guided mode available)
strands-decider: starting on 8010 (first run downloads ~4.5 GB)...
  pid 2544  logs: strands-server.log

UI: starting on http://127.0.0.1:8077   (models load in the background)
    open http://127.0.0.1:8077 once it says 'models ready'
```

If `kociemba` is missing it says so and warns that only `guided` will be
unavailable, instead of failing. Ctrl-C stops the UI; the strands server keeps
running in the background (stop it with `pkill -f strands-decider`).

---

## 7. Use it

Controls at the top:

| Control | Values | Meaning |
|---|---|---|
| **seed** | any integer | Fixes the scramble. Same seed, same starting cube for every model. |
| **mode** | `guided` | **Default. The cube actually gets solved.** A Kociemba solver holds the optimal move; the model picks; if its pick is worse, the solver plays the optimal move and the turn is logged `corrected`. |
| | `greedy` | Unaided. "Which single move helps most?" No plan, no lookahead. Nobody solves it. |
| | `staged` | Unaided, but handed a beginner-method subgoal each turn (white cross, first layer, two layers, solve). |
| **policy** | `sample` | Draw the move from the model's own distribution. The honest way to run a decision model in a loop. |
| | `argmax` | Always take the top choice. Demonstrates the collapse: the model repeats one move forever. |
| **moves** | integer | Move cap per model. GLiNER2.5-Decide is slowest (~3 s/move solo), so it sets the pace. |

Press **Start race**. All ready models run **in parallel**, each in its own
section, cubes updating live.

What you should see in `guided` mode (seed 20261002, optimal 22 moves):

| Section | Result |
|---|---|
| Laya 421M | **solved**, 28 moves, ~5 s |
| Strands Decider 2B | **solved**, 28 moves, ~64 s |
| GLiNER2.5-Decide 340M | **solved**, 27 moves, ~95 s |

Each guided section also shows `optimal`, `model hit`, `accepted`, `neutral`, and
`solver corrected`. Expect the solver to override most turns: these models almost
never pick the solver's move, which is the point of the demo.

---

## 8. Run it without the UI (optional)

The same harness drives headless runs that write JSON into `results/`:

```bash
cd ~/cube-arena && source .venv/bin/activate

# Solver-guided: the cube gets solved
python arena.py --engines laya,strands,gliner --mode guided --policy sample --moves 80

# The unaided baseline (nobody solves it)
python arena.py --engines laya,strands,gliner --mode greedy --policy sample --moves 24

# Does the model's probability rank moves by true quality?
python probe.py --engines laya,strands --states 25

# Terminal summary table + results/progress.png chart
python render.py
```

---

## 9. Screenshots for the video (optional)

The agent browser tool refuses localhost by design, so use headless Chromium
through Playwright. Playwright does not need to be in the project venv:

```bash
# any python that has playwright installed
/opt/anaconda3/bin/python3 -c "import playwright; print('ok')"
# if missing:  pip install playwright && playwright install chromium
```

Then, with the UI server running:

```bash
cd ~/cube-arena
/opt/anaconda3/bin/python3 capture_pw.py     # starts a guided race, shoots mid-run + final
```

Or screenshot an existing run without re-racing:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --window-size=1920,1300 --screenshot=shot.png "http://127.0.0.1:8077/?run=<run_id>"
```

---

## 10. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Failed to build kociemba` with `ld: ... error: unknown architecture` on `libSystem.tbd` | Your Xcode Command Line Tools are broken (the SDK's `libSystem.tbd` lists an architecture the linker does not know). This is a machine problem, not a project problem. Fix, then retry step 3b:<br>`sudo rm -rf /Library/Developer/CommandLineTools`<br>`xcode-select --install`<br>`uv pip install kociemba`<br>Check with `xcode-select -p` first; if it points somewhere odd, the reinstall fixes it. |
| `ModuleNotFoundError: No module named 'pycuber'` | An earlier `uv pip install` aborted part-way (usually the kociemba build). Re-run step 3a, which installs pycuber and the rest. |
| `kociemba is not available` shown in the guided panel | The solver is missing. Greedy and staged modes work fine. Fix the CLT (row above) and install kociemba, then restart `server.py`. |
| `command not found: uv` | `uv` is not on that shell's PATH. Use `~/.local/bin/uv` or activate the venv first. |
| strands section `unavailable` | The strands-decider server (step 5) is not running. Start it and reload the page. |
| clef sections `unavailable` | No `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_AUTH_TOKEN`. Check `~/cube-arena/.env` and restart `server.py`. |
| clef sections `error` on the first move | The token is present but rejected. Check its scope is "Workers AI: Read" and it has not expired. |
| kev section `unavailable` | No server on `:8008`. Start `kev.serve` (step 5b), or ignore it. |
| First `Start race` feels stuck | GLiNER2.5-Decide takes ~3 s per move and loads for ~40 s warm. Lower **moves** or run fewer models. |
| All sections error instantly | A code/import problem, not a model problem. Run `python test_server_guided.py` to isolate it. |
| `422 Unprocessable Entity` from strands | `choice.criteria` must be a **dict** `{option: description}`, not a list. `engines.py` already does this. |
| `AttributeError: 'Cube' object has no attribute 'faces'` | pycuber uses `cube.get_face("U")`, not `cube.faces`. |
| `deepcopy` fails on the cube | Use `cube.copy()` (pycuber's own), not `copy.deepcopy`. |
| laya prints a temperature-clamping `RuntimeWarning` | Expected. Its `choice:11+` bucket ships an out-of-range temperature, clamped at load. Treat its confidence as uncalibrated. |
| Sticker count dips mid-solve in guided mode | Expected. The solver optimises move count, not stickers. Judge a guided run by `solved`. |

---

## 11. The whole thing, one block

For a machine that already has `uv` and Python 3.12:

```bash
# 1. project
cd ~/cube-arena

# 2. environment
uv venv --python 3.12
source .venv/bin/activate
uv pip install laya-mlx strands-decider gliner2 pycuber rich matplotlib requests httpx
uv pip install kociemba     # separate: compiles a C extension, may need the CLT fix

# 3. keys
cp .env.example .env
# then edit .env: CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_AUTH_TOKEN (for the Clef panels)

# 4. terminal 1: the strands server
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 \
  --device mps --port 8010 --model-name strands-decider

# 5. terminal 2: the UI
cd ~/cube-arena && source .venv/bin/activate
python server.py
# open http://127.0.0.1:8077
```

---

## 12. Final checklist

- [ ] `python3.12 --version` prints 3.12.x
- [ ] `uv --version` works
- [ ] `~/cube-arena` copied over, no `.venv` from the old machine
- [ ] fresh `.venv` created and the packages installed (pycuber and the rest first, `kociemba` separately)
- [ ] `python -c "import kociemba"` succeeds (needed for guided mode; greedy and staged work without it)
- [ ] `~/cube-arena/.env` exists, with whichever keys you have (all blank is fine)
- [ ] `curl http://127.0.0.1:8010/health` returns `{"status":"ok",...}`
- [ ] `curl http://127.0.0.1:8077/api/engines` shows `ready` for the models you want
- [ ] the page shows six sections, two per row, with 3D cubes
- [ ] a finished run shows the Scorecard chart under the panels
- [ ] a `guided` run ends with the green `solved` badge
