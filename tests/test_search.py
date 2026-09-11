"""Invariants of the build loop (Algorithm 1).

The frozen outputs in expected/ check that the demos still produce the trace the
tutorial prints. These tests check something else: that the loop keeps its
properties under inputs the demos never exercise. Both are needed — a golden file
passes happily while a loop is wrong in a case nobody runs.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import MockLLM  # noqa: E402
from search import build_and_validate  # noqa: E402


def envelope(value):
    return f"CANDIDATE\nid: t\npayload:\n{value}\nEND_CANDIDATE"


class IntSpec:
    """Toy problem: the artifact is an integer, and lower is better."""

    def render(self, cur, score, feedback):
        return f"incumbent {cur} score {score}"

    @staticmethod
    def parse(text):
        if "CANDIDATE" not in text:
            raise ValueError("schema error: no CANDIDATE envelope")
        body = text.split("payload:")[1].split("END_CANDIDATE")[0].strip()
        try:
            return int(body)
        except ValueError:
            raise ValueError("syntax error: payload is not an integer")

    @staticmethod
    def feasible(v):
        if v < 0:
            raise ValueError("feasibility: negative value")
        return True

    def repair_prompt(self, prompt, text, err):
        return prompt + f"\n[repair] {err}"


class BuildLoopTest(unittest.TestCase):
    def test_best_is_kept_when_the_walk_moves_away_from_it(self):
        """The reason `best` exists apart from `cur`: an accept rule may walk downhill."""
        llm = MockLLM([envelope(1), envelope(9)])
        best, best_score, log = build_and_validate(
            llm, lambda v: float(v), lambda c, sc, cur, scur: True,  # accept everything
            incumbent=5, spec=IntSpec(), budget=2, retries=0, minimize=True)
        self.assertEqual(best, 1)
        self.assertEqual(best_score, 1.0)
        self.assertEqual([kind for _, kind, _ in log], ["accepted", "accepted"])

    def test_an_invalid_sample_is_repaired_within_the_retry_budget(self):
        llm = MockLLM(["no envelope here", envelope(2)])
        best, best_score, log = build_and_validate(
            llm, lambda v: float(v), lambda c, sc, cur, scur: sc < scur,
            incumbent=5, spec=IntSpec(), budget=1, retries=1, minimize=True)
        self.assertEqual(best, 2)
        self.assertEqual([kind for _, kind, _ in log], ["accepted"])

    def test_a_step_that_exhausts_its_retries_is_logged_invalid_and_the_search_continues(self):
        llm = MockLLM(["garbage", "still garbage", envelope(3)])
        best, _, log = build_and_validate(
            llm, lambda v: float(v), lambda c, sc, cur, scur: sc < scur,
            incumbent=5, spec=IntSpec(), budget=2, retries=0, minimize=True)
        self.assertEqual([kind for _, kind, _ in log], ["invalid", "invalid"])
        self.assertEqual(best, 5, "the incumbent survives when nothing valid arrives")

    def test_a_rejected_candidate_does_not_move_the_incumbent(self):
        llm = MockLLM([envelope(9), envelope(4)])
        best, best_score, log = build_and_validate(
            llm, lambda v: float(v), lambda c, sc, cur, scur: sc < scur,
            incumbent=5, spec=IntSpec(), budget=2, retries=0, minimize=True)
        self.assertEqual([kind for _, kind, _ in log], ["rejected", "accepted"])
        self.assertEqual(best, 4)

    def test_maximization_uses_the_same_loop(self):
        llm = MockLLM([envelope(7)])
        best, best_score, _ = build_and_validate(
            llm, lambda v: float(v), lambda c, sc, cur, scur: sc > scur,
            incumbent=5, spec=IntSpec(), budget=1, retries=0, minimize=False)
        self.assertEqual((best, best_score), (7, 7.0))

    def test_the_mock_model_is_deterministic(self):
        a = MockLLM([envelope(1), envelope(2)])
        b = MockLLM([envelope(1), envelope(2)])
        self.assertEqual([a.sample("x") for _ in range(4)], [b.sample("y") for _ in range(4)])


if __name__ == "__main__":
    unittest.main()
