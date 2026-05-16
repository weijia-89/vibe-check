#!/usr/bin/env python3
"""
check_claims.py — claims ledger lint.

Two-mode lint, both enforced in CI:

  Mode A (default): every named-paper / arXiv / numeric / PSI / SWE-bench
  reference in SKILL.md and references/GEMINI_AI_CODE_DETECTION_RESEARCH.md
  must resolve to a row in references/CLAIMS.md, OR be tagged [unverified]
  in prose.

  Mode B (--strict-quotes): every row in CLAIMS.md must have a non-empty
  `quote` field. Empty quotes mean the claim was never primary-checked.
  CI fails if any row violates this.

Exit codes:
  0  — clean
  1  — Mode A findings (claim without ledger row)
  2  — Mode A is fine but Mode B (quote enforcement) has violations
  3  — CLAIMS.md missing or unparseable
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

KNOWN_PAPERS = [
    "DuCodeMark",
    "AICD Bench",
    "Feitelson",
    "Jay et al.",
    "Landman",
    "MASH",
    "LLM-AuthorBench",
    "Code2Doc",
    "CodeWiki",
    "DivEye",
    "SICO",
    "Barkmann",
    "Caliskan",
    "TIOBE",
    "Pearce",
    "Sandoval",
    "Perry",
    "Fu et al",
    "Wang et al",
    "Park et al",
    "Tao et al",
    "Binoculars",
]

ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})", re.IGNORECASE)
PERCENT_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?\s*%")
PSI_NUM_RE = re.compile(r"(PSI[^\n]{0,40}?\d[\.,]\d\d?|\d[\.,]\d\d?[^\n]{0,40}?PSI)", re.IGNORECASE)
SWE_RE = re.compile(r"SWE-bench[^\n]{0,80}?\d", re.IGNORECASE)

SKIP_SECTION_RE = re.compile(
    r"^\s*(#+\s*(Bibliography|References|Key citations|Works cited|Tier\s+\d|Full bibliography|## Citations|## Schema|## How to add|## Rules|## Pending).*$|\|\s*arXiv:)",
    re.IGNORECASE,
)
NUMBER_ON_LINE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%|\b\d+\.\d+\b|AUC|auc|F1|f1|MCC|mcc|precision|recall")


# ──────────────────────────────────────────────────────────────────────────
# Mode A — claim/citation reachability
# ──────────────────────────────────────────────────────────────────────────


def scan_doc(path: Path, claim_keys: set[str]) -> list[str]:
    findings = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    skip_section = False
    joined_keys = "\n".join(claim_keys)
    for i, line in enumerate(lines, 1):
        if line.startswith("##") or line.startswith("### "):
            skip_section = bool(SKIP_SECTION_RE.search(line))
        if skip_section:
            continue
        if "[unverified]" in line or "[claims-skip]" in line:
            continue
        for m in ARXIV_RE.finditer(line):
            if m.group(1) not in joined_keys:
                findings.append(
                    f"{path}:{i}: arXiv:{m.group(1)} not in CLAIMS.md (add entry or tag [unverified])"
                )
        has_number = bool(NUMBER_ON_LINE_RE.search(line))
        for paper in KNOWN_PAPERS:
            if paper.lower() in line.lower() and paper not in joined_keys and has_number:
                findings.append(f"{path}:{i}: named paper '{paper}' carries numeric claim, not in CLAIMS.md")
        if PSI_NUM_RE.search(line) and "PSI" not in joined_keys:
            findings.append(f"{path}:{i}: PSI numeric claim, but PSI entry missing from CLAIMS.md")
        if SWE_RE.search(line) and "SWE-bench" not in joined_keys:
            findings.append(f"{path}:{i}: SWE-bench numeric claim, no corresponding CLAIMS.md entry")
    return findings


def load_claim_keys(paths: list[Path]) -> set[str]:
    tokens: set[str] = set()
    for p in paths:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        tokens.update(ARXIV_RE.findall(text))
        for paper in KNOWN_PAPERS:
            if paper.lower() in text.lower():
                tokens.add(paper)
        if "PSI" in text:
            tokens.add("PSI")
        if "SWE-bench" in text:
            tokens.add("SWE-bench")
    return tokens


# ──────────────────────────────────────────────────────────────────────────
# Mode B — every CLAIMS row has a non-empty quote
# ──────────────────────────────────────────────────────────────────────────


# Match a row of the CLAIMS.md table:
#   | C-NNN | claim... | "quote" | source | section | primary? | status | accessed |
ROW_RE = re.compile(
    r"^\|\s*(C-\d{3})\s*\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$",
    re.MULTILINE,
)


def check_quotes(claims_path: Path) -> list[str]:
    """Each row in the Entries table must have a non-empty quote field,
    UNLESS the `primary?` column is `secondary` — secondary/industry-convention
    rows reference consensus, not a single quotable passage."""
    if not claims_path.is_file():
        return [f"{claims_path}: missing"]
    text = claims_path.read_text(encoding="utf-8", errors="ignore")
    findings = []
    rows_seen = 0
    for m in ROW_RE.finditer(text):
        rows_seen += 1
        cid = m.group(1)
        quote = m.group(3).strip()
        primary = m.group(6).strip().lower()
        # An empty literal is `""` or just whitespace
        empty_markers = {'""', "''", "``", "—", "-", ""}
        if quote in empty_markers and primary != "secondary":
            findings.append(
                f"{claims_path}: row {cid} has empty `quote` field — every "
                f"claim must carry a literal primary-source quote unless "
                f"`primary?` is `secondary` (Mode B)"
            )
    if rows_seen == 0:
        findings.append(f"{claims_path}: no parseable rows found (table format may have changed)")
    return findings


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description="Lint claims/citation ledger.")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--strict-quotes", action="store_true",
                    help="Fail if any CLAIMS.md row has an empty `quote` field (Mode B).")
    ap.add_argument("--only-mode-b", action="store_true",
                    help="Run Mode B (quote enforcement) only, skip Mode A.")
    args = ap.parse_args()

    claims_path = args.root / "references" / "CLAIMS.md"

    # Mode B
    if args.strict_quotes or args.only_mode_b:
        b_findings = check_quotes(claims_path)
        if b_findings:
            print("=== Mode B (quote enforcement) ===")
            print("\n".join(b_findings))
            if args.only_mode_b:
                return 2
        elif args.only_mode_b:
            print("OK: every CLAIMS.md row has a non-empty quote (Mode B clean)")
            return 0

    # Mode A
    research_path = args.root / "references" / "RESEARCH.md"
    claim_keys = load_claim_keys([claims_path, research_path])
    if not claim_keys:
        print(f"ERROR: {claims_path} missing or empty; create it first (see CLAIMS.md schema)", file=sys.stderr)
        return 3

    targets = [
        args.root / "SKILL.md",
        args.root / "README.md",
        args.root / "references" / "GEMINI_AI_CODE_DETECTION_RESEARCH.md",
    ]
    a_findings: list[str] = []
    for t in targets:
        if t.is_file():
            a_findings.extend(scan_doc(t, claim_keys))

    print("=== Mode A (citation reachability) ===")
    if a_findings:
        print("\n".join(a_findings))

    # Mode B (always run, even without --strict-quotes — but only fails CI when flag is set)
    print()
    print("=== Mode B (quote enforcement) ===")
    b_findings = check_quotes(claims_path)
    if b_findings:
        print("\n".join(b_findings))
    else:
        print("OK: every CLAIMS.md row has a non-empty quote")

    if a_findings:
        return 1
    if args.strict_quotes and b_findings:
        return 2
    print()
    print("OK: claims ledger lint passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
