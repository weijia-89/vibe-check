---
name: vibe-check
description: >
  Reviewer evidence surfacer for PRs that may contain LLM-generated code. Runs ten regex/AST
  heuristics against a unified diff and returns per-signal evidence (hallucinated APIs, bare
  except:, AI tool markers, comment-phrasing boilerplate, etc.). Triggers: vibe check, vibe
  coded, AI-generated code review, copilot detection, hallucinated APIs, bare except, PR AI
  review. **Not a detector, not a gate, not a metric** — recent benchmarks (AICD Bench 2026,
  Wang ICSE 2025; CLAIMS C-005, C-008) report detectors of this class as below practical
  usability under distribution shift. Use as a reviewer prompt to slow down on suspicious
  patterns. Default thresholds are speculative priors (CALIBRATION_NOTES.md) — calibrate
  per-codebase before quoting any number.
---

# vibe-check — reviewer evidence surfacer for AI-generated PRs

> **Honest scope.** This is a reviewer prompt. Per-signal evidence is the useful output. The
> aggregate score is a weighted convenience number that uses speculative default weights; treat
> it as ordinal at best. The literature this skill cites — CLAIMS C-005 (Wang et al.), CLAIMS
> C-008 (AICD Bench) — concludes detectors of this class are below practical usability under
> distribution shift. Calibrate per-codebase or use `--no-aggregate`.

## Quick start

`scripts/vibe_check.py` — Python 3.10+, stdlib only.

```bash
python <skill-path>/scripts/vibe_check.py --pr 123
python <skill-path>/scripts/vibe_check.py --repo-path . --base main --head feature-branch
python <skill-path>/scripts/vibe_check.py --diff changes.diff --format json
python <skill-path>/scripts/vibe_check.py --diff changes.diff --no-aggregate    # evidence only
```

**Workflow:** get diff → run with flags → read **per-signal evidence first**, score second →
add human review (logic, integration, real APIs).

## Ten signals — what they look for, what they don't promise

Default weights are **SPECULATIVE PRIORS** (see `references/CALIBRATION_NOTES.md`). Tao et al.
(CLAIMS C-007) show signal magnitude varies drastically across models, so a single fixed weight
cannot generalize.

| Tier | Signal | Default weight | What it looks for | CLAIMS map |
|------|--------|-----------------:|---------------------|------------|
| **Strong** | Hallucinated APIs | 0.06 | 12 regex patterns for non-existent APIs (`os.path.mkdirs`, `dict.merge`, `Promise.allResolved`, etc.) — **most prompt-resistant** | author catalog |
| **Strong** | Commit metadata | 0.05 | "Co-authored-by: Claude/Copilot/GPT/...", AI tool name in title — **highest precision when fires** | pattern catalog |
| **Strong** | Bare `except:` | 0.12 (within error_handling) | Python `except:` with no type — catches SystemExit/KeyboardInterrupt; LLMs commonly emit | author + CLAIMS P-003 (pending) |
| Medium | Comment-to-code ratio | 0.18 | Higher ratios correlate with LLM output, with magnitude varying by model (Tao et al.) | CLAIMS C-007 |
| Medium | Comment phrasing | 0.08 | "Initialize the X", "Iterate over each Y" — boilerplate imperative | author catalog |
| Medium | Docstring consistency | 0.15 | Most-or-all functions documented (paraphrase setting) | CLAIMS C-006 |
| Weak (Python/Go) | Naming uniformity | 0.13 | Capped at 0.4 in {Python, Go} because PEP 8/gofmt enforce style — **language-confounded** | CLAIMS C-006 + CALIBRATION_NOTES |
| Weak | Declarative bias | 0.10 | Assignments+returns vs control flow — varies by model | CLAIMS C-007 |
| Weak | Function length CV | 0.08 | Diff-only approximation — confidence capped at 0.4 | CLAIMS C-007 + CALIBRATION_NOTES K-002 |
| Weak | Edge-case depth | 0.05 | Indent-based nesting + null/guard-check density (Python AST-style) | author heuristic |

**Lead with the Strong tier.** Hallucinated APIs and AI tool markers in commits are the patterns
most resistant to prompt engineering and have the highest precision when they fire.

## What changed in v0.2.0 (you should know this if you read older docs)

- **`edge_case_depth` Python implementation was broken.** It only ever incremented (no `}` to
  decrement in Python) — reported impossible values like `Depth=198` on a 1874-line file.
  Replaced with indent-based depth tracking. Test:
  `tests/test_analyzers.py::TestEdgeCaseDepthPython`.
- **`error_handling` mis-flagged `except Exception`** as "blanket" while ignoring all the
  `except SpecificError` cases nearby. Now tiers bare `except:` (strong) vs broad `except
  Exception` (soft) vs typed (no signal). Word boundary prevents false-match on
  `except ExceptionGroup` (Py 3.11+).
- **`naming_uniformity` flagged PEP 8 as AI-typical.** Python and Go uniformity scores are now
  capped at 0.4 (soft signal only) regardless of how uniform the file is, because language
  conventions (PEP 8, gofmt) make high uniformity the baseline.
- **`declarative_bias` regex counted `assert x == 1` as an assignment.** Now uses a
  negative-lookahead for `==`, `!=`, `<=`, `>=`, `=>`.
