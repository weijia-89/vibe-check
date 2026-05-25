# Changelog

Entries track changes to `vibe-check` (folder renamed from `AIDetector`). Dates follow the day files landed in the workspace.

## [0.2.0] - 2026-05-14 - Honest framing, root-cause bug fixes, citation rebuild

This release rolls back two false claims and fixes four bugs in the scoring code. The aggregate score on the tool's own source dropped from 36% (grade C) to 24% (grade B) because the bugs were inflating the score in ways the v0.1.x test suite never caught. We checked.

### Added

- `references/CALIBRATION_NOTES.md`. Per-signal accounting of what each default threshold and weight actually represents. This replaces the deleted "from Gemini research, Table 1" code comment. Open work tracked as K-001 through K-005.
- `tests/test_analyzers.py`. 22 unit tests, one per bug fixed. If `edge_case_depth` ever regresses to its monotonic-increment behavior, `TestEdgeCaseDepthPython::test_self_dogfood_realistic_depth` will fail.
- Real diff fixtures under `tests/fixtures/`: clean-human Python, an AI-style dump with heavy docstrings, a hallucinated-API trigger, clean-human JavaScript, a bare-except example.
- `.github/workflows/test.yml`. Runs on push and PR across Python 3.10, 3.11, 3.12, 3.13. Steps: unittest, smoke, `check_claims.py` Mode A, `check_claims.py --strict-quotes`, dogfood. Every step must exit zero; there's no `|| true` anywhere.
- `--no-aggregate` CLI flag. Suppresses the AI Probability headline and the letter grade in Markdown and JSON output. Per-signal evidence stays. We recommend this for reviewers who tend to anchor on the single number.
- `compute_residual_quantile_margin` and `compute_residual_margin_from_result`. These replace the misnamed `compute_conformal_ci*` pair. More on the rename below.
- Mode B in `scripts/check_claims.py`. With `--strict-quotes`, CI fails if any CLAIMS.md row has an empty `quote` field. Rows tagged `primary?: secondary` are exempt because industry consensus doesn't have one canonical passage to quote.

### Changed

- **Root-cause bug fixes in `scripts/vibe_check.py`.**
  - `analyze_edge_case_depth` for Python. The implementation only ever incremented. There are no `}` characters in Python for it to decrement on, so it kept counting upward all the way through the file. On the tool's own source it reported `Depth=198`, which is nonsense. Replaced with indent-based depth tracking. Empirical check: 198 dropped to 6 on the same input.
  - `analyze_error_handling` regex. The old pattern was `except\s*(?:Exception|BaseException|\s*:)`. That matched `except ExceptionGroup` on Python 3.11+ by prefix, which is wrong. New version uses `\b`-bounded patterns and three tiers. Bare `except:` adds 0.3 to the score, broad `except Exception` adds 0.1, specific types contribute nothing. Test: `TestErrorHandlingPython::test_exception_group_not_matched_as_broad`.
  - `analyze_declarative_bias` regex. The old pattern was `^\s*\w+\s*=\s*`. It matched `assert x == 1` and `if foo == bar:` as assignments, which biased the signal upward on test code. Now uses a negative-lookahead `(?![=<>!])` so `==`, `!=`, `<=`, `>=`, and `=>` no longer count.
  - `analyze_naming_uniformity` for Python and Go. The old curve scored 0.91 on PEP-8 compliant code, labeling 98% snake_case as "AI-typical consistency". This was confusing the language standard with an LLM tell. Now Python and Go uniformity is capped at 0.4 (soft signal only). Other languages keep the previous curve because they don't have an equivalent style enforcer.
  - `analyze_function_length` confidence cap. The signal was reporting confidence up to 0.7 on what's really a diff-only approximation (we don't see the full function body). Now capped at 0.4. See CALIBRATION_NOTES K-002.
- **Naming and disclaimers.**
  - `compute_conformal_ci` and `compute_conformal_ci_from_result` are now deprecated shims that emit `DeprecationWarning`. The real names are `compute_residual_quantile_margin` and `compute_residual_margin_from_result`. The old name implied a coverage guarantee the math doesn't provide. Real conformal prediction needs a held-out calibration set with labels, a nonconformity score, and a coverage theorem. None of those hold here.
  - The two CI-style functions previously used different formulas. The live-signal path used `(1 - alpha)` quantile; the from-result path used a hardcoded 0.9. Now both use `(1 - alpha)`.
  - `--show-ci` Markdown line: "Confidence Interval (90%)" became "Residual-quantile margin (heuristic; no coverage guarantee)".
  - The `# from Gemini research, Table 1` comment is gone. No such table existed in any cited source; we'd been propagating a hallucination. `SIGNAL_THRESHOLDS` is now labeled "SPECULATIVE PRIORS, NOT FITTED" with a pointer to CALIBRATION_NOTES.md.
