# Research Synthesis: AI-Generated Code Detection

> **Apr 2026:** Gemini structured review of **deterministic** detector limits (multicollinearity of the 10-signal ensemble, Wasserstein on discrete-derived features, adversarial tools, SSL pitfalls, per-language baselines) → **`GEMINI_AI_CODE_DETECTION_RESEARCH.md`**. Use it alongside this ledger; where they conflict on drift transport, prefer the newer **discrete-syntax** caveat.

## Evidence Ledger

| Claim | Sources | Quality | Confidence | Status |
|-------|---------|---------|------------|--------|
| Comment-to-code ratio is universal discriminator | arXiv:2411.04299, arXiv:2502.17749, Gemini synthesis | Peer-reviewed, large N | 85 | CONCLUSIVE-PROVISIONAL |
| CCR predictive magnitude fluctuates by model instruction tuning | Gemini synthesis (citing arXiv:2409.01382, arXiv:2507.00838) | Cross-referenced, multi-model | 75 | CONCLUSIVE-PROVISIONAL |
| LLMs document 80-100% of functions | arXiv:2502.17749 | Peer-reviewed | 75 | CONCLUSIVE-PROVISIONAL |
| Naming uniformity >95% in LLM code | arXiv:2502.17749 | Peer-reviewed | 70 | CONCLUSIVE-PROVISIONAL |
| LLMs favor declarative over control flow | arXiv:2409.01382 | Single study, Claude 3 only | 55 | INCONCLUSIVE |
| AI code has 5.7-7.1% churn vs 3.3% baseline | Grey lit (larridin.com) | Not peer-reviewed | 40 | INSUFFICIENT-DATA |
| Humans cannot distinguish AI from human code | arXiv:2411.04299 | Empirical, peer-reviewed | 80 | CONCLUSIVE-PROVISIONAL |
| Empty catches are AI-indicative | arXiv:2512.05239 | Survey, peer-reviewed | 65 | INCONCLUSIVE |
| SWE-bench AI resolution: 4.4% (2023) → 71.7% (2024) | Stanford HAI 2025 AI Index (via Gemini) | Institutional report, large N | 90 | CONCLUSIVE-HIGH |
| Stylometric convergence: GPT-3.5 AUC=0.96 → modern models significantly lower | arXiv:2409.01382, CodeSearchNet (via Gemini) | Peer-reviewed + empirical | 80 | CONCLUSIVE-PROVISIONAL |
| AI code introduces architectural hallucinations (missing auth, injection vulns) | Georgia Tech SSLab Vibe Security Radar (via Gemini) | Academic lab, production data | 70 | CONCLUSIVE-PROVISIONAL |
| 35+ CVEs/month directly attributable to AI generation (March 2026) | Georgia Tech SSLab (via Gemini) | Single-month snapshot, lab report | 60 | INCONCLUSIVE |
| Inter-model stylistic fingerprints remain separable (>97% accuracy GPT-4o vs GPT-4.1) | LLM-AuthorBench, 32K programs (via Gemini) | Large dataset, encoder-only classifiers | 75 | CONCLUSIVE-PROVISIONAL |
| RLHF/DPO drives docstring over-indexing and naming hyper-uniformity | Gemini synthesis (citing arXiv:2507.00838) | Theoretical + empirical observation | 65 | INCONCLUSIVE |
| ADWIN is optimal drift detector for gradual stylometric convergence | Bifet & Gavaldà; Gemini GRADE=High | Foundational CS, massive body of RCTs | 85 | CONCLUSIVE-HIGH |
| Optimal transport for drift on **scalar vibe signals** | W2 can spike on trivial AST refactors; Sinkhorn / structured MMD better motivated for discrete code (Gemini Apr 2026; Feydy et al.) | Theory strong; empirical on *these* heuristics partial | 65 | INCONCLUSIVE |
| BOCD provides exact posterior uncertainty for changepoint detection | Adams & MacKay 2007; Gemini GRADE=Moderate | Seminal work, good multidimensional scaling | 70 | CONCLUSIVE-PROVISIONAL |
| Pseudo-labeling carries severe feedback loop divergence risk | ACL Anthology 2025 (via Gemini); Gemini GRADE=Low | Well-documented risk, no code-specific validation | 75 | CONCLUSIVE-PROVISIONAL |
| Dynamic Reference Generation (query LLMs for fresh baselines) | Gemini synthesis; GRADE=Very Low | Novel proposal, no published precedent in code stylometry | 35 | INSUFFICIENT-DATA |
| MAB (Thompson Sampling/UCB) viable for dynamic signal weighting | Recommendation systems literature; Gemini GRADE=Moderate | Strong theoretical foundation, untested on live code | 60 | INCONCLUSIVE |
| Self-healing bounded threshold shifting preferable to unbounded retraining | Gemini adversarial analysis | Logical argument, no RCT | 65 | INCONCLUSIVE |

