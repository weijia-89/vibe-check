"""
Tests for calibration functions in scripts/calibration_pipeline.py,
scripts/vibe_calibration.py, and scripts/vibe_check.py.

Scope: the pure statistical functions (cohen's d, ROC-Youden, beta HDI,
MDE, skewness, pooled SD, AUC), the pure classification helpers
(classify_label, label_priority, parse_iso, size_stratum, infer_pr_type,
stratified_sample, stats_dict), and the module-state-mutating override
loader (load_calibration_overrides in vibe_check.py). The gh-CLI-dependent
network functions (phase1, fetch_pr_detail, run_vibe in
calibration_pipeline.py) are covered in tests/test_gh_integration.py.

Discipline (per the action plan):
    Each function gets ≥3 tests covering positive, negative, and boundary.
    Adversarial discrimination > defensive coverage. Stats functions get
    additional tests pinning known mathematical properties (e.g. Cohen's d
    of identical distributions = 0; AUC bounded in [0, 1]).

The statistical functions are the load-bearing claim of the calibration
pipeline's evidence ledger. These tests pin the math so that a future
refactor can't quietly change a threshold or a confidence interval the
calibration ledger was anchored against. load_calibration_overrides is
the runtime hook that promotes calibration_pipeline.py's findings into
vibe_check.py's live decision surface; tests pin the contract for
threshold update, weight clamping, version-gated apply, and
no-mutation-on-failure paths.
"""
from __future__ import annotations

import copy
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from calibration_pipeline import (  # noqa: E402
    API_TOTAL,
    CURRENT_DECISION_T,
    SIGNAL_SHORT,
    Budget,
    beta_hdi_equal_tailed,
    classify_label,
    cohens_d,
    cosine_sim,
    extract_signals,
    label_priority,
    mde_cohens_d,
    mean_vec,
    parse_iso,
    phase4,
    pooled_sd,
    roc_auc_mannwhitney,
    roc_youden,
    signals_row,
    size_bucket,
    skewness,
    stratified_unlabeled,
    time_bucket,
    write_tsv,
)
import vibe_check  # noqa: E402  (module import for monkeypatching globals)
from vibe_check import (  # noqa: E402
    CALIBRATION_VERSION,
    OVERRIDE_FILENAME,
    load_calibration_overrides,
)
from vibe_calibration import (  # noqa: E402
    infer_pr_type,
    size_stratum,
    stats_dict,
    stratified_sample,
)


# ---------------------------------------------------------------------------
# classify_label
# ---------------------------------------------------------------------------


class TestClassifyLabel:
    """
    classify_label(name) -> (bucket, label_class)

    Pure string classifier. Routes label names to one of four buckets:
    vibe-coded, ai-assisted, human-written, ignore. The fall-through ordering
    is significant; tests pin it.
    """

    def test_vibe_coded_canonical_forms(self):
        # Positive: explicit canonical spellings are caught by the exact-match path.
        for name in ("vibe coded", "vibe-coded", "vibecoded", "VIBE CODED"):
            assert classify_label(name) == ("vibe", "vibe-coded")

    def test_human_written_canonical_forms(self):
        for name in ("human written", "human-written", "manual", "hand coded", "hand-coded"):
            assert classify_label(name) == ("human", "human-written")

    def test_ai_assisted_canonical_forms(self):
        for name in ("ai generated", "ai-generated", "ai assisted", "ai-assisted", "copilot", "cursor"):
            assert classify_label(name) == ("ai", "ai-assisted")

    def test_fuzzy_vibe_match_via_substring(self):
        # Discrimination: "vibe-experiment" contains "vibe" → falls through to vibe path.
        assert classify_label("vibe-experiment") == ("vibe", "vibe-coded")

    def test_anti_ai_label_routes_to_ignore(self):
        # Negative: "no-ai" / "anti-ai" / "human ai" must NOT route to ai-assisted
        # despite containing "ai". This is the override clause; pin it so
        # refactors can't drop the special case.
        assert classify_label("anti-ai") == ("ignore", "ignore")
        assert classify_label("no ai") == ("ignore", "ignore")
        assert classify_label("human ai") == ("ignore", "ignore")

    def test_unmatched_label_returns_ignore(self):
        # Negative: bug/feature/docs labels (orthogonal to AI provenance)
        # must NOT be misclassified as a provenance label.
        for name in ("bug", "feature", "documentation", "wontfix", "good first issue"):
            assert classify_label(name) == ("ignore", "ignore")

    def test_llm_or_generated_routes_to_ai(self):
        # Discrimination: "llm" or "generated" in label → ai-assisted.
        assert classify_label("llm-output") == ("ai", "ai-assisted")
        assert classify_label("generated-by-model") == ("ai", "ai-assisted")

    def test_partial_match_human_substring_routes_to_human(self):
        # Discrimination: labels that CONTAIN a human-written marker but
        # don't exact-match the canonical set fall through to the substring
        # check at line 143-144. Pins this fallthrough so a refactor that
        # tightens the human bucket to exact-match-only would fail loudly.
        assert classify_label("manual-touched") == ("human", "human-written")
        assert classify_label("hand-coded-by-team") == ("human", "human-written")
        assert classify_label("legacy-human-written") == ("human", "human-written")

    def test_partial_match_copilot_or_cursor_substring_routes_to_ai(self):
        # Discrimination: labels containing "copilot" or "cursor" as a
        # substring (e.g. "copilot-suggested", "cursor-team") hit the
        # partial-match branch at line 147-148, separate from the exact
        # canonical set at line 141. Pins both branches.
        assert classify_label("copilot-suggested") == ("ai", "ai-assisted")
        assert classify_label("cursor-team-pr") == ("ai", "ai-assisted")

    def test_auto_plus_code_or_gen_substring_routes_to_ai(self):
        # Discrimination: the compound pattern at line 151-152 — "auto" AND
        # ("code" OR "gen") — catches "autogen" and "auto-code" style labels.
        # Neither would hit the LLM/generated branch above (they don't
        # contain those exact substrings).
        assert classify_label("autogen") == ("ai", "ai-assisted")
        assert classify_label("auto-code") == ("ai", "ai-assisted")
        assert classify_label("automated-codegen") == ("ai", "ai-assisted")

    def test_unblocked_ai_substring_routes_to_ai(self):
        # Discrimination: a label containing "ai" that does NOT also
        # contain "human" / "anti-ai" / "no ai" hits the unblocked branch
        # at line 156. The blocked path is covered by
        # test_anti_ai_label_routes_to_ignore above; this test covers
        # the symmetric default-to-ai case.
        assert classify_label("ai-pr") == ("ai", "ai-assisted")
        assert classify_label("ai-tools") == ("ai", "ai-assisted")


class TestLabelPriority:
    """label_priority maps classification strings to integer priorities."""

    def test_vibe_coded_has_highest_priority(self):
        # Positive: lower number = higher priority. Vibe (0) > AI (1) > Human (2).
        assert label_priority("vibe-coded") < label_priority("ai-assisted")
        assert label_priority("ai-assisted") < label_priority("human-written")

    def test_unknown_label_class_returns_sentinel(self):
        # Boundary: unrecognized class returns 9 (lowest priority).
        assert label_priority("something-else") == 9
        assert label_priority("") == 9


# ---------------------------------------------------------------------------
# parse_iso
# ---------------------------------------------------------------------------


class TestParseISO:
    """parse_iso(s) -> Optional[datetime]. Returns None on failure."""

    def test_parses_z_suffix(self):
        from datetime import datetime, timezone
        dt = parse_iso("2026-05-19T14:30:00Z")
        assert dt == datetime(2026, 5, 19, 14, 30, 0, tzinfo=timezone.utc)

    def test_parses_offset_suffix(self):
        from datetime import datetime, timezone
        dt = parse_iso("2026-05-19T14:30:00+00:00")
        assert dt is not None
        assert dt.year == 2026

    def test_returns_none_on_empty(self):
        # Boundary: empty / None-like input → None (the empty-check path).
        assert parse_iso("") is None

    def test_returns_none_on_garbage(self):
        # Negative: malformed ISO → None, no exception.
        assert parse_iso("not a date") is None
        assert parse_iso("2026-13-99T99:99:99Z") is None


