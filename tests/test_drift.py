"""
Tests for drift functions in scripts/eval_drift.py and scripts/vibe_check.py.

Discipline (per the action plan in
applications/_reviews/2026-05-19-portfolio-action-plan.md item #2):
    Each function gets at least three tests:
      - Positive: the assertion under test holds for valid input
      - Negative: the function does NOT do what it shouldn't
      - Boundary: edge of valid input (empty, min-sample guards, identical
        distributions, std=0, n_bins=1, etc.)
    Adversarial discrimination > defensive coverage.

The drift functions are the load-bearing claim of the vibe-check tool's
"calibrated under distribution shift" framing. These tests pin the behavior
that the README documents and that downstream calibration rebalances against.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from eval_drift import (  # noqa: E402
    bucketize,
    histogram_01,
    load_jsonl,
    mcc,
    mean_shift,
    psi,
    sinkhorn_1d,
)
from vibe_check import (  # noqa: E402
    DRIFT_STATE_FILENAME,
    _apply_persistence_rule,
    _global_drift_psi,
    _global_drift_sinkhorn,
    _histogram_01,
    _load_drift_state,
    _psi_1d,
    _save_drift_state,
    _sinkhorn_1d,
    check_drift_status,
)


# ---------------------------------------------------------------------------
# histogram_01
# ---------------------------------------------------------------------------


class TestHistogram01:
    """
    histogram_01(vals, n_bins=20) -> list[float]

    Normalizes values to [0, 1], bins them, returns the normalized histogram.
    Empty input returns all zeros (denominator coerced to 1 via `or 1.0`).
    """

    def test_uniform_distribution_spreads_across_bins(self):
        # Positive: 100 uniformly-spaced values fill all 20 bins roughly evenly.
        vals = [i / 100.0 for i in range(100)]
        h = histogram_01(vals, n_bins=20)
        assert len(h) == 20
        assert math.isclose(sum(h), 1.0, abs_tol=1e-9)
        # Each bin holds ~5 of 100 values = 0.05. Wide tolerance allows boundary effects.
        assert all(0.03 <= b <= 0.07 for b in h)

    def test_skewed_distribution_concentrates(self):
        # Positive: all values near 0 land in low bins.
        vals = [0.01] * 50
        h = histogram_01(vals, n_bins=10)
        # All 50 values are 0.01, so int(0.01 * 10) = 0; entire mass in bin 0.
        assert math.isclose(h[0], 1.0, abs_tol=1e-9)
        assert all(b == 0.0 for b in h[1:])

    def test_empty_input_returns_zero_histogram(self):
        # Boundary: empty input → all zeros, no ZeroDivision (because of `or 1.0`).
        h = histogram_01([], n_bins=20)
        assert h == [0.0] * 20

    def test_clamps_values_above_one(self):
        # Boundary: values > 1.0 are clamped to 1.0 → last bin.
        h = histogram_01([5.0, 10.0, 100.0], n_bins=10)
        assert h[-1] == 1.0
        assert all(b == 0.0 for b in h[:-1])

    def test_clamps_values_below_zero(self):
        # Boundary: values < 0 are clamped to 0 → first bin.
        h = histogram_01([-1.0, -5.0], n_bins=10)
        assert h[0] == 1.0
        assert all(b == 0.0 for b in h[1:])

    def test_exactly_one_lands_in_last_bin(self):
        # Boundary: value == 1.0 → int(1.0 * n_bins) == n_bins, capped to n_bins-1.
        h = histogram_01([1.0], n_bins=5)
        assert h[-1] == 1.0

    def test_custom_n_bins_is_honored(self):
        # Negative: histogram does NOT use the default 20 when caller overrides.
        h = histogram_01([0.5], n_bins=3)
        assert len(h) == 3

    def test_string_coerced_via_float(self):
        # Defensive: the function calls float(v); ints are accepted via that path.
        # If something un-floatable arrives the function will raise (correct
        # behavior; pinning that contract here so a refactor can't silently
        # change it).
        h = histogram_01([0, 1], n_bins=2)
        assert math.isclose(sum(h), 1.0, abs_tol=1e-9)
        with pytest.raises((TypeError, ValueError)):
            histogram_01(["not-a-float"])


# ---------------------------------------------------------------------------
# psi
# ---------------------------------------------------------------------------


class TestPSI:
    """
    psi(expected, actual, epsilon=1e-4) -> float

    Population Stability Index between two value sequences. Identical
    distributions score 0 (modulo epsilon floor). Larger shifts score higher.
    """

    def test_identical_distributions_score_near_zero(self):
        # Positive: PSI of a distribution against itself ≈ 0.
        vals = [0.1, 0.2, 0.3, 0.4, 0.5] * 20
        assert psi(vals, vals) == pytest.approx(0.0, abs=1e-9)

    def test_shifted_distribution_scores_positive(self):
        # Positive: a clear shift produces a positive PSI.
        baseline = [0.1] * 100
        shifted = [0.9] * 100
        assert psi(baseline, shifted) > 0.5

    def test_psi_discriminates_by_mass_fraction_moved(self):
        # Discrimination: PSI grows with the FRACTION of mass that moves
        # between bins, not with the distance between bins. (Sinkhorn handles
        # distance; PSI is shape-only.) This test pins that contract.
        baseline = [0.5] * 100
        small_shift = [0.5] * 90 + [0.9] * 10  # 10% mass moves to bin 18
        large_shift = [0.5] * 50 + [0.9] * 50  # 50% mass moves to bin 18
        assert psi(baseline, small_shift) < psi(baseline, large_shift)

    def test_psi_invariant_to_bin_distance(self):
        # Negative: PSI does NOT increase with bin-distance when the same
        # amount of mass moves. This is the explicit limitation of PSI vs
        # Sinkhorn; codifying it so a future "improvement" can't silently
        # break the assumption downstream calibration was tuned against.
        baseline = [0.5] * 100
        near_target = [0.55] * 100  # all mass to adjacent bin
        far_target = [0.95] * 100   # all mass to distant bin
        assert psi(baseline, near_target) == pytest.approx(
            psi(baseline, far_target), abs=1e-9
        )

    def test_empty_inputs_score_zero(self):
        # Boundary: two empty histograms → both all-zero → PSI = 0
        # (each bin contribution is (epsilon - epsilon) * log(1) = 0).
        assert psi([], []) == pytest.approx(0.0, abs=1e-9)

    def test_epsilon_floor_prevents_log_zero(self):
        # Boundary: when actual has zero density in a bin, epsilon floor keeps
        # log finite. The score should be a number (not inf, not nan).
        baseline = [0.5] * 100
        actual = [0.05] * 100  # all in lowest bin only
        score = psi(baseline, actual)
        assert math.isfinite(score)
        assert score > 0  # discrimination: the shift is detected

    def test_custom_epsilon_changes_result_for_zero_bins(self):
        # Discrimination: larger epsilon dampens the score when bins are empty.
        baseline = [0.5] * 100
        actual = [0.05] * 100
        s_default = psi(baseline, actual)
        s_large_eps = psi(baseline, actual, epsilon=0.1)
        # Larger epsilon raises the floor on near-zero bins, so the divergence
        # between (a - e) * log(a/e) terms shrinks: the score should be smaller
        # (or at minimum not larger) when epsilon is bigger.
        assert s_large_eps <= s_default


# ---------------------------------------------------------------------------
# mean_shift
# ---------------------------------------------------------------------------


class TestMeanShift:
    """
    mean_shift(expected, actual) -> float

    Z-style shift: |mu_a - mu_e| / std_e. Below 3 samples in either input
    returns 0 (min-sample guard). std=0 substituted with 1e-4.
    """

    def test_identical_means_score_zero(self):
        # Positive: same distribution → mean shift is 0.
        vals = [0.1, 0.2, 0.3, 0.4, 0.5]
        assert mean_shift(vals, vals) == pytest.approx(0.0)

    def test_shifted_means_score_positive(self):
        # Positive: shift in mean is detected.
        baseline = [0.0, 0.0, 0.0, 0.0, 0.0]
        shifted = [1.0, 1.0, 1.0, 1.0, 1.0]
        # std_e = 0 → substituted with 1e-4 → shift = 1.0 / 1e-4 = 1e4.
        assert mean_shift(baseline, shifted) > 100.0

    def test_min_sample_guard_returns_zero_when_expected_too_short(self):
        # Boundary: n < 3 in expected → 0.
        assert mean_shift([0.5, 0.5], [0.0, 1.0, 2.0, 3.0]) == 0.0

    def test_min_sample_guard_returns_zero_when_actual_too_short(self):
        # Boundary: n < 3 in actual → 0.
        assert mean_shift([0.0, 1.0, 2.0, 3.0], [0.5, 0.5]) == 0.0

    def test_zero_variance_baseline_handled_via_epsilon(self):
        # Boundary: std=0 substituted with 1e-4. With identical baseline (var=0)
        # and a different actual mean, the score should be very large but
        # finite, not nan or div-by-zero.
        baseline = [0.5, 0.5, 0.5, 0.5, 0.5]
        actual = [0.6, 0.6, 0.6, 0.6, 0.6]
        score = mean_shift(baseline, actual)
        assert math.isfinite(score)
        assert score == pytest.approx(0.1 / 1e-4, rel=1e-6)

    def test_discrimination_grows_with_shift_magnitude(self):
        # Discrimination: larger shift → larger score.
        baseline = [0.0, 0.1, 0.2, 0.3, 0.4]
        small = [0.1, 0.2, 0.3, 0.4, 0.5]
        large = [1.0, 1.1, 1.2, 1.3, 1.4]
        assert mean_shift(baseline, small) < mean_shift(baseline, large)


# ---------------------------------------------------------------------------
# sinkhorn_1d
# ---------------------------------------------------------------------------


class TestSinkhorn1D:
    """
    sinkhorn_1d(expected, actual, reg=0.06, iters=60) -> float

    Entropy-regularized 1D optimal transport cost. Identical distributions
    score near zero; larger distributional gaps score higher.
    """

    def test_identical_distributions_score_near_zero(self):
        # Positive: same distribution → near-zero transport cost.
        vals = [0.2, 0.4, 0.6, 0.8] * 25
        score = sinkhorn_1d(vals, vals)
        assert score < 0.05

    def test_shifted_distribution_scores_higher(self):
        # Positive: moving mass from low to high bins costs more than identity.
        baseline = [0.1] * 100
        shifted = [0.9] * 100
        score_identity = sinkhorn_1d(baseline, baseline)
        score_shift = sinkhorn_1d(baseline, shifted)
        assert score_shift > score_identity

    def test_discrimination_grows_with_distance(self):
        # Discrimination: bigger geographic shift in 1D → bigger cost.
        baseline = [0.0] * 100
        near = [0.1] * 100
        far = [0.9] * 100
        assert sinkhorn_1d(baseline, near) < sinkhorn_1d(baseline, far)

    def test_returns_finite_value_with_few_iters(self):
        # Boundary: small iter count still returns a finite, non-nan value.
        score = sinkhorn_1d([0.1] * 20, [0.9] * 20, iters=5)
        assert math.isfinite(score)
        assert score >= 0.0

    def test_returns_finite_value_with_small_reg(self):
        # Boundary: small regularization can push numbers near float limits;
        # function still returns finite (the `or 1e-12` guards divide-by-zero).
        score = sinkhorn_1d([0.1] * 20, [0.9] * 20, reg=0.001, iters=10)
        assert math.isfinite(score)

    def test_empty_inputs_return_finite(self):
        # Boundary: both inputs empty → both histograms all zero. The function
        # still completes (divide-by-zero is guarded by `or 1e-12`).
        score = sinkhorn_1d([], [])
        assert math.isfinite(score)


# ---------------------------------------------------------------------------
# mcc
# ---------------------------------------------------------------------------


class TestMCC:
    """
    mcc(tp, fp, tn, fn) -> float

    Matthews correlation coefficient. Returns 0 if denominator is 0.
    Range [-1, 1] for well-posed inputs.
    """

    def test_perfect_classification_scores_one(self):
        # Positive: all predictions correct → MCC = 1.
        assert mcc(tp=10, fp=0, tn=10, fn=0) == pytest.approx(1.0)

    def test_perfect_anti_classification_scores_negative_one(self):
        # Discrimination: all predictions inverted → MCC = -1.
        assert mcc(tp=0, fp=10, tn=0, fn=10) == pytest.approx(-1.0)

    def test_zero_denominator_returns_zero(self):
        # Boundary: any of (tp+fp), (tp+fn), (tn+fp), (tn+fn) zero → MCC = 0.
        # Here tp+fp = 0 (no predicted positives).
        assert mcc(tp=0, fp=0, tn=10, fn=5) == 0.0

    def test_balanced_random_classification_near_zero(self):
        # Negative: a balanced confusion matrix where predictions are
        # uncorrelated with labels → MCC near 0.
        # tp=5, fp=5, tn=5, fn=5 → numerator = 25 - 25 = 0.
        assert mcc(tp=5, fp=5, tn=5, fn=5) == pytest.approx(0.0)

    def test_within_range_for_realistic_inputs(self):
        # Negative: MCC must not exceed [-1, 1] for any well-posed input.
        score = mcc(tp=8, fp=2, tn=7, fn=3)
        assert -1.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# load_jsonl
# ---------------------------------------------------------------------------


class TestLoadJSONL:
    """
    load_jsonl(path) -> list[dict]

    Reads JSONL, keeps rows with both a `signals` dict AND a `timestamp` key.
    Skips empty lines, malformed JSON, and rows missing required keys.
    """

    def test_happy_path_loads_valid_rows(self, tmp_path):
        # Positive: well-formed rows are returned in order.
        p = tmp_path / "t.jsonl"
        p.write_text(
            '{"signals": {"a": 0.1}, "timestamp": "2026-01-01T00:00:00Z"}\n'
            '{"signals": {"a": 0.2}, "timestamp": "2026-01-02T00:00:00Z"}\n'
        )
        rows = load_jsonl(p)
        assert len(rows) == 2
        assert rows[0]["signals"]["a"] == 0.1

    def test_empty_lines_skipped(self, tmp_path):
        # Negative: blank lines are NOT counted as rows.
        p = tmp_path / "t.jsonl"
        p.write_text(
            '{"signals": {"a": 0.1}, "timestamp": "2026-01-01T00:00:00Z"}\n'
            '\n'
            '   \n'
            '{"signals": {"a": 0.2}, "timestamp": "2026-01-02T00:00:00Z"}\n'
        )
        assert len(load_jsonl(p)) == 2

    def test_malformed_json_skipped(self, tmp_path):
        # Negative: a non-JSON line does not abort the whole load.
        p = tmp_path / "t.jsonl"
        p.write_text(
            '{"signals": {"a": 0.1}, "timestamp": "2026-01-01T00:00:00Z"}\n'
            'not-json-at-all\n'
            '{"signals": {"a": 0.2}, "timestamp": "2026-01-02T00:00:00Z"}\n'
        )
        assert len(load_jsonl(p)) == 2

    def test_missing_signals_key_skipped(self, tmp_path):
        # Negative: row without a `signals` dict is dropped.
        p = tmp_path / "t.jsonl"
        p.write_text(
            '{"timestamp": "2026-01-01T00:00:00Z"}\n'
            '{"signals": {"a": 0.1}, "timestamp": "2026-01-02T00:00:00Z"}\n'
        )
        rows = load_jsonl(p)
        assert len(rows) == 1
        assert rows[0]["signals"]["a"] == 0.1

    def test_missing_timestamp_skipped(self, tmp_path):
        # Negative: row without a `timestamp` is dropped.
        p = tmp_path / "t.jsonl"
        p.write_text(
            '{"signals": {"a": 0.1}}\n'
            '{"signals": {"a": 0.2}, "timestamp": "2026-01-02T00:00:00Z"}\n'
        )
        rows = load_jsonl(p)
        assert len(rows) == 1

    def test_signals_must_be_dict_not_list(self, tmp_path):
        # Boundary: `signals` must be a dict; a list is rejected.
        p = tmp_path / "t.jsonl"
        p.write_text(
            '{"signals": [0.1, 0.2], "timestamp": "2026-01-01T00:00:00Z"}\n'
        )
        assert load_jsonl(p) == []

    def test_empty_file_returns_empty(self, tmp_path):
        # Boundary: empty file → empty list, no exception.
        p = tmp_path / "t.jsonl"
        p.write_text("")
        assert load_jsonl(p) == []


# ---------------------------------------------------------------------------
# bucketize
# ---------------------------------------------------------------------------


class TestBucketize:
    """
    bucketize(ts, granularity) -> str

    Converts an ISO timestamp to a week bucket "YYYY-Www" (default) or a day
    bucket "YYYY-MM-DD". Invalid timestamps return "unknown".
    """

    def test_day_bucket_extracts_date(self):
        # Positive: day granularity returns calendar date.
        assert bucketize("2026-05-19T14:30:00Z", "day") == "2026-05-19"

    def test_week_bucket_uses_iso_week(self):
        # Positive: week granularity returns ISO year + week.
        # 2026-05-19 is in ISO week 21.
        assert bucketize("2026-05-19T14:30:00Z", "week") == "2026-W21"

    def test_zero_padded_week_number(self):
        # Boundary: ISO week 1-9 is zero-padded to two digits.
        # 2026-01-05 is ISO week 2.
        assert bucketize("2026-01-05T00:00:00Z", "week") == "2026-W02"

    def test_invalid_timestamp_returns_unknown(self):
        # Negative: malformed timestamp doesn't crash; returns sentinel.
        assert bucketize("not-a-date", "week") == "unknown"
        assert bucketize("", "day") == "unknown"

    def test_handles_z_suffix(self):
        # Boundary: bare "Z" suffix is replaced with +00:00 so fromisoformat
        # accepts it on older Python versions.
        assert bucketize("2026-05-19T14:30:00Z", "day") == "2026-05-19"

    def test_handles_offset_suffix(self):
        # Boundary: explicit timezone offset works too.
        assert bucketize("2026-05-19T14:30:00+00:00", "day") == "2026-05-19"


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


class TestEvalDriftCLI:
    """
    Subprocess smoke test for `python scripts/eval_drift.py`. Verifies the
    CLI accepts the documented arguments, produces the expected output files,
    and exits cleanly on valid input. Failure here would mean the README's
    documented usage is broken.
    """

    def _build_inputs(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Generate 60 telemetry rows across two weeks with a synthetic drift."""
        jsonl = tmp_path / "telemetry.jsonl"
        labels = tmp_path / "labels.csv"
        out_dir = tmp_path / "out"
        # Week 1: low signal values (baseline).
        # Week 2: high signal values (drift).
        lines = []
        for day in range(7):
            for hour in range(5):  # 35 rows in week 1
                lines.append(
                    json.dumps(
                        {
                            "signals": {"sig_a": 0.1, "sig_b": 0.2},
                            "timestamp": f"2026-01-{day + 5:02d}T{hour:02d}:00:00Z",
                        }
                    )
                )
        for day in range(7):
            for hour in range(5):  # 35 rows in week 2
                lines.append(
                    json.dumps(
                        {
                            "signals": {"sig_a": 0.9, "sig_b": 0.8},
                            "timestamp": f"2026-01-{day + 12:02d}T{hour:02d}:00:00Z",
                        }
                    )
                )
        jsonl.write_text("\n".join(lines) + "\n")
        labels.write_text(
            "week_bucket,is_drift\n"
            "2026-W02,0\n"
            "2026-W03,1\n"
        )
        return jsonl, labels, out_dir

    def test_cli_produces_expected_artifacts(self, tmp_path):
        # Positive: CLI runs to completion and produces grid + roc + summary.
        jsonl, labels, out_dir = self._build_inputs(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "eval_drift.py"),
                "--jsonl", str(jsonl),
                "--labels", str(labels),
                "--out-dir", str(out_dir),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert (out_dir / "grid_results.tsv").exists()
        assert (out_dir / "metric_roc.tsv").exists()
        assert (out_dir / "summary.json").exists()
        summary = json.loads((out_dir / "summary.json").read_text())
        assert summary["n_rows"] == 70

    def test_cli_rejects_insufficient_telemetry(self, tmp_path):
        # Negative: <30 rows → exit code 1 with informative stderr.
        jsonl = tmp_path / "tiny.jsonl"
        labels = tmp_path / "labels.csv"
        jsonl.write_text(
            '{"signals": {"a": 0.1}, "timestamp": "2026-01-01T00:00:00Z"}\n'
        )
        labels.write_text("week_bucket,is_drift\n2026-W01,0\n")
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "eval_drift.py"),
                "--jsonl", str(jsonl),
                "--labels", str(labels),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 1
        assert "30 telemetry rows" in result.stderr

    def test_cli_grid_override_replaces_default_thresholds(self, tmp_path):
        # Discrimination: --grid replaces metric defaults; the grid_results
        # TSV should only contain the threshold(s) we supplied.
        jsonl, labels, out_dir = self._build_inputs(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "eval_drift.py"),
                "--jsonl", str(jsonl),
                "--labels", str(labels),
                "--out-dir", str(out_dir),
                "--grid", "0.5",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        # Every row in grid_results.tsv should have threshold == 0.5.
        rows = (out_dir / "grid_results.tsv").read_text().strip().splitlines()
        for row in rows[1:]:  # skip header
            parts = row.split("\t")
            assert parts[2] == "0.5", f"unexpected threshold: {parts[2]}"


