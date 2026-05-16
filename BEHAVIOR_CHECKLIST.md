# Pre-release verification checklist

> **Why this file changed (v0.2.0).** Previously this file was a list of pre-checked `[x]`
> items with no automation behind them — performative compliance. It now lists the exact
> commands a contributor must run before opening a PR or cutting a release. Every item must
> exit zero. Nothing here is pre-checked; agents and humans must run the commands and copy
> the success line into the PR body.

## Pre-PR gate (every contributor)

Run all five. Each must exit zero.

```bash
# 1. Unit tests — covers v0.2.0 regressions for the analyzer fixes.
python -m unittest tests/test_analyzers.py

# 2. Integration smoke — exercises every CLI shape, enforces no-aggregate contract.
bash tests/test_skill_smoke.sh

# 3. Citation reachability lint (Mode A).
python scripts/check_claims.py

# 4. Citation quote enforcement (Mode B). Strict.
python scripts/check_claims.py --strict-quotes

# 5. Dogfood — run vibe_check on its own source. Sanity check that
#    edge_case_depth has not regressed to its v0.1.x monotonic-increment bug.
(printf '%s\n' '+++ b/scripts/vibe_check.py' '@@ -0,0 +1,9999 @@'; \
  sed 's/^/+/' scripts/vibe_check.py) \
  | python scripts/vibe_check.py --format json \
  | python -c "import json,sys; d=json.load(sys.stdin); \
    s = next(s for s in d['file_analyses'][0]['signals'] if s['name']=='edge_case_depth'); \
    depth=int(s['explanation'].split('Depth=')[1].split(',')[0]); \
    assert depth < 12, f'edge_case_depth regressed: {depth} >= 12'"
```

If you want one command:

```bash
python -m unittest tests/test_analyzers.py && \
  bash tests/test_skill_smoke.sh && \
  python scripts/check_claims.py --strict-quotes
```

## Release gate (cut a tag)

Beyond the pre-PR gate:

- [ ] CHANGELOG.md has an entry for the new version with `### Added`, `### Changed`, `### Removed`, and `### Notes for callers` sections as appropriate.
- [ ] `CALIBRATION_VERSION` in `scripts/vibe_check.py` is bumped if `SIGNAL_THRESHOLDS` or default `WEIGHTS` changed in a backwards-incompatible way.
- [ ] If `CALIBRATION_VERSION` changed, the legacy synonym set in `load_calibration_overrides()` is updated so existing user calibrations don't silently break.
- [ ] Every new arXiv reference in prose has a row in `references/CLAIMS.md` with a literal abstract quote and an `accessed` date.
- [ ] If any signal weight or threshold default was changed, `references/CALIBRATION_NOTES.md` reflects the new value and explains the empirical or principled basis (or labels it speculative).
- [ ] No new pip dependency. Stdlib only. CI step `Verify stdlib-only` will fail otherwise.

## Cross-skill compatibility (only if the skill is bundled with others)

- [ ] `SKILL.md` frontmatter `name:` is unique among the bundled skills.
- [ ] `SKILL.md` description triggers a non-trivial subset of the project keywords (vibe check, AI-generated code, hallucinated APIs, etc.).

## What's deliberately NOT here

- Subjective taste checks ("does the prose feel good"). Use `deai` skill or peer review.
- Anything that requires trusting the author's word — every checkbox above can be verified by running a command.
- Pre-checked items. If you check a box, paste the command output into the PR body.
