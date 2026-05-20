# gh CLI response fixtures

Real captures and synthetic-augmented variants used by `tests/test_gh_integration.py` to exercise `calibration_pipeline.py`'s gh-CLI-dependent functions (`phase1`, `fetch_pr_detail`, `run_vibe`).

These fixtures replace the inline synthetic JSON the tests used in PR #2. The motivations are:

- **Schema contract documentation.** The real captures are living docs of what `gh` actually returns under the `--json` field selectors used by `calibration_pipeline.py`. If gh's schema drifts in a future major version, the diff against these files makes the breakage obvious.
- **Realistic shape exercise.** Real captures include fields the inline synthetic helpers happened to omit (e.g. `id`, `color` on label objects; `is_bot`, `name` on author objects; full `authors[]` arrays with `email` and `id` on commits). The code under test reads only specific fields, so a thin synthetic happens to satisfy it — but a thin synthetic also fails to demonstrate the contract.
- **Reproducibility.** Anyone debugging a test failure can re-run the capture command at the top of each file's section below and compare.

The captures never round-trip through network at test time. Tests load these files via `Path(__file__).parent / "fixtures" / "gh_responses" / "<name>"`.

## Real captures (verbatim from `cli/cli` @ 2026-05-19)

`cli/cli` was chosen as the capture source because it is the gh CLI's own repository — meta-canonical for gh schema. The captures were taken on 2026-05-19 against the public GitHub `cli/cli` repo using `gh` v2.x.

| File | Capture command |
|---|---|
| `label_list_real_clicli.json` | `gh label list --repo cli/cli --limit 40 --json name,description` |
| `pr_list_real_clicli.json` | `gh pr list --repo cli/cli --limit 5 --state merged --json number,title,author,createdAt,mergedAt,additions,deletions,changedFiles,commits,labels` |
| `pr_diff_real_clicli.diff` | `gh pr diff 13444 --repo cli/cli --color=never` |
| `pr_view_commits_real_clicli.json` | `gh pr view 13444 --repo cli/cli --json commits` |

PR 13444 was picked because it is a small docs-only PR (8-line diff, 1 commit), keeping the fixture small and reviewable while still exercising the full schema.

## Synthetic-augmented captures

Real production repos in 2026 rarely have explicit `vibe-coded` / `ai-assisted` / `human-written` labels (the very thing `calibration_pipeline.py` was built to consume). To exercise `classify_label`'s vibe/ai/human classification paths, we need fixtures with those label names. The synthetic-augmented files below use the **same JSON shape** as the real captures, but with label names and PR data crafted to hit specific classification paths.

| File | Purpose |
|---|---|
| `label_list_synthetic_single_vibe.json` | 1 label named `vibe-coded` for the simple happy-path test |
| `label_list_synthetic_vibe_plus_ai.json` | 2 labels (`vibe-coded`, `ai-assisted`) for the priority-resolution test |
| `label_list_synthetic_no_match.json` | 3 labels (`bug`, `feature`, `documentation`) all classified as `ignore` |
| `pr_list_synthetic_single.json` | 1 synthetic PR (number 42) for happy-path scenarios |
| `pr_list_synthetic_dual_labeled.json` | 1 synthetic PR (number 99) that appears under two label queries; tests label-priority resolution |

The synthetic PRs use real-shape author and commit objects (`id`, `is_bot`, `authors[]` with `email`/`id`, `oid`) so the schema contract is preserved.

## Re-capturing

To refresh the real captures (e.g. after a gh major version bump):

```
cd tests/fixtures/gh_responses
gh label list --repo cli/cli --limit 40 --json name,description > /tmp/raw_labels.json
gh pr list --repo cli/cli --limit 5 --state merged \
  --json number,title,author,createdAt,mergedAt,additions,deletions,changedFiles,commits,labels \
  > /tmp/raw_prs.json
gh pr diff 13444 --repo cli/cli --color=never > pr_diff_real_clicli.diff
gh pr view 13444 --repo cli/cli --json commits > /tmp/raw_commits.json
python3 -c "import json,pathlib; p=pathlib.Path('/tmp/raw_labels.json'); pathlib.Path('label_list_real_clicli.json').write_text(json.dumps(json.loads(p.read_text()),indent=2)+chr(10))"
# repeat the python one-liner for raw_prs.json and raw_commits.json
```

If PR 13444 has been deleted or amended by the time you re-capture, pick another small merged PR with at least 1 commit and update this README + the file name to match.

## Why not capture from `weijia-89/vibe-check`?

The own repo only has 2 PRs and lacks the label diversity needed to exercise `classify_label` exhaustively. `cli/cli` provides a richer label set (40 labels covering bug, enhancement, docs, dependencies, gh-subcommand-specific tags, etc.) — every one of which classifies as `ignore` under the current rules, which is exactly the realistic-shape case worth fixturing.
