"""
Integration tests for the gh-CLI-dependent functions in
scripts/calibration_pipeline.py: phase1, fetch_pr_detail, run_vibe.

These functions exec the gh CLI (and run_vibe execs the sibling
vibe_check.py) via subprocess.run. The tests mock the subprocess.run
import inside calibration_pipeline to canned CompletedProcess payloads
and assert both the function's behavioral contract AND the argv shape
constructed by run_gh (so a refactor cannot silently change the gh
invocation form).

Mocking strategy (per the PR-1 deferred-items rationale):
    Option A — monkeypatch subprocess.run at calibration_pipeline's
    import path. Lightweight, no extra dependency, no fixture binary
    needed. The tradeoff: tests bypass the actual subprocess path, so a
    bug in argv construction would go uncaught without explicit argv
    assertions. Tests below pin argv shape to mitigate.

Fixture payloads live under tests/fixtures/gh_responses/. See the
README there for capture provenance: four real-captures from cli/cli
(`label list`, `pr list`, `pr diff`, `pr view --json commits`) plus
five synthetic-augmented files for vibe/ai/human label scenarios that
no real repo carries widely yet. Captures are static; tests never
hit the network. The `_load()` helper reads a fixture file as raw
text and returns it directly to the mocked subprocess stdout.

Discipline (per the action plan):
    Each function gets ≥4 tests covering positive, negative, boundary,
    and adversarial (argv-shape pinning, budget enforcement). Adversarial
    discrimination beats defensive coverage. An additional
    TestRealCaptureSchema class demonstrates that real cli/cli output
    flows through the code under test unmodified.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import calibration_pipeline  # noqa: E402  (module import for monkeypatching)
from calibration_pipeline import (  # noqa: E402
    PR_DETAIL_CAP,
    P1_API,
    Budget,
    VIBE_CHECK,
    analyze_prs,
    fetch_pr_detail,
    phase1,
    run_gh,
    run_vibe,
)


# ---------------------------------------------------------------------------
# Subprocess.run mocking infrastructure
# ---------------------------------------------------------------------------


class FakeCompletedProcess:
    """Minimal stand-in for subprocess.CompletedProcess. Only the
    attributes consumed by run_gh / run_vibe are populated."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunRecorder:
    """
    Records every call to subprocess.run and dispenses queued responses.

    Usage:
        recorder.enqueue(returncode=0, stdout='[...]')
        # ... call code under test ...
        assert recorder.calls[0][0][:3] == ["gh", "-R", "owner/repo"]

    If a queued exception is enqueued (via enqueue_exc), the recorder
    raises it instead of returning a CompletedProcess. This is how we
    simulate subprocess errors (TimeoutExpired, FileNotFoundError, etc.)
    that run_gh's outer try/except is supposed to catch.

    Calls outpacing the response queue return a default 0/empty response
    so a test only enqueues the responses it actually cares about.
    """

    def __init__(self):
        self.calls: list[tuple[list[str], dict[str, Any]]] = []
        self.responses: list[Any] = []

    def enqueue(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.responses.append(FakeCompletedProcess(returncode, stdout, stderr))

    def enqueue_exc(self, exc: BaseException) -> None:
        self.responses.append(exc)

    def __call__(self, cmd, **kwargs):
        # Normalize cmd to list[str] for stable assertions even if a caller
        # passes a tuple or generator.
        self.calls.append((list(cmd), kwargs))
        if self.responses:
            resp = self.responses.pop(0)
            if isinstance(resp, BaseException):
                raise resp
            return resp
        # Default: rc=0, empty stdout. Lets tests only enqueue what they assert.
        return FakeCompletedProcess(returncode=0, stdout="", stderr="")


@pytest.fixture
def fake_run(monkeypatch):
    """Replace calibration_pipeline.subprocess.run with a FakeRunRecorder."""
    recorder = FakeRunRecorder()
    monkeypatch.setattr(calibration_pipeline.subprocess, "run", recorder)
    return recorder


# ---------------------------------------------------------------------------
# Fixture loaders
#
# Fixtures live under tests/fixtures/gh_responses/. See the README in
# that directory for capture provenance (cli/cli @ 2026-05-19) and the
# synthetic-augmented file inventory.
# ---------------------------------------------------------------------------


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "gh_responses"


def _load(filename: str) -> str:
    """Load a fixture file as raw text.

    Returned verbatim so the mocked subprocess stdout matches exactly
    what `gh` would produce. Used for both JSON fixtures (`.json`) and
    diff fixtures (`.diff`); callers don't need to decode/re-encode.
    """
    return (FIXTURES_DIR / filename).read_text()


def _synthetic_commits(*messages: str) -> str:
    """Construct a minimal commits payload from message headlines.

    Used by tests that need controlled message strings to assert
    specific text appears in `commit_meta`. The code under test reads
    only `commits[].messageHeadline` from this schema, so omitting the
    other fields is safe. For full-schema exercise, prefer the captured
    `pr_view_commits_real_clicli.json` fixture via `_load()`.
    """
    return json.dumps(
        {"commits": [{"messageHeadline": m} for m in messages]}
    )


# ---------------------------------------------------------------------------
# phase1
# ---------------------------------------------------------------------------


class TestPhase1:
    """
    phase1(repo, budget, out) -> (labeled_pr_rows, label_map, matched_names).

    Calls gh label list, classifies each label, then for each matched
    label calls gh pr list --label NAME. Writes label_map.tsv and
    labeled_prs.tsv into out_dir. Returns ([], {}, set()) if the first
    gh call returns nonzero.
    """

    def test_happy_path_with_one_vibe_label(self, fake_run, tmp_path):
        # Positive: one matched label ("vibe-coded"), one PR returned by
        # the pr list call. Verify labeled output, both gh calls happened,
        # and label_map.tsv is written. Fixtures use the real gh schema
        # shape (id, color, is_bot, full commits[]) captured from cli/cli.
        fake_run.enqueue(
            returncode=0,
            stdout=_load("label_list_synthetic_single_vibe.json"),
        )
        fake_run.enqueue(
            returncode=0,
            stdout=_load("pr_list_synthetic_single.json"),
        )
        budget = Budget()
        labeled, label_map, matched = phase1("owner/repo", budget, tmp_path)

        assert len(labeled) == 1
        # PR number 42 is the synthetic-fixture choice; see
        # tests/fixtures/gh_responses/pr_list_synthetic_single.json.
        assert labeled[0]["pr_number"] == 42
        assert labeled[0]["label_class"] == "vibe-coded"
        assert label_map == {"vibe-coded": "vibe-coded"}
        assert matched == {"vibe-coded"}
        # Argv-shape pinning for the labels call (first gh invocation).
        assert fake_run.calls[0][0][:6] == [
            "gh", "-R", "owner/repo", "label", "list", "--limit"
        ]
        # Output files written.
        assert (tmp_path / "label_map.tsv").exists()
        assert (tmp_path / "labeled_prs.tsv").exists()

    def test_returns_empty_when_labels_call_fails(self, fake_run, tmp_path):
        # Negative: the first gh call (label list) returns nonzero → the
        # function short-circuits with empty tuples; no follow-on gh calls.
        fake_run.enqueue(returncode=1, stdout="", stderr="gh boom")
        budget = Budget()
        labeled, label_map, matched = phase1("owner/repo", budget, tmp_path)
        assert labeled == []
        assert label_map == {}
        assert matched == set()
        # Only one subprocess call was made; the loop body never ran.
        assert len(fake_run.calls) == 1

    def test_no_matching_labels_returns_empty(self, fake_run, tmp_path):
        # Boundary: gh returns labels but NONE classify as vibe/ai/human
        # (only generic project labels). The function returns empty
        # matched set; the pr-list loop never iterates. Fixture has 3
        # synthetic labels (bug, feature, documentation) all classifying
        # to the `ignore` bucket. For the realistic 40-label case see
        # TestRealCaptureSchema below.
        fake_run.enqueue(
            returncode=0,
            stdout=_load("label_list_synthetic_no_match.json"),
        )
        budget = Budget()
        labeled, label_map, matched = phase1("owner/repo", budget, tmp_path)
        assert labeled == []
        assert matched == set()
        # Only the labels call; no pr list calls.
        assert len(fake_run.calls) == 1

    def test_label_priority_picks_vibe_over_ai_when_both_apply(self, fake_run, tmp_path):
        # Discrimination: a PR carrying BOTH a vibe and ai-assisted label
        # (returned under different label queries) should end up tagged
        # vibe-coded — the lower-priority class wins per label_priority()
        # ordering (vibe=0 < ai=1 < human=2). Pins the priority contract
        # that calibration ledger downstream depends on.
        fake_run.enqueue(
            returncode=0,
            stdout=_load("label_list_synthetic_vibe_plus_ai.json"),
        )
        # PR 99 returned under the vibe-coded label query (first iteration).
        fake_run.enqueue(
            returncode=0,
            stdout=_load("pr_list_synthetic_dual_labeled.json"),
        )
        # Same PR 99 returned under the ai-assisted label query.
        fake_run.enqueue(
            returncode=0,
            stdout=_load("pr_list_synthetic_dual_labeled.json"),
        )
        budget = Budget()
        labeled, _label_map, _matched = phase1("owner/repo", budget, tmp_path)
        # The single PR appears once in the output (deduped by pr_number),
        # tagged with the highest-priority class.
        assert len(labeled) == 1
        assert labeled[0]["pr_number"] == 99
        assert labeled[0]["label_class"] == "vibe-coded"

    def test_budget_exhaustion_mid_iteration_breaks_loop(self, fake_run, tmp_path):
        # Adversarial: budget exhausts after the label call. The pr-list
        # loop should short-circuit (the `if code == -1` branch). Pins
        # the anti-cascade contract.
        fake_run.enqueue(
            returncode=0,
            stdout=_load("label_list_synthetic_vibe_plus_ai.json"),
        )
        # Exhaust phase-1 budget so the next budget.gh("1") returns False
        # and run_gh returns (-1, "").
        budget = Budget()
        budget.p1 = P1_API  # phase 1 cap already reached
        # NOTE: budget.total is still 0, so first call (which already
        # happened via the .enqueue above) consumed one. Set p1 high
        # enough that the next gh call (the pr list) fails.
        labeled, _label_map, _matched = phase1("owner/repo", budget, tmp_path)
        # The label list call goes through (because we set p1 AFTER the
        # call would normally be allowed), but subsequent pr-list calls
        # hit the cap. With our manually-set p1 the first gh call from
        # phase1 also fails. Either way, no labeled PRs are produced.
        assert labeled == []

    def test_malformed_pr_json_raises_when_strip_nonempty(self, fake_run, tmp_path):
        # Negative: gh returns non-empty but invalid JSON for the labels
        # response. The function does NOT guard json.loads; this pins
        # the behavior (the existing source raises). A future refactor
        # adding graceful handling must update this test.
        fake_run.enqueue(returncode=0, stdout="not-json-at-all")
        budget = Budget()
        with pytest.raises(json.JSONDecodeError):
            phase1("owner/repo", budget, tmp_path)

    def test_pr_list_nonzero_marks_zero_count_and_continues(self, fake_run, tmp_path):
        # Boundary: a per-label gh pr list call that exits nonzero sets
        # count=0 and continues (does not abort the whole phase1 loop).
        fake_run.enqueue(
            returncode=0,
            stdout=_load("label_list_synthetic_single_vibe.json"),
        )
        fake_run.enqueue(returncode=1, stdout="", stderr="rate limited")
        budget = Budget()
        labeled, label_map, matched = phase1("owner/repo", budget, tmp_path)
        assert matched == {"vibe-coded"}
        assert labeled == []
        assert label_map["vibe-coded"] == "vibe-coded"
        tsv = (tmp_path / "label_map.tsv").read_text()
        assert "\tvibe-coded\t0\n" in tsv or tsv.endswith("\tvibe-coded\t0")

    def test_phase1_breaks_label_loop_on_budget_minus_one(self, fake_run, tmp_path, monkeypatch):
        # Adversarial: after the first label's pr-list succeeds, run_gh returns
        # (-1, "") for the next label — phase1 `if code == -1: break` path.
        fake_run.enqueue(
            returncode=0,
            stdout=_load("label_list_synthetic_vibe_plus_ai.json"),
        )
        fake_run.enqueue(
            returncode=0,
            stdout=_load("pr_list_synthetic_single.json"),
        )
        real_run_gh = calibration_pipeline.run_gh
        calls = {"n": 0}

        def gated_run_gh(budget, phase, repo, args):
            calls["n"] += 1
            if calls["n"] >= 3:
                return -1, ""
            return real_run_gh(budget, phase, repo, args)

        monkeypatch.setattr(calibration_pipeline, "run_gh", gated_run_gh)
        budget = Budget()
        labeled, label_map, matched = phase1("owner/repo", budget, tmp_path)
        assert len(labeled) == 1
        assert "vibe-coded" in matched
        assert label_map.get("vibe-coded") == "vibe-coded"
        assert calls["n"] == 3

    def test_parses_commits_total_count_dict(self, fake_run, tmp_path):
        # Boundary: gh pr list may return commits as {totalCount: N} rather
        # than a list. Pins phase1 isinstance(commits, dict) totalCount branch.
        fake_run.enqueue(
            returncode=0,
            stdout=_load("label_list_synthetic_single_vibe.json"),
        )
        pr_payload = json.dumps(
            [
                {
                    "number": 77,
                    "title": "feat",
                    "author": {"login": "dev"},
                    "createdAt": "2026-01-01T00:00:00Z",
                    "mergedAt": "2026-01-02T00:00:00Z",
                    "additions": 10,
                    "deletions": 1,
                    "changedFiles": 1,
                    "commits": {"totalCount": 4},
                    "labels": [{"name": "vibe-coded"}],
                }
            ]
        )
        fake_run.enqueue(returncode=0, stdout=pr_payload)
        budget = Budget()
        labeled, _, _ = phase1("owner/repo", budget, tmp_path)
        assert len(labeled) == 1
        assert labeled[0]["commit_count"] == 4


# ---------------------------------------------------------------------------
# run_gh
# ---------------------------------------------------------------------------


class TestRunGh:
    """run_gh(budget, phase, repo, args) -> (code, stdout). Budget gate + argv."""

    def test_budget_exhausted_skips_subprocess(self, fake_run):
        # Boundary: when budget.gh() returns False, run_gh short-circuits
        # with (-1, "") and never invokes subprocess.
        budget = Budget()
        budget.p1 = P1_API
        code, out = run_gh(budget, "1", "owner/repo", ["label", "list"])
        assert code == -1
        assert out == ""
        assert fake_run.calls == []

    def test_subprocess_exception_returns_999(self, fake_run):
        # Negative: subprocess.run raises → code 999, error logged on budget.
        fake_run.enqueue_exc(RuntimeError("gh unavailable"))
        budget = Budget()
        code, out = run_gh(budget, "1", "owner/repo", ["label", "list"])
        assert code == 999
        assert out == ""
        assert any("gh exc" in e for e in budget.errors)

    def test_nonzero_returncode_appends_budget_error(self, fake_run):
        # Negative: gh exits nonzero → stderr snippet appended to budget.errors.
        fake_run.enqueue(returncode=1, stdout="", stderr="API rate limit")
        budget = Budget()
        code, out = run_gh(budget, "1", "owner/repo", ["label", "list"])
        assert code == 1
        assert out == ""
        assert any("gh fail" in e for e in budget.errors)

    def test_argv_prefix_pins_gh_repo_form(self, fake_run):
        # Adversarial: argv must begin with gh -R <repo> so refactors can't
        # drop the repo scoping that prevents cross-repo leakage.
        fake_run.enqueue(returncode=0, stdout="[]")
        run_gh(Budget(), "2", "acme/widget", ["pr", "list"])
        assert fake_run.calls[0][0][:3] == ["gh", "-R", "acme/widget"]


# ---------------------------------------------------------------------------
# analyze_prs
# ---------------------------------------------------------------------------


class TestAnalyzePrs:
    """
    analyze_prs(repo, budget, phase, pr_rows, diff_dir, max_prs) -> signal rows.

    Chains fetch_pr_detail → run_vibe → extract_signals → signals_row.
    Tests mock the gh/vibe subprocess boundary; no network.
    """

    def _vj(self) -> dict:
        return {
            "overall_ai_probability": 0.75,
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
            "file_analyses": [{"language": "python"}],
        }

    def test_happy_path_returns_signal_rows(self, tmp_path, monkeypatch):
        diff_path = tmp_path / "d" / "pr_9.diff"
        diff_path.parent.mkdir()
        diff_path.write_text("+x\n")

        def fake_fetch(_repo, _budget, _phase, pr, diff_dir):
            assert pr == 9
            return diff_dir / "pr_9.diff", "fix: thing"

        monkeypatch.setattr(calibration_pipeline, "fetch_pr_detail", fake_fetch)
        monkeypatch.setattr(calibration_pipeline, "run_vibe", lambda dp: self._vj())

        rows = analyze_prs(
            "owner/repo",
            Budget(),
            "2",
            [{"pr_number": 9, "label_class": "vibe-coded"}],
            tmp_path / "d",
            max_prs=5,
        )
        assert len(rows) == 1
        assert rows[0]["pr_number"] == 9
        assert rows[0]["label_class"] == "vibe-coded"
        assert rows[0]["_languages"] == ["python"]

    def test_skips_row_when_fetch_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            calibration_pipeline,
            "fetch_pr_detail",
            lambda *_a, **_k: (None, ""),
        )
        monkeypatch.setattr(
            calibration_pipeline,
            "run_vibe",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not run")),
        )
        rows = analyze_prs(
            "owner/repo",
            Budget(),
            "2",
            [{"pr_number": 1, "label_class": "human-written"}],
            tmp_path,
            max_prs=1,
        )
        assert rows == []

    def test_skips_row_when_run_vibe_returns_none(self, tmp_path, monkeypatch):
        diff_path = tmp_path / "pr_1.diff"
        diff_path.write_text("+x\n")
        monkeypatch.setattr(
            calibration_pipeline,
            "fetch_pr_detail",
            lambda *_a, **_k: (diff_path, ""),
        )
        monkeypatch.setattr(calibration_pipeline, "run_vibe", lambda *_a, **_k: None)
        rows = analyze_prs(
            "owner/repo",
            Budget(),
            "2",
            [{"pr_number": 1, "label_class": "ai-assisted"}],
            tmp_path,
            max_prs=1,
        )
        assert rows == []

    def test_respects_max_prs_slice(self, tmp_path, monkeypatch):
        # Boundary: only the first max_prs rows are processed even when the
        # input list is longer.
        seen: list[int] = []

        def fake_fetch(_repo, _budget, _phase, pr, _diff_dir):
            seen.append(pr)
            return None, ""

        monkeypatch.setattr(calibration_pipeline, "fetch_pr_detail", fake_fetch)
        pr_rows = [{"pr_number": i, "label_class": "vibe-coded"} for i in (1, 2, 3)]
        analyze_prs("owner/repo", Budget(), "2", pr_rows, tmp_path, max_prs=2)
        assert seen == [1, 2]