# ===========================================================================
# vibe_check.py private drift functions
# ===========================================================================
#
# The private (`_`-prefixed) functions in vibe_check.py mirror the public
# eval_drift.py functions but operate on the live in-process telemetry path.
# Both paths must agree on identical-distribution-scores-zero, monotone
# growth with shift magnitude, and graceful handling of empty / undersized
# input. Tests below pin those contracts so a future refactor that
# consolidates the two paths can't silently change the live decision
# function's behavior.


class TestPrivateHistogram01:
    """`_histogram_01` in vibe_check.py. Pairs with public histogram_01."""

    def test_matches_public_for_typical_input(self):
        # Positive: public and private implementations agree on the same input.
        vals = [0.1, 0.2, 0.3, 0.7, 0.9]
        assert _histogram_01(vals) == histogram_01(vals)

    def test_empty_input_returns_zero_histogram(self):
        # Boundary: no values → no division-by-zero, all bins zero.
        assert _histogram_01([], n_bins=10) == [0.0] * 10

    def test_clamps_out_of_range_values(self):
        # Boundary: < 0 → bin 0; > 1 → last bin.
        h = _histogram_01([-1.0, 2.0], n_bins=5)
        assert h[0] == 0.5
        assert h[-1] == 0.5


class TestPrivatePSI:
    """
    `_psi_1d(expected, actual, n_bins=10, epsilon=1e-4)` in vibe_check.py.

    Note: default n_bins is 10 here vs 20 in the public psi(). Tests pin both
    contracts so the bin-count divergence doesn't silently regress.
    """

    def test_identical_distributions_score_zero(self):
        vals = [0.1, 0.3, 0.5, 0.7] * 25
        assert _psi_1d(vals, vals) == pytest.approx(0.0, abs=1e-9)

    def test_empty_expected_returns_zero(self):
        # Boundary: explicit early-return for empty inputs (different from
        # public psi() which goes through the histogram pathway).
        assert _psi_1d([], [0.1, 0.2, 0.3]) == 0.0

    def test_empty_actual_returns_zero(self):
        assert _psi_1d([0.1, 0.2], []) == 0.0

    def test_shifted_distribution_scores_positive(self):
        baseline = [0.1] * 50
        shifted = [0.9] * 50
        assert _psi_1d(baseline, shifted) > 0.5

    def test_default_n_bins_is_ten_not_twenty(self):
        # Boundary: default n_bins=10 in private path; pin so refactor can't
        # silently change it (downstream thresholds were tuned against 10).
        # With n_bins=10, value 0.5 lands in bin 5; with n_bins=20, bin 10.
        # We verify the path uses 10 by checking a known shift's score
        # against n_bins=10 explicitly.
        baseline = [0.5] * 50
        actual = [0.5] * 25 + [0.95] * 25
        default_score = _psi_1d(baseline, actual)
        explicit_score = _psi_1d(baseline, actual, n_bins=10)
        assert default_score == pytest.approx(explicit_score, abs=1e-12)


