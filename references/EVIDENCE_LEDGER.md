# Evidence ledger

Sources referenced by `SKILL.md`, `RESEARCH.md`, `GEMINI_AI_CODE_DETECTION_RESEARCH.md`, `CLAIMS.md`, and related docs. Links were HTTP-checked on 2026-04-16. A `(gated)` tag means automated HEAD returns 403 but the page loads in a normal browser (Cloudflare, ACM, Medium, and ResearchGate block scripted fetches).

For the smaller, quote-level set of numeric claims, see `references/CLAIMS.md`. This file is the broader bibliography with working URLs.

## A0. AI code security and human-factor studies

| id | source | link |
|----|--------|------|
| A0a | Pearce et al., *Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions*, IEEE S&P 2022 (arXiv:2108.09293). 1,689 programs across 89 CWE-aligned scenarios; about 40% of generated code was vulnerable. | <https://arxiv.org/abs/2108.09293> |
| A0b | Fu et al., *Security Weaknesses of Copilot Generated Code in GitHub*, 2023 (arXiv:2310.02059). 29.5% of Python and 24.2% of JavaScript Copilot snippets contained security weaknesses across 43 CWE categories, with eight in the 2023 CWE Top-25. (Corrected v0.2.0 — prior entry said "32.8% / 24.5% / 38–43 CWEs" which did not match the abstract; see CLAIMS C-002.) | <https://arxiv.org/abs/2310.02059> |
| A0c | Perry et al., *Do Users Write More Insecure Code with AI Assistants?*, ACM CCS 2023 (arXiv:2211.03622). 47 participants, five tasks, three languages. AI-assisted users wrote less secure code on four of five tasks, and were more likely to believe their code was secure. | <https://arxiv.org/abs/2211.03622> |
| A0d | Sandoval et al., *Lost at C: A User Study on the Security Implications of Large Language Model Code Assistants*, USENIX Security 2023 (arXiv:2208.09727). User study; reports the "AI-assisted" group did not produce *significantly more* security bugs than the control group, with ≤10% delta on most CWEs. (Note: an EMSE link previously cited here as "33% vs 25%" did not match this paper's findings; the claim is reclassified as *Pending* P-001 in CLAIMS.md. Use this user-study source instead.) | <https://arxiv.org/abs/2208.09727> |

## A. Primary AI code-detection studies

| id | source | link |
|----|--------|------|
| A1 | Wang et al., *An Empirical Study on Detecting AI-Generated Source Code*, ICSE 2025. | <https://arxiv.org/abs/2411.04299> |
| A2 | *Detection of LLM-Paraphrased Code via Stylometry*, 2025. | <https://arxiv.org/abs/2502.17749> |
| A3 | *Automatic Detection of LLM-Generated Code: Claude 3 Case Study*, 2024. | <https://arxiv.org/abs/2409.01382> |
| A4 | *A Survey of Bugs in AI-Generated Code*, 2025. | <https://arxiv.org/abs/2512.05239> |
| A5 | *Spotting LLMs With Binoculars*, ICML 2024. | <https://arxiv.org/abs/2401.12070> |
| A6 | *GPTSniffer: CodeBERT-based Detection*, JSS 2024. DOI 10.1016/j.jss.2024.112059. | <https://doi.org/10.1016/j.jss.2024.112059> |
| A7 | *I Know Which LLM Wrote Your Code (LLM-AuthorBench)*, 2025. | <https://arxiv.org/abs/2506.17323> |
| A8 | *Stylometry recognizes human and LLM-generated texts in short samples*, arXiv:2507.00838. | <https://arxiv.org/abs/2507.00838> |

## B. Benchmarks and capability trajectory

| id | source | link |
|----|--------|------|
| B1 | Stanford HAI, *2025 AI Index, Technical Performance*. SWE-bench trajectory 4.4% to 71.7%. | <https://hai.stanford.edu/ai-index/2025-ai-index-report/technical-performance> |
| B2 | *AICD Bench: A Challenging Benchmark for AI-Generated Code Detection*, ACL EACL-long 325, 2026 (arXiv:2602.02079). | <https://arxiv.org/abs/2602.02079>, <https://aclanthology.org/2026.eacl-long.325/> |
| B3 | *Vibe Coding: Toward an AI-Native Approach*, arXiv:2510.17842. | <https://arxiv.org/abs/2510.17842> |

## C. Drift detection, changepoint, distribution divergence

| id | source | link |
|----|--------|------|
| C1 | Adams & MacKay, *Bayesian Online Changepoint Detection*, 2007. | <https://lips.cs.princeton.edu/pdfs/adams2007changepoint.pdf>, <https://arxiv.org/abs/0710.3742> |
| C2 | *A benchmark and survey of fully unsupervised concept drift detectors on real-world data streams*, IJDSA 2024 or 2025 (19:1–31). | <https://link.springer.com/article/10.1007/s41060-024-00620-y> |
| C3 | *Unsupervised Concept Drift Detection from Deep Learning Representations*, arXiv:2406.17813. | <https://arxiv.org/abs/2406.17813> |
| C4 | *Monitoring Drift and ML Incident Response* (ScaleMind, 2025). Layer model and segment-specific thresholds. | <https://scalemind.dev/ai/ml/mlops/monitoring-drift-and-ml-incident-response/> |

## D. Complexity, comprehension, stylometry foundations

| id | source | link |
|----|--------|------|
| D1 | Feitelson, *From Code Complexity Metrics to Program Comprehension*, Communications of the ACM 2023. ACM DOI 10.1145/3546576. | <https://doi.org/10.1145/3546576> (gated), arXiv preprint <https://export.arxiv.org/pdf/2303.07722v1.pdf> |
| D2 | Feitelson, *Considerations and Pitfalls in Controlled Experiments on Code Comprehension*, EMSE 2022 (arXiv:2103.08769). | <https://arxiv.org/abs/2103.08769> |
| D3 | Landman et al., *Empirical Analysis of the Relationship between CC and SLOC in a Large Corpus of Java Methods*, SCAM 2014 (arXiv:1411.5787). | <https://arxiv.org/abs/1411.5787> |
| D4 | Barkmann et al., *Quantitative Evaluation of Software Quality Metrics in Open-Source Projects*, 2009. | <https://www.arisa.se/files/BLL-09.pdf> |
| D5 | Caliskan et al., *De-anonymizing Programmers via Code Stylometry*, USENIX Security 2015. | <https://www.usenix.org/system/files/conference/usenixsecurity15/sec15-paper-caliskan-islam.pdf> |

## E. Adversarial robustness and evasion

| id | source | link |
|----|--------|------|
| E1 | *MASH: Evading Black-Box AI-Generated Text Detectors via Style Humanization*, arXiv:2601.08564. | <https://arxiv.org/abs/2601.08564> |
| E2 | *The TIP of the Iceberg: Task-in-Prompt Adversarial Attacks on LLMs*, arXiv:2501.18626. | <https://arxiv.org/abs/2501.18626> |
| E3 | *DuCodeMark: Dual-Purpose Code Dataset Watermarking via Style-Aware Watermark and Poison Design*, arXiv:2604.10611. | <https://arxiv.org/abs/2604.10611> |
| E4 | *Large Language Models can be Guided to Evade AI-Generated Text Detection (SICO)*, arXiv:2305.10847. | <https://arxiv.org/abs/2305.10847> |
| E5 | *Diversity Boosts AI-Generated Text Detection (DivEye)*, arXiv:2509.18880. | <https://arxiv.org/abs/2509.18880> |

## F. Per-language and ecosystem baselines

| id | source | link |
|----|--------|------|
| F1 | TIOBE, *Which programming language produces the most complex code?* Industry blog cited for per-language cyclomatic complexity distributions. | <https://www.tiobe.com/knowledge/article/which-programming-language-produces-the-most-complex-code/> |
| F2 | *Evaluation of Rust code verbosity, understandability and complexity*, PMC7959618. | <https://pmc.ncbi.nlm.nih.gov/articles/PMC7959618/> |
| F3 | *Scalable, Validated Code Translation of Entire Projects using LLMs*, arXiv:2412.08035. Cross-language error-handling idioms. | <https://arxiv.org/abs/2412.08035> |
| F4 | *Understanding and Detecting Real-World Safety Issues in Rust* (Rust TSE). | <https://songlh.github.io/paper/rust-tse.pdf> |
| F5 | *Code2Doc: A Quality-First Dataset for Code Documentation*, arXiv:2512.18748. | <https://arxiv.org/abs/2512.18748> |
| F6 | *CodeWiki: Automated Repository-Level Documentation at Scale*, arXiv:2510.24428. | <https://arxiv.org/abs/2510.24428> |

## G. Industry drift-monitoring guides (Field B; convention, not RCT)

| id | source | link |
|----|--------|------|
| G1 | Fiddler AI, *Measuring Data Drift: Population Stability Index*. | <https://www.fiddler.ai/blog/measuring-data-drift-population-stability-index> |
| G2 | Coralogix, *A Practical Introduction to Population Stability Index (PSI)*. | <https://coralogix.com/ai-blog/a-practical-introduction-to-population-stability-index-psi> |
| G3 | TheLinuxCode, *Population Stability Index (PSI) in 2026, a practitioner's field guide*. | <https://thelinuxcode.com/population-stability-index-psi-in-2026-a-practitioners-field-guide/> |

## H. Tools used by this repo

| id | source | link |
|----|--------|------|
| H1 | GitHub CLI (`gh`). | <https://cli.github.com/> |

## Notes and known gates

- ACM DOI landing pages (D1 and similar) return 403 to scripted fetch but open in a browser.
- ResearchGate, Medium, and SciRP routinely block curl. They are cited but automated checks are unreliable.
- When a paper has both a publisher page and an arXiv preprint, the arXiv version is listed first so a reader is not paywalled.
- The Feitelson CACM paper has a HUJI preprint at `cs.huji.ac.il/~feit/papers/Comp23CACM.pdf`. It answers `GET` but rejects `HEAD`. The arXiv preprint above is the stable automated link.

## Updating this ledger

1. Add a row in the matching section. One line per source.
2. Prefer arXiv or institutional preprint over a paywalled publisher link when both exist.
3. Run a link check before you commit:

```bash
grep -Eo 'https?://[^ )>]+' references/EVIDENCE_LEDGER.md \
  | sort -u \
  | while read u; do
      code=$(curl -sIL -A "Mozilla/5.0" -o /dev/null -w "%{http_code}" --max-time 15 "$u")
      printf "%s\t%s\n" "$code" "$u"
    done
```

If a row's primary link fails HEAD but works in a browser, tag it `(gated)` instead of removing it.