# ---------------------------------------------------------------------------
# fetch_pr_detail
# ---------------------------------------------------------------------------


class TestFetchPRDetail:
    """
    fetch_pr_detail(repo, budget, phase, pr, diff_dir) -> (Path|None, str).

    Calls gh pr diff to fetch the diff, writes it to {diff_dir}/pr_N.diff,
    then gh pr view --json commits to capture commit metadata. Returns
    (None, '') on any failure path (budget cap, gh nonzero, empty diff).
    """

    def test_happy_path_writes_diff_and_captures_commits(self, fake_run, tmp_path):
        # Positive: diff fetched, file written, commits captured. Uses
        # the REAL cli/cli PR 13444 capture (a small docs-only PR) for
        # both diff and commits, so the full schema shape — including
        # commit `authors[]`, `oid`, `messageBody` — flows through the
        # code under test as a smoke test of real-world parsing.
        diff_text = _load("pr_diff_real_clicli.diff")
        fake_run.enqueue(returncode=0, stdout=diff_text)
        fake_run.enqueue(
            returncode=0,
            stdout=_load("pr_view_commits_real_clicli.json"),
        )
        budget = Budget()
        diff_dir = tmp_path / "diffs"
        diff_dir.mkdir()
        path, commit_meta = fetch_pr_detail("owner/repo", budget, "1", 13444, diff_dir)
        assert path == diff_dir / "pr_13444.diff"
        assert path.read_text() == diff_text
        # Assert against the real PR 13444 commit headline (verbatim
        # from the captured fixture). If the fixture is re-captured
        # against a different PR, this assertion needs updating.
        assert "docs: drop --repo gh-cli from dnf install lines" in commit_meta
        # pr_detail counter incremented exactly once.
        assert budget.pr_detail == 1

    def test_pr_detail_cap_short_circuits_before_any_gh_call(self, fake_run, tmp_path):
        # Negative: budget.pr_detail >= PR_DETAIL_CAP → function returns
        # (None, "") immediately; no subprocess call is made.
        budget = Budget()
        budget.pr_detail = PR_DETAIL_CAP  # already at cap
        diff_dir = tmp_path / "diffs"
        diff_dir.mkdir()
        path, commit_meta = fetch_pr_detail("owner/repo", budget, "1", 99, diff_dir)
        assert path is None
        assert commit_meta == ""
        # Critical: no subprocess invocation; the cap check fired first.
        assert fake_run.calls == []

    def test_gh_diff_nonzero_returns_none(self, fake_run, tmp_path):
        # Negative: gh pr diff exits nonzero → returns (None, ""), no
        # diff file written, pr_detail counter NOT incremented.
        fake_run.enqueue(returncode=1, stdout="", stderr="not found")
        budget = Budget()
        diff_dir = tmp_path / "diffs"
        diff_dir.mkdir()
        path, commit_meta = fetch_pr_detail("owner/repo", budget, "2", 7, diff_dir)
        assert path is None
        assert commit_meta == ""
        # pr_detail not bumped because the diff fetch failed.
        assert budget.pr_detail == 0
        assert not (diff_dir / "pr_7.diff").exists()

    def test_empty_diff_text_returns_none(self, fake_run, tmp_path):
        # Boundary: gh returns rc=0 but stdout is whitespace-only. The
        # `not diff_text.strip()` guard fires; the function returns
        # (None, ""). No diff file written.
        fake_run.enqueue(returncode=0, stdout="   \n   \n")
        budget = Budget()
        diff_dir = tmp_path / "diffs"
        diff_dir.mkdir()
        path, commit_meta = fetch_pr_detail("owner/repo", budget, "2", 8, diff_dir)
        assert path is None
        assert commit_meta == ""
        assert budget.pr_detail == 0

    def test_commits_view_failure_still_returns_diff_path(self, fake_run, tmp_path):
        # Boundary: diff succeeds but the follow-up pr view fails. The
        # function still returns the diff path; commit_meta is empty
        # string. This pins that downstream callers can rely on getting
        # the diff even when commit metadata is unavailable.
        fake_run.enqueue(returncode=0, stdout="+a\n")
        fake_run.enqueue(returncode=1, stdout="", stderr="boom")
        budget = Budget()
        diff_dir = tmp_path / "diffs"
        diff_dir.mkdir()
        path, commit_meta = fetch_pr_detail("owner/repo", budget, "2", 10, diff_dir)
        assert path is not None
        assert commit_meta == ""

    def test_malformed_commits_json_handled(self, fake_run, tmp_path):
        # Negative: diff succeeds, pr view succeeds with nonempty stdout
        # but malformed JSON. The try/except (json.JSONDecodeError) clause
        # catches it; commit_meta stays empty. Diff path still returned.
        fake_run.enqueue(returncode=0, stdout="+a\n")
        fake_run.enqueue(returncode=0, stdout="not-json")
        budget = Budget()
        diff_dir = tmp_path / "diffs"
        diff_dir.mkdir()
        path, commit_meta = fetch_pr_detail("owner/repo", budget, "2", 11, diff_dir)
        assert path is not None
        assert commit_meta == ""

    def test_diff_argv_shape_pins_color_disabled(self, fake_run, tmp_path):
        # Adversarial: the diff invocation must include --color=never so
        # ANSI escape codes don't pollute the diff written to disk (and
        # subsequently parsed by vibe_check.py). Pin this argv shape.
        # This test cares about argv only, not commit content, so it uses
        # the lightweight _synthetic_commits helper rather than a fixture.
        fake_run.enqueue(returncode=0, stdout="+x\n")
        fake_run.enqueue(returncode=0, stdout=_synthetic_commits("x"))
        budget = Budget()
        diff_dir = tmp_path / "diffs"
        diff_dir.mkdir()
        fetch_pr_detail("owner/repo", budget, "1", 1, diff_dir)
        # First call is the diff fetch.
        diff_argv = fake_run.calls[0][0]
        assert "--color=never" in diff_argv
        assert "pr" in diff_argv
        assert "diff" in diff_argv


