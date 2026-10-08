#!/usr/bin/env bash
# Start the whole Rubik's Cube Decision Arena on this machine.
#
#   ./run.sh              # strands server + UI on the default ports
#   PORT_UI=9000 ./run.sh # override ports
#
# Starts the strands-decider model server (skipped if it is already up), then runs
# the UI in the foreground. Ctrl-C stops the UI; the strands server keeps running
# in the background (see the note it prints).
set -euo pipefail
cd "$(dirname "$0")"

PORT_STRANDS="${PORT_STRANDS:-8010}"
PORT_UI="${PORT_UI:-8077}"
STRANDS_LOG="strands-server.log"

if [ ! -f .venv/bin/activate ]; then
  echo "No .venv found in $(pwd)." >&2
  echo "Create it first:  uv venv --python 3.12 && source .venv/bin/activate" >&2
  echo "                  uv pip install laya-mlx strands-decider gliner2 pycuber rich matplotlib requests httpx" >&2
  echo "                  uv pip install kociemba" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import pycuber" 2>/dev/null; then
  echo "pycuber is missing from the venv. Run the install commands in SETUP.md." >&2
  exit 1
fi

if python -c "import kociemba" 2>/dev/null; then
  echo "solver: kociemba present (guided mode available)"
else
  echo "solver: MISSING -> guided mode will be unavailable; greedy and staged still work."
  echo "        fix: sudo rm -rf /Library/Developer/CommandLineTools && xcode-select --install"
  echo "             uv pip install kociemba"
fi

if curl -s --max-time 2 "http://127.0.0.1:${PORT_STRANDS}/health" >/dev/null 2>&1; then
  echo "strands-decider: already running on ${PORT_STRANDS}"
else
  echo "strands-decider: starting on ${PORT_STRANDS} (first run downloads ~4.5 GB)..."
  strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 \
    --device mps --port "${PORT_STRANDS}" --model-name strands-decider \
    > "${STRANDS_LOG}" 2>&1 &
  echo "  pid $!  logs: ${STRANDS_LOG}"
fi

echo
echo "UI: starting on http://127.0.0.1:${PORT_UI}   (models load in the background)"
echo "    open http://127.0.0.1:${PORT_UI} once it says 'models ready'"
echo
exec python server.py --port "${PORT_UI}"
