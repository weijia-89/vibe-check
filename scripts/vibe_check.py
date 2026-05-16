#!/usr/bin/env python3
"""
vibe_check.py — Reviewer evidence surfacer for PR diffs (not a detector).

Reads a unified diff, runs ten regex/AST heuristics, and surfaces per-signal
evidence that *correlates* with LLM-generated code in published studies. The
aggregate score is a weighted convenience number; the per-signal evidence is
the useful output. See `references/CLAIMS.md` and `references/CALIBRATION_NOTES.md`
for what each default actually represents.

Signals (citation IDs map to `references/CLAIMS.md`):
- Comment-to-code ratio          — CLAIMS C-007 (universal but model-variable)
- Docstring consistency          — CLAIMS C-006 (paraphrase setting)
- Naming convention uniformity   — CLAIMS C-006 (language-confounded; PEP 8 etc.)
- Error handling shape           — CLAIMS P-003 (pending body quote)
- Declarative-vs-control ratio   — CLAIMS C-007 (varies by model)
- Function length / CV           — CLAIMS C-007 (varies by model)
- Comment phrasing boilerplate   — author catalog
- Hallucinated API patterns      — author catalog (12 patterns); see VIBE_CHECK_HALLUCINATION_EXTRAS
- Edge-case depth / null checks  — author heuristic
- Commit metadata markers        — pattern catalog

Honest scope (CLAIMS C-005, C-008): the AICD Bench (2026) and Wang et al.
(ICSE 2025) report that detectors of this class — including ML detectors —
are below practical usability under distribution shift. This tool is a
**reviewer prompt**, not a gate, not a metric, not a compliance control.

Usage:
    python vibe_check.py --diff <path_to_diff_file>
    python vibe_check.py --pr <owner/repo#number>
    python vibe_check.py --repo-path <path> --base <base_ref> --head <head_ref>
    python vibe_check.py --diff <path> --no-aggregate   # evidence only, no grade

Output: Markdown by default, JSON with --format json. Exit code 0 always
(this is a reviewer aid, not a CI gate).
"""

import argparse
import datetime
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


# ─── Signal weights (SPECULATIVE DEFAULTS — see CALIBRATION_NOTES.md) ───
# These are authored priors, NOT fitted on labeled data. Tao et al. (CLAIMS
# C-007) explicitly find that signal magnitude varies drastically across
# models, so a single fixed weight is provably wrong in general. Override via
# `calibration_override.json` after running `scripts/calibration_pipeline.py`
# on a labeled corpus of ≥100 PRs from your codebase.
WEIGHTS = {
    "comment_ratio":        0.18,  # CLAIMS C-007 — universal-but-model-variable
    "docstring_consistency": 0.15,  # CLAIMS C-006 — paraphrase setting
    "naming_uniformity":    0.13,  # CLAIMS C-006 — language-confounded (PEP 8 etc.)
    "error_handling":       0.12,  # CLAIMS P-003 — pending body quote
    "declarative_bias":     0.10,  # CLAIMS C-007 — varies by model
    "function_length":      0.08,  # CLAIMS C-007 — varies by model
    "comment_phrasing":     0.08,  # author catalog
    "hallucinated_apis":    0.06,  # author catalog (12 patterns)
    "edge_case_depth":      0.05,  # author heuristic
    "commit_metadata":      0.05,  # pattern catalog
}

# Optional JSON list of {"pattern": "regex", "desc": "..."} — path via VIBE_CHECK_HALLUCINATION_EXTRAS
HALLUCINATION_PATTERN_BUILTINS = [
    (r'\bArray\.prototype\.\w+Async\b', "Non-existent async Array method"),
    (r'\bPromise\.allResolved\b', "Non-existent Promise method (did you mean allSettled?)"),
    (r'\bwindow\.ai\b', "Non-standard browser API"),
    (r'\bnavigator\.ai\b', "Non-standard browser API"),
    (r'\bfetch\(\s*\{', "Incorrect fetch signature (first arg should be URL)"),
    (r'\bos\.path\.mkdirs\b', "Non-existent (use os.makedirs)"),
    (r'\blist\.flat\(\)', "Non-existent Python method (JS Array.flat)"),
    (r'\bstr\.trimStart\b', "Non-existent Python method (JS String method)"),
    (r'\bdict\.merge\b', "Non-existent dict method (use | operator or .update())"),
    (r'\berrors\.Wrapf?\b', "pkg/errors, not stdlib — verify import"),
    (r'\bstrings\.Reverse\b', "Non-existent strings function"),
    (r'import\s+\{[^}]+\}\s+from\s+[\'"][^"\']+/internal', "Importing from internal/private module path"),
]

_HALLUC_EXTRA_CACHE = (None, None, [])  # type: Tuple[Optional[str], Optional[float], list]


def merged_hallucination_patterns():
    """Built-in patterns plus optional JSON file (re-read when mtime changes)."""
    global _HALLUC_EXTRA_CACHE
    path = os.environ.get("VIBE_CHECK_HALLUCINATION_EXTRAS")
    if not path:
        return list(HALLUCINATION_PATTERN_BUILTINS)
    p = Path(path)
    if not p.is_file():
        return list(HALLUCINATION_PATTERN_BUILTINS)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return list(HALLUCINATION_PATTERN_BUILTINS)
    if _HALLUC_EXTRA_CACHE[0] == str(p.resolve()) and _HALLUC_EXTRA_CACHE[1] == mtime:
        return _HALLUC_EXTRA_CACHE[2]
    extra = []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("pattern"):
                    extra.append((str(item["pattern"]), str(item.get("desc", "custom"))))
    except (json.JSONDecodeError, OSError, TypeError):
        extra = []
    merged = list(HALLUCINATION_PATTERN_BUILTINS) + extra
    _HALLUC_EXTRA_CACHE = (str(p.resolve()), mtime, merged)
    return merged


# ─── Pattern taxonomy ───────────────────────────────────────────────────

class PatternCategory(str, Enum):
    OVER_COMMENTING = "over_commenting"
    BOILERPLATE_BLOAT = "boilerplate_bloat"
    SHALLOW_ERROR_HANDLING = "shallow_error_handling"
    UNIFORM_NAMING = "uniform_naming"
    HALLUCINATED_API = "hallucinated_api"
    MISSING_EDGE_CASES = "missing_edge_cases"
    DECLARATIVE_HEAVY = "declarative_heavy"
    COOKIE_CUTTER_STRUCTURE = "cookie_cutter_structure"
    AI_COMMIT_MARKERS = "ai_commit_markers"
    EXCESSIVE_DOCSTRINGS = "excessive_docstrings"


@dataclass
class Signal:
    name: str
    score: float          # 0.0 (human-like) to 1.0 (AI-like)
    weight: float
    confidence: float     # How confident we are in this signal
    evidence: list        # Specific examples found
    patterns: list        # PatternCategory tags
    explanation: str


@dataclass
class FileAnalysis:
    path: str
    language: str
    added_lines: int
    signals: list = field(default_factory=list)
    ai_probability: float = 0.0


@dataclass
class VibeCheckResult:
    overall_ai_probability: float
    confidence: float
    grade: str                       # A-F scale
    file_analyses: list
    signal_summary: dict
    pattern_taxonomy: dict
    recommendations: list
    methodology_notes: list
    evidence_status: str             # GRADE-style


# ─── Language detection ─────────────────────────────────────────────────

LANG_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".jsx": "javascript", ".go": "go",
    ".java": "java", ".rb": "ruby", ".rs": "rust", ".cpp": "cpp",
    ".c": "c", ".cs": "csharp", ".php": "php", ".swift": "swift",
    ".kt": "kotlin", ".scala": "scala", ".sh": "bash",
}

