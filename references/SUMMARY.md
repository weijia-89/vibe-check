# Agent-Optimized Summary: vibe-check skill

> **Status (v0.2.0):** This file is a one-page summary for cross-agent handoff.
> The detailed/canonical version is `SKILL.md`. If anything here disagrees
> with `SKILL.md`, `SKILL.md` wins.

## What this is

A reviewer evidence surfacer (not a detector) plus a stdlib-only Python CLI. Takes a unified
diff (from `gh`, local `git`, or file), runs ten regex/AST heuristics, outputs Markdown report
or JSON with: per-signal evidence, an aggregate score (use with skepticism), letter grade
(A–F), per-file breakdown, AI pattern taxonomy, and prioritized review prompts.

**Honest scope (CLAIMS C-005, C-008):** AICD Bench (2026) and Wang et al. (ICSE 2025) report
detectors of this class as below practical usability under distribution shift. The skill's
value is *prompting reviewer attention*, not classification.

## Architecture

```
vibe-check/
├── SKILL.md                    — Trigger rules, workflow, methodology, references
├── README.md                   — Install + run; full feature surface
├── CHANGELOG.md                — Release notes (v0.2.0 = honest framing)
├── scripts/
│   ├── vibe_check.py           — Stdlib CLI scorer
│   ├── calibration_pipeline.py — Per-codebase calibration on labeled PRs
│   ├── check_claims.py         — Two-mode citation lint (reachability + quotes)
│   └── vibe_detect/            — Older PR-batch scanner (incident workflows)
├── references/
│   ├── CLAIMS.md               — Quote-level ledger (literal abstract text)
│   ├── CALIBRATION_NOTES.md    — Per-signal accounting of speculative priors
│   └── EVIDENCE_LEDGER.md      — Bibliography
└── tests/
    ├── test_analyzers.py       — 22 unit tests (incl. v0.2.0 bug regressions)
    └── test_skill_smoke.sh     — Integration smoke (no `|| true`)
```

## Signal ensemble (default weights — SPECULATIVE PRIORS)

CCR(0.18) + docstring(0.15) + naming(0.13) + error_handling(0.12) + declarative(0.10) +
func_length(0.08) + comment_phrasing(0.08) + hallucinated_apis(0.06) + edge_depth(0.05) +
commit_meta(0.05). Total = 1.0.

Defaults are authored priors, not fitted on labeled data. CLAIMS C-007 (Tao et al.) shows
signal magnitude varies drastically across LLMs — fixed weights cannot generalize. Run
`scripts/calibration_pipeline.py` on ≥100 labeled PRs from your codebase before quoting any
number. See `references/CALIBRATION_NOTES.md` for per-signal provenance.

Confidence-weighted aggregation: each signal's effective weight = `weight × confidence`. Per-
file influence is also weighted by added-line count.

## Pattern taxonomy (10 categories)

`over_commenting`, `boilerplate_bloat`, `shallow_error_handling`, `uniform_naming`,
`hallucinated_api`, `missing_edge_cases`, `declarative_heavy`, `cookie_cutter_structure`,
`ai_commit_markers`, `excessive_docstrings`.

## Strongest tier of signals (use these first)

- **Hallucinated APIs.** 12 regex patterns; high precision when fires.
- **Commit metadata.** AI-tool name in title/body/Co-authored-by trailer; high precision.
- **Bare `except:` (Python).** Tiered evidence — bare `except:` is a strong signal; `except
  Exception` is a soft signal; specific exception types are not flagged.

## Known weak / language-confounded signals

- **Naming uniformity in {Python, Go}.** PEP 8 / gofmt enforce style — high uniformity is the
  language baseline, not an AI marker. Capped at 0.4 (soft signal only) for these languages.
- **Function length CV in `--diff` mode.** Diff-only approximation; confidence capped at 0.4.
- **Comment-to-code ratio.** Tao et al. (CLAIMS C-007) report AUC-ROC varies 0.68–0.96 across
  models. The fixed default weight is a starting point only.

## Key limitations

- FP/FN rules-of-thumb (~15–25% / ~20–30%) are author estimates, not validated against labeled
  data in this repo. Treat as "mileage will vary."
- Best language coverage: Python, JS/TS, Go, Java. Partial: Rust, Ruby, C/C++, C#, PHP.
- Adversarial robustness: determined authors can edit around CCR/docstrings/naming/declarative
  signals. Hallucinated APIs and commit metadata are the hardest to game.
- The `MODEL_FINGERPRINTS` table and `--model-evolution` CLI flag are EXPERIMENTAL_DISABLED by
  default; opt in with `VIBE_CHECK_ENABLE_MODEL_EVOLUTION=1` only after fitting on labeled data.

## CLI cheat sheet

```bash
python scripts/vibe_check.py --pr 123                      # PR via gh
python scripts/vibe_check.py --diff changes.diff           # diff file
python scripts/vibe_check.py --diff changes.diff --no-aggregate   # evidence-only mode
python scripts/vibe_check.py --drift-status                # needs telemetry
python scripts/vibe_check.py --recalibrate --dry-run       # preview overrides
python scripts/check_claims.py --strict-quotes             # CI lint
```

## Cross-agent rules

- Every numeric claim or named-paper reference in agent-emitted prose must resolve to a row in
  `references/CLAIMS.md` (with non-empty primary-source quote, except `secondary` rows) or be
  tagged `[unverified]`.
- Do not present the aggregate score as a calibrated probability. Frame it as ordinal evidence.
- Never use `--model-evolution` output without first fitting `MODEL_FINGERPRINTS` on labeled
  data. The default ranges are unsourced.
