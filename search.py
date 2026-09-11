"""Algorithm 1 of the paper: an LLM variation operator with bounded repair.

This is the reference build loop.  It keeps the incumbent the search walks (`cur`)
separate from the best artifact ever seen (`best`), so it stays correct under any
acceptance rule, including non-monotone rules (e.g. simulated-annealing style) that
may accept a worsening move.

A problem is plugged in through `spec`, which must supply four methods:
    render(cur, score, feedback) -> str        # assemble the prompt (Section 4.2)
    parse(text) -> artifact                    # schema + syntax (Algorithm 2)
    feasible(artifact) -> True | raises ValueError   # domain feasibility
    repair_prompt(prompt, text, err) -> str    # append the diagnostic, re-prompt
"""
from __future__ import annotations
from typing import Any, Callable, List, Tuple


def build_and_validate(llm, evaluator: Callable[[Any], float],
                       accept: Callable[[Any, float, Any, float], bool],
                       incumbent: Any, spec, budget: int, retries: int,
                       minimize: bool = True) -> Tuple[Any, float, List[tuple]]:
    cur = best = incumbent
    best_score = evaluator(incumbent)
    feedback: List[tuple] = []
    log: List[tuple] = []
    for t in range(budget):
        prompt = spec.render(cur, evaluator(cur), feedback)
        ok, cand, err = False, None, None
        for _ in range(retries + 1):
            text = llm.sample(prompt)
            try:
                cand = spec.parse(text)        # schema + syntax
                spec.feasible(cand)            # domain feasibility
                ok = True
                break
            except ValueError as exc:
                err = str(exc)
                prompt = spec.repair_prompt(prompt, text, err)
        if not ok:
            feedback.append(("invalid", err))
            log.append((t, "invalid", err))
            continue
        score_c = evaluator(cand)
        if accept(cand, score_c, cur, evaluator(cur)):
            cur = cand
            better = score_c < best_score if minimize else score_c > best_score
            if better:
                best, best_score = cand, score_c
            feedback.append(("accepted", score_c))
            log.append((t, "accepted", score_c))
        else:
            feedback.append(("rejected", score_c))
            log.append((t, "rejected", score_c))
    return best, best_score, log
