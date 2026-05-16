"""
signals.py — Deterministic AI vibe-code signal detectors.
No network calls. All functions are pure: (text) -> list[str] of hit descriptors.

Tiers:
  T1  — metadata (highest precision; each hit weight 3.0)
  T2  — diff patterns (medium; each hit weight 1.5)
  T2b — Playwright test patterns (medium; each hit weight 1.5)
  T3  — PR body prose (lowest; conjunction-gated, each hit weight 0.5)

Score = sum(weights) / 9.0  (capped at 1.0)
Verdicts: strong >= 0.33 | moderate 0.17-0.32 | weak 0.06-0.16 | no_signal < 0.06
"""

import re
from collections import Counter

# ── Tier 1 ─────────────────────────────────────────────────────────────────

_AI_COAUTHOR = re.compile(
    r"(?im)^co-authored-by:.*"
    r"(claude|copilot|chatgpt|gpt-\d|openai|anthropic|cursor|gemini|qodo|codium|cody|tabnine)"
)
_AI_FOOTER = re.compile(
    r"(?i)(generated\s+(with|by|using)\s+(copilot|cursor|claude|gpt|ai)|"
    r"written\s+by\s+ai|ai[-\s]assisted)"
)
_AI_LABELS = {"skill-used", "cursor-command-supported", "ai-generated", "copilot", "ai-assisted"}
_QODO_WALKTHROUGH = re.compile(r"##\s*File\s+Walkthrough", re.IGNORECASE)
_MERMAID_BLOCK = re.compile(r"```mermaid", re.IGNORECASE)


def tier1_metadata(pr_body, commit_messages, labels):
    hits = []
    full_commits = "\n".join(commit_messages)
    if _AI_COAUTHOR.search(full_commits):
        hits.append("co_authored_by_ai")
    if _AI_FOOTER.search(pr_body):
        hits.append("ai_footer_in_body")
    matched_labels = _AI_LABELS & {l.lower() for l in labels}
    if matched_labels:
        hits.append("ai_labels:" + ",".join(sorted(matched_labels)))
    if _QODO_WALKTHROUGH.search(pr_body) and _MERMAID_BLOCK.search(pr_body):
        hits.append("qodo_merge_pr_body")
    return hits


# ── Tier 2 ─────────────────────────────────────────────────────────────────

_COMMENT_LINE = re.compile(r"^\+\s*(//|#|/\*|\*)", re.MULTILINE)
_ADDED_LINE = re.compile(r"^\+(?!\+\+)", re.MULTILINE)
_SECTION_DIVIDER = re.compile(r"^\+\s*(//|#)\s*[=\-\*]{3,}", re.MULTILINE)
_WHAT_NOT_WHY = re.compile(
    r"(?im)^\+\s*(//|#)\s*"
    r"(this\s+(function|method|class|file)|the\s+following|"
    r"initialize[s]?|validate[s]?|check[s]?\s+if|ensure[s]?\s+that)\b"
)
_PHP_USE = re.compile(r"^\+use\s+[\w\\]+;", re.MULTILINE)
_CATCH = re.compile(r"^\+\s*catch\s*\(", re.MULTILINE)
_FUNC_DEF = re.compile(r"^\+\s*(function|public\s+function|private\s+function|protected\s+function)\s+\w+", re.MULTILINE)
_PHPDOC_TAG = re.compile(r"^\+\s*\*\s*@(param|return|throws)\b", re.MULTILINE)
_COMPOUND_IDENT = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+){3,}\b")


def tier2_diff(diff_text):
    hits = []
    added_lines = _ADDED_LINE.findall(diff_text)
    total_added = len(added_lines)
    if total_added == 0:
        return hits

    comment_count = len(_COMMENT_LINE.findall(diff_text))
    comment_ratio = comment_count / total_added
    if comment_ratio > 0.30:
        hits.append("comment_ratio:%.2f" % comment_ratio)

    dividers = _SECTION_DIVIDER.findall(diff_text)
    if len(dividers) >= 2:
        hits.append("section_dividers:%d" % len(dividers))

    wny_count = len(_WHAT_NOT_WHY.findall(diff_text))
    wny_per_100 = wny_count / max(total_added, 1) * 100
    if wny_per_100 >= 3.0:
        hits.append("what_not_why_density:%.1f/100" % wny_per_100)

    php_uses = _PHP_USE.findall(diff_text)
    if php_uses:
        unused = []
        for stmt in php_uses:
            cls = stmt.rstrip(";").split("\\")[-1].strip()
            usage_re = re.compile(r"^\+(?!use\s)" + re.escape(cls), re.MULTILINE)
            if not usage_re.search(diff_text):
                unused.append(cls)
        if unused:
            hits.append("unused_imports:%d" % len(unused))

    catches = len(_CATCH.findall(diff_text))
    funcs = len(_FUNC_DEF.findall(diff_text))
    if funcs > 0 and catches / funcs > 0.5:
        hits.append("catch_scaffolding:%dcatches/%dfuncs" % (catches, funcs))

    phpdoc_tags = len(_PHPDOC_TAG.findall(diff_text))
    if funcs > 0 and phpdoc_tags / funcs > 2.0:
        hits.append("phpdoc_density:%dtags/%dfuncs" % (phpdoc_tags, funcs))

    compound_ids = _COMPOUND_IDENT.findall(diff_text)
    compound_density = len(compound_ids) / max(total_added, 1) * 100
    if compound_density > 5.0:
        hits.append("compound_identifiers:%.1f/100lines" % compound_density)

    return hits