# ---------------------------------------------------------------------------
# mean_vec
# ---------------------------------------------------------------------------


class TestMeanVec:
    """mean_vec(rows, keys) -> list[float]. Per-key arithmetic mean."""

    def test_empty_rows_returns_zero_vector(self):
        # Boundary: no rows → vector of zeros (not nan, not exception).
        assert mean_vec([], ["a", "b", "c"]) == [0.0, 0.0, 0.0]

    def test_means_computed_per_key(self):
        rows = [{"a": 1.0, "b": 2.0}, {"a": 3.0, "b": 4.0}]
        assert mean_vec(rows, ["a", "b"]) == [2.0, 3.0]

    def test_missing_key_treated_as_zero(self):
        # Defensive: a row missing a key contributes 0 (via `r.get(k, 0)`).
        rows = [{"a": 1.0}, {"a": 3.0, "b": 4.0}]
        assert mean_vec(rows, ["a", "b"]) == [2.0, 2.0]

    def test_none_value_treated_as_zero(self):
        # Defensive: `or 0` clause handles None in the dict.
        rows = [{"a": None}, {"a": 4.0}]
        assert mean_vec(rows, ["a"]) == [2.0]


# ---------------------------------------------------------------------------
# cosine_sim
# ---------------------------------------------------------------------------