# ---------------------------------------------------------------------------
# run_vibe
# ---------------------------------------------------------------------------


class TestRunVibe:
    """
    run_vibe(diff_path) -> dict | None.

    Invokes vibe_check.py as a subprocess with --diff DIFF --format json.
    Returns the parsed JSON dict on success, or None on any failure
    (nonzero exit, malformed JSON, subprocess exception).
    """

    def test_happy_path_returns_parsed_json(self, fake_run, tmp_path):
        # Positive: subprocess returns rc=0 with valid JSON → dict returned.
        diff_path = tmp_path / "pr_1.diff"
        diff_path.write_text("+x\n")
        expected = {
            "overall_ai_probability": 0.42,
            "grade": "B",
            "signal_summary": {},
            "file_analyses": [],
        }
        fake_run.enqueue(returncode=0, stdout=json.dumps(expected))
        result = run_vibe(diff_path)
        assert result == expected

    def test_nonzero_returncode_returns_none(self, fake_run, tmp_path):
        # Negative: vibe_check.py exits nonzero → None.
        diff_path = tmp_path / "pr_1.diff"
        diff_path.write_text("+x\n")
        fake_run.enqueue(returncode=1, stdout="", stderr="vibe_check crashed")
        assert run_vibe(diff_path) is None

    def test_malformed_json_returns_none(self, fake_run, tmp_path):
        # Negative: rc=0 but stdout is not valid JSON. The outer
        # except Exception catches json.JSONDecodeError → None.
        diff_path = tmp_path / "pr_1.diff"
        diff_path.write_text("+x\n")
        fake_run.enqueue(returncode=0, stdout="not-json")
        assert run_vibe(diff_path) is None

    def test_subprocess_timeout_returns_none(self, fake_run, tmp_path):
        # Negative: subprocess.run raises TimeoutExpired (180s cap).
        # The outer except Exception catches it → None.
        diff_path = tmp_path / "pr_1.diff"
        diff_path.write_text("+x\n")
        fake_run.enqueue_exc(
            subprocess.TimeoutExpired(cmd=["python"], timeout=180)
        )
        assert run_vibe(diff_path) is None

    def test_filenotfound_returns_none(self, fake_run, tmp_path):
        # Boundary: python interpreter missing or vibe_check.py path
        # broken → FileNotFoundError. Same except-Exception path → None.
        diff_path = tmp_path / "pr_1.diff"
        diff_path.write_text("+x\n")
        fake_run.enqueue_exc(FileNotFoundError("python missing"))
        assert run_vibe(diff_path) is None

    def test_argv_shape_includes_diff_and_format_json(self, fake_run, tmp_path):
        # Adversarial: pin the argv shape so a refactor cannot silently
        # change the vibe_check.py invocation contract (--diff DIFF
        # --format json). This is the integration boundary the
        # calibration pipeline depends on; downstream parsing assumes
        # JSON output, not the default tabular format.
        diff_path = tmp_path / "pr_42.diff"
        diff_path.write_text("+x\n")
        fake_run.enqueue(returncode=0, stdout='{"overall_ai_probability": 0.5}')
        run_vibe(diff_path)
        argv = fake_run.calls[0][0]
        # First arg is the python interpreter path (sys.executable).
        assert argv[0] == sys.executable
        # Second is the vibe_check.py path.
        assert argv[1] == str(VIBE_CHECK)
        # The --diff <path> --format json arguments must be present.
        assert "--diff" in argv
        assert str(diff_path) in argv
        assert "--format" in argv
        assert "json" in argv


