# Gemini Deep Research v2: Open Questions in Heuristic AI Code Detection

**Status:** Ready to submit
**Prerequisites:** Gemini Deep Research v1 completed (April 2026, "Autonomous Recalibration in Heuristic Code Classifiers"). This prompt covers the 6 research areas that v1 either flagged as unresolved, didn't address, or that have emerged since.

Copy everything below the line into Gemini Deep Research.

---

```
═══════════════════════════════════════════════════════════
META
═══════════════════════════════════════════════════════════

ROLE: Research scientist investigating open problems in deterministic AI-generated code detection.

TOKEN BUDGET: UNLIMITED. Be fully exhaustive. Do not summarize prematurely, do not truncate literature reviews, do not skip negative results or methodological limitations. Cover every relevant paper, every conflicting finding, every edge case. Length is not a constraint, thoroughness is.

PRIOR WORK: You (Gemini) produced a 20-page synthesis in April 2026 titled "Autonomous Recalibration in Heuristic Code Classifiers: Mitigating Concept Drift in the Era of Vibe Coding" covering:
- ADWIN drift detection (GRADE: High) ✅
- Wasserstein-2 for global drift (GRADE: Moderate) ✅
- BOCD (GRADE: Moderate) ✅
- Pseudo-labeling risk (GRADE: Low) ✅
- SWE-bench convergence 4.4%→71.7% ✅
- RLHF/DPO signal inflation ✅
- CCR as universal discriminator ✅
- Inter-model fingerprints at >97% (LLM-AuthorBench) ✅
- Georgia Tech SSLab 35 CVEs/month ✅
- Self-healing 6-component pipeline ✅

This prompt covers what v1 LEFT OPEN, FLAGGED AS LIMITATIONS, or DID NOT ADDRESS.

DOWNSTREAM CONSUMER: Claude Opus 4.6 (200K context window). Your output will be ingested directly by an LLM. This means:
- Use consistent, parseable structure throughout (labeled sections, tables, YAML blocks)
- Prefer verbatim quotes from papers over paraphrases, let the downstream model interpret
- Separate FINDINGS (what papers say) from SYNTHESIS (your interpretation) from SPECULATION (your extrapolation beyond evidence)
- For every claim, provide: source, year, sample size, methodology, reported effect size, and your GRADE assessment
- Include null results and failed replications, they constrain the hypothesis space
- When two papers conflict, report both with full methodology comparison, do not pick a winner
- End each research area with a structured summary block (schema provided below)

PROJECT CONTEXT:

We operate vibe_check.py, a deterministic (stdlib-only Python, no ML) PR diff analyzer using 10 weighted heuristic signals:

| # | Signal | Weight | Type | Current Threshold | Vulnerability Status |
|---|--------|--------|------|-------------------|---------------------|
| 1 | Cyclomatic Complexity Ratio (CCR) | 0.18 | Continuous | varies | ROBUST, sole universal discriminator |
| 2 | Docstring Consistency | 0.15 | Continuous | 0.65 | FRAGILE: RLHF/DPO inflates beyond human baseline |
| 3 | Naming Uniformity | 0.13 | Continuous | 0.92 | FRAGILE: RLHF/DPO inflates beyond human baseline |
| 4 | Error Handling Depth | 0.12 | Continuous | 0.45 | MODERATE |
| 5 | Declarative Bias (decl/control ratio) | 0.10 | Continuous | 1.8 | MODERATE |
| 6 | Function Length CV | 0.08 | Continuous | 0.4 | MODERATE |
| 7 | Comment Phrasing (boilerplate %) | 0.08 | Continuous | 0.35 | MODERATE, hypothesized r≈0.6 correlation with Signal 1 |
| 8 | Hallucinated APIs | 0.06 | Binary | presence | HIGH PRECISION, LOW RECALL |
| 9 | Edge Case Nesting Depth | 0.05 | Continuous | 1.5 | MODERATE, hypothesized r≈0.5 correlation with Signal 4 |
| 10 | Commit Metadata Markers | 0.05 | Pattern | pattern match | TRIVIALLY GAMEABLE |

The tool outputs a 0-1 "vibe score" (weighted sum of normalized signal scores) with conformal prediction confidence intervals.

═══════════════════════════════════════════════════════════
RESEARCH AREA 1: SIGNAL CORRELATION & MULTICOLLINEARITY
═══════════════════════════════════════════════════════════

STATUS: Never researched. Prompt existed but was never submitted.
IMPORTANCE: CRITICAL, if correlated signals double-count information, the weighted sum is miscalibrated and confidence intervals are too narrow.

HYPOTHESIZED CORRELATION CLUSTERS:
- Cluster A (documentation signals): CCR ↔ Comment Phrasing ↔ Docstring Consistency (Signals 1, 7, 2). If r>0.5 between any pair, these three signals with combined weight 0.41 may be effectively counting the same thing twice.
- Cluster B (defensive coding signals): Error Handling ↔ Edge Case Depth (Signals 4, 9). Both measure "how defensive is the code." Combined weight 0.17.
- Cluster C (uniformity signals): Naming Uniformity ↔ Function Length CV (Signals 3, 6). Both measure "how cookie-cutter is the structure." Combined weight 0.21.

RESEARCH QUESTIONS:

1.1. EMPIRICAL CORRELATION STRUCTURE IN CODE STYLOMETRY
- What correlation matrices have been published for syntactic code features used in authorship attribution or AI detection?
- Key studies to locate: Caliskan et al. (2015) "De-anonymizing Programmers via Code Stylometry", Frantzeskou et al. (2006) n-gram authorship, Kalgutkar et al. (2016) ML source code authorship, AND any post-2023 studies on AI-generated code detection features.
- For each study: report the full correlation matrix (or as much as published), sample size, languages covered, and whether they used VIF diagnostics.
- Do ANY of these studies use features similar to our 10 signals? Map their features to ours where possible.

1.2. MULTICOLLINEARITY DIAGNOSTICS
- What are standard diagnostic methods for detecting multicollinearity in weighted ensembles? (VIF, condition number, eigenvalue analysis, tolerance)
- At what correlation threshold should features be merged, reweighted, or dropped? (Is r>0.7 the conventional cutoff? What do code stylometry papers use?)
- How does multicollinearity affect confidence interval width? (If our conformal prediction CIs assume independent signals but signals are correlated, how much are CIs underestimated?)

1.3. WEIGHT ADJUSTMENT METHODS
- How should weights be adjusted for correlated features? Compare at least 4 approaches:
  a) Principal Component Analysis (PCA), rotate to orthogonal components
  b) VIF-based deflation, divide weight by VIF
  c) Elastic Net regularization: L1+L2 penalty discovers sparsity
  d) Information-theoretic, mutual information to measure unique vs. shared information
- For each: mathematical formulation, assumptions, limitations, published applications to similar problems.
- Which is most appropriate for a 10-signal deterministic ensemble with no training data? (We can't retrain, we need a principled adjustment to fixed weights.)

1.4. INTERACTION EFFECTS & NON-LINEARITY
- Are there known non-linear relationships between code features? (e.g., does high CCR + high docstring consistency together indicate AI MORE than either alone, multiplicative effect?)
- Has anyone used Random Forests, SHAP values, or partial dependence plots to discover interaction effects among code stylometry features?
- Is our additive weighted sum fundamentally the wrong model? When would a non-linear aggregator (e.g., log-odds, product of experts) be more appropriate?

1.5. LATENT FACTOR ANALYSIS
- If we factor-analyze our 10 signals, how many independent latent factors would we expect?
- Published factor analyses of code style features, what latent structure emerges? (e.g., "documentation quality" factor, "structural uniformity" factor, "defensive coding" factor)
- What is the "effective dimensionality", if our 10 signals reduce to 4 latent factors, we're really using a 4-signal detector with 10 noisy measurements.

SUMMARY BLOCK (fill this out):
```yaml
area_1_summary:
  strongest_evidence: "..."
  weakest_evidence: "..."
  hypothesized_clusters_confirmed: [list]
  hypothesized_clusters_refuted: [list]
  recommended_diagnostic_method: "..."
  recommended_weight_adjustment: "..."
  estimated_effective_dimensionality: "N signals (range)"
  impact_on_confidence_intervals: "CIs likely [under/over]estimated by [X]%"
  grade: HIGH | MODERATE | LOW | VERY_LOW
  key_papers: ["...", "..."]
