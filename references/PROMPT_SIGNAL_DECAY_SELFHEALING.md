# Self-Healing Module for AI Code Detection: Deep Research Prompt

> **STATUS: PARTIALLY VALIDATED (April 2026)**
> This prompt was submitted to Gemini Deep Research, which produced a 20-page synthesis
> ("Autonomous Recalibration in Heuristic Code Classifiers: Mitigating Concept Drift in
> the Era of Vibe Coding") drawing on 60+ sources with GRADE-assessed evidence. Sections
> below are annotated with validation status:
> - ✅ **VALIDATED** — Gemini confirmed with evidence
> - ⚠️ **PARTIALLY VALIDATED** — Gemini confirmed direction but flagged limitations
> - ❌ **REFUTED / DEPRIORITIZED** — Gemini recommended against or found insufficient evidence
> - 🔬 **OPEN** — Not addressed or insufficient data; remains a research question

## Executive Context

We operate `vibe_check.py`, a deterministic heuristic-based classifier that estimates AI-generation probability in pull request diffs using 10 calibrated signals (2023-2025 baseline). **Core problem:** as language models improve, their outputs converge toward human coding patterns, degrading signal discriminative power. We need an automated, self-healing system that:

1. **Detects signal decay** in real time without manual intervention
2. **Recalibrates thresholds** using unsupervised or semi-supervised methods
3. **Maintains epistemic rigor** about when/why recalibration fails
4. **Provides rollback mechanisms** for bad calibrations
5. **Generates alerts** when confidence degrades below acceptable thresholds

This prompt is for **exhaustive, rigorous research** with unlimited token budget. Target audience: deep research agents (ChatGPT Deep Research, Gemini Deep Research, equivalent). Budget: ~50-100k tokens for comprehensive coverage.

### Gemini-Validated Key Findings Summary

The following critical findings from the Gemini synthesis should inform any further research:

1. **SWE-bench convergence is real and fast:** AI resolution jumped 4.4% (2023) → 71.7% (2024). Static thresholds from 2023 are already partially obsolete. (Stanford HAI 2025, GRADE: High)
2. **CCR remains the sole universal discriminator** but its predictive magnitude fluctuates with RLHF/DPO tuning. (arXiv:2411.04299, arXiv:2507.00838)
3. **ADWIN is the optimal drift detector** for gradual stylometric convergence. Massive literature + RCTs. (Bifet & Gavaldà, GRADE: High)
4. **Wasserstein-2 preferred over KL divergence** for global drift measurement, but limited empirical results on code ASTs. (GRADE: Moderate)
5. **Pseudo-labeling carries severe feedback loop divergence risk.** Well-documented in ACL 2025 literature. (GRADE: Low)
6. **Dynamic Reference Generation is novel but unproven.** No published precedent in code stylometry. (GRADE: Very Low)
7. **Inter-model fingerprints remain separable** (>97% accuracy GPT-4o vs GPT-4.1) even as human-AI gap narrows. (LLM-AuthorBench, 32K programs)
8. **Georgia Tech SSLab found 35 CVEs/month** directly attributable to AI code generation (March 2026). LLMs introduce baked-in design flaws, not just surface typos.
9. **Bounded threshold shifting is safer than unbounded retraining.** Gemini's own adversarial review recommends manual periodic recalibration may be safer than automated miscalibration.
10. **Discrete syntax problem:** Code is fundamentally discrete and structured. Continuous divergence metrics (Wasserstein) may behave unpredictably on sparse ASTs. This is the biggest scope limitation flagged by Gemini itself.

---

## The 10 Current Signals (2023-2025 Calibration)

| Signal | ID | Human Baseline | LLM Baseline | Current Threshold | Type |
|--------|----|----|----|----|------|
| Cyclomatic Complexity Ratio (CCR) | 1 | ~0.15 | ~0.5 | TBD | Continuous |
| Docstring Coverage | 2 | ~25% | ~90% | 65% | Continuous |
| Naming Uniformity | 3 | ~80% | ~97% | 92% | Continuous |
| Shallow Error Handling (catch ratio) | 4 | ~20% | ~60% | 45% | Continuous |
| Declarative/Control Flow Ratio | 5 | ~1.0 | ~2.2 | 1.8 | Continuous |
| Function Length Coefficient of Variation | 6 | ~0.6 | ~0.3 | 0.4 | Continuous |
| Boilerplate Comment % | 7 | ~15% | ~45% | 35% | Continuous |
| Hallucinated APIs | 8 | ~2% | ~18% | Binary threshold | Binary |
| Edge Case Nesting Depth | 9 | ~2.0+ avg | ~1.3 avg | 1.5 | Continuous |
| Commit Message Markers | 10 | Pattern-specific | Pattern-specific | Pattern match | Pattern |

**Critical assumption:** These baselines will drift. GPT-4o, o1, Claude 4, and future models will drive signal distributions toward human baselines, reducing separation.

---

## RESEARCH AREA 1: Concept Drift Detection in Classification Systems

> **GEMINI STATUS: ✅ VALIDATED — This was the strongest section of Gemini's response.**
> Gemini confirmed ADWIN as optimal (GRADE: High), Wasserstein-2 as preferred global metric
> (GRADE: Moderate), and BOCD as providing exact posterior uncertainty (GRADE: Moderate).
> Key addition: multi-tiered decision logic combining per-signal ADWIN + global Wasserstein.

### 1.1 Core Drift Detection Algorithms

**Objective:** Understand how production ML systems detect when classifier performance degrades due to distributional shift, not true performance loss.

**Research Questions:**
- What are the mathematical foundations of ADWIN, Page-Hinkley test, DDM, and EDDM?
- How do they differ in computational cost, latency, and sensitivity?
- Which are suitable for embedded real-time systems (our use case: per-PR analysis)?
- What are false positive / false negative rates on synthetic concept drift?

**Specific Topics to Investigate:**

1. **ADWIN (Adaptive Windowing)** ✅ VALIDATED — Gemini GRADE: High
   - How does it maintain a sliding window of "recent" concept?
   - What's the computational complexity for streaming data?
   - Published applications in production systems (cite papers)
   - Sensitivity to window parameters
   - **Gemini finding:** Massive body of literature + RCTs. Proven in streaming ML. Optimal for
     gradual stylometric convergence. Uses Hoeffding bound for statistically principled split detection.
   - **IMPLEMENTED:** `vibe_check.py` uses per-signal Hoeffding-bound checks (1.5σ threshold)
     as a lightweight ADWIN approximation.

2. **Page-Hinkley Test**
   - CUSUM-based sequential analysis
   - Threshold determination
   - Lag time to detect shift (how many samples needed?)
   - Applications in fraud detection, intrusion detection
   - **Gemini status:** Not specifically addressed. Remains a viable alternative to ADWIN.

3. **DDM (Drift Detection Method) & EDDM (Early Drift Detection Method)**
   - Original motivation: online learning in evolving data streams
   - How are they applied in Scikit-learn, MOA frameworks?
   - Performance on real datasets (Spam, Electricity, Covtype)
   - Comparison with ADWIN on same benchmarks
   - **Gemini status:** Not specifically recommended. ADWIN preferred.

4. **Statistical Process Control (SPC) Methods** 🔬 OPEN
   - Shewhart control charts: X-bar, moving range (MR)
   - EWMA (Exponentially Weighted Moving Average)
   - Why use in drift detection vs. pure statistical tests?
   - Tuning control limits for domain-specific acceptable error rates
   - **Gemini status:** Not addressed. Remains unexplored for code stylometry.

5. **Bayesian Online Changepoint Detection** ⚠️ PARTIALLY VALIDATED — Gemini GRADE: Moderate
   - Papers: Adams & MacKay (2007), Fearnhead & Liu (2011)
   - Posterior probability of changepoint at time t
   - Computational tractability for high-dimensional data
   - Advantage over frequentist methods for real-time decisions
   - **Gemini finding:** Provides exact posterior uncertainty. Highly resilient to multidimensional
     scaling. Assumes known prior structures (limitation). Seminal foundational work.

**Methodological Note:** Distinguish between:
- **Drift** (distributional shift in input features)
- **Concept drift** (shift in decision boundary / P(y|x) changes)
- **Real degradation** (our thresholds are fundamentally wrong now)

We likely face concept drift: LLM-generated code distributions are shifting toward human distributions, but the true separation may still exist—it's just smaller.

**Gemini-confirmed decision logic (IMPLEMENTED in vibe_check.py):**
```
IF wasserstein_dist > 1.5 * baseline_std AND adwin_signals >= 2:
    → TRIGGER_RECALIBRATION (automatic)
ELIF adwin_signals == 1 OR confidence_interval_collapse:
    → TRIGGER_ALERT_MANUAL_REVIEW
ELSE:
    → CONTINUE_CURRENT_THRESHOLDS
```

---

## RESEARCH AREA 2: Self-Calibrating / Self-Healing System Architecture

> **GEMINI STATUS: ⚠️ PARTIALLY VALIDATED — Core architecture confirmed, but pseudo-labeling
> carries severe risk. Gemini recommends bounded threshold shifting over unbounded retraining.**

### 2.1 The Feedback Loop Problem

**Core Challenge:** How do we get ground truth labels (is this PR AI-generated?) over time without manual review?

**Research Questions:**
- What are realistic feedback mechanisms in a PR analysis tool?
- How can we leverage developer behavior as implicit labels?
- What's the minimum labeling rate to maintain calibration?

**Specific Approaches:**

1. **Explicit Feedback** 🔬 OPEN
   - Users can mark PRs as "I wrote this" vs. "Copilot wrote this" vs. "Uncertain"
   - Incentive mechanisms (badges, trust scores)?
   - How many labels do we need for statistical power?
   - Bias: self-reporting may be unreliable
   - **Gemini status:** Not directly addressed. Remains viable but unvalidated.

2. **Implicit Feedback / Proxy Labels** 🔬 OPEN
   - Commit metadata: does PR touch tests? (humans write tests more)
   - Review comments: do reviewers question code quality?
   - Time patterns: late-night commits → more likely AI?
   - Merge velocity: code quality feedback loops?
   - **Caveat:** These are weak signals, prone to confounding

3. **High-Confidence Pseudo-Labels** ❌ HIGH RISK — Gemini GRADE: Low
   - If vibe_check gives P(AI) = 0.95 or P(AI) = 0.05, use as self-training
   - Requires careful error analysis: what's our confidence calibration?
   - Risks: error compounding, feedback loop instability
   - Mitigation: human spot-checks on pseudo-labels
   - **Gemini finding:** "Severe feedback loop divergence risk." System risks becoming "perfectly
     calibrated to its own historical hallucinations." ACL 2025 literature documents this well.
     Only viable if gated by conformal prediction CI — narrow-bound predictions only.
   - **Mitigation implemented:** `vibe_check.py` uses conformal prediction CIs. Only top 5%
     most confident predictions would qualify as pseudo-labels.

4. **Semi-Supervised Learning Framework** 🔬 OPEN
   - Few labeled + many unlabeled data → leverage unlabeled
   - Methods: self-training, co-training, consistency regularization
   - Graph-based SSL: if two PRs are similar in signal space, likely same label
   - **Research:** How well do semi-supervised methods work on code stylometry?
   - **Gemini status:** Not specifically addressed for code. General SSL risks apply.

### 2.2 Threshold Adaptation Without Ground Truth

> **GEMINI STATUS: ✅ VALIDATED — Recommended 6-component decoupled pipeline.**
> Zero-label recalibration via Bregman projection + quantile shift confirmed as primary strategy.
> Weak-label (top 5% pseudo-labels + logistic regression) confirmed as secondary, gated by CI.

**Objective:** Update thresholds when signal distributions shift, using only unlabeled data.

**Research Questions:**
- Can we use unsupervised methods to identify when distributions have changed?
- What's the trade-off between sensitivity and false alarms?
- How much historical data do we need for robust estimation?

**Specific Approaches:**

1. **Distribution-Based Adaptation** ✅ VALIDATED
   - Maintain rolling windows: baseline (week 1-52) vs. recent (week 52)
   - ~~KL divergence~~, **Wasserstein-2 distance** (Gemini: preferred over KL), or Kolmogorov-Smirnov test
   - When distance exceeds threshold → flag drift
   - **Gemini finding:** Wasserstein-2 is theoretically optimal for measuring distributional shift.
     However, it may behave unpredictably on discrete code syntax — this is the biggest scope
     limitation. (GRADE: Moderate)
   - **Question:** Is shifting the decision threshold the right response, or are signals fundamentally broken?

2. **Quantile-Based Recalibration** ✅ VALIDATED (as "Bregman projection + quantile shift")
   - Current: use fixed percentile thresholds (e.g., 90th percentile of LLM baseline)
   - Adaptive: recalibrate percentiles using live data
   - **Gemini finding:** Maps drifted distribution to historical KDE shape, adjusting percentile
     cutoffs to maintain original False Positive Rate. This is the recommended zero-label strategy.
   - Advantage: parameter-free, robust to outliers
   - **Caveat:** Assumes historical calibration is directionally correct

3. **ROC / Precision-Recall Curve Analysis** 🔬 OPEN
   - If we have even a small labeled subset (e.g., 100 PRs/quarter with ground truth), retrain ROC curves
   - Identify new optimal operating points (threshold for different error tolerance)
   - Compare old vs. new curves: if AUC drops >5%, escalate

4. **Ensemble Signal Reweighting** ⚠️ PARTIALLY VALIDATED (via MAB)
   - Some signals may degrade faster than others
   - Use online learning to dynamically weight signals
   - E.g., if signal #3 (naming uniformity) loses discriminative power, reduce its weight
   - Methods: ~~online boosting, Hedge algorithm~~, **Thompson Sampling / UCB bandits** (Gemini-recommended)
   - **Gemini finding:** MAB for dynamic signal weighting is theoretically grounded in recommendation
     systems literature. Untested on live code. (GRADE: Moderate). Scheduled for Phase 5 (Month 9+).

### 2.3 A/B Testing Framework

> **GEMINI STATUS: ✅ VALIDATED — Incorporated into deployment gate component.**

**Objective:** Compare old vs. new calibration before deploying.

**Research Questions:**
- How do we A/B test a classifier recalibration in production?
- What's the minimum sample size to detect a 5% change in detection accuracy?
- How do we avoid selection bias?

**Specific Design:**

1. **Shadow Deployment** ✅ VALIDATED — Gemini Phase 3 (Months 5-6)
   - Run new calibration in parallel, log results, don't change user feedback
   - Compare detection rates, precision/recall on known test sets
   - Monitor false positive / false negative trends

2. **Canary Rollout** ✅ VALIDATED — Gemini Phase 4 (Months 7-8)
   - Route small % of PRs (5%) to new calibration
   - Monitor error rates, user complaints, confidence scores
   - Gradual rollout if no issues observed

3. **Holdout Test Set** 🔬 OPEN — Not specifically addressed by Gemini
   - Maintain curated, ground-truth labeled PR set (200-500 PRs)
   - Periodically re-evaluate both old and new calibrations on this set
   - Directly measure AUC, precision, recall changes

---

## RESEARCH AREA 3: Longitudinal Code Stylometry & LLM Evolution

> **GEMINI STATUS: ✅ VALIDATED with strong empirical data.**
> Key findings:
> - SWE-bench convergence: 4.4% → 71.7% (2023→2024). Stanford HAI 2025. GRADE: High.
> - Stylometric convergence: GPT-3.5 AUC=0.96 → modern models significantly lower. (arXiv:2409.01382)
> - Inter-model fingerprints remain separable at >97% accuracy (LLM-AuthorBench, 32K programs).
>   This means human-AI gap narrows, but model-to-model differences persist.
> - RLHF/DPO drives docstring over-indexing and naming hyper-uniformity (arXiv:2507.00838).
>   This is a mechanism explanation for why some signals inflate rather than converge.
> - CCR predictive magnitude fluctuates by model instruction tuning, but remains universally discriminative.

### 3.1 Historical Analysis: GPT-3 → GPT-4o → o1 → Claude 4

**Objective:** Empirically document how LLM code generation patterns have evolved.

**Research Questions:**
- Are there published analyses comparing code generated by different model generations?
- Have signal values (our 10 heuristics) changed over time?
- What's the velocity of convergence toward human code?
- Is convergence uniform across all signals, or are some more resilient?

**Specific Research Directions:**

1. **arxiv / Published Research**
   - Search: "code generation model evolution", "LLM code quality over time"
   - Key papers to find:
     - Comparisons of GPT-3, GPT-3.5, GPT-4 on HumanEval (Zellers et al., OpenAI reports)
     - Code style analysis across model versions
     - Benchmark improvements (HumanEval, SWE-bench, MultiPL-E) as proxy for convergence
   - **Hypothesis:** If HumanEval pass rate went 48% → 67% → 88%, did code *style* also converge?

2. **Code Benchmark Temporal Trends**
   - HumanEval pass rates: GPT-4 (88%) → GPT-4 Turbo (90%) → ? (GPT-4o, o1)
   - SWE-bench: track pass rates on real GitHub issues over model releases
   - MBPP: multi-platform benchmark trends
   - **Extract signal:** Do improving benchmarks correlate with human-like code?

3. **Copilot / Cursor Usage Analysis**
   - GitHub Copilot started ~2021; usage patterns over time?
   - Does increasing Copilot adoption bias training data toward Copilot-like code?
   - Any public analysis from GitHub, Microsoft, Cursor teams?
   - **Causal inference challenge:** Is Copilot improving because model improved, or because training on Copilot-generated code?

4. **Direct Measurement: Stylometry Across Versions**
   - If possible: run our 10 signals on code samples from GPT-3.5 vs. GPT-4 vs. Claude 3
   - Quantify drift in each signal
   - Predict: which signals will degrade fastest?
   - **Data source:** 
     - OpenAI's official code samples
     - HumanEval solutions (if model-generated versions available)
     - GitHub issue solutions (filter by "created by AI" markers if available)

### 3.2 Theoretical Model: Why Convergence Happens

> **GEMINI STATUS: ⚠️ PARTIALLY VALIDATED — RLHF/DPO mechanism confirmed, but with a twist.**
> Gemini found that RLHF/DPO doesn't uniformly push toward human patterns — it specifically
> inflates docstring coverage and naming uniformity (over-indexing), while CCR remains fluctuating.
> This means some signals get WORSE at discrimination not because LLMs match humans, but because
> RLHF pushes them to over-document and over-standardize.

**Research Questions:**
- What drives LLM code output toward human-like patterns?
- Is it training data composition, alignment techniques, or optimization?
- Can we predict which signals degrade when?

**Hypotheses to Explore:**
- **RLHF Hypothesis:** ✅ CONFIRMED — But nuanced. RLHF/DPO drives docstring over-indexing and naming hyper-uniformity (arXiv:2507.00838). Does NOT uniformly converge all signals toward human baselines.
- **Data Composition:** 🔬 OPEN — Training on GitHub → model learns to match GitHub code style
- **Alignment Techniques:** ✅ CONFIRMED — DPO emphasizes "helpfulness" → more documentation, clearer naming. This inflates signals 2 (docstrings) and 3 (naming) specifically.
- **Scale Laws:** 🔬 OPEN — Larger models have more capacity to capture human-like subtleties
- **Instruction Following:** 🔬 OPEN — Better instruction tuning → models follow human style guides → convergence

---

## RESEARCH AREA 4: Concrete Self-Healing Module Design

> **GEMINI STATUS: ✅ VALIDATED — Gemini proposed a 6-component decoupled pipeline that
> supersedes the architecture below. The Gemini architecture has been IMPLEMENTED in vibe_check.py
> (Phases 1-2: telemetry + drift detection). See RESEARCH.md for the full component table.**
>
> Gemini's 6 components: Inference Engine, Telemetry Logger, Drift Monitor,
> Recalibration Node, Deployment Gate, Rollback Engine.
>
> **What's implemented:** Telemetry Logger (JSONL), Drift Monitor (Hoeffding + CI collapse),
> conformal prediction CIs, calibration versioning.
> **What's NOT yet implemented:** Recalibration Node, Deployment Gate, Rollback Engine.

### 4.1 Architecture: Components & Data Flow

**Objective:** Propose a complete system architecture.

**Core Components (SUPERSEDED by Gemini 6-component architecture — retained for reference):**

```
┌─────────────────────────────────────────────┐
│         Incoming PR / Code Diff             │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────▼──────────┐
        │  Extract 10 Signals│
        └────────┬───────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌───────┐ ┌──────────┐ ┌──────────┐
│ Score │ │Confidence│ │Log Signals│
│(0-1)  │ │Intervals │ │for Future │
└───┬───┘ └────┬─────┘ │Recalibr. │
    │          │       └──────────┘
    │          │
    └──────┬───┘
           │
    ┌──────▼──────────────┐
    │ Format: JSON Log    │
    │  Append to Stream   │
    └─────┬────────────┬──┘
          │            │
          │      ┌─────▼──────────────┐
          │      │ Recalibration      │
          │      │ Scheduler (hourly) │
          │      └─────┬──────────────┘
          │            │
          │      ┌─────▼──────────────────┐
          │      │ Batch Drift Detection  │
          │      │ & Recalibration        │
          │      │ (Statistical Analysis) │
          │      └─────┬──────────────────┘
          │            │
          │      ┌─────▼──────────────────┐
          │      │ Update Config YAML     │
          │      │ New Thresholds         │
          │      │ Alert if Confidence↓   │
          │      └────────────────────────┘
          │
    ┌─────▼──────────────────────┐
    │ Return Score + Explanation │
    │ (with calibration version)  │
    └─────────────────────────────┘
```

**Key Design Decisions:**

1. **Real-Time Scoring:** Use current thresholds, no latency
2. **Batch Recalibration:** Hourly or daily job, not real-time
3. **Versioned Config:** Track calibration version, enable rollback
4. **Signal Logging:** Append all signal values to immutable log (for replay, debugging)
5. **Decoupled Analysis:** Drift detection runs separately from scoring

### 4.2 Data Collection & Storage

**Strategy:** Immutable log of all signals analyzed.

**Log Entry Format (JSON Lines):**
```json
{
  "timestamp": "2026-04-16T14:32:15Z",
  "repo": "org/repo",
  "pr_id": "12345",
  "commit_hash": "abc1234",
  "calibration_version": "v2026_q1",
  "signals": {
    "ccr": 0.42,
    "docstring_coverage": 0.78,
    "naming_uniformity": 0.94,
    "error_handling_ratio": 0.55,
    "declarative_control_ratio": 1.9,
    "function_length_cv": 0.35,
    "boilerplate_comment_pct": 0.38,
    "hallucinated_api": 0,
    "edge_case_depth": 1.4,
    "commit_markers": 1
  },
  "vibe_score": 0.71,
  "confidence_interval": [0.65, 0.77]
}
```

**Storage:**
- **Primary:** Cloud-native data warehouse (Parquet, BigQuery, Snowflake)
- **Backup:** S3 / GCS append-only bucket
- **Retention:** 2-3 years (track long-term trends)
- **Sampling:** For memory-constrained systems, sample 10% of low-confidence PRs

**Privacy Considerations:**
- Anonymize repo names? Or keep for debugging?
- Signal values are code metrics (non-sensitive)
- Store only hash of commit message (for marker detection)

### 4.3 Drift Detection Logic

**Trigger:** Run hourly or after N new samples (N=1000).

**Statistical Tests:**

1. **Primary Test: Kolmogorov-Smirnov (KS) Test**
   - Compare baseline distribution (week 1-4) vs. recent (week 4 only)
   - H0: distributions are identical
   - If p < 0.05 for any signal → potential drift
   - Advantage: nonparametric, distribution-agnostic
   - Limitation: doesn't quantify shift magnitude

2. **Secondary Test: Wasserstein Distance**
   - Measure "earth-mover distance" between two distributions
   - More intuitive than KS; interpretable in signal units
   - If distance > 2 SD of baseline → recalibration triggered
   - Robust to outliers

3. **Tertiary Check: Confidence Interval Narrowing**
   - Current: vibe_score returned with 95% CI
   - If CI width shrinks significantly → signals becoming less informative
   - Possible cause: convergence toward 0.5 (maximum uncertainty)

**Decision Rule:**
```
IF (KS p-value < 0.05 for ≥2 signals) AND (Wasserstein distance > 1.5 SD)
  THEN trigger recalibration
ELSE if KS p < 0.05 for 1 signal
  THEN alert (manual review advised, but don't recalibrate yet)
ELSE
  THEN continue with current thresholds
```

**Sensitivity Analysis:**
- Test decision rule on synthetic data with known ground truth drift
- What's the false positive rate? (False alarm on no actual drift)
- What's the detection lag? (Time to detect actual drift)
- Tune thresholds empirically

### 4.4 Recalibration Strategies

**Scenario 1: Limited Labeled Data (< 100 PRs/quarter)**

1. **Quantile Shift:**
   - Old threshold: 65th percentile of 2023-2025 LLM baseline
   - New threshold: 65th percentile of current rolling window (last 100 analyzed)
   - Advantage: completely unsupervised
   - **Risk:** If separation is truly collapsing, this won't help

2. **Distribution Matching:**
   - Use Kernel Density Estimation (KDE) to model P(signal | LLM) and P(signal | Human)
   - Update KDE parameters with recent data
   - Recalibrate threshold to maximize some metric (Youden's J, F1, etc.)
   - Requires assumption: distribution shapes haven't fundamentally changed

**Scenario 2: Moderate Labeled Data (100-500 PRs/quarter)**

1. **Logistic Regression Recalibration:**
   - Fit logistic model: log-odds(AI) = β0 + β1*signal1 + ... + β10*signal10
   - Use current predictions (high-confidence) as pseudo-labels for unlabeled data
   - Retrain with mixed supervised + semi-supervised approach
   - Update thresholds to maintain same FPR / TPR tradeoff

2. **Isotonic Regression / Platt Scaling:**
   - Simple postprocessing: map old scores through isotonic function
   - Adjusts calibration without retraining full model
   - Can use small labeled set (50 examples) to fit

**Scenario 3: High Labeled Data (> 500 PRs/quarter)**

- Full retraining of signal weights
- Update decision rules / thresholds
- Compare new vs. old model on holdout test set
- Deploy with confidence

### 4.5 Alerting & Transparency

**Alert Levels:**

1. **Level 1 (Info):** Drift detected on 1 signal, but recalibration not triggered
   - Message: "Signal [X] is shifting. Monitoring..."

2. **Level 2 (Warning):** Recalibration triggered
   - Message: "Recalibration completed. Thresholds updated for [signal list]."
   - Quantify changes: "Docstring threshold shifted from 65% → 62%"

3. **Level 3 (Critical):** Confidence significantly degraded
   - Message: "Classifier confidence has dropped below acceptable threshold. Manual review recommended."
   - Evidence: "Average confidence went 0.82 → 0.68 over past 2 weeks"

**User-Facing Output:**
```json
{
  "vibe_score": 0.71,
  "confidence_interval": [0.65, 0.77],
  "calibration_version": "v2026_q2_updated",
  "calibration_age_days": 7,
  "health_status": "good",
  "alert": null
}
```

### 4.6 Rollback Mechanism

**Scenario:** Recalibration was bad (e.g., false positive signals, introduced unexpected failures).

**Strategy:**
1. **Version Control:** Every calibration is versioned with timestamp + commit hash
2. **Metrics Tracking:** Log precision, recall, F1 for each version on holdout test set
3. **Automated Rollback:**
   - If precision drops > 10% within 24h of recalibration → auto-rollback
   - Send alert: "Recalibration v2026_q2_updated rolled back due to performance degradation"
4. **Manual Rollback:**
   - Admin can revert to previous version via config change
   - Requires 2-person approval (audit trail)

---

## RESEARCH AREA 5: Out-of-the-Box Thinking

### 5.1 Dynamic Reference Generation ❌ DEPRIORITIZED — Gemini GRADE: Very Low

**Idea:** Instead of relying on fixed 2023-2025 baselines, periodically generate fresh samples from current LLMs.

**Design:**
1. **Quarterly refresh:** Every Q, prompt GPT-4o, Claude 4, o1 to generate code on standard problems (HumanEval, LeetCode easy)
2. **Signal measurement:** Compute all 10 signals on fresh samples
3. **Update baselines:** New LLM baseline for Q2 2026 becomes 0.52 (was 0.50 in 2025)
4. **Threshold adjustment:** Automatically shift thresholds to maintain same relative separation

**Advantages:**
- Always uses current model behavior
- Catches sudden shifts (new model release)

**Disadvantages:**
- Assumes models continue improving (not true for all signals)
- Cost of generating synthetic data
- Potential gaming: models could be trained to look like humans

**Gemini finding:** Novel proposal with NO published precedent in code stylometry. High
implementation risk. Models may spoof human patterns when instructed. Scheduled for Phase 5
(Month 9+) as experimental only. Theoretically sound but entirely unproven.

### 5.2 Adversarial Calibration

**Idea:** Prompt LLMs to write "human-like" code—use that as a harder positive class.

**Design:**
1. **Prompt:** "Write Python code that is indistinguishable from human-written code. Use natural variable names, appropriate comments, realistic error handling."
2. **Measure signals** on adversarial samples
3. **Update thresholds:** If LLM can make signals that look human, shift threshold higher
4. **Active learning:** Use adversarial samples to identify which signals are most robust

**Advantages:**
- Captures model intent to appear human-like
- Proactive: doesn't wait for organic drift

**Disadvantages:**
- Models may not be aligned with prompt intent
- Potential for arms race (models learn to fool adversarial test)
- Requires manual evaluation to verify success

### 5.3 Crowdsourced Recalibration

**Idea:** Developers marking PRs with confidence can feed back into calibration.

**Design:**
1. **UI Element:** "Was this PR human-written?" [Yes] [No] [Unsure]
2. **Collect feedback:** Store for PRs with high uncertainty (0.4-0.6 vibe score)
3. **Feed into semi-supervised learning:** Use crowdsourced labels as weak supervision
4. **Trust scores:** Weight feedback by reviewer expertise (frequent, accurate annotators weighted higher)

**Advantages:**
- Ground truth from domain experts (developers)
- Low friction (one-click annotation)

**Disadvantages:**
- Selection bias: developers only annotate when suspicious
- Incentive misalignment: developers may want to hide use of AI
- Sparse labels: requires critical mass of feedback

### 5.4 Multi-Armed Bandit Approach ⚠️ PARTIALLY VALIDATED — Gemini GRADE: Moderate

**Idea:** Dynamically allocate weight to signals based on current discriminative power.

**Design:**
```
For each signal i:
  - Maintain estimated "winning rate": P(signal i correctly separates AI from human)
  - Use Thompson sampling or UCB to choose which signals to emphasize
  - After each batch: update estimates based on realized separation
  - Over time: high-performing signals get higher weight, low-performing signals get lower weight
```

**Advantages:**
- Adaptive without explicit drift detection
- Automatically adjusts to which signals are still working
- Theoretically grounded (bandit algorithms are well-studied)

**Disadvantages:**
- Exploration overhead: need to periodically try low-weighted signals
- May converge prematurely if unlucky in early sampling

**Gemini finding:** Strong theoretical foundation in recommendation systems. Viable for
dynamic signal weighting. Untested on live code — no published example in code stylometry.
Scheduled for Phase 5 (Month 9+). Upgrade factor: strong theoretical foundation.

### 5.5 Ensemble Signal Expansion

**Idea:** Add new signals as old ones degrade.

**Strategy:**
1. **Maintain a pool of candidate signals** (30-50 ideas, not yet deployed)
2. **Quarterly evaluation:** Test which candidates have good separation on recent data
3. **Rotate:** If signal #3 (naming uniformity) drops below 0.7 AUC, replace with candidate #15 (e.g., "unused import ratio")
4. **Maintain constant ensemble size:** Always use 10 signals, but composition changes

**Advantages:**
- Automatically discovers which signals remain valuable over time
- Hedge against any single signal's collapse

**Disadvantages:**
- Introduces instability (changing signal composition)
- Hard to interpret why vibe_score changed (signal roster changed, or threshold changed?)
- Requires maintaining + testing large candidate pool

---

## RESEARCH AREA 6: Full Epistemic Rigor & Limitations

### 6.1 Methodology Assessment (GRADE + Cochrane RoB 2 Framework)

> **GEMINI STATUS: ✅ VALIDATED — Gemini independently performed GRADE assessment on all methods.
> Table below updated with Gemini's ratings (original estimates shown for comparison).**

**Objective:** Honestly assess the evidence quality for each proposed approach.

**Rating Scale (GRADE):**
- **High:** We are confident the estimate is correct
- **Moderate:** Likely correct but further research may change estimate
- **Low:** Real possibility that result is substantially different
- **Very Low:** Very little confidence

**Apply to Each Proposal (UPDATED with Gemini GRADE):**

| Proposal | Original Est. | Gemini GRADE | RoB Concerns | Upgrade/Downgrade Factors |
|----------|---|---|---|---|
| ADWIN drift detection | Moderate | **High** ⬆ | Proven in streaming ML; low risk of bias | **Upgrade**: Massive literature + RCTs |
| Wasserstein-2 adaptation | — (new) | **Moderate** | Theoretically optimal; sensitive to outliers | **Downgrade**: Limited empirical results on code ASTs |
| BOCD (Bayesian changepoint) | — (new) | **Moderate** | Exact inference; assumes known prior structures | **Upgrade**: Highly resilient to multidimensional scaling |
| Unsupervised recalibration (Bregman/quantile) | Low | **Moderate** ⬆ | Zero-label approach has theoretical backing | Gemini validated specific algorithm (Bregman projection) |
| Pseudo-labeling retraining | Low | **Low** ⬇ | High confirmation bias; assumes conformal bounds hold | **Downgrade**: Feedback loop instability well-documented (ACL 2025) |
| LLM reference generation | Very Low | **Very Low** | No published precedent in code detection | **Downgrade**: No published precedent in code stylometry |
| Crowdsourced labels | Low | 🔬 Not assessed | Selection bias, incentive misalignment | Social desirability bias in self-reporting |
| Bandit approach (MAB) | Moderate | **Moderate** | Works in simulation; untested on real code data | **Upgrade**: Strong theoretical foundation in recommendation systems |

**Key Uncertainties:**
- Do current signals actually degrade as predicted? (Hypothesis not yet validated)
- Can we get sufficient high-quality labels?
- Will recalibration cause more harm than degradation? (false positives / false negatives may trade off)

### 6.2 Adversarial Self-Review: Against Self-Healing

> **GEMINI STATUS: ✅ VALIDATED — Gemini conducted its own adversarial review and AGREED
> with points 1 and 3 as strongest. Added two new critical arguments (6 and 7 below).**

**Devil's Advocate Argument:**

> Automatic recalibration is a trap. Here's why:
> 
> 1. **Feedback loop instability:** ✅ CONFIRMED by Gemini (ACL 2025). Retraining on your own predictions (pseudo-labels) compounds errors. System risks becoming "perfectly calibrated to its own historical hallucinations."
> 
> 2. **Unobservable ground truth:** You don't know when you're wrong. With no external validation (labeled data), you have no signal that recalibration failed.
> 
> 3. **Concept drift vs. real degradation:** If thresholds collapse because LLMs truly converged toward human code, recalibrating won't help—you're using the same signals that are now worthless.
> 
> 4. **Operational complexity:** Self-healing adds monitoring, versioning, rollback logic. What's the operational debt? Are you trading one problem (manual recalibration) for another (automated failures)?
> 
> 5. **Incentives misaligned:** Recalibration that reduces false positives looks good to end users but may hide true AI usage. Is that what you want?
> 
> 6. **Discrete syntax problem (NEW — from Gemini):** Code is structured, deeply contextual, and fundamentally discrete. Continuous divergence metrics (Wasserstein) may behave unpredictably on sparse ASTs. This is applying continuous math to discrete structures — a domain transfer that is largely unproven.
> 
> 7. **Manual may be safer (NEW — from Gemini):** Gemini's own adversarial review argues that manual periodic recalibration may be safer than automated miscalibration. Bounded threshold shifting mitigates but does not eliminate this risk.

**Counterargument (Pro Self-Healing):**

> The devils advocate makes valid points, but overstates the case:
> 
> 1. **Incremental changes:** Self-healing doesn't do wholesale retraining. Small, statistically validated threshold shifts reduce compound error risk. **Gemini validated:** Bounded threshold shifting is the recommended mitigation.
> 
> 2. **Multiple validation layers:** Drift detection + A/B testing + holdout test set + rollback mechanisms create feedback. **Gemini validated:** F1 drop ≥ 0.05 → immediate revert to previous version.
> 
> 3. **Hybrid model:** Combine self-healing with quarterly manual review. Not fully automated, but more responsive than annual recalibration. **Gemini agrees:** Human-in-the-loop required for Level 3 critical confidence alerts.
> 
> 4. **Transparency trade-off:** If users know the system adapts, they can audit it. Stale thresholds silently fail—worse.
> 
> 5. **Inevitable obsolescence:** Without adaptation, the system will definitely fail. Self-healing may fail too, but at least you have a chance. **Gemini confirmed:** SWE-bench 4.4% → 71.7% proves static thresholds decay rapidly.

**Conclusion:** Self-healing is a bet on epistemic humility + operational discipline. It's not guaranteed to work, but the status quo (manual recalibration every N years) is worse. **Gemini's verdict:** Proceed with bounded threshold shifting + rollback, avoid unbounded retraining.

### 6.3 Dunning-Kruger Guard: Scope Limitations

> **GEMINI STATUS: Updated with Gemini's own scope limitations + new knowledge.**

**Be honest about what we don't know:**

1. **Code stylometry:** ⚠️ IMPROVED — Gemini cross-validated against LLM-AuthorBench (32K programs), arXiv:2507.00838 (short-sample stylometry). We now have stronger evidence base, but still no RCT specific to this heuristic ensemble.

2. **Concept drift:** ⚠️ IMPROVED — ADWIN validated at GRADE: High. But self-supervised drift detection in code stylometry specifically remains unproven. The discrete syntax problem (Gemini's biggest scope limitation) applies here.

3. **LLM evolution:** ✅ IMPROVED — SWE-bench convergence data (4.4% → 71.7%) and RLHF/DPO mechanism (arXiv:2507.00838) provide concrete empirical grounding. Inter-model fingerprints remain separable at >97% (LLM-AuthorBench).

4. **Semi-supervised learning on code:** 🔬 STILL OPEN — No Gemini finding on this. Pseudo-labeling specifically flagged as high-risk.

5. **Operational complexity:** 🔬 STILL OPEN — Not addressed by Gemini.

6. **Continuous math on discrete structures (NEW):** Wasserstein-2 and other continuous divergence metrics may behave unpredictably on sparse ASTs. This is applying optimal transport theory to fundamentally discrete, structured data. Gemini flagged this as its biggest scope limitation.

**What we should research:** ~~Before building, empirically validate on historical data that self-healing would have worked.~~ **Phases 1-2 are now implemented.** Next priority: collect ≥50 telemetry evaluations and run first drift check. Long-term: validate Wasserstein behavior on real code AST distributions.

### 6.4 Separating Theoretical Proposals from Validated Systems

> **UPDATED with Gemini GRADE assessments.**

**Tier 1 (Empirically Validated — Gemini GRADE: High/Moderate):**
- ADWIN drift detection: published, tested in production. **Gemini: High.** ✅ IMPLEMENTED
- Wasserstein-2 for global drift: theoretically optimal. **Gemini: Moderate.** ⚠️ Discrete syntax caveat
- BOCD (Bayesian changepoint): exact posterior uncertainty. **Gemini: Moderate.** Future candidate
- A/B testing / shadow deployment: proven methodology. ✅ On roadmap (Phase 3-4)
- Conformal prediction CIs: standard technique. ✅ IMPLEMENTED

**Tier 2 (Theoretically Sound, Limited Empirical Validation — Gemini GRADE: Moderate/Low):**
- Bregman projection + quantile shift (zero-label recalibration): **Gemini validated as primary strategy**
- MAB signal weighting (Thompson Sampling/UCB): **Gemini: Moderate.** Phase 5 candidate
- Logistic regression refit on pseudo-labels: **Gemini: Low.** Gated by CI bounds only
- ~~Page-Hinkley test~~: Not specifically recommended by Gemini. ADWIN preferred.

**Tier 3 (Novel, Untested — Gemini GRADE: Very Low):**
- Dynamic reference generation from current LLMs: **Gemini: Very Low.** No published precedent. Phase 5+ experimental
- Adversarial calibration: interesting, but unclear if it works or just teaches LLMs to evade
- Crowdsourced recalibration: not assessed by Gemini

**Research Priority:** Tier 1 methods implemented. Tier 2 methods next (Phases 3-5). Tier 3 experimental only.

---

## RESEARCH AREA 7: Integrated System Design & Implementation Roadmap

> **GEMINI STATUS: ✅ VALIDATED — Gemini proposed a 5-phase roadmap that closely mirrors
> this one. Updated below to reflect: (a) Gemini's specific algorithm recommendations,
> (b) what's already implemented in vibe_check.py, (c) revised timelines.**

### 7.1 Phase 1: Baseline + Monitoring (Months 1-2) — ✅ IMPLEMENTED

**Objective:** Build infrastructure to understand the problem.

**Tasks:**
1. ✅ Implement signal logging to all vibe_check.py runs (JSONL) — `VIBE_CHECK_TELEMETRY_DIR` env var
2. ⬜ Build dashboards: signal distributions over time (time series plots)
3. ✅ Implement baseline variance calculation from telemetry data
4. ✅ Establish calibration versioning (`v2026_q2_gemini`)
5. ⬜ Curate holdout test set (200-500 manually labeled PRs) — see PROMPT_LABELED_DATASET.md

**Success Criteria:**
- ✅ Signal values logged per-evaluation with timestamp, PR metadata, calibration version
- ⬜ Can visualize whether drift is happening in real-time (needs dashboard)
- ⬜ Have labeled validation data (see labeled dataset prompt)

### 7.2 Phase 2: Drift Detection (Months 3-4) — ✅ IMPLEMENTED

**Objective:** Detect when recalibration is needed.

**Tasks:**
1. ✅ Implement drift detection — `--drift-status` flag in vibe_check.py
2. ✅ Set thresholds: Hoeffding-bound per-signal (1.5σ), CI collapse (<0.15 avg width)
3. ✅ Multi-tiered decision logic: TRIGGER_RECALIBRATION / TRIGGER_ALERT_MANUAL_REVIEW / CONTINUE
4. ⬜ Run on historical data: what would have been detected? (needs ≥50 evaluations)
5. ⬜ False positive analysis on real telemetry data

**Success Criteria:**
- ✅ Returns INSUFFICIENT_DATA when <50 evaluations (tested)
- ✅ Implements Gemini-recommended multi-tiered logic
- ⬜ Validated on real drift scenarios (needs production data)

### 7.3 Phase 3: Unsupervised Recalibration (Months 5-6) — ⬜ NOT YET IMPLEMENTED

**Objective:** Automatically adapt thresholds. **Gemini algorithm: Bregman projection + quantile shift.**

**Tasks:**
1. Implement KDE-based distribution modeling for each signal
2. Bregman projection: map drifted distribution to historical KDE shape
3. Adjust percentile cutoffs to maintain original False Positive Rate
4. Shadow deployment: score all PRs with both old and new thresholds
5. Measure disagreement: what % of PRs get different classification?
6. Manual review: do disagreements look valid?

**Success Criteria:**
- Shadow deployment matches old thresholds on 95% of cases
- 5% disagreement cases seem like genuine improvements
- No obvious failure modes

### 7.4 Phase 4: Canary Rollout + Automated Rollback (Months 7-8) — ⬜ NOT YET IMPLEMENTED

**Objective:** Deploy recalibrated thresholds safely. **Gemini addition: F1-based rollback.**

**Tasks:**
1. Canary rollout: route 5% of evaluations to new calibration
2. Monitor error rates, confidence scores, CI widths
3. ✅ Rollback trigger defined: F1 drop ≥ 0.05 → immediate revert
4. Weak-label recalibration: top 5% most confident predictions as pseudo-labels,
   gated by conformal prediction CI (narrow-bound only)
5. Logistic regression refit over 10 signals (if weak labels available)
6. Compare to Phase 3 unsupervised result

**Success Criteria:**
- Canary produces no regressions on holdout set
- Weak-label model beats unsupervised on holdout set (if labels available)
- Rollback mechanism activates correctly on injected degradation

### 7.5 Phase 5: Dynamic Signal Weighting + Experimental (Months 9+) — ⬜ FUTURE

**Objective:** Advanced self-healing capabilities.

**Tasks:**
1. MAB dynamic signal weighting (Thompson Sampling / UCB) — **Gemini: Moderate**
2. Dynamic Reference Generation (query frontier LLMs for fresh baselines) — **Gemini: Very Low**
3. Architectural hallucination detection as Signal 11 (Georgia Tech SSLab findings)
4. Quarterly manual audit: pick 50 random PRs, verify vibe_score correctness
5. Document calibration history: maintain audit trail

**Success Criteria:**
- System runs for 6 months with <2 manual interventions
- Holdout test set accuracy stable (within 5% over time)
- Zero catastrophic failures

---

## RESEARCH AREA 8: Questions for Deep Research Agents

### 8.1 Key Empirical Questions

1. **Signal Drift:** How much have the 10 signals actually changed from 2023 to 2026? (Measure if possible on historical code)
2. **Model Release Impact:** Did each major model release (GPT-4 Turbo, o1, Claude 4) cause measurable signal shifts?
3. **Convergence Rate:** Are signals converging exponentially or linearly? Will we have 12 months before unusable, or 3 years?
4. **Label Requirement:** What's minimum labeled data needed for semi-supervised recalibration to beat unsupervised baseline?
5. **Operational Overhead:** How much compute/monitoring infrastructure is required? Rough cost estimate?

### 8.2 Methodological Questions

1. **Drift Detection Tuning:** Which drift detector (ADWIN vs. Page-Hinkley vs. DDM) is optimal for code stylometry? No published comparison exists.
2. **Pseudo-label Reliability:** How accurate must pseudo-labels be for semi-supervised learning not to backfire? (E.g., if 70% of pseudo-labels wrong?)
3. **Threshold Adaptation Math:** If signal distribution shifts left by 0.1 SD, how much should threshold shift? (Theoretically derived answer?)
4. **Feedback Loop Stability:** Can you prove the system won't diverge in recalibration? (Stability analysis)

### 8.3 Implementation Questions

1. **Infrastructure:** Should recalibration run in-process, or as separate scheduled job?
2. **State Management:** How to version + store calibration state? Database schema?
3. **User Communication:** How much recalibration detail should users see? (Transparency vs. confusing)
4. **Sampling Strategy:** For high-volume systems (1000s PRs/day), sample 10%? Or analyze all?

---

## RESEARCH AREA 9: Recommended Reading List

### Foundational Drift Detection
- Gama et al. (2014). "Learning from Evolving Data Streams" (comprehensive survey)
- Ditzler et al. (2015). "Learning in Nonstationary Environments" (practical overview)
- **Bifet & Gavaldà (2007). "Learning from Time-Changing Data with Adaptive Windowing" (ADWIN paper)** — Gemini GRADE: High
- Page (1954). "Continuous Inspection Schemes" (Page-Hinkley test, foundational)
- **Adams & MacKay (2007). "Bayesian Online Changepoint Detection"** — Gemini GRADE: Moderate
- [Benchmarking Change Detector Algorithms (ArTS/IEEE)](https://arts.units.it/retrieve/7a52a7b5-351d-43f4-9cca-a77660b4dbd9/futureinternet-15-00169-v2.pdf) — Added via Gemini

### Code Stylometry & LLM Detection
- **[An Empirical Study on Detecting AI-Generated Source Code (ICSE 2025)](https://arxiv.org/abs/2411.04299)** — CCR universal discriminator
- **[Detection of LLM-Paraphrased Code via Stylometry (2025)](https://arxiv.org/abs/2502.17749)** — Docstring + naming signals
- **[Automatic Detection of LLM-Generated Code: Claude 3 Case Study (2024)](https://arxiv.org/abs/2409.01382)** — Single-model study
- **[Stylometry in short samples (arXiv:2507.00838)](https://arxiv.org/abs/2507.00838)** — RLHF/DPO signal inflation. Added via Gemini
- **LLM-AuthorBench** (32K programs) — Inter-model separation >97%. Referenced via Gemini
- [I Know Which LLM Wrote Your Code (2025)](https://arxiv.org/abs/2506.17323)

### Self-Healing ML
- **[Self-Healing ML Pipelines (Preprints.org:202510.2522)](https://www.preprints.org/manuscript/202510.2522)** — Added via Gemini
- [Self-Healing Machine Learning Framework (Semantic Scholar)](https://www.semanticscholar.org/paper/Self-Healing-Machine-Learning%3A-A-Framework-for-in-Rauba-Seedat/e2670a59f28ea58a9e05391372cbad6c361cc1a9) — Added via Gemini
- [Unsupervised Concept Drift Detection from Deep Learning Representations (arXiv:2406.17813)](https://arxiv.org/abs/2406.17813)
- [concept-drift library (GitHub)](https://github.com/blablahaha/concept-drift)

### Semi-Supervised Learning
- Zhu & Goldberg (2009). "Introduction to Semi-Supervised Learning" (textbook)
- Grandvalet & Bengio (2004). "Semi-Supervised Learning by Entropy Minimization" (consistency regularization)
- **[Calibrating Pseudo-Labeling with Class Distribution (ACL 2025)](https://aclanthology.org/2025.emnlp-main.658.pdf)** — Feedback loop risk. Added via Gemini

### ML Ops & Monitoring
- Sculley et al. (2015). "Hidden Technical Debt in Machine Learning Systems" (monitoring, maintenance)
- Breck et al. (2017). "The ML Test Score" (testing ML systems)
- [A Comparison of Approaches for Handling Concept Drifts (IEEE)](https://ieeexplore.org/iel8/6287639/6514899/10947750.pdf) — Added via Gemini

### LLM Code Generation Evolution & Security
- **[Stanford HAI 2025 AI Index — Technical Performance](https://hai.stanford.edu/ai-index/2025-ai-index-report/technical-performance)** — SWE-bench convergence. Gemini GRADE: High
- **[Vibe Coding: Toward an AI-Native Paradigm (arXiv:2510.17842)](https://arxiv.org/abs/2510.17842)** — Added via Gemini
- **Georgia Tech SSLab Vibe Security Radar** — 35 CVEs/month from AI code (March 2026). Added via Gemini
- **[A Self-Improving Architecture for Dynamic Safety in LLMs (arXiv:2511.07645)](https://arxiv.org/abs/2511.07645)** — Added via Gemini
- OpenAI technical reports on GPT-4, o1
- Anthropic / DeepSeek / Meta research on Claude, other models

---

## FINAL SYNTHESIS & DECISION FRAMEWORK

### For Implementation, Prioritize By:

1. **Certainty:** Use well-established methods (ADWIN, logistic regression) before novel ones
2. **Empirical Validation:** Test on historical data first (simulation) before production
3. **Operational Simplicity:** Start with Phase 1-2 (monitoring + simple drift detection); avoid Phase 4+ complexity until necessary
4. **Risk Tolerance:** If false negatives (AI code sneaks in) are very costly, be conservative; recalibrate slowly
5. **Data Availability:** Self-healing with no labels is risky; prioritize mechanisms to get labels

### Success Metrics (Define Now, Measure Later)

- **Signal Stability:** Holdout test set accuracy stays within ±5% over 6 months
- **Operational:** <1 false alarm per week; <1 manual rollback per quarter
- **User Trust:** Developers report that vibe_check alerts remain calibrated (qualitative feedback)
- **Coverage:** Recalibration triggers on schedule (quarterly or on drift detection)

---

## APPENDIX: Glossary

- **Drift:** Shift in input feature distribution P(X)
- **Concept Drift:** Shift in decision boundary P(Y|X)
- **Pseudo-label:** High-confidence prediction used as ground truth
- **Calibration:** Adjustment of thresholds/weights to match observed data distributions
- **Rollback:** Reverting to previous configuration after recalibration failure
- **AUC:** Area Under Curve (ROC or PR); 0.5 = random, 1.0 = perfect
- **False Positive:** Marking human code as AI
- **False Negative:** Missing AI-generated code
- **Semi-Supervised Learning:** Leveraging unlabeled data + few labeled samples
- **Thompson Sampling:** Probabilistic approach to multi-armed bandit problem
- **Wasserstein Distance:** Optimal transport distance between distributions

---

## APPENDIX B: Gemini Research Validation Summary

**Gemini Deep Research Title:** "Autonomous Recalibration in Heuristic Code Classifiers: Mitigating Concept Drift in the Era of Vibe Coding"
**Date:** April 2026
**Scope:** 20-page synthesis, 60+ sources, GRADE-assessed

### What Gemini Confirmed
- ADWIN is optimal for gradual stylometric drift (GRADE: High)
- Wasserstein-2 preferred for global drift measurement (GRADE: Moderate)
- CCR remains universal discriminator, though magnitude fluctuates (multiple sources)
- SWE-bench convergence proves static thresholds decay (GRADE: High)
- Inter-model fingerprints remain separable even as human-AI gap narrows (LLM-AuthorBench)
- RLHF/DPO mechanism drives specific signal inflation (docstrings, naming)
- Bounded threshold shifting is safer than unbounded retraining
- F1 drop ≥ 0.05 is appropriate rollback trigger

### What Gemini Flagged as High Risk
- Pseudo-labeling feedback loop divergence (ACL 2025, GRADE: Low)
- Continuous math on discrete code structures (biggest scope limitation)
- Dynamic Reference Generation has no precedent (GRADE: Very Low)
- Manual recalibration may be safer than automated miscalibration

### What Remains Open (Not Addressed by Gemini)
- SPC methods (Shewhart, EWMA) for code stylometry
- Crowdsourced recalibration incentive design
- Explicit feedback mechanisms and minimum labeling rates
- Semi-supervised learning effectiveness specifically on code
- Operational complexity / cost-benefit analysis
- Holdout test set curation methodology
- Per-codebase calibration (addressed in separate prompt: PROMPT_CALIBRATION_AGENT.md)

### Implementation Status (as of April 2026)
- ✅ Phase 1: JSONL telemetry + baseline variance calculation
- ✅ Phase 2: Hoeffding-bound drift detection + CI collapse check + multi-tiered decision logic
- ✅ Conformal prediction confidence intervals
- ✅ Calibration versioning (v2026_q2_gemini)
- ⬜ Phase 3: Unsupervised threshold adaptation (Bregman projection + quantile shift)
- ⬜ Phase 4: Canary rollout + automated rollback (F1 ≥ 0.05)
- ⬜ Phase 5: MAB signal weighting + dynamic reference generation

---

## END OF PROMPT

**Token Budget Estimate:** This prompt is designed for 50-100k tokens of analysis. Deep research agents should:
1. Search for papers on each topic area — **Many now confirmed by Gemini; focus on OPEN items**
2. Synthesize findings into concrete recommendations — **Architecture validated; focus on Phase 3-5 implementation**
3. Propose full system architecture with code sketches — **6-component pipeline validated; need Phase 3 code**
4. Identify knowledge gaps and unknown unknowns — **See "What Remains Open" above**
5. Produce a prioritized implementation roadmap — **Phases 1-2 done; focus on Phase 3 next**

**Deliverable:** Research report with sections mirroring the 9 areas above, plus integrated summary and specific recommendations for your codebase. **Priority: deep-dive on discrete syntax problem (Gemini's biggest scope limitation) and Phase 3 Bregman projection implementation details.**
