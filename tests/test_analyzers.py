#!/usr/bin/env python3
"""Unit tests for individual signal analyzers in vibe_check.py.

Stdlib `unittest` only — matches the project's stdlib-only constraint.

Each test exercises a specific bug class fixed in v0.2.0:
- T1: edge_case_depth no longer monotonically increments on Python
- T2: error_handling distinguishes bare `except:` from `except Exception`
- T3: declarative_bias regex no longer matches `==` comparisons
- T4: naming_uniformity language-aware floor for Python (PEP 8)
- T5: ExceptionGroup is NOT matched by the broad-except regex (Py 3.11+)
- T6: function_length carries diff-only confidence cap
- T7: residual_quantile_margin == conformal_ci shim (deprecation parity)
"""
from __future__ import annotations

import io
import sys
import unittest
import warnings
from pathlib import Path

# Add scripts/ to path so we can import vibe_check directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import vibe_check as vc  # type: ignore  # noqa: E402


def _hunk_from_added_lines(filepath: str, lines: list[str]) -> vc.DiffHunk:
    """Build a DiffHunk directly so tests don't have to format a unified diff."""
    added = [(i + 1, line) for i, line in enumerate(lines)]
    return vc.DiffHunk(filepath=filepath, added_lines=added,
                       removed_lines=[], context_lines=[])


# ──────────────────────────────────────────────────────────────────────────
# T1 — edge_case_depth no longer monotonic on Python
# ──────────────────────────────────────────────────────────────────────────


class TestEdgeCaseDepthPython(unittest.TestCase):

    def test_flat_python_has_low_depth(self):
        """A flat sequence of `if/for/while` statements at the same level
        should report depth 1, not the count of openers (the v0.1.x bug)."""
        lines = [
            "def f(xs):",
            "    if not xs:",
            "        return None",
            "    for x in xs:",
            "        print(x)",
            "    while xs:",
            "        xs.pop()",
            "    try:",
            "        do_thing()",
            "    except ValueError:",
            "        pass",
        ]
        depth = vc._python_max_depth(lines)
        self.assertLessEqual(depth, 4,
                             f"depth={depth} — should be ~3 (def + control), "
                             "not the count of openers (which would be ~7)")

    def test_nested_python_reports_real_depth(self):
        """Nested control flow should report increasing depth."""
        lines = [
            "def f():",
            "    if a:",
            "        for b in c:",
            "            while d:",
            "                if e:",
            "                    pass",
        ]
        depth = vc._python_max_depth(lines)
        # 5 nested openers → depth 5 (def, if, for, while, if).
        self.assertEqual(depth, 5)

    def test_dedent_resets_depth(self):
        """When indentation decreases, depth must release blocks."""
        lines = [
            "def f():",
            "    if a:",
            "        if b:",
            "            pass",
            "    if c:",            # back to outer level
            "        pass",
        ]
        depth = vc._python_max_depth(lines)
        # Max depth observed is 3 (def → if → if), not 5 (def + 4 ifs flat).
        self.assertEqual(depth, 3)

    def test_self_dogfood_realistic_depth(self):
        """vibe_check.py itself should report a realistic max depth.

        Before the v0.2.0 fix, this returned 198 for a 1874-line file.
        Realistic Python max depth is in the single digits.
        """
        text = (ROOT / "scripts" / "vibe_check.py").read_text()
        lines = text.splitlines()
        depth = vc._python_max_depth(lines)
        self.assertLess(depth, 12,
                        f"depth={depth} on vibe_check.py — "
                        "regression of the v0.1.x monotonic-increment bug")


# ──────────────────────────────────────────────────────────────────────────
# T2 + T5 — error_handling: bare except vs broad-typed; ExceptionGroup
# ──────────────────────────────────────────────────────────────────────────