```

═══════════════════════════════════════════════════════════
RESEARCH AREA 2: THE DISCRETE SYNTAX PROBLEM
═══════════════════════════════════════════════════════════

STATUS: Flagged by Gemini v1 as "biggest scope limitation" but NOT researched.
IMPORTANCE: CRITICAL, this is the theoretical foundation of our entire drift detection system. If Wasserstein-2 behaves unpredictably on discrete code distributions, our drift detector may produce false triggers or miss real drift.

THE PROBLEM:
Our drift detection uses Wasserstein-2 distance to measure distributional shift between baseline and recent signal values. Wasserstein is a continuous optimal transport metric designed for continuous probability distributions. But code is:
- DISCRETE: tokens, AST nodes, and syntax elements are categorical, not continuous
- SPARSE: most possible code structures never appear in any given codebase
- STRUCTURED: code has grammar, not all token sequences are valid programs
- HIGH-DIMENSIONAL: even a small function spans dozens of AST node types
- CONTEXT-DEPENDENT: the same syntax pattern means different things in different languages

When we compute Wasserstein distance on signal values (which ARE continuous, e.g., CCR=0.42), we're measuring continuous-valued statistics derived from discrete structures. This may be fine, or it may introduce systematic artifacts.

RESEARCH QUESTIONS:

2.1. OPTIMAL TRANSPORT ON DISCRETE / MIXED DISTRIBUTIONS
- How does Wasserstein distance behave on distributions with discrete support?
- Are there variants designed for discrete spaces? (e.g., Earth Mover's Distance on histograms, Sinkhorn divergences, sliced Wasserstein on graphs)
- Papers: Peyré & Cuturi (2019) "Computational Optimal Transport", any work on Wasserstein for text/NLP distributions (which face the same discrete problem).
- Specifically: when continuous signals (like CCR) are derived from discrete structures (AST node counts), does Wasserstein distance on the continuous signals faithfully represent distributional shift in the underlying discrete structures?

2.2. ALTERNATIVE DIVERGENCE METRICS FOR CODE DISTRIBUTIONS
- What divergence metrics are used in NLP / program analysis for measuring distributional shift in discrete structured data?
- Candidates: Jensen-Shannon divergence, Maximum Mean Discrepancy (MMD) with appropriate kernels, Fisher-Rao metric, chi-squared distance on discretized histograms, tree edit distance for AST comparison
- For each: mathematical definition, computational cost, behavior on sparse high-dimensional data, published applications to code/text
- Has anyone directly compared Wasserstein vs. alternatives on code-derived features?

2.3. DISCRETIZATION EFFECTS ON DRIFT DETECTION
- If we bin our continuous signals into discrete bins (e.g., CCR in [0, 0.1, 0.2, ...]), does the drift detection behave differently?
- How sensitive is Wasserstein distance to bin width? (Resolution-dependence)
- Is there a principled way to choose bin width for code features?
- Kolmogorov-Smirnov test (which we considered as alternative), does it handle the discrete-origin problem better or worse?

2.4. EMPIRICAL EVIDENCE FROM CODE / NLP DOMAIN
- Has anyone published drift detection results on code feature distributions?
- Has anyone applied optimal transport to software engineering metrics and reported artifacts or unexpected behavior?
- Search: "concept drift" + "software metrics", "distributional shift" + "code features", "optimal transport" + "source code", "Wasserstein" + "program analysis"
- Any work from the mining software repositories (MSR) community on detecting temporal shifts in code metrics?

2.5. PRACTICAL IMPLICATIONS FOR OUR SYSTEM
- Given what the literature says, should we:
  a) Keep Wasserstein-2 as-is (the continuous signal values are "continuous enough")
  b) Switch to an alternative metric better suited to discrete-origin data
  c) Use multiple metrics and require agreement (ensemble drift detection)
  d) Discretize signals first, then use a discrete divergence metric
- What is the risk of false drift triggers from the discrete-origin artifact?
- What is the risk of missed real drift?

SUMMARY BLOCK:
```yaml
area_2_summary:
  discrete_syntax_problem_severity: CRITICAL | MODERATE | MINOR | NON_ISSUE
  wasserstein_on_continuous_derived_signals: SAFE | RISKY | UNKNOWN
  recommended_metric: "..."
  recommended_metric_rationale: "..."
  alternative_metrics_ranked: [{name: "...", suitability: HIGH|MEDIUM|LOW, evidence: "..."}, ...]
  false_trigger_risk: HIGH | MEDIUM | LOW
  missed_drift_risk: HIGH | MEDIUM | LOW
  practical_recommendation: "..."
  grade: HIGH | MODERATE | LOW | VERY_LOW
  key_papers: ["...", "..."]