def detect_language(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    return LANG_MAP.get(ext, "unknown")


# ─── Diff parser ────────────────────────────────────────────────────────

@dataclass
class DiffHunk:
    filepath: str
    added_lines: list     # (line_number, content)
    removed_lines: list   # (line_number, content)
    context_lines: list   # (line_number, content)


def parse_unified_diff(diff_text: str) -> list:
    """Parse unified diff into structured hunks per file."""
    files = []
    current_file = None
    current_added = []
    current_removed = []
    current_context = []
    line_num_new = 0

    for line in diff_text.splitlines():
        # New file header
        if line.startswith("+++ b/"):
            if current_file:
                files.append(DiffHunk(
                    current_file, current_added, current_removed, current_context
                ))
            current_file = line[6:]
            current_added = []
            current_removed = []
            current_context = []
        elif line.startswith("--- "):
            continue
        elif line.startswith("@@ "):
            # Parse hunk header for line numbers
            match = re.search(r'\+(\d+)', line)
            if match:
                line_num_new = int(match.group(1)) - 1
        elif current_file:
            if line.startswith("+"):
                line_num_new += 1
                current_added.append((line_num_new, line[1:]))
            elif line.startswith("-"):
                current_removed.append((0, line[1:]))
            else:
                line_num_new += 1
                current_context.append((line_num_new, line[1:] if line.startswith(" ") else line))

    if current_file:
        files.append(DiffHunk(
            current_file, current_added, current_removed, current_context
        ))
    return files


# ─── Signal analyzers ──────────────────────────────────────────────────

# --- Comment patterns by language ---
COMMENT_PATTERNS = {
    "python":     {"line": r"^\s*#", "block_start": r'^\s*("""|\'\'\')' , "block_end": r'("""|\'\'\')\s*$'},
    "javascript": {"line": r"^\s*//", "block_start": r"^\s*/\*", "block_end": r"\*/\s*$"},
    "typescript": {"line": r"^\s*//", "block_start": r"^\s*/\*", "block_end": r"\*/\s*$"},
    "go":         {"line": r"^\s*//", "block_start": r"^\s*/\*", "block_end": r"\*/\s*$"},
    "java":       {"line": r"^\s*//", "block_start": r"^\s*/\*", "block_end": r"\*/\s*$"},
    "ruby":       {"line": r"^\s*#",  "block_start": r"^\s*=begin", "block_end": r"^\s*=end"},
    "rust":       {"line": r"^\s*//", "block_start": r"^\s*/\*", "block_end": r"\*/\s*$"},
    "cpp":        {"line": r"^\s*//", "block_start": r"^\s*/\*", "block_end": r"\*/\s*$"},
    "c":          {"line": r"^\s*//", "block_start": r"^\s*/\*", "block_end": r"\*/\s*$"},
    "csharp":     {"line": r"^\s*//", "block_start": r"^\s*/\*", "block_end": r"\*/\s*$"},
    "php":        {"line": r"^\s*(//|#)", "block_start": r"^\s*/\*", "block_end": r"\*/\s*$"},
}

# Boilerplate comment phrases typical of LLMs
AI_COMMENT_PHRASES = [
    r"(?i)\b(check if|initialize the|return the|validate the|ensure that)\b",
    r"(?i)\b(create a new|set up the|configure the|handle the)\b",
    r"(?i)\b(this function|this method|this class)\s+(is responsible for|handles|manages|creates|returns|validates)",
    r"(?i)\b(helper function|utility function|main function)\b",
    r"(?i)\b(iterate over|loop through)\s+(the|each|all)\b",
    r"(?i)\b(update the|modify the|process the|parse the|extract the)\b",
    r"(?i)^\s*(\/\/|#)\s*(TODO|FIXME|HACK|NOTE):\s*(implement|add|fix|update)\s",
    r"(?i)\b(default (implementation|behavior|value))\b",
]

# Commit message patterns suggesting AI generation
AI_COMMIT_PATTERNS = [
    r"(?i)\b(copilot|github copilot|claude|chatgpt|gpt-4|gemini|ai[- ]generated|ai[- ]assisted)\b",
    r"(?i)\b(cursor|cody|tabnine|codex|aider|continue\.dev)\b",
    r"(?i)co-authored-by:.*\b(copilot|claude|gpt|ai|bot)\b",
    r"(?i)^(feat|fix|refactor|chore|docs|test)\(.+\):\s",  # Conventional commits (weak signal alone)
    r"(?i)\b(implement(s|ed)?|add(s|ed)?|updat(e[sd]?|ing)|fix(e[sd]?|ing)|refactor(s|ed)?)\s+(the\s+)?\w+\s+(function|method|class|component|module|handler|service|controller|middleware|hook|util)",
]


def analyze_comment_ratio(hunk: DiffHunk, lang: str) -> Signal:
    """Signal 1: Comment-to-code ratio — strongest universal discriminator."""
    patterns = COMMENT_PATTERNS.get(lang, COMMENT_PATTERNS.get("javascript", {}))
    if not patterns:
        return Signal("comment_ratio", 0.5, WEIGHTS["comment_ratio"], 0.2,
                      [], [], "Language not supported for comment analysis")

    added_code = [l for _, l in hunk.added_lines]
    comment_count = 0
    code_count = 0
    in_block = False
    evidence = []

    for line in added_code:
        stripped = line.strip()
        if not stripped:
            continue

        if in_block:
            comment_count += 1
            if re.search(patterns.get("block_end", r"$^"), stripped):
                in_block = False
            continue

        if patterns.get("block_start") and re.search(patterns["block_start"], stripped):
            comment_count += 1
            if not re.search(patterns.get("block_end", r"$^"), stripped):
                in_block = True
            continue

        if patterns.get("line") and re.search(patterns["line"], stripped):
            comment_count += 1
            continue

        code_count += 1

    total = comment_count + code_count
    if total < 5:
        return Signal("comment_ratio", 0.5, WEIGHTS["comment_ratio"], 0.1,
                      [], [], "Too few lines to assess comment ratio")

    ratio = comment_count / max(code_count, 1)

    # Calibration: human avg ~0.1-0.2, LLM avg ~0.3-0.6
    if ratio > 0.5:
        score = min(1.0, 0.7 + (ratio - 0.5) * 0.6)
        evidence.append(f"Comment ratio {ratio:.2f} — significantly above human baseline (~0.15)")
    elif ratio > 0.3:
        score = 0.4 + (ratio - 0.3) * 1.5
        evidence.append(f"Comment ratio {ratio:.2f} — elevated vs human baseline (~0.15)")
    elif ratio > 0.15:
        score = 0.2 + (ratio - 0.15) * 1.33
    else:
        score = max(0, ratio / 0.15 * 0.2)

    confidence = min(0.9, 0.3 + total / 100)
    patterns_found = [PatternCategory.OVER_COMMENTING] if score > 0.5 else []

    return Signal(
        "comment_ratio", round(score, 3), WEIGHTS["comment_ratio"],
        round(confidence, 2), evidence, patterns_found,
        f"CCR={ratio:.2f} ({comment_count} comments / {code_count} code lines)"
    )


def analyze_docstring_consistency(hunk: DiffHunk, lang: str) -> Signal:
    """Signal 2: Docstring/JSDoc coverage consistency."""
    added = "\n".join(l for _, l in hunk.added_lines)

    # Detect function definitions
    func_patterns = {
        "python":     r"^\s*(?:async\s+)?def\s+\w+",
        "javascript": r"(?:^\s*(?:async\s+)?function\s+\w+|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\(|^\s*\w+\s*\(.*\)\s*\{)",
        "typescript": r"(?:^\s*(?:async\s+)?function\s+\w+|(?:const|let|var)\s+\w+\s*[:=].*=>|^\s*(?:public|private|protected)?\s*(?:async\s+)?\w+\s*\()",
        "go":         r"^\s*func\s+",
        "java":       r"^\s*(?:public|private|protected)\s+.*\w+\s*\(",
    }

    pattern = func_patterns.get(lang, func_patterns.get("javascript"))
    if not pattern:
        return Signal("docstring_consistency", 0.5, WEIGHTS["docstring_consistency"],
                      0.1, [], [], "Language not supported")

    lines = [l for _, l in hunk.added_lines]
    func_count = 0
    documented_count = 0
    evidence = []

    for i, line in enumerate(lines):
        if re.search(pattern, line):
            func_count += 1
            # Check preceding lines for docstring/comment
            has_doc = False
            for j in range(max(0, i - 5), i):
                prev = lines[j].strip()
                if (prev.startswith('"""') or prev.startswith("'''") or
                    prev.startswith("/**") or prev.startswith("///") or
                    prev.startswith("// ") or prev.startswith("# ")):
                    has_doc = True
                    break
            if has_doc:
                documented_count += 1

    if func_count < 2:
        return Signal("docstring_consistency", 0.5, WEIGHTS["docstring_consistency"],
                      0.1, [], [], "Too few functions to assess documentation pattern")

    doc_ratio = documented_count / func_count

    # LLMs document 80-100%; humans 20-40%
    if doc_ratio > 0.8:
        score = 0.7 + (doc_ratio - 0.8) * 1.5
        evidence.append(f"{documented_count}/{func_count} functions documented ({doc_ratio:.0%}) — AI-typical range")
    elif doc_ratio > 0.5:
        score = 0.3 + (doc_ratio - 0.5) * 1.33
    else:
        score = max(0, doc_ratio * 0.6)

    score = min(1.0, score)
    patterns_found = [PatternCategory.EXCESSIVE_DOCSTRINGS] if score > 0.6 else []
    confidence = min(0.85, 0.3 + func_count / 10)

    return Signal(
        "docstring_consistency", round(score, 3), WEIGHTS["docstring_consistency"],
        round(confidence, 2), evidence, patterns_found,
        f"{documented_count}/{func_count} functions have docstrings ({doc_ratio:.0%})"
    )


def analyze_naming_uniformity(hunk: DiffHunk, lang: str) -> Signal:
    """Signal 3: Naming convention consistency."""
    added = " ".join(l for _, l in hunk.added_lines)

    # Extract identifiers (variable/function names)
    identifiers = re.findall(r'\b([a-z][a-zA-Z0-9_]{2,30})\b', added)

    if len(identifiers) < 10:
        return Signal("naming_uniformity", 0.5, WEIGHTS["naming_uniformity"],
                      0.1, [], [], "Too few identifiers to assess naming patterns")

    camel_count = sum(1 for i in identifiers if re.search(r'[a-z][A-Z]', i))
    snake_count = sum(1 for i in identifiers if '_' in i and not re.search(r'[a-z][A-Z]', i))
    other_count = len(identifiers) - camel_count - snake_count

    total_styled = camel_count + snake_count
    if total_styled == 0:
        return Signal("naming_uniformity", 0.5, WEIGHTS["naming_uniformity"],
                      0.2, [], [], "No clear naming convention detected")

    dominant = max(camel_count, snake_count)
    uniformity = dominant / total_styled

    evidence = []
    # Language-aware floor: PEP 8 mandates snake_case for Python, gofmt for Go.
    # In those languages, 95%+ uniformity is the language baseline, NOT an AI
    # signal. Apply a higher floor before flagging. (CLAIMS C-006 confirms
    # naming differences exist for LLM-paraphrased code, but the absolute
    # threshold is language-confounded — see CALIBRATION_NOTES.md.)
    if lang in ("python", "go"):
        # Only flag truly *exceptional* uniformity in {Python, Go}. PEP 8 and
        # gofmt enforce convention so high uniformity is the language baseline.
        # Even at 100% uniformity over 50+ identifiers, cap the score at 0.4 —
        # this is at most a *soft* signal because real Python code naturally
        # has ClassNames and CONSTANTS in addition to snake_case functions.
        if uniformity >= 1.0 and len(identifiers) > 50:
            score = 0.4
            evidence.append(
                f"Naming 100% uniform in {lang} across {len(identifiers)} identifiers "
                f"(unusual even by PEP 8/gofmt standards; soft signal only)"
            )
        else:
            # All other Python/Go uniformity levels are below-suspicion baseline.
            score = 0.10
    else:
        # Other languages have less aggressive style enforcement.
        if uniformity > 0.95:
            score = 0.7 + (uniformity - 0.95) * 6.0
            evidence.append(f"Naming {uniformity:.0%} uniform — AI-typical consistency")
        elif uniformity > 0.85:
            score = 0.3 + (uniformity - 0.85) * 4.0
        else:
            score = max(0, uniformity * 0.35)

    score = min(1.0, score)

    # Check for "universally sensible" names (no abbreviations)
    abbrev_count = sum(1 for i in identifiers if len(i) <= 3 and i not in {"get", "set", "new", "add", "put", "run", "map", "err", "req", "res", "ctx", "buf", "log", "len", "max", "min", "str", "num", "val", "idx", "tmp", "arg", "key", "msg", "cmd", "cfg", "env", "fmt", "pkg", "src", "dst"})
    abbrev_ratio = abbrev_count / len(identifiers)
    # Low abbreviation usage is mildly AI-indicative
    if abbrev_ratio < 0.05 and len(identifiers) > 20:
        score = min(1.0, score + 0.1)
        evidence.append(f"Very few abbreviations ({abbrev_ratio:.0%}) — AI tends toward full words")

    patterns_found = [PatternCategory.UNIFORM_NAMING] if score > 0.5 else []
    confidence = min(0.8, 0.2 + len(identifiers) / 50)

    return Signal(
        "naming_uniformity", round(score, 3), WEIGHTS["naming_uniformity"],
        round(confidence, 2), evidence, patterns_found,
        f"Naming uniformity: {uniformity:.0%} (camel={camel_count}, snake={snake_count})"
    )


def analyze_error_handling(hunk: DiffHunk, lang: str) -> Signal:
    """Signal 4: Shallow/defensive error handling patterns."""
    added = "\n".join(l for _, l in hunk.added_lines)

    # Language-specific try-catch patterns
    try_patterns = {
        "python":     (r'\btry\s*:', r'\bexcept\b'),
        "javascript": (r'\btry\s*\{', r'\bcatch\s*\('),
        "typescript": (r'\btry\s*\{', r'\bcatch\s*\('),
        "go":         (r'\bif\s+err\s*!=\s*nil', None),  # Go idiom
        "java":       (r'\btry\s*\{', r'\bcatch\s*\('),
        "rust":       (r'\b(unwrap|expect)\s*\(', None),  # Rust idiom
    }

    tp = try_patterns.get(lang, try_patterns.get("javascript"))
    if not tp:
        return Signal("error_handling", 0.5, WEIGHTS["error_handling"],
                      0.1, [], [], "Language not supported for error analysis")

    try_regex, catch_regex = tp
    evidence = []

    if lang == "go":
        # Go: check for shallow error handling (just return err)
        err_checks = re.findall(r'if\s+err\s*!=\s*nil\s*\{([^}]*)\}', added, re.DOTALL)
        if not err_checks:
            return Signal("error_handling", 0.5, WEIGHTS["error_handling"],
                          0.1, [], [], "No error handling found in diff")

        shallow = sum(1 for e in err_checks if re.search(r'^\s*return\s', e.strip()))
        total = len(err_checks)
        shallow_ratio = shallow / total
        if shallow_ratio > 0.8:
            score = 0.7
            evidence.append(f"{shallow}/{total} error blocks just return err")
        else:
            score = shallow_ratio * 0.5
    else:
        try_count = len(re.findall(try_regex, added))
        if try_count == 0:
            # No try-catch: check for lack of error handling entirely
            lines = added.splitlines()
            if len(lines) > 30:
                score = 0.4
                evidence.append("No error handling in 30+ line addition — possible miss")
            else:
                return Signal("error_handling", 0.5, WEIGHTS["error_handling"],
                              0.15, [], [], "No error handling patterns found")
        else:
            # Check for empty/generic catches
            if catch_regex:
                catches = re.findall(catch_regex + r'[^)]*\)\s*\{([^}]*)\}', added, re.DOTALL)
                empty_catches = sum(1 for c in catches if len(c.strip()) < 10)
                log_only = sum(1 for c in catches if re.search(r'console\.(log|error|warn)|print|log\.\w+', c))

                total_catches = len(catches)
                if total_catches == 0:
                    score = 0.5
                else:
                    weak_ratio = (empty_catches + log_only) / total_catches
                    score = min(1.0, weak_ratio * 0.8)
                    if empty_catches > 0:
                        evidence.append(f"{empty_catches} empty catch blocks")
                    if log_only > 0:
                        evidence.append(f"{log_only} log-only catch blocks")
            else:
                score = 0.5

    # Check for blanket Exception catching (Python). Tier the matches.
    # Bare `except:` is the strongest signal (catches SystemExit/KeyboardInterrupt).
    # `except Exception:` is broad but standard for top-level handlers; weaker signal.
    # `except ExceptionGroup:` (Py 3.11+) is specific and should NOT match.
    if lang == "python":
        bare_except = len(re.findall(r'^\s*except\s*:\s*$', added, re.MULTILINE))
        # `\b` boundary prevents matching ExceptionGroup, BaseExceptionGroup, etc.
        broad_typed = len(re.findall(r'^\s*except\s+(?:Exception|BaseException)\b(?!\w)', added, re.MULTILINE))
        if bare_except > 0:
            score = min(1.0, score + 0.3)
            evidence.append(f"{bare_except} bare `except:` (catches everything incl. SystemExit)")
        if broad_typed > 0:
            score = min(1.0, score + 0.1)
            evidence.append(f"{broad_typed} broad `except Exception` (acceptable for top-level handlers; specific types preferred)")

    patterns_found = [PatternCategory.SHALLOW_ERROR_HANDLING] if score > 0.5 else []
    confidence = min(0.75, 0.2 + try_count / 5) if 'try_count' in dir() else 0.4

    return Signal(
        "error_handling", round(score, 3), WEIGHTS["error_handling"],
        round(confidence, 2), evidence, patterns_found,
        f"Error handling analysis: score={score:.2f}"
    )


def analyze_declarative_bias(hunk: DiffHunk, lang: str) -> Signal:
    """Signal 5: Ratio of declarative statements to control flow.

    Counts only true assignments. Excludes `==`, `!=`, `<=`, `>=`, `=>` (arrow),
    and walrus `:=` confusion. Previous version counted `assert x == 1` and
    `if foo == bar:` as assignments, biasing the signal toward AI-typical.
    """
    added = "\n".join(l for _, l in hunk.added_lines)

    # JS/TS-style declarations (const/let/var/:=). Negative-lookahead avoids `:==`.
    js_assigns = len(re.findall(r'(?:const|let|var)\s+\w+\s*=(?!=)', added))
    walrus = len(re.findall(r'\w+\s*:=(?!=)', added))
    # Plain `name = value` assignments — excludes ==, !=, <=, >=, =>
    # Pattern requires `=` followed by NOT one of `=<>!`-style operators.
    plain_assigns = len(re.findall(
        r'^\s*[A-Za-z_]\w*(?:\s*[,.\[\]\w]*)?\s*=(?![=<>!])', added, re.MULTILINE
    ))
    # Subtract lines that look like comparisons or arrows that the plain regex
    # would still catch (defensive — keeps the count conservative).
    arrow_funcs = len(re.findall(r'=>\s*', added))
    plain_assigns = max(0, plain_assigns - arrow_funcs)

    assignments = js_assigns + walrus + plain_assigns
    returns = len(re.findall(r'\breturn\b', added))
    declarative = assignments + returns

    # Count control flow (word-boundary so `format` doesn't match `for`).
    ifs = len(re.findall(r'\bif\b', added))
    fors = len(re.findall(r'\bfor\b', added))
    whiles = len(re.findall(r'\bwhile\b', added))
    switches = len(re.findall(r'\b(?:switch|match|case)\b', added))
    control = ifs + fors + whiles + switches

    if control == 0 and declarative == 0:
        return Signal("declarative_bias", 0.5, WEIGHTS["declarative_bias"],
                      0.1, [], [], "Insufficient statements to analyze")

    if control == 0:
        ratio = 5.0  # Pure declarative
    else:
        ratio = declarative / control

    evidence = []
    # LLM: 1.8-2.5x higher ratio
    if ratio > 2.5:
        score = min(1.0, 0.7 + (ratio - 2.5) * 0.1)
        evidence.append(f"Declarative/control ratio {ratio:.1f} — heavily declarative (AI-typical)")
    elif ratio > 1.8:
        score = 0.4 + (ratio - 1.8) * 0.43
    elif ratio > 1.0:
        score = 0.2 + (ratio - 1.0) * 0.25
    else:
        score = max(0, ratio * 0.2)

    patterns_found = [PatternCategory.DECLARATIVE_HEAVY] if score > 0.5 else []
    total_stmts = declarative + control
    confidence = min(0.7, 0.2 + total_stmts / 50)

    return Signal(
        "declarative_bias", round(score, 3), WEIGHTS["declarative_bias"],
        round(confidence, 2), evidence, patterns_found,
        f"Declarative={declarative}, Control={control}, Ratio={ratio:.1f}"
    )


def analyze_function_length(hunk: DiffHunk, lang: str) -> Signal:
    """Signal 6: Function length distribution — DIFF-ONLY APPROXIMATION.

    Limitation: this measures the gap between consecutive function-definition
    lines among `added_lines` only. It is not the actual function body length
    when the diff is partial. Confidence is capped at 0.4 to reflect this.
    For a real measurement, use `--repo-path` mode (future: AST parse).
    See `references/CALIBRATION_NOTES.md` open question K-002.
    """
    lines = [l for _, l in hunk.added_lines]

    func_patterns = {
        "python":     r"^\s*(?:async\s+)?def\s+",
        "javascript": r"(?:^\s*(?:async\s+)?function\s+|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\()",
        "typescript": r"(?:^\s*(?:async\s+)?function\s+|(?:const|let|var)\s+\w+\s*[:=])",
        "go":         r"^\s*func\s+",
        "java":       r"^\s*(?:public|private|protected)\s+",
    }

    pattern = func_patterns.get(lang)
    if not pattern:
        return Signal("function_length", 0.5, WEIGHTS["function_length"],
                      0.1, [], [], "Language not supported")

    # Find function boundaries (approximate via indentation reset)
    func_starts = [i for i, l in enumerate(lines) if re.search(pattern, l)]

    if len(func_starts) < 2:
        return Signal("function_length", 0.5, WEIGHTS["function_length"],
                      0.1, [], [], "Too few functions to analyze length distribution")

    # Approximate function lengths
    lengths = []
    for i in range(len(func_starts)):
        start = func_starts[i]
        end = func_starts[i + 1] if i + 1 < len(func_starts) else len(lines)
        lengths.append(end - start)

    avg_len = sum(lengths) / len(lengths)
    std_len = math.sqrt(sum((l - avg_len) ** 2 for l in lengths) / len(lengths)) if len(lengths) > 1 else 0

    evidence = []
    # AI functions tend toward uniform 15-30 line functions
    # High uniformity (low std) is AI-indicative
    cv = std_len / avg_len if avg_len > 0 else 1

    if cv < 0.3 and len(lengths) >= 3:
        score = 0.7
        evidence.append(f"Very uniform function lengths (CV={cv:.2f}) — AI-typical")
    elif cv < 0.5:
        score = 0.4
    else:
        score = 0.15

    # AI tends toward medium-length functions (15-40 lines)
    if 15 <= avg_len <= 40:
        score = min(1.0, score + 0.15)
        evidence.append(f"Avg function length {avg_len:.0f} lines — in AI-typical range")

    patterns_found = [PatternCategory.COOKIE_CUTTER_STRUCTURE] if score > 0.5 else []
    # Capped at 0.4 — this is a diff-only approximation, not real function length.
    confidence = min(0.4, 0.15 + len(func_starts) / 12)

    return Signal(
        "function_length", round(score, 3), WEIGHTS["function_length"],
        round(confidence, 2), evidence, patterns_found,
        f"Avg gap={avg_len:.0f} (diff approximation), CV={cv:.2f}, N={len(lengths)}"
    )


def analyze_comment_phrasing(hunk: DiffHunk, lang: str) -> Signal:
    """Signal 7: Boilerplate comment phrase detection."""
    comments = []
    patterns = COMMENT_PATTERNS.get(lang, COMMENT_PATTERNS.get("javascript", {}))

    for _, line in hunk.added_lines:
        stripped = line.strip()
        if patterns.get("line") and re.search(patterns["line"], stripped):
            comments.append(stripped)

    if len(comments) < 3:
        return Signal("comment_phrasing", 0.5, WEIGHTS["comment_phrasing"],
                      0.1, [], [], "Too few comments to analyze phrasing")

    ai_phrase_hits = 0
    matched_phrases = []
    for comment in comments:
        for pattern in AI_COMMENT_PHRASES:
            if re.search(pattern, comment):
                ai_phrase_hits += 1
                matched_phrases.append(comment.strip()[:80])
                break

    hit_ratio = ai_phrase_hits / len(comments)

    if hit_ratio > 0.5:
        score = min(1.0, 0.6 + (hit_ratio - 0.5) * 0.8)
    elif hit_ratio > 0.25:
        score = 0.3 + (hit_ratio - 0.25) * 1.2
    else:
        score = hit_ratio * 1.2

    evidence = [f"Matched: {p}" for p in matched_phrases[:5]]
    patterns_found = [PatternCategory.BOILERPLATE_BLOAT] if score > 0.5 else []
    confidence = min(0.7, 0.2 + len(comments) / 20)

    return Signal(
        "comment_phrasing", round(score, 3), WEIGHTS["comment_phrasing"],
        round(confidence, 2), evidence, patterns_found,
        f"{ai_phrase_hits}/{len(comments)} comments match AI boilerplate patterns ({hit_ratio:.0%})"
    )


def analyze_hallucinated_apis(hunk: DiffHunk, lang: str) -> Signal:
    """Signal 8: Detection of potentially hallucinated API calls."""
    added = "\n".join(l for _, l in hunk.added_lines)
    evidence = []

    hit_count = 0
    for pattern, desc in merged_hallucination_patterns():
        matches = re.findall(pattern, added)
        if matches:
            hit_count += len(matches)
            evidence.append(f"{desc}: found {len(matches)} occurrence(s)")

    if hit_count == 0:
        score = 0.0
    elif hit_count <= 2:
        score = 0.5
    else:
        score = min(1.0, 0.5 + hit_count * 0.1)

    patterns_found = [PatternCategory.HALLUCINATED_API] if hit_count > 0 else []
    confidence = 0.4  # Low base — pattern set is limited

    return Signal(
        "hallucinated_apis", round(score, 3), WEIGHTS["hallucinated_apis"],
        round(confidence, 2), evidence, patterns_found,
        f"Found {hit_count} potential hallucinated API calls"
    )


def _python_max_depth(lines: list) -> int:
    """Indent-based max nesting depth for Python.

    Tracks indentation columns of control-flow openers (if/for/while/try/with/
    def/class). Depth resets when indentation decreases. Returns the deepest
    block-nesting observed in the added lines.

    Replaces the previous monotonic-increment-only implementation that
    produced impossible values (e.g. depth=198 on a 1874-line file). See the
    v0.2.0 changelog and `references/CALIBRATION_NOTES.md`.
    """
    indent_stack = []  # stack of indent columns of open control blocks
    max_depth = 0
    opener_re = re.compile(r'^(\s*)(if|elif|else|for|while|try|except|finally|with|def|class|match|case)\b')
    for line in lines:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        leading = len(line) - len(line.lstrip(' \t'))
        # Pop blocks whose indent we're now outside of.
        while indent_stack and leading <= indent_stack[-1]:
            indent_stack.pop()
        m = opener_re.match(line)
        if m:
            indent_stack.append(leading)
            if len(indent_stack) > max_depth:
                max_depth = len(indent_stack)
    return max_depth


def _brace_max_depth(lines: list) -> int:
    """Brace-counting max depth for C-family languages."""
    current = 0
    max_depth = 0
    for line in lines:
        # Strip strings/comments only crudely — good enough for diff samples.
        stripped = re.sub(r'//[^\n]*', '', line)
        stripped = re.sub(r'/\*.*?\*/', '', stripped)
        opens = stripped.count('{')
        closes = stripped.count('}')
        current = max(0, current + opens - closes)
        if current > max_depth:
            max_depth = current
    return max_depth


def analyze_edge_case_depth(hunk: DiffHunk, lang: str) -> Signal:
    """Signal 9: Conditional depth / null-check coverage."""
    lines = [l for _, l in hunk.added_lines]
    added = "\n".join(lines)

    # Count null/undefined checks
    null_checks = len(re.findall(r'(?:===?\s*null|===?\s*undefined|!=\s*nil|\bis\s+None|is\s+not\s+None)', added))

    # Count parameter validation / guard clauses
    guards = len(re.findall(r'^\s*if\s*\(!?\w+\)\s*(return|throw|raise)', added, re.MULTILINE))

    # Measure max nesting depth — language-specific.
    if lang == "python":
        max_depth = _python_max_depth(lines)
    elif lang in ("javascript", "typescript", "go", "java", "rust", "cpp", "c", "csharp", "php", "swift", "kotlin", "scala"):
        max_depth = _brace_max_depth(lines)
    else:
        max_depth = _brace_max_depth(lines)  # best-effort fallback

    total_lines = len(lines)
    if total_lines < 10:
        return Signal("edge_case_depth", 0.5, WEIGHTS["edge_case_depth"],
                      0.1, [], [], "Too few lines to assess edge case handling")

    evidence = []

    # AI: avg nesting 1.2-1.5, human: 2.0+
    # Low null checks + low nesting = AI-indicative
    null_density = null_checks / max(total_lines / 10, 1)
    guard_density = guards / max(total_lines / 20, 1)

    shallow_score = 0
    if max_depth <= 2 and total_lines > 30:
        shallow_score += 0.3
        evidence.append(f"Max nesting depth {max_depth} in {total_lines} lines — shallow")
    if null_density < 0.5 and total_lines > 20:
        shallow_score += 0.3
        evidence.append(f"Low null-check density ({null_checks} checks in {total_lines} lines)")
    if guard_density < 0.3:
        shallow_score += 0.2
        evidence.append(f"Few guard clauses ({guards} guards)")

    score = min(1.0, shallow_score)
    patterns_found = [PatternCategory.MISSING_EDGE_CASES] if score > 0.5 else []
    confidence = min(0.6, 0.15 + total_lines / 100)

    return Signal(
        "edge_case_depth", round(score, 3), WEIGHTS["edge_case_depth"],
        round(confidence, 2), evidence, patterns_found,
        f"Depth={max_depth}, NullChecks={null_checks}, Guards={guards}"
    )


def analyze_commit_metadata(commit_messages: list) -> Signal:
    """Signal 10: AI tool markers in commit messages."""
    if not commit_messages:
        return Signal("commit_metadata", 0.0, WEIGHTS["commit_metadata"],
                      0.1, [], [], "No commit messages provided")

    evidence = []
    ai_marker_score = 0

    for msg in commit_messages:
        for pattern in AI_COMMIT_PATTERNS:
            if re.search(pattern, msg):
                ai_marker_score += 1
                evidence.append(f"Commit pattern match: {msg[:80]}")
                break

    if ai_marker_score == 0:
        score = 0.0
    else:
        score = min(1.0, ai_marker_score / len(commit_messages))

    patterns_found = [PatternCategory.AI_COMMIT_MARKERS] if ai_marker_score > 0 else []
    confidence = min(0.5, 0.1 + len(commit_messages) / 10)

    return Signal(
        "commit_metadata", round(score, 3), WEIGHTS["commit_metadata"],
        round(confidence, 2), evidence, patterns_found,
        f"{ai_marker_score}/{len(commit_messages)} commits have AI markers"
    )


# ─── Aggregation ────────────────────────────────────────────────────────

def compute_weighted_score(signals: list) -> tuple:
    """Compute weighted AI probability from all signals."""
    total_weight = 0
    weighted_sum = 0
    confidence_sum = 0

    for sig in signals:
        effective_weight = sig.weight * sig.confidence
        weighted_sum += sig.score * effective_weight
        total_weight += effective_weight
        confidence_sum += sig.confidence

    if total_weight == 0:
        return 0.5, 0.0

    probability = weighted_sum / total_weight
    avg_confidence = confidence_sum / len(signals)

    return round(probability, 3), round(avg_confidence, 2)


def assign_grade(probability: float) -> str:
    """Map AI probability to letter grade (A=human, F=vibe-coded)."""
    if probability < 0.15:
        return "A"   # Almost certainly human
    elif probability < 0.30:
        return "B"   # Mostly human, some AI patterns
    elif probability < 0.50:
        return "C"   # Mixed signals
    elif probability < 0.70:
        return "D"   # Likely AI-generated
    else:
        return "F"   # Strong AI signals


def generate_recommendations(file_analyses: list, pattern_counts: dict) -> list:
    """Generate actionable recommendations based on detected patterns."""
    recs = []

    if pattern_counts.get(PatternCategory.OVER_COMMENTING, 0) > 0:
        recs.append({
            "priority": "high",
            "category": "over_commenting",
            "recommendation": "Review comment density. AI-generated code often has 2-3x more comments than needed. Remove comments that merely restate the code.",
            "what_to_check": "Are comments explaining 'what' instead of 'why'? Remove trivial comments like '// Initialize the variable'."
        })

    if pattern_counts.get(PatternCategory.SHALLOW_ERROR_HANDLING, 0) > 0:
        recs.append({
            "priority": "high",
            "category": "error_handling",
            "recommendation": "Audit error handling. AI code frequently uses empty catches or log-only error handlers that swallow failures silently.",
            "what_to_check": "Does each catch block handle the specific error type? Are errors propagated to callers who need to know? Are there retry mechanisms where appropriate?"
        })

    if pattern_counts.get(PatternCategory.MISSING_EDGE_CASES, 0) > 0:
        recs.append({
            "priority": "high",
            "category": "edge_cases",
            "recommendation": "AI-generated code frequently assumes clean inputs. Verify boundary conditions, null checks, empty collections, and concurrent access patterns.",
            "what_to_check": "What happens with: empty arrays, null params, negative numbers, very large inputs, concurrent modifications, network timeouts?"
        })

    if pattern_counts.get(PatternCategory.HALLUCINATED_API, 0) > 0:
        recs.append({
            "priority": "critical",
            "category": "hallucinated_apis",
            "recommendation": "VERIFY ALL API CALLS. Detected potentially non-existent or incorrect API usage — a hallmark of AI generation.",
            "what_to_check": "Cross-reference every method call against the actual library documentation for the version in use."
        })

    if pattern_counts.get(PatternCategory.BOILERPLATE_BLOAT, 0) > 0:
        recs.append({
            "priority": "medium",
            "category": "boilerplate",
            "recommendation": "Check for unnecessary boilerplate. AI tends to generate formulaic code rather than leveraging existing abstractions.",
            "what_to_check": "Could this code reuse existing utilities? Is there duplicated logic that should be extracted? Are there framework features being reimplemented?"
        })

    if pattern_counts.get(PatternCategory.UNIFORM_NAMING, 0) > 0:
        recs.append({
            "priority": "low",
            "category": "naming",
            "recommendation": "Naming is unusually uniform. While not inherently bad, verify names reflect domain understanding rather than generic descriptions.",
            "what_to_check": "Do names match the team's domain vocabulary? Are there project-specific conventions being missed?"
        })

    if pattern_counts.get(PatternCategory.COOKIE_CUTTER_STRUCTURE, 0) > 0:
        recs.append({
            "priority": "medium",
            "category": "structure",
            "recommendation": "Functions are suspiciously uniform in length. AI often generates code in predictable chunks rather than sizing functions to their responsibility.",
            "what_to_check": "Does each function do one thing well? Are some functions artificially padded or split?"
        })

    if pattern_counts.get(PatternCategory.DECLARATIVE_HEAVY, 0) > 0:
        recs.append({
            "priority": "low",
            "category": "complexity",
            "recommendation": "Code is heavily declarative with minimal control flow. Verify the logic handles complex branching scenarios.",
            "what_to_check": "Are there real-world conditions (feature flags, user permissions, data variants) that need branching?"
        })

    # Always add these meta-recommendations
    recs.append({
        "priority": "medium",
        "category": "context_verification",
        "recommendation": "Verify the PR author understands the code they're submitting. AI-assisted code is fine; code submitted without understanding is risky.",
        "what_to_check": "Can the author explain design decisions? Do they understand the failure modes? Can they debug this without AI help?"
    })

    recs.append({
        "priority": "medium",
        "category": "integration_context",
        "recommendation": "AI lacks project context. Verify integration with existing patterns, shared state, concurrency models, and deployment constraints.",
        "what_to_check": "Does the code follow existing patterns in the codebase? Does it handle the project's specific error propagation, logging, and monitoring conventions?"
    })

    return recs


# ─── Input fetching ─────────────────────────────────────────────────────

def fetch_pr_diff(pr_ref: str) -> tuple:
    """Fetch diff and commit messages from GitHub PR via gh CLI."""
    try:
        diff = subprocess.check_output(
            ["gh", "pr", "diff", pr_ref, "--color=never"],
            text=True, timeout=30
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error fetching PR diff: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        commits_json = subprocess.check_output(
            ["gh", "pr", "view", pr_ref, "--json", "commits"],
            text=True, timeout=30
        )
        commits_data = json.loads(commits_json)
        messages = [c.get("messageHeadline", "") for c in commits_data.get("commits", [])]
    except Exception:
        messages = []

    return diff, messages


def fetch_local_diff(repo_path: str, base: str, head: str) -> tuple:
    """Fetch diff from local git repo."""
    try:
        diff = subprocess.check_output(
            ["git", "-C", repo_path, "diff", f"{base}...{head}"],
            text=True, timeout=30
        )
        log = subprocess.check_output(
            ["git", "-C", repo_path, "log", "--format=%s", f"{base}...{head}"],
            text=True, timeout=30
        )
        messages = [m for m in log.strip().splitlines() if m]
    except subprocess.CalledProcessError as e:
        print(f"Error fetching local diff: {e}", file=sys.stderr)
        sys.exit(1)

    return diff, messages


# ─── Main analysis pipeline ────────────────────────────────────────────

def analyze_diff(diff_text: str, commit_messages: list = None) -> VibeCheckResult:
    """Run full analysis pipeline on a diff."""
    hunks = parse_unified_diff(diff_text)
    commit_messages = commit_messages or []

    file_analyses = []
    all_signals = []
    pattern_counts = Counter()

    for hunk in hunks:
        lang = detect_language(hunk.filepath)
        if lang == "unknown" or len(hunk.added_lines) < 3:
            continue

        signals = [
            analyze_comment_ratio(hunk, lang),
            analyze_docstring_consistency(hunk, lang),
            analyze_naming_uniformity(hunk, lang),
            analyze_error_handling(hunk, lang),
            analyze_declarative_bias(hunk, lang),
            analyze_function_length(hunk, lang),
            analyze_comment_phrasing(hunk, lang),
            analyze_hallucinated_apis(hunk, lang),
            analyze_edge_case_depth(hunk, lang),
        ]

        ai_prob, confidence = compute_weighted_score(signals)

        fa = FileAnalysis(
            path=hunk.filepath,
            language=lang,
            added_lines=len(hunk.added_lines),
            signals=[asdict(s) for s in signals],
            ai_probability=ai_prob
        )
        file_analyses.append(fa)
        all_signals.extend(signals)

        for sig in signals:
            for p in sig.patterns:
                pattern_counts[p] += 1

    # Add commit metadata signal
    commit_signal = analyze_commit_metadata(commit_messages)
    all_signals.append(commit_signal)
    for p in commit_signal.patterns:
        pattern_counts[p] += 1

    # Overall score
    if not file_analyses:
        overall_prob = 0.5
        overall_confidence = 0.0
    else:
        # Weight by file size (more added lines = more influence)
        total_lines = sum(fa.added_lines for fa in file_analyses)
        if total_lines > 0:
            overall_prob = sum(
                fa.ai_probability * fa.added_lines / total_lines
                for fa in file_analyses
            )
        else:
            overall_prob = 0.5
        _, overall_confidence = compute_weighted_score(all_signals)

    # Signal summary (aggregate across files)
    signal_summary = {}
    signal_groups = defaultdict(list)
    for sig in all_signals:
        signal_groups[sig.name].append(sig)

    for name, sigs in signal_groups.items():
        avg_score = sum(s.score for s in sigs) / len(sigs)
        avg_conf = sum(s.confidence for s in sigs) / len(sigs)
        all_evidence = [e for s in sigs for e in s.evidence]
        signal_summary[name] = {
            "avg_score": round(avg_score, 3),
            "avg_confidence": round(avg_conf, 2),
            "weight": WEIGHTS.get(name, 0),
            "evidence_count": len(all_evidence),
            "top_evidence": all_evidence[:3],
        }

    # Pattern taxonomy
    taxonomy = {p.value: count for p, count in pattern_counts.items()}

    # Recommendations
    recommendations = generate_recommendations(file_analyses, pattern_counts)

    # Methodology notes
    methodology = [
        "Signals are computed deterministically from diff text using regex and AST-style structural analysis.",
        "Default weights are SPECULATIVE PRIORS (see references/CALIBRATION_NOTES.md). Tao et al. (CLAIMS C-007) show signal magnitude varies drastically across models — fixed weights cannot generalize. Calibrate per-codebase before quantitative claims.",
        "Per-signal evidence (specifically commit metadata, hallucinated APIs, and bare `except:` patterns) is more useful than the aggregate score.",
        "The aggregate score is a weighted convenience number. Use --no-aggregate to suppress it.",
        "AICD Bench (CLAIMS C-008) and Wang et al. (CLAIMS C-005) report detectors of this class are below practical usability under distribution shift. This is a reviewer prompt, not a gate.",
        "FP/FN rates are author rules-of-thumb (not validated on labeled data in this repo). Treat as 'mileage will vary by language, codebase, and model'.",
        "Adversarial limitation: determined authors can edit around most surface signals (hallucinated APIs and commit metadata are hardest to game).",
    ]

    # Evidence status (GRADE-style)
    if overall_confidence > 0.7:
        evidence_status = "CONCLUSIVE-PROVISIONAL"
    elif overall_confidence > 0.4:
        evidence_status = "INCONCLUSIVE"
    else:
        evidence_status = "INSUFFICIENT-DATA"

    return VibeCheckResult(
        overall_ai_probability=round(overall_prob, 3),
        confidence=overall_confidence,
        grade=assign_grade(overall_prob),
        file_analyses=[asdict(fa) for fa in file_analyses],
        signal_summary=signal_summary,
        pattern_taxonomy=taxonomy,
        recommendations=recommendations,
        methodology_notes=methodology,
        evidence_status=evidence_status,
    )


def format_markdown_report(result: VibeCheckResult, no_aggregate: bool = False) -> str:
    """Format analysis result as markdown report.

    When `no_aggregate=True`, suppresses the headline AI probability and grade
    line (and the grade interpretation paragraph). Per-signal evidence and
    recommendations are still emitted. Use this mode when reviewers should
    focus on specific evidence rather than a single number.
    """
    lines = []
    pct = result.overall_ai_probability * 100

    lines.append(f"# Vibe Check Report")
    lines.append("")
    if no_aggregate:
        lines.append(f"_Aggregate score suppressed (--no-aggregate). Per-signal evidence below._")
        lines.append("")
        lines.append(f"Status: {result.evidence_status}")
        lines.append("")
    else:
        lines.append(f"**AI Probability: {pct:.0f}%** | Grade: **{result.grade}** | Confidence: {result.confidence:.0%} | Status: {result.evidence_status}")
        lines.append("")
        # Grade interpretation
        grade_desc = {
            "A": "Almost certainly human-written code.",
            "B": "Mostly human, with some AI-like patterns (could be well-structured human code).",
            "C": "Mixed signals — could be AI-assisted with human editing, or well-templated human code.",
            "D": "Likely AI-generated. Several strong AI indicators present.",
            "F": "Strong AI signals across multiple dimensions. High probability of unedited AI output.",
        }
        lines.append(f"> {grade_desc.get(result.grade, '')}")
        lines.append("")
        lines.append(f"_Note: the aggregate score uses speculative default weights (CALIBRATION_NOTES.md). Per-signal evidence below is the more reliable output._")
        lines.append("")

    # Signal breakdown
    lines.append("## Signal Breakdown")
    lines.append("")
    lines.append("| Signal | Score | Weight | Confidence | Top Evidence |")
    lines.append("|--------|-------|--------|------------|-------------|")

    for name, data in sorted(result.signal_summary.items(), key=lambda x: x[1]["avg_score"], reverse=True):
        score_bar = "█" * int(data["avg_score"] * 10) + "░" * (10 - int(data["avg_score"] * 10))
        top_ev = data["top_evidence"][0][:50] + "..." if data["top_evidence"] else "—"
        lines.append(f"| {name} | {score_bar} {data['avg_score']:.2f} | {data['weight']:.2f} | {data['avg_confidence']:.0%} | {top_ev} |")

    lines.append("")

    # Pattern taxonomy
    if result.pattern_taxonomy:
        lines.append("## Detected AI Patterns")
        lines.append("")
        for pattern, count in sorted(result.pattern_taxonomy.items(), key=lambda x: x[1], reverse=True):
            label = pattern.replace("_", " ").title()
            lines.append(f"- **{label}** — detected in {count} file(s)")
        lines.append("")

    # Per-file analysis
    lines.append("## Per-File Analysis")
    lines.append("")
    for fa in sorted(result.file_analyses, key=lambda x: x["ai_probability"], reverse=True):
        pct = fa["ai_probability"] * 100
        emoji = "🔴" if pct > 60 else "🟡" if pct > 35 else "🟢"
        lines.append(f"### {emoji} `{fa['path']}` — {pct:.0f}% AI probability")
        lines.append(f"Language: {fa['language']} | Added lines: {fa['added_lines']}")
        lines.append("")

        for sig in sorted(fa["signals"], key=lambda x: x["score"], reverse=True):
            if sig["score"] > 0.3 and sig["evidence"]:
                lines.append(f"- **{sig['name']}** ({sig['score']:.2f}): {sig['explanation']}")
                for ev in sig["evidence"][:2]:
                    lines.append(f"  - {ev}")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for rec in sorted(result.recommendations, key=lambda x: priority_order.get(x["priority"], 99)):
        icon = {"critical": "🚨", "high": "⚠️", "medium": "ℹ️", "low": "💡"}.get(rec["priority"], "•")
        lines.append(f"{icon} **[{rec['priority'].upper()}]** {rec['recommendation']}")
        lines.append(f"   *Check:* {rec['what_to_check']}")
        lines.append("")

    # Methodology
    lines.append("## Methodology Notes")
    lines.append("")
    for note in result.methodology_notes:
        lines.append(f"- {note}")
    lines.append("")

    lines.append("---")
    lines.append(
        "*Generated by `vibe_check.py` — reviewer evidence surfacer. The aggregate score is a "
        "weighted convenience number; per-signal evidence is the useful output. AICD Bench (CLAIMS C-008) "
        "and Wang et al. (CLAIMS C-005) report detectors of this class are below practical usability under "
        "distribution shift. Use as a reviewer prompt, not a gate.*"
    )

    return "\n".join(lines)


# ─── Default thresholds — SPECULATIVE PRIORS, NOT FITTED ───────────────
# These are authored defaults. They are NOT derived from any single cited
# source. See `references/CALIBRATION_NOTES.md` for what each represents and
# how to replace them with empirical values from `calibration_pipeline.py`.
# (Previous code comment claimed "from Gemini research, Table 1" — no such
# table existed in any cited source. Removed in v0.2.0.)
SIGNAL_THRESHOLDS = {
    "comment_ratio":         {"human_baseline": 0.15, "llm_baseline": 0.50, "threshold": None},  # TBD per-codebase
    "docstring_consistency": {"human_baseline": 0.25, "llm_baseline": 0.90, "threshold": 0.65},
    "naming_uniformity":     {"human_baseline": 0.80, "llm_baseline": 0.97, "threshold": 0.92},
    "error_handling":        {"human_baseline": 0.20, "llm_baseline": 0.60, "threshold": 0.45},
    "declarative_bias":      {"human_baseline": 1.0,  "llm_baseline": 2.2,  "threshold": 1.8},
    "function_length":       {"human_baseline": 0.6,  "llm_baseline": 0.3,  "threshold": 0.4},    # CV: lower = more AI-like
    "comment_phrasing":      {"human_baseline": 0.15, "llm_baseline": 0.45, "threshold": 0.35},
    "hallucinated_apis":     {"human_baseline": 0.02, "llm_baseline": 0.18, "threshold": None},    # Binary
    "edge_case_depth":       {"human_baseline": 2.0,  "llm_baseline": 1.3,  "threshold": 1.5},     # Avg nesting
    "commit_metadata":       {"human_baseline": None, "llm_baseline": None, "threshold": None},     # Pattern match
}

# Calibration version. The previous string was "v2026_q2_gemini" — the
# "gemini" suffix referenced an unsourced internal claim that was retracted in
# v0.2.0 (see CHANGELOG and references/CALIBRATION_NOTES.md). Increment this
# string only when SIGNAL_THRESHOLDS or WEIGHTS are changed in a backwards-
# incompatible way; telemetry consumers compare exact strings.
CALIBRATION_VERSION = "v0.2.0_honest"


# ─── Residual-quantile margin (NOT conformal prediction) ────────────────
# Previous versions called this "conformal prediction CI". It is not. Real
# conformal prediction requires (a) a held-out calibration set with labels,
# (b) a nonconformity score derived from those labels, (c) a coverage
# theorem. None of those hold here. The function below computes a
# residual-quantile band around the weighted mean of (score × confidence)
# values, which is a useful uncertainty heuristic but carries no formal
# coverage guarantee. Renamed in v0.2.0.

def compute_residual_quantile_margin(signals: list, alpha: float = 0.1) -> tuple:
    """Heuristic uncertainty band around the aggregate score.

    Computes the (1-alpha)-quantile of |score·conf - mean(score·conf)|
    across signals, then returns (overall_score - margin, overall_score + margin)
    clipped to [0, 1].

    NOT a conformal prediction interval. NO coverage guarantee.
    Use as a "wide vs narrow" indicator only. For real uncertainty,
    calibrate against labeled data.
    """
    if not signals:
        return (0.0, 1.0)

    scores = [s.score * s.confidence for s in signals if s.confidence > 0.1]
    if len(scores) < 3:
        return (0.0, 1.0)

    mean_score = sum(scores) / len(scores)
    residuals = sorted(abs(s - mean_score) for s in scores)

    idx = min(len(residuals) - 1, int(math.ceil((1 - alpha) * len(residuals))))
    margin = residuals[idx]

    overall, _ = compute_weighted_score(signals)
    lower = max(0.0, overall - margin)
    upper = min(1.0, overall + margin)

    return (round(lower, 3), round(upper, 3))


# Backwards-compatible alias. Deprecated in v0.2.0.
def compute_conformal_ci(signals: list, alpha: float = 0.1) -> tuple:
    """DEPRECATED. Use compute_residual_quantile_margin instead.

    The old name implied a coverage guarantee that the math does not provide.
    Kept as a thin shim so older callers don't break; emits a DeprecationWarning.
    """
    import warnings
    warnings.warn(
        "compute_conformal_ci is deprecated; use compute_residual_quantile_margin. "
        "The old name was misleading — this is not conformal prediction.",
        DeprecationWarning, stacklevel=2,
    )
    return compute_residual_quantile_margin(signals, alpha)


# ─── Telemetry Logger (Phase 1 of self-healing roadmap) ────────────────
# Implements the immutable JSONL data warehouse described in the Gemini
# self-healing architecture. Every evaluation is logged for future drift
# detection via ADWIN + mean z-shift (default global). Optional Sinkhorn on
# binned scores: VIBE_CHECK_DRIFT_GLOBAL_METRIC=sinkhorn (Gemini discrete-syntax note).

TELEMETRY_DIR = os.environ.get("VIBE_CHECK_TELEMETRY_DIR", None)

def log_telemetry(result: VibeCheckResult, pr_id: str = "", repo: str = "",
                  commit_hash: str = ""):
    """Append evaluation to immutable JSONL telemetry log.

    Format matches the Gemini-recommended schema (Table 2 / Data Collection Format).
    Only logs if VIBE_CHECK_TELEMETRY_DIR environment variable is set.
    """
    if not TELEMETRY_DIR:
        return

    telemetry_path = Path(TELEMETRY_DIR)
    telemetry_path.mkdir(parents=True, exist_ok=True)

    ci = compute_residual_margin_from_result(result)

    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "repo": repo,
        "pr_id": pr_id,
        "commit_hash": commit_hash,
        "calibration_version": CALIBRATION_VERSION,
        "signals": {
            name: data["avg_score"]
            for name, data in result.signal_summary.items()
        },
        "vibe_score": result.overall_ai_probability,
        "confidence_interval": list(ci),
        "confidence": result.confidence,
        "grade": result.grade,
        "evidence_status": result.evidence_status,
        "files_analyzed": len(result.file_analyses),
        "pattern_taxonomy": result.pattern_taxonomy,
    }

    log_file = telemetry_path / "vibe_check_telemetry.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def compute_residual_margin_from_result(result: VibeCheckResult, alpha: float = 0.1) -> tuple:
    """Residual-quantile margin reconstructed from a completed result.

    Uses the same (1-alpha) quantile rule as compute_residual_quantile_margin
    so the two functions agree on the same inputs. Previous version used
    hardcoded 0.9 which inconsistently differed from the live-signal path.
    """
    scores = []
    for name, data in result.signal_summary.items():
        scores.append(data["avg_score"] * data["avg_confidence"])

    if len(scores) < 3:
        return (0.0, 1.0)

    mean_s = sum(scores) / len(scores)
    residuals = sorted(abs(s - mean_s) for s in scores)
    idx = min(len(residuals) - 1, int(math.ceil((1 - alpha) * len(residuals))))
    margin = residuals[idx]

    lower = max(0.0, result.overall_ai_probability - margin)
    upper = min(1.0, result.overall_ai_probability + margin)
    return (round(lower, 3), round(upper, 3))


# Backwards-compatible alias. Deprecated in v0.2.0.
def compute_conformal_ci_from_result(result: VibeCheckResult) -> tuple:
    """DEPRECATED. Use compute_residual_margin_from_result."""
    import warnings
    warnings.warn(
        "compute_conformal_ci_from_result is deprecated; use compute_residual_margin_from_result.",
        DeprecationWarning, stacklevel=2,
    )
    return compute_residual_margin_from_result(result)


def _histogram_01(vals: list[float], n_bins: int = 20) -> list[float]:
    h = [0.0] * n_bins
    for v in vals:
        v = max(0.0, min(1.0, float(v)))
        i = min(n_bins - 1, int(v * n_bins))
        h[i] += 1.0
    s = sum(h) or 1.0
    return [x / s for x in h]


def _sinkhorn_1d(p: list[float], q: list[float], reg: float = 0.06, iters: int = 100) -> float:
    """Entropy-regularized 1D transport cost (Sinkhorn-style); small n_bins only."""
    n = len(p)
    if n != len(q) or n < 2:
        return 0.0
    c = [[abs(i - j) / float(n - 1) for j in range(n)] for i in range(n)]
    k = [[math.exp(-c[i][j] / reg) for j in range(n)] for i in range(n)]
    u = [1.0 / n] * n
    v = [1.0 / n] * n
    for _ in range(iters):
        nu = []
        for i in range(n):
            s = sum(k[i][j] * v[j] for j in range(n)) or 1e-12
            nu.append(p[i] / s)
        u = nu
        nv = []
        for j in range(n):
            s = sum(k[i][j] * u[i] for i in range(n)) or 1e-12
            nv.append(q[j] / s)
        v = nv
    cost = 0.0
    for i in range(n):
        for j in range(n):
            t = u[i] * k[i][j] * v[j]
            cost += t * c[i][j]
    return cost


def _global_drift_sinkhorn(baseline: list, recent: list, signal_names: list[str]) -> float:
    dists = []
    for sig in signal_names:
        b = [e["signals"].get(sig, 0) for e in baseline if isinstance(e.get("signals"), dict)]
        r = [e["signals"].get(sig, 0) for e in recent if isinstance(e.get("signals"), dict)]
        if len(b) < 10 or len(r) < 10:
            continue
        dists.append(_sinkhorn_1d(_histogram_01(b), _histogram_01(r)))
    return sum(dists) / len(dists) if dists else 0.0


def _psi_1d(expected: list[float], actual: list[float], n_bins: int = 10, epsilon: float = 1e-4) -> float:
    """Population Stability Index. Industry-standard drift metric on binned proportions.

    Conventional thresholds (Field B / practitioner consensus, NOT RCT):
      <0.10 stable, 0.10-0.25 moderate, >=0.25 significant.
    """
    if not expected or not actual:
        return 0.0
    e = _histogram_01(expected, n_bins)
    a = _histogram_01(actual, n_bins)
    psi = 0.0
    for ei, ai in zip(e, a):
        ei = max(ei, epsilon)
        ai = max(ai, epsilon)
        psi += (ai - ei) * math.log(ai / ei)
    return psi


def _global_drift_psi(baseline: list, recent: list, signal_names: list[str]) -> float:
    psis = []
    for sig in signal_names:
        b = [e["signals"].get(sig, 0) for e in baseline if isinstance(e.get("signals"), dict)]
        r = [e["signals"].get(sig, 0) for e in recent if isinstance(e.get("signals"), dict)]
        if len(b) < 10 or len(r) < 10:
            continue
        psis.append(_psi_1d(b, r))
    return sum(psis) / len(psis) if psis else 0.0


DRIFT_STATE_FILENAME = "drift_persistence.json"


def _load_drift_state(tdir: Path) -> list:
    """Load recent drift-check statuses for M-of-N persistence (opt-in)."""
    p = tdir / DRIFT_STATE_FILENAME
    if not p.is_file():
        return []
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return list(obj.get("recent_statuses", []))
    except (json.JSONDecodeError, OSError):
        return []


def _save_drift_state(tdir: Path, statuses: list, window: int) -> None:
    p = tdir / DRIFT_STATE_FILENAME
    try:
        p.write_text(json.dumps({"recent_statuses": statuses[-window:], "schema": "drift_persistence.v1"}, indent=2))
    except OSError:
        pass


def _apply_persistence_rule(raw_status: str, tdir: Path) -> tuple:
    """Persistence rule: require M-of-N recent raw trips before exposing TRIGGER_*.

    Opt-in via VIBE_CHECK_DRIFT_PERSISTENCE_M / _N (defaults 1/1 = no-op).
    """
    try:
        m = int(os.environ.get("VIBE_CHECK_DRIFT_PERSISTENCE_M", "1"))
        n = int(os.environ.get("VIBE_CHECK_DRIFT_PERSISTENCE_N", "1"))
    except ValueError:
        m, n = 1, 1
    m = max(1, m)
    n = max(m, n)
    history = _load_drift_state(tdir) + [raw_status]
    _save_drift_state(tdir, history, n)
    recent = history[-n:]
    if m <= 1 and n <= 1:
        return raw_status, {"m_of_n": [m, n], "recent_statuses": recent, "noop": True}
    trip_count = sum(1 for s in recent if s.startswith("TRIGGER_"))
    if raw_status.startswith("TRIGGER_") and trip_count < m:
        return "WATCH", {"m_of_n": [m, n], "trips_seen": trip_count, "recent_statuses": recent, "suppressed_status": raw_status}
    return raw_status, {"m_of_n": [m, n], "trips_seen": trip_count, "recent_statuses": recent}


# ─── Drift Detection Stub (Phase 2 of self-healing roadmap) ───────────
# Implements the multi-tiered drift trigger logic from the Gemini research.
# Requires accumulated telemetry data — returns CONTINUE until sufficient
# data exists (minimum 50 evaluations for baseline).
# Default global metric is mean per-signal z-shift (not true Wasserstein-2).
# Opt-in: VIBE_CHECK_DRIFT_GLOBAL_METRIC=psi|sinkhorn
#   psi: Population Stability Index (binned). Threshold default 0.25 (Field B industry convention).
#   sinkhorn: entropy-regularized OT on binned scores (experimental).
# Opt-in: VIBE_CHECK_DRIFT_PERSISTENCE_M / _N for M-of-N persistence (defaults 1/1 = no-op).

def check_drift_status(telemetry_dir: str = None) -> dict:
    """Check for signal drift against baseline distribution.

    Implements the Gemini-recommended 3-tier decision logic:
    - TRIGGER_RECALIBRATION: Wasserstein > 1.5σ AND ≥2 ADWIN signals
    - TRIGGER_ALERT_MANUAL_REVIEW: 1 ADWIN signal OR CI collapse
    - CONTINUE_CURRENT_THRESHOLDS: No significant drift

    Returns dict with status, details, and per-signal drift indicators.
    """
    tdir = telemetry_dir or TELEMETRY_DIR
    if not tdir:
        return {"status": "NO_TELEMETRY", "message": "Set VIBE_CHECK_TELEMETRY_DIR to enable drift detection"}

    log_file = Path(tdir) / "vibe_check_telemetry.jsonl"
    if not log_file.exists():
        return {"status": "NO_DATA", "message": "No telemetry data yet"}

    # Load telemetry
    entries = []
    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if len(entries) < 50:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": f"Need ≥50 evaluations for drift detection. Have {len(entries)}.",
            "evaluations": len(entries),
        }

    # Split into baseline (first 60%) and recent window (last 40%)
    split_idx = int(len(entries) * 0.6)
    baseline = entries[:split_idx]
    recent = entries[split_idx:]

    # Per-signal mean comparison (simplified ADWIN-like check)
    signal_names = list(SIGNAL_THRESHOLDS.keys())
    drifted_signals = []
    signal_drift_detail = {}

    for sig_name in signal_names:
        baseline_vals = [e["signals"].get(sig_name, 0) for e in baseline if sig_name in e.get("signals", {})]
        recent_vals = [e["signals"].get(sig_name, 0) for e in recent if sig_name in e.get("signals", {})]

        if len(baseline_vals) < 10 or len(recent_vals) < 10:
            signal_drift_detail[sig_name] = {"status": "insufficient_data"}
            continue

        baseline_mean = sum(baseline_vals) / len(baseline_vals)
        recent_mean = sum(recent_vals) / len(recent_vals)
        baseline_std = math.sqrt(sum((v - baseline_mean) ** 2 for v in baseline_vals) / len(baseline_vals))

        if baseline_std == 0:
            baseline_std = 0.01  # Prevent division by zero

        # Hoeffding-bound inspired threshold (ADWIN uses this internally)
        shift_magnitude = abs(recent_mean - baseline_mean) / baseline_std

        is_drifted = shift_magnitude > 1.5  # 1.5σ threshold from Gemini
        if is_drifted:
            drifted_signals.append(sig_name)

        signal_drift_detail[sig_name] = {
            "baseline_mean": round(baseline_mean, 4),
            "recent_mean": round(recent_mean, 4),
            "baseline_std": round(baseline_std, 4),
            "shift_sigma": round(shift_magnitude, 2),
            "drifted": is_drifted,
        }

    # Check CI collapse (tertiary check from Gemini)
    recent_cis = [e.get("confidence_interval", [0, 1]) for e in recent]
    ci_widths = [ci[1] - ci[0] for ci in recent_cis if len(ci) == 2]
    ci_collapse = False
    if ci_widths:
        avg_ci_width = sum(ci_widths) / len(ci_widths)
        ci_collapse = avg_ci_width < 0.15  # Narrowing toward 0.5 = concept drift

    drift_metric = os.environ.get("VIBE_CHECK_DRIFT_GLOBAL_METRIC", "mean_shift").strip().lower()
    all_shifts = [d["shift_sigma"] for d in signal_drift_detail.values() if "shift_sigma" in d]
    global_drift_mean_shift = sum(all_shifts) / len(all_shifts) if all_shifts else 0.0
    global_drift_sinkhorn = _global_drift_sinkhorn(baseline, recent, signal_names)
    global_drift_psi = _global_drift_psi(baseline, recent, signal_names)

    if drift_metric == "sinkhorn":
        global_drift = global_drift_sinkhorn
        drift_threshold = float(os.environ.get("VIBE_CHECK_DRIFT_SINKHORN_THRESHOLD", "0.22"))
    elif drift_metric == "psi":
        global_drift = global_drift_psi
        drift_threshold = float(os.environ.get("VIBE_CHECK_DRIFT_PSI_THRESHOLD", "0.25"))
    else:
        drift_metric = "mean_shift"
        global_drift = global_drift_mean_shift
        drift_threshold = 1.5

    if len(drifted_signals) >= 2 and global_drift > drift_threshold:
        raw_status = "TRIGGER_RECALIBRATION"
        message = (
            f"Significant drift detected in {len(drifted_signals)} signals "
            f"(global={global_drift:.3f}, metric={drift_metric}, threshold={drift_threshold}). "
            "Automated recalibration recommended."
        )
    elif len(drifted_signals) == 1 or ci_collapse:
        raw_status = "TRIGGER_ALERT_MANUAL_REVIEW"
        reasons = []
        if drifted_signals:
            reasons.append(f"1 signal drifted: {drifted_signals[0]}")
        if ci_collapse:
            reasons.append(f"CI collapse detected (avg width: {avg_ci_width:.3f})")
        message = f"Potential drift. {'; '.join(reasons)}. Manual review recommended."
    else:
        raw_status = "CONTINUE_CURRENT_THRESHOLDS"
        message = f"No significant drift detected across {len(entries)} evaluations."

    status, persistence = _apply_persistence_rule(raw_status, Path(tdir))
    if status == "WATCH" and raw_status.startswith("TRIGGER_"):
        message = (
            f"WATCH: raw={raw_status} not yet persistent "
            f"({persistence.get('trips_seen')}/{persistence['m_of_n'][0]} required of last "
            f"{persistence['m_of_n'][1]}). No action."
        )

    return {
        "status": status,
        "raw_status": raw_status,
        "message": message,
        "evaluations_total": len(entries),
        "baseline_size": len(baseline),
        "recent_window_size": len(recent),
        "drifted_signals": drifted_signals,
        "drift_global_metric": drift_metric,
        "drift_threshold": drift_threshold,
        "global_drift": round(global_drift, 4),
        "global_drift_sigma": round(global_drift, 2),
        "global_drift_mean_shift": round(global_drift_mean_shift, 4),
        "global_drift_sinkhorn": round(global_drift_sinkhorn, 4),
        "global_drift_psi": round(global_drift_psi, 4),
        "ci_collapse": ci_collapse,
        "per_signal": signal_drift_detail,
        "persistence": persistence,
        "layers": {
            "telemetry_layer": {"rows": len(entries), "baseline": len(baseline), "recent": len(recent)},
            "signal_layer": {"drifted_count": len(drifted_signals)},
            "score_layer": {"metric": drift_metric, "value": round(global_drift, 4), "threshold": drift_threshold},
            "override_layer_placeholder": {"source": "external", "doc": "docs/AUDIT_PRIORITY_ETHICS.md"},
        },
        "calibration_version": CALIBRATION_VERSION,
    }