- **Experimental subsystems are now fenced.**
  - `detect_model_evolution()` returns `{"status": "EXPERIMENTAL_DISABLED"}` unless `VIBE_CHECK_ENABLE_MODEL_EVOLUTION=1`. The `MODEL_FINGERPRINTS` table was unsourced. Don't flip the env var until you've fit the table on a labeled-by-model corpus. Tracked as CALIBRATION_NOTES K-004.
- **`references/CLAIMS.md` rebuilt.**
  - Every row now carries a literal abstract quote from one of 11 verified arXiv papers, all accessed 2026-05-14.
  - Fu et al. numbers corrected from "32.8% Python / 24.5% JS / 38-43 CWEs" to "29.5% / 24.2% / 43 CWEs". The old numbers didn't match the abstract; we don't know where they came from.
  - The "Sandoval EMSE 33% vs 25%" claim is now Pending (P-001). The Springer EMSE page is gated, the arXiv version (2208.09727, "Lost at C") is a different study reporting ≤10% delta. Reading the EMSE PDF directly would resolve this.
  - Tao et al. (arXiv:2409.01382) re-attributed. The paper does conclude that CCR is universal, but it also reports AUC-ROC varies 0.68-0.96 across models. That second number undermines using one fixed weight everywhere.
  - New row C-005: Wang et al. (ICSE 2025) explicitly say existing detectors "perform poorly and lack sufficient generalizability to be practically deployed". The skill's own framing now says that out loud instead of around it.
  - Schema now requires non-empty `quote` field; the lint enforces.
- **`scripts/check_claims.py`** has two modes. Mode A (citation reachability) is unchanged. Mode B (`--strict-quotes`) enforces non-empty primary-source quotes with the `secondary`-row exemption. CI runs both.
- **`SKILL.md`** is rewritten around "reviewer evidence surfacer", not detector. The framing now acknowledges AICD Bench and Wang findings up front rather than burying them in a limitations section.
- **`README.md`** rewritten on the same honest framing. The `outputs/vibe-baseline-calibration/` directory is now explicitly labeled a 5-PR demo, not a baseline. (We should have done this earlier.)
- **`tests/test_skill_smoke.sh`** lost its `|| true` suffix on the Markdown check. Previously the test was unfailable. Added four more integration assertions: `--no-aggregate` Markdown contract, `--no-aggregate` JSON contract, `--drift-status` returns `NO_TELEMETRY` by default, `--model-evolution` returns `EXPERIMENTAL_DISABLED` by default.

### Removed

- The `# from Gemini research, Table 1` code comment (line 1170 of pre-v0.2.0). No such table existed.
- The "deterministic AI code detection based on empirical research" footer in the Markdown report. Replaced with a scope note pointing at CLAIMS C-005 and C-008.

### Notes for callers

- The CLI contract is preserved. JSON keys (`overall_ai_probability`, `grade`, `signal_summary`, `file_analyses`, `pattern_taxonomy`, `recommendations`, `methodology_notes`, `evidence_status`, `confidence_interval`) keep their names. New keys appear only when `--no-aggregate` is set: `aggregate_suppressed: true`, and the three aggregate keys become `null`.
- Telemetry schema unchanged. The residual margin is still emitted under the key `confidence_interval` for backwards compatibility. Renaming it would break consumers, so we left it.
- `CALIBRATION_VERSION` changed from `"v2026_q2_gemini"` to `"v0.2.0_honest"`. `load_calibration_overrides()` accepts the old string as a legacy synonym so existing calibration files keep working.
- Deprecated function names emit `DeprecationWarning` but continue to work. They'll stay for at least one more minor version.

### One thing we still don't know

The default weights in `SIGNAL_THRESHOLDS` are speculative. Tao et al. show CCR's AUC-ROC ranges 0.68 to 0.96 across models, so a single fixed weight cannot generalize. Run `scripts/calibration_pipeline.py` on a labeled corpus from your own codebase before treating any per-signal number as authoritative. CALIBRATION_NOTES K-001 through K-005 list the specific open questions.

## [Unreleased]

### Added

