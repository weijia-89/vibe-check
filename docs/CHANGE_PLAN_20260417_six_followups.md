# Change plan, six follow-ups (vibe-check repo)

## 1. Change summary

Add offline **VIF/correlation** tool, optional **Sinkhorn** global drift metric behind env vars, **extensible hallucination regex** file, **`review_depth.py`** gh metadata JSON, **ethics doc**, and **citation caveats** in Gemini reference, without changing default `vibe_check` scoring behavior.

## 2. Blast radius

| Surface | Consumers |
|---------|-----------|
| `scripts/vibe_check.py` | Anyone running `vibe_check`; drift JSON gains fields; default drift path unchanged |
| `scripts/signal_correlation_vif.py` | New, offline analytics |
| `scripts/review_depth.py` | New, optional CI/human |
| `examples/`, `docs/` | Readers only |

Downstream: JSON parsers of `--drift-status` should accept new keys (`drift_global_metric`, `global_drift_sinkhorn`, …).

## 3. Observability plan

- **Before:** drift output already printed JSON; now includes `drift_global_metric` and parallel metrics for A/B comparison.  
- **Metrics:** none required in-app; CI can assert keys exist when `VIBE_CHECK_DRIFT_GLOBAL_METRIC=sinkhorn`.

## 4. Characterization tests

- `tests/test_skill_smoke.sh`: `vibe_check.py --diff` JSON keys unchanged.  
- Manual: `--drift-status` with `mean_shift` default matches prior `global_drift_sigma` semantics (mean of per-signal z-shifts).

## 5. Implementation sequence (strangler)

1. Land **extras** (scripts + docs + examples), no default behavior change.  
2. Land **vibe_check** hallucination merge + drift fields + Sinkhorn **opt-in** via env.  
3. Document env vars in README / CHANGELOG.

Each step independently revertible via git revert.

## 6. Rollback

```bash
git revert <sha>   # or
git checkout HEAD~1 -- scripts/vibe_check.py
unset VIBE_CHECK_DRIFT_GLOBAL_METRIC VIBE_CHECK_HALLUCINATION_EXTRAS
```

**RTO:** &lt; 1 hr.

## 7. Risk register

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Sinkhorn threshold miscalibrated | Med | Default remains `mean_shift`; tune `VIBE_CHECK_DRIFT_SINKHORN_THRESHOLD` |
| Extra hallucination regex FP | Low | JSON file is opt-in; test on sample diffs |
| `review_depth.py` gh rate limits | Low | Run only on demand, not per-file |

## 8. What we don’t know

- Empirical calibration of **Sinkhorn threshold** vs your telemetry, needs **local** ROC-style eval (resolve: run `signal_correlation_vif` + labeled subset).  
- Whether **PHP** example pattern causes FPs on real-world PHP codebases: **resolve:** run on 20 representative diffs before enabling the extras file.

## Evidence posture

- **Feathers:** new behavior behind **env** (feature seam), not invasive edit to core diff parser.  
- **Fowler strangler:** Sinkhorn alongside legacy mean-shift.  
- **Folklore:** “6–9 month shelf life” for heuristics: **speculative** (Gemini PDF); not reified as code constants.