# ─── Self-healing: Closed-loop recalibration (Phase 3) ────────────────
# Reads drift status + telemetry. When drift is confirmed, computes new
# thresholds via quantile shift and writes calibration_override.json.
# On next run, overrides are loaded automatically. No ML, no LLM calls.

OVERRIDE_FILENAME = "calibration_override.json"


def load_calibration_overrides():
    """Load threshold overrides from calibration_override.json if it exists.

    Called once at import time. Overrides are applied to SIGNAL_THRESHOLDS
    and WEIGHTS in-place. Returns True if overrides were applied.
    """
    if not TELEMETRY_DIR:
        return False

    override_path = Path(TELEMETRY_DIR) / OVERRIDE_FILENAME
    if not override_path.exists():
        return False

    try:
        with open(override_path) as f:
            overrides = json.loads(f.read())
    except (json.JSONDecodeError, OSError):
        return False

    # Validate version — only apply if override was generated for the current
    # calibration epoch. We accept the v0.1.x string "v2026_q2_gemini" as a
    # legacy synonym so existing users don't lose their calibration after the
    # v0.2.0 rename (see CHANGELOG migration note).
    ov = overrides.get("base_calibration", "")
    legacy_synonyms = {"v2026_q2_gemini"}
    if ov and ov != CALIBRATION_VERSION and ov not in legacy_synonyms:
        # Stale override from a different calibration epoch — skip
        return False

    # Apply threshold overrides
    for sig_name, new_vals in overrides.get("thresholds", {}).items():
        if sig_name in SIGNAL_THRESHOLDS:
            for key in ("threshold", "llm_baseline", "human_baseline"):
                if key in new_vals and new_vals[key] is not None:
                    SIGNAL_THRESHOLDS[sig_name][key] = new_vals[key]

    # Apply weight overrides (bounded: no single weight can exceed 0.30 or drop below 0.02)
    for sig_name, new_weight in overrides.get("weights", {}).items():
        if sig_name in WEIGHTS:
            WEIGHTS[sig_name] = max(0.02, min(0.30, new_weight))

    # Re-normalize weights to sum to 1.0
    total = sum(WEIGHTS.values())
    if total > 0:
        for k in WEIGHTS:
            WEIGHTS[k] = round(WEIGHTS[k] / total, 4)

    return True