- Branch-gap tests for `calibration_pipeline` pure helpers (`write_tsv`, `phase4`, `run_gh`, `analyze_prs`) and `check_drift_status` orchestration paths (TRIGGER/WATCH/ci_collapse); CI enforces a combined coverage floor only (`--fail-under=38` on the drift+calibration test surface; per-module baselines in workflow comments are informational).
- `references/EVIDENCE_LEDGER.md`. A hyperlinked bibliography covering the Gemini synthesis, `RESEARCH.md`, `CLAIMS.md`, and `SKILL.md`. Every link HTTP-checked. Bot-gated URLs (ACM DOI landing pages, PMC HEAD) are flagged rather than removed.
- `references/CLAIMS.md`. A smaller quote-level ledger for numeric claims. `scripts/check_claims.py` is the lint. It covers arXiv IDs, named papers, and numeric mentions of PSI or SWE-bench.
- `scripts/eval_drift.py`. An offline threshold-grid replay that reads `vibe_check_telemetry.jsonl` and a labeled week or day CSV. Writes `grid_results.tsv`, `metric_roc.tsv`, and `summary.json` (best by MCC).
- `scripts/signal_correlation_vif.py`. Pearson correlation and exact VIF (OLS R² per column) computed from telemetry. Emits a `weights_suggestion_renorm.json` fragment for manual merge. Live weights are not touched.
- `scripts/review_depth.py`. A `gh pr view` wrapper that emits audit-priority JSON (commit cadence, file spread, why/what body score).
- `docs/AUDIT_PRIORITY_ETHICS.md`. Deployment guardrails for audit-priority output covering framing, retention, and kill switch.
- `docs/CHANGE_PLAN_20260417_six_followups.md` and `docs/CHANGE_PLAN_20260417_psi_persistence_claims.md`. Two Feathers-style change plans for the recent batches.
- `examples/hallucination_extras.example.json`. A template for `VIBE_CHECK_HALLUCINATION_EXTRAS`.

### Changed

- `scripts/vibe_check.py`
  - `VIBE_CHECK_DRIFT_GLOBAL_METRIC` now accepts `psi` alongside `mean_shift` (default, unchanged) and `sinkhorn` (experimental). Default PSI threshold is 0.25 via `VIBE_CHECK_DRIFT_PSI_THRESHOLD`.
  - Added M-of-N persistence via `VIBE_CHECK_DRIFT_PERSISTENCE_M` and `_N`. A lone raw trip becomes `WATCH`. State lives in `drift_persistence.json` under `VIBE_CHECK_TELEMETRY_DIR`.
  - Drift JSON gains `raw_status`, `global_drift_psi`, `global_drift_mean_shift`, `global_drift_sinkhorn`, `drift_global_metric`, `drift_threshold`, `persistence`, and a `layers` block (telemetry, signal, score, override_placeholder).
  - Moved the hallucinated-API list to `HALLUCINATION_PATTERN_BUILTINS` with an optional merge from `VIBE_CHECK_HALLUCINATION_EXTRAS`.
- `references/GEMINI_AI_CODE_DETECTION_RESEARCH.md`. Added a citation spot-check table with CLAIMS.md IDs. Softened phrasing around DuCodeMark and Feitelson. Routed hyperlinks through `EVIDENCE_LEDGER.md`.
- `SKILL.md`. Compressed the self-healing section to one table. Marked PSI as the recommended primary metric. Documented persistence and the layer snapshot.
- `README.md`. Rewrote around entry points and opt-in flags.
- `scripts/vibe_detect/`. Relocated `vibe_detect.py`, `signals.py`, and `vibe_detect_results.json` from `ai-governance/revert-report/vibe-detect/`.

### Notes

- The default scoring path and JSON contract did not change. New drift fields are additive. Consumers that read `status`, `per_signal`, and `drifted_signals` keep working.
- No new Python dependencies. Stdlib only.
- Default run directory for the calibration pipeline is `outputs/calibration_<UTC timestamp>/`.

## Earlier entries (folder still named `AIDetector`)

- Converted the repo to a git working tree with a `.gitignore` for `outputs/`, `__pycache__`, and common junk.
- Added `SECURITY.md` covering threat model, `git` and `gh` boundaries, and telemetry handling.
- Shipped self-healing hooks in `scripts/vibe_check.py`.
  - `load_calibration_overrides()` auto-applies `calibration_override.json` at import. Weights are bounded 0.02 to 0.30 and renormalized.
  - `recalibrate_from_drift()` does a quantile-shift from telemetry with a 60/40 baseline split and a ±20% cap. It aborts recalibration when more than 60% of scores land in 0.3–0.7.
  - `MODEL_FINGERPRINTS` and `detect_model_evolution()` flag runs whose signal profiles fall outside known families.
  - `discover_new_patterns()` is a stub for mining telemetry-gated comment patterns. It needs diff caching first.
- Added CLI flags `--recalibrate`, `--dry-run`, and `--model-evolution`.
- Shipped `scripts/calibration_pipeline.py`. It joins labels to diffs, scores per PR, computes pseudo-labels, runs ROC-style stats, writes `dataset_summary.json`, and caps at 3000 `gh` calls and 300 diffs.
- Added `docs/ARCHITECTURE.md` with the pipeline diagram and data flow.