- **The "conformal prediction CI" was renamed `compute_residual_quantile_margin`.** It is not
  conformal prediction — there's no calibration set, no nonconformity score, no coverage
  theorem. Old name remains as a deprecated shim.
- **`--model-evolution` is fenced.** The MODEL_FINGERPRINTS table is unsourced; the CLI returns
  `EXPERIMENTAL_DISABLED` unless `VIBE_CHECK_ENABLE_MODEL_EVOLUTION=1` is explicitly set.
- **The `# from Gemini research, Table 1` comment is gone.** No such table existed in any cited
  source. Defaults are honestly labeled "SPECULATIVE PRIORS" with a pointer to
  `references/CALIBRATION_NOTES.md`.

## Telemetry, drift, and recalibration (opt-in only)

| # | What | How |
|---|------|-----|
| 1 | Telemetry | `export VIBE_CHECK_TELEMETRY_DIR=./vibe_telemetry` then run `vibe_check.py` — appends signals, score, residual margin, calibration version |
| 2 | Stratified baseline | `python scripts/vibe_calibration.py --gh-repo owner/repo --root .` → `outputs/vibe-baseline-calibration/` (note: previous baseline run was n=5, demo only) |
| 2b | Collinearity / VIF | `python scripts/signal_correlation_vif.py --jsonl $VIBE_CHECK_TELEMETRY_DIR/vibe_check_telemetry.jsonl` — offline only |
| 2c | Audit metadata | `python scripts/review_depth.py --pr N [--repo o/r]` — see `docs/AUDIT_PRIORITY_ETHICS.md` |
| 2d | Drift eval replay | `python scripts/eval_drift.py --jsonl …telemetry.jsonl --labels buckets.csv` — threshold grid → precision/recall/MCC |
| 3 | Drift status | `python scripts/vibe_check.py --drift-status` (needs ≥50 log rows). Set `VIBE_CHECK_DRIFT_GLOBAL_METRIC=psi\|sinkhorn\|mean_shift` (default `mean_shift`) |
| 4 | Recalibrate thresholds | `python scripts/vibe_check.py --recalibrate [--dry-run]` → writes `calibration_override.json` |
| 5 | Model fingerprint drift | `python scripts/vibe_check.py --model-evolution` (default-disabled; see CALIBRATION_NOTES K-004) |
| 6 | Override file | JSON `signal_thresholds` / `weights` (weights bounded 0.02–0.30, renormalized to sum 1.0) |

`--show-ci` adds a residual-quantile margin to Markdown; JSON includes the same as
`confidence_interval`. **The margin has no coverage guarantee** — it's a "wide vs narrow"
indicator, not a calibrated CI.

**Drift metrics** — default stays `mean_shift` for backwards compatibility. **PSI** is available
(`VIBE_CHECK_DRIFT_GLOBAL_METRIC=psi`, thresholds 0.10/0.25, CLAIMS C-012, **secondary / Field B
industry convention**). **Sinkhorn** is experimental — no defensible default threshold on this
workload. **Persistence rule** (`M`-of-`N` recent trips) suppresses single-check `TRIGGER_*` to
`WATCH`; configure via env vars.

## Output: grade scale (use with skepticism)

| Grade | AI Probability | Interpretation |
|-------|---------------|----------------|
| A | <15% | Mostly human-like signal profile |
| B | 15–30% | Mixed; could be careful human or lightly edited AI |
| C | 30–50% | Ambiguous |
| D | 50–70% | Several strong LLM-typical patterns |
| F | >70% | Strong LLM-typical pattern bundle |

> **Use `--no-aggregate` to suppress the grade entirely** if reviewers tend to over-anchor on a
> single number. Per-signal evidence stays in the report.

## Limitations (read these before quoting any number)

- **Not a detector.** AICD Bench (CLAIMS C-008) and Wang et al. (CLAIMS C-005) report detectors
  of this class are below practical usability under distribution shift. ML approaches with AST
  features get F1 ≈ 82.55 in-distribution (Wang); regex heuristics like this skill are weaker.
- **Default weights are speculative.** Tao et al. (CLAIMS C-007) show CCR's discriminative power
  varies wildly across models (AUC-ROC ~0.68–0.96). Calibrate per-codebase before any
  quantitative claim. See `references/CALIBRATION_NOTES.md`.
- **Languages.** Python and JS/TS strongest; Go and Java partial; Rust, C/C++, Ruby, PHP, C#
  shallow. **Python and Go** specifically have language-style enforcement (PEP 8, gofmt) that
  confounds the naming-uniformity signal — the implementation caps Python/Go uniformity at 0.4.
- **Adversarial.** A determined author can edit around CCR, docstrings, naming, and declarative
  bias. Hallucinated APIs and commit-metadata markers are the hardest to game.

## Evidence (GRADE)

**CONCLUSIVE-PROVISIONAL** for the claim that LLM-generated code differs in style from
human-written code (CLAIMS C-006, C-007). **WEAK** for the claim that fixed-weight regex
heuristics can detect those differences in production (CLAIMS C-005, C-008).

Full ledger with literal primary-source quotes: **`references/CLAIMS.md`**.
Default-threshold provenance: **`references/CALIBRATION_NOTES.md`**.

## Security

See [`SECURITY.md`](SECURITY.md). Short version: stdlib only, no inbound network, telemetry is
local JSONL, never log full diff bodies that may contain secrets.
