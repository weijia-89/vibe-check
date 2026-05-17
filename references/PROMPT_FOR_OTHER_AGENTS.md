# Cross-Agent Research Prompt: AI-Generated Code Detection

## Context
You are continuing research on deterministic detection of AI-generated ("vibe coded") pull requests. A prior research agent compiled the findings below. Your job: validate independently, discover new sources, extend the analysis, and challenge assumptions.

## Prior findings to validate

### Core claim: Deterministic heuristics can estimate AI-generation probability from git diffs
**Confidence: 70/100 | Status: CONCLUSIVE-PROVISIONAL**

10 signals were identified, weighted by empirical discriminative power:

| Signal | Weight | Basis | Validate |
|--------|--------|-------|----------|
| Comment-to-code ratio | 0.18 | arXiv:2411.04299, "sole universal discriminator" | Verify claim holds across models post-2025 |
| Docstring consistency | 0.15 | arXiv:2502.17749, 80-100% LLM vs 20-40% human | Check if newer models learned to skip docstrings |
| Naming uniformity | 0.13 | arXiv:2502.17749, 95%+ LLM consistency | Verify with Go/Rust codebases (enforced style) |
| Error handling patterns | 0.12 | arXiv:2512.05239, shallow try-catch | Replicate on current model outputs |
| Declarative bias | 0.10 | arXiv:2409.01382: Claude 3 only | Test with GPT-4, Gemini, newer Claude |
| Function length CV | 0.08 | arXiv:2409.01382 | Low sample size concern |
| Comment phrasing | 0.08 | arXiv:2502.17749 | Cultural/team bias risk |
| Hallucinated APIs | 0.06 | Augment Code blog, practitioner reports | No peer-reviewed source |
| Edge case depth | 0.05 | Heuristic, multiple practitioner reports | No quantitative study |
| Commit metadata | 0.05 | GitHub AI usage framework | Trivially gameable |

### Known gaps
1. No large-scale RCT validating this ensemble approach
2. Signal correlation not quantified (CCR and comment phrasing likely correlate ~0.6+)
3. No per-codebase calibration mechanism
4. Threshold values are approximate, derived from paper medians
5. No validation against "vibe coded" specifically (proxy: AI-generated)
6. Cultural bias in human baselines (Western open-source projects)
7. Signal decay as models improve, no longitudinal tracking

### Adversarial weaknesses identified
- Well-documented codebases trigger false positives
- Strict linters (ESLint, Black) enforce uniformity → naming signal useless
- Post-generation editing defeats most signals
- The core risk ("code submitted without understanding") is not directly measurable

## Your tasks

1. **Source validation**: Verify the cited papers exist, are peer-reviewed, and the claims attributed match the actual paper findings. Check Retraction Watch.
2. **New sources**: Search PubMed, Semantic Scholar, Google Scholar for 2025-2026 papers on: AI code detection, code stylometry, LLM fingerprinting, vibe coding measurement.
3. **Signal calibration**: Find any empirical data on threshold values for these signals. Are 0.15 CCR human baseline and 0.5 LLM baseline defensible?
4. **Correlation analysis**: Find data on which signals are independent vs correlated. Adjust effective weight accordingly.
5. **Gap filling**: Specifically look for research on hallucinated API detection and edge case coverage measurement.
6. **Adversarial challenge**: Try to construct a scenario where this tool gives a confident wrong answer. Document it.
7. **Model evolution**: Has post-2025 LLM output changed enough to invalidate these signals?

## Epistemic rules
- Apply GRADE, Cochrane RoB 2, ROBINS-I standards per source
- Separate peer-reviewed from grey literature
- Flag replication-crisis concerns (this touches CS/software engineering, moderate risk)
- Apply Dunning-Kruger guard: what are you NOT qualified to assess here?
- Be dialectical: argue for AND against each finding

## Output format
- Evidence Ledger: table with claim, sources, quality, confidence, status
- New findings: structured like the signal table above
- Revised weights if warranted
- Updated gap list
- Questions for next iteration
