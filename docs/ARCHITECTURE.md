# Vibe-Check Architecture

## What this is

Vibe-check is a **reviewer evidence surfacer** for PR diffs: it runs ten regex/AST heuristics
that *correlate* with LLM-generated code in published studies and emits per-signal evidence so
a reviewer can ask better follow-up questions. It is not a detector. Recent benchmarks
(CLAIMS C-005 Wang et al. ICSE 2025; CLAIMS C-008 AICD Bench 2026) report detectors of this
class as below practical usability under distribution shift.

A calibration loop is also provided: telemetry → drift detection → threshold-shift overrides.
The defaults shipped in this repo are **speculative priors** (see `references/CALIBRATION_NOTES.md`)
and should be replaced via `scripts/calibration_pipeline.py` on a labeled corpus from the user's
codebase before any quantitative claim. The pipeline shells out to `gh`, runs the deterministic
analyzer on each diff, and writes per-signal split statistics. There is no model training step.

## Layout

```
vibe-check/
  scripts/
    vibe_check.py              # Diff → scores (JSON/Markdown), telemetry + drift + recalibration loop, CLI
    vibe_calibration.py        # Stratified PR baselines → outputs/vibe-baseline-calibration/
    signal_correlation_vif.py  # Offline: telemetry JSONL → VIF / correlation (no weight writes)
    review_depth.py            # Optional: gh pr view → audit-priority JSON (artifact-only)
    calibration_pipeline.py    # Orchestration + Phase 4 stats
    calibration_override.json  # [generated] Threshold/weight overrides from recalibration
    vibe_detect/               # Batch PR scanner (moved from ai-governance/revert-report/)
      vibe_detect.py
      signals.py
      vibe_detect_results.json
  outputs/
    calibration_<UTC>/         # One run per invocation (or --out-dir)
    vibe-baseline-calibration/
  references/
    RESEARCH.md                # Full bibliography (60+ sources), GRADE assessments
    PROMPT_SIGNAL_DECAY_SELFHEALING.md  # Gemini-validated research annotations
```

`calibration_pipeline.py` sits beside `vibe_check.py`, so the subprocess can call `python vibe_check.py --diff <file> --format json` with no extra install.

## Data flow

1. **Labels to PR list (Phase 1)**  
   `gh label list` loads names. Each name maps to `vibe-coded`, `ai-assisted`, `human-written`, or is skipped. For each kept label, `gh pr list --label … --state merged --limit 100` pulls metadata. If a PR has several labels, one row wins: `label_class` uses a fixed order (vibe-coded, then ai-assisted, then human-written).

2. **Labeled PRs to signals (Phase 2)**  
   At most 150 labeled PRs run, sorted with vibe-coded first, then by change size. For each PR run `gh pr diff` and `gh pr view --json commits`. Write the patch to disk and pass it to `vibe_check`. Column names in the TSV shorten internal keys (`comment_ratio` becomes `ccr`, and so on).

3. **Unlabeled pool to pseudo-labels (Phase 3)**  
   One `gh pr list` pulls up to 500 merged PRs. Any row whose labels overlap the Phase 1 “matched” set is dropped. The remainder is split by addition count and merge date, then up to 100 PRs get the same diff and vibe pass. Labeled `vibe-coded` and `human-written` rows define mean signal vectors (prototypes). If one side is missing, Phase 2’s top or bottom quartile by `overall_ai_prob` fills in. Cosine similarity to each prototype gives a ratio; cutoffs at 2.0 and 0.5 yield `likely-vibe-coded`, `likely-human`, or `ambiguous`.

4. **Stats (Phase 4)**  
   Stdlib-only math. Per-class tables where N is at least 5. Cohen’s d between vibe-coded and human-written only if both sides have at least five rows. Each signal gets a Mann–Whitney-style AUC and a Youden threshold against the binary “is vibe-coded”. Beta(1,1) with a normal approximation yields 90% intervals on sensitivity and specificity at that cut. The script also prints a rough minimum detectable Cohen’s d at 80% power and warns when strata are thin.

## Budget object

Every `gh` invocation that runs counts against the budget. Hard limits: 3000 calls in total; at most 300 PRs that fetch a diff; per-phase caps 200, 1500, and 1000. If a limit blocks the next call, `run_gh` returns `-1` and that branch stops. Retries are off.

## Outputs (artifact contract)

| File | Role |
|------|------|
| `label_map.tsv` | Matched labels and PR counts |
| `labeled_prs.tsv` | Deduped labeled PR metadata |
| `signals.tsv` | Labeled PRs crossed with vibe signals |
| `expanded_dataset.tsv` | Labeled rows plus pseudo-labeled rows |
| `descriptive_stats.tsv` | Means, spreads, skew, optional d |
| `discrimination.tsv` | AUC, Youden threshold, sens/spec |
| `bayesian_ci.tsv` | 90% intervals on sens/spec |
| `threshold_comparison.tsv` | 0.5 vs Youden per signal |
| `dataset_summary.json` | Counts, warnings, API use |
| `RUN_SUMMARY.txt` | One-line run stats and errors |
| `diffs/pr_*.diff` | Cached unified diffs |

## Failure behavior

Failed `gh` or `vibe_check` steps append to an error list and skip that PR. No automatic retries.

## Extension points

