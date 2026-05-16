# Labeled Dataset Construction Prompt

Copy the prompt below into a GitHub MCP-connected agent session.

```
ROLE: Dataset construction agent for AI-generated code detection calibration.
CONTEXT: A repo contains PRs with labels indicating "vibe coded" vs "AI-assisted but understood" vs unlabeled. Build a ground-truth dataset from these + expand via semi-supervised methods.

CONSTRAINTS:
- Budget: max 3000 API calls, max 300 PRs fetched in detail
- Time: single session
- No cascading searches: each phase has a hard call limit
- Output: TSV + JSON, token-minimal

═══════════════════════════════════════════
PHASE 1: DISCOVER LABELED PRs (max 200 API calls)
═══════════════════════════════════════════

1.1 Fetch all PR labels in the repo:
    gh label list --limit 200 --json name,description

1.2 Identify AI-related labels. Match patterns:
    - Exact: "vibe-coded", "vibe coded", "ai-generated", "ai-assisted", "copilot", "cursor"
    - Fuzzy: any label containing "ai", "llm", "generated", "vibe", "copilot", "auto"
    - Negative labels (human-confirmed): "human-written", "manual", "hand-coded"
    Output: label_map.tsv (label_name \t classification \t count)

1.3 Fetch PRs with each identified label:
    For each label in label_map:
      gh pr list --label "{label}" --state merged --limit 100 --json number,title,author,createdAt,mergedAt,additions,deletions,changedFiles,commits,labels

1.4 Output: labeled_prs.tsv
    Columns: pr_number \t label_class \t title \t author \t created \t merged \t additions \t deletions \t changed_files \t commit_count

═══════════════════════════════════════════
PHASE 2: COMPUTE SIGNALS ON LABELED PRs (max 1500 API calls)
═══════════════════════════════════════════

For each PR in labeled_prs.tsv (cap at 150 PRs, prioritize labeled ones):

2.1 Fetch diff:
    gh pr diff {number} --color=never > /tmp/pr_{number}.diff

2.2 Fetch commit messages:
    gh pr view {number} --json commits --jq '.commits[].messageHeadline'

2.3 Run vibe_check.py in JSON mode:
    python vibe_check.py --diff /tmp/pr_{number}.diff --format json

2.4 Extract per-signal scores from JSON output.

2.5 Append to signals.tsv:
    pr_number \t label_class \t overall_ai_prob \t ccr \t docstring \t naming \t error_handling \t declarative \t func_length \t comment_phrasing \t hallucinated \t edge_depth \t commit_meta

═══════════════════════════════════════════
PHASE 3: EXPAND DATASET VIA SEMI-SUPERVISED SAMPLING (max 1000 API calls)
═══════════════════════════════════════════

Goal: Find unlabeled PRs that are likely vibe-coded or likely human-written based on existing signal patterns, to expand the training set.

3.1 From Phase 2 results, compute signal thresholds:
    - vibe_coded_prototype: mean signal vector of label_class="vibe-coded" PRs
    - human_prototype: mean signal vector of label_class="human-written" PRs (or lowest-scoring unlabeled)

3.2 Sample additional unlabeled merged PRs (N=100, stratified):
    gh pr list --state merged --limit 500 --json number,title,additions,deletions,createdAt,labels

    Stratify by:
    - Size bucket: <50 adds, 50-200, 200-500, 500+
    - Recency: last 3mo, 3-6mo, 6-12mo
    Sample ~25 from each size bucket, spread across time.

3.3 For each sampled PR: repeat Phase 2 steps (fetch diff, run vibe_check, extract signals).

3.4 Classify each by cosine similarity to prototypes:
    - sim(pr_signals, vibe_prototype) vs sim(pr_signals, human_prototype)
    - If ratio > 2.0: pseudo-label as "likely-vibe-coded"
    - If ratio < 0.5: pseudo-label as "likely-human"
    - Otherwise: "ambiguous" (keep but don't use for threshold calibration)

3.5 Output: expanded_dataset.tsv (same columns as signals.tsv + pseudo_label + similarity_ratio)

═══════════════════════════════════════════
PHASE 4: STATISTICAL ANALYSIS (no API calls)
═══════════════════════════════════════════

4.1 Descriptive statistics:
    For each signal, grouped by label_class:
    - N, mean, median, std, IQR, skewness
    - Effect size: Cohen's d between vibe-coded vs human groups
    - Output: descriptive_stats.tsv

4.2 Discrimination analysis:
    For each signal:
    - ROC AUC (binary: vibe-coded vs not)
    - Optimal threshold via Youden's J
    - Sensitivity and specificity at optimal threshold
    - Output: discrimination.tsv

4.3 Bayesian credible intervals:
    For each signal threshold:
    - Use Beta-Binomial model: prior Beta(1,1), update with observed correct/incorrect at threshold
    - Report 90% HDI for sensitivity and specificity
    - Output: bayesian_ci.tsv

4.4 Dataset quality assessment:
    - Class balance: N per label_class
    - Representation: are all PR size buckets covered? All time periods? Multiple authors?
    - Minimum detectable effect: given N, what's smallest Cohen's d detectable at power 0.80?
    - Flag if any stratum has N < 10

4.5 Compare current vibe_check.py thresholds against data-driven optimal thresholds:
    - For each signal: current_threshold vs optimal_threshold vs difference
    - Recommend recalibration if difference > 0.1 for any signal
    - Output: threshold_comparison.tsv

═══════════════════════════════════════════
PHASE 5: OUTPUT PACKAGE
═══════════════════════════════════════════

Produce these files:
1. labeled_prs.tsv — all discovered labeled PRs
2. signals.tsv — signal scores for all analyzed PRs
3. expanded_dataset.tsv — full dataset including pseudo-labels
4. descriptive_stats.tsv — per-signal statistics by class
5. discrimination.tsv — ROC AUC and optimal thresholds
6. bayesian_ci.tsv — credible intervals
7. threshold_comparison.tsv — current vs optimal thresholds
8. dataset_summary.json:
   {
     "total_prs_analyzed": N,
     "labeled_vibe_coded": N,
     "labeled_human": N,
     "pseudo_labeled_vibe": N,
     "pseudo_labeled_human": N,
     "ambiguous": N,
     "languages_observed": [...],
     "signals_with_significant_discrimination": [...],
     "recommended_threshold_changes": {...},
     "dataset_quality_warnings": [...]
   }
9. Summary (under 300 words): key findings, strongest discriminators, recommended changes, dataset gaps.

═══════════════════════════════════════════
ANTI-CASCADE RULES
═══════════════════════════════════════════

- HARD LIMIT: 3000 total API calls. Track with counter variable. Stop when reached.
- HARD LIMIT: 300 total PRs fetched in detail. 
- NO recursive expansion: if a search returns more results, do NOT paginate beyond limit.
- NO retry loops: if an API call fails, log it and move on.
- Prefer batch operations: use --limit and --json flags to get multiple fields per call.
- If labeled PRs < 10: WARN that dataset is too small for reliable calibration. Proceed anyway but set all confidence to LOW in output.
- If any label_class has < 5 PRs: flag as undersampled, do NOT compute stats for that class.

═══════════════════════════════════════════
EXECUTION ORDER
═══════════════════════════════════════════

□ Phase 1 → labeled_prs.tsv
□ Phase 2 → signals.tsv  
□ Phase 3 → expanded_dataset.tsv
□ Phase 4 → all analysis TSVs + dataset_summary.json
□ Phase 5 → summary text

Start now. No preamble.
```
