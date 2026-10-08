#!/usr/bin/env bash
# Start the Kev SystemOne server for the arena's `kev` panel.
#
#   ./run_kev.sh                 # Kev-0.8B on :8008 (the only size that fits 16 GB)
#   KEV_MODEL=jaredpalmer/kev-4b ./run_kev.sh   # needs a 32 GB+ machine
#
# Kev lives in its own checkout + venv (it pins torch<2.9, which conflicts with
# the arena's venv), so this script drives `uv run` inside that checkout instead
# of the cube-arena venv.
#
# One-time setup:
#   git clone https://github.com/jaredpalmer/kev.git ~/experiments/kev
#   cd ~/experiments/kev && uv sync --extra serve
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
KEV_DIR="${KEV_DIR:-$(cd "${HERE}/../kev" 2>/dev/null && pwd || true)}"
PORT_KEV="${PORT_KEV:-8008}"
KEV_MODEL="${KEV_MODEL:-jaredpalmer/kev-0.8b}"

if [ -z "${KEV_DIR}" ] || [ ! -f "${KEV_DIR}/pyproject.toml" ]; then
  echo "No Kev checkout found. Clone it and sync the serve extra first:" >&2
  echo "  git clone https://github.com/jaredpalmer/kev.git ~/experiments/kev" >&2
  echo "  cd ~/experiments/kev && uv sync --extra serve" >&2
  exit 1
fi

if curl -s --max-time 2 "http://127.0.0.1:${PORT_KEV}/v1/models" >/dev/null 2>&1; then
  echo "kev: already running on ${PORT_KEV}"
  exit 0
fi

echo "kev: starting ${KEV_MODEL} on ${PORT_KEV} (first run downloads the base + adapter)"
cd "${KEV_DIR}"
exec uv run --extra serve python -m kev.serve --run "${KEV_MODEL}" --port "${PORT_KEV}"