"""Pluggable LLM interface for the companion to
'The Semantic Turn in Metaheuristics: A Tutorial on Conditioning, Building, and
Choosing LLM Variation Operators'.

The MockLLM makes every demo runnable offline, with no API key and no network: it
returns completions from a fixed pool so the search loop runs end to end and is
fully deterministic.  A real adapter (AnthropicLLM) is provided as an example;
for reproducibility, pin a dated model snapshot and record the seed (Appendix B
of the paper).
"""
from __future__ import annotations
from typing import List


class MockLLM:
    """Deterministic, offline stand-in for an LLM operator.

    It ignores the prompt and returns the next completion from a fixed pool
    (round robin).  This is enough to exercise the full build-and-validate loop
    --- prompt assembly, sampling, parse/validate, bounded repair, selection ---
    without any external dependency, which is what makes the demos reproducible.
    """

    def __init__(self, pool: List[str], seed: int = 0):
        if not pool:
            raise ValueError("MockLLM needs a non-empty completion pool")
        self.pool = list(pool)
        self.seed = seed
        self.i = 0

    def sample(self, prompt: str) -> str:  # noqa: ARG002 (prompt unused by design)
        c = self.pool[self.i % len(self.pool)]
        self.i += 1
        return c


class AnthropicLLM:
    """Example real adapter (optional).

    Requires `pip install anthropic` and the ANTHROPIC_API_KEY environment
    variable.  Pin a dated model snapshot and report temperature/seed for a
    reproducible study (see Appendix B of the paper).
    """

    def __init__(self, model: str = "claude-opus-4-8",
                 temperature: float = 1.0, max_tokens: int = 1024):
        import anthropic  # lazy import so the rest of the package stays dependency-free
        self.client = anthropic.Anthropic()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def sample(self, prompt: str) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