## Source Quality Assessment

### Tier 1: High quality
- **arXiv:2411.04299** (ICSE 2025): Large empirical study, peer-reviewed at top venue. N=sufficient. Replication: methodology published. COI: Academic, no industry funding disclosed.
- **arXiv:2502.17749** (2025): Code stylometry focus. Peer-reviewed. Comprehensive feature analysis. Multiple model comparison.
- **Stanford HAI 2025 AI Index** (via Gemini): Institutional report. SWE-bench convergence data (4.4% → 71.7%).
- **Adams & MacKay 2007** (BOCD): Seminal foundational work. Universally cited in changepoint detection.
- **Bifet & Gavaldà** (ADWIN): Foundational. Massive body of literature and RCTs in streaming ML.

### Tier 2: Moderate quality  
- **arXiv:2409.01382** (2024): Claude 3 Haiku only, limited generalization. Methodology sound but single-model. Gemini cross-validated against CodeSearchNet dataset.
- **arXiv:2512.05239** (2025): Survey methodology. Good breadth but relies on taxonomy from limited sample.
- **ICML 2024 Binoculars**: Strong methodology but requires ML models (not applicable to deterministic approach).
- **Georgia Tech SSLab Vibe Security Radar** (via Gemini): Academic lab, production evidence. 35 CVEs/month finding is single snapshot. Architectural hallucination finding is high-signal.
- **LLM-AuthorBench** (via Gemini): 32K program dataset. Inter-model separation >97%. Validates that fingerprints persist even as human-AI gap narrows.
- **arXiv:2507.00838** (via Gemini): Stylometry in short samples. RLHF/DPO signal inflation mechanism.
- **DriftLens framework** (via Gemini): Fréchet Inception Distance for drift. Wasserstein-2 validation.

### Tier 3: Low quality / grey lit
- Code turnover metrics (larridin.com): Blog post, no peer review. Interesting signal but unvalidated.
- AI usage measurement framework (GitHub): Open source, community-maintained. Anecdotal evidence base.
- **Gemini-proposed Dynamic Reference Generation**: Novel concept (query frontier LLMs for fresh baselines). No published precedent. Theoretically sound but high implementation risk.

## Adversarial Review

### Arguments against this approach
1. **Signal decay (VALIDATED by Gemini)**: SWE-bench data confirms rapid convergence. GPT-3.5 was easily detectable (AUC 0.96); modern frontier models are not. Static 2023 thresholds are already partially obsolete for docstring coverage.
2. **Codebase bias**: Well-run codebases with strict linting, documentation requirements, and style guides will trigger false positives on every signal except hallucinated APIs.
3. **Ensemble fragility**: Weighting 10 signals doesn't make them independent. Comment ratio and comment phrasing correlate; docstring consistency and comment ratio correlate. Effective independent signals may be only 5-6.
4. **No ground truth**: Without labeled datasets of "vibe coded" vs "AI-assisted but understood" code, we can't validate the core claim.
5. **Cultural bias**: Some teams and cultures produce more documentation naturally. The human baselines cited are predominantly from Western open-source projects.
6. **Feedback loop divergence (NEW from Gemini)**: Self-healing via pseudo-labels risks confirmation bias where the system becomes "perfectly calibrated to its own historical hallucinations." Bounded threshold shifting is the mitigation.
7. **Discrete syntax problem (NEW from Gemini)**: Code is structured, deeply contextual, and fundamentally discrete. Continuous divergence metrics (Wasserstein) may behave unpredictably on sparse ASTs. The Gemini paper itself flags this as its biggest scope limitation.

### Where counterarguments succeed
- Points 1 and 6 are the strongest. The tool has a shelf life AND the self-healing approach carries real risk.
- Point 7 is foundational, we're applying continuous math to discrete structures.
- Gemini's own adversarial review argues manual periodic recalibration may be safer than automated miscalibration.

