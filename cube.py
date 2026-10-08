"""3x3 cube simulation + metrics, built on pycuber.

Everything here is deterministic given a scramble seed, so all engines face the
identical cube. Two metrics:

  solved_facelets(cube) -> 0..54   smooth progress line
  solved_faces(cube)    -> 0..6    chunky milestones

A sticker counts as correct when it matches its own face's centre sticker
(centres never move, so the centre is the face's solved colour).
"""

from __future__ import annotations

import random

from pycuber import Cube

FACES = "URFDLB"
MOVES = [f + s for f in FACES for s in ("", "'", "2")]  # 18 quarter/half turns


def solved_cube() -> Cube:
    return Cube()


def scramble(seed: int, n: int = 25) -> tuple[Cube, list[str]]:
    """Return a scrambled cube and the move list that produced it."""
    rng = random.Random(seed)
    seq: list[str] = []
    prev_face = None
    while len(seq) < n:
        mv = rng.choice(MOVES)
        if mv[0] == prev_face:  # avoid trivial same-face repeats
            continue
        prev_face = mv[0]
        seq.append(mv)
    c = Cube()
    for mv in seq:
        c.perform_algo(mv)
    return c, seq


def apply_move(cube: Cube, move: str) -> Cube:
    cube.perform_algo(move)
    return cube


def _face(cube: Cube, f: str):
    return cube.get_face(f)


def centre_colour(cube: Cube, f: str) -> str:
    return _face(cube, f)[1][1].colour


def solved_facelets(cube: Cube) -> int:
    n = 0
    for f in FACES:
        ctr = centre_colour(cube, f)
        face = _face(cube, f)
        for r in range(3):
            for c in range(3):
                if face[r][c].colour == ctr:
                    n += 1
    return n


def solved_faces(cube: Cube) -> int:
    n = 0
    for f in FACES:
        ctr = centre_colour(cube, f)
        face = _face(cube, f)
        if all(face[r][c].colour == ctr for r in range(3) for c in range(3)):
            n += 1
    return n


def facelet_rows(cube: Cube) -> dict[str, str]:
    """One 9-char colour string per face, row-major, seen from outside."""
    out = {}
    for f in FACES:
        face = _face(cube, f)
        out[f] = "".join(face[r][c].colour[0].upper() for r in range(3) for c in range(3))
    return out


def state_text(cube: Cube) -> str:
    """Compact state description handed to the model on every turn."""
    rows = facelet_rows(cube)
    body = "\n".join(f"{f}: {rows[f]}" for f in FACES)
    return (
        "3x3 Rubik's cube. Faces U R F D L B, each 9 stickers read row by row "
        "seen from outside. Letters are sticker colours (W Y G B R O). A face is "
        "solved when all 9 stickers match its fixed centre sticker.\n"
        f"{body}\n"
        f"Correct stickers: {solved_facelets(cube)}/54. "
        f"Complete faces: {solved_faces(cube)}/6."
    )


# ---- staged (beginner-method) subgoal metrics ------------------------------- #

def _u_edges(cube: Cube) -> int:
    """How many of the 4 U-face edge stickers match the U centre (0..4)."""
    ctr = centre_colour(cube, "U")
    face = _face(cube, "U")
    return sum(1 for (r, c) in ((0, 1), (1, 0), (1, 2), (2, 1)) if face[r][c].colour == ctr)


def _side_top_centres(cube: Cube) -> int:
    """How many side top-centre stickers match their own centre (0..4)."""
    return sum(1 for f in "RFLB" if _face(cube, f)[0][1].colour == centre_colour(cube, f))


def _u_all(cube: Cube) -> int:
    ctr = centre_colour(cube, "U")
    face = _face(cube, "U")
    return sum(1 for r in range(3) for c in range(3) if face[r][c].colour == ctr)


def _side_rows(cube: Cube, rows: int) -> int:
    """Matching stickers in the top `rows` rows of each side face (0..rows*12)."""
    n = 0
    for f in "RFLB":
        ctr = centre_colour(cube, f)
        face = _face(cube, f)
        for r in range(rows):
            for c in range(3):
                if face[r][c].colour == ctr:
                    n += 1
    return n


def white_cross(cube: Cube) -> int:
    return _u_edges(cube) + _side_top_centres(cube)          # target 8


def first_layer(cube: Cube) -> int:
    return _u_all(cube) + _side_rows(cube, 1)                # target 21


def two_layers(cube: Cube) -> int:
    return _u_all(cube) + _side_rows(cube, 2)                # target 33


# Ordered stages: (name, description used in the question, metric, target)
STAGES = [
    (
        "white_cross",
        "make a white cross on the U face: all four U-face edge stickers correct "
        "and each side top-centre sticker matching its own centre",
        white_cross,
        8,
    ),
    (
        "first_layer",
        "complete the first layer: the whole U face correct and the top row of "
        "every side face matching its centre",
        first_layer,
        21,
    ),
    (
        "two_layers",
        "complete the first two layers: the whole U face and the top two rows of "
        "every side face matching their centres",
        two_layers,
        33,
    ),
    (
        "solve",
        "fully solve the cube: every sticker matching its face centre",
        solved_facelets,
        54,
    ),
]
