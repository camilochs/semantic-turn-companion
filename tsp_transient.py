"""Worked build of Section 4: a TRANSIENT, numeric-conditioned operator.

The LLM operator proposes a TSP tour directly (a permutation).  This reproduces
the traced iteration of Section 4.4: an incumbent [0,2,3,4,1] of length 9.236, an
invalid first sample [0,1,4,4,2] that the validator rejects (city 4 duplicated,
city 3 missing), and a repaired [0,1,2,3,4] of length 8.000 that is accepted.

Run:  uv run tsp_transient.py
"""
from __future__ import annotations
import math
import re

from search import build_and_validate
from llm import MockLLM, load_pool

COORDS = {0: (0, 0), 1: (1, 0), 2: (2, 0), 3: (2, 2), 4: (0, 2)}
N = len(COORDS)


def tour_len(t):
    return sum(math.dist(COORDS[t[i]], COORDS[t[(i + 1) % len(t)]]) for i in range(len(t)))


_ENV = re.compile(r"CANDIDATE(.*?)END_CANDIDATE", re.S)


def parse(text):
    m = _ENV.search(text)
    if not m:
        raise ValueError("schema error: no CANDIDATE envelope")
    pm = re.search(r"payload:\s*(\[[^\]]*\])", m.group(1))
    if not pm:
        raise ValueError("syntax error: no payload list")
    body = pm.group(1).strip()[1:-1]
    try:
        return [int(x) for x in body.split(",") if x.strip() != ""]
    except ValueError:
        raise ValueError("syntax error: payload is not a list of integers")


def feasible(perm):
    if sorted(perm) != list(range(N)):
        missing = [c for c in range(N) if c not in perm]
        dup = sorted({c for c in perm if perm.count(c) > 1})
        raise ValueError(f"feasibility: city {dup} duplicated, city {missing} missing")
    return True


class Spec:
    def render(self, cur, score, feedback):
        return ("[context] TSP toy instance; minimize Euclidean closed-tour length.\n"
                f"[conditioning] R = permutation of {list(range(N))} starting at 0; "
                f"incumbent {cur}, score {score:.3f}.\n"
                "[instruction] Emit one lower-length tour if possible.\n"
                "[format] Use the CANDIDATE envelope.")

    parse = staticmethod(parse)
    feasible = staticmethod(feasible)

    def repair_prompt(self, prompt, text, err):
        return prompt + f"\n[repair] previous payload failed validation: {err}. Emit a corrected CANDIDATE."


def main():
    incumbent = [0, 2, 3, 4, 1]
    # fixtures/tsp_pool.txt holds the four completions, in this order:
    #   [0,1,4,4,2]  invalid (city 4 duplicated, city 3 missing) -> triggers repair
    #   [0,1,2,3,4]  the repaired tour, length 8.000
    #   [0,2,1,3,4]  a further valid, non-improving candidate
    #   [0,3,1,2,4]  likewise
    pool = load_pool("tsp_pool.txt")
    llm = MockLLM(pool, seed=0)
    accept = lambda cand, sc, cur, scur: sc < scur  # strict improvement
    best, best_score, log = build_and_validate(
        llm, tour_len, accept, incumbent, Spec(), budget=3, retries=1, minimize=True)

    print(f"incumbent {incumbent}  length {tour_len(incumbent):.3f}")
    for t, kind, info in log:
        info = round(info, 3) if isinstance(info, float) else info
        print(f"  step {t}: {kind:8s} {info}")
    print(f"best {best}  length {best_score:.3f}")
    return best, best_score


if __name__ == "__main__":
    main()
