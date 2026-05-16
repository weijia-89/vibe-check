# Token compression (approximate `len(utf8)/4`)

| File | Before (B / tok) | After (B / tok) | Ratio |
|------|------------------|-----------------|-------|
| [vibe-check/SKILL.md](SKILL.md) | 12757 / 3189 | 6610 / 1652 | 0.52 |
| [txtext/SKILL.md](../txtext/SKILL.md) | 5165 / 1291 | 3976 / 994 | 0.77 |
| [skill-sync/SKILL.md](../skill-sync/SKILL.md) | 3429 / 857 | 2972 / 743 | 0.87 |
| [qe-suite/.cursor/skills/qforge/SKILL.md](../qe-suite/.cursor/skills/qforge/SKILL.md) | 6236 / 1559 | 4217 / 1054 | 0.68 |

**T1 flag:** vibe-check dropped ~48% of bytes; removed long GRADE narrative in favor of `references/RESEARCH.md` pointer (no long verbatim user menus removed).

**T6 (meaning pass):** Same imperative flows: run `vibe_check.py` with `--pr` / `--diff` / `--repo-path`; JSON vs markdown; false-positive / false-negative ranges; drift/telemetry bash unchanged; qforge welcome ASCII unchanged vs `main` (see `verify_welcome_fence.py`).