class TestErrorHandlingPython(unittest.TestCase):

    def test_bare_except_scores_high(self):
        """Bare `except:` should add 0.3 to the score and emit evidence."""
        hunk = _hunk_from_added_lines("legacy.py", [
            "def f():",
            "    try:",
            "        do()",
            "    except:",
            "        return None",
        ])
        sig = vc.analyze_error_handling(hunk, "python")
        self.assertTrue(any("bare `except:`" in e for e in sig.evidence),
                        f"bare except not flagged; evidence={sig.evidence}")

    def test_broad_except_exception_softer(self):
        """`except Exception:` is broad-typed; weaker signal than bare."""
        hunk = _hunk_from_added_lines("svc.py", [
            "def f():",
            "    try:",
            "        do()",
            "    except Exception:",
            "        return None",
        ])
        sig = vc.analyze_error_handling(hunk, "python")
        self.assertTrue(any("broad `except Exception`" in e for e in sig.evidence),
                        f"broad-typed except not flagged; evidence={sig.evidence}")
        self.assertFalse(any("bare `except:`" in e for e in sig.evidence),
                         "bare-except evidence should NOT fire on `except Exception:`")

    def test_specific_exception_not_flagged(self):
        """`except ValueError:` and friends must NOT trigger blanket evidence."""
        hunk = _hunk_from_added_lines("svc.py", [
            "def f():",
            "    try:",
            "        do()",
            "    except ValueError:",
            "        return None",
            "    except (OSError, KeyError):",
            "        return -1",
        ])
        sig = vc.analyze_error_handling(hunk, "python")
        self.assertFalse(any("bare `except:`" in e for e in sig.evidence))
        self.assertFalse(any("broad `except Exception`" in e for e in sig.evidence))

    def test_exception_group_not_matched_as_broad(self):
        """Py 3.11+ `except ExceptionGroup:` must NOT match the broad regex.

        Regression test for v0.1.x: pattern `except\\s*Exception` matched any
        Exception-prefixed type. Word boundary fixes this.
        """
        hunk = _hunk_from_added_lines("svc.py", [
            "def f():",
            "    try:",
            "        do()",
            "    except ExceptionGroup as eg:",
            "        return eg",
            "    except BaseExceptionGroup as eg:",
            "        return eg",
        ])
        sig = vc.analyze_error_handling(hunk, "python")
        self.assertFalse(any("broad `except Exception`" in e for e in sig.evidence),
                         f"ExceptionGroup falsely flagged as broad-except; "
                         f"evidence={sig.evidence}")


# ──────────────────────────────────────────────────────────────────────────
# T3 — declarative_bias regex doesn't catch comparisons
# ──────────────────────────────────────────────────────────────────────────


class TestDeclarativeBias(unittest.TestCase):

    def test_assert_equality_not_counted_as_assignment(self):
        """`assert x == 1` must not be counted as a declarative assignment.

        The v0.1.x regex `^\\s*\\w+\\s*=\\s*` matched 'assert' + ' ='.
        """
        hunk = _hunk_from_added_lines("test.py", [
            "def test_thing():",
            "    x = compute()",
            "    assert x == 1",
            "    assert x != 0",
            "    if x >= 5:",
            "        pass",
        ])
        sig = vc.analyze_declarative_bias(hunk, "python")
        # Real assignments: 1 (`x = compute()`). The other 4 lines are
        # comparisons. The signal description should reflect that.
        self.assertIn("Declarative=", sig.explanation)
        # We can't assert exact counts (returns/control mix in), but we can
        # verify the score isn't sky-high for code with mostly comparisons.
        self.assertLess(sig.score, 0.6,
                        f"score={sig.score} too high for code with mostly "
                        f"comparisons: {sig.explanation}")

    def test_pure_assignments_score_high(self):
        """Pure assignment-heavy code with no control flow should score high."""
        hunk = _hunk_from_added_lines("conf.py", [
            "x = 1",
            "y = 2",
            "z = 3",
            "a = 'foo'",
            "b = 'bar'",
            "c = 'baz'",
            "d = 4",
            "return d",
        ])
        sig = vc.analyze_declarative_bias(hunk, "python")
        self.assertGreater(sig.score, 0.5,
                           f"score={sig.score} too low for pure-assignment code")


# ──────────────────────────────────────────────────────────────────────────
# T4 — naming_uniformity language-aware floor
# ──────────────────────────────────────────────────────────────────────────


