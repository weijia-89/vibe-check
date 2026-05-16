# Claims ledger — verifiable primary-source quotes

Every numeric or named-paper claim used in `SKILL.md`, `README.md`, or
`references/GEMINI_AI_CODE_DETECTION_RESEARCH.md` must resolve to a row here
or be tagged `[unverified]` in prose. `scripts/check_claims.py` enforces this
**and** requires a non-empty `quote` field per row (CI fails otherwise).

## Schema

| field | meaning |
|-------|---------|
| `id` | Stable ID (`C-NNN`); never reused |
| `claim` | One-sentence paraphrase of what we assert |
| `quote` | Literal text copied from the cited section. Required, non-empty |
| `source` | Title, venue, arXiv or DOI |
| `section` | Where in the source the quote appears (Abstract, §3.2, Table 4, etc.) |
| `primary?` | `yes-abstract` (abstract read), `yes-body` (body read), `secondary` (cited via blog/review), `gated` (paywalled) |
| `status` | `confirmed`, `weakened`, `contradicted`, `unverified`, `removed` |
| `accessed` | YYYY-MM-DD when the source was checked |

## Entries

| id | claim | quote | source | section | primary? | status | accessed |
|----|-------|-------|--------|---------|----------|--------|----------|
| C-001 | About 40% of GitHub Copilot programs across CWE-aligned scenarios were vulnerable. | "In total, we produce 89 different scenarios for Copilot to complete, producing 1,689 programs. Of these, we found approximately 40% to be vulnerable." | Pearce et al., *Asleep at the Keyboard?*, IEEE S&P 2022 — arXiv:2108.09293. | Abstract. | yes-abstract | confirmed | 2026-05-14 |
| C-002 | About 29.5% of Copilot Python and 24.2% of JavaScript snippets in real GitHub projects contained security weaknesses across 43 CWE categories; eight of those CWEs are in the 2023 CWE Top-25. | "Our analysis identified 733 snippets, revealing a high likelihood of security weaknesses, with 29.5% of Python and 24.2% of JavaScript snippets affected. These issues span 43 Common Weakness Enumeration (CWE) categories ... Notably, eight of those CWEs are among the 2023 CWE Top-25, highlighting their severity." | Fu et al., *Security Weaknesses of Copilot-Generated Code in GitHub Projects*, 2023 — arXiv:2310.02059. | Abstract. | yes-abstract | confirmed | 2026-05-14 |
| C-003 | Users with access to an AI code assistant wrote significantly less secure code and were more likely to believe their code was secure. | "Overall, we find that participants who had access to an AI assistant based on OpenAI's codex-davinci-002 model wrote significantly less secure code than those without access. Additionally, participants with access to an AI assistant were more likely to believe they wrote secure code than those without access to the AI assistant." | Perry et al., *Do Users Write More Insecure Code with AI Assistants?*, ACM CCS 2023 — arXiv:2211.03622. | Abstract. | yes-abstract | confirmed | 2026-05-14 |
| C-004 | In a controlled C-pointer task, AI-assisted users introduced critical security bugs at a rate at most ~10 percentage points above the no-assistant control. | "AI-assisted users produce critical security bugs at a rate no greater than 10% more than the control, indicating the use of LLMs does not introduce new security risks." | Sandoval et al., *Lost at C: A User Study on the Security Implications of Large Language Model Code Assistants*, USENIX Security 2023 — arXiv:2208.09727. | Abstract. | yes-abstract | confirmed | 2026-05-14 |
| C-005 | Existing AI-generated-code detectors perform poorly and lack generalization; ML on AST/static metrics can achieve F1 ≈ 82.55 in-distribution. | "The results show that they all perform poorly and lack sufficient generalizability to be practically deployed. … Our best model outperforms state-of-the-art AI-generated code detector (GPTSniffer) and achieves an F1 score of 82.55." | Wang et al., *An Empirical Study on Automatically Detecting AI-Generated Source Code: How Far Are We?*, ICSE 2025 — arXiv:2411.04299. | Abstract. | yes-abstract | confirmed | 2026-05-14 |
| C-006 | LLM-paraphrased code differs from human-written code in naming consistency, code structure, and readability. | "We statistically confirm significant differences in the coding styles of human-written and LLM-paraphrased code, particularly in terms of naming consistency, code structure, and readability." | Park et al., *Detection of LLM-Paraphrased Code and Identification of the Responsible LLM Using Coding Style Features*, 2025 — arXiv:2502.17749. | Abstract. | yes-abstract | confirmed (scoped to paraphrasing, not from-scratch generation) | 2026-05-14 |
| C-007 | SHAP analysis on per-LLM CatBoost classifiers identifies Comment-to-Code Ratio as the only universally predictive feature, but its predictive magnitude varies drastically across models, and modern-model AUC-ROC is ~0.68–0.80 vs. 0.96 for GPT-3.5. | "SHAP analysis identifies the Comment-to-Code Ratio as the sole universal discriminator. However, its predictive magnitude varies drastically across models, explaining why detectors trained on specific LLMs fail to generalize. … GPT-3.5's exceptional detectability (AUC-ROC 0.96) is unrepresentative of contemporary models (AUC-ROC approximately between 0.68 and 0.80)." | Tao et al., *Automatic Detection of LLM-Generated Code: A Comparative Case Study Across Function and Class Granularities*, 2024 — arXiv:2409.01382. | Abstract. | yes-abstract | confirmed (qualifies "CCR is universal" with model-dependent magnitude) | 2026-05-14 |
| C-008 | The AICD Bench (2M examples, 77 models across 11 families, 9 languages) shows that current detectors remain "far below practical usability" under distribution shift and on hybrid or adversarial code. | "It spans 2M examples, 77 models across 11 families, and 9 programming languages, including recent reasoning models. … Extensive evaluation on neural and classical detectors shows that performance remains far below practical usability, particularly under distribution shift and for hybrid or adversarial code." | *AICD Bench: A Challenging Benchmark for AI-Generated Code Detection*, 2026 — arXiv:2602.02079. | Abstract. | yes-abstract | confirmed | 2026-05-14 |
| C-009 | Transformer authorship attribution on C programs reaches 95–97% accuracy across multi-class settings using LLM-AuthorBench (32k programs, 8 LLMs); deterministic regex stylometry is not in the same regime. | "In binary classification, our model achieves 97.56% accuracy in distinguishing C programs generated by closely related models such as GPT-4.1 and GPT-4o, and 95.40% accuracy for multi-class attribution among five leading LLMs." | *I Know Which LLM Wrote Your Code Last Summer*, 2025 — arXiv:2506.17323. | Abstract. | yes-abstract | confirmed | 2026-05-14 |
| C-010 | Style-aware AST watermarking can be embedded into code datasets with high stealth and verifiability; AST transforms can shift surface style without changing structural metrics. | "DuCodeMark parses each code sample into an abstract syntax tree (AST), applies language-specific style transformations to construct stealthy trigger-target pairs … achieves strong verifiability (p < 0.05), high stealthiness (suspicion rate ≤ 0.36), robustness against both watermark and poisoning attacks (recall ≤ 0.57)." | *DuCodeMark*, 2026 — arXiv:2604.10611. | Abstract. | yes-abstract | confirmed (no "0.00 variance" claim in abstract — that phrasing is secondary) | 2026-05-14 |
| C-011 | "Vibe coding" is a defined paradigm in the recent literature: a developer specifies high-level functional intent plus qualitative descriptors, and an agent transforms those into executable software. | "We formalize the definition of vibe coding and propose a reference architecture that includes an intent parser, a semantic embedding engine, an agentic code generator, and an interactive feedback loop." | *Vibe Coding: Toward an AI-Native Paradigm for Semantic and Intent-Driven Programming*, 2025 — arXiv:2510.17842. | Abstract. | yes-abstract | confirmed | 2026-05-14 |
| C-012 | PSI thresholds 0.10 and 0.25 are widely cited industry conventions, not derived from peer-reviewed RCTs. | "" | Practitioner guides — Fiddler AI; Coralogix; TheLinuxCode (2026). | Multiple industry blog posts. | secondary | confirmed (convention, not RCT) | 2026-05-14 |