```

═══════════════════════════════════════════════════════════
RESEARCH AREA 3: ADVERSARIAL ROBUSTNESS OF HEURISTIC DETECTORS
═══════════════════════════════════════════════════════════

STATUS: Gemini v1 mentioned adversarial calibration in passing but did not research robustness.
IMPORTANCE: HIGH, determines the tool's shelf life. If a simple prompt like "write code that looks human-written" defeats all 10 signals, the tool is dead on arrival.

THE THREAT MODEL:
- PASSIVE ADVERSARY: Developer uses Copilot normally, doesn't try to hide it. Our current target.
- ACTIVE ADVERSARY: Developer prompts LLM specifically to evade detection. ("Write code that doesn't look AI-generated", "Use variable naming like a human", "Add realistic edge case handling")
- SYSTEMIC ADVERSARY: LLM providers fine-tune models to produce less detectable code (market pressure for "natural-looking" code).
- TEMPORAL ADVERSARY: Models naturally improve over time (the convergence Gemini v1 documented).

RESEARCH QUESTIONS:

3.1. ADVERSARIAL CODE GENERATION STUDIES
- Has anyone studied what happens when LLMs are prompted to write "human-like" code?
- Specifically: does adversarial prompting defeat individual stylometric signals? Which ones are most robust, which are most fragile?
- Search: "adversarial" + "code generation", "evading" + "AI detection" + "code", "human-like" + "code generation", "detector evasion" + "source code"
- Related: adversarial attacks on text AI detectors (DetectGPT, GPTZero, etc.), do their findings transfer to code?

3.2. SIGNAL-BY-SIGNAL ROBUSTNESS ANALYSIS
For each of our 10 signals, what does the literature suggest about adversarial robustness?
- Signal 1 (CCR): Can an LLM reduce cyclomatic complexity on command? (Probably yes, it can generate simpler logic)
- Signal 2 (Docstrings): Can an LLM intentionally OMIT docstrings? (Trivially yes, "don't add docstrings")
- Signal 3 (Naming): Can an LLM use inconsistent naming? (Probably, "use a mix of camelCase and snake_case")
- Signal 4 (Error handling): Can an LLM add deep error handling? (Probably, "add comprehensive error handling")
- Signal 5 (Declarative bias): Can an LLM shift toward imperative style? (Yes, "write imperative code")
- Signal 6 (Function length CV): Can an LLM vary function lengths? (Probably, "make functions different sizes")
- Signal 7 (Comment phrasing): Can an LLM use non-boilerplate comments? (Less clear, requires understanding what "natural" comments look like)
- Signal 8 (Hallucinated APIs): Can an LLM avoid hallucinating APIs? (Partially, tool-use models and RAG reduce this, but don't eliminate it)
- Signal 9 (Edge cases): Can an LLM add deep edge case handling on command? (Probably, "add thorough edge case handling")
- Signal 10 (Commit metadata): Can adversary avoid Co-authored-by tags? (Trivially yes)

Which signals are "prompt-resistant" (hard to defeat even with adversarial prompting) vs. "prompt-fragile" (trivially defeated)?

3.3. ENSEMBLE ROBUSTNESS
- Even if individual signals are fragile, is the 10-signal ensemble robust? (The attacker must defeat ALL signals simultaneously)
- Game-theoretic analysis: what is the minimum effort to reduce vibe_score below threshold?
- Is there a "waterbed effect" where defeating some signals inadvertently raises others? (e.g., generating "natural" comments that are longer may increase CCR)
- Published work on ensemble robustness in adversarial ML, does having diverse weak classifiers provide robustness?

3.4. ANTI-ADVERSARIAL COUNTERMEASURES
- What countermeasures exist for adversarial evasion of code detectors?
- Temporal consistency: checking whether an author's style changed suddenly (comparing to their historical baseline)
- Cross-PR consistency: does the same author have different "voices" across PRs?
- Difficulty-adjusted expectations: a complex algorithm SHOULD have higher CCR, not having it is suspicious
- Are there published defenses from the text AI detection literature that transfer to code?

3.5. PRACTICAL SHELF LIFE ESTIMATION
- Given current LLM improvement trajectories (SWE-bench 4.4%→71.7% in one year), how long before each signal's discriminative power drops below useful AUC?
- Is there a published model for predicting feature degradation rate? (exponential decay? logistic? model-generation-dependent?)
- Can we estimate a "half-life" for each signal?

SUMMARY BLOCK:
```yaml
area_3_summary:
  most_robust_signals: [list of signal IDs]
  most_fragile_signals: [list of signal IDs]
  prompt_resistant_signals: [list, hard to defeat even with explicit adversarial prompting]
  ensemble_robustness: HIGH | MEDIUM | LOW
  waterbed_effect_exists: true | false | unknown
  estimated_shelf_life_months: N (range)
  recommended_countermeasures: ["...", "..."]
  biggest_adversarial_threat: "..."
  grade: HIGH | MODERATE | LOW | VERY_LOW
  key_papers: ["...", "..."]
