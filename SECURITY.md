# Security policy for vibe-check

## Scope

This project ships Python scripts. They read code diffs. They call `git` and optionally the GitHub CLI (`gh`). They can append JSON lines to a local telemetry directory. There is no inbound network listener.

## Threat model

#### Hostile diffs

A unified diff is untrusted data. Parsing bugs could theoretically affect the Python process. Treat diffs from unknown senders like any other untrusted file.

#### Secrets in patches

Pull requests and `gh pr diff` output can contain API keys and tokens. They can also contain PII. Reports and JSON echo derived metrics, not full secrets by design. Still treat every diff as potentially sensitive.

#### Telemetry on disk

When `VIBE_CHECK_TELEMETRY_DIR` is set, each run appends a JSON line with scores and metadata. That directory is local only. Set permissions on the directory so other OS users cannot read it on shared machines.

#### GitHub access

`gh` uses your existing auth. Calibration and `--pr` flows can list and fetch many PRs. Use least-privilege tokens and the correct `GH_HOST` for your enterprise.

#### Supply chain

Install Python from a trusted channel. Do not `pip install` random helpers into the same env you use for scoring unless you review them.

## Trust boundaries

| Boundary | What crosses it |
|----------|-----------------|
| Local FS | Diff files, `calibration_override.json`, telemetry JSONL, `outputs/` |
| Subprocess | `git`, `gh` with fixed argument lists (no shell interpolation of diff body) |
| Network | Only through `gh` when you use PR-based modes |

## Do and do not

**Do**

- Run `vibe_check.py` on diffs you are allowed to read.
- Redact before you paste JSON or Markdown into a public ticket.
- Point telemetry at a private directory under your home tree.

**Do not**

- Pipe untrusted shell scripts into `bash` while in the same session as production credentials.
- Commit `outputs/` without review.
- Commit telemetry JSONL without review.
- Commit raw `gh` captures without review.
- Share calibration exports that still contain full PR bodies if your org forbids it.

## Secrets handling

The scorer does not need GitHub tokens inside this repo. If you export `GH_TOKEN` in your shell, keep it out of logs and screen shares.

## Scan results and PR references

`scripts/vibe_detect/` can write `vibe_detect_results.json` with PR numbers and repository paths from wherever you ran it. That file is `.gitignore`d. Do not check it back in. If you must share results, redact the `pr` field first.

## Reporting

Open a GitHub Security Advisory on this repo, or use your organisation's security intake process if you're using this in a corporate context.

Each report should list:

- commit hash of `vibe_check.py`
- command line with secrets removed
- whether the input diff came from a public PR

Owner: repo maintainers. Last reviewed: 2026-05-15.

## Scan findings (2026-05-15)

- No credentials, tokens, or private keys in the working tree or git history (verified by scrub on 2026-05-15).
- No external webhooks, private IPs, or telemetry endpoints baked into code.
- GitHub host and default-repo configuration moved to env vars (`VIBE_DETECT_GH_HOST`, `VIBE_DETECT_DEFAULT_REPO`); no organisation-specific defaults shipped.
- `scripts/vibe_detect/vibe_detect_results.json` is in `.gitignore`, never commit it; PR identifiers can be sensitive depending on context.