### Mitigations
- Tool is presented as probabilistic, not definitive
- Recommendations focus on "what to verify" rather than "this is AI code"
- Grade C (30-50%) intentionally ambiguous to avoid false accusations
- Users are told about false positive/negative rates
- Self-healing module uses bounded threshold shifting, not unbounded retraining
- Rollback trigger at F1 drop ≥ 0.05 prevents catastrophic miscalibration
- Human-in-the-loop required for Level 3 critical confidence alerts

## Self-Healing Architecture (from Gemini Research)

### Recommended approach: 6-component decoupled pipeline

| Component | Function | Algorithm |
|-----------|----------|-----------|
| Inference Engine | Score PRs against active thresholds | Deterministic heuristics + conformal prediction CIs |
| Telemetry Logger | Immutable append-only signal log | JSONL data warehouse |
| Drift Monitor | Detect distributional shifts | ADWIN (per-signal) + Wasserstein-2 (global) |
| Recalibration Node | Synthesize new thresholds | KDE + Bregman projection (zero-label) or logistic regression (weak-label) |
| Deployment Gate | Validate before activation | Shadow deployment + canary rollout (5% traffic) |
| Rollback Engine | Revert bad calibrations | F1 drop ≥ 0.05 → immediate revert to previous version |

### Drift trigger logic (multi-tiered)
```
IF wasserstein_dist > 1.5 * baseline_std AND adwin_signals >= 2:
    → TRIGGER_RECALIBRATION (automatic)
ELIF adwin_signals == 1 OR confidence_interval_collapse:
    → TRIGGER_ALERT_MANUAL_REVIEW
ELSE:
    → CONTINUE_CURRENT_THRESHOLDS
```

### Recalibration strategies
- **Zero-label** (no ground truth): Bregman projection + quantile shift. Maps drifted distribution to historical KDE shape, adjusting percentile cutoffs to maintain original False Positive Rate.
- **Weak-label** (top 5% most confident predictions as pseudo-labels): Logistic regression refit over 10 signals. Gated by conformal prediction CI, only narrow-bound predictions admitted.
- **Dynamic Reference Generation** (experimental): Periodically query frontier LLMs (Claude, GPT) on HumanEval/LeetCode tasks. Extract fresh signal baselines from pure-LLM output. GRADE: Very Low, no precedent.

### Implementation roadmap
- Phase 1 (Months 1-2): JSONL telemetry + baseline variance calculation
- Phase 2 (Months 3-4): ADWIN + Wasserstein-2 alerting (observational only)
- Phase 3 (Months 5-6): Unsupervised threshold adaptation (shadow mode)
- Phase 4 (Months 7-8): Canary rollout + automated rollback
- Phase 5 (Months 9+): Dynamic reference generation + MAB signal weighting

### GRADE assessment of self-healing methods

| Method | Evidence | RoB Concerns | Upgrade/Downgrade |
|--------|----------|-------------|-------------------|
| ADWIN Drift Detection | High | Proven in streaming ML; low risk of bias | **Upgrade**: Massive literature + RCTs |
| Wasserstein-2 Adaptation | Moderate | Theoretically optimal; sensitive to outliers | **Downgrade**: Limited empirical results on code ASTs |
| BOCD (Bayesian Changepoint) | Moderate | Exact inference; assumes known prior structures | **Upgrade**: Highly resilient to multidimensional scaling |
| Pseudo-Labeling Retraining | Low | High confirmation bias; assumes conformal bounds hold | **Downgrade**: Feedback loop instability well-documented |
| Dynamic Reference Generation | Very Low | High implementation risk; models may spoof humans | **Downgrade**: No published precedent in code stylometry |
| MAB Signal Weighting | Moderate | Works in simulation; untested on live code | **Upgrade**: Strong theoretical foundation in recommendation systems |

## Key finding from Gemini: Georgia Tech SSLab Vibe Security Radar

Modern agentic LLMs don't just produce localized typos, they introduce **baked-in design flaws born of hallucinated architectural assumptions**:
- Deploying server-side infra lacking basic authentication
- Committing command injection vulnerabilities
- 35 new CVEs in a single month (March 2026) directly attributable to AI generation

This validates upgrading hallucinated API detection from a supplementary signal (weight 0.06) to a potentially critical security signal, especially once integrated with package manifests via MCP.

Additionally: as developers strip explicit AI metadata (co-author tags, bot emails), detection must rely entirely on deep behavioral signatures. The Georgia Tech finding that LLMs lack human entropy, producing uniform patterns across thousands of repos, confirms the enduring viability of stylometric detection even as surface features converge.