class TestNamingUniformity(unittest.TestCase):

    def test_python_pep8_compliant_not_flagged(self):
        """98% snake_case in Python is PEP 8, not AI-typical.

        Regression test for v0.1.x naming_uniformity false-positive.
        """
        hunk = _hunk_from_added_lines("util.py", [
            f"def some_function_{i}(arg_one, arg_two):"
            for i in range(20)
        ])
        sig = vc.analyze_naming_uniformity(hunk, "python")
        self.assertLess(sig.score, 0.5,
                        f"score={sig.score} flags PEP 8 compliance as AI-typical")

    def test_javascript_high_uniformity_still_flagged(self):
        """JS doesn't have PEP 8; high uniformity is still a soft AI signal."""
        # 30 camelCase identifiers
        hunk = _hunk_from_added_lines("util.js", [
            f"const someVariable{i} = computeValue{i}(inputArg{i});"
            for i in range(30)
        ])
        sig = vc.analyze_naming_uniformity(hunk, "javascript")
        # Should fire at >0.95 uniformity since JS has no equivalent style enforcer.
        self.assertGreater(sig.score, 0.5,
                           f"score={sig.score} too low for highly-uniform JS")

    def test_extreme_python_uniformity_at_100pct_softly_flagged(self):
        """Python uniformity at 100% with many identifiers is exceptional
        even by PEP 8 standards and should be soft-flagged at exactly 0.4
        (the deliberate Python/Go cap; CALIBRATION_NOTES.md)."""
        # All snake_case, no abbreviations, no exceptions.
        ids = [f"transform_value_into_processed_form_{i}" for i in range(50)]
        hunk = _hunk_from_added_lines("util.py", [
            f"def {n}(input_value): return input_value" for n in ids
        ])
        sig = vc.analyze_naming_uniformity(hunk, "python")
        # Should fire as soft signal, capped at 0.4 by design.
        self.assertGreaterEqual(sig.score, 0.4,
                                f"score={sig.score} should flag exceptional uniformity")
        self.assertLessEqual(sig.score, 0.5,
                             f"score={sig.score} too high — Python uniformity is "
                             "PEP 8-confounded and capped at ~0.4 by design")
        self.assertTrue(any("unusual even by PEP 8" in e for e in sig.evidence),
                        f"evidence does not explain why this fires; ev={sig.evidence}")


# ──────────────────────────────────────────────────────────────────────────
# T6 — function_length confidence cap
# ──────────────────────────────────────────────────────────────────────────


class TestFunctionLength(unittest.TestCase):

    def test_confidence_capped_at_diff_only_max(self):
        """Diff-only function-length is approximate; confidence ≤ 0.4."""
        hunk = _hunk_from_added_lines("svc.py", [
            "def f():",
            "    pass",
            "",
            "def g():",
            "    pass",
            "",
            "def h():",
            "    pass",
            "",
            "def i():",
            "    pass",
        ])
        sig = vc.analyze_function_length(hunk, "python")
        self.assertLessEqual(sig.confidence, 0.4,
                             f"confidence={sig.confidence} exceeds diff-only cap of 0.4")


# ──────────────────────────────────────────────────────────────────────────
# T7 — residual_quantile_margin and deprecation shim parity
# ──────────────────────────────────────────────────────────────────────────


class TestUncertaintyMargin(unittest.TestCase):

    def _toy_signals(self):
        return [
            vc.Signal("comment_ratio", 0.3, 0.18, 0.8, [], [], "x"),
            vc.Signal("docstring_consistency", 0.5, 0.15, 0.7, [], [], "x"),
            vc.Signal("naming_uniformity", 0.4, 0.13, 0.6, [], [], "x"),
            vc.Signal("error_handling", 0.6, 0.12, 0.5, [], [], "x"),
            vc.Signal("declarative_bias", 0.45, 0.1, 0.65, [], [], "x"),
        ]

    def test_residual_margin_returns_bounded_pair(self):
        lo, hi = vc.compute_residual_quantile_margin(self._toy_signals())
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)
        self.assertLessEqual(lo, hi)

    def test_deprecation_shim_emits_warning_and_agrees(self):
        """Old `compute_conformal_ci` must emit DeprecationWarning AND
        return identical values to `compute_residual_quantile_margin`."""
        sigs = self._toy_signals()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old = vc.compute_conformal_ci(sigs)
            self.assertTrue(
                any(issubclass(x.category, DeprecationWarning) for x in w),
                "compute_conformal_ci did not emit DeprecationWarning",
            )
        new = vc.compute_residual_quantile_margin(sigs)
        self.assertEqual(old, new)


