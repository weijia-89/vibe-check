# Change plan — PSI / persistence / claims ledger

## 1. Change summary (one sentence)

Add **PSI** as a supported global drift metric (documented Field B default 0.25) next to existing `mean_shift` (default) and experimental `sinkhorn`, add a **persistence rule (M-of-N)** that downgrades single-shot trips to `WATCH`, expose a **four-layer** snapshot in drift JSON, ship a small **`eval_drift.py`** replay tool, and introduce a minimal **CLAIMS.md + lint** so numeric claims in research docs are traceable.

## 2. Blast radius

| Surface | Who feels it | Reversibility |
|---------|--------------|---------------|
| `scripts/vibe_check.py` (`check_drift_status`) | `--drift-status` JSON consumers | Additive keys only; `mean_shift` default unchanged. Revert = `git revert`. |
| `scripts/eval_drift.py` (new) | Anyone with telemetry + labels | Delete file; no state mutation. |
| `scripts/check_claims.py` + `references/CLAIMS.md` (new) | Docs authors / CI job | Skip the CI step. |
| `docs/*`, `SKILL.md`, `README.md`, `CHANGELOG.md`, `references/GEMINI_…md` | Readers | Documentation only. |

No schema migration, no new service, no new Python deps, no runtime change for the existing diff-scoring path.

## 3. Observability plan (before / with change)

- **Before:** existing drift JSON already prints per-signal + global.
- **After (same command, richer JSON):**
  - `drift_global_metric`, `drift_threshold`
  - `global_drift`, `global_drift_sigma` (alias), `global_drift_mean_shift`, `global_drift_psi`, `global_drift_sinkhorn`
  - `raw_status` (pre-persistence) and `status` (post-persistence, can become `WATCH`)
  - `persistence` (`m_of_n`, `trips_seen`, `recent_statuses`)
  - `layers` (telemetry / signal / score / override_placeholder)

Existing CI assertions that only read `status`, `per_signal`, `drifted_signals` continue to pass.

## 4. Characterization tests

- `tests/test_skill_smoke.sh` — `vibe_check --diff … --format json` still produces required keys (`overall_ai_probability`, `grade`, `signal_summary`, `file_analyses`). Smoke run passes.
- Manual synthetic-telemetry run covering:
  - `VIBE_CHECK_DRIFT_GLOBAL_METRIC=mean_shift|psi|sinkhorn` → all produce a decision, defaults match docs.
  - `VIBE_CHECK_DRIFT_PERSISTENCE_M=2 _N=3` → first trip exposes `WATCH`, second trip exposes `TRIGGER_*`.
- `scripts/check_claims.py` → clean on current tree (ledger section in `RESEARCH.md` treated as claim source, bibliography headings skipped).

## 5. Implementation sequence (strangler, each step shippable+reversible)

1. Add PSI + Sinkhorn global-metric alternatives behind env flag (already present); default unchanged.
2. Add persistence rule behind env flag (`M`=`N`=1 is no-op).
3. Add layer snapshot block (pure read of existing values; no behavior change).
4. Add `scripts/eval_drift.py` — offline only.
5. Add `references/CLAIMS.md` + `scripts/check_claims.py`; scope lint to `SKILL.md`/`GEMINI_…`; let `RESEARCH.md` also act as ledger to avoid churn.
6. Patch prose in `GEMINI_AI_CODE_DETECTION_RESEARCH.md` to reference `CLAIMS.md` IDs; mark DuCodeMark "0.00" phrasing as weakened pending primary read.

Each step is a separate intent; reverts cleanly.

## 6. Rollback

```bash
# Disable opt-ins without code change
unset VIBE_CHECK_DRIFT_GLOBAL_METRIC VIBE_CHECK_DRIFT_PSI_THRESHOLD \
      VIBE_CHECK_DRIFT_SINKHORN_THRESHOLD \
      VIBE_CHECK_DRIFT_PERSISTENCE_M VIBE_CHECK_DRIFT_PERSISTENCE_N
# Remove CI step for check_claims.py.
# Full revert: git revert <sha>   (# RTO << 1hr)
rm -f "$VIBE_CHECK_TELEMETRY_DIR/drift_persistence.json"
```

## 7. Risk register (top 3)

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| PSI threshold (0.25) too loose/tight on this repo’s telemetry | Med | Use `scripts/eval_drift.py` on a labeled week/day CSV before enabling in CI; stay with `mean_shift` default until a decision lands. |
| Persistence suppresses a real spike | Low | Default is `M=N=1` (no-op); only opt-in teams see suppression; raw status still present. |
| `check_claims.py` false negatives/positives on heuristic regex | Med | Tag with `[unverified]` or `[claims-skip]`; ledger is the single source of truth. Lint is advisory, not enforced on code paths. |

## 8. What I don’t know

- Whether **PSI 0.25** or **Sinkhorn 0.22** matches this org’s manually-judged drift weeks — resolve by running `eval_drift.py` on a labeled CSV; **no code change** needed.
- Whether **DuCodeMark's "0.00 Δ complexity"** phrasing appears in the primary PDF body — resolve by a **primary-text pass** on arXiv:2604.10611; update `CLAIMS.md` C-004 with a literal quote or remove the number.
- Whether `check_claims.py` should be run as CI vs local-only — depends on repo’s CI budget; suggest opt-in initially.

## Evidence posture

- **Feathers/Fowler:** all behavior is opt-in env / separate scripts; no change to core diff parser (strangler seams).
- **Parnas (information hiding):** `persistence` state lives in a single JSON in telemetry dir; drift logic doesn’t care about format history beyond last N.
- **Folklore disclosed:** PSI cutoffs (0.10 / 0.25) are **industry convention, not RCT**; “M-of-N persistence” is a **practitioner pattern** (2025/26 drift-monitoring guides) — both marked Field B in docs/ledger.
- **Published evidence used:** PSI threshold convention (multiple 2024–2026 guides), AICD Bench ACL-2026 on detector limits, Feitelson / Jay / Landman on CC↔LOC correlation, Unsupervised Drift Benchmark IJDSA 2025.