class TestCosineSim:
    """cosine_sim(a, b) -> float in [-1, 1]. Returns 0 if either norm ~0."""

    def test_identical_vectors_score_one(self):
        assert cosine_sim([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_antiparallel_vectors_score_negative_one(self):
        assert cosine_sim([1.0, 2.0, 3.0], [-1.0, -2.0, -3.0]) == pytest.approx(-1.0)

    def test_orthogonal_vectors_score_zero(self):
        # Boundary: dot product = 0.
        assert cosine_sim([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_norm_returns_zero(self):
        # Negative: degenerate input → 0 (not nan, not div-by-zero).
        assert cosine_sim([0.0, 0.0], [1.0, 1.0]) == 0.0
        assert cosine_sim([1.0, 1.0], [0.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# skewness
# ---------------------------------------------------------------------------


class TestSkewness:
    """skewness(vals) -> third standardized moment. Returns 0 if n<3 or m2~0."""

    def test_symmetric_distribution_near_zero(self):
        # Positive: symmetric integer sequence has skewness ≈ 0.
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert skewness(vals) == pytest.approx(0.0, abs=1e-9)

    def test_right_skewed_distribution_positive(self):
        # Discrimination: mass on the left + long right tail → positive skew.
        vals = [1.0, 1.0, 1.0, 1.0, 10.0]
        assert skewness(vals) > 0

    def test_left_skewed_distribution_negative(self):
        # Discrimination: long left tail → negative skew.
        vals = [-10.0, 1.0, 1.0, 1.0, 1.0]
        assert skewness(vals) < 0

    def test_min_sample_guard_returns_zero(self):
        # Boundary: n < 3 → 0 (not exception, not nan).
        assert skewness([]) == 0.0
        assert skewness([1.0]) == 0.0
        assert skewness([1.0, 2.0]) == 0.0

    def test_constant_input_returns_zero(self):
        # Boundary: m2 = 0 → 0 (avoids division by zero in the m3/m2**1.5 path).
        assert skewness([5.0, 5.0, 5.0, 5.0]) == 0.0


# ---------------------------------------------------------------------------
# pooled_sd
# ---------------------------------------------------------------------------


class TestPooledSD:
    """pooled_sd(a, b) -> pooled standard deviation. Returns 0 if n<4."""

    def test_identical_groups_pooled_sd_matches_within_sd(self):
        # Positive: pooling two identical samples returns ~ their common sample SD.
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [1.0, 2.0, 3.0, 4.0, 5.0]
        # Sample variance of [1..5] = 2.5; pooled with equal weights → 2.5.
        expected = math.sqrt(2.5)
        assert pooled_sd(a, b) == pytest.approx(expected, rel=1e-4)

    def test_min_sample_guard_when_both_undersized(self):
        # Boundary: n_a + n_b < 4 → 0.
        assert pooled_sd([1.0], [2.0]) == 0.0
        assert pooled_sd([], [1.0, 2.0]) == 0.0

    def test_handles_one_sided_singleton(self):
        # Boundary: when one group is a singleton its variance is 0 but the
        # other group's contributes normally (n_a + n_b >= 4 path).
        a = [1.0]
        b = [1.0, 2.0, 3.0, 4.0]
        # va = 0, vb = variance([1..4]) = 5/3. Pooled with weights 0, 3.
        result = pooled_sd(a, b)
        assert result > 0
        assert math.isfinite(result)


# ---------------------------------------------------------------------------
# cohens_d
# ---------------------------------------------------------------------------


class TestCohensD:
    """
    cohens_d(a, b) -> standardized mean difference.

    By convention, d > 0 means a's mean > b's mean. d = 0 for identical
    distributions or when pooled SD is ~0.
    """

    def test_identical_groups_score_zero(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert cohens_d(a, a) == pytest.approx(0.0, abs=1e-9)

    def test_shifted_groups_score_positive(self):
        # Discrimination: a mean > b mean → d > 0.
        a = [5.0, 6.0, 7.0, 8.0]
        b = [1.0, 2.0, 3.0, 4.0]
        assert cohens_d(a, b) > 0

    def test_sign_inverts_when_groups_swap(self):
        # Property: cohens_d(b, a) == -cohens_d(a, b).
        a = [5.0, 6.0, 7.0, 8.0]
        b = [1.0, 2.0, 3.0, 4.0]
        assert cohens_d(a, b) == pytest.approx(-cohens_d(b, a), abs=1e-9)

    def test_zero_variance_returns_zero(self):
        # Boundary: pooled SD = 0 (constant groups) → 0 (not nan, not inf).
        assert cohens_d([5.0, 5.0, 5.0, 5.0], [5.0, 5.0, 5.0, 5.0]) == 0.0


# ---------------------------------------------------------------------------
# roc_auc_mannwhitney
# ---------------------------------------------------------------------------


class TestROCAUCMannWhitney:
    """
    roc_auc_mannwhitney(scores, labels) -> AUC in [0, 1].

    Uses the Mann-Whitney U formulation. Ties contribute 0.5 to the
    concordance count. Returns 0.5 when either class is empty (no
    discrimination is computable).
    """

    def test_perfect_separation_scores_one(self):
        # Positive: all positives strictly above all negatives → AUC = 1.
        scores = [0.1, 0.2, 0.9, 1.0]
        labels = [0, 0, 1, 1]
        assert roc_auc_mannwhitney(scores, labels) == pytest.approx(1.0)

    def test_perfect_anti_separation_scores_zero(self):
        # Discrimination: positives all below negatives → AUC = 0.
        scores = [0.9, 1.0, 0.1, 0.2]
        labels = [0, 0, 1, 1]
        assert roc_auc_mannwhitney(scores, labels) == pytest.approx(0.0)

    def test_ties_contribute_half(self):
        # Boundary: all ties → AUC = 0.5.
        scores = [0.5, 0.5, 0.5, 0.5]
        labels = [0, 0, 1, 1]
        assert roc_auc_mannwhitney(scores, labels) == pytest.approx(0.5)

    def test_empty_positives_returns_half(self):
        # Boundary: no positive class → 0.5 (no discrimination computable).
        assert roc_auc_mannwhitney([0.1, 0.5, 0.9], [0, 0, 0]) == 0.5

    def test_empty_negatives_returns_half(self):
        assert roc_auc_mannwhitney([0.1, 0.5, 0.9], [1, 1, 1]) == 0.5

    def test_within_unit_interval_for_realistic_inputs(self):
        # Negative: AUC must always be in [0, 1].
        scores = [0.1, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9]
        labels = [0, 0, 0, 1, 1, 1, 1]
        auc = roc_auc_mannwhitney(scores, labels)
        assert 0.0 <= auc <= 1.0


# ---------------------------------------------------------------------------
# roc_youden
# ---------------------------------------------------------------------------


class TestROCYouden:
    """
    roc_youden(scores, labels) -> (auc, threshold, sens, spec, j).

    Selects the threshold that maximizes Youden's J = sens + spec - 1.
    """

    def test_perfect_separation_returns_perfect_youden(self):
        scores = [0.1, 0.2, 0.8, 0.9]
        labels = [0, 0, 1, 1]
        auc, t, sens, spec, j = roc_youden(scores, labels)
        assert auc == pytest.approx(1.0)
        assert j == pytest.approx(1.0)
        assert sens == pytest.approx(1.0)
        assert spec == pytest.approx(1.0)
        # Optimal threshold is somewhere between the highest negative (0.2)
        # and the lowest positive (0.8). The function picks one of the
        # unique scores; we verify it lies in the separator gap.
        assert 0.2 < t <= 0.8

    def test_empty_positives_returns_default_threshold(self):
        # Boundary: n_pos = 0 → return sentinel (0.5, CURRENT_DECISION_T, 0, 0, 0).
        auc, t, sens, spec, j = roc_youden([0.1, 0.5], [0, 0])
        assert auc == 0.5
        assert t == CURRENT_DECISION_T
        assert sens == 0.0
        assert spec == 0.0
        assert j == 0.0

    def test_empty_negatives_returns_default_threshold(self):
        auc, t, sens, spec, j = roc_youden([0.1, 0.5], [1, 1])
        assert auc == 0.5
        assert t == CURRENT_DECISION_T

    def test_youden_j_in_valid_range(self):
        # Negative: J is bounded in [-1, 1] for any well-posed input.
        scores = [0.1, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9]
        labels = [0, 1, 0, 1, 0, 1, 1]
        _, _, _, _, j = roc_youden(scores, labels)
        assert -1.0 <= j <= 1.0


# ---------------------------------------------------------------------------
# beta_hdi_equal_tailed
# ---------------------------------------------------------------------------


class TestBetaHDI:
    """
    beta_hdi_equal_tailed(successes, trials, alpha=0.10) -> (lo, hi).

    90% equal-tailed CI on Beta(s+1, f+1) via normal approximation. Bounded
    to [0, 1].
    """

    def test_zero_successes_lower_bound_at_zero(self):
        lo, hi = beta_hdi_equal_tailed(0, 100)
        assert lo == 0.0
        assert hi > 0  # finite upper bound

    def test_all_successes_upper_bound_at_one(self):
        lo, hi = beta_hdi_equal_tailed(100, 100)
        assert hi == 1.0
        assert lo < 1.0

    def test_interval_brackets_observed_proportion(self):
        # Positive: CI should bracket the maximum-likelihood proportion for
        # reasonable n (the normal approximation is close to symmetric here).
        s, n = 50, 100  # observed p = 0.5
        lo, hi = beta_hdi_equal_tailed(s, n)
        # Beta(51, 51) mean = 51/102 ≈ 0.5. CI should contain 0.5.
        assert lo < 0.5 < hi

    def test_interval_tightens_with_more_trials(self):
        # Discrimination: more data → tighter CI.
        lo_small, hi_small = beta_hdi_equal_tailed(5, 10)
        lo_big, hi_big = beta_hdi_equal_tailed(50, 100)
        assert (hi_big - lo_big) < (hi_small - lo_small)

    def test_inverted_inputs_return_degenerate_interval(self):
        # Adversarial: when successes > trials (which shouldn't happen
        # in normal use but is defensively handled), b = (trials -
        # successes) + 1 becomes ≤ 0, which makes a*b ≤ 0 and var ≤ 0.
        # The function returns the mean as both endpoints — a degenerate
        # "interval" that signals the inputs were invalid. Pins the
        # var ≤ 0 branch at line 273-274.
        lo, hi = beta_hdi_equal_tailed(successes=10, trials=5)
        assert lo == hi  # degenerate: zero-width interval
        # mean = a/(a+b) where a=11, b=-4 → mean = 11/7 ≈ 1.571.
        # This is clearly nonsensical (outside [0,1]) which IS the
        # signal: the caller should validate inputs before relying on
        # the result.
        assert lo == pytest.approx(11 / 7)

    def test_zero_trials_degenerate_interval(self):
        # Boundary: 0 trials → Beta(1, 1) = uniform; var > 0, so CI is wide
        # but still well-defined. Just verify it doesn't crash.
        lo, hi = beta_hdi_equal_tailed(0, 0)
        assert 0.0 <= lo <= hi <= 1.0


# ---------------------------------------------------------------------------
# mde_cohens_d
# ---------------------------------------------------------------------------


class TestMDE:
    """mde_cohens_d(n) -> minimum detectable Cohen's d for a 2-group test."""

    def test_decreases_with_sample_size(self):
        # Discrimination: more n → smaller detectable effect.
        assert mde_cohens_d(10) > mde_cohens_d(100)
        assert mde_cohens_d(100) > mde_cohens_d(1000)

    def test_min_sample_guard_returns_nan(self):
        # Boundary: n < 2 → NaN (not zero, not exception).
        result = mde_cohens_d(1)
        assert math.isnan(result)
        assert math.isnan(mde_cohens_d(0))

    def test_returns_positive_for_valid_n(self):
        # Negative: MDE is a magnitude; must be positive for valid n.
        assert mde_cohens_d(50) > 0


# ---------------------------------------------------------------------------
# Budget dataclass
# ---------------------------------------------------------------------------


class TestBudget:
    """
    Budget tracks gh-CLI call counts per phase + a separate pr_detail cap.
    Used to enforce anti-cascade limits on the calibration pipeline.
    """

    def test_initial_state_has_room(self):
        b = Budget()
        assert b.gh("1") is True
        assert b.total == 1
        assert b.p1 == 1

    def test_phase_specific_cap_enforced(self):
        # Discrimination: phase 1 has its own cap (P1_API=200). Exhausting it
        # blocks further phase-1 calls but not phase-2 calls.
        b = Budget()
        from calibration_pipeline import P1_API
        for _ in range(P1_API):
            assert b.gh("1") is True
        # Next phase-1 call should be denied even though total < API_TOTAL.
        assert b.gh("1") is False
        assert b.gh("2") is True  # phase 2 still has its own budget

    def test_pr_detail_cap_independent(self):
        # Discrimination: pr_detail_ok() uses its own cap (PR_DETAIL_CAP=300),
        # independent of gh budgets.
        from calibration_pipeline import PR_DETAIL_CAP
        b = Budget()
        b.pr_detail = PR_DETAIL_CAP - 1
        assert b.pr_detail_ok() is True
        b.pr_detail = PR_DETAIL_CAP
        assert b.pr_detail_ok() is False

    def test_errors_list_populated_via_post_init(self):
        # Negative: the dataclass default for `errors` is None; __post_init__
        # must reify it to [] so callers can append.
        b = Budget()
        b.errors.append("test error")
        assert b.errors == ["test error"]

    def test_total_cap_blocks_all_phases(self):
        # Adversarial: when total >= API_TOTAL, gh() returns False
        # regardless of phase or per-phase counter state. Pins the
        # global anti-cascade ceiling that runs orthogonal to per-phase
        # caps. If a refactor makes total a soft limit, this fails.
        b = Budget()
        b.total = API_TOTAL
        assert b.gh("1") is False
        assert b.gh("2") is False
        assert b.gh("3") is False

    def test_phase_3_increment_works(self):
        # Discrimination: phase "3" hits the elif branch at line 96-97
        # incrementing self.p3 (separate from p1/p2 paths). Pins both
        # the elif clause's existence and its specific counter target.
        b = Budget()
        assert b.gh("3") is True
        assert b.p3 == 1
        assert b.p1 == 0
        assert b.p2 == 0
        assert b.total == 1

    def test_unknown_phase_uses_total_cap_and_skips_per_phase_increment(self):
        # Boundary: an unrecognized phase (e.g. "9") falls through the
        # .get() defaults at lines 87-88 (lim=API_TOTAL, cur=self.total).
        # The call counts toward `total` but no per-phase counter is
        # incremented (the if/elif chain at 92-97 has no else clause).
        # Pins this defensive shape so a future explicit "unknown phase"
        # rejection would have to update this test.
        b = Budget()
        assert b.gh("9") is True
        assert b.total == 1
        assert b.p1 == 0
        assert b.p2 == 0
        assert b.p3 == 0


# ---------------------------------------------------------------------------
# size_stratum (vibe_calibration.py)
# ---------------------------------------------------------------------------


class TestSizeStratum:
    """size_stratum bucketizes PR change-size into one of five strata."""

    def test_each_bucket_boundary(self):
        # Positive: each of the 5 buckets is reachable.
        assert size_stratum(10, 10) == "<50"      # 20 < 50
        assert size_stratum(100, 50) == "50-200"  # 150 in [50, 200)
        assert size_stratum(300, 100) == "200-500"
        assert size_stratum(1000, 500) == "500-2000"
        assert size_stratum(2000, 500) == ">2000"

    def test_boundary_values_use_inclusive_lower(self):
        # Boundary: 50 falls into "50-200" (inclusive lower), 200 falls into
        # "200-500", etc. Pins the < vs <= contract.
        assert size_stratum(50, 0) == "50-200"
        assert size_stratum(200, 0) == "200-500"
        assert size_stratum(500, 0) == "500-2000"
        assert size_stratum(2000, 0) == ">2000"

    def test_handles_none_inputs(self):
        # Defensive: `or 0` handles None values from the PR JSON.
        assert size_stratum(None, None) == "<50"
        assert size_stratum(None, 100) == "50-200"


# ---------------------------------------------------------------------------
# infer_pr_type (vibe_calibration.py)
# ---------------------------------------------------------------------------


class TestInferPRType:
    """
    infer_pr_type(pr) -> classification string.

    Routes by: hotfix branch prefix → labels → title keyword fallback → "feature".
    """

    def test_hotfix_branch_takes_priority(self):
        # Positive: hotfix/ prefix wins over labels and title.
        pr = {"headRefName": "hotfix/critical-bug", "labels": [{"name": "feature"}], "title": "Add new feature"}
        assert infer_pr_type(pr) == "hotfix"

    def test_label_takes_priority_over_title(self):
        # Discrimination: a "bug" label wins even when title says "add new".
        pr = {"headRefName": "feat/x", "labels": [{"name": "bug"}], "title": "add new thing"}
        assert infer_pr_type(pr) == "bug_fix"

    def test_title_fallback_for_fix_keyword(self):
        # Boundary: no labels, no hotfix branch → title keyword routing.
        pr = {"headRefName": "branch", "labels": [], "title": "Fix the parser"}
        assert infer_pr_type(pr) == "bug_fix"

    def test_title_fallback_for_feature_keyword(self):
        pr = {"headRefName": "x", "labels": [], "title": "Add new endpoint"}
        assert infer_pr_type(pr) == "feature"

    def test_default_is_feature(self):
        # Negative: completely uncategorizable PR defaults to "feature".
        pr = {"headRefName": "x", "labels": [], "title": "Cleanup"}
        assert infer_pr_type(pr) == "feature"

    def test_handles_missing_keys_gracefully(self):
        # Defensive: empty PR dict → "feature" (no exception).
        assert infer_pr_type({}) == "feature"


# ---------------------------------------------------------------------------
# stats_dict (vibe_calibration.py)
# ---------------------------------------------------------------------------


class TestStatsDict:
    """
    stats_dict returns mean/median/std/q25/q75/p5/p95 in one dict. NaN
    values are filtered out before stats are computed. Empty input → all NaN.
    """

    def test_known_values(self):
        d = stats_dict([1.0, 2.0, 3.0, 4.0, 5.0])
        assert d["mean"] == 3.0
        assert d["median"] == 3.0
        # Sample std of [1..5] = sqrt(2.5) ≈ 1.5811.
        assert d["std"] == pytest.approx(math.sqrt(2.5), abs=1e-4)

    def test_quartiles_are_monotone(self):
        d = stats_dict(list(range(1, 101)))
        assert d["p5"] < d["q25"] < d["median"] < d["q75"] < d["p95"]

    def test_filters_nan(self):
        # Defensive: NaN values are excluded from the computation.
        d = stats_dict([1.0, 2.0, float("nan"), 3.0])
        assert d["mean"] == 2.0

    def test_empty_returns_all_nan(self):
        # Boundary: empty input → every field is NaN, no exception.
        d = stats_dict([])
        for k, v in d.items():
            assert math.isnan(v), f"{k} not nan: {v}"

    def test_single_value_no_std(self):
        # Boundary: n=1 → std = 0 (stdev would raise; the function guards this).
        d = stats_dict([42.0])
        assert d["mean"] == 42.0
        assert d["std"] == 0.0


# ---------------------------------------------------------------------------
# stratified_sample (vibe_calibration.py)
# ---------------------------------------------------------------------------


class TestStratifiedSample:
    """
    stratified_sample picks `target_n` PRs while preserving distribution
    across (size_stratum, infer_pr_type) cells. Deterministic given a seeded
    rng. Includes an author-diversity top-up if fewer than 10 distinct
    authors are picked.
    """

    def _make_prs(self, n: int, base: int = 0) -> list[dict]:
        """Generate n synthetic PRs with varying sizes, types, and authors."""
        prs = []
        for i in range(n):
            additions = (i * 17) % 2500   # spread across all size strata
            deletions = (i * 7) % 100
            labels = []
            if i % 3 == 0:
                labels = [{"name": "bug"}]
            elif i % 3 == 1:
                labels = [{"name": "feature"}]
            prs.append({
                "number": base + i,
                "additions": additions,
                "deletions": deletions,
                "labels": labels,
                "headRefName": "main",
                "title": f"PR {i}",
                "author": {"login": f"user_{i % 5}"},  # 5 distinct authors
            })
        return prs

    def test_deterministic_with_seeded_rng(self):
        # Positive: same seed → same picks. The stratified sampler is the
        # foundation of reproducible calibration runs.
        pool = self._make_prs(50)
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        picks1 = stratified_sample(pool, 10, rng1)
        picks2 = stratified_sample(pool, 10, rng2)
        assert [p["number"] for p in picks1] == [p["number"] for p in picks2]

    def test_empty_pool_returns_empty(self):
        # Boundary: empty pool → empty result, no exception.
        assert stratified_sample([], 10, random.Random(42)) == []

    def test_respects_target_n_upper_bound(self):
        # Negative: picks must not exceed target_n.
        pool = self._make_prs(100)
        picks = stratified_sample(pool, 20, random.Random(42))
        assert len(picks) == 20

    def test_caps_at_pool_size_when_target_exceeds_pool(self):
        # Boundary: target > pool → pick everything (no duplication).
        pool = self._make_prs(5)
        picks = stratified_sample(pool, 100, random.Random(42))
        # Function picks up to target_n. With 5 in pool it returns those 5 (or
        # the result of the author-diversity top-up clause).
        assert len(picks) <= 5
        # No duplicates by PR number.
        nums = [p["number"] for p in picks]
        assert len(nums) == len(set(nums))

    def test_picks_span_multiple_strata(self):
        # Discrimination: stratification means picks span multiple size buckets.
        pool = self._make_prs(50)
        picks = stratified_sample(pool, 30, random.Random(42))
        strata = {size_stratum(p["additions"], p["deletions"]) for p in picks}
        assert len(strata) >= 2  # at least two distinct size buckets


# ---------------------------------------------------------------------------
# load_calibration_overrides (vibe_check.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_vibe_check_globals():
    """
    Snapshot and restore SIGNAL_THRESHOLDS and WEIGHTS so per-test mutations
    don't leak across tests. load_calibration_overrides mutates these
    module-level dicts in-place; without this fixture, any test that
    successfully applies an override would contaminate every subsequent test
    in the suite.

    Pattern: deepcopy the dicts before yield; clear+update on teardown so
    the dict identity is preserved (other modules may already hold a
    reference) but the contents revert to the source-file defaults.
    """
    thresholds_snapshot = copy.deepcopy(vibe_check.SIGNAL_THRESHOLDS)
    weights_snapshot = copy.deepcopy(vibe_check.WEIGHTS)
    yield
    vibe_check.SIGNAL_THRESHOLDS.clear()
    vibe_check.SIGNAL_THRESHOLDS.update(thresholds_snapshot)
    vibe_check.WEIGHTS.clear()
    vibe_check.WEIGHTS.update(weights_snapshot)


class TestLoadCalibrationOverrides:
    """
    load_calibration_overrides() reads {TELEMETRY_DIR}/calibration_override.json
    and mutates SIGNAL_THRESHOLDS and WEIGHTS in vibe_check.py in-place.
    Returns True on apply, False on every short-circuit (no telemetry dir,
    no file, malformed JSON, stale version).

    Test isolation pattern:
        - monkeypatch swaps vibe_check.TELEMETRY_DIR to tmp_path per test;
          the function reads this by bare-name lookup at call time, not at
          import time, so no importlib.reload is needed.
        - restore_vibe_check_globals fixture snapshots and restores
          SIGNAL_THRESHOLDS and WEIGHTS so positive-path mutations don't
          leak across tests in the file or in the broader test suite.
    """

    pytestmark = pytest.mark.usefixtures("restore_vibe_check_globals")

    def _write_override(self, tmp_path: Path, payload: dict) -> Path:
        """Write a JSON override file at the canonical location."""
        p = tmp_path / OVERRIDE_FILENAME
        p.write_text(json.dumps(payload))
        return p

    def test_returns_false_when_telemetry_dir_unset(self, monkeypatch):
        # Negative: the first guard. With TELEMETRY_DIR None (env var unset),
        # the function returns False immediately without touching anything.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", None)
        before = copy.deepcopy(vibe_check.SIGNAL_THRESHOLDS)
        assert load_calibration_overrides() is False
        assert vibe_check.SIGNAL_THRESHOLDS == before

    def test_returns_false_when_file_absent(self, tmp_path, monkeypatch):
        # Negative: TELEMETRY_DIR is set but no override file exists at the
        # expected location. Returns False; no mutation.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        before = copy.deepcopy(vibe_check.SIGNAL_THRESHOLDS)
        assert load_calibration_overrides() is False
        assert vibe_check.SIGNAL_THRESHOLDS == before

    def test_returns_false_on_malformed_json(self, tmp_path, monkeypatch):
        # Negative: file exists but content is not valid JSON. The
        # except (json.JSONDecodeError, OSError) clause catches it.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        (tmp_path / OVERRIDE_FILENAME).write_text("not-json{")
        before = copy.deepcopy(vibe_check.SIGNAL_THRESHOLDS)
        assert load_calibration_overrides() is False
        assert vibe_check.SIGNAL_THRESHOLDS == before

    def test_well_formed_thresholds_applied(self, tmp_path, monkeypatch):
        # Positive: a valid override JSON updates threshold/baselines
        # in-place and returns True.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "base_calibration": CALIBRATION_VERSION,
            "thresholds": {
                "docstring_consistency": {"threshold": 0.50, "llm_baseline": 0.85},
            },
        })
        assert load_calibration_overrides() is True
        assert vibe_check.SIGNAL_THRESHOLDS["docstring_consistency"]["threshold"] == 0.50
        assert vibe_check.SIGNAL_THRESHOLDS["docstring_consistency"]["llm_baseline"] == 0.85
        # human_baseline not in override → unchanged (pin the field-by-field
        # selective-update contract; a future refactor must not silently
        # replace the whole sub-dict).
        assert vibe_check.SIGNAL_THRESHOLDS["docstring_consistency"]["human_baseline"] == 0.25

    def test_partial_override_leaves_other_signals_untouched(self, tmp_path, monkeypatch):
        # Boundary: only one signal's threshold is overridden. Other signals
        # must remain at their compiled-in defaults.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "base_calibration": CALIBRATION_VERSION,
            "thresholds": {"naming_uniformity": {"threshold": 0.75}},
        })
        assert load_calibration_overrides() is True
        assert vibe_check.SIGNAL_THRESHOLDS["naming_uniformity"]["threshold"] == 0.75
        # Other signals unchanged.
        assert vibe_check.SIGNAL_THRESHOLDS["error_handling"]["threshold"] == 0.45
        assert vibe_check.SIGNAL_THRESHOLDS["edge_case_depth"]["threshold"] == 1.5

    def test_unknown_signal_name_silently_ignored(self, tmp_path, monkeypatch):
        # Boundary: an override for a signal name not in SIGNAL_THRESHOLDS
        # is skipped via the `if sig_name in SIGNAL_THRESHOLDS` guard. No
        # exception; the function still returns True.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "base_calibration": CALIBRATION_VERSION,
            "thresholds": {"nonexistent_signal_xyz": {"threshold": 0.99}},
        })
        assert load_calibration_overrides() is True
        assert "nonexistent_signal_xyz" not in vibe_check.SIGNAL_THRESHOLDS

    def test_stale_base_calibration_version_rejected(self, tmp_path, monkeypatch):
        # Negative: an override produced against a different calibration
        # epoch (and not the legacy synonym) must be ignored. Returns False,
        # SIGNAL_THRESHOLDS unchanged.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "base_calibration": "v0.99.0_future_epoch_not_yet_real",
            "thresholds": {"docstring_consistency": {"threshold": 0.10}},
        })
        before = copy.deepcopy(vibe_check.SIGNAL_THRESHOLDS)
        assert load_calibration_overrides() is False
        assert vibe_check.SIGNAL_THRESHOLDS == before

    def test_legacy_v2026_q2_gemini_version_accepted(self, tmp_path, monkeypatch):
        # Boundary: the documented legacy synonym (v2026_q2_gemini from
        # v0.1.x) is still honored so existing user calibration files keep
        # working after the v0.2.0 rename. See CHANGELOG migration note.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "base_calibration": "v2026_q2_gemini",
            "thresholds": {"comment_phrasing": {"threshold": 0.20}},
        })
        assert load_calibration_overrides() is True
        assert vibe_check.SIGNAL_THRESHOLDS["comment_phrasing"]["threshold"] == 0.20

    def test_missing_base_calibration_key_accepted(self, tmp_path, monkeypatch):
        # Boundary: when `base_calibration` is absent, `ov = ""` and the
        # version-mismatch guard short-circuits via `if ov and ...`. The
        # override is applied; this is the documented permissive path for
        # legacy files that pre-dated the version-tag convention.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "thresholds": {"function_length": {"threshold": 0.5}},
        })
        assert load_calibration_overrides() is True
        assert vibe_check.SIGNAL_THRESHOLDS["function_length"]["threshold"] == 0.5

    def test_weight_above_30pct_clamped(self, tmp_path, monkeypatch):
        # Boundary: an override that tries to push a single signal's weight
        # above 0.30 must be clamped (documented invariant: no single signal
        # can dominate the overall score). Re-normalization runs afterward,
        # so the post-norm value will be 0.30 / new_total; verify <= 0.30
        # in the post-norm state and that the per-signal floor still holds.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "base_calibration": CALIBRATION_VERSION,
            "weights": {"comment_ratio": 0.99},
        })
        assert load_calibration_overrides() is True
        # After clamp to 0.30 then re-normalization across 10 weights, the
        # clamped value sits below 0.30 (≈0.30 / 1.12 ≈ 0.268).
        assert vibe_check.WEIGHTS["comment_ratio"] <= 0.30
        # Per-signal floor invariant after normalization (the clamp happens
        # pre-norm, so post-norm values can dip a touch below 0.02 only via
        # rounding; allow that micro-tolerance).
        assert all(w >= 0.02 - 1e-3 for w in vibe_check.WEIGHTS.values())

    def test_weight_below_2pct_clamped(self, tmp_path, monkeypatch):
        # Boundary: weight = 0.001 (below the 0.02 floor) must be clamped up.
        # The floor exists because a signal at near-zero weight may as well
        # be removed; clamping preserves the signal-shape invariant.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "base_calibration": CALIBRATION_VERSION,
            "weights": {"hallucinated_apis": 0.001},
        })
        assert load_calibration_overrides() is True
        # 0.001 < 0.02 floor → clamped to 0.02 before normalize. After
        # normalize the value is well above the 0.001 input; pin that
        # the floor actually fired.
        assert vibe_check.WEIGHTS["hallucinated_apis"] > 0.001

    def test_weights_renormalize_to_unit_sum(self, tmp_path, monkeypatch):
        # Positive: after any weight override, the weights must sum to ~1.0
        # (modulo 4-decimal rounding). This is the load-bearing invariant
        # of the overall-score formula: sum(weight_i * signal_score_i).
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "base_calibration": CALIBRATION_VERSION,
            "weights": {
                "comment_ratio": 0.25,
                "docstring_consistency": 0.20,
            },
        })
        assert load_calibration_overrides() is True
        total = sum(vibe_check.WEIGHTS.values())
        # 4-decimal rounding per weight (10 weights) → ε ≈ 1e-3 worst-case.
        assert total == pytest.approx(1.0, abs=1e-3)

    def test_repeated_invocation_picks_up_new_file_contents(self, tmp_path, monkeypatch):
        # Adversarial: the function does NOT cache. Each call re-reads the
        # file from disk. If calibration_pipeline rewrites the override
        # between two load_calibration_overrides() calls, the second call's
        # effect must reflect the new file.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        self._write_override(tmp_path, {
            "base_calibration": CALIBRATION_VERSION,
            "thresholds": {"error_handling": {"threshold": 0.30}},
        })
        assert load_calibration_overrides() is True
        assert vibe_check.SIGNAL_THRESHOLDS["error_handling"]["threshold"] == 0.30
        # Rewrite file with a different threshold.
        self._write_override(tmp_path, {
            "base_calibration": CALIBRATION_VERSION,
            "thresholds": {"error_handling": {"threshold": 0.55}},
        })
        assert load_calibration_overrides() is True
        assert vibe_check.SIGNAL_THRESHOLDS["error_handling"]["threshold"] == 0.55

    def test_null_threshold_in_override_skipped(self, tmp_path, monkeypatch):
        # Boundary: the source code guards `if new_vals[key] is not None`,
        # so an explicit null override does NOT overwrite the existing
        # value. This protects against the calibration pipeline emitting
        # null when it has insufficient data to recommend a threshold.
        monkeypatch.setattr(vibe_check, "TELEMETRY_DIR", str(tmp_path))
        original = vibe_check.SIGNAL_THRESHOLDS["docstring_consistency"]["threshold"]
        self._write_override(tmp_path, {
            "base_calibration": CALIBRATION_VERSION,
            "thresholds": {
                "docstring_consistency": {"threshold": None, "llm_baseline": 0.95},
            },
        })
        assert load_calibration_overrides() is True
        # null threshold skipped → original preserved.
        assert vibe_check.SIGNAL_THRESHOLDS["docstring_consistency"]["threshold"] == original
        # Non-null co-field still updated.
        assert vibe_check.SIGNAL_THRESHOLDS["docstring_consistency"]["llm_baseline"] == 0.95


