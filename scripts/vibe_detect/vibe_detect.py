#!/usr/bin/env python3
"""
vibe_detect.py — Scan GitHub PRs for deterministic AI vibe-code signals.

Usage:
  python3 vibe_detect.py --prs "owner/repo#1234 owner/repo#5678"
  python3 vibe_detect.py --ledger /path/to/candidate-ledger.jsonl [--min-year 2024]
  python3 vibe_detect.py --prs "owner/repo#N" --playwright   # enable Tier 2b for .spec.ts diffs

Requires: gh CLI authenticated for your target host.
Configure via env: VIBE_DETECT_GH_HOST (default: github.com),
                   VIBE_DETECT_DEFAULT_REPO (optional).
Output: vibe_detect_results.json (gitignored) + markdown table to stdout.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import signals as sig

GITHUB_HOST = os.environ.get("VIBE_DETECT_GH_HOST", "github.com")
DEFAULT_REPO = os.environ.get("VIBE_DETECT_DEFAULT_REPO", "")
OUT_FILE = os.path.join(os.path.dirname(__file__), "vibe_detect_results.json")


# ── GitHub API helpers ──────────────────────────────────────────────────────

def gh(path, host=GITHUB_HOST):
    """Call gh api and return parsed JSON. Raises on error."""
    result = subprocess.run(
        ["gh", "api", "--hostname", host, path],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError("gh api %s failed: %s" % (path, result.stderr.strip()))
    return json.loads(result.stdout)


def fetch_pr(owner_repo, num):
    """Return (pr_body, labels, commit_messages, patch_text, is_playwright)."""
    base = "repos/%s/pulls/%d" % (owner_repo, num)

    pr = gh(base)
    body = pr.get("body") or ""
    labels = [l["name"] for l in pr.get("labels", [])]

    commits = gh(base + "/commits")
    commit_messages = []
    for c in commits:
        msg = c.get("commit", {}).get("message", "")
        commit_messages.append(msg)

    files = gh(base + "/files")
    patches = []
    is_playwright = False
    for f in files:
        fname = f.get("filename", "")
        patch = f.get("patch", "")
        if patch:
            patches.append("--- %s\n%s" % (fname, patch))
        if re.search(r"\.(spec|test)\.(ts|js)$", fname, re.IGNORECASE):
            is_playwright = True

    return body, labels, commit_messages, "\n".join(patches), is_playwright


# ── PR string parsing ───────────────────────────────────────────────────────

def parse_pr_spec(spec):
    """Parse 'owner/repo#NUM' -> (owner/repo, int(NUM))."""
    m = re.match(r"^([\w\-\.]+/[\w\-\.]+)#(\d+)$", spec.strip())
    if not m:
        raise ValueError("Bad PR spec: %r (expected owner/repo#NUM)" % spec)
    return m.group(1), int(m.group(2))


def prs_from_ledger(ledger_path, min_year=2024):
    """Extract (owner_repo, num) from candidate-ledger.jsonl github_prs field."""
    prs = []
    seen = set()
    with open(ledger_path) as f:
        for line in f:
            row = json.loads(line)
            if row.get("year", 0) < min_year:
                continue
            if row.get("verdict") not in ("confirmed_incident", "confirmed_bug_rollback"):
                continue
            for pr_ref in row.get("github_prs", []):
                # pr_ref formats: "#309236", "owner/repo#309236",
                # "#274896 [TICKET-1234] roll back ...", "PR#1072 in other-repo ..."
                m = re.search(r"([\w\-]+/[\w\-]+)?#?(\d{4,})", pr_ref)
                if not m:
                    continue
                repo = m.group(1) or DEFAULT_REPO
                num = int(m.group(2))
                key = "%s#%d" % (repo, num)
                if key not in seen:
                    seen.add(key)
                    prs.append((repo, num, row.get("inc_id", ""), row.get("id", "")))
    return prs


# ── Core scan ──────────────────────────────────────────────────────────────

def scan_pr(owner_repo, num, force_playwright=False, rate_delay=1.0):
    time.sleep(rate_delay)
    pr_label = "%s#%d" % (owner_repo, num)
    print("  scanning %s ..." % pr_label, flush=True)

    try:
        body, labels, commits, diff, is_pw = fetch_pr(owner_repo, num)
    except Exception as e:
        return {
            "pr": pr_label,
            "error": str(e),
            "tier1_hits": [], "tier2_hits": [], "tier2b_hits": [], "tier3_hits": [],
            "score": 0.0, "verdict": "error"
        }

    use_playwright = is_pw or force_playwright
    t1 = sig.tier1_metadata(body, commits, labels)
    t2 = sig.tier2_diff(diff)
    t2b = sig.tier2b_playwright(diff) if use_playwright else []
    t3 = sig.tier3_body(body)
    s, verdict = sig.score(t1, t2, t2b, t3)

    return {
        "pr": pr_label,
        "tier1_hits": t1,
        "tier2_hits": t2,
        "tier2b_hits": t2b,
        "tier3_hits": t3,
        "score": s,
        "verdict": verdict,
        "playwright_files": use_playwright,
    }


# ── Output ──────────────────────────────────────────────────────────────────

def print_table(results):
    cols = ["PR", "Score", "Verdict", "T1", "T2", "T2b", "T3"]
    rows = []
    for r in results:
        rows.append([
            r["pr"],
            "%.4f" % r.get("score", 0),
            r.get("verdict", "error"),
            "; ".join(r.get("tier1_hits", [])) or "—",
            "; ".join(r.get("tier2_hits", [])) or "—",
            "; ".join(r.get("tier2b_hits", [])) or "—",
            "; ".join(r.get("tier3_hits", [])) or "—",
        ])

    widths = [max(len(cols[i]), max((len(row[i]) for row in rows), default=0)) for i in range(len(cols))]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    header = "| " + " | ".join(cols[i].ljust(widths[i]) for i in range(len(cols))) + " |"

    print("\n" + header)
    print(sep)
    for row in rows:
        print("| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(cols))) + " |")

    strong = [r for r in results if r.get("verdict") == "strong"]
    moderate = [r for r in results if r.get("verdict") == "moderate"]
    weak = [r for r in results if r.get("verdict") == "weak"]
    print("\nSummary: %d strong | %d moderate | %d weak | %d no_signal | %d error" % (
        len(strong), len(moderate), len(weak),
        len([r for r in results if r.get("verdict") == "no_signal"]),
        len([r for r in results if r.get("verdict") == "error"]),
    ))


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Detect AI vibe-code signals in GitHub PRs")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prs", help='Space-separated list of "owner/repo#NUM" specs')
    group.add_argument("--ledger", help="Path to candidate-ledger.jsonl")
    parser.add_argument("--min-year", type=int, default=2024, help="Skip ledger rows before this year")
    parser.add_argument("--playwright", action="store_true", help="Force Tier 2b Playwright signals on all PRs")
    parser.add_argument("--out", default=OUT_FILE, help="Output JSON path")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between API calls")
    args = parser.parse_args()

    pr_specs = []  # list of (owner_repo, num, inc_id, ledger_id)
    if args.prs:
        for spec in args.prs.split():
            repo, num = parse_pr_spec(spec)
            pr_specs.append((repo, num, "", ""))
    else:
        pr_specs = prs_from_ledger(args.ledger, args.min_year)

    if not pr_specs:
        print("No PRs to scan.", file=sys.stderr)
        sys.exit(1)

    print("Scanning %d PRs..." % len(pr_specs))
    results = []
    for repo, num, inc_id, ledger_id in pr_specs:
        r = scan_pr(repo, num, force_playwright=args.playwright, rate_delay=args.delay)
        r["inc_id"] = inc_id
        r["ledger_id"] = ledger_id
        results.append(r)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults written to %s" % args.out)

    print_table(results)


if __name__ == "__main__":
    main()