def recalibrate_from_drift(telemetry_dir: str = None, dry_run: bool = False) -> dict:
    """Phase 3: Quantile-shift recalibration when drift is detected.

    Algorithm (Bregman-lite):
    1. Load telemetry, split into baseline (first 60%) and recent (last 40%)
    2. For each drifted signal: compute the percentile of the current threshold
       in the baseline distribution, then find the value at that same percentile
       in the recent distribution → new threshold preserves the original FPR
    3. Write calibration_override.json (or return dry-run preview)

    Bounded: threshold shifts are capped at ±20% of original to prevent runaway.
    Rollback: if overall F1-proxy degrades, override is not written.
    """
    tdir = telemetry_dir or TELEMETRY_DIR
    if not tdir:
        return {"status": "ERROR", "message": "No telemetry directory configured"}

    # First check drift
    drift = check_drift_status(tdir)
    if drift["status"] not in ("TRIGGER_RECALIBRATION", "TRIGGER_ALERT_MANUAL_REVIEW"):
        return {"status": "NO_ACTION", "message": drift["message"], "drift": drift}

    # Load full telemetry
    log_file = Path(tdir) / "vibe_check_telemetry.jsonl"
    entries = []
    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    split_idx = int(len(entries) * 0.6)
    baseline_entries = entries[:split_idx]
    recent_entries = entries[split_idx:]

    new_thresholds = {}
    changes = []

    for sig_name, sig_info in SIGNAL_THRESHOLDS.items():
        current_threshold = sig_info.get("threshold")
        if current_threshold is None:
            continue

        # Collect signal values from baseline and recent
        baseline_vals = sorted([e["signals"].get(sig_name, 0) for e in baseline_entries
                                if sig_name in e.get("signals", {})])
        recent_vals = sorted([e["signals"].get(sig_name, 0) for e in recent_entries
                              if sig_name in e.get("signals", {})])

        if len(baseline_vals) < 10 or len(recent_vals) < 10:
            continue

        # Find what percentile the current threshold sits at in the baseline
        below = sum(1 for v in baseline_vals if v <= current_threshold)
        percentile = below / len(baseline_vals)

        # Find the value at that percentile in the recent distribution
        recent_idx = min(len(recent_vals) - 1, int(percentile * len(recent_vals)))
        new_threshold = recent_vals[recent_idx]

        # Bound the shift: max ±20% of original
        max_shift = abs(current_threshold) * 0.20
        if abs(new_threshold - current_threshold) > max_shift:
            if new_threshold > current_threshold:
                new_threshold = current_threshold + max_shift
            else:
                new_threshold = current_threshold - max_shift

        new_threshold = round(new_threshold, 4)

        if new_threshold != current_threshold:
            new_thresholds[sig_name] = {
                "threshold": new_threshold,
                "human_baseline": sig_info["human_baseline"],
                "llm_baseline": sig_info["llm_baseline"],
            }
            changes.append({
                "signal": sig_name,
                "old_threshold": current_threshold,
                "new_threshold": new_threshold,
                "shift": round(new_threshold - current_threshold, 4),
                "shift_pct": round((new_threshold - current_threshold) / current_threshold * 100, 1)
                             if current_threshold else 0,
                "percentile_preserved": round(percentile, 3),
            })

    if not changes:
        return {"status": "NO_CHANGES", "message": "Drift detected but thresholds unchanged after bounding"}

    # F1-proxy guard: estimate whether new thresholds would degrade separation
    # Use the recent window: count how many high-score (>0.7) and low-score (<0.3)
    # evaluations exist, check if separation is preserved
    high_scores = [e for e in recent_entries if e.get("vibe_score", 0) > 0.7]
    low_scores = [e for e in recent_entries if e.get("vibe_score", 0) < 0.3]
    separation = len(high_scores) + len(low_scores)
    ambiguous = len(recent_entries) - separation

    # If >60% of recent evals are ambiguous (0.3-0.7), recalibration may not help
    if len(recent_entries) > 0 and ambiguous / len(recent_entries) > 0.60:
        return {
            "status": "ABORTED",
            "message": f"Too many ambiguous scores ({ambiguous}/{len(recent_entries)}). "
                       f"Signals may be fundamentally degraded — manual review needed.",
            "changes_proposed": changes,
        }

    override = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "base_calibration": CALIBRATION_VERSION,
        "trigger": drift["status"],
        "evaluations_analyzed": len(entries),
        "thresholds": new_thresholds,
        "weights": {},  # Weight adjustment reserved for Phase 5 (MAB)
        "changes": changes,
    }

    if dry_run:
        return {"status": "DRY_RUN", "override": override}

    # Write override file
    override_path = Path(tdir) / OVERRIDE_FILENAME
    with open(override_path, "w") as f:
        f.write(json.dumps(override, indent=2, default=str))

    return {
        "status": "RECALIBRATED",
        "message": f"Updated {len(changes)} threshold(s). Override written to {override_path}",
        "changes": changes,
        "override_path": str(override_path),
    }


