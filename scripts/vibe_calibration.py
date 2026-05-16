#!/usr/bin/env python3
"""
vibe_calibration.py — Baseline calibration for vibe_check.py (stratified PR sampling).

Phases 1–6 per references/PROMPT_CALIBRATION_AGENT.md.
Requires: Python 3.10+, gh CLI authenticated for the target host.

Usage:
  python scripts/vibe_calibration.py --gh-repo owner/repo [--root /path/to/vibe-check] [--output-dir ...]

Environment:
  GH_HOST=<your.github.host>   (optional; defaults to gh's configured host)
  VIBE_CALIBRATION_GH_REPO=owner/repo   (default if --gh-repo omitted)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median, mean, variance, stdev
from typing import Any, Optional

ROOT_DEFAULT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent

EXT_TO_LANG = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "JavaScript",
    ".tsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
}

SIZE_BINS = ["<50", "50-200", "200-500", "500-2000", ">2000"]
SIGNAL_KEYS = [
    "ccr",
    "docstring_pct",
    "naming_uniform_pct",
    "error_pattern_rate",
    "decl_bias",
    "func_len_mean",
    "func_len_cv",
    "comment_phrase_pct",
    "halluc_api_count",
    "edge_case_depth",
    "commit_ai_marker_pct",
]

Z_A, Z_B, D_COHEN = 1.96, 0.84, 0.5
N_FORMULA = int(math.ceil(2 * ((Z_A + Z_B) / D_COHEN) ** 2))  # ~31


def load_vibe_check():
    path = SCRIPT_DIR / "vibe_check.py"
    spec = importlib.util.spec_from_file_location("vibe_check", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def _gh_cmd(repo: str, args: list[str]) -> list[str]:
    """Build gh argv: `repo view` uses OWNER/REPO positional; `pr *` uses --repo."""
    if len(args) >= 2 and args[0] == "repo" and args[1] == "view":
        return ["gh", "repo", "view", repo] + args[2:]
    return ["gh"] + args + ["--repo", repo]


def gh_json(repo: str, args: list[str], budget: list, cost: int = 1) -> Any:
    """Run gh with JSON output; decrement budget[0] by cost (default 1)."""
    cmd = _gh_cmd(repo, args)
    out = subprocess.check_output(cmd, text=True, timeout=120)
    budget[0] -= cost
    return json.loads(out)


def gh_text(repo: str, args: list[str], budget: list, cost: int = 1) -> str:
    cmd = _gh_cmd(repo, args)
    out = subprocess.check_output(cmd, text=True, timeout=120)
    budget[0] -= cost
    return out


def size_stratum(additions: int, deletions: int) -> str:
    s = (additions or 0) + (deletions or 0)
    if s < 50:
        return "<50"
    if s < 200:
        return "50-200"
    if s < 500:
        return "200-500"
    if s < 2000:
        return "500-2000"
    return ">2000"


def infer_pr_type(pr: dict) -> str:
    labels = [str(x.get("name", "")).lower() for x in (pr.get("labels") or [])]
    head = (pr.get("headRefName") or "").lower()
    title = (pr.get("title") or "").lower()

    if "hotfix/" in head or head.startswith("hotfix/"):
        return "hotfix"

    def has_any(words):
        return any(w in labels for w in words)

    if has_any(["bug", "fix", "bugfix"]):
        return "bug_fix"
    if has_any(["feature", "feat"]):
        return "feature"
    if has_any(["refactor"]):
        return "refactor"
    if has_any(["docs", "doc"]):
        return "docs"
    if has_any(["test"]):
        return "test"
    if has_any(["config", "ci", "deployment"]):
        return "config"

    if re.search(r"\b(fix|fixed|fixes)\b", title):
        return "bug_fix"
    if re.search(r"\b(add|feature|new)\b", title):
        return "feature"
    if "refactor" in title:
        return "refactor"
    if re.search(r"\b(doc|docs)\b", title):
        return "docs"
    if "test" in title:
        return "test"

    return "feature"


def enumerate_files_git(repo_path: Path) -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(repo_path), "ls-tree", "-r", "HEAD", "--name-only"],
        text=True,
        timeout=60,
        stderr=subprocess.DEVNULL,
    )
    return [ln for ln in out.splitlines() if ln.strip()]


def enumerate_files_walk(root: Path) -> list[str]:
    skip = {".git", "__pycache__", ".venv", "node_modules", ".mypy_cache"}
    paths = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in skip or part.startswith(".") for part in rel.parts):
            continue
        paths.append(str(rel).replace(os.sep, "/"))
    return paths


def language_profile(root: Path, out_tsv: Path, repo: str, budget: list) -> dict:
    meta = gh_json(repo, ["repo", "view", "--json", "primaryLanguage,url,nameWithOwner"], budget)
    primary = (meta.get("primaryLanguage") or {}).get("name", "unknown")

    try:
        files = enumerate_files_git(root)
        source = "git_ls_tree_HEAD"
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = enumerate_files_walk(root)
        source = "walk_workspace"

    ext_counts: Counter[str] = Counter()
    ext_lines: dict[str, int] = defaultdict(int)

    for f in files:
        suf = Path(f).suffix.lower()
        if not suf:
            continue
        ext_counts[suf] += 1
        fp = root / f
        if fp.is_file():
            try:
                with fp.open("r", encoding="utf-8", errors="ignore") as fh:
                    ext_lines[suf] += sum(1 for _ in fh)
            except OSError:
                pass

    lang_files: Counter[str] = Counter()
    lang_lines: dict[str, int] = defaultdict(int)
    for ext, c in ext_counts.items():
        lang = EXT_TO_LANG.get(ext)
        if not lang:
            continue
        lang_files[lang] += c
        lang_lines[lang] += ext_lines.get(ext, 0)

    total_f = sum(lang_files.values()) or 1
    total_l = sum(lang_lines.values()) or 1

    rows = []
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w") as w:
        w.write("lang\tfile_count\tpct_count\tline_count\tpct_lines\n")
        for lang in sorted(lang_files.keys()):
            fc = lang_files[lang]
            lc = lang_lines[lang]
            rows.append(
                {
                    "lang": lang,
                    "file_count": fc,
                    "pct_count": round(100 * fc / total_f, 4),
                    "line_count": lc,
                    "pct_lines": round(100 * lc / total_l, 4),
                }
            )
            w.write(f"{lang}\t{fc}\t{100 * fc / total_f:.6f}\t{lc}\t{100 * lc / total_l:.6f}\n")

    return {
        "primaryLanguage_gh": primary,
        "enumeration": source,
        "rows": rows,
        "repo_meta": meta,
    }


def parse_signal_row(signals: list[dict], weight: int) -> dict[str, float]:
    """Parse per-file signals into metric dict; caller aggregates by weight."""
    out: dict[str, float] = {}
    by_name = {s["name"]: s for s in signals}

    def g(name):
        return by_name.get(name, {})

    def expl(name):
        return g(name).get("explanation") or ""

    cr = g("comment_ratio")
    m = re.search(r"CCR=([\d.]+)", expl("comment_ratio"))
    out["ccr"] = float(m.group(1)) if m else float(cr.get("score", 0.5))

    ds = expl("docstring_consistency")
    m = re.search(r"(\d+)/(\d+) functions", ds)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        out["docstring_pct"] = (a / b) if b else 0.0
    else:
        out["docstring_pct"] = float(g("docstring_consistency").get("score", 0.5))

    nm = expl("naming_uniformity")
    m = re.search(r"uniformity:\s*(\d+)%", nm) or re.search(r"Naming\s+(\d+)%", nm)
    out["naming_uniform_pct"] = (float(m.group(1)) / 100.0) if m else float(g("naming_uniformity").get("score", 0.5))

    out["error_pattern_rate"] = float(g("error_handling").get("score", 0.5))

    db = expl("declarative_bias")
    m = re.search(r"Ratio=([\d.]+)", db)
    out["decl_bias"] = float(m.group(1)) if m else float(g("declarative_bias").get("score", 0.5))

    fl = expl("function_length")
    m = re.search(r"Avg length=([\d.]+).*CV=([\d.]+)", fl)
    if m:
        out["func_len_mean"] = float(m.group(1))
        out["func_len_cv"] = float(m.group(2))
    else:
        out["func_len_mean"] = float("nan")
        out["func_len_cv"] = float("nan")

    cp = expl("comment_phrasing")
    m = re.search(r"(\d+)/(\d+) comments", cp)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        out["comment_phrase_pct"] = (a / b) if b else 0.0
    else:
        out["comment_phrase_pct"] = float(g("comment_phrasing").get("score", 0.5))

    ha = expl("hallucinated_apis")
    m = re.search(r"Found\s+(\d+)\s+potential", ha)
    out["halluc_api_count"] = float(m.group(1)) if m else 0.0

    ed = expl("edge_case_depth")
    m = re.search(r"Depth=(\d+)", ed)
    out["edge_case_depth"] = float(m.group(1)) if m else float(g("edge_case_depth").get("score", 0.5))

    out["_weight"] = float(weight)
    return out


def aggregate_file_metrics(file_analyses: list[dict]) -> dict[str, float]:
    acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for fa in file_analyses:
        w = float(fa.get("added_lines") or 0)
        if w <= 0:
            continue
        row = parse_signal_row(fa.get("signals") or [], int(w))
        ww = row.pop("_weight")
        for k, v in row.items():
            if k == "halluc_api_count":
                acc[k].append((v, ww))  # sum weighted by file
            elif math.isnan(v):
                continue
            else:
                acc[k].append((v, ww))
    out: dict[str, float] = {}
    for k, pairs in acc.items():
        if not pairs:
            out[k] = float("nan")
            continue
        if k == "halluc_api_count":
            out[k] = float(sum(p[0] for p in pairs))
        else:
            tw = sum(p[1] for p in pairs)
            out[k] = sum(p[0] * p[1] for p in pairs) / tw if tw else float("nan")

    # commit_metadata is PR-level: take from last file's absence — inject from signal_summary
    return out


def dominant_language_from_diff(vc_mod, diff_text: str) -> str:
    hunks = vc_mod.parse_unified_diff(diff_text)
    loc_by_lang: Counter[str] = Counter()
    for h in hunks:
        lang = vc_mod.detect_language(h.filepath)
        if lang == "unknown":
            continue
        n = len(h.added_lines)
        display = {
            "python": "Python",
            "javascript": "JavaScript",
            "typescript": "JavaScript",
            "go": "Go",
            "java": "Java",
            "ruby": "Ruby",
            "rust": "Rust",
            "cpp": "C++",
            "c": "C",
            "csharp": "C#",
            "php": "PHP",
            "swift": "Swift",
            "kotlin": "Kotlin",
            "scala": "Scala",
        }.get(lang, lang.title())
        loc_by_lang[display] += n
    if not loc_by_lang:
        return "unknown"
    return loc_by_lang.most_common(1)[0][0]


def run_vibe_on_pr(vc_mod, diff_text: str, commits: list[str]) -> dict[str, Any]:
    result = vc_mod.analyze_diff(diff_text, commits)
    file_analyses = result.file_analyses
    metrics = aggregate_file_metrics(file_analyses)
    cm = result.signal_summary.get("commit_metadata") or {}
    metrics["commit_ai_marker_pct"] = float(cm.get("avg_score", 0.0))
    depths: list[float] = []
    for fa in file_analyses:
        for s in fa.get("signals") or []:
            if s.get("name") == "edge_case_depth":
                m = re.search(r"Depth=(\d+)", s.get("explanation") or "")
                if m:
                    depths.append(float(m.group(1)))
    if depths:
        metrics["edge_case_depth"] = max(depths)
    return {
        "metrics": metrics,
        "file_analyses": file_analyses,
        "signal_summary": result.signal_summary,
        "grade": result.grade,
    }


def fetch_pr_bundle(repo: str, num: int, budget: list) -> tuple[str, list[str]]:
    """Cost model: 5 for pr view JSON, 1 for pr diff (per calibration prompt)."""
    view = gh_json(
        repo,
        [
            "pr",
            "view",
            str(num),
            "--json",
            "commits,files",
        ],
        budget,
        cost=5,
    )
    diff = gh_text(repo, ["pr", "diff", str(num), "--color=never"], budget, cost=1)
    commits = []
    for c in view.get("commits") or []:
        commits.append(c.get("messageHeadline") or "")
    return diff, commits


def stats_dict(values: list[float]) -> dict[str, float]:
    xs = sorted(v for v in values if not math.isnan(v))
    if not xs:
        return {"mean": float("nan"), "median": float("nan"), "std": float("nan"), "q25": float("nan"), "q75": float("nan"), "p5": float("nan"), "p95": float("nan")}
    n = len(xs)

    def pct(p):
        if n == 1:
            return xs[0]
        k = (n - 1) * p / 100.0
        lo = int(math.floor(k))
        hi = int(math.ceil(k))
        if lo == hi:
            return xs[lo]
        return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)

    mu = mean(xs)
    sd = stdev(xs) if n > 1 else 0.0
    return {
        "mean": round(mu, 6),
        "median": round(median(xs), 6),
        "std": round(sd, 6),
        "q25": round(pct(25), 6),
        "q75": round(pct(75), 6),
        "p5": round(pct(5), 6),
        "p95": round(pct(95), 6),
    }


def stratified_sample(pool: list[dict], target_n: int, rng: random.Random) -> list[dict]:
    if not pool:
        return []
    by_cell: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for pr in pool:
        sz = size_stratum(pr.get("additions") or 0, pr.get("deletions") or 0)
        ty = infer_pr_type(pr)
        by_cell[(sz, ty)].append(pr)

    cells = list(by_cell.keys())
    rng.shuffle(cells)
    quota = max(3, target_n // max(len(cells), 1))
    picked: list[dict] = []
    used = set()

    for cell in cells:
        opts = [p for p in by_cell[cell] if p["number"] not in used]
        rng.shuffle(opts)
        take = min(quota, len(opts), max(0, target_n - len(picked)))
        for p in opts[:take]:
            picked.append(p)
            used.add(p["number"])

    remainder = [p for p in pool if p["number"] not in used]
    rng.shuffle(remainder)
    for p in remainder:
        if len(picked) >= target_n:
            break
        if p["number"] in used:
            continue
        picked.append(p)
        used.add(p["number"])

    authors = {((p.get("author") or {}).get("login") or "unknown") for p in picked}
    if len(authors) < 10:
        for p in pool:
            if len(picked) >= min(target_n + 20, len(pool)):
                break
            a = (p.get("author") or {}).get("login") or "unknown"
            if p["number"] in used or a in authors:
                continue
            picked.append(p)
            used.add(p["number"])
            authors.add(a)
            if len(authors) >= 10:
                break
    return picked[:target_n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT_DEFAULT, help="Repo root for language profile / git ls-tree")
    ap.add_argument("--gh-repo", default=os.environ.get("VIBE_CALIBRATION_GH_REPO", ""), help="owner/name for gh")
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DEFAULT / "outputs" / "vibe-baseline-calibration",
        help="Directory for calibration.json, sampling_log.tsv, language_profile.tsv, summary.txt",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--merged-after", default="2025-04-16")
    ap.add_argument("--sample-date", default="2026-04-16")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    repo = args.gh_repo.strip()
    if not repo:
        print("ERROR: set --gh-repo or VIBE_CALIBRATION_GH_REPO (owner/name).", file=sys.stderr)
        sys.exit(2)

    budget = [5000]
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    vc_mod = load_vibe_check()

    lang_meta = language_profile(args.root, out_dir / "language_profile.tsv", repo, budget)

    search = f'is:merged merged:>={args.merged_after}'
    pr_list = gh_json(
        repo,
        [
            "pr",
            "list",
            "--search",
            search,
            "--limit",
            "500",
            "--json",
            "number,title,labels,baseRefName,headRefName,additions,deletions,author,mergedAt",
        ],
        budget,
    )

    if not pr_list:
        notes = f"No merged PRs returned for {search}. Nothing to sample."
        calibration = {
            "metadata": {
                "repo": (lang_meta.get("repo_meta") or {}).get("url", repo),
                "sample_size": 0,
                "sample_date": args.sample_date,
                "languages": sorted({r["lang"] for r in lang_meta["rows"]}),
                "time_period": f"{args.merged_after} to {args.sample_date}",
            },
            "baselines": {"overall": {}, "by_language": {}, "by_type": {}},
            "variant_distribution": {},
            "author_count": 0,
            "notes": notes,
            "pilot_stats": {},
            "n_required": 0,
            "budget_remaining": budget[0],
        }
        (out_dir / "calibration.json").write_text(json.dumps(calibration, indent=2))
        (out_dir / "sampling_log.tsv").write_text("\t".join(["pr_number", "type", "size_stratum", "lang"] + SIGNAL_KEYS) + "\n")
        (out_dir / "summary.txt").write_text(notes[:500])
        print(notes, file=sys.stderr)
        sys.exit(0)

    pilot_n = min(30, len(pr_list))
    pilot = rng.sample(pr_list, pilot_n)

    pilot_rows: list[dict[str, float]] = []
    cache: dict[int, tuple[str, list[str]]] = {}

    def get_bundle(num: int):
        if num not in cache:
            if budget[0] < 6:
                raise RuntimeError("budget_exhausted")
            cache[num] = fetch_pr_bundle(repo, num, budget)
        return cache[num]

    for pr in pilot:
        try:
            diff, commits = get_bundle(pr["number"])
        except Exception as e:
            print(f"pilot skip PR#{pr['number']}: {e}", file=sys.stderr)
            continue
        try:
            vr = run_vibe_on_pr(vc_mod, diff, commits)
            m = vr["metrics"]
            pilot_rows.append({k: m.get(k, float("nan")) for k in SIGNAL_KEYS})
        except Exception as e:
            print(f"pilot analyze PR#{pr['number']}: {e}", file=sys.stderr)

    pilot_var = {}
    for k in SIGNAL_KEYS:
        vals = [r[k] for r in pilot_rows if not math.isnan(r.get(k, float("nan")))]
        if len(vals) > 1:
            pilot_var[k] = variance(vals)
        else:
            pilot_var[k] = 0.01

    med_var = median(pilot_var.values()) if pilot_var else 0.01
    scale = max(med_var, 1e-6) / 0.02
    n_required = min(500, max(N_FORMULA, int(math.ceil(N_FORMULA * scale))))
    n_required = max(n_required, min(len(pr_list), pilot_n))

    target_n = min(n_required, len(pr_list), 500)
    final_prs = stratified_sample(pr_list, target_n, rng)

    rows_out: list[dict[str, Any]] = []
    variant_counts: Counter[str] = Counter()
    authors: set[str] = set()

    for pr in final_prs:
        try:
            diff, commits = get_bundle(pr["number"])
        except Exception as e:
            print(f"skip PR#{pr['number']}: {e}", file=sys.stderr)
            continue
        sz = size_stratum(pr.get("additions") or 0, pr.get("deletions") or 0)
        ty = infer_pr_type(pr)
        variant_counts[ty] += 1
        authors.add(((pr.get("author") or {}).get("login") or "unknown"))

        try:
            vr = run_vibe_on_pr(vc_mod, diff, commits)
            lang = dominant_language_from_diff(vc_mod, diff)
            m = vr["metrics"]
            row = {
                "pr_number": pr["number"],
                "type": ty,
                "size_stratum": sz,
                "lang": lang,
            }
            for k in SIGNAL_KEYS:
                row[k] = m.get(k, float("nan"))
            rows_out.append(row)
        except Exception as e:
            print(f"analyze PR#{pr['number']}: {e}", file=sys.stderr)

    strata_counts: Counter[tuple[str, str]] = Counter()
    for r in rows_out:
        strata_counts[(r["size_stratum"], r["type"])] += 1

    def baseline_for(rows: list[dict], key_prefix: str = "") -> dict[str, dict]:
        out = {}
        for k in SIGNAL_KEYS:
            vals = [float(r[k]) for r in rows if isinstance(r.get(k), (int, float)) and not math.isnan(float(r[k]))]
            out[k] = stats_dict(vals)
        return out

    overall_rows = rows_out
    by_lang: dict[str, list[dict]] = defaultdict(list)
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in rows_out:
        by_lang[r["lang"]].append(r)
        by_type[r["type"]].append(r)

    calibration = {
        "metadata": {
            "repo": (lang_meta.get("repo_meta") or {}).get("url", repo),
            "github_repo": repo,
            "sample_size": len(rows_out),
            "sample_date": args.sample_date,
            "languages": sorted({r["lang"] for r in lang_meta["rows"]}),
            "profile_enumeration": lang_meta.get("enumeration"),
            "primaryLanguage_github": lang_meta.get("primaryLanguage_gh"),
            "time_period": f"{args.merged_after} to {args.sample_date}",
        },
        "baselines": {
            "overall": baseline_for(overall_rows),
            "by_language": {lg: baseline_for(rs) for lg, rs in sorted(by_lang.items()) if lg != "unknown"},
            "by_type": {t: baseline_for(rs) for t, rs in sorted(by_type.items())},
        },
        "variant_distribution": dict(variant_counts),
        "author_count": len(authors),
        "stratum_counts": {f"{a}|{b}": c for (a, b), c in strata_counts.items()},
        "pilot_stats": {"variance": pilot_var, "n_pilot": pilot_n},
        "n_required": min(n_required, len(pr_list)),
        "n_required_formula_uncapped": n_required,
        "pr_pool_size": len(pr_list),
        "budget_remaining": budget[0],
        "notes": "",
    }

    notes_parts = []
    if n_required >= 500:
        notes_parts.append("N_required capped at 500.")
    if len(pr_list) < N_FORMULA:
        notes_parts.append(f"Small pool ({len(pr_list)} PRs); baselines are indicative only.")

    undersampled = [f"{a}|{b}" for (a, b), c in strata_counts.items() if c < 3]
    if undersampled:
        notes_parts.append("Undersampled strata (N<3): " + ", ".join(undersampled[:12]))

    for lg, bl in calibration["baselines"]["by_language"].items():
        ov = calibration["baselines"]["overall"]
        for sig in SIGNAL_KEYS:
            om, lm = ov.get(sig, {}).get("mean"), bl.get(sig, {}).get("mean")
            osd = ov.get(sig, {}).get("std") or 0
            if om is None or lm is None or math.isnan(om) or math.isnan(lm):
                continue
            if osd and abs(lm - om) > osd:
                notes_parts.append(f"Outlier: {sig} in {lg} >1SD from overall.")

    if rows_out:
        bf = [r for r in rows_out if r["type"] == "bug_fix"]
        oth = [r for r in rows_out if r["type"] != "bug_fix"]
        if bf and oth:
            for sig in ["error_pattern_rate", "ccr"]:
                mb = mean(float(x[sig]) for x in bf if not math.isnan(float(x[sig])))
                mo = mean(float(x[sig]) for x in oth if not math.isnan(float(x[sig])))
                if mb > mo:
                    notes_parts.append(f"bug_fix mean {sig} ({mb:.3f}) > other ({mo:.3f}).")

    notes_parts.append("Alert rule of thumb: flag PR if signal differs from overall mean by >2*std.")
    if not args.root.joinpath(".git").exists():
        notes_parts.append("Language profile used workspace walk (no .git at --root).")

    calibration["notes"] = " ".join(notes_parts)[:2000]
    (out_dir / "calibration.json").write_text(json.dumps(calibration, indent=2, default=str))

    with (out_dir / "sampling_log.tsv").open("w") as w:
        w.write("\t".join(["pr_number", "type", "size_stratum", "lang"] + SIGNAL_KEYS) + "\n")
        for r in rows_out:
            w.write(
                "\t".join(
                    [str(r["pr_number"]), r["type"], r["size_stratum"], r["lang"]]
                    + [("" if isinstance(r[k], float) and math.isnan(r[k]) else str(r[k])) for k in SIGNAL_KEYS]
                )
                + "\n"
            )

    summary = (
        f"Repo {repo}: sampled {len(rows_out)} merged PRs ({args.merged_after}+). "
        f"Authors={len(authors)}. N_required={n_required} (pilot n={pilot_n}). "
        f"Budget left={budget[0]}. Primary language (GitHub)={lang_meta.get('primaryLanguage_gh')}. "
        + " ".join(notes_parts)[:1800]
    )
    words = summary.split()
    if len(words) > 200:
        summary = " ".join(words[:200]) + " …"
    (out_dir / "summary.txt").write_text(summary)

    print(json.dumps({"output_dir": str(out_dir), "sample_size": len(rows_out), "budget": budget[0]}, indent=2))


if __name__ == "__main__":
    main()
