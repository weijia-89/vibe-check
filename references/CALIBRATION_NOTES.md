# Calibration notes — what each default actually represents

Every default threshold and weight in `scripts/vibe_check.py` is a **speculative
prior**, not an empirically fitted value. This file says exactly what each is
based on so a future contributor can replace them with real data.

> **Why this file exists.** The previous version of the codebase carried a
> comment "from Gemini research, Table 1" next to `SIGNAL_THRESHOLDS`. No such
> table existed in any cited source. That comment was removed in v0.2.0. This
> file replaces it with an honest accounting.

## What we know from the cited literature

The most-cited paper in this repo is Tao et al. (arXiv:2409.01382, see CLAIMS
C-007): SHAP feature importance across four LLMs identified Comment-to-Code
Ratio as the *only* universally predictive feature, but its predictive
magnitude varies by model and modern-model AUC-ROC sits at ~0.68–0.80. AICD
Bench (CLAIMS C-008) confirms that detectors of this class are "far below
practical usability" under distribution shift.

**Implication.** A single fixed weight per signal is scientifically
incorrect — the same signal contributes very differently per model and per
language. Defaults in this repo should be treated as a *starting prior* that
must be replaced by per-codebase calibration before any quantitative claim.

## Signal-by-signal accounting

| Signal | Weight | Default thresholds | Source of the number | Status |
|--------|-------:|--------------------|----------------------|--------|
| `comment_ratio` | 0.18 | human ≈ 0.15, LLM ≈ 0.50 | Authored ranges; not from a fitted study. CLAIMS C-007 confirms CCR is universally predictive but says nothing about absolute thresholds. | speculative prior |
| `docstring_consistency` | 0.15 | human ≈ 0.25, LLM ≈ 0.90 | Authored ranges. CLAIMS C-006 confirms naming/structure differ for LLM-paraphrased code; no specific docstring-coverage numbers in the cited abstracts. | speculative prior |
| `naming_uniformity` | 0.13 | human ≈ 0.80, LLM ≈ 0.97 | Authored ranges. **Caveat: PEP 8 enforces snake_case in Python, gofmt enforces formatting in Go.** A high uniformity score in those languages is the language baseline, not an AI signal. The Python adapter applies a stricter floor (0.99) before flagging. | speculative prior, language-confounded |
| `error_handling` | 0.12 | LLM ≈ 0.60 | Authored. CLAIMS P-003 (`Survey of bugs in AI-generated code`) does not give a specific shallow-error-handling rate in the abstract. | speculative prior |
| `declarative_bias` | 0.10 | LLM ≈ 2.2× declarative/control | Authored. No paper in CLAIMS cites this ratio. | speculative prior |
| `function_length` | 0.08 | CV ≈ 0.3 | Authored. The Tao et al. paper (C-007) does not cite a CV threshold. | speculative prior |
| `comment_phrasing` | 0.08 | hit-rate ≈ 0.45 | Authored regex set; matched against a small list of common imperative comment phrases. No cited evidence for the specific 0.45 cutoff. | speculative prior |
| `hallucinated_apis` | 0.06 | binary, raw count | 12-pattern regex catalog; **patterns are real bugs the authors have seen**, but the catalog is small and language-skewed. Pearce/Fu (C-001, C-002) document insecure code generation; they don't enumerate hallucinated APIs as a feature. | catalog-based, narrow |
| `edge_case_depth` | 0.05 | nesting ≤ 2 + few null checks | Authored. The previous Python implementation was buggy (monotonic increment); v0.2.0 uses indent-based depth tracking on added lines. Even fixed, the threshold is authored. | speculative prior, implementation-fixed |
| `commit_metadata` | 0.05 | binary, regex hit | Pattern set is reasonable (matches "Co-authored-by: Claude" etc.), but the conventional-commits regex inside the set causes false positives on disciplined human teams. | catalog-based, narrow |

## How to replace these defaults with empirical values

1. Collect **at least 100 labeled PRs** (50 confirmed-AI, 50 confirmed-human) from the codebase you are calibrating for. Use `vibe-coded` / `copilot` / `llm` labels or a manual label sheet.
2. Run `scripts/calibration_pipeline.py --repo OWNER/REPO --out-dir outputs/cal_$(date +%s)/`.
3. Read `outputs/cal_*/discrimination.tsv`. Per-signal best Youden split is the **codebase-specific threshold**.
4. Read `outputs/cal_*/threshold_comparison.tsv`. If `youden_threshold` differs from the speculative default by more than 25%, **prefer the Youden value**.
5. Write the chosen thresholds to `calibration_override.json` next to your telemetry directory. They are loaded at import.
6. Validate: re-run on a held-out 20% of the labeled set. If F1 < 0.7, the signal isn't useful for your codebase. Either lower its weight or drop it.

## What "outputs/vibe-baseline-calibration/" is

A demo run on 5 PRs from one author. It is **not** a baseline. The summary
file (`outputs/vibe-baseline-calibration/summary.txt`) says so explicitly:
"Small pool (5 PRs); baselines are indicative only." Treat it as fixture
data for testing the pipeline runner, nothing more.

## Open work

| ID | Question | Owner | Notes |
|----|----------|-------|-------|
| K-001 | Per-signal weight fitting on a labeled corpus ≥ 1,000 PRs across ≥ 5 repos | unassigned | Required to drop "speculative prior" tags |
| K-002 | Per-language baselines (Python, JS/TS, Go, Java, Rust) for `naming_uniformity`, `comment_ratio`, `function_length` | unassigned | Tao et al. (C-007) shows magnitude varies by model; will also vary by language |
| K-003 | VIF analysis on signals across a real telemetry corpus | unassigned | `scripts/signal_correlation_vif.py` exists but has never been run on real data in this repo |
| K-004 | Empirical fit for `MODEL_FINGERPRINTS`. Until done, `--model-evolution` is fenced as `EXPERIMENTAL_DISABLED`. | unassigned | Requires labeled-by-model corpus, e.g. LLM-AuthorBench (C-009) |
| K-005 | Body-text quote for Sandoval EMSE 33%/25% (CLAIMS P-001) or removal of that prose | unassigned | Springer paywall; access via institutional library |