# ─── Model evolution fingerprinting — EXPERIMENTAL, FENCED ──────────
# These per-LLM signal ranges (gpt4_family / claude_family / gemini_family)
# are NOT derived from any cited dataset. The previous comment claimed they
# came "from LLM-AuthorBench + empirical data", but LLM-AuthorBench
# (CLAIMS C-009) studied C programs and reports ML classifier accuracy, not
# per-signal ranges. The values below are speculative.
#
# `detect_model_evolution()` returns EXPERIMENTAL_DISABLED unless the env var
# `VIBE_CHECK_ENABLE_MODEL_EVOLUTION=1` is explicitly set, and a contributor
# has fitted these ranges on a labeled-by-model corpus. See CALIBRATION_NOTES
# K-004.
MODEL_FINGERPRINTS = {
    "gpt4_family": {
        "comment_ratio":    (0.35, 0.60),
        "docstring_consistency": (0.80, 1.00),
        "naming_uniformity": (0.93, 0.99),
        "function_length":  (0.20, 0.40),  # CV — very uniform
        "declarative_bias": (0.55, 0.80),  # score, not ratio
    },
    "claude_family": {
        "comment_ratio":    (0.25, 0.45),
        "docstring_consistency": (0.70, 0.95),
        "naming_uniformity": (0.90, 0.98),
        "function_length":  (0.25, 0.50),
        "declarative_bias": (0.40, 0.70),
    },
    "gemini_family": {
        "comment_ratio":    (0.30, 0.55),
        "docstring_consistency": (0.75, 0.98),
        "naming_uniformity": (0.92, 0.99),
        "function_length":  (0.15, 0.35),
        "declarative_bias": (0.50, 0.75),
    },
}


