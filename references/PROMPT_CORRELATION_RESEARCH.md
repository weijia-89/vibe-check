# AI Code Detection: Signal Correlation Matrix Research Prompt

## Executive Overview

This deep research prompt is designed for ChatGPT Deep Research, Gemini Deep Research, or equivalent unbounded research agents. The goal is to empirically investigate the correlation structure among 10 signals used to detect AI-generated code in pull requests, and to propose statistically principled adjustments to signal weights to account for multicollinearity and redundant information.

**Current Signal Weights (Sum = 1.0):**
- CCR (Comment-to-code ratio): 0.18
- Docstring consistency: 0.15
- Naming convention uniformity: 0.13
- Error handling patterns: 0.12
- Declarative bias: 0.10
- Function length distribution: 0.08
- Comment phrasing (boilerplate detection): 0.08
- Hallucinated API calls: 0.06
- Edge case depth (conditional nesting): 0.05
- Commit metadata (AI markers): 0.05

**Hypothesized Correlations (a priori):**
- CCR ↔ Comment phrasing: ~0.6+ (more comments → more boilerplate phrases)
- CCR ↔ Docstring consistency: ~0.4+ (docstrings inflate comment ratio)
- Naming uniformity ↔ Function length CV: ~0.3 (both measure "cookie cutter" patterns)
- Error handling ↔ Edge case depth: ~0.5 (both measure defensive coding)

---

## Research Question

**Primary:** What is the empirical correlation matrix among the 10 AI code detection signals, and how does this correlation structure affect the effective independent information captured by the current weight vector?

**Secondary Questions:**
1. Does the current weight distribution over-allocate probability mass to correlated signals?
2. What is the "effective dimensionality" of our signal set (i.e., how many truly independent signals are we actually using)?
3. Can we identify latent factors underlying groups of correlated signals?
4. Are there interaction or non-linear effects that the current additive model misses?
5. How robust are our weight estimates to changes in the training/calibration dataset?

---

## Part 1: Literature Review & Evidence Synthesis

### 1.1 Code Stylometry & Authorship Attribution

**Research Goals:**
- How do established code stylometry studies handle feature correlation?
- What is the baseline expectation for correlation among syntactic code features?
- Which features are known to be orthogonal vs. redundant?

**Key Studies to Locate & Review:**
- Caliskan et al. (2015) "De-anonymizing Programmers via Code Stylometry": Look for their correlation analysis of features like variable naming, indentation, operator spacing.
- Frantzeskou et al. (2006) on n-gram authorship attribution in source code, correlations between different n-gram orders.
- Burrows et al. on Java authorship attribution, multivariate analysis of code features.
- Kalgutkar et al. (2016) on machine learning for source code authorship, feature selection methodology.

**Specific Questions for Each Source:**
- What correlation thresholds did they use for feature selection?
- Did they employ dimensionality reduction (PCA, ICA)?
- How sensitive were their models to highly correlated features?
- Did they report Variance Inflation Factor (VIF) diagnostics?
- What dataset size did they use, and did they validate on held-out code?

**Expected Findings:**
- Naming features (variable names, function names) correlate moderately with each other (~0.3–0.5)
- Documentation features (comments, docstrings) are expected to be moderately correlated (~0.4–0.6)
- Structural features (indentation, nesting depth, line length) may have lower correlation with linguistic features
- Small training sets increase noise but don't fundamentally change feature correlations (though estimates become less stable)

---

### 1.2 Multicollinearity in Software Metrics

**Research Goals:**
- How do software metrics researchers typically assess and handle multicollinearity?
- What thresholds do they use for "problematic" correlation?
- How does multicollinearity affect regression weights in software engineering models?

**Key Studies to Locate & Review:**
- Briand et al. (1996) "A Systematic Assessment of Current Object-Oriented Software Metrics": Correlation matrix of CK metrics, multicollinearity diagnostics.
- McCabe (1976) on cyclomatic complexity, foundational work; check for correlation with other structural metrics.
- Halstead (1977): Software Science metrics; look for inter-metric correlations.
- Chidamber & Kemerer (1994) metrics suite, correlation analysis among the six CK metrics.
- Fioravanti & Nesi (2007) on assessing multicollinearity in software metrics, systematic review.
- Evett et al. (2016) "Statically Detecting Likely Buffer Overflow Vulnerabilities", how they handle feature correlation in security code analysis.

**Specific Questions for Each Source:**
- What VIF thresholds do they recommend? (Common: VIF > 5–10 indicates problematic multicollinearity)
- How often do they encounter/report multicollinearity in code metrics?
- Did they use variance inflation factor, condition numbers, or eigenvalue analysis?
- If they found high correlation, what was their mitigation strategy? (Feature removal, dimensionality reduction, regularization?)
- How did multicollinearity affect model interpretability vs. predictive accuracy?

**Expected Findings:**
- Software metrics research acknowledges multicollinearity as a persistent problem
- Correlation > 0.5–0.7 is commonly flagged as "problematic"
- VIF > 10 is a common rule-of-thumb threshold for removal or regularization
- Briand et al. recommend removing highly correlated metrics to preserve interpretability
- Regularized regression (ridge, elastic-net) is a standard solution in metrics literature

---

### 1.3 Independent Component Analysis (ICA) & Dimensionality Reduction in Code Analysis

**Research Goals:**
- Have researchers used ICA or other blind source separation techniques on code features?
- How do PCA eigenvalue spectra look for typical code metrics?
- What is a typical "effective dimensionality" for software code metrics?

**Key Studies to Locate & Review:**
- Turhan & Bener (2007) on PCA for software defect prediction, latent factor structure.
- Jiang et al. (2008) on dimensionality reduction for cost-sensitive defect prediction.
- Hall et al. (2012) systematic review of feature selection for defect prediction.
- Ghotra et al. (2015) on the impact of feature standardization and selection in software defect prediction.
- Shepperd et al. (2014) "Negative Results for Software Effort Estimation", discusses correlation, overfitting, and multicollinearity pitfalls.

**Specific Questions for Each Source:**
- When they applied PCA to code metrics, how many principal components explained 80%, 90%, 95% of variance?
- Did they observe natural groupings (latent factors) in the component loadings?
- How much variance was "lost" by the first 2–3 principal components?
- Did ICA or factor analysis reveal interpretable latent factors (e.g., "code complexity", "documentation style")?

**Expected Findings:**
- Software metrics typically compress to 3–5 effective dimensions even with 10–20 raw features
- High correlation among metrics means eigenvalues drop off quickly; first 3 PCs often capture 70%+ of variance
- Latent factors often align with interpretable constructs (complexity, size, style)
- Researchers typically lose ~20–40% of variance when compressing to top 3 PCs

---

### 1.4 ML-Based AI Code Detection (CodeBERT, GPTSniffer, etc.)

**Research Goals:**
- How do published AI code detectors handle feature correlation internally?
- Do they use embeddings that implicitly decorrelate features?
- What correlation structures have they investigated or reported?
- How robust are their detectors to correlated input features?