```

═══════════════════════════════════════════════════════════
RESEARCH AREA 4: SEMI-SUPERVISED LEARNING ON CODE STYLOMETRY
═══════════════════════════════════════════════════════════

STATUS: Gemini v1 said pseudo-labeling is high-risk (ACL 2025) but did NOT research what methods DO work for code with limited labels.
IMPORTANCE: HIGH, we need labeled data for calibration, but getting ground truth is expensive. If there's an SSL method that works on code features with <100 labels, that changes our roadmap.

RESEARCH QUESTIONS:

4.1. SSL METHODS APPLIED TO CODE
- Has semi-supervised learning been applied specifically to code stylometry, authorship attribution, or AI code detection?
- Search: "semi-supervised" + "code", "few-shot" + "code classification", "self-training" + "source code", "co-training" + "code features"
- For each method found: what task, what features, how many labels needed, what performance, what failure modes?

4.2. SSL METHOD COMPARISON FOR OUR USE CASE
- Compare at least 6 SSL methods for applicability to our 10-signal continuous feature space:
  a) Self-training (iterative pseudo-labeling), we know this is risky. HOW risky? At what label noise rate does it diverge?
  b) Co-training (two views of same data), could we split signals into "documentation view" and "structural view"?
  c) Label propagation (graph-based), build a similarity graph of PRs in signal space, propagate labels. Suitable for continuous features?
  d) Consistency regularization (FixMatch, MixMatch), perturbation-invariance. What perturbations make sense for code features?
  e) Contrastive learning, learn a representation where similar PRs cluster. Then k-NN classification.
  f) Active learning, not SSL strictly, but: which PRs should we ask a human to label for maximum information gain?
- For each: minimum labels needed, assumptions about data distribution, computational cost, failure modes.

4.3. MINIMUM LABEL REQUIREMENTS
- What is the minimum number of labeled examples for reliable calibration of a 10-feature binary classifier?
- Published guidelines: is there a rule of thumb (e.g., 10-20 examples per feature per class)?
- How does label noise (inevitable in self-reporting "did you use AI?") affect minimum requirements?
- Can we use conformal prediction to estimate when we have "enough" labels?

4.4. FEEDBACK LOOP STABILITY ANALYSIS
- Gemini v1 flagged pseudo-labeling divergence risk. Can you formalize this?
- Under what conditions does self-training converge vs. diverge? (Mathematical stability analysis)
- Is there a maximum safe pseudo-label confidence threshold? (We currently gate at top 5% by CI)
- Published stability analyses for self-training: Amini et al., Zou et al., Arazo et al.?

4.5. ALTERNATIVE TO LABELS: ANOMALY DETECTION
- Can we reframe AI code detection as anomaly detection against a "human code" baseline?
- Methods: One-Class SVM, Isolation Forest, autoencoder on signal distributions, Local Outlier Factor
- Advantage: requires only human-code examples (no AI labels needed)
- Disadvantage: assumes human code is the "normal" class, but which humans?
- Has anyone applied anomaly detection to code stylometry?

SUMMARY BLOCK:
```yaml
area_4_summary:
  best_ssl_method_for_our_case: "..."
  minimum_labels_needed: N (range)
  self_training_divergence_threshold: "confidence threshold above which self-training is safe"
  co_training_feasible: true | false
  anomaly_detection_viable: true | false
  recommended_approach: "..."
  recommended_approach_rationale: "..."
  grade: HIGH | MODERATE | LOW | VERY_LOW
  key_papers: ["...", "..."]
