# Audit priority, ethics, and deployment guardrails

Audience: engineering leads, security, and people partners.
Scope: optional `scripts/review_depth.py` JSON, plus any future merge of similar fields into `vibe_check` pipelines.

## What we measure

Artifact-only signals. Commit count. File touch count. PR body and title heuristics for "why vs what" language. A flag for unusually large single commits.

We do not measure individual "comprehension", IQ, performance ratings, or keystroke surveillance.

## Why wording matters

SE literature (Feitelson 2023, Peitek et al. eye-tracking) shows fluency bias. Polished text increases a reader's confidence without increasing correctness. Any metric that can be read as "how smart is this engineer" creates adversarial dynamics between developers and management. Dunning-Kruger style framing from org psych has a thin RCT bridge to software engineering. Treat it as a cautionary pattern, not a hard law.

## Approved framing

| Do | Don't |
|----|-------|
| "Higher review-depth index suggests a second reviewer or domain expert." | "Low score means a bad engineer." |
| Route PRs by risk and blast radius (files, infra areas). | Rank individuals on a leaderboard. |
| Combine with a human checklist (SRE, security). | Auto-block merge from this JSON alone. |

## Data retention

`review_depth.py` calls `gh` only. There is no new server. Logs are whatever your shell or CI retains. Default behavior is to keep full bodies out of a shared SIEM unless you have a redaction policy.

## Rollback and kill switch

Stop invoking the script. Remove the CI step. Target RTO is under one hour. No schema migrations.

## Owner and review

Assign an owner and an expiry when you enable this in CI. Template: owner `@team`, expiry `YYYY-MM-DD`, kill `remove job step`.

## Evidence posture

Feathers and Fowler. The CLI boundary is a seam. It keeps legacy `vibe_check` behavior unchanged unless you explicitly compose the two.

METR and DORA counterweights apply when you argue for budget for human review. They do not apply when someone wants to automate HR.