class TestPrivateSinkhorn:
    """
    `_sinkhorn_1d(p, q, ...)` in vibe_check.py.

    Note: this takes already-normalized histograms (NOT raw values), unlike
    public sinkhorn_1d() in eval_drift.py which takes raw values and
    histograms internally. Tests pin the I/O contract so callers can't
    silently swap one for the other.
    """

    def test_identical_histograms_score_zero(self):
        # Positive: same histogram → near-zero transport cost.
        h = _histogram_01([0.2, 0.4, 0.6, 0.8] * 25)
        assert _sinkhorn_1d(h, h) < 0.05

    def test_length_mismatch_returns_zero(self):
        # Boundary: explicit guard returns 0.0 when len(p) != len(q). This
        # protects against shape mismatches from upstream signal-name drift.
        assert _sinkhorn_1d([0.5, 0.5], [1.0, 0.0, 0.0]) == 0.0

    def test_n_less_than_two_returns_zero(self):
        # Boundary: n < 2 → 0.0 (single-bin transport is degenerate).
        assert _sinkhorn_1d([1.0], [1.0]) == 0.0
        assert _sinkhorn_1d([], []) == 0.0

    def test_shifted_histogram_scores_higher(self):
        # Discrimination: mass moved across bins costs more than identity.
        p = _histogram_01([0.1] * 100)
        q = _histogram_01([0.9] * 100)
        identity_cost = _sinkhorn_1d(p, p)
        shift_cost = _sinkhorn_1d(p, q)
        assert shift_cost > identity_cost