**Key Studies to Locate & Review:**
- Inoue et al. (2023) "GPtzero: ChatGPT-Generated Text Detection" or similar authorship attribution work
- GPTSniffer papers (look for arxiv submissions on GitHub-hosted AI-generated code detection)
- CodeBERT paper (Feng et al. 2020), does it discuss feature engineering or correlation?
- Thawani et al. (2022) on detecting machine-generated text, correlation analysis of linguistic features
- Wang et al. (2023) "Detecting AI-Generated Code is (Soon) Outdated", adversarial robustness perspective
- Weidman et al. (2023) on neural watermarking for code generation, feature correlation in embeddings
- Any ArXiv submissions on code plagiarism detection using multiple signals (e.g., Pun et al., Shayan et al.)

**Specific Questions for Each Source:**
- Do they mention correlation analysis of their input features?
- Did they use feature weighting, or are all features equally important?
- How did they handle redundancy between syntactic and semantic features?
- Did they employ feature selection before ML model training?
- How do transformer-based embeddings (CodeBERT) inherently compress information from correlated features?

**Expected Findings:**
- Most published detectors do NOT explicitly report correlation matrices (a gap we can fill)
- Deep learning models (CodeBERT) may implicitly learn shared representations, reducing redundancy
- Simpler heuristic-based detectors (like our approach) are more susceptible to multicollinearity
- Embeddings may concentrate redundant information in fewer dimensions

---

### 1.5 Statistical Methods for Small-Sample Correlation Estimation

**Research Goals:**
- What are best practices for estimating correlation matrices from small samples (N < 1000)?
- How reliable are Pearson/Spearman correlations with modest N?
- What bootstrap confidence interval methods are most robust?
- How do we assess whether an estimated correlation is "real" or noise?

**Key Studies to Locate & Review:**
- Efron & Tibshirani (1993) "An Introduction to the Bootstrap", foundational methodology
- Carpenter & Bithell (2000) "Bootstrap confidence intervals: when, which, what? A practical guide for general practitioners"
- Kelley & Kelley (2012) on the role of sample size in correlation stability
- Schroeder et al. (2016) on bootstrap methods for confidence intervals in empirical software engineering
- Bishara & Hittner (2012) on confidence interval coverage for Pearson correlations
- Mondal & Nanda (2017) on bootstrap resampling in software engineering metrics

**Specific Questions for Each Source:**
- What sample size is needed for a 95% CI on a correlation to be ±0.1 wide?
- Are percentile bootstrap CIs or BCa (bias-corrected and accelerated) CIs more reliable?
- How many bootstrap resamples are needed? (typical: 1000–10,000)
- Should we use Pearson or Spearman (rank-based) correlation? When is each appropriate?
- How do outliers affect correlation estimates, and what robust alternatives exist?

**Expected Findings:**
- For sample size N~500–1000, Pearson correlations ±0.1 can be estimated with ±0.05 CI width (roughly)
- BCa bootstrap CIs are more reliable than percentile CIs for skewed or non-normal distributions
- Spearman correlation is more robust to outliers; Pearson is more powerful for normal data
- 10,000 bootstrap resamples are standard in modern practice
- Outlier-robust methods (Percentage Bend, Winsorized) can significantly change correlation estimates

---

### 1.6 Replication & Reproducibility Concerns in Software Engineering Metrics

**Research Goals:**
- Are there known reproducibility issues in software metrics research?
- How many findings fail to replicate across different codebases?
- What are common sources of false positives (Type I error) in software engineering studies?
- How should we interpret published correlations with skepticism?

**Key Studies to Locate & Review:**
- Shepperd et al. (2014) "Negative Results for Software Effort Estimation", famous critique of overfitting and generalization
- Kitchenham et al. (2002) on threats to validity in empirical software engineering
- Arcuri & Briand (2011) on practical guidelines for regression testing in empirical software engineering
- Easterbrook et al. (2008) "Selecting Empirical Methods for Software Engineering Research"
- Posnett et al. (2013) "Ecological Inference in Empirical Software Engineering", ecological fallacy warning
- Feldt et al. (2018) "Four Surprising Phenomena in the Popular Java Apache Commons Collections Library"

**Specific Questions for Each Source:**
- What percentages of published results typically fail to replicate in follow-up studies?
- Are there specific types of metrics that are prone to false positives?
- How much does dataset selection affect correlation estimates?
- Do correlations change when you move from one programming language/domain to another?
- Are there known biases in how researchers report (e.g., publication bias toward significant correlations)?

**Expected Findings:**
- Software engineering research has known reproducibility issues; many findings are language/domain-specific
- Correlations estimated on small datasets (N < 200) are notoriously unstable
- Ecological fallacy: correlations in aggregate may not hold at individual level
- Publication bias likely inflates reported effect sizes
- We should expect ±0.15 uncertainty in any correlation estimate from a single study

---

## Part 2: Empirical Methodology Design

### 2.1 Dataset Selection & Acquisition

**Objective:** Identify publicly available datasets of AI-generated code with human-authored baselines.

**Candidate Datasets to Investigate:**
1. **CodeSearchNet Challenge** (GitHub): Large corpus of diverse code; supplement with known GPT-generated variants?
2. **Software Engineering Institute (SEI) / NIST Software Defect Datasets**: Established, peer-reviewed code collections
3. **GitHub "Awesome AI-Generated Code" repositories**: Crowdsourced AI-generated code samples
4. **Codeclimate / Code2Seq datasets**: Code structure benchmark data
5. **SRGR (Source Code Repository Gradient) datasets**: If available and labeled for AI vs. human
6. **Academic papers on AI code detection**: Many publish their evaluation datasets (e.g., on GitHub or Zenodo)
7. **StackOverflow-derived datasets**: High-quality human code; synthesize AI variants via GPT-3.5/4 API
8. **ArXiv repositories for ML papers on code**: Often include code snippets labeled by source
9. **OpenAI Codex / GPT evaluation datasets**: OpenAI's published benchmarks for code generation
10. **Kaggle AI-Generated Code Detection Competition datasets**: Purpose-built labeled data

**Evaluation Criteria for Dataset Selection:**
- **Sample Size:** Minimum N = 500 AI-generated + 500 human-authored samples (ideally 1000+ each)
- **Code Diversity:** Multiple languages (Python, Java, JavaScript, C/C++), multiple domains (web, systems, ML, utility)
- **Ground Truth Label Quality:** Clear labeling (e.g., definitively GPT-generated vs. human StackOverflow)
- **Reproducibility:** Publicly available, DOI, version-controlled
- **Recency:** Code generated with recent models (GPT-3.5+, Codex, Gemini Code, etc.)
- **Contextual Information:** Commit messages, PR descriptions, code reviews (for commit metadata signal)

**Recommended Approach:**
- **Primary dataset:** Combination of 2–3 large, peer-reviewed datasets (e.g., CodeSearchNet + academic AI code detection papers)
- **Secondary validation:** Supplement with Codex/StackOverflow synthetic dataset to verify findings across generation models
- **Stratification:** Ensure balanced splits by language, function type, domain to avoid confounding