# ---------------------------------------------------------------------------
# extract_signals
# ---------------------------------------------------------------------------


class TestExtractSignals:
    """
    extract_signals(vj) -> dict[str, Any].

    Reads vibe_check.py's JSON output and flattens it into a row-shaped
    dict: overall_ai_prob (float), one float per SIGNAL_SHORT key (avg_score
    from signal_summary[INTERNAL]), and _languages (sorted list of
    file_analyses[].language). Missing/None branches default to safe values
    so partial vibe_check output doesn't crash the calibration loop.
    """

    def test_happy_path_extracts_all_fields(self):
        # Positive: full vj with overall_ai_probability, signal_summary
        # populated for every SIGNAL_INTERNAL key, and file_analyses
        # with mixed languages → all output fields populated.
        vj = {
            "overall_ai_probability": 0.73,
            "signal_summary": {
                "comment_ratio": {"avg_score": 0.4},
                "docstring_consistency": {"avg_score": 0.5},
                "naming_uniformity": {"avg_score": 0.6},
                "error_handling": {"avg_score": 0.3},
                "declarative_bias": {"avg_score": 0.2},
                "function_length": {"avg_score": 0.7},
                "comment_phrasing": {"avg_score": 0.8},
                "hallucinated_apis": {"avg_score": 0.1},
                "edge_case_depth": {"avg_score": 0.9},
                "commit_metadata": {"avg_score": 0.55},
            },
            "file_analyses": [
                {"language": "python"},
                {"language": "javascript"},
                {"language": "python"},  # dedup
            ],
        }
        out = extract_signals(vj)
        assert out["overall_ai_prob"] == 0.73
        assert out["ccr"] == 0.4
        assert out["docstring"] == 0.5
        assert out["naming"] == 0.6
        assert out["commit_meta"] == 0.55
        # _languages is sorted and deduped via the langs set.
        assert out["_languages"] == ["javascript", "python"]
        # All SIGNAL_SHORT keys present in the output dict.
        for short in SIGNAL_SHORT:
            assert short in out

    def test_missing_overall_ai_probability_defaults_to_half(self):
        # Boundary: .get("overall_ai_probability", 0.5) — default fires
        # when vibe_check produced no scalar grade. Pins the safe default
        # so a missing field doesn't propagate as 0.0 (which would bias
        # the calibration ledger toward "all PRs look human").
        out = extract_signals({})
        assert out["overall_ai_prob"] == 0.5

    def test_missing_signal_summary_defaults_all_signals_to_zero(self):
        # Boundary: signal_summary missing or None → ss = {}; per-signal
        # block lookup returns {} → avg_score defaults to 0.0. Pins the
        # safe-default chain so partial vibe_check output yields zeroed
        # signals rather than raising KeyError.
        out = extract_signals({"overall_ai_probability": 0.5})
        for short in SIGNAL_SHORT:
            assert out[short] == 0.0

    def test_signal_summary_none_block_defaults_to_zero(self):
        # Discrimination: an explicit None for one signal's block (not
        # just a missing key) must also default that signal to 0.0 via
        # the `block = ss.get(internal) or {}` guard. If the `or {}`
        # fallback is dropped, this fails with TypeError.
        vj = {"signal_summary": {"comment_ratio": None}}
        out = extract_signals(vj)
        assert out["ccr"] == 0.0

    def test_file_analyses_missing_language_recorded_as_unknown(self):
        # Boundary: a file_analysis entry without a language field gets
        # "unknown" via the `str(fa.get("language") or "unknown")` chain.
        # Pins this so a refactor that drops the fallback would surface.
        vj = {
            "file_analyses": [
                {"language": "python"},
                {},  # no language key
                {"language": None},  # explicit None
            ],
        }
        out = extract_signals(vj)
        # Both empty-dict and None-language entries collapse to "unknown".
        assert out["_languages"] == ["python", "unknown"]