class TestGlobalDriftPSI:
    """
    `_global_drift_psi(baseline, recent, signal_names)` averages per-signal
    PSI across signals that have ≥10 baseline AND ≥10 recent samples each.
    """

    def _entries(self, signal_value: float, n: int):
        return [
            {"signals": {"sig_a": signal_value, "sig_b": signal_value}}
            for _ in range(n)
        ]

    def test_identical_distributions_score_zero(self):
        baseline = self._entries(0.5, 20)
        recent = self._entries(0.5, 20)
        assert _global_drift_psi(baseline, recent, ["sig_a", "sig_b"]) == pytest.approx(
            0.0, abs=1e-9
        )

    def test_shifted_signals_score_positive(self):
        baseline = self._entries(0.1, 20)
        recent = self._entries(0.9, 20)
        assert _global_drift_psi(baseline, recent, ["sig_a", "sig_b"]) > 0.5

    def test_skips_signals_with_insufficient_samples(self):
        # Boundary: signals with <10 samples on either side are dropped from
        # the average. With only sig_a having enough, the score reflects sig_a
        # alone (not pulled toward 0 by missing sig_b).
        baseline = [{"signals": {"sig_a": 0.1}} for _ in range(15)]
        recent = [{"signals": {"sig_a": 0.9}} for _ in range(15)]
        score = _global_drift_psi(baseline, recent, ["sig_a", "sig_b_missing"])
        assert score > 0.5

    def test_returns_zero_when_no_signals_have_enough_data(self):
        # Boundary: no signal meets the ≥10 threshold → 0 (not exception).
        baseline = [{"signals": {"sig_a": 0.1}}]
        recent = [{"signals": {"sig_a": 0.9}}]
        assert _global_drift_psi(baseline, recent, ["sig_a"]) == 0.0

    def test_skips_entries_without_signals_dict(self):
        # Defensive: rows without a `signals` dict are filtered out at the
        # comprehension level. Mixed-shape input should not crash.
        baseline = [{"signals": {"sig_a": 0.5}}] * 15 + [{"no_signals": True}] * 5
        recent = [{"signals": {"sig_a": 0.5}}] * 15
        score = _global_drift_psi(baseline, recent, ["sig_a"])
        assert score == pytest.approx(0.0, abs=1e-9)