## Signals NOT implemented (and why)

| Signal | Why excluded |
|--------|-------------|
| Perplexity/entropy (DetectGPT, Binoculars) | Requires trained LLM, not deterministic |
| CodeBERT embeddings | Requires fine-tuned model |
| Token frequency distribution | Requires language model tokenizer |
| Code clone detection | Requires large corpus comparison |
| Timing analysis (keystroke patterns) | Not available from diff |
| IDE telemetry (Copilot accept rate) | Not available from diff |
| Architectural security signals (SSLab Radar) | Requires deep semantic analysis; future candidate for Signal 11 |

## Future work
- Per-codebase calibration (learn the team's baseline comment ratio, naming patterns)
- Integration with package manifest for hallucinated API validation
- Longitudinal tracking (is AI probability trending up across PRs?)
- Confidence interval estimation via conformal prediction (Gemini-recommended)
- Self-healing telemetry pipeline (Phase 1: JSONL logging)
- ADWIN + Wasserstein-2 drift monitoring (Phase 2)
- MAB dynamic signal weighting (Phase 4+)
- Architectural hallucination detection as Signal 11 (SSLab Radar findings)

## References

### Original sources
- [An Empirical Study on Detecting AI-Generated Source Code (ICSE 2025)](https://arxiv.org/abs/2411.04299)
- [Detection of LLM-Paraphrased Code via Stylometry (2025)](https://arxiv.org/abs/2502.17749)
- [Automatic Detection of LLM-Generated Code: Claude 3 Case Study (2024)](https://arxiv.org/abs/2409.01382)
- [Survey of Bugs in AI-Generated Code (2025)](https://arxiv.org/abs/2512.05239)
- [Spotting LLMs With Binoculars (ICML 2024)](https://arxiv.org/abs/2401.12070)
- [GPTSniffer: CodeBERT-based Detection (JSS 2024)](https://doi.org/10.1016/j.jss.2024.112059)
- [I Know Which LLM Wrote Your Code (2025)](https://arxiv.org/abs/2506.17323)

### Added via Gemini Deep Research synthesis
- [Stanford HAI 2025 AI Index: Technical Performance](https://hai.stanford.edu/ai-index/2025-ai-index-report/technical-performance)
- [Vibe Coding: Toward an AI-Native Paradigm (arXiv:2510.17842)](https://arxiv.org/abs/2510.17842)
- [Stylometry recognizes human and LLM-generated texts in short samples (arXiv:2507.00838)](https://arxiv.org/abs/2507.00838)
- [Self-Healing ML Pipelines: Automating Drift Detection (Preprints.org:202510.2522)](https://www.preprints.org/manuscript/202510.2522)
- [Self-Healing Machine Learning: A Framework (Semantic Scholar)](https://www.semanticscholar.org/paper/Self-Healing-Machine-Learning%3A-A-Framework-for-in-Rauba-Seedat/e2670a59f28ea58a9e05391372cbad6c361cc1a9)
- [Benchmarking Change Detector Algorithms from Different Concept Drift Perspectives (ArTS)](https://arts.units.it/retrieve/7a52a7b5-351d-43f4-9cca-a77660b4dbd9/futureinternet-15-00169-v2.pdf)
- [Bayesian Online Changepoint Detection (Adams & MacKay 2007)](https://lips.cs.princeton.edu/pdfs/adams2007changepoint.pdf)
- [Unsupervised Concept Drift Detection from Deep Learning Representations (arXiv:2406.17813)](https://arxiv.org/abs/2406.17813)
- [concept-drift library (GitHub: blablahaha)](https://github.com/blablahaha/concept-drift)
- [A Comparison of Approaches for Handling Concept Drifts (IEEE)](https://ieeexplore.org/iel8/6287639/6514899/10947750.pdf)
- [Calibrating Pseudo-Labeling with Class Distribution (ACL 2025)](https://aclanthology.org/2025.emnlp-main.658.pdf)
- [A Self-Improving Architecture for Dynamic Safety in LLMs (arXiv:2511.07645)](https://arxiv.org/abs/2511.07645)
- Georgia Tech SSLab Vibe Security Radar (referenced via Gemini; primary source pending direct citation)
- LLM-AuthorBench (32K program dataset; referenced via Gemini; primary source pending)