# ── Tier 2b — Playwright ───────────────────────────────────────────────────

_WAIT_FOR_TIMEOUT = re.compile(r"waitForTimeout\(\d+\)")
_BRITTLE_SELECTOR = re.compile(r"(\.nth\(\d+\)|getByText\(['\"].{40,}['\"])")
_VERBOSE_TEST_NAME = re.compile(r"""test\s*\(\s*['"][^'"]{60,}['"]""")
_EXPECT = re.compile(r"\bexpect\s*\(")
_TEST_STEP = re.compile(r"\btest\.step\s*\(")
_LOCATOR_CALL = re.compile(r"(page\.locator|getByRole|getByLabel|getByText|getByTestId)\s*\([^)]+\)")


def tier2b_playwright(diff_text):
    hits = []

    wft = _WAIT_FOR_TIMEOUT.findall(diff_text)
    if wft:
        hits.append("wait_for_timeout:%d" % len(wft))

    brittle = _BRITTLE_SELECTOR.findall(diff_text)
    if brittle:
        hits.append("brittle_selectors:%d" % len(brittle))

    verbose_names = _VERBOSE_TEST_NAME.findall(diff_text)
    if verbose_names:
        hits.append("verbose_test_names:%d" % len(verbose_names))

    expect_count = len(_EXPECT.findall(diff_text))
    step_count = len(_TEST_STEP.findall(diff_text))
    if expect_count > 0 and (step_count == 0 or expect_count / max(step_count, 1) > 8):
        hits.append("flat_assertion_density:expect=%d,steps=%d" % (expect_count, step_count))

    locator_calls = _LOCATOR_CALL.findall(diff_text)
    if locator_calls:
        c = Counter(locator_calls)
        redundant = {k: v for k, v in c.items() if v > 2}
        if redundant:
            hits.append("redundant_assertions:%dlocators" % len(redundant))

    return hits


# ── Tier 3 ─────────────────────────────────────────────────────────────────

_AI_PHRASES = re.compile(
    r"(?i)(i\s+hope\s+this\s+helps|feel\s+free\s+to|"
    r"let\s+me\s+know\s+if\s+you\s+need|happy\s+to\s+help)"
)
_PERFECT_SECTIONS = re.compile(
    r"##\s*Background.+##\s*Implementation.+##\s*Testing",
    re.DOTALL | re.IGNORECASE,
)
_THIS_PR_OPENER = re.compile(r"(?im)^this\s+pr\b")


def tier3_body(pr_body, author_pr_count=999):
    hits = []
    phrase_hits = _AI_PHRASES.findall(pr_body)
    if len(phrase_hits) >= 2:
        hits.append("ai_phrases:%d" % len(phrase_hits))
    if _PERFECT_SECTIONS.search(pr_body) and author_pr_count < 5:
        hits.append("perfect_section_template_new_author")
    if _THIS_PR_OPENER.search(pr_body):
        hits.append("this_pr_opener")
    # Conjunction gate: require 2+ distinct hits
    return hits if len(hits) >= 2 else []


# ── Scoring ─────────────────────────────────────────────────────────────────

WEIGHTS = {"T1": 3.0, "T2": 1.5, "T2b": 1.5, "T3": 0.5}
SCORE_CAP = 9.0


def score(t1, t2, t2b, t3):
    raw = (
        len(t1) * WEIGHTS["T1"]
        + len(t2) * WEIGHTS["T2"]
        + len(t2b) * WEIGHTS["T2b"]
        + len(t3) * WEIGHTS["T3"]
    )
    s = min(raw / SCORE_CAP, 1.0)
    if s >= 0.33:
        verdict = "strong"
    elif s >= 0.17:
        verdict = "moderate"
    elif s >= 0.06:
        verdict = "weak"
    else:
        verdict = "no_signal"
    return round(s, 4), verdict
