"""Kociemba solver bridge.

The decision models cannot solve a cube on their own (measured: no net progress
over 24 moves, move-ranking correlation ~0 or negative). So the solver is the
search, and the model is the decision layer inside it.

Two things this module provides:

    solution(cube)        a concrete move list that solves the cube ([] if solved)
    distance(cube)        length of that solution
    optimal_move(cube)    its first move

The tricky part is the encoding bridge. pycuber colours its stickers with
colour names (white/yellow/...) and Kociemba wants a 54-char string of FACE
letters in URFDLB order, each face read row by row from outside. We derive the
colour -> face map from the centres (centres never move) instead of hardcoding,
because pycuber's default cube is not the usual white-up arrangement.

Every state is cached by its facelet string: the race revisits states often
(neutral moves, repeated positions), and Kociemba is the slow part.

DEPENDENCY NOTE: kociemba has no Apple-silicon wheel on PyPI (only a Python 3.7
Intel wheel and an sdist), so it always compiles a small C extension. If that
build failed, guided mode is unavailable but greedy and staged modes still work.
Importing this module therefore never raises; the failure surfaces only when you
actually ask for a solution. See SOLVER_HELP for the fix.

Do NOT swap in pycuber's own CFOPSolver as a fallback: it was tested and returns
solutions that do not solve the cube (55-58 moves applied, still unsolved).
"""

from __future__ import annotations

from functools import lru_cache

from pycuber import Cube

FACES = "URFDLB"

try:  # noqa: SIM105
    import kociemba

    KOCIEMBA_AVAILABLE = True
    KOCIEMBA_ERROR: str | None = None
except Exception as _e:  # noqa: BLE001
    kociemba = None  # type: ignore[assignment]
    KOCIEMBA_AVAILABLE = False
    KOCIEMBA_ERROR = f"{type(_e).__name__}: {_e}"

SOLVER_HELP = (
    "Guided mode needs the `kociemba` package. It has no Apple-silicon wheel, so "
    "pip compiles a small C extension, and that build fails if your Xcode Command "
    "Line Tools are broken (the usual symptom is `ld: ... error: unknown "
    "architecture` on a libSystem.tbd).\n"
    "Fix:\n"
    "  sudo rm -rf /Library/Developer/CommandLineTools\n"
    "  xcode-select --install\n"
    "  uv pip install kociemba\n"
    "Greedy and staged modes run without it."
)


def available() -> bool:
    return KOCIEMBA_AVAILABLE


def solver_name() -> str:
    return "kociemba" if KOCIEMBA_AVAILABLE else "none"


def require_solver() -> None:
    if not KOCIEMBA_AVAILABLE:
        raise RuntimeError(f"kociemba is not available ({KOCIEMBA_ERROR}).\n{SOLVER_HELP}")


def colour_map(cube: Cube) -> dict[str, str]:
    """colour name -> face letter, taken from the fixed centres."""
    return {cube.get_face(f)[1][1].colour: f for f in FACES}


def facelet_string(cube: Cube) -> str:
    """54-char Kociemba facelet string, URFDLB order, row-major from outside."""
    m = colour_map(cube)
    out: list[str] = []
    for f in FACES:
        face = cube.get_face(f)
        for r in range(3):
            for c in range(3):
                out.append(m[face[r][c].colour])
    return "".join(out)


def solved_string() -> str:
    return "".join(f * 9 for f in FACES)


@lru_cache(maxsize=200_000)
def _solve_cached(state: str) -> str:
    return kociemba.solve(state)


def solution(cube: Cube) -> list[str]:
    """A concrete move list from this state to solved ([] when already solved)."""
    s = facelet_string(cube)
    if s == solved_string():
        return []
    require_solver()
    return _solve_cached(s).split()


def distance(cube: Cube) -> int:
    """Length of the solver's solution from this state. 0 means solved."""
    return len(solution(cube))


def optimal_move(cube: Cube) -> str | None:
    """First move of the solver's solution, or None if already solved."""
    sol = solution(cube)
    return sol[0] if sol else None


def is_solved(cube: Cube) -> bool:
    return facelet_string(cube) == solved_string()