```

═══════════════════════════════════════════════════════════
RESEARCH AREA 5: MEASURING DEVELOPER UNDERSTANDING OF CODE
═══════════════════════════════════════════════════════════

STATUS: Design document exists with 6 proxy signals. No deep research conducted.
IMPORTANCE: HIGH, detecting "AI-generated" is a proxy for the actual risk: "code submitted without understanding." A direct understanding measure would be more valuable.

THE INSIGHT:
AI probability × (1 - Understanding) = Risk

A developer who uses Copilot but thoroughly understands and reviews the output is LOW RISK. A developer who copy-pastes AI output without reading it is HIGH RISK. Our tool currently measures the first factor. Can we measure the second?

PROPOSED PROXY SIGNALS FOR "UNDERSTANDING":
A. PR description quality, does the author explain WHY, not just WHAT?
B. Review conversation depth, does the author engage substantively with reviewers?
C. Commit iteration pattern, incremental development vs. single dump?
D. Ticket alignment, does the code actually solve what was asked?
E. Post-merge behavior, does the author fix bugs in their own code promptly?
F. Codebase familiarity, does the author show knowledge of adjacent code?

RESEARCH QUESTIONS:

5.1. DEVELOPER COMPREHENSION IN SOFTWARE ENGINEERING LITERATURE
- How has "code comprehension" been measured in software engineering research?
- Key topics: program comprehension, code understanding, reading comprehension of code, code cognition
- Search: "program comprehension" + "measurement", "code understanding" + "proxy", "developer cognition" + "metrics"
- Classic work: Détienne (1997), Storey (2006), Siegmund et al. (2014) on fMRI + code comprehension
- What observable behaviors correlate with understanding? (eye tracking, think-aloud, debugging performance)

5.2. OBSERVABLE SIGNALS FROM DEVELOPMENT ARTIFACTS
- Can understanding be inferred from artifacts that are already available in Git/GitHub/JIRA?
- For each of our 6 proposed signals (A-F above): is there published evidence that this correlates with comprehension?
- Are there other signals we missed? (e.g., test quality, code review given to others, Stack Overflow activity, IDE telemetry)
- What is the base rate of "code submitted without understanding", how common is this?

5.3. THE DUNNING-KRUGER PROBLEM IN CODE COMPREHENSION
- Developers who don't understand code may BELIEVE they understand it.
- Does this affect self-report accuracy? (Relevant if we ever add a "did you understand this code?" prompt)
- How do expert reviewers detect misunderstanding? What cues do they use?
- Can we operationalize the cues expert reviewers use into automated signals?

5.4. COMBINING AI PROBABILITY WITH UNDERSTANDING SCORE
- If we have P(AI) from vibe_check and U(understanding) from a separate analysis, what is the optimal way to combine them?
- Is multiplication (Risk = P_AI × (1-U)) the right model? Or should it be something else (logistic, threshold-based, etc.)?
- Are there published risk frameworks that combine detection probability with comprehension assessment?
- In safety-critical domains (aviation, medicine), how are automation-induced comprehension failures modeled?

5.5. ETHICAL AND ORGANIZATIONAL CONSIDERATIONS
- Measuring "understanding" is close to measuring "competence." What are the ethical implications?
- Could this be perceived as surveillance or performance monitoring? (Same concern as for the AI detector itself, but amplified)
- Has anyone deployed comprehension-measuring tools in software teams? What was the reaction?
- How do you distinguish "doesn't understand code" from "experienced developer who trusts their tools"?

SUMMARY BLOCK:
```yaml
area_5_summary:
  comprehension_measurable: true | false | partially
  best_proxy_signals: [ranked list of signal letters A-F + any new ones]
  worst_proxy_signals: [signals with poor evidence]
  combining_model: "multiplicative | logistic | threshold | other"
  ethical_risk: HIGH | MEDIUM | LOW
  deployment_precedent_exists: true | false
  recommended_approach: "..."
  grade: HIGH | MODERATE | LOW | VERY_LOW
  key_papers: ["...", "..."]