# ---------------------------------------------------------------------------
# signals_row
# ---------------------------------------------------------------------------


class TestSignalsRow:
    """
    signals_row(pr, label_class, sig) -> dict.

    Flattens an extract_signals() output into a TSV-writable row keyed
    by pr_number / label_class / overall_ai_prob / each SIGNAL_SHORT.
    The function uses sig[k] (not .get()), so missing keys raise KeyError
    by design — incomplete extract_signals output should fail loudly,
    not silently produce a row of zeros.
    """

    def test_happy_path_constructs_complete_row(self):
        # Positive: a fully-populated sig dict produces a row with all
        # expected keys and the originating pr/label_class.
        sig = {
            "overall_ai_prob": 0.42,
            "ccr": 0.1, "docstring": 0.2, "naming": 0.3,
            "error_handling": 0.4, "declarative": 0.5, "func_length": 0.6,
            "comment_phrasing": 0.7, "hallucinated": 0.8, "edge_depth": 0.9,
            "commit_meta": 0.55,
        }
        row = signals_row(42, "vibe-coded", sig)
        assert row["pr_number"] == 42
        assert row["label_class"] == "vibe-coded"
        assert row["overall_ai_prob"] == 0.42
        for short in SIGNAL_SHORT:
            assert row[short] == sig[short]

    def test_missing_signal_short_key_raises_keyerror(self):
        # Negative: the function uses sig[k] not sig.get(k); a missing
        # key must raise. This is intentional: incomplete signal data
        # should surface immediately, not silently produce a zero row
        # that pollutes the calibration ledger. Pin the contract.
        incomplete_sig = {"overall_ai_prob": 0.5}  # no SIGNAL_SHORT keys
        with pytest.raises(KeyError):
            signals_row(1, "ai-assisted", incomplete_sig)


