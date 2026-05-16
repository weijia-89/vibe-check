# vibe_detect (revert-report batch scanner)

Deterministic GitHub PR scanner used for incident / falsification workflows (FC-3). Migrated from `ai-governance/revert-report/vibe-detect/`.

```bash
cd "$(dirname "$0")"
python3 vibe_detect.py --prs "owner/repo#123"
# or
python3 vibe_detect.py --ledger /path/to/candidate-ledger.jsonl --min-year 2024
```

Results append to `vibe_detect_results.json` in this directory (see `OUT_FILE` in `vibe_detect.py`). For diff-only scoring of a single patch, prefer **`../vibe_check.py`**.