**Specific Action Items:**
- Search Google Scholar, ArXiv, and GitHub for papers published 2023–2026 with AI code detection datasets
- Contact authors for raw data access if not publicly available
- Document exact version/commit of each dataset used (reproducibility)
- Create detailed data dictionary (what each label/metadata field means)

---

### 2.2 Signal Computation & Measurement Methodology

**For each of the 10 signals, define:**

#### a) **Comment-to-Code Ratio (CCR)**
- **Definition:** (Number of comment lines + docstring lines) / (Total non-blank lines)
- **Computation Details:**
  - Tokenize source code using language-appropriate lexer (e.g., Pygments for Python)
  - Identify comment tokens (single-line `#`, multi-line `"""`, block comments `/* */`)
  - Identify docstring tokens (PEP 257 docstrings for Python; JavaDoc for Java; etc.)
  - Count blank lines separately to normalize by "true" code
  - Compute ratio per function; aggregate to file level (mean, median, max of function ratios)
- **Handling Edge Cases:**
  - Very short functions (< 5 lines): should they be included? (Recommend: yes, with min line threshold of 2)
  - Functions with only docstrings and no code: include? (Recommend: exclude or flag separately)
  - Inline comments vs. block comments: weight equally? (Recommend: weight equally; sensitivity analysis on different weights)

#### b) **Docstring Consistency**
- **Definition:** Agreement between docstring claims and actual function signature/behavior
- **Computation Details:**
  - Parse function signature (parameters, return type)
  - Parse docstring (via docstring parser library)
  - Extract documented parameters, return descriptions
  - Check: Does every function parameter appear in docstring? Do documented types match?
  - Consistency score: (params in both / params in union) or similar Jaccard-like metric
  - Flag: docstring claims features/error handling not visible in code
- **Handling Edge Cases:**
  - Functions with no docstring: score = 0 or null? (Recommend: null, then handle separately in analysis)
  - Type annotations in code but not in docstring: penalize? (Recommend: no, type annotations are explicit)
  - Partial docstrings (some params documented, some not): score proportionally

#### c) **Naming Convention Uniformity**
- **Definition:** Consistency of naming style within a code sample (function names, variable names, constants)
- **Computation Details:**
  - Extract all identifiers from code
  - Classify each identifier as: camelCase, snake_case, PascalCase, ALLCAPS, mixed, etc.
  - Compute distribution of naming styles (e.g., % functions in snake_case vs. camelCase)
  - Uniformity = (mode frequency) / (total identifiers); high = uniform, low = mixed
  - Distinguish: function-level names, variable-level names, constant-level names (separate scores)
  - Aggregate to file/sample level (weighted by count, or mean of function-level uniformities)