# ---------------------------------------------------------------------------
# size_bucket
# ---------------------------------------------------------------------------


class TestSizeBucket:
    """
    size_bucket(adds) -> str in {s0, s1, s2, s3}.

    Bucketizes additions count into 4 size strata for stratified sampling.
    Boundaries (per source): <50 → s0, <200 → s1, <500 → s2, ≥500 → s3.
    """

    @pytest.mark.parametrize(
        "adds,expected",
        [
            (0, "s0"),
            (1, "s0"),
            (49, "s0"),    # boundary: just under 50
            (50, "s1"),    # boundary: at 50
            (199, "s1"),   # boundary: just under 200
            (200, "s2"),   # boundary: at 200
            (499, "s2"),   # boundary: just under 500
            (500, "s3"),   # boundary: at 500
            (10_000, "s3"),  # large
        ],
    )
    def test_each_boundary(self, adds, expected):
        # Discrimination: pin every boundary so a refactor that flips
        # < to <= (or shifts a threshold by 1) is caught immediately.
        # The 4 buckets feed stratified_unlabeled's per-cell quotas.
        assert size_bucket(adds) == expected


# ---------------------------------------------------------------------------
# time_bucket
# ---------------------------------------------------------------------------


class TestTimeBucket:
    """
    time_bucket(merged, ref) -> str in {t0, t1, t2, t3, u}.

    Bucketizes a merged-at ISO timestamp into recency strata relative
    to a reference datetime. Boundaries: ≤90 days → t0, ≤180 → t1,
    ≤365 → t2, >365 → t3. Returns "u" if parse_iso fails (empty or
    malformed input). Naive datetimes are treated as UTC.
    """

    REF = datetime(2026, 5, 19, tzinfo=timezone.utc)

    def test_recent_merge_routes_to_t0(self):
        # Positive: 30 days before ref → t0 (≤90).
        merged = "2026-04-19T12:00:00Z"
        assert time_bucket(merged, self.REF) == "t0"

    def test_each_recency_boundary(self):
        # Discrimination: pin all four recency boundaries.
        # 90 days exactly → t0 (≤90)
        assert time_bucket("2026-02-18T00:00:00Z", self.REF) == "t0"
        # 91 days → t1 (>90, ≤180)
        assert time_bucket("2026-02-17T00:00:00Z", self.REF) == "t1"
        # 180 days exactly → t1
        assert time_bucket("2025-11-20T00:00:00Z", self.REF) == "t1"
        # 181 days → t2
        assert time_bucket("2025-11-19T00:00:00Z", self.REF) == "t2"
        # 365 days exactly → t2
        assert time_bucket("2025-05-19T00:00:00Z", self.REF) == "t2"
        # 366 days → t3
        assert time_bucket("2025-05-18T00:00:00Z", self.REF) == "t3"
        # very old → t3
        assert time_bucket("2020-01-01T00:00:00Z", self.REF) == "t3"

    def test_empty_or_malformed_input_returns_u(self):
        # Negative: parse_iso returns None on empty or unparseable input
        # → time_bucket returns "u" (the unknown bucket). Pins this so
        # callers can distinguish "no data" from "very old".
        assert time_bucket("", self.REF) == "u"
        assert time_bucket("not-a-date", self.REF) == "u"
        assert time_bucket("2026-13-99T00:00:00Z", self.REF) == "u"

    def test_naive_datetime_treated_as_utc(self):
        # Boundary: an ISO timestamp without timezone info (parse_iso
        # returns a naive datetime) gets UTC tzinfo applied at line
        # 499-500 before the delta calculation. Without that, comparing
        # naive vs aware datetime would raise TypeError. Pin the guard.
        # Note: parse_iso always returns aware datetimes for inputs
        # ending in Z (it converts Z → +00:00 first), so to actually
        # produce a naive datetime we need an ISO string with no tz
        # marker at all.
        merged_naive = "2026-04-19T12:00:00"  # no Z, no offset
        # Should not raise; should bucketize relative to UTC ref.
        bucket = time_bucket(merged_naive, self.REF)
        assert bucket in ("t0", "t1", "t2", "t3")


