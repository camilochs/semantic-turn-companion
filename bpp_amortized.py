"""Worked build of Section 4 / Section 5.2: an AMORTIZED, code-conditioned operator
(automatic heuristic design, FunSearch / EoH style).

Here the LLM operator searches *program* space: it emits a Python heuristic
`priority(item, bins)` as text.  The validator (Algorithm 2) parses the envelope,
compiles the payload to an AST, rejects imports, executes it in a restricted
namespace, and checks it returns one score per bin.  The evaluator runs the
heuristic on a small set of synthetic online-bin-packing instances and scores it
by the total number of bins used (lower is better).  The LLM is paid once,
offline; the emitted heuristic then runs with no further LLM calls --- the cost is
amortized.

Run:  uv run bpp_amortized.py
"""
from __future__ import annotations
import ast
import math
import re

from search import build_and_validate
from llm import MockLLM, load_pool

CAPACITY = 10

# Fixed synthetic instances (deterministic; no randomness, so results reproduce).
INSTANCES = [
    [6, 8, 5, 2, 8, 2, 4, 5, 7, 7, 2, 2, 7],
    [5, 7, 3, 4, 5, 6, 7, 5, 2, 3, 7, 3],
    [2, 7, 8, 5, 5, 5, 7, 6, 3, 5, 4],
]

# A minimal, safe builtins set for executing generated heuristics (the paper's
# "run in an isolated environment that cannot touch the host"; harden further
# before running genuinely untrusted code).
_SAFE_BUILTINS = {
    "abs": abs, "min": min, "max": max, "len": len, "sum": sum, "range": range,
    "sorted": sorted, "enumerate": enumerate, "float": float, "int": int, "list": list,
}

_ENV = re.compile(r"CANDIDATE(.*?)END_CANDIDATE", re.S)


def lower_bound_total():
    return sum(math.ceil(sum(inst) / CAPACITY) for inst in INSTANCES)


def parse(text):
    m = _ENV.search(text)
    if not m:
        raise ValueError("schema error: no CANDIDATE envelope")
    pm = re.search(r"payload:\s*(.*)", m.group(1), re.S)
    if not pm or not pm.group(1).strip():
        raise ValueError("syntax error: empty payload")
    code = pm.group(1).strip()
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"syntax error: {exc.msg}")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("feasibility: imports are not allowed")
    g = {"__builtins__": _SAFE_BUILTINS}
    try:
        exec(compile(tree, "<candidate>", "exec"), g)  # noqa: S102 (sandboxed by design)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"syntax error: {exc}")
    fn = g.get("priority")
    if not callable(fn):
        raise ValueError("schema error: no priority(item, bins) defined")
    return fn


def feasible(priority):
    probe = priority(3, [7, 4])
    if not (isinstance(probe, (list, tuple)) and len(probe) == 2):
        raise ValueError("feasibility: priority must return one score per bin")
    return True


def pack(priority, items):
    """Run the heuristic on one instance and return what each open bin holds.

    Returns the contents rather than the count so a caller can look at the
    packing itself; `evaluator` only needs how many bins it took. One
    implementation, because a second one written for inspection would sooner or
    later disagree with the one being scored.
    """
    bins = []  # contents of each open bin
    for item in items:
        room = [CAPACITY - sum(b) for b in bins]
        feas = [i for i, free in enumerate(room) if free >= item]
        if feas:
            scores = priority(item, [room[i] for i in feas])
            # first maximum wins, as in the C++ port
            j = feas[max(range(len(feas)), key=lambda k: scores[k])]
            bins[j].append(item)
        else:
            bins.append([item])
    return bins


def evaluator(priority):
    return sum(len(pack(priority, inst)) for inst in INSTANCES)


class Spec:
    def render(self, cur, score, feedback):
        return ("[context] online bin packing, capacity 10; artifact: a Python "
                "priority(item, bins) returning one score per open bin.\n"
                f"[conditioning] current best total bins = {score}.\n"
                "[instruction] Emit one improved priority function.\n"
                "[format] CANDIDATE envelope with code in the payload.")

    parse = staticmethod(parse)
    feasible = staticmethod(feasible)

    def repair_prompt(self, prompt, text, err):
        return prompt + f"\n[repair] previous program failed validation: {err}."


def main():
    # fixtures/bpp_incumbent.txt is the first-fit heuristic the search starts from;
    # fixtures/bpp_pool.txt holds the three completions, in this order:
    #   returns a scalar   invalid (not one score per bin) -> triggers repair
    #   worst fit          largest leftover, no improvement
    #   best fit           smallest leftover, reaches the lower bound
    incumbent = parse(load_pool("bpp_incumbent.txt")[0])
    pool = load_pool("bpp_pool.txt")
    llm = MockLLM(pool, seed=0)
    accept = lambda cand, sc, cur, scur: sc < scur  # strict improvement
    best, best_score, log = build_and_validate(
        llm, evaluator, accept, incumbent, Spec(), budget=4, retries=1, minimize=True)

    lb = lower_bound_total()
    print(f"lower bound (total bins) = {lb}")
    print(f"first-fit start: total bins = {evaluator(incumbent)}  "
          f"(gap {100*(evaluator(incumbent)-lb)/lb:.1f}%)")
    for t, kind, info in log:
        print(f"  step {t}: {kind:8s} {info}")
    print(f"best heuristic: total bins = {best_score}  (gap {100*(best_score-lb)/lb:.1f}%)")
    return best, best_score


if __name__ == "__main__":
    main()