# ──────────────────────────────────────────────────────────────────────────
# T8 — model_evolution is fenced (default-disabled)
# ──────────────────────────────────────────────────────────────────────────


class TestModelEvolutionFencing(unittest.TestCase):

    def test_disabled_by_default(self):
        import os
        os.environ.pop("VIBE_CHECK_ENABLE_MODEL_EVOLUTION", None)
        result = vc.detect_model_evolution()
        self.assertEqual(result["status"], "EXPERIMENTAL_DISABLED")
        self.assertIn("MODEL_FINGERPRINTS", result["reason"])


# ──────────────────────────────────────────────────────────────────────────
# T9 — fixtures end-to-end smoke
# ──────────────────────────────────────────────────────────────────────────


class TestFixturesEndToEnd(unittest.TestCase):

    def _analyze_fixture(self, name: str) -> vc.VibeCheckResult:
        diff = (ROOT / "tests" / "fixtures" / name).read_text()
        return vc.analyze_diff(diff)

    def test_clean_human_python_grade_below_C(self):
        """A small, idiomatic, lightly-tested Python module should grade B or A."""
        result = self._analyze_fixture("clean_human_python.diff")
        self.assertIn(result.grade, ("A", "B"),
                      f"clean human Python graded {result.grade}; "
                      f"prob={result.overall_ai_probability}")

    def test_ai_dump_python_flags_overcommenting(self):
        """The AI-dump fixture has heavy docstrings + 'Initialize the' comments
        + bare `except Exception:`. At least one AI pattern must fire."""
        result = self._analyze_fixture("ai_dump_python.diff")
        # Either OVER_COMMENTING, BOILERPLATE_BLOAT, EXCESSIVE_DOCSTRINGS,
        # or SHALLOW_ERROR_HANDLING should fire.
        ai_patterns = result.pattern_taxonomy
        self.assertTrue(
            any(k in ai_patterns for k in
                ("over_commenting", "boilerplate_bloat", "excessive_docstrings",
                 "shallow_error_handling")),
            f"AI-dump fixture surfaced no expected patterns: {ai_patterns}"
        )

    def test_hallucination_fixture_fires_hallucinated_apis(self):
        """The hallucination fixture must trigger `hallucinated_api`."""
        result = self._analyze_fixture("hallucination_trigger.diff")
        self.assertIn("hallucinated_api", result.pattern_taxonomy)

    def test_bare_except_fixture_fires_specifically(self):
        """Bare `except:` fixture must mention bare in evidence."""
        result = self._analyze_fixture("bare_except_python.diff")
        eh = result.signal_summary.get("error_handling", {})
        self.assertTrue(
            any("bare `except:`" in e for e in eh.get("top_evidence", [])),
            f"bare-except fixture didn't surface bare-except evidence: {eh}",
        )


# ──────────────────────────────────────────────────────────────────────────
# T10 — JSON output contract
# ──────────────────────────────────────────────────────────────────────────


class TestJSONContract(unittest.TestCase):

    def test_required_keys_present(self):
        diff = (ROOT / "tests" / "fixtures" / "clean_human_python.diff").read_text()
        result = vc.analyze_diff(diff)
        from dataclasses import asdict
        d = asdict(result)
        for k in ("overall_ai_probability", "grade", "signal_summary",
                  "file_analyses", "pattern_taxonomy", "recommendations",
                  "methodology_notes", "evidence_status"):
            self.assertIn(k, d, f"missing JSON key: {k}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