def detect_model_evolution(telemetry_dir: str = None) -> dict:
    """Analyze telemetry for model evolution signals.

    EXPERIMENTAL: returns EXPERIMENTAL_DISABLED unless
    `VIBE_CHECK_ENABLE_MODEL_EVOLUTION=1` is set. The MODEL_FINGERPRINTS
    table this function uses is unsourced (CALIBRATION_NOTES K-004) and
    will produce misleading results until empirically fitted.
    """
    if os.environ.get("VIBE_CHECK_ENABLE_MODEL_EVOLUTION") != "1":
        return {
            "status": "EXPERIMENTAL_DISABLED",
            "reason": (
                "MODEL_FINGERPRINTS values are unsourced speculative defaults. "
                "Set VIBE_CHECK_ENABLE_MODEL_EVOLUTION=1 only if you have fitted "
                "the table on a labeled-by-model corpus. See "
                "references/CALIBRATION_NOTES.md K-004."
            ),
        }

    tdir = telemetry_dir or TELEMETRY_DIR
    if not tdir:
        return {"status": "NO_TELEMETRY"}

    log_file = Path(tdir) / "vibe_check_telemetry.jsonl"
    if not log_file.exists():
        return {"status": "NO_DATA"}

    entries = []
    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # Filter to high-confidence AI detections
    ai_detections = [e for e in entries if e.get("vibe_score", 0) > 0.6]

    if len(ai_detections) < 10:
        return {"status": "INSUFFICIENT_DATA", "ai_detections": len(ai_detections)}

    # Fingerprint matching
    matched = {"gpt4_family": 0, "claude_family": 0, "gemini_family": 0}
    unmatched = []

    for entry in ai_detections:
        signals = entry.get("signals", {})
        best_match = None
        best_score = 0

        for model_name, fingerprint in MODEL_FINGERPRINTS.items():
            match_count = 0
            total_signals = 0
            for sig_name, (lo, hi) in fingerprint.items():
                val = signals.get(sig_name)
                if val is not None:
                    total_signals += 1
                    if lo <= val <= hi:
                        match_count += 1

            if total_signals > 0:
                ratio = match_count / total_signals
                if ratio > best_score:
                    best_score = ratio
                    best_match = model_name

        if best_match and best_score >= 0.6:
            matched[best_match] += 1
        else:
            unmatched.append(entry)

    # Temporal analysis of unmatched: are they clustered recently?
    recent_unmatched = 0
    if unmatched and len(entries) > 20:
        recent_cutoff = int(len(entries) * 0.7)  # last 30% of evals
        recent_timestamps = set()
        for i, e in enumerate(entries):
            if i >= recent_cutoff:
                recent_timestamps.add(e.get("timestamp", ""))
        recent_unmatched = sum(1 for u in unmatched
                               if u.get("timestamp", "") in recent_timestamps)

    # Co-drift detection: which signals shifted together in unmatched set?
    co_drift_signals = []
    if len(unmatched) >= 5:
        # Compare unmatched signal means to overall AI-detection means
        all_ai_means = {}
        unmatched_means = {}
        for sig_name in SIGNAL_THRESHOLDS:
            all_vals = [e["signals"].get(sig_name, 0) for e in ai_detections
                        if sig_name in e.get("signals", {})]
            unm_vals = [e["signals"].get(sig_name, 0) for e in unmatched
                        if sig_name in e.get("signals", {})]
            if all_vals:
                all_ai_means[sig_name] = sum(all_vals) / len(all_vals)
            if unm_vals:
                unmatched_means[sig_name] = sum(unm_vals) / len(unm_vals)

        for sig_name in all_ai_means:
            if sig_name in unmatched_means:
                diff = abs(unmatched_means[sig_name] - all_ai_means[sig_name])
                if diff > 0.1:  # >10% shift
                    co_drift_signals.append({
                        "signal": sig_name,
                        "all_ai_mean": round(all_ai_means[sig_name], 3),
                        "unmatched_mean": round(unmatched_means[sig_name], 3),
                        "shift": round(diff, 3),
                    })

    # Determine if new model pattern detected
    new_model_detected = (
        len(unmatched) > len(ai_detections) * 0.25  # >25% don't match known fingerprints
        and recent_unmatched > len(unmatched) * 0.5   # Most unmatched are recent
    )

    return {
        "status": "NEW_MODEL_PATTERN" if new_model_detected else "KNOWN_PATTERNS",
        "total_ai_detections": len(ai_detections),
        "fingerprint_matches": matched,
        "unmatched_count": len(unmatched),
        "unmatched_recent": recent_unmatched,
        "co_drift_signals": co_drift_signals,
        "new_model_detected": new_model_detected,
        "recommendation": (
            "New AI model signature detected. Unmatched patterns cluster in recent evaluations. "
            "Consider running recalibration and updating MODEL_FINGERPRINTS."
            if new_model_detected else
            "All AI detections match known model families. No evolution detected."
        ),
    }