# ---------------------------------------------------------------------------
# stratified_unlabeled
# ---------------------------------------------------------------------------


class TestStratifiedUnlabeled:
    """
    stratified_unlabeled(pr_json, matched_label_names, ref, k) -> list[dict].

    Picks k unlabeled PRs (those whose labels don't intersect
    matched_label_names) stratified across 4 size buckets × 4 time
    buckets = 16 cells. Quotas: target_per_size = max(1, k // 4) per
    size bucket. Within each (size, time) cell, PRs are sorted by
    number descending. After per-size quotas are filled, any remaining
    capacity is filled by descending-number order across the entire
    candidate pool.
    """

    REF = datetime(2026, 5, 19, tzinfo=timezone.utc)

    def _make_pr(self, number: int, additions: int, merged: str, label_names: list[str]) -> dict:
        """Construct a minimal PR dict matching the gh schema fields
        stratified_unlabeled actually reads (number, additions, mergedAt,
        labels[].name)."""
        return {
            "number": number,
            "additions": additions,
            "mergedAt": merged,
            "labels": [{"name": n} for n in label_names],
        }

    def test_excludes_prs_with_matched_labels(self):
        # Positive: PRs labeled with anything in matched_label_names are
        # filtered out at line 521-522 (the candidate-pool guard).
        prs = [
            self._make_pr(1, 100, "2026-05-01T00:00:00Z", ["vibe-coded"]),
            self._make_pr(2, 100, "2026-05-01T00:00:00Z", ["bug"]),
            self._make_pr(3, 100, "2026-05-01T00:00:00Z", ["ai-assisted"]),
        ]
        picked = stratified_unlabeled(prs, {"vibe-coded", "ai-assisted"}, self.REF, k=10)
        # PRs 1 and 3 excluded; only PR 2 remains as a candidate.
        assert [p["number"] for p in picked] == [2]

    def test_k_zero_returns_empty(self):
        # Boundary: k=0 → target_per_size = max(1, 0) = 1, but the inner
        # break check `if len(picked) >= k` fires immediately on the
        # first append. With k=0 we expect exactly 0 PRs.
        prs = [self._make_pr(1, 100, "2026-05-01T00:00:00Z", [])]
        picked = stratified_unlabeled(prs, set(), self.REF, k=0)
        assert picked == []

    def test_descending_number_order_within_cell(self):
        # Discrimination: within a (size, time) cell, PRs are sorted by
        # number descending (line 539). With k large enough to take
        # everything from one cell, we should see PRs in descending
        # number order. Pin this so a refactor that swaps to ascending
        # order would surface — the calibration sampler treats higher
        # PR numbers as "more recent" and prioritizes them.
        prs = [
            self._make_pr(10, 30, "2026-05-01T00:00:00Z", []),  # all in (s0, t0)
            self._make_pr(20, 30, "2026-05-01T00:00:00Z", []),
            self._make_pr(30, 30, "2026-05-01T00:00:00Z", []),
        ]
        picked = stratified_unlabeled(prs, set(), self.REF, k=10)
        numbers = [p["number"] for p in picked]
        # All 3 picked (only one cell, k > pool); descending order.
        assert numbers == [30, 20, 10]

    def test_stratifies_across_size_buckets(self):
        # Discrimination: with k=4 (target_per_size = 1), the algorithm
        # picks 1 PR per size bucket (where available) before falling
        # through to the leftover-fill at line 550. Pin that the size
        # stratification quota is honored — the load-bearing claim of
        # this function for the calibration ledger.
        prs = [
            # 2 PRs in s0 (additions < 50)
            self._make_pr(1, 10, "2026-05-01T00:00:00Z", []),
            self._make_pr(2, 20, "2026-05-01T00:00:00Z", []),
            # 2 PRs in s1 (50 ≤ additions < 200)
            self._make_pr(3, 100, "2026-05-01T00:00:00Z", []),
            self._make_pr(4, 150, "2026-05-01T00:00:00Z", []),
            # 2 PRs in s2 (200 ≤ additions < 500)
            self._make_pr(5, 250, "2026-05-01T00:00:00Z", []),
            self._make_pr(6, 400, "2026-05-01T00:00:00Z", []),
            # 2 PRs in s3 (additions ≥ 500)
            self._make_pr(7, 600, "2026-05-01T00:00:00Z", []),
            self._make_pr(8, 1000, "2026-05-01T00:00:00Z", []),
        ]
        picked = stratified_unlabeled(prs, set(), self.REF, k=4)
        # Exactly 4 picked, one per size bucket. Within each size, the
        # higher-numbered PR wins (descending sort). So we expect:
        # s0: 2, s1: 4, s2: 6, s3: 8.
        assert sorted(p["number"] for p in picked) == [2, 4, 6, 8]

    def test_unknown_time_bucket_collapses_to_t3(self):
        # Boundary: a PR with empty mergedAt → time_bucket returns "u"
        # → coerced to "t3" at line 529-530 before cell assignment.
        # Pins this coercion so PRs with missing merge dates aren't
        # silently dropped from the candidate pool.
        prs = [
            self._make_pr(1, 100, "", []),  # empty mergedAt → "u" → "t3"
        ]
        picked = stratified_unlabeled(prs, set(), self.REF, k=10)
        assert [p["number"] for p in picked] == [1]

    def test_leftover_fill_uses_descending_number_order(self):
        # Discrimination: when per-size quotas are filled but k isn't
        # met (e.g. some size buckets are empty), the algorithm falls
        # through to lines 550-556, picking remaining candidates in
        # descending number order, deduplicated against `seen`. Pin
        # this to ensure deterministic sampling.
        prs = [
            # All in s0; k=4 means target_per_size=1, but only s0 has
            # candidates so quotas fill 1 then leftover-fill takes 3 more.
            self._make_pr(1, 10, "2026-05-01T00:00:00Z", []),
            self._make_pr(2, 20, "2026-05-01T00:00:00Z", []),
            self._make_pr(3, 30, "2026-05-01T00:00:00Z", []),
            self._make_pr(4, 40, "2026-05-01T00:00:00Z", []),
        ]
        picked = stratified_unlabeled(prs, set(), self.REF, k=4)
        numbers = [p["number"] for p in picked]
        # All 4 picked, descending order from both quota-fill and
        # leftover-fill paths (which both sort descending).
        assert numbers == [4, 3, 2, 1]

    def test_skips_duplicate_pr_numbers_in_pool(self):
        # Boundary: if the candidate pool contains the same PR number twice
        # (malformed gh payload), the `if n in seen: continue` guard at
        # stratified_unlabeled `if n in seen` guard must dedupe without double-counting toward k.
        prs = [
            self._make_pr(5, 30, "2026-05-01T00:00:00Z", []),
            self._make_pr(5, 30, "2026-05-01T00:00:00Z", []),  # duplicate number
            self._make_pr(4, 30, "2026-05-01T00:00:00Z", []),
        ]
        picked = stratified_unlabeled(prs, set(), self.REF, k=10)
        assert [p["number"] for p in picked] == [5, 4]