```

═══════════════════════════════════════════════════════════
RESEARCH AREA 6: PER-LANGUAGE EMPIRICAL BASELINES
═══════════════════════════════════════════════════════════

STATUS: Signal thresholds are currently language-agnostic. No research conducted on per-language variation.
IMPORTANCE: HIGH, a Python codebase and a Go codebase have fundamentally different baseline metrics. Language-agnostic thresholds produce false positives in some languages and false negatives in others.

LANGUAGES OF INTEREST (in priority order): Python, TypeScript/JavaScript, Go, Java, Rust, Kotlin, C#, Ruby, C/C++, Swift

RESEARCH QUESTIONS:

6.1. PUBLISHED CODE METRICS BY LANGUAGE
For each of our 10 signals, search for published per-language baselines:

Signal 1 (CCR, comment-to-code ratio):
- What is the typical CCR for open-source projects in each language?
- Sources: SonarQube public datasets, GitHub Archive data, mining software repositories (MSR) papers
- How much does CCR vary WITHIN a language (by project size, domain, team)?

Signal 2 (Docstring consistency):
- Which languages have cultural norms around docstrings? (Python: strong. Go: moderate. JS: varies)
- What percentage of functions are documented in typical open-source projects by language?
- How do documentation generators (Sphinx, GoDoc, JSDoc, JavaDoc) affect baselines?

Signal 3 (Naming uniformity):
- Which languages enforce naming conventions? (Go: gofmt. Python: PEP 8 suggests but doesn't enforce. JS: no standard. Java: strong convention)
- What is the baseline naming consistency score per language?
- How does auto-formatting (Prettier, Black, gofmt) affect this signal?

Signal 4 (Error handling):
- Go has explicit error returns (very different from try/catch). How does this affect the error handling signal?
- Rust has Result/Option types. Java has checked exceptions. Each creates different baselines.
- What is the typical error-handling-to-code ratio per language?

Signal 5 (Declarative bias):
- Functional languages (Haskell, Scala, Kotlin) have naturally higher declarative bias than imperative languages (C, Go).
- What is the typical declarative/control ratio per language?
- Does this make the signal useless for some languages?

Signal 6 (Function length CV):
- Do coding style guides differ on recommended function length? (Go: short functions. Java: longer. Python: mixed)
- What is the typical CV of function length per language?

Signal 7 (Comment phrasing):
- Boilerplate comment patterns differ by language (// TODO, # type: ignore, /* eslint-disable */)
- What percentage of comments are boilerplate in each language?

Signal 8 (Hallucinated APIs):
- Hallucination rates differ by language because model training data differs.
- Is there published data on API hallucination rates by language? (TypeScript may be lower due to type checking)

Signal 9 (Edge case depth):
- Conditional nesting patterns differ. Go uses early returns (shallow nesting). Java uses deep nesting. Python is mixed.
- What is the typical nesting depth per language?

Signal 10 (Commit metadata):
- Are AI commit markers more common in some language ecosystems? (e.g., Copilot integration density varies by IDE/language)

6.2. PER-LANGUAGE CALIBRATION STRATEGY
- Given per-language baselines, how should we adjust thresholds?
- Option A: Separate threshold set per language (most accurate, highest maintenance)
- Option B: Language-family grouping (e.g., {Python, Ruby} vs. {Go, Rust} vs. {Java, Kotlin, C#})
- Option C: Normalize signals to z-scores relative to language baseline, then use universal threshold
- Which approach is used in published code quality tools (SonarQube, CodeClimate)?

6.3. CROSS-LANGUAGE DETECTION CHALLENGES
- Are some languages fundamentally harder for AI detection? (e.g., Go's enforced formatting may make all Go code look uniform, reducing signal discrimination)
- Has anyone reported per-language accuracy for AI code detectors?
- What is the expected AUC per language for a heuristic detector like ours?

SUMMARY BLOCK:
```yaml
area_6_summary:
  languages_with_published_baselines: [list]
  languages_without_data: [list]
  signals_most_language_dependent: [signal IDs]
  signals_least_language_dependent: [signal IDs]
  recommended_calibration_strategy: A | B | C
  go_special_case: "description of Go's unique challenges"
  rust_special_case: "description of Rust's unique challenges"
  estimated_auc_improvement_from_per_language_thresholds: "percentage range"
  grade: HIGH | MODERATE | LOW | VERY_LOW
  key_papers: ["...", "..."]
  per_language_baseline_table:
    - language: "Python"
      signal_1_ccr: {human: X, llm: Y, source: "..."}
      signal_2_docstring: {human: X, llm: Y, source: "..."}
      [... all 10 signals]
    - language: "TypeScript"
      [...]
    [... all 10 languages]