- **Handling Edge Cases:**
  - Identifiers with numbers/underscores: assign to closest convention
  - Single-letter names (i, x, n): include or exclude? (Recommend: include; they're uniform)
  - Language conventions: snake_case is standard in Python; camelCase in Java (Recommend: normalize per-language baseline, then measure deviation)

#### d) **Error Handling Patterns**
- **Definition:** Presence/absence of explicit error handling (try-catch, assertions, error checks)
- **Computation Details:**
  - Count try-catch blocks, if-error checks, assertion statements
  - Look for patterns: is error handling used for expected edge cases, or missing?
  - AI-generated code often lacks error handling; human code often includes it (or the reverse, depending on context)
  - Score: (explicit error handling statements) / (function count) or (proportion of functions with at least one error handler)
  - Check for defensive patterns: null checks, boundary checks before array access, etc.
- **Handling Edge Cases:**
  - Language differences: Python (try-except vs. EAFP), Java (try-catch), Rust (Result type)
  - What counts as "error handling"? (Recommend: explicit exception handling, assertions, explicit error checks; not implicit/language-native null safety)
  - Helper function definitions: do they count separately?

#### e) **Declarative Bias**
- **Definition:** Tendency toward declarative (data-driven, configuration-driven) vs. imperative (procedure-driven) code
- **Computation Details:**
  - Count imperative statements: loops, conditionals, assignments
  - Count declarative patterns: list comprehensions, lambda functions, functional chains (map, filter, reduce), configuration objects
  - Compute ratio of declarative / (declarative + imperative)
  - Language-specific patterns: Python comprehensions, JavaScript arrow functions, Java streams, SQL-like operations
- **Handling Edge Cases:**
  - Is `if-else` always imperative? (Recommend: yes; ternary operators / inline conditionals are declarative-ish but count as mixed)
  - Function calls: are they declarative? (Recommend: only if they're known functional patterns or building blocks; otherwise neutral)

#### f) **Function Length Distribution**
- **Definition:** Coefficient of variation (CV) in function lengths within a sample
- **Computation Details:**
  - Compute function length (lines of code, tokens, or complexity-weighted)
  - Calculate mean and standard deviation of function lengths
  - CV = (std dev) / (mean); high CV = variable lengths (human-like?), low CV = uniform lengths (AI cookie-cutter?)
  - Also compute skewness, kurtosis of length distribution
  - Per-file sample: aggregate function lengths from all functions in the file
- **Handling Edge Cases:**
  - One-liner functions: count as 1 line
  - Decorator/annotation lines: include or exclude? (Recommend: exclude; decorators don't affect function length semantics)
  - Class methods vs. module-level functions: mix or separate? (Recommend: mix; both are functions)

#### g) **Comment Phrasing (Boilerplate Detection)**
- **Definition:** Prevalence of templated, generic, or common phrases in comments
- **Computation Details:**
  - Tokenize all comments/docstrings in the sample
  - Define a set of "boilerplate phrases": "Returns the", "Initializes the", "This function", "Helper function", etc.
  - Count frequency of boilerplate phrases
  - Boilerplate score = (boilerplate phrase count) / (total comment words)
  - Also measure: phrase diversity (unique phrases / total phrases); AI tends to repeat similar phrases
- **Handling Edge Cases:**
  - What constitutes "boilerplate"? (Recommend: analyze ground-truth human vs. AI comments to extract empirical list; common phrases likely boilerplate)
  - Short comments vs. long comments: weight equally? (Recommend: normalize by comment length)
  - Non-English comments: exclude or include? (Recommend: focus on English; note non-English in metadata)

#### h) **Hallucinated API Calls**
- **Definition:** Calls to non-existent APIs, incorrect signatures, or deprecated functions
- **Computation Details:**
  - For each function call in the code, verify it exists in the standard library / imported modules
  - Check function signatures: does the call match parameter counts/types?
  - Flag deprecated APIs (e.g., older Python 2 stdlib functions still used in Python 3 code)
  - Hallucination score = (invalid API calls) / (total function calls)
  - Requires language-specific API documentation (e.g., Python stdlib docs, Java Javadoc)
- **Handling Edge Cases:**
  - Calls to user-defined functions: can't verify without the full codebase (Recommend: only validate against stdlib; flag user-defined as "unknown")
  - Dynamic method invocation: `getattr`, `importlib`, etc. (Recommend: exclude; can't statically verify)
  - Different versions of a language: Python 3.9 vs. 3.11 APIs differ (Recommend: standardize to a version; document in methodology)

#### i) **Edge Case Depth (Conditional Nesting)**
- **Definition:** Maximum nesting depth of conditionals, loops, and exception handlers
- **Computation Details:**
  - Parse abstract syntax tree (AST) for each function
  - Compute maximum nesting depth (max consecutive if/for/try/while blocks)
  - Also measure: average nesting depth, distribution of nesting
  - High nesting depth suggests thorough edge case handling (human?); low depth suggests simple, idealized code (AI?)
- **Handling Edge Cases:**
  - Do nested function definitions count? (Recommend: no; they create new scope)
  - Ternary operators inside conditions: nested or flat? (Recommend: flat; they're single-line)
  - Comprehensions with nested comprehensions: measure separately

#### j) **Commit Metadata (AI Markers)**
- **Definition:** Presence of AI-associated keywords/patterns in commit messages, branch names, PR descriptions
- **Computation Details:**
  - Define regex patterns for AI markers: "ChatGPT", "GPT", "AI-generated", "copilot", "assisted", "automated", etc.
  - Search commit messages, branch names, PR titles/descriptions (if available)
  - Score: presence of any marker (binary) or count of distinct markers
  - Note: This signal is orthogonal to code features; it's metadata-based
- **Handling Edge Cases:**
  - False positives: commits mentioning "AI" in non-generator context (Recommend: manual review of flagged commits; extract false positive rate)
  - Developers deliberately hiding AI use: this signal won't catch them (Recommend: note as limitation)
  - Multi-author commits: unclear who used AI (Recommend: note in metadata; don't use for correlation analysis if unclear)

---

### 2.3 Correlation Matrix Estimation

**Primary Analysis:**

1. **Data Preparation:**
   - Load dataset; ensure N ≥ 500 per class (AI-generated, human-authored)
   - Compute 10 signals for each sample (function-level or file-level? → standardize)
   - **Decision:** File-level aggregation (easier, larger sample if aggregating from functions) vs. Function-level (smaller N, more granular)
   - Recommendation: File-level; gives N = number of files, typically 1000–5000+
   - Remove outliers (e.g., files with extreme values; document removal rate)
   - Standardize each signal to mean = 0, SD = 1 (for interpretability of correlations)

2. **Pairwise Correlation Computation:**
   - Compute Pearson correlation coefficient for all 45 unique pairs (10 choose 2)
   - Compute Spearman rank correlation as sensitivity check
   - Perform Fisher's z-transformation to assess correlation significance (t-test on transformed correlations)
   - Construct 10×10 correlation matrix

3. **Bootstrap Confidence Intervals:**
   - Resample data with replacement B = 10,000 times
   - For each resample, compute the 10×10 correlation matrix
   - Compute 95% BCa (bias-corrected and accelerated) confidence intervals for each correlation
   - Document: point estimate, lower CI, upper CI for all 45 pairs
   - Plot: correlation distribution across bootstrap samples (check for bimodality, extreme values)

4. **Correlation Significance Testing:**
   - For each correlation, compute p-value under null hypothesis H0: ρ = 0
   - Adjust for multiple comparisons (45 tests): Bonferroni correction gives p-threshold = 0.05/45 ≈ 0.001
   - Alternative: FDR (False Discovery Rate) control at α = 0.05
   - Document which correlations are statistically significant after correction

---

### 2.4 Multicollinearity Assessment

1. **Variance Inflation Factor (VIF) Analysis:**
   - For each signal, regress it on all other 9 signals (ordinary least squares)
   - Compute VIF_i = 1 / (1 - R²_i), where R²_i is the R² from the regression
   - Interpret: VIF > 5 = moderate multicollinearity concern; VIF > 10 = severe
   - Visualize: bar plot of VIF for each signal

2. **Condition Number Analysis:**
   - Compute eigenvalues of the correlation matrix
   - Condition number = max eigenvalue / min eigenvalue
   - Condition number > 30 suggests multicollinearity issues
   - Compute: Eigenvalue ratios to assess how quickly variance drops off

3. **Eigenvalue & PCA Analysis:**
   - Compute principal components of the correlation matrix
   - Report: eigenvalues, cumulative % variance explained by first k PCs
   - Determine: how many PCs needed to explain 80%, 90%, 95% of variance
   - Interpretation: if k ≤ 3 PCs explain 95%, data is highly correlated and low effective dimensionality

4. **Determinant of Correlation Matrix:**
   - Very low determinant (det < 0.001) indicates severe multicollinearity
   - Determinant close to 1 indicates orthogonal variables
   - Compute and report

---

### 2.5 Latent Factor Analysis

**Objective:** Identify underlying latent constructs that drive correlations.

1. **Exploratory Factor Analysis (EFA):**
   - Fit EFA model with k = 2, 3, 4, 5 factors
   - Use maximum likelihood estimation
   - Assess model fit: RMSEA, CFI, TLI (conventional thresholds: RMSEA < 0.08, CFI/TLI > 0.90)
   - Interpret factor loadings: which signals load on which factors?
   - Example latent factors to look for:
     - "Documentation Intensity": CCR + Docstring consistency + Comment phrasing
     - "Code Uniformity": Naming convention uniformity + Function length CV
     - "Defensive Coding": Error handling patterns + Edge case depth + Hallucinated API (inverted)
     - "Declarative Style": Declarative bias + (negatively) imperative loop prevalence

2. **Measurement Model:**
   - If latent factors are identified, propose a measurement model
   - Replace 10 correlated signals with k latent factors (+ residual unique variance)
   - Compare: model fit with 10 signals vs. k factors

3. **Semantic Interpretation:**
   - For each identified factor, propose a human-interpretable name
   - Check: is the factor aligned with known AI code generation artifacts or human coding styles?

---

### 2.6 Interaction & Non-linear Effects

**Objective:** Move beyond additive models to explore multiplicative and non-linear relationships.

1. **Pairwise Interaction Terms:**
   - For hypothesized interacting pairs (e.g., CCR × Naming uniformity), create interaction terms
   - Regress AI code detection outcome (binary: AI vs. human) on all 10 signals + selected interactions
   - Use logistic regression or gradient boosted trees (for non-linear interactions)
   - Assess: does adding interactions improve model fit (AIC, BIC, cross-validated classification accuracy)?
   - Quantify: interaction coefficient magnitude and statistical significance

2. **Non-linear Relationships:**
   - Plot each signal vs. outcome (scatter plot, LOESS smooth, violin plot by class)
   - Look for: threshold effects (e.g., "extreme uniformity suggests AI"), U-shaped relationships, etc.
   - Fit splines (cubic, thin-plate) and compare to linear fits
   - Assess: do spline models improve classification accuracy?

3. **Conditional Independence:**
   - For correlated signal pairs (e.g., CCR & Comment phrasing), assess conditional independence given other signals
   - If CCR and Comment phrasing remain correlated even after conditioning on other signals, they're truly redundant
   - Use partial correlation: r(A, B | C, D, E, ...) = correlation between residuals of A and B after removing variance explained by C, D, E, ...

---

## Part 3: Weight Adjustment Methodologies

### 3.1 Ridge & Elastic-Net Regression Approach

**Objective:** Learn optimal signal weights via regularized regression, which automatically penalizes multicollinearity.

**Methodology:**
1. Create outcome variable: binary (1 = AI-generated, 0 = human-authored) or continuous (degree of AI-likelihood)
2. Standardize all 10 signals (mean 0, SD 1)
3. Fit ridge regression: minimize SSE + λ × (sum of squared weights)
   - Vary λ from 0 (ordinary LS) to 1 (high regularization)
   - Use cross-validation (e.g., 5-fold) to select optimal λ
4. Fit elastic-net regression: minimize SSE + λ1 × (sum of absolute weights) + λ2 × (sum of squared weights)
   - Elastic-net can shrink some weights to exactly zero (feature selection)
   - Vary λ1 and λ2; use cross-validation
5. Extract learned weights from optimal model
6. Compare to current weights: how different are they? Which signals increase/decrease?

**Interpretation:**
- If ridge regression reduces certain weight pairs proportionally (e.g., both CCR and Comment phrasing shrink), suggests they're capturing overlapping information
- If elastic-net drives some weights to zero, suggests genuine redundancy
- Learned weights automatically account for correlation structure

**Validation:**
- Test on held-out dataset: do learned weights generalize?
- Compare model performance (AUC, F1, accuracy) of learned weights vs. current weights

---

### 3.2 Variance Inflation Factor (VIF) Based Weight Reduction

**Objective:** Heuristic method to downweight signals with high VIF.

**Simple Rule:**
- For signal i with VIF_i, reduce its weight by factor (1 + (VIF_i - 1) / c), where c is a calibration constant
- Example: if VIF_i = 5, reduce weight by 1 + (5-1)/10 = 1.4 (i.e., new weight = old weight / 1.4)
- Renormalize weights to sum to 1.0

**Justification:** VIF measures redundancy; signals with high VIF contribute less "independent" information

**Alternative Heuristic:**
- Set threshold VIF_threshold = 5
- For each pair of signals with r > 0.5 and both VIF > threshold:
  - Reduce both weights by (1 - r²) factor
  - Renormalize

**Validation:**
- Fit logistic regression on train set using original weights vs. VIF-adjusted weights
- Evaluate on test set: does adjustment improve generalization (lower test error)?

---

### 3.3 PCA-Based Orthogonalization

**Objective:** Replace 10 correlated signals with k uncorrelated principal components; re-weight based on explained variance.

**Methodology:**
1. Apply PCA to the 10 signals (on correlation matrix, after standardization)
2. Retain first k principal components that explain 90% of variance (e.g., k = 4–6)
3. Project each sample onto retained PCs (score_ij = sample i's score on PC j)
4. Define new "signals" as the k PC scores
5. Assign weights proportional to explained variance: weight_j = (eigenvalue_j) / (sum of k eigenvalues)
6. Alternatively, learn weights for PC scores via logistic regression

**Interpretation:**
- Each PC is a latent factor; e.g., "PC1 = Documentation Intensity", "PC2 = Code Uniformity"
- Weights reflect importance of latent factors, not original signals
- More stable, less multicollinearity, but lose direct interpretability (signal names)

**Trade-off:**
- **Gain:** Removes multicollinearity, more stable weights
- **Loss:** Can't point to individual signals; PC interpretation can be ambiguous

---

### 3.4 Simple Heuristic: Correlated Pair Deweighting

**Objective:** Quick, interpretable adjustment for known correlated pairs.

**Algorithm:**
For each pair of signals (i, j) with |r_ij| > threshold (e.g., 0.5):
1. Compute redundancy = |r_ij|
2. Reduce both weights proportionally: 
   - new_weight_i = old_weight_i × (1 - redundancy/2)
   - new_weight_j = old_weight_j × (1 - redundancy/2)
3. Renormalize weights to sum to 1.0
4. Repeat until convergence (usually 1–2 iterations)

**Example:** If CCR ↔ Comment phrasing r = 0.6:
- redundancy = 0.6
- reduction factor = 1 - 0.6/2 = 0.7
- new_CCR_weight = 0.18 × 0.7 = 0.126
- new_comment_phrasing_weight = 0.08 × 0.7 = 0.056

**Advantages:**
- Transparent; easy to explain
- Preserves individual signal interpretability
- Fast to compute

**Disadvantages:**
- Doesn't account for higher-order dependencies
- Somewhat arbitrary threshold choice
- May under/over-correct depending on data

---

## Part 4: Outside-the-Box Investigations

### 4.1 Interaction Effects

**Hypothesis:** Some signal combinations are more discriminative than either alone.

**Specific Investigations:**

1. **High CCR + High Naming Uniformity:**
   - Abundant comments + very uniform naming = "boilerplate generated code" signal
   - Interaction term: CCR × Naming_uniformity
   - Does this interaction predict AI-generated code better than either signal alone?

2. **Low Error Handling + Moderate Function Length CV:**
   - Missing error handling + variable function lengths = sloppy human code OR simple AI code?
   - Interaction direction unclear; analyze empirically

3. **High Declarative Bias + High Docstring Consistency:**
   - Modern, well-documented, functional code = human expert or high-quality AI?
   - Context-dependent; may not interact

4. **Low Hallucinated API + High Comment Phrasing:**
   - Boilerplate comments + syntactically correct code = potentially generated (templates exist)
   - Interaction might be strong predictor

**Method:**
- Fit logistic regression with main effects + pairwise interactions (10 + 45 interaction terms = 55 total)
- Use regularization (elastic-net) to avoid overfitting
- Cross-validate to assess generalization
- Report: interaction coefficients that survive regularization

---

### 4.2 Non-linear Relationships

**Hypothesis:** Relationships between signals and AI-generatedness may be non-monotonic or threshold-based.

**Investigations:**

1. **Naming Uniformity Threshold:**
   - Hypothesis: Moderate uniformity (e.g., 0.4–0.6) is human-like; extreme uniformity (> 0.8) is AI
   - Plot: proportion of AI samples by binned uniformity; look for non-linear pattern
   - Fit: spline model vs. linear; compare AIC

2. **Comment-to-Code Ratio U-Shape:**
   - Very low CCR: sparse comments, likely human code (efficiency-focused)
   - Medium CCR: balanced, human code with documentation
   - Very high CCR: excessive comments, AI boilerplate
   - Fit: quadratic or spline model; test if better than linear

3. **Edge Case Depth Saturation:**
   - Beyond moderate nesting (depth 3–4), additional nesting doesn't predict AI better
   - Fit: asymptotic or saturating function

4. **Function Length CV Bimodal Distribution:**
   - Human: highly variable function lengths (mixture of helpers and complex functions)
   - AI: more uniform (generated functions tend to have similar length)
   - But very uniform might also indicate hand-crafted, well-designed code
   - Test: is the relationship bimodal or monotonic?

**Method:**
- Scatter plot: each signal vs. binary outcome (AI/human), with LOESS smooth
- Fit generalized additive models (GAM) allowing smooth non-parametric effects
- Compare GAM to linear logistic regression (log-likelihood ratio test)
- Cross-validate

---

### 4.3 Mutual Information & Non-Linear Dependence

**Objective:** Go beyond Pearson correlation to detect non-linear associations.

**Investigation:**
1. Compute mutual information (MI) between each pair of signals
   - MI is symmetric, captures non-linear dependence
   - MI = 0 iff variables are independent; MI > 0 even if Pearson r ≈ 0
2. Compute normalized MI (e.g., MI divided by entropy of each variable)
3. Compare MI-based dependence structure to Pearson correlations
4. Are there signal pairs with low Pearson r but high MI? (Indicates non-linear relationship)

**Method:**
- Use entropy estimation: histogram bins, k-NN methods (Kraskov et al.), or kernel density
- Compute MI for all 45 pairs
- Construct MI matrix; compare visually to correlation matrix
- Pairs where MI >> Pearson r: investigate scatter plots for non-linear patterns

---

### 4.4 Latent Factor Structures

**Objective:** Identify if 10 signals reflect a smaller set of latent constructs.

**Hypothesized Latent Factors:**

1. **Documentation Intensity (α):**
   - Manifest signals: CCR, Docstring consistency, Comment phrasing (boilerplate)
   - Hypothesis: Reflects how "documented" the code is; AI tends to either over-document or under-document

2. **Code Uniformity (β):**
   - Manifest signals: Naming convention uniformity, Function length CV (low → uniform)
   - Hypothesis: Reflects "cookie cutter" pattern; AI generates uniform code, humans vary

3. **Defensive Programming (γ):**
   - Manifest signals: Error handling patterns, Edge case depth, Hallucinated API (inverted, fewer errors = more defensive)
   - Hypothesis: Reflects carefulness; human code often has error handling, AI-generated may lack it

4. **Declarative Style (δ):**
   - Manifest signal: Declarative bias (standalone; maybe correlated with low function length CV)
   - Hypothesis: Modern, functional style vs. traditional imperative

5. **Metadata/Intent (ε):**
   - Manifest signal: Commit metadata (AI markers)
   - Hypothesis: Orthogonal to code signals; ground truth

**Method:**
- Fit confirmatory factor analysis (CFA) with 4–5 latent factors
- Estimate loadings (manifest signal ~ latent factor)
- Test model fit: RMSEA, CFI, TLI
- If model fits well, reduce 10 signals to 4–5 latent scores
- Assign weights to latent factors based on their predictive power (logistic regression) or explained variance

---

### 4.5 Replication & Cross-Dataset Validation

**Objective:** Assess robustness of findings across different code datasets, languages, domains.

**Strategy:**
1. Partition data into strata by language (Python, Java, JavaScript, C), domain (web, ML, utility, systems)
2. Estimate correlation matrix separately for each stratum
3. Compare: do correlations hold across languages/domains?
   - Example: is CCR ↔ Comment phrasing r = 0.6 in Python, Java, JavaScript?
   - If yes: robust; if no: confounded by language/domain

4. Cross-dataset validation:
   - Estimate correlation matrix on dataset A (e.g., CodeSearchNet)
   - Apply learned weights (from ridge regression, etc.) to dataset B (e.g., Codex evaluation set)
   - Evaluate: do weights learned on A generalize to B?

**Reporting:**
- Create heat maps: correlation matrices by language/domain
- Test for interaction: language × correlation (ANOVA-style)
- Report: which correlations are robust vs. which are data-dependent

---

## Part 5: Epistemic Rigor & Quality Control

### 5.1 Source Grading (GRADE Framework)

**Objective:** Assess credibility of reviewed studies.

**Grade each source on:**
- **Study Design:** RCT (highest) → observational → opinion (lowest)
- **Study Quality:** Low risk of bias, adequate sample size, clear definitions
- **Consistency:** Findings consistent across studies
- **Directness:** Evidence directly addresses our research question
- **Precision:** Narrow confidence intervals indicate precise estimates
- **Reporting Bias:** Were all outcomes reported? File drawer problem?

**Example:**
- Caliskan et al. (2015) authorship attribution: High-quality empirical study, n=1600+ programmers, peer-reviewed → GRADE = A
- Random ArXiv preprint on AI code detection: Small n, no replication, high risk of bias → GRADE = C
- Opinion piece on Reddit: → GRADE = D (not admitted to evidence base)

**Reporting:** Create summary table with source, GRADE, and justification

---

### 5.2 Replication Crisis & Dunning-Kruger Defense

**Objective:** Maintain healthy skepticism about our own and others' findings.

**Specific Safeguards:**

1. **Publication Bias Awareness:**
   - Expect that published correlations are inflated (effect size inflation)
   - Our estimated correlations may be upwardly biased if we've only reviewed published studies
   - Discount published correlations by ~15–20% as rough correction

2. **Small Sample Instability:**
   - Correlations estimated on N < 500 are notoriously unstable
   - Our bootstrap CIs should be wide; if narrow, we may be overconfident
   - Always report effective sample size and quality

3. **Multiple Comparisons Problem:**
   - We're computing 45 correlations; expect ~2–3 false positives at p = 0.05
   - Use Bonferroni or FDR correction; be conservative

4. **Confounding by Language/Domain:**
   - A correlation might be driven by a third variable (e.g., "web code" has different characteristics)
   - Stratify analysis by language/domain; check if correlation persists

5. **Overfitting in Weight Optimization:**
   - If we learn weights on the same data we use to estimate correlations, we overfit
   - Split data: use 70% to estimate correlations, 30% to learn weights
   - Cross-validate learned weights on held-out data

6. **Our Own Biases:**
   - We hypothesized certain correlations; confirmation bias may inflate their importance
   - Treat hypothesized correlations skeptically; give priority to unexpected findings
   - Have a neutral party review our interpretation

---

### 5.3 Adversarial Self-Review

**After drafting conclusions, ask:**

1. **What would falsify our findings?**
   - What correlation pattern would suggest we're wrong?
   - Could the data support an opposite conclusion? (Probably yes; datasets are messy)

2. **What are the strongest objections to our approach?**
   - Is file-level aggregation vs. function-level aggregation affecting results?
   - Could the dataset be biased toward certain types of AI models (GPT-3.5) and not generalize to others (Claude, Gemini)?

3. **What if we're completely wrong about a signal?**
   - Example: What if "comment phrasing boilerplate" doesn't predict AI code at all, and we just got lucky?
   - How would we know? (Negative result: no correlation with ground truth in new dataset)

4. **Are we conflating correlation with causation?**
   - High CCR might not "cause" AI detection; both might be caused by code style
   - Latent factors may be the true causal drivers

5. **How much would our conclusions change if we dropped the weakest signal (Commit metadata)?**
   - If dropping it doesn't substantially change weights, maybe it's not important
   - Sensitivity analysis: drop each signal one at a time; recompute weights

---

### 5.4 Separation of Peer-Reviewed vs. Grey Literature

**Organization:**

- **Peer-Reviewed Sources (Tier 1):**
  - Published in venues: IEEE TSE, ACM TOSEM, FSE, ICSE, Empirical SE journals, arXiv with >10 citations
  - Examples: Caliskan et al., Briand et al., Hall et al.
  - Weight heavily in evidence synthesis

- **Grey Literature (Tier 2):**
  - ArXiv preprints, technical reports, dissertations, conference papers not in top venues
  - Examples: Recent AI code detection papers (many are preprints)
  - Include but note uncertainty; don't treat as definitively established

- **Opinion / Blog Posts (Tier 3):**
  - Useful for context, not evidence
  - Do not cite as supporting correlations or methodological claims

**Reporting:** Clearly label sources by tier; summarize evidence from each tier separately

---

### 5.5 Retraction Watch & Integrity Check

**Before citing a study:**
1. Check Retraction Watch (retractionwatch.com) for retractions or expressions of concern
2. Google scholar: look at citation count and whether subsequent papers disputed findings
3. Note any methodology criticisms in follow-up studies

**Example:** If a famous software metrics paper was retracted/disputed, downgrade its GRADE and note uncertainty

---

## Part 6: Expected Outputs & Deliverables

### 6.1 Estimated Correlation Matrix

**Deliverable:** 10×10 correlation matrix with 95% confidence intervals

**Format:**
```
Signal Pair                              Pearson r    [Lower CI, Upper CI]    p-value (FDR-adj.)    Spearman ρ    Notes
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
CCR ↔ Docstring consistency              0.42         [0.35, 0.50]            p < 0.001 *          0.38          Moderate; docstrings inflate CCR
CCR ↔ Comment phrasing                   0.61         [0.54, 0.68]            p < 0.001 *          0.59          High; predicted ~0.6
CCR ↔ Naming uniformity                  0.18         [0.05, 0.30]            p = 0.021             0.15          Weak; unexpected
...
(all 45 pairs)
```

**Key Metrics to Include:**
- Pearson correlation (primary)
- Spearman correlation (robustness check)
- 95% BCa bootstrap CI
- FDR-adjusted p-value
- Effect size interpretation (Cohen's guidelines: r < 0.3 = small, 0.3–0.5 = medium, > 0.5 = large)

---

### 6.2 Multicollinearity Assessment Report

**Deliverable:** VIF diagnostics, condition number, eigenvalue analysis

**Report Contents:**
1. **VIF Summary Table:**
   | Signal                        | VIF    | Interpretation                  |
   |-------------------------------|--------|----------------------------------|
   | CCR                           | 4.2    | Moderate; consider adjustment   |
   | Comment phrasing              | 4.8    | Moderate; consider adjustment   |
   | Docstring consistency         | 3.5    | Acceptable                      |
   | ... (rest of signals)         | ...    | ...                             |

2. **Condition Number:** κ = λ_max / λ_min = [value]; interpretation (< 10 = good, 10–30 = moderate, > 30 = severe)

3. **PCA Summary:**
   | PC  | Eigenvalue | % Variance | Cumulative % |
   |-----|------------|------------|----|
   | 1   | 3.2        | 32%        | 32% |
   | 2   | 2.1        | 21%        | 53% |
   | 3   | 1.4        | 14%        | 67% |
   | 4   | 0.9        | 9%         | 76% |
   | 5   | 0.7        | 7%         | 83% |
   | ...continue until 95% |

   **Interpretation:** 5–6 PCs needed for 95% variance; suggests moderate dimensionality reduction possible

4. **Visualization:** Heat map of correlation matrix with dendrogram showing clustering

---

### 6.3 Effective Independent Signal Count

**Deliverable:** Quantitative estimate of "true" independent signals

**Method & Result:**
- From PCA eigenvalues: k = number of PCs explaining 90% variance = **5**
- Effective signal count = 5 / 10 = **50% efficiency**
- Interpretation: Our 10 signals contain the information equivalent of ~5 independent signals; 50% of dimensionality is "wasted" on correlations

**Alternative Metric (Renyi Entropy):**
- Entropy of normalized eigenvalues = 0.78 (range: 0–1)
- Interpretation: relatively high entropy; signals aren't perfectly redundant

---

### 6.4 Revised Weight Vector

**Deliverable:** Adjusted weights accounting for multicollinearity

**Report Format:**
```
Method: Ridge Regression (λ = 0.3 selected by 5-fold CV)

Signal                          Original Wt    Learned Wt    Change        Interpretation
──────────────────────────────────────────────────────────────────────────────────────────
Comment-to-code ratio           0.180          0.145         -19.4%        High correlation with comment phrasing; downweighted
Docstring consistency           0.150          0.138         -8.0%         Moderate correlation with CCR; slight downweight
Naming conv. uniformity         0.130          0.141         +8.5%         Relatively independent; slight upweight
Error handling patterns         0.120          0.128         +6.7%         Independent; slightly upweighted
Declarative bias                0.100          0.103         +3.0%         Relatively independent
Function length distribution    0.080          0.091         +13.8%        Independent; upweighted (inverse of function length CV)
Comment phrasing                0.080          0.064         -20.0%        Highly correlated with CCR; downweighted
Hallucinated API calls          0.060          0.073         +21.7%        Independent; strong signal; upweighted
Edge case depth                 0.050          0.067         +34.0%        Independent from error handling; upweighted
Commit metadata                 0.050          0.051         +2.0%         Minimal change; nearly orthogonal
────────────────────────────────────────────────────────────────────────────────────────
Total                           1.000          1.000                        (normalized)

Cross-validated accuracy improvement: 78.2% (original) → 80.1% (learned) [+1.9 percentage points]
```

**Alternative Methods (for comparison):**
- **PCA-based:** Weights derived from first 5 PC eigenvalues (differs from ridge in pattern)
- **VIF-based heuristic:** Simple, interpretable adjustment (compare to ridge output)
- **EFA latent factors:** If 4 latent factors identified, weights to latent factors (not original signals)

---

### 6.5 Interaction Effects Report

**Deliverable:** Significant interaction terms and their interpretation

```
Interaction Term                      Coefficient    p-value    Interpretation
─────────────────────────────────────────────────────────────────────────────────────
CCR × Comment phrasing                +0.083         < 0.001 *  Synergistic effect: both high → strong AI signal
Naming uniformity × Function length CV -0.045        0.018  *   Moderate effect: both suggest "generated" code
Error handling × Edge case depth      +0.021         0.12       Not significant; no interaction
Declarative bias × Naming uniformity  +0.032         0.04  *    Weak interaction; modern style + uniformity
[Non-significant interactions omitted]

Logistic regression model:
  - Main effects only: AIC = 1205, accuracy (cross-val) = 78.2%
  - Main + interactions: AIC = 1191, accuracy (cross-val) = 79.8%
  - Improvement: 9 interaction terms, 1.6 percentage point accuracy gain
```

---

### 6.6 Non-Linear Effects Report

**Deliverable:** Evidence for threshold effects, non-monotonic relationships

```
Signal                         Non-linear Pattern?    Evidence Strength
──────────────────────────────────────────────────────────────────────────
Naming convention uniformity   Threshold at 0.75      Moderate: AI >> human above 0.75
Comment-to-code ratio          U-shaped               Weak: scatter plot suggests monotonic relationship
Edge case depth                Saturation at depth 4  Moderate: diminishing returns beyond depth 4
Function length CV             Bimodal distribution   Strong: distinct human (high CV) vs. AI (low CV) clusters
Declarative bias               Slight non-linearity   Weak: mostly monotonic

Best-fitting models per signal (GAM vs. Linear):
  - Naming uniformity: GAM superior (log-likelihood ratio test, p = 0.008)
  - Edge case depth: GAM superior (p = 0.042)
  - Comment phrasing: Linear adequate (p = 0.23, no non-linearity detected)
  [etc.]
```

---

### 6.7 Latent Factor Structure (if identified)

**Deliverable:** Confirmatory factor analysis results

```
Latent Factor 1: "Documentation Style" (α = 0.73, Cronbach's alpha)
  Manifest signals:
    - CCR:                 loading = 0.71
    - Docstring consistency: loading = 0.68
    - Comment phrasing:    loading = 0.64
  Interpretation: Reflects how extensively code is documented; AI tends to extreme (over- or under-)

Latent Factor 2: "Code Uniformity" (α = 0.61)
  Manifest signals:
    - Naming uniformity:   loading = 0.79
    - Function length CV:  loading = -0.68 (inverse; uniform lengths)
    - Declarative bias:    loading = 0.42
  Interpretation: Reflects "cookie cutter" vs. diverse code; AI more uniform

Latent Factor 3: "Defensive Programming" (α = 0.55)
  Manifest signals:
    - Error handling patterns: loading = 0.72
    - Edge case depth:         loading = 0.81
    - Hallucinated API:        loading = -0.60 (inverse; fewer errors)
  Interpretation: Code robustness/defensive patterns; humans more defensive

Model fit: RMSEA = 0.06, CFI = 0.92, TLI = 0.90 → acceptable fit
```

---

### 6.8 Cross-Dataset Validation Results

**Deliverable:** Generalization of findings across datasets, languages, domains

```
Dataset                      N(AI)  N(Human)  r(CCR, Comment) r(Naming, Length)  Model Accuracy (Test)
──────────────────────────────────────────────────────────────────────────────────────────────────────
CodeSearchNet Python         580    520       0.62            0.28               81.3%
CodeSearchNet Java           415    410       0.59            0.32               79.1%
CodeSearchNet JavaScript     490    505       0.65            0.25               82.4%
Codex evaluation set         1200   800       0.58            0.31               78.5%  [slightly lower, model domain shift]
StackOverflow synthetic      320    320       0.63            0.29               80.7%
[Across all datasets]        [3005] [2555]    0.61 ± 0.03     0.29 ± 0.03        80.4% ± 1.4%

Conclusion: Correlations & learned weights are robust across language/domain; modest domain shift effect on accuracy
```

---

### 6.9 Methodology for Ongoing Recalibration

**Deliverable:** Process document for periodic re-estimation

```
Recalibration Cycle:
1. Frequency: Every 6 months (as new AI models emerge) or when N_new > 500 samples accumulated
2. Data: Pool existing dataset with new samples
3. Re-estimate:
   - Correlation matrix (full 10×10, with CIs)
   - Multicollinearity metrics (VIF, condition number)
   - Learned weights (ridge regression, cross-validation)
4. Comparison:
   - Have correlations changed materially (> 0.10 shift)? Flag for review
   - Has multicollinearity increased? (VIF > 5?)
   - Do learned weights differ from current by > 20%? Discuss trade-offs
5. Decision:
   - If changes < 5%: keep current weights
   - If changes 5–20%: update weights, document rationale
   - If changes > 20%: signal model drift; investigate root cause (new model generation style? dataset bias? code domain shift?)
6. Governance:
   - Changes require 2-person review + sign-off
   - Document before/after model accuracy on test set
   - Archive old weight vectors for reproducibility
```

---

### 6.10 Identified Gaps & Future Research

**Deliverable:** Honest assessment of what we don't know

```
Gap 1: Causal vs. Correlational Inference
  Current: We estimate correlations; we don't know if high CCR causes AI detection or is caused by a latent "documentation style"
  Needed: Interventional studies (e.g., rewrite human code with high comments, see if detection accuracy changes)
  Timeline: 2–3 year effort; requires human annotation

Gap 2: Model Generalization Across AI Generators
  Current: Data includes GPT-3.5/4, Codex; limited Gemini, Claude, specialized code-gen models
  Needed: Systematic evaluation on diverse models + version updates (GPT-5, etc.)
  Timeline: Ongoing; partner with model vendors

Gap 3: Adversarial Robustness
  Current: We don't know if developers can deliberately evade detection
  Needed: Red-teaming; rewrite AI code to mimic human style, measure evasion
  Timeline: 1–2 year research project

Gap 4: Temporal Stability
  Current: Single snapshot of code; no longitudinal analysis
  Needed: Track pull requests over time; does AI detection accuracy decay as code is refactored?
  Timeline: 6 months; requires historical data

Gap 5: Cross-Language Equivalence
  Current: Correlations differ by language; unclear if latent factors are language-invariant
  Needed: Deeper analysis of signal definitions per language; potential language-specific weight vectors
  Timeline: 3–6 months; requires language specialists
```

---

## Part 7: Implementation Checklist

**Before finalizing research:**

- [ ] **Literature review:** Retrieved and reviewed ≥ 10 peer-reviewed sources on authorship attribution, metrics correlation, AI code detection
- [ ] **GRADE assessment:** Assigned quality ratings to all sources; clearly flagged grey literature
- [ ] **Dataset selection:** Identified 2–3 candidate datasets; confirmed N ≥ 1000 AI-generated + 1000 human samples per class
- [ ] **Signal definitions:** Documented clear, reproducible definitions for all 10 signals + edge cases
- [ ] **Correlation matrix:** Computed all 45 pairwise correlations with 95% BCa bootstrap CIs; applied FDR correction
- [ ] **Multicollinearity:** Reported VIF for each signal, condition number, PCA eigenvalues
- [ ] **Weight optimization:** Learned weights via ridge/elastic-net regression, compared to original, cross-validated
- [ ] **Latent factors:** Attempted EFA/CFA; reported whether k < 10 latent factors explain data
- [ ] **Interaction effects:** Fit models with pairwise interactions; identified significant terms
- [ ] **Non-linearity:** Tested splines/GAM vs. linear; reported evidence for threshold effects
- [ ] **Cross-dataset validation:** Confirmed findings generalize across languages/domains
- [ ] **Adversarial self-review:** Drafted & addressed major objections; flagged limitations
- [ ] **Retraction check:** Verified no retractions in cited studies
- [ ] **Epistemic honesty:** Clearly separated confident findings from speculative ones
- [ ] **Documentation:** Written methodology sufficient for replication by independent team

---

## End of Research Prompt

This prompt is designed for exhaustive, unflinching investigation suitable for deep research agents (ChatGPT Deep Research, Gemini Deep Research, similar). It prioritizes methodological rigor, statistical sophistication, and honest treatment of uncertainty. The goal is to produce a defensible, evidence-based revised weight vector for the 10 AI code detection signals, along with a clear assessment of which findings are robust and which require further validation.

**Total estimated research effort:** 40–60 hours for a competent researcher (literature review + dataset acquisition + analysis + interpretation).