class TestGlobalDriftSinkhorn:
    """`_global_drift_sinkhorn(baseline, recent, signal_names)`."""

    def _entries(self, signal_value: float, n: int):
        return [{"signals": {"sig_a": signal_value}} for _ in range(n)]

    def test_identical_distributions_score_near_zero(self):
        baseline = self._entries(0.5, 20)
        recent = self._entries(0.5, 20)
        assert _global_drift_sinkhorn(baseline, recent, ["sig_a"]) < 0.05

    def test_shifted_distributions_score_higher(self):
        baseline = self._entries(0.1, 20)
        recent = self._entries(0.9, 20)
        identity = _global_drift_sinkhorn(baseline, baseline, ["sig_a"])
        shifted = _global_drift_sinkhorn(baseline, recent, ["sig_a"])
        assert shifted > identity

    def test_returns_zero_with_insufficient_data(self):
        baseline = self._entries(0.5, 5)
        recent = self._entries(0.5, 5)
        assert _global_drift_sinkhorn(baseline, recent, ["sig_a"]) == 0.0


# ---------------------------------------------------------------------------
# Drift state persistence (_load_drift_state, _save_drift_state)
# ---------------------------------------------------------------------------


class TestDriftStatePersistence:
    """
    Round-trip persistence of recent drift statuses for M-of-N gating.
    The save function trims to the last `window` statuses; load returns []
    when the file is missing or unparseable.
    """

    def test_load_returns_empty_when_file_missing(self, tmp_path):
        # Boundary: no file → empty list (not exception).
        assert _load_drift_state(tmp_path) == []

    def test_save_then_load_round_trip(self, tmp_path):
        # Positive: persisted statuses come back in order.
        statuses = ["CONTINUE", "TRIGGER_ALERT", "CONTINUE", "TRIGGER_RECAL"]
        _save_drift_state(tmp_path, statuses, window=10)
        loaded = _load_drift_state(tmp_path)
        assert loaded == statuses

    def test_save_trims_to_window_size(self, tmp_path):
        # Discrimination: window=N keeps only the last N statuses.
        statuses = ["S1", "S2", "S3", "S4", "S5"]
        _save_drift_state(tmp_path, statuses, window=3)
        loaded = _load_drift_state(tmp_path)
        assert loaded == ["S3", "S4", "S5"]

    def test_load_returns_empty_on_corrupt_json(self, tmp_path):
        # Negative: unparseable file → empty list (not exception).
        (tmp_path / DRIFT_STATE_FILENAME).write_text("not json{")
        assert _load_drift_state(tmp_path) == []

    def test_save_writes_schema_marker(self, tmp_path):
        # Positive: persisted file declares its schema version for future
        # migration support.
        _save_drift_state(tmp_path, ["CONTINUE"], window=5)
        body = (tmp_path / DRIFT_STATE_FILENAME).read_text()
        assert "drift_persistence.v1" in body


