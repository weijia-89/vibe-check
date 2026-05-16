#!/usr/bin/env python3
"""
PR audit-priority metadata via gh (no diff scoring).

Outputs JSON only — keeps separation from vibe_check.py (Feathers seam).
Default-off: only runs when invoked explicitly.

Usage:
  python3 scripts/review_depth.py --pr 123 [--repo owner/name]
  python3 scripts/review_depth.py --pr 456 --repo myorg/myrepo
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def gh_json(repo, rest):
    cmd = ["gh"] + rest
    if repo:
        cmd.extend(["--repo", repo])
    out = subprocess.check_output(cmd, text=True, timeout=60)
    return json.loads(out)


def score_why_vs_what(body: str, title: str) -> float:
    """Heuristic 0..1: higher if prose looks like rationale vs changelog."""
    text = f"{title}\n{body or ''}".lower()
    if len(text.strip()) < 40:
        return 0.35
    why_markers = sum(
        1
        for w in (
            "because",
            "therefore",
            "trade-off",
            "tradeoff",
            "risk",
            "rollback",
            "why",
            "motivation",
            "context",
            "incident",
            "customer",
            "latency",
            "security",
        )
        if w in text
    )
    what_markers = sum(
        1
        for w in (
            "add",
            "update",
            "implement",
            "new endpoint",
            "this pr",
            "changes:",
            "changelog",
        )
        if w in text
    )
    raw = (why_markers + 1) / (what_markers + why_markers + 2)
    return max(0.0, min(1.0, raw))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", required=True, help="PR number or owner/repo#num")
    ap.add_argument("--repo", default=None, help="owner/name for gh when cwd repo is wrong")
    args = ap.parse_args()
    pr = args.pr
    try:
        data = gh_json(
            args.repo,
            [
                "pr",
                "view",
                pr,
                "--json",
                "number,title,body,additions,deletions,commits,files,author,mergedAt,createdAt",
            ],
        )
    except subprocess.CalledProcessError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

    commits = data.get("commits") or []
    n_commits = len(commits)
    bodies = [((c.get("messageBody") or "") + (c.get("messageHeadline") or "")) for c in commits]
    large_dump = 1 if any(len(b) > 4000 for b in bodies) else 0
    incremental = 1 if n_commits >= 3 else 0

    files = data.get("files") or []
    n_files = len(files)
    paths = [f.get("path", "") for f in files if isinstance(f, dict)]

    out = {
        "schema": "vibe_check.review_depth.v1",
        "pr": data.get("number"),
        "title": data.get("title"),
        "audit_priority": {
            "commit_count": n_commits,
            "incremental_commits_hint": bool(incremental),
            "single_large_commit_hint": bool(large_dump),
            "files_touched": n_files,
            "why_vs_what_body_score": round(score_why_vs_what(data.get("body") or "", data.get("title") or ""), 3),
        },
        "lines_changed": (data.get("additions") or 0) + (data.get("deletions") or 0),
        "author": (data.get("author") or {}).get("login"),
        "paths_sample": paths[:25],
        "disclaimer": "Heuristic artifact scores only — not employment or competence metrics.",
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