Change `--repo` to any host `gh -R` accepts. Edit the constants at the top of `calibration_pipeline.py` for caps. To change pseudo-labels, edit Phase 3 ratio cutoffs and how prototypes are built.

---

## Self-healing architecture

Six components form a closed loop. Each is implemented in `vibe_check.py` with no external dependencies.

```
┌──────────────┐    ┌───────────────┐    ┌──────────────────┐
│ 1. Telemetry │───▶│ 2. Drift      │───▶│ 3. Recalibration │
│   Collection │    │   Detection   │    │   (quantile-     │
│   (JSONL)    │    │   (Hoeffding) │    │    shift)        │
└──────────────┘    └───────────────┘    └────────┬─────────┘
       ▲                                          │
       │            ┌───────────────┐             ▼
       │            │ 5. Model      │    ┌──────────────────┐
       └────────────│   Evolution   │◀───│ 4. Override      │
                    │   Detection   │    │   Persistence    │
                    └───────┬───────┘    │ (JSON file)      │
                            │            └──────────────────┘
                            ▼
                    ┌───────────────┐
                    │ 6. Pattern    │
                    │   Discovery   │
                    │   (stub)      │
                    └───────────────┘
```

### Component 1: Telemetry collection (`log_telemetry`)

Every `analyze_diff()` call appends one JSON line to `$VIBE_CHECK_TELEMETRY_DIR/vibe_check_telemetry.jsonl`. Fields: timestamp, 10 signal values, overall score, residual-quantile margin bounds (key kept as `confidence_interval` for backwards compatibility: NOT a coverage interval; see CHANGELOG v0.2.0), calibration version, PR ID, repo name. No network calls.

### Component 2: Drift detection (`check_drift_status`)

CLI: `--drift-status`. Requires ≥50 logged evaluations.

Algorithm: split telemetry at the 60th-percentile timestamp (baseline vs recent). Per-signal Hoeffding bound test checks whether the recent mean deviates from baseline beyond ε. Also monitors CI width collapse (recent < 50% of baseline).

Decision logic (multi-tiered):
- `TRIGGER_RECALIBRATION`: ≥2 signals exceed 1.5σ AND global Wasserstein shift detected
- `TRIGGER_ALERT_MANUAL_REVIEW`: exactly 1 signal drifted OR CI collapse without signal drift
- `CONTINUE_CURRENT_THRESHOLDS`: no significant drift

### Component 3: Recalibration (`recalibrate_from_drift`)

CLI: `--recalibrate` (with optional `--dry-run`).

Quantile-shift algorithm (label-free):
1. Load telemetry, split baseline/recent at 60/40.
2. For each drifted signal: find the percentile rank of the current threshold in the baseline distribution.
3. Map that same percentile to the recent distribution.
4. Cap any single shift at ±20% of the original threshold (prevents runaway).
5. F1-proxy guard: if >60% of recent evaluations would score in the ambiguous zone (0.3–0.7) after applying new thresholds, abort and return `GUARD_TRIGGERED`.
6. Write `calibration_override.json`.

### Component 4: Override persistence (`load_calibration_overrides`)

File: `calibration_override.json` (next to `vibe_check.py`). Auto-loaded at import time. Applies:
- `signal_thresholds`: partial overrides merged into `SIGNAL_THRESHOLDS` dict
- `weights`: overrides bounded to [0.02, 0.30], then re-normalized to sum to 1.0
- `calibration_version`: updates `CALIBRATION_VERSION` global

No override file = no changes. Malformed file = warning to stderr, original thresholds preserved.

### Component 5: Model evolution detection (`detect_model_evolution`)

CLI: `--model-evolution`.

Compares signal profiles of high-confidence AI detections (score > 0.7) against `MODEL_FINGERPRINTS`, known ranges for GPT-4, Claude, and Gemini families. If >25% of detections are unmatched AND >50% of unmatched cluster in recent evaluations (last 30 days), returns `NEW_MODEL_PATTERN`.

Surfaces co-drift signals: signals where unmatched detections differ by >10% from the overall AI mean, indicating which heuristics the new model shifts.

### Component 6: Pattern discovery (`discover_new_patterns`), stub

Planned: mine telemetry + cached diffs for recurring comment phrases in high-confidence AI code not already in `AI_COMMENT_PHRASES`. Returns candidate regex patterns. Requires diff caching (not yet implemented).

### Self-healing data flow summary

```
PR diff → analyze_diff() → log_telemetry() → JSONL file
                                                  │
                         ┌────────────────────────┘
                         ▼
              check_drift_status()
                    │
        ┌───────────┼───────────────┐
        ▼           ▼               ▼
   CONTINUE    ALERT_REVIEW    TRIGGER_RECAL
                                    │
                                    ▼
                         recalibrate_from_drift()
                              │         │
                         guard ok    guard fail
                              │         │
                              ▼         ▼
                    write override    ABORT
                              │
                              ▼
                    next run: load_calibration_overrides()
                              │
                              ▼
                    updated SIGNAL_THRESHOLDS + WEIGHTS
```

### Token optimization

The telemetry / drift / recalibration loop is designed for minimal overhead:
- Telemetry: single dict append per evaluation (~0.5ms)
- Drift check: one pass through JSONL, stdlib math only
- Recalibration: percentile lookups on in-memory arrays
- Override load: single JSON parse at startup
- No LLM calls, no network, no ML model inference anywhere in the loop