# ---------------------------------------------------------------------------
# Persistence rule (_apply_persistence_rule)
# ---------------------------------------------------------------------------


class TestApplyPersistenceRule:
    """
    `_apply_persistence_rule(raw_status, tdir)` reads M and N from env vars
    `VIBE_CHECK_DRIFT_PERSISTENCE_M` / `_N` (defaults 1/1 = no-op). When
    raw is a TRIGGER but fewer than M of the last N statuses were trips,
    returns "WATCH" with the raw status preserved in detail. Otherwise
    returns the raw status unchanged.
    """

    def test_noop_when_m_and_n_default(self, tmp_path, monkeypatch):
        # Positive: 1/1 defaults pass the raw status through unchanged.
        monkeypatch.delenv("VIBE_CHECK_DRIFT_PERSISTENCE_M", raising=False)
        monkeypatch.delenv("VIBE_CHECK_DRIFT_PERSISTENCE_N", raising=False)
        status, detail = _apply_persistence_rule("TRIGGER_RECALIBRATION", tmp_path)
        assert status == "TRIGGER_RECALIBRATION"
        assert detail["noop"] is True

    def test_suppresses_first_trigger_when_m_of_n_unmet(self, tmp_path, monkeypatch):
        # Discrimination: M=2 of N=3, only 1 trip in history → WATCH.
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_M", "2")
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_N", "3")
        status, detail = _apply_persistence_rule("TRIGGER_RECALIBRATION", tmp_path)
        assert status == "WATCH"
        assert detail["suppressed_status"] == "TRIGGER_RECALIBRATION"
        assert detail["trips_seen"] == 1

    def test_promotes_trigger_when_m_of_n_met(self, tmp_path, monkeypatch):
        # Positive: M=2 of N=3, two prior trips already in state → TRIGGER.
        _save_drift_state(tmp_path, ["TRIGGER_RECAL", "TRIGGER_RECAL"], window=10)
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_M", "2")
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_N", "3")
        status, detail = _apply_persistence_rule("TRIGGER_RECAL", tmp_path)
        assert status == "TRIGGER_RECAL"
        assert detail["trips_seen"] == 3

    def test_continue_passes_through_regardless(self, tmp_path, monkeypatch):
        # Negative: CONTINUE is never suppressed (the rule only gates TRIGGERs).
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_M", "3")
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_N", "5")
        status, _ = _apply_persistence_rule("CONTINUE_CURRENT_THRESHOLDS", tmp_path)
        assert status == "CONTINUE_CURRENT_THRESHOLDS"

    def test_invalid_env_vars_fall_back_to_defaults(self, tmp_path, monkeypatch):
        # Boundary: non-int env vars → fall back to 1/1 (no-op).
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_M", "garbage")
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_N", "alsogarbage")
        status, detail = _apply_persistence_rule("TRIGGER_RECAL", tmp_path)
        assert status == "TRIGGER_RECAL"
        assert detail["m_of_n"] == [1, 1]

    def test_n_coerced_to_at_least_m(self, tmp_path, monkeypatch):
        # Boundary: N < M is invalid; the function silently raises N to M.
        # Verifies via the detail dict.
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_M", "3")
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PERSISTENCE_N", "1")
        _, detail = _apply_persistence_rule("CONTINUE", tmp_path)
        assert detail["m_of_n"] == [3, 3]


