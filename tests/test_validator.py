"""The validator, one test per reason it can reject (Algorithm 2).

Algorithm 2 rejects in three layers — envelope and schema, payload syntax, domain
feasibility — and returns a layer-specific diagnostic, because that diagnostic is
what the repair prompt feeds back to the model. A validator that says only "invalid"
makes bounded repair useless, so each layer is tested for what it says, not only
for the fact that it refused.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpp_amortized as bpp  # noqa: E402
import tsp_transient as tsp  # noqa: E402
from llm import load_pool  # noqa: E402


class TspValidatorTest(unittest.TestCase):
    def test_missing_envelope_is_a_schema_error(self):
        with self.assertRaises(ValueError) as cm:
            tsp.parse("here is a tour: [0,1,2,3,4]")
        self.assertIn("schema error", str(cm.exception))

    def test_missing_payload_list_is_a_syntax_error(self):
        with self.assertRaises(ValueError) as cm:
            tsp.parse("CANDIDATE\nid: t\npayload:\nnot a list\nEND_CANDIDATE")
        self.assertIn("syntax error", str(cm.exception))

    def test_a_duplicated_city_is_a_feasibility_error_that_names_the_city(self):
        with self.assertRaises(ValueError) as cm:
            tsp.feasible([0, 1, 4, 4, 2])
        msg = str(cm.exception)
        self.assertIn("feasibility", msg)
        self.assertIn("4", msg, "the diagnostic must name the duplicated city")
        self.assertIn("3", msg, "and the missing one")

    def test_a_valid_tour_passes(self):
        self.assertTrue(tsp.feasible([0, 1, 2, 3, 4]))

    def test_the_frozen_pool_still_contains_the_invalid_completion(self):
        """The traced iteration only teaches repair if the first sample really fails."""
        first = load_pool("tsp_pool.txt")[0]
        with self.assertRaises(ValueError):
            tsp.feasible(tsp.parse(first))


class BppValidatorTest(unittest.TestCase):
    def test_an_import_is_refused(self):
        code = "CANDIDATE\npayload:\nimport os\ndef priority(item, bins):\n    return [0]*len(bins)\nEND_CANDIDATE"
        with self.assertRaises(ValueError) as cm:
            bpp.parse(code)
        self.assertIn("imports are not allowed", str(cm.exception))

    def test_broken_python_is_a_syntax_error(self):
        with self.assertRaises(ValueError) as cm:
            bpp.parse("CANDIDATE\npayload:\ndef priority(item, bins)\n    return []\nEND_CANDIDATE")
        self.assertIn("syntax error", str(cm.exception))

    def test_code_without_the_expected_function_is_a_schema_error(self):
        with self.assertRaises(ValueError) as cm:
            bpp.parse("CANDIDATE\npayload:\ndef other(x):\n    return x\nEND_CANDIDATE")
        self.assertIn("no priority(item, bins)", str(cm.exception))

    def test_a_heuristic_returning_a_scalar_fails_the_execution_probe(self):
        fn = bpp.parse("CANDIDATE\npayload:\ndef priority(item, bins):\n    return 0\nEND_CANDIDATE")
        with self.assertRaises(ValueError) as cm:
            bpp.feasible(fn)
        self.assertIn("one score per bin", str(cm.exception))

    def test_best_fit_reaches_the_lower_bound_and_first_fit_does_not(self):
        best_fit = bpp.parse(load_pool("bpp_pool.txt")[2])
        first_fit = bpp.parse(load_pool("bpp_incumbent.txt")[0])
        self.assertEqual(bpp.evaluator(best_fit), bpp.lower_bound_total())
        self.assertGreater(bpp.evaluator(first_fit), bpp.lower_bound_total())


if __name__ == "__main__":
    unittest.main()