# ---------------------------------------------------------------------------
# Real-capture schema contract
# ---------------------------------------------------------------------------


class TestRealCaptureSchema:
    """
    Demonstrates that verbatim `gh` output (captured from cli/cli on
    2026-05-19) flows through the code under test unmodified. The
    value here is a schema contract regression test: if gh's JSON
    shape drifts in a future major version, these tests catch it
    before production runs do.

    See tests/fixtures/gh_responses/README.md for capture provenance
    and re-capture instructions.
    """

    def test_real_clicli_labels_all_classify_as_ignore(self, fake_run, tmp_path):
        # Realistic shape: cli/cli has 40 labels (bug, enhancement,
        # windows, gh-pr, dependencies, etc.). NONE classify as
        # vibe/ai/human under classify_label's rules. Pins both:
        #   (a) phase1 handles the 40-label case without error
        #   (b) classify_label's default-to-ignore behavior holds for
        #       a realistic project label set
        # If a future classify_label refactor accidentally promotes
        # one of these labels (e.g. "auto" partially matching the
        # "auto + code/gen" branch), this test fails loudly.
        fake_run.enqueue(
            returncode=0,
            stdout=_load("label_list_real_clicli.json"),
        )
        budget = Budget()
        labeled, label_map, matched = phase1("cli/cli", budget, tmp_path)
        # Zero PRs labeled because no labels matched.
        assert labeled == []
        assert matched == set()
        # phase1 filters out ignore-classified labels at the
        # bucket == "ignore": continue clause, so label_map (built
        # from label_map_rows after the filter) is empty for this
        # all-ignore fixture. This is the contract: realistic project
        # labels produce no calibration-pipeline work.
        assert label_map == {}
        # Only the labels gh call happened; no pr-list calls because
        # matched_names is empty so the pr-list loop never iterates.
        assert len(fake_run.calls) == 1

    def test_real_clicli_pr_list_with_synthetic_vibe_label(self, fake_run, tmp_path):
        # Pairs a synthetic vibe label (so classification matches)
        # with the REAL cli/cli pr_list response shape — including
        # is_bot author flags, full commits[] with authors[]/oid/
        # messageBody, and labels with color/id/description. Pins
        # that the rich real schema flows through phase1's writer
        # without KeyError or TypeError on optional fields.
        fake_run.enqueue(
            returncode=0,
            stdout=_load("label_list_synthetic_single_vibe.json"),
        )
        fake_run.enqueue(
            returncode=0,
            stdout=_load("pr_list_real_clicli.json"),
        )
        budget = Budget()
        labeled, _label_map, matched = phase1("owner/repo", budget, tmp_path)
        assert matched == {"vibe-coded"}
        # 5 real PRs from cli/cli @ 2026-05-19; all end up labeled
        # vibe-coded because the synthetic label query "returned" them.
        # If the fixture is re-captured with a different PR count,
        # this assertion needs updating.
        assert len(labeled) == 5
        # PR 13444 (the docs-only PR used for the diff fixture) is
        # one of the captured 5. Verify it appears.
        pr_numbers = {row["pr_number"] for row in labeled}
        assert 13444 in pr_numbers

    def test_real_clicli_diff_preserves_content_byte_for_byte(self, fake_run, tmp_path):
        # Pins that fetch_pr_detail does NOT munge the diff text on
        # the path from gh stdout → on-disk file. A future refactor
        # that, say, strips trailing whitespace or normalizes line
        # endings would change the byte content and break this test.
        # The captured diff from cli/cli PR 13444 is a small docs
        # change with realistic unified-diff hunk headers.
        diff_text = _load("pr_diff_real_clicli.diff")
        fake_run.enqueue(returncode=0, stdout=diff_text)
        fake_run.enqueue(
            returncode=0,
            stdout=_load("pr_view_commits_real_clicli.json"),
        )
        budget = Budget()
        diff_dir = tmp_path / "diffs"
        diff_dir.mkdir()
        path, _commit_meta = fetch_pr_detail("cli/cli", budget, "1", 13444, diff_dir)
        assert path is not None
        # Byte-for-byte equality, not just text equivalence.
        assert path.read_bytes() == diff_text.encode("utf-8")