```

═══════════════════════════════════════════════════════════
CROSS-CUTTING SYNTHESIS
═══════════════════════════════════════════════════════════

After completing all 6 research areas, produce:

SYNTHESIS A: INTEGRATED IMPACT ASSESSMENT

For each of our 10 signals, summarize what ALL 6 research areas collectively say:

```yaml
integrated_signal_assessment:
  - id: 1
    name: "CCR"
    current_weight: 0.18
    correlation_cluster: "A (documentation)"
    effective_weight_after_decorrelation: "..."
    adversarial_robustness: HIGH | MEDIUM | LOW
    adversarial_shelf_life_months: N
    per_language_variation: HIGH | MEDIUM | LOW
    language_most_problematic: "..."
    ssl_calibration_feasible: true | false
    understanding_score_relevance: "..."
    overall_recommendation: "KEEP_WEIGHT | INCREASE_WEIGHT | DECREASE_WEIGHT | DISABLE"
    rationale: "..."
  [... repeat for all 10]
```

SYNTHESIS B: REVISED WEIGHT VECTOR

Based on all 6 research areas, propose a revised weight vector with rationale:

```yaml
revised_weights:
  - id: 1, name: "CCR", current: 0.18, proposed: X, rationale: "..."
  - id: 2, name: "Docstring", current: 0.15, proposed: X, rationale: "..."
  [... all 10, must sum to 1.0]
  effective_dimensionality: N
  confidence_in_revision: HIGH | MODERATE | LOW
