# AI code detection. Gemini synthesis (Apr 2026)

Condensed from *Open Problems in Deterministic AI-Generated Code Detection* (PDF). Maps to the ten-signal ensemble in `scripts/vibe_check.py`. Read alongside `SKILL.md`. This file is the long-form supplement. For every numeric claim, check `references/CLAIMS.md` and `references/EVIDENCE_LEDGER.md`.

## 1. Multicollinearity (grade: HIGH)

Documentation cluster (A). CCR, docstring consistency, and comment phrasing share volume and LOC structure. Feitelson (complexity versus comprehension, HUJI or CACM line) shows CC and LOC are tightly coupled on many corpora. The exact "near-perfect" wording depends on the dataset. Cite the primary text, not this summary alone (see CLAIMS.md C-005).

Defensive cluster (B). Error-handling score and nesting or edge depth both rise with branching. They are nested subsets of "how much control flow".

Uniformity cluster (C). Naming uniformity and function-length CV are less collinear. One is semantic, the other structural. Linters can touch both, but the axes differ.

Implication. The weighted sum double-counts size and documentation. The PDF estimates about 0.41 of total weight on that cluster. Effective dimensionality of independent information is around four latent factors. This number is speculative and an eigen-analysis is pending.

Mitigations. Compute static VIF on a frozen PR corpus. Deflate fixed weights by VIF. Do not use naive PCA or elastic-net without training data.

Confidence intervals. The ensemble conformal CI assumes independence. It is optimistic. For borderline A, B, and C grades, widen uncertainty mentally by about 30 to 50 percent until someone models the covariances.

## 2. Discrete syntax and drift metrics (grade: HIGH)

Code is categorical and sparse. Scalar signals (like CCR) collapse many ASTs to one number.

Wasserstein-2 on those summaries shows false-positive drift when discrete support shifts (for example `switch` to `if/else`), and false-negative drift when two generators share the same ratio.

Near-term workaround: prefer Sinkhorn (entropy-regularized OT) over raw W2 on binned signals. Longer term: MMD with tree or AST-aware kernels compares structure without the continuous projection loss.

## 3. Adversarial robustness (grade: HIGH)

Fragile to prompts. Docstrings, comment boilerplate, naming uniformity, declarative bias, and commit footers.

Prompt-resistant but refactorable. CCR, error patterns, and nesting. Style-aware and AST transforms such as DuCodeMark ([arXiv:2604.10611](https://arxiv.org/abs/2604.10611)) can shift style while preserving the structural metrics the abstract discusses. The "0.00 Δ complexity" phrasing is secondary-source. It is not in the abstract. A primary-text pass is pending. See `references/CLAIMS.md` C-004.

Strongest static signal. Hallucinated or impossible APIs. A model may not know its API reference is wrong.

Waterbed. Defeating shallow-error signals often raises uniformity elsewhere.

Shelf life (speculative). About six to nine months for static absolute thresholds as models and enterprise defaults move.

Countermeasures. Author-trajectory consistency. Task difficulty (crypto versus CRUD expects different depth). Optional compression or entropy variance proxies (DivEye-style). Each needs validation for a stdlib-only pipeline.

## 4. Semi-supervised learning (grade: HIGH on method choice)

Naive self-training is risky. Collinearity concentrates pseudo-labels on "big doc" PRs (Aminian et al. divergence analysis).

Co-training is the recommended alternative. Split views: structural (CCR, error handling, nesting, function-length CV) and lexical or documentation (docstring, naming, comment phrasing, declarative bias). Require agreement before assigning a pseudo-label (the MultiMatch head-agreement idea as a metaphor).

Anchor size rule of thumb. About ten to fifteen labels per effective dimension. If effective dimensionality is four, that is forty to sixty verified human or AI PRs. Initial classifier accuracy should exceed about 75 percent before trusting self-training expansion. Gate pseudo-labels with tight conformal bounds.

## 5. "Understanding" is not detection (grade: MODERATE)

The tool scores AI-like style, not comprehension.

Strong artifact proxies. Incremental commit evolution versus a single dump. Multi-file or call-graph scope. A PR description that explains "why" rather than "what".

Weak proxies. Review thread depth (bikeshedding). Raw Jira title match.

How to deploy. Never call it a "developer understanding score". Use it as a review-depth or audit-priority signal on the artifact.

## 6. Per-language baselines (grade: HIGH)

Universal thresholds misfire. TIOBE-style mean paths per function differ between C, Java, Rust, and JS.

Preferred approach. Z-score versus repo and language baselines from `vibe_calibration.py`. Re-estimate on a cadence.

Go. `gofmt` plus the idiomatic `if err != nil` style lowers structural separation between human and LLM code.

Rust. Baseline cyclomatic complexity is low. Watch for borrow-checker workarounds: spikes in `.clone()`, `.unwrap()`, or `Arc<Mutex<_>>` are language-specific red flags.

## Cross-cut: revised weights (hypothesis only; not shipped)

The PDF proposes raising weight on hallucination and comment-phrasing. It proposes lowering CCR, docstring, and function-length CV. It proposes dropping commit metadata from the weighted sum and treating it as a boolean override when present. Do not apply without an empirical fit on your telemetry. Track as an experiment in `calibration_override.json`.

## Priority open questions (from synthesis)

1. Can static entropy or compression variance on source strings substitute for model log-probs (DivEye-style)?
2. Is fast MMD or a tree kernel feasible in stdlib-only Python for drift?
3. What does the empirical VIF vector look like on ten thousand or more PRs for these specific heuristics?
4. What does an ethical pilot of a Git temporal "audit priority" look like, without surveillance framing?

## Key citations (short list)

Feitelson 2023 (complexity versus comprehension). Barkmann 2009 (OO metric correlation). Caliskan et al. 2015 (stylometry). Feydy, Sinkhorn 2020. MASH, TIP, DuCodeMark on the adversarial side. MultiMatch for co-training. Aminian f-divergence SSL. TIOBE language complexity blog. Code2Doc and CodeWiki on doc rates. Song's Rust safety paper. Full numbered bibliography in the original PDF *Works cited*. Hyperlinks: `references/EVIDENCE_LEDGER.md`.

## Citation spot-check (Apr 2026, agent)

Every concrete numeric claim should resolve to an entry in `references/CLAIMS.md` (schema plus a `status` field). `scripts/check_claims.py` lints for missing entries. Anything still pending primary-source read is tagged `[unverified]` in prose.

| Claim in PDF summary | CLAIMS.md id | Spot-check |
|----------------------|--------------|------------|
| DuCodeMark arXiv | C-004 | 2604.10611 resolves. The abstract covers style-aware AST transforms. The "0.00 CC or NLOC variance" number is secondary-source phrasing, pending a primary-text read. |
| Feitelson CC and LOC | C-005 | Supported across SE literature (Jay 2009 "stable linear", Landman 2014 "moderate"). Avoid "universal" or "near-perfect" phrasing externally. |
| TIOBE paths per function | (not yet) | Industry blog (Field B). Useful for motivating per-language z-scores, not for academic claims. |
| AICD Bench (2026) | C-002 | ACL EACL-long 325. Detectors "far below practical usability" under shift and adversarial code. Supports the shelf-life caveat. |
| PSI 0.10 and 0.25 cutoffs | C-001 | Industry convention (Coralogix, Fiddler, TheLinuxCode). No peer-reviewed empirical validation located (Field B). |
| SWE-bench 4.4% to 71.7% | C-003 | Stanford HAI AI Index 2025. A public institutional report. |