## Pending / unverified

| id | claim | reason | next step |
|----|-------|--------|-----------|
| P-001 | Sandoval et al. EMSE 2023 (DOI 10.1007/s10664-023-10380-1) reports Copilot reproduces vulnerable code ~33% vs. fixed code ~25%. | EMSE journal version is gated (Springer auth wall). The arXiv version 2208.09727 is "Lost at C" (USENIX 2023, different study) and reports different numbers (≤10% delta). | Read the EMSE PDF directly or remove the 33%/25% claim from prose. |
| P-002 | Perry et al. report users wrote less secure code on **four of five** specific tasks. | Abstract says "significantly less secure" overall; the 4-of-5 split is in the body. | Read §4 of arXiv:2211.03622 PDF. |
| P-003 | Survey of bugs in AI-generated code (arXiv:2512.05239) supports the specific claim that LLMs produce shallow `try`/`except` patterns. | Abstract is a generic taxonomy survey; specific shallow-error-handling rate is not in the abstract. | Read PDF body or downgrade `error_handling` signal citation. |
| P-004 | Specific signal weight values (0.18 / 0.15 / 0.13 / …) are derived from any peer-reviewed feature-importance ranking. | No source maps weights to these exact numbers. They were authored as defaults. | Either fit empirically on telemetry (≥1k labeled PRs) or label as "speculative defaults". |
| P-005 | `MODEL_FINGERPRINTS` per-LLM signal ranges (gpt4_family, claude_family, gemini_family) are derived from LLM-AuthorBench or any cited dataset. | LLM-AuthorBench studied C programs and reports classifier accuracy, not per-signal ranges. The fingerprint values appear nowhere in any cited source. | Mark `--model-evolution` `EXPERIMENTAL_DISABLED` until empirical fitting is done. |

## Rules

- **No numeric claim in `SKILL.md` / `README.md` without a row here, or `[unverified]` tag in prose.** `scripts/check_claims.py` enforces.
- **`quote` MUST be non-empty.** Empty quotes mean the claim was never primary-checked. The lint fails.
- **`primary?: secondary` allowed for industry-convention claims** (PSI thresholds). Mark them "Field B" in prose.
- **When the abstract doesn't support the specific number you want to cite, list the claim under *Pending* and read the body.** Don't paraphrase the abstract into a number that isn't there.
- **Update `accessed` whenever you re-read the source.** Sources are updated on arXiv; check before relying on quote text.

## How to add a row

```bash
# 1. Read the primary source.
# 2. Copy the literal text (exact characters, including punctuation).
# 3. Paste under "Entries" with a unique C-NNN id.
# 4. Run: python3 scripts/check_claims.py --strict
# 5. If lint passes and CI is green, ship.
```