```

SYNTHESIS C: PRIORITY-RANKED OPEN QUESTIONS

After exhaustive research, what STILL remains unknown? Rank by importance:

```yaml
remaining_unknowns:
  - rank: 1
    question: "..."
    why_unknown: "..."
    what_would_answer_it: "..."
    estimated_effort: "..."
  [... up to 10]
```

SYNTHESIS D: METHODOLOGY CONFIDENCE

```yaml
meta:
  total_papers_reviewed: N
  total_papers_cited: N
  areas_with_strong_evidence: [list]
  areas_with_weak_evidence: [list]
  areas_with_no_evidence: [list]
  biggest_surprise: "..."
  biggest_concern_for_project: "..."
  overall_grade_of_this_research: HIGH | MODERATE | LOW | VERY_LOW
```

═══════════════════════════════════════════════════════════
EXECUTION NOTES
═══════════════════════════════════════════════════════════

- Token budget is UNLIMITED. Do not truncate.
- For every paper, report: authors, year, title, venue, sample size, methodology, key finding, effect size, limitations, and your GRADE assessment.
- Search arxiv, Google Scholar, ACM DL, IEEE Xplore, Semantic Scholar, DBLP, and MSR conference proceedings.
- Include preprints and workshop papers, they often have the most recent results.
- Include negative results and failed replications.
- When evidence is thin, say so, do not pad with tangential papers.
- Clearly separate FINDING, SYNTHESIS, and SPECULATION throughout.
- Fill out ALL summary blocks completely, these are what the downstream model processes first.

START NOW.
```