# ---------------------------------------------------------------------------
# write_tsv
# ---------------------------------------------------------------------------


class TestWriteTSV:
    """write_tsv(path, headers, rows) — tab-delimited export with mkdir."""

    def test_writes_header_and_rows(self, tmp_path):
        path = tmp_path / "nested" / "out.tsv"
        write_tsv(path, ["col_a", "col_b"], [{"col_a": "1", "col_b": "2"}])
        assert path.exists()
        lines = path.read_text().splitlines()
        assert lines[0] == "col_a\tcol_b"
        assert lines[1] == "1\t2"

    def test_ignores_extra_dict_keys(self, tmp_path):
        # Negative: extrasaction="ignore" — stray keys must not crash the writer.
        path = tmp_path / "out.tsv"
        write_tsv(path, ["only"], [{"only": "x", "extra": "drop-me"}])
        assert path.read_text().splitlines()[1] == "x"

    def test_empty_rows_writes_header_only(self, tmp_path):
        # Boundary: zero data rows still emits the header line.
        path = tmp_path / "out.tsv"
        write_tsv(path, ["a"], [])
        assert path.read_text() == "a\n"


# ---------------------------------------------------------------------------
# phase4 (pure stats orchestration on in-memory rows)
# ---------------------------------------------------------------------------


class TestPhase4:
    """
    phase4(signals_rows, expanded_rows, out, low_confidence) -> summary dict.

    Network-free: consumes pre-built signal rows and writes TSV/JSON artifacts.
    """

    def _labeled_row(self, label_class: str, prob: float) -> dict:
        row = {
            "label_class": label_class,
            "overall_ai_prob": prob,
            "_languages": ["python"],
        }
        for short in SIGNAL_SHORT:
            row[short] = prob if label_class == "vibe-coded" else 1.0 - prob
        return row

    def _expanded_row(self, pseudo: str, additions: int = 100) -> dict:
        return {
            "pseudo_label": pseudo,
            "author": "dev1",
            "additions": additions,
            "merged": "2026-05-01T00:00:00Z",
        }

    def test_writes_artifacts_and_summary(self, tmp_path):
        # Positive: ≥5 rows per labeled class triggers descriptive + discrimination paths.
        signals = (
            [self._labeled_row("vibe-coded", 0.85) for _ in range(5)]
            + [self._labeled_row("human-written", 0.15) for _ in range(5)]
        )
        expanded = (
            [self._expanded_row("likely-vibe-coded", 600) for _ in range(3)]
            + [self._expanded_row("likely-human", 30) for _ in range(3)]
            + [self._expanded_row("ambiguous", 250) for _ in range(2)]
        )
        summary = phase4(signals, expanded, tmp_path, low_confidence=False)
        assert summary["labeled_vibe_coded"] == 5
        assert summary["labeled_human"] == 5
        assert (tmp_path / "descriptive_stats.tsv").exists()
        assert (tmp_path / "discrimination.tsv").exists()
        assert (tmp_path / "dataset_summary.json").exists()
        assert "python" in summary["languages_observed"]

    def test_low_confidence_flag_adds_warning(self, tmp_path):
        # Boundary: low_confidence=True appends LABELED_LT_10 to dataset_quality_warnings.
        signals = [self._labeled_row("vibe-coded", 0.9) for _ in range(5)]
        expanded = [self._expanded_row("likely-vibe-coded")]
        summary = phase4(signals, expanded, tmp_path, low_confidence=True)
        assert any("LABELED_LT_10" in w for w in summary["dataset_quality_warnings"])

    def test_undersampled_class_emits_warning(self, tmp_path):
        # Negative: a class with <5 rows is skipped in descriptive stats but
        # triggers UNDERSAMPLED warning in the summary.
        signals = (
            [self._labeled_row("vibe-coded", 0.9) for _ in range(5)]
            + [self._labeled_row("ai-assisted", 0.5)]  # N=1 → undersampled
        )
        expanded = [self._expanded_row("likely-vibe-coded")]
        summary = phase4(signals, expanded, tmp_path, low_confidence=False)
        assert any(w.startswith("UNDERSAMPLED:ai-assisted") for w in summary["dataset_quality_warnings"])