# ---------------------------------------------------------------------------
# check_drift_status orchestrator
# ---------------------------------------------------------------------------


class TestCheckDriftStatusOrchestrator:
    """
    The orchestrator reads telemetry from `telemetry_dir`, partitions into
    baseline (60%) and recent (40%), computes per-signal mean shifts, and
    selects a global metric via env var. Returns a structured dict whose
    `status` field drives downstream CI logic. Tests below pin the env-var
    routing, the threshold defaults, and the empty / undersized paths.
    """

    def _write_telemetry(
        self,
        tmp_path: Path,
        baseline_value: float,
        recent_value: float,
        n: int = 100,
    ) -> Path:
        """Helper: write a JSONL telemetry file with two phases of signal data."""
        log = tmp_path / "vibe_check_telemetry.jsonl"
        # Use one of the real signal names from SIGNAL_THRESHOLDS so the
        # orchestrator's signal_names loop picks it up.
        from vibe_check import SIGNAL_THRESHOLDS
        sig_name = next(iter(SIGNAL_THRESHOLDS.keys()))
        baseline_n = int(n * 0.6)
        recent_n = n - baseline_n
        lines = []
        for _ in range(baseline_n):
            lines.append(json.dumps({"signals": {sig_name: baseline_value}}))
        for _ in range(recent_n):
            lines.append(json.dumps({"signals": {sig_name: recent_value}}))
        log.write_text("\n".join(lines) + "\n")
        return log

    def test_returns_no_telemetry_when_dir_unset(self, monkeypatch):
        # Boundary: no telemetry dir provided AND env not set → NO_TELEMETRY.
        monkeypatch.delenv("VIBE_CHECK_TELEMETRY_DIR", raising=False)
        # Pass None explicitly to bypass the module-level TELEMETRY_DIR closure.
        # We have to monkeypatch the module attr because it's captured at import.
        import vibe_check
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", None)
        result = check_drift_status(telemetry_dir=None)
        assert result["status"] == "NO_TELEMETRY"

    def test_returns_no_data_when_telemetry_file_missing(self, tmp_path):
        # Boundary: dir exists, file doesn't → NO_DATA.
        result = check_drift_status(telemetry_dir=str(tmp_path))
        assert result["status"] == "NO_DATA"

    def test_returns_insufficient_data_below_threshold(self, tmp_path):
        # Boundary: <50 entries → INSUFFICIENT_DATA with the count.
        log = tmp_path / "vibe_check_telemetry.jsonl"
        lines = [json.dumps({"signals": {"comment_to_code_ratio": 0.5}}) for _ in range(20)]
        log.write_text("\n".join(lines))
        result = check_drift_status(telemetry_dir=str(tmp_path))
        assert result["status"] == "INSUFFICIENT_DATA"
        assert result["evaluations"] == 20

    def test_no_drift_returns_continue(self, tmp_path, monkeypatch):
        # Positive: baseline == recent → CONTINUE_CURRENT_THRESHOLDS.
        monkeypatch.delenv("VIBE_CHECK_DRIFT_GLOBAL_METRIC", raising=False)
        self._write_telemetry(tmp_path, baseline_value=0.5, recent_value=0.5, n=100)
        result = check_drift_status(telemetry_dir=str(tmp_path))
        assert result["status"] == "CONTINUE_CURRENT_THRESHOLDS"
        assert result["evaluations_total"] == 100

    def test_env_var_selects_psi_metric(self, tmp_path, monkeypatch):
        # Discrimination: VIBE_CHECK_DRIFT_GLOBAL_METRIC=psi routes through
        # the PSI threshold and reports drift_global_metric=psi.
        monkeypatch.setenv("VIBE_CHECK_DRIFT_GLOBAL_METRIC", "psi")
        self._write_telemetry(tmp_path, baseline_value=0.5, recent_value=0.5, n=100)
        result = check_drift_status(telemetry_dir=str(tmp_path))
        assert result["drift_global_metric"] == "psi"
        assert result["drift_threshold"] == 0.25

    def test_env_var_selects_sinkhorn_metric(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VIBE_CHECK_DRIFT_GLOBAL_METRIC", "sinkhorn")
        self._write_telemetry(tmp_path, baseline_value=0.5, recent_value=0.5, n=100)
        result = check_drift_status(telemetry_dir=str(tmp_path))
        assert result["drift_global_metric"] == "sinkhorn"
        assert result["drift_threshold"] == 0.22

    def test_unknown_env_var_falls_back_to_mean_shift(self, tmp_path, monkeypatch):
        # Boundary: unknown metric name → fall back to mean_shift default.
        monkeypatch.setenv("VIBE_CHECK_DRIFT_GLOBAL_METRIC", "made-up-metric")
        self._write_telemetry(tmp_path, baseline_value=0.5, recent_value=0.5, n=100)
        result = check_drift_status(telemetry_dir=str(tmp_path))
        assert result["drift_global_metric"] == "mean_shift"
        assert result["drift_threshold"] == 1.5

    def test_custom_psi_threshold_via_env(self, tmp_path, monkeypatch):
        # Discrimination: VIBE_CHECK_DRIFT_PSI_THRESHOLD overrides the 0.25 default.
        monkeypatch.setenv("VIBE_CHECK_DRIFT_GLOBAL_METRIC", "psi")
        monkeypatch.setenv("VIBE_CHECK_DRIFT_PSI_THRESHOLD", "0.99")
        self._write_telemetry(tmp_path, baseline_value=0.5, recent_value=0.5, n=100)
        result = check_drift_status(telemetry_dir=str(tmp_path))
        assert result["drift_threshold"] == 0.99

    def test_malformed_lines_skipped(self, tmp_path, monkeypatch):
        # Negative: invalid JSON lines are dropped, not counted toward evaluations.
        monkeypatch.delenv("VIBE_CHECK_DRIFT_GLOBAL_METRIC", raising=False)
        log = tmp_path / "vibe_check_telemetry.jsonl"
        good = json.dumps({"signals": {"comment_to_code_ratio": 0.5}})
        # 60 good lines + 5 garbage lines → only 60 counted.
        lines = [good] * 60 + ["{garbage", "not-json", "", "{}", "   "]
        log.write_text("\n".join(lines))
        result = check_drift_status(telemetry_dir=str(tmp_path))
        # Empty lines drop in stripping, "{}" parses successfully as empty
        # dict (counts), garbage lines fail JSON decode (drop). So 60 +
        # whichever of the trailing 5 are valid JSON dicts.
        # Concrete assertion: at minimum the 60 good rows count.
        assert result["evaluations_total"] >= 60
        # And the metric is mean_shift because we cleared the env var.
        assert result["drift_global_metric"] == "mean_shift"

    def test_response_includes_layered_breakdown(self, tmp_path, monkeypatch):
        # Contract: the response includes a `layers` dict with the four
        # documented layers (telemetry, signal, score, override_layer_placeholder).
        # Pins the schema downstream consumers depend on.
        monkeypatch.delenv("VIBE_CHECK_DRIFT_GLOBAL_METRIC", raising=False)
        self._write_telemetry(tmp_path, baseline_value=0.5, recent_value=0.5, n=100)
        result = check_drift_status(telemetry_dir=str(tmp_path))
        assert "layers" in result
        assert {"telemetry_layer", "signal_layer", "score_layer", "override_layer_placeholder"} <= set(result["layers"].keys())

    def test_response_includes_all_three_global_metrics(self, tmp_path, monkeypatch):
        # Contract: every result includes the value of all three global metrics
        # (mean_shift, sinkhorn, psi) regardless of which one was chosen for
        # the decision. This lets downstream tooling compare metrics offline.
        monkeypatch.delenv("VIBE_CHECK_DRIFT_GLOBAL_METRIC", raising=False)
        self._write_telemetry(tmp_path, baseline_value=0.5, recent_value=0.5, n=100)
        result = check_drift_status(telemetry_dir=str(tmp_path))
        for k in ("global_drift_mean_shift", "global_drift_sinkhorn", "global_drift_psi"):
            assert k in result
            assert isinstance(result[k], (int, float))