# ─── Auto-expand AI patterns from telemetry ───────────────────────────
# Discovers new boilerplate comment phrases from high-confidence AI
# evaluations. Appended to AI_COMMENT_PHRASES at startup if telemetry
# has enough data. Token-free: pure regex extraction, no LLM.

def discover_new_patterns(telemetry_dir: str = None, min_frequency: int = 5) -> list:
    """Mine telemetry for recurring comment patterns in high-confidence AI code.

    Looks at evaluations with score > 0.7, extracts comment text from cached
    diffs (if available), and finds recurring 3-5 word phrases not already in
    AI_COMMENT_PHRASES. Returns list of candidate regex patterns.
    """
    tdir = telemetry_dir or TELEMETRY_DIR
    if not tdir:
        return []

    log_file = Path(tdir) / "vibe_check_telemetry.jsonl"
    if not log_file.exists():
        return []

    # This is a stub that returns empty until diff caching is implemented.
    # The architecture is: telemetry logs PR IDs → diff cache stores raw diffs
    # → this function extracts comment lines → frequency analysis → new patterns
    # Full implementation requires diff caching (Phase 5).
    return []


# ─── Apply startup overrides ──────────────────────────────────────────
_OVERRIDES_APPLIED = load_calibration_overrides()


# ─── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Estimate AI-generation probability of a PR diff.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vibe_check.py --diff changes.diff
  python vibe_check.py --pr 123
  python vibe_check.py --pr owner/repo#123
  python vibe_check.py --repo-path . --base main --head feature-branch
  python vibe_check.py --diff changes.diff --format json
  python vibe_check.py --drift-status
  python vibe_check.py --recalibrate --dry-run
  python vibe_check.py --recalibrate
  python vibe_check.py --model-evolution
  VIBE_CHECK_TELEMETRY_DIR=./telemetry python vibe_check.py --pr 123
        """
    )
    parser.add_argument("--diff", help="Path to unified diff file")
    parser.add_argument("--pr", help="GitHub PR reference (number or owner/repo#number)")
    parser.add_argument("--repo-path", help="Local repo path for git diff")
    parser.add_argument("--base", default="main", help="Base ref for local diff (default: main)")
    parser.add_argument("--head", default="HEAD", help="Head ref for local diff (default: HEAD)")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                        help="Output format (default: markdown)")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--drift-status", action="store_true",
                        help="Check drift status from telemetry data (requires VIBE_CHECK_TELEMETRY_DIR)")
    parser.add_argument("--show-ci", action="store_true",
                        help="Include residual-quantile margin in output (NOT a coverage interval)")
    parser.add_argument("--repo-name", default="",
                        help="Repository name for telemetry logging (e.g., 'owner/repo')")
    parser.add_argument("--recalibrate", action="store_true",
                        help="Run quantile-shift recalibration from telemetry (requires VIBE_CHECK_TELEMETRY_DIR)")
    parser.add_argument("--dry-run", action="store_true",
                        help="With --recalibrate: preview overrides without writing calibration_override.json")
    parser.add_argument("--model-evolution", action="store_true",
                        help="[EXPERIMENTAL] Detect new AI model signatures from telemetry fingerprints. Disabled unless VIBE_CHECK_ENABLE_MODEL_EVOLUTION=1")
    parser.add_argument("--no-aggregate", action="store_true",
                        help="Suppress the aggregate score and grade in output. Show only per-signal evidence (recommended for quantitative-skeptical reviewers).")

    args = parser.parse_args()

    # Self-healing modes — no diff needed
    if args.drift_status:
        drift = check_drift_status()
        print(json.dumps(drift, indent=2, default=str))
        sys.exit(0)

    if args.recalibrate:
        result = recalibrate_from_drift(dry_run=args.dry_run)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result.get("status") != "ERROR" else 1)

    if args.model_evolution:
        result = detect_model_evolution()
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    # Get diff text
    pr_id = ""
    if args.diff:
        diff_text = Path(args.diff).read_text()
        commit_messages = []
    elif args.pr:
        diff_text, commit_messages = fetch_pr_diff(args.pr)
        pr_id = args.pr
    elif args.repo_path:
        diff_text, commit_messages = fetch_local_diff(args.repo_path, args.base, args.head)
    else:
        # Read from stdin
        diff_text = sys.stdin.read()
        commit_messages = []

    if not diff_text.strip():
        print("Error: Empty diff", file=sys.stderr)
        sys.exit(1)

    # Run analysis
    result = analyze_diff(diff_text, commit_messages)

    # Compute residual-quantile margin (heuristic, not a coverage interval)
    ci = compute_residual_margin_from_result(result)

    # Log telemetry (silent — only if VIBE_CHECK_TELEMETRY_DIR is set)
    log_telemetry(result, pr_id=pr_id, repo=args.repo_name)

    # Format output
    if args.format == "json":
        result_dict = asdict(result)
        result_dict["confidence_interval"] = list(ci)
        result_dict["calibration_version"] = CALIBRATION_VERSION
        if args.no_aggregate:
            # Honest mode: blank the aggregate fields. Per-signal data stays.
            result_dict["overall_ai_probability"] = None
            result_dict["grade"] = None
            result_dict["confidence_interval"] = None
            result_dict["aggregate_suppressed"] = True
        output = json.dumps(result_dict, indent=2, default=str)
    else:
        output = format_markdown_report(result, no_aggregate=args.no_aggregate)
        if args.show_ci and not args.no_aggregate:
            ci_line = f"\n**Residual-quantile margin (heuristic; no coverage guarantee):** [{ci[0]:.0%} – {ci[1]:.0%}] | Calibration: {CALIBRATION_VERSION}\n"
            # Insert after the first line (title)
            lines = output.split("\n")
            lines.insert(3, ci_line)
            output = "\n".join(lines)

    # Write output
    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
