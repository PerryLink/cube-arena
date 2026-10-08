"""Verify the Clef adapter without any Cloudflare credentials.

The Clef panels are blocked on a Workers AI token, so this proves the code path
that token will exercise: request shape out, and both response shapes parsed
correctly (Workers AI may or may not wrap the SystemOne body in `result`).

Run: python test_clef_mock.py
"""

from __future__ import annotations

import json
import os

# Set fake credentials BEFORE importing engines, so ClefEngine constructs.
os.environ["CLOUDFLARE_ACCOUNT_ID"] = "test-account"
os.environ["CLOUDFLARE_AUTH_TOKEN"] = "test-token"

from engines import ClefEngine, move_question  # noqa: E402

STATE = "a scrambled cube\nU: WWWWWWWWW ..."

# What the adapter should send.
EXPECTED_URL_FRAGMENT = "/accounts/test-account/ai/run/@cf/cloudflare/clef-flash"


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


def answers_body() -> dict:
    """A SystemOne `answers` body, as Clef documents it."""
    return {
        "model": "clef-flash",
        "answers": {
            "move": {
                "choice": "R",
                "confidence": 0.81,
                "probabilities": {"R": 0.81, "U": 0.11, "F": 0.08},
            }
        },
        "usage": {"input_tokens": 412, "output_tokens": 0},
    }


def run_case(name: str, payload: dict, expect_choice: str | None, status: int = 200) -> bool:
    eng = ClefEngine("clef-flash")
    sent: dict = {}

    def fake_post(url, json=None, **kw):  # noqa: A002
        sent["url"] = url
        sent["body"] = json
        return FakeResponse(payload, status)

    eng.client.post = fake_post
    d = eng.decide(STATE, move_question("Which move?"), "move")

    ok = True
    if expect_choice is not None and d.choice != expect_choice:
        ok = False
    if expect_choice is None and not d.error:
        ok = False
    print(f"  [{'ok ' if ok else 'FAIL'}] {name}: choice={d.choice!r} "
          f"conf={d.confidence} probs={len(d.probabilities)} err={(d.error or '')[:40]!r}")
    return ok, sent, d


def main() -> None:
    print("=== URL + request shape ===")
    eng = ClefEngine("clef-flash")
    print("  url:", eng.url)
    assert EXPECTED_URL_FRAGMENT in eng.url, "wrong Workers AI URL"
    print("  auth header set:", "Authorization" in eng.client.headers)
    print("  url fragment ok: True")

    print("=== response parsing ===")
    all_ok = True

    # 1. bare answers body
    ok, sent, d = run_case("bare {answers: ...}", answers_body(), "R")
    all_ok &= ok
    body = sent["body"]
    assert body["model"] == "clef-flash", body.get("model")
    assert "questions" in body and "move" in body["questions"], "question not wrapped under its id"
    crit = body["questions"]["move"]["criteria"]
    assert isinstance(crit, dict) and len(crit) == 18, f"criteria must be an 18-entry dict, got {type(crit)}"
    assert body["questions"]["move"]["type"] == "choice"
    print("  request: model + questions{move: choice, criteria=18 dict} ok")
    assert d.confidence == 0.81 and abs(sum(d.probabilities.values()) - 1.0) < 1e-6

    # 2. Workers AI wrapped in "result"
    wrapped = {"result": answers_body(), "success": True, "errors": [], "messages": []}
    ok, _, d = run_case('wrapped {"result": ...}', wrapped, "R")
    all_ok &= ok

    # 3. HTTP error surfaces cleanly
    ok, _, d = run_case("HTTP 401", {}, None, status=401)
    all_ok &= ok

    # 4. malformed body surfaces a parse error, never a bogus move
    ok, _, d = run_case("malformed body", {"nope": 1}, None)
    all_ok &= ok
    assert d.error and "parse" in d.error, d.error

    print()
    print("ALL CLEF ADAPTER CHECKS PASSED" if all_ok else "SOME CHECKS FAILED")


if __name__ == "__main__":
    main()