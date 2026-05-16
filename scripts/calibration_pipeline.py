#!/usr/bin/env python3
"""
PR calibration pipeline: labeled PR discovery, vibe_check signals, semi-supervised
expansion, stats. Enforces API call budgets (gh invocations).

Usage:
  python calibration_pipeline.py --repo OWNER/REPO [--out-dir DIR]

Requires: gh CLI authenticated; vibe_check.py sibling in scripts/.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

# ─── Budgets (anti-cascade) ─────────────────────────────────────────────
API_TOTAL = 3000
PR_DETAIL_CAP = 300
P1_API = 200
P2_API = 1500
P3_API = 1000
P2_MAX_PRS = 150
P3_SAMPLE = 100
P3_LIST_LIMIT = 500

SCRIPT_DIR = Path(__file__).resolve().parent
VIBE_CHECK = SCRIPT_DIR / "vibe_check.py"
REPO_ROOT = SCRIPT_DIR.parent

SIGNAL_INTERNAL = [
    "comment_ratio",
    "docstring_consistency",
    "naming_uniformity",
    "error_handling",
    "declarative_bias",
    "function_length",
    "comment_phrasing",
    "hallucinated_apis",
    "edge_case_depth",
    "commit_metadata",
]
SIGNAL_SHORT = [
    "ccr",
    "docstring",
    "naming",
    "error_handling",
    "declarative",
    "func_length",
    "comment_phrasing",
    "hallucinated",
    "edge_depth",
    "commit_meta",
]
CURRENT_DECISION_T = 0.5  # operational binary threshold on avg_score (vibe_check scale 0–1)

Z_A = 1.96
Z_B = 0.84


@dataclass
class Budget:
    total: int = 0
    p1: int = 0
    p2: int = 0
    p3: int = 0
    pr_detail: int = 0
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def gh(self, phase: str) -> bool:
        if self.total >= API_TOTAL:
            return False
        lim = {"1": P1_API, "2": P2_API, "3": P3_API}.get(phase, API_TOTAL)
        cur = {"1": self.p1, "2": self.p2, "3": self.p3}.get(phase, self.total)
        if cur >= lim:
            return False
        self.total += 1
        if phase == "1":
            self.p1 += 1
        elif phase == "2":
            self.p2 += 1
        elif phase == "3":
            self.p3 += 1
        return True

    def pr_detail_ok(self) -> bool:
        return self.pr_detail < PR_DETAIL_CAP


def run_gh(
    budget: Budget,
    phase: str,
    repo: str,
    args: list[str],
    *,
    stdin: Optional[str] = None,
) -> tuple[int, str]:
    if not budget.gh(phase):
        return -1, ""
    cmd = ["gh", "-R", repo] + args
    try:
        r = subprocess.run(
            cmd,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=120,
            env={**os.environ},
        )
        if r.returncode != 0:
            budget.errors.append(f"gh fail {' '.join(cmd)}: {r.stderr[:200]}")
        return r.returncode, r.stdout or ""
    except Exception as e:
        budget.errors.append(f"gh exc {' '.join(cmd)}: {e}")
        return 999, ""


def classify_label(name: str) -> tuple[str, str]:
    """
    Returns (bucket, label_class) where label_class is vibe-coded|ai-assisted|human-written|ignore
    """
    low = name.strip().lower().replace("_", " ")
    if low in {"vibe coded", "vibe-coded", "vibecoded"}:
        return ("vibe", "vibe-coded")
    if low in {"human written", "human-written", "manual", "hand coded", "hand-coded"}:
        return ("human", "human-written")
    if low in {"ai generated", "ai-generated", "ai assisted", "ai-assisted", "copilot", "cursor"}:
        return ("ai", "ai-assisted")
    if any(h in low for h in ("human-written", "human written", "hand-coded", "hand coded", "manual")):
        return ("human", "human-written")
    if "vibe" in low:
        return ("vibe", "vibe-coded")
    if any(x in low for x in ("copilot", "cursor")):
        return ("ai", "ai-assisted")
    if "llm" in low or "generated" in low:
        return ("ai", "ai-assisted")
    if "auto" in low and ("code" in low or "gen" in low):
        return ("ai", "ai-assisted")
    if "ai" in low:
        if "human" in low or "anti-ai" in low or "no ai" in low:
            return ("ignore", "ignore")
        return ("ai", "ai-assisted")
    return ("ignore", "ignore")


def label_priority(lc: str) -> int:
    return {"vibe-coded": 0, "ai-assisted": 1, "human-written": 2}.get(lc, 9)


def parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def mean_vec(rows: list[dict], keys: list[str]) -> list[float]:
    if not rows:
        return [0.0] * len(keys)
    acc = [0.0] * len(keys)
    for r in rows:
        for i, k in enumerate(keys):
            acc[i] += float(r.get(k, 0) or 0)
    n = len(rows)
    return [x / n for x in acc]


def cosine_sim(a: Iterable[float], b: Iterable[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


def skewness(vals: list[float]) -> float:
    if len(vals) < 3:
        return 0.0
    m = statistics.mean(vals)
    m2 = sum((x - m) ** 2 for x in vals) / len(vals)
    m3 = sum((x - m) ** 3 for x in vals) / len(vals)
    if m2 < 1e-12:
        return 0.0
    return m3 / (m2**1.5)


def pooled_sd(a: list[float], b: list[float]) -> float:
    if len(a) < 2 and len(b) < 2:
        return 0.0
    va = statistics.variance(a) if len(a) > 1 else 0.0
    vb = statistics.variance(b) if len(b) > 1 else 0.0
    na, nb = len(a), len(b)
    if na + nb < 4:
        return 0.0
    return math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2 + 1e-9))


def cohens_d(a: list[float], b: list[float]) -> float:
    sd = pooled_sd(a, b)
    if sd < 1e-9:
        return 0.0
    return (statistics.mean(a) - statistics.mean(b)) / sd


def roc_auc_mannwhitney(scores: list[float], labels: list[int]) -> float:
    pos = [s for s, lb in zip(scores, labels) if lb == 1]
    neg = [s for s, lb in zip(scores, labels) if lb == 0]
    if not pos or not neg:
        return 0.5
    c = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                c += 1.0
            elif p == n:
                c += 0.5
    return c / (len(pos) * len(neg))


def roc_youden(scores: list[float], labels: list[int]) -> tuple[float, float, float, float, float]:
    """Returns auc, optimal_threshold, sens, spec, j at optimal. labels 1=positive."""
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5, CURRENT_DECISION_T, 0.0, 0.0, 0.0
    auc = roc_auc_mannwhitney(scores, labels)
    best_t, best_j, best_sens, best_spec = CURRENT_DECISION_T, -1.0, 0.0, 0.0
    uniq = sorted(set(scores))
    for t in uniq:
        tp = fp = tn = fn = 0
        for sc, lb in zip(scores, labels):
            pred = 1 if sc >= t else 0
            if pred == 1 and lb == 1:
                tp += 1
            elif pred == 1 and lb == 0:
                fp += 1
            elif pred == 0 and lb == 0:
                tn += 1
            else:
                fn += 1
        sens = tp / (tp + fn) if (tp + fn) else 0.0
        spec = tn / (tn + fp) if (tn + fp) else 0.0
        j = sens + spec - 1.0
        if j > best_j:
            best_j, best_t, best_sens, best_spec = j, t, sens, spec
    return auc, best_t, best_sens, best_spec, best_j


def beta_hdi_equal_tailed(successes: int, trials: int, alpha: float = 0.10) -> tuple[float, float]:
    """90% equal-tailed CI for Beta(s+1, f+1); normal approx if trials huge."""
    a, b = successes + 1, (trials - successes) + 1
    mean = a / (a + b)
    var = (a * b) / (((a + b) ** 2) * (a + b + 1))
    if var <= 0:
        return mean, mean
    z = 1.6448536269514722  # 90% two-sided -> 5% tail
    lo = max(0.0, mean - z * math.sqrt(var))
    hi = min(1.0, mean + z * math.sqrt(var))
    return lo, hi


def mde_cohens_d(n_per_group: int) -> float:
    if n_per_group < 2:
        return float("nan")
    return (Z_A + Z_B) * math.sqrt(2.0 / n_per_group)


def run_vibe(diff_path: Path) -> Optional[dict]:
    try:
        r = subprocess.run(
            [sys.executable, str(VIBE_CHECK), "--diff", str(diff_path), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(SCRIPT_DIR),
        )
        if r.returncode != 0:
            return None
        return json.loads(r.stdout)
    except Exception:
        return None


def extract_signals(vj: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["overall_ai_prob"] = float(vj.get("overall_ai_probability", 0.5))
    ss = vj.get("signal_summary") or {}
    for short, internal in zip(SIGNAL_SHORT, SIGNAL_INTERNAL):
        block = ss.get(internal) or {}
        out[short] = float(block.get("avg_score", 0.0))
    langs = set()
    for fa in vj.get("file_analyses") or []:
        langs.add(str(fa.get("language") or "unknown"))
    out["_languages"] = sorted(langs)
    return out


def signals_row(pr: int, label_class: str, sig: dict) -> dict:
    row = {
        "pr_number": pr,
        "label_class": label_class,
        "overall_ai_prob": sig["overall_ai_prob"],
    }
    for k in SIGNAL_SHORT:
        row[k] = sig[k]
    return row


def write_tsv(path: Path, headers: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def phase1(repo: str, budget: Budget, out: Path) -> tuple[list[dict], dict[str, str], set[int]]:
    """Returns labeled_pr rows, label_name -> classification bucket, set of matched label names."""
    code, raw = run_gh(budget, "1", repo, ["label", "list", "--limit", "200", "--json", "name,description"])
    if code != 0:
        return [], {}, set()
    labels = json.loads(raw) if raw.strip() else []
    label_map_rows: list[dict] = []
    matched_names: set[str] = set()
    for lb in labels:
        name = lb["name"]
        bucket, lc = classify_label(name)
        if bucket == "ignore":
            continue
        matched_names.add(name)
        label_map_rows.append({"label_name": name, "classification": lc, "count": ""})

    pr_by_num: dict[int, dict] = {}
    for row in label_map_rows:
        name = row["label_name"]
        code, pr_raw = run_gh(
            budget,
            "1",
            repo,
            [
                "pr",
                "list",
                "--label",
                name,
                "--state",
                "merged",
                "--limit",
                "100",
                "--json",
                "number,title,author,createdAt,mergedAt,additions,deletions,changedFiles,commits,labels",
            ],
        )
        if code == -1:
            row["count"] = "0"
            break
        if code != 0:
            row["count"] = "0"
            continue
        prs = json.loads(pr_raw) if pr_raw.strip() else []
        row["count"] = str(len(prs))
        _, lc = classify_label(name)
        for p in prs:
            num = int(p["number"])
            auth = (p.get("author") or {}).get("login") or ""
            commits = p.get("commits")
            if isinstance(commits, dict):
                cc = int(commits.get("totalCount", 0))
            elif isinstance(commits, list):
                cc = len(commits)
            else:
                cc = int(commits or 0)
            prev = pr_by_num.get(num)
            rec = {
                "pr_number": num,
                "label_class": lc,
                "title": (p.get("title") or "").replace("\t", " "),
                "author": auth,
                "created": p.get("createdAt") or "",
                "merged": p.get("mergedAt") or "",
                "additions": p.get("additions") or 0,
                "deletions": p.get("deletions") or 0,
                "changed_files": p.get("changedFiles") or 0,
                "commit_count": cc,
            }
            if prev is None or label_priority(lc) < label_priority(prev["label_class"]):
                pr_by_num[num] = rec

    labeled = sorted(pr_by_num.values(), key=lambda x: x["pr_number"])
    write_tsv(
        out / "label_map.tsv",
        ["label_name", "classification", "count"],
        label_map_rows,
    )
    write_tsv(
        out / "labeled_prs.tsv",
        [
            "pr_number",
            "label_class",
            "title",
            "author",
            "created",
            "merged",
            "additions",
            "deletions",
            "changed_files",
            "commit_count",
        ],
        labeled,
    )
    return labeled, {r["label_name"]: r["classification"] for r in label_map_rows}, matched_names


def fetch_pr_detail(
    repo: str, budget: Budget, phase: str, pr: int, diff_dir: Path
) -> tuple[Optional[Path], str]:
    if not budget.pr_detail_ok():
        return None, ""
    diff_path = diff_dir / f"pr_{pr}.diff"
    code, diff_text = run_gh(budget, phase, repo, ["pr", "diff", str(pr), "--color=never"])
    if code != 0 or not diff_text.strip():
        return None, ""
    diff_path.write_text(diff_text)
    budget.pr_detail += 1

    code, raw = run_gh(budget, phase, repo, ["pr", "view", str(pr), "--json", "commits"])
    commit_meta = ""
    if code == 0 and raw.strip():
        try:
            data = json.loads(raw)
            msgs = []
            for c in data.get("commits") or []:
                m = (c.get("messageHeadline") or c.get("message") or "").split("\n")[0]
                msgs.append(m.replace("\t", " "))
            commit_meta = " | ".join(msgs[:20])
        except json.JSONDecodeError:
            pass
    return diff_path, commit_meta


def analyze_prs(
    repo: str,
    budget: Budget,
    phase: str,
    pr_rows: list[dict],
    diff_dir: Path,
    max_prs: int,
) -> list[dict]:
    out: list[dict] = []
    for row in pr_rows[:max_prs]:
        pr = int(row["pr_number"])
        lc = row["label_class"]
        dp, _cm = fetch_pr_detail(repo, budget, phase, pr, diff_dir)
        if dp is None:
            continue
        vj = run_vibe(dp)
        if not vj:
            continue
        sig = extract_signals(vj)
        r = signals_row(pr, lc, sig)
        r["_languages"] = sig["_languages"]
        out.append(r)
    return out


def size_bucket(adds: int) -> str:
    if adds < 50:
        return "s0"
    if adds < 200:
        return "s1"
    if adds < 500:
        return "s2"
    return "s3"


def time_bucket(merged: str, ref: datetime) -> str:
    dt = parse_iso(merged)
    if not dt:
        return "u"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = (ref - dt).days
    if delta <= 90:
        return "t0"
    if delta <= 180:
        return "t1"
    if delta <= 365:
        return "t2"
    return "t3"


def stratified_unlabeled(
    pr_json: list[dict],
    matched_label_names: set[str],
    ref: datetime,
    k: int,
) -> list[dict]:
    """Pick k PRs stratified by size (additions) and recency buckets."""
    cands = []
    for p in pr_json:
        labels = [x.get("name", "") for x in (p.get("labels") or [])]
        if any(ln in matched_label_names for ln in labels):
            continue
        cands.append(p)
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in cands:
        adds = int(p.get("additions") or 0)
        sb = size_bucket(adds)
        tb = time_bucket(p.get("mergedAt") or "", ref)
        if tb == "u":
            tb = "t3"
        cells[(sb, tb)].append(p)
    target_per_size = max(1, k // 4)
    picked: list[dict] = []
    seen: set[int] = set()
    for sb in ("s0", "s1", "s2", "s3"):
        pool: list[dict] = []
        for tb in ("t0", "t1", "t2", "t3"):
            pool.extend(cells.get((sb, tb), []))
        pool.sort(key=lambda x: int(x["number"]), reverse=True)
        for p in pool:
            if len([x for x in picked if size_bucket(int(x.get("additions") or 0)) == sb]) >= target_per_size:
                break
            n = int(p["number"])
            if n in seen:
                continue
            seen.add(n)
            picked.append(p)
            if len(picked) >= k:
                return picked[:k]
    for p in sorted(cands, key=lambda x: int(x["number"]), reverse=True):
        n = int(p["number"])
        if n not in seen:
            seen.add(n)
            picked.append(p)
        if len(picked) >= k:
            break
    return picked[:k]


def phase4(
    signals_rows: list[dict],
    expanded_rows: list[dict],
    out: Path,
    low_confidence: bool,
) -> dict:
    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in signals_rows:
        by_class[r["label_class"]].append(r)

    desc_headers = [
        "signal",
        "label_class",
        "N",
        "mean",
        "median",
        "std",
        "iqr_low",
        "iqr_high",
        "skewness",
        "cohens_d_vs_human",
    ]
    desc_rows: list[dict] = []
    vibe = by_class.get("vibe-coded", [])
    human = by_class.get("human-written", [])
    skip_d = len(vibe) < 5 or len(human) < 5

    for lc, rows in sorted(by_class.items()):
        if len(rows) < 5:
            continue
        for short in SIGNAL_SHORT:
            vals = [float(r[short]) for r in rows]
            vals_s = sorted(vals)
            n = len(vals)
            q1 = vals_s[n // 4]
            q3 = vals_s[(3 * n) // 4]
            dvh = ""
            if not skip_d:
                va = [float(r[short]) for r in vibe]
                vb = [float(r[short]) for r in human]
                if va and vb:
                    dvh = f"{cohens_d(va, vb):.4f}"
            desc_rows.append(
                {
                    "signal": short,
                    "label_class": lc,
                    "N": str(n),
                    "mean": f"{statistics.mean(vals):.4f}",
                    "median": f"{statistics.median(vals):.4f}",
                    "std": f"{statistics.pstdev(vals):.4f}" if n > 1 else "0",
                    "iqr_low": f"{q1:.4f}",
                    "iqr_high": f"{q3:.4f}",
                    "skewness": f"{skewness(vals):.4f}",
                    "cohens_d_vs_human": dvh,
                }
            )
    write_tsv(out / "descriptive_stats.tsv", desc_headers, desc_rows)

    labels_v = [1 if r["label_class"] == "vibe-coded" else 0 for r in signals_rows]
    disc_rows: list[dict] = []
    sig_auc: list[str] = []
    thr_cmp: list[dict] = []
    for short in SIGNAL_SHORT + ["overall_ai_prob"]:
        sc = [float(r[short if short != "overall_ai_prob" else "overall_ai_prob"]) for r in signals_rows]
        auc, opt_t, sens, spec, j = roc_youden(sc, labels_v)
        disc_rows.append(
            {
                "signal": short,
                "roc_auc": f"{auc:.4f}",
                "optimal_threshold": f"{opt_t:.4f}",
                "sensitivity_at_opt": f"{sens:.4f}",
                "specificity_at_opt": f"{spec:.4f}",
                "youden_j": f"{j:.4f}",
            }
        )
        if short in SIGNAL_SHORT and auc > 0.6:
            sig_auc.append(short)
        diff = opt_t - CURRENT_DECISION_T
        rec = "no"
        if abs(diff) > 0.1:
            rec = "recalibrate"
        thr_cmp.append(
            {
                "signal": short,
                "current_threshold": f"{CURRENT_DECISION_T:.2f}",
                "optimal_threshold": f"{opt_t:.4f}",
                "difference": f"{diff:.4f}",
                "recommendation": rec,
            }
        )
    write_tsv(
        out / "discrimination.tsv",
        ["signal", "roc_auc", "optimal_threshold", "sensitivity_at_opt", "specificity_at_opt", "youden_j"],
        disc_rows,
    )
    write_tsv(
        out / "threshold_comparison.tsv",
        ["signal", "current_threshold", "optimal_threshold", "difference", "recommendation"],
        thr_cmp,
    )

    bay_rows: list[dict] = []
    for short in SIGNAL_SHORT + ["overall_ai_prob"]:
        sc = [float(r[short if short != "overall_ai_prob" else "overall_ai_prob"]) for r in signals_rows]
        _, opt_t, _, _, _ = roc_youden(sc, labels_v)
        tp = fp = tn = fn = 0
        for r, lb in zip(sc, labels_v):
            pred = 1 if r >= opt_t else 0
            if pred == 1 and lb == 1:
                tp += 1
            elif pred == 1 and lb == 0:
                fp += 1
            elif pred == 0 and lb == 0:
                tn += 1
            else:
                fn += 1
        if tp + fn > 0:
            sens_lo, sens_hi = beta_hdi_equal_tailed(tp, tp + fn)
        else:
            sens_lo, sens_hi = 0.0, 1.0
        if tn + fp > 0:
            spec_lo, spec_hi = beta_hdi_equal_tailed(tn, tn + fp)
        else:
            spec_lo, spec_hi = 0.0, 1.0
        bay_rows.append(
            {
                "signal": short,
                "threshold": f"{opt_t:.4f}",
                "sensitivity_90ci_low": f"{sens_lo:.4f}",
                "sensitivity_90ci_high": f"{sens_hi:.4f}",
                "specificity_90ci_low": f"{spec_lo:.4f}",
                "specificity_90ci_high": f"{spec_hi:.4f}",
            }
        )
    write_tsv(
        out / "bayesian_ci.tsv",
        [
            "signal",
            "threshold",
            "sensitivity_90ci_low",
            "sensitivity_90ci_high",
            "specificity_90ci_low",
            "specificity_90ci_high",
        ],
        bay_rows,
    )

    n_vibe = sum(1 for r in signals_rows if r["label_class"] == "vibe-coded")
    n_human = sum(1 for r in signals_rows if r["label_class"] == "human-written")
    n_pseudo_v = sum(1 for r in expanded_rows if r.get("pseudo_label") == "likely-vibe-coded")
    n_pseudo_h = sum(1 for r in expanded_rows if r.get("pseudo_label") == "likely-human")
    n_amb = sum(1 for r in expanded_rows if r.get("pseudo_label") == "ambiguous")
    langs: set[str] = set()
    for r in signals_rows:
        for x in r.get("_languages") or []:
            langs.add(x)
    authors = len({r.get("author", "") for r in expanded_rows if r.get("author")})
    size_cov = len({size_bucket(int(r.get("additions", 0) or 0)) for r in expanded_rows})
    time_cov = len(
        {
            time_bucket(r.get("merged", "") or "", datetime.now(timezone.utc))
            for r in expanded_rows
            if r.get("merged")
        }
    )

    warnings: list[str] = []
    if low_confidence:
        warnings.append("LABELED_LT_10:LOW_CONFIDENCE")
    for lc, rows in by_class.items():
        if len(rows) < 5:
            warnings.append(f"UNDERSAMPLED:{lc}:N={len(rows)}")
    for sb in ("s0", "s1", "s2", "s3"):
        if sum(1 for r in expanded_rows if size_bucket(int(r.get("additions", 0) or 0)) == sb) < 10:
            warnings.append(f"STRATUM_SIZE_LT_10:{sb}")

    nmin = min(n_vibe, n_human) if n_vibe and n_human else max(n_vibe, n_human, 1)
    mde = mde_cohens_d(nmin)

    rec_thr = {r["signal"]: r["optimal_threshold"] for r in thr_cmp if r["recommendation"] == "recalibrate"}

    summary = {
        "total_prs_analyzed": len(expanded_rows),
        "labeled_vibe_coded": n_vibe,
        "labeled_human": n_human,
        "pseudo_labeled_vibe": n_pseudo_v,
        "pseudo_labeled_human": n_pseudo_h,
        "ambiguous": n_amb,
        "languages_observed": sorted(langs),
        "signals_with_significant_discrimination": sig_auc,
        "recommended_threshold_changes": rec_thr,
        "dataset_quality_warnings": warnings
        + ([f"MDE_COHEN_D_80POW≈{mde:.3f}"] if not math.isnan(mde) else []),
        "size_buckets_covered": size_cov,
        "time_buckets_covered": time_cov,
        "unique_authors_sample": authors,
        "api_calls_used": 0,
    }
    (out / "dataset_summary.json").write_text(json.dumps(summary, separators=(",", ":")))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/repo for gh -R")
    ap.add_argument("--out-dir", default="", help="output directory (default: outputs/calibration/<ts>)")
    args = ap.parse_args()
    repo = args.repo.strip()
    ref_time = datetime.now(timezone.utc)
    if args.out_dir:
        out = Path(args.out_dir)
    else:
        ts = ref_time.strftime("%Y%m%d-%H%M%SZ")
        out = REPO_ROOT / "outputs" / f"calibration_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    diff_dir = out / "diffs"
    diff_dir.mkdir(exist_ok=True)

    budget = Budget()

    labeled, _lm, matched_names = phase1(repo, budget, out)
    low_conf = len(labeled) < 10

    labeled_sorted = sorted(
        labeled,
        key=lambda r: (
            0 if r["label_class"] == "vibe-coded" else 1,
            -int(r.get("additions") or 0),
        ),
    )
    sig_rows = analyze_prs(repo, budget, "2", labeled_sorted, diff_dir, P2_MAX_PRS)
    for r in sig_rows:
        r["author"] = next((x["author"] for x in labeled if int(x["pr_number"]) == int(r["pr_number"])), "")
        r["merged"] = next((x["merged"] for x in labeled if int(x["pr_number"]) == int(r["pr_number"])), "")
        r["additions"] = next((x["additions"] for x in labeled if int(x["pr_number"]) == int(r["pr_number"])), 0)

    base_headers = [
        "pr_number",
        "label_class",
        "overall_ai_prob",
        *SIGNAL_SHORT,
    ]
    write_tsv(out / "signals.tsv", base_headers, [{k: r[k] for k in base_headers} for r in sig_rows])

    code, raw = run_gh(
        budget,
        "3",
        repo,
        ["pr", "list", "--state", "merged", "--limit", str(P3_LIST_LIMIT), "--json", "number,title,additions,deletions,createdAt,labels,mergedAt,author"],
    )
    pool = json.loads(raw) if code == 0 and raw.strip() else []

    keys = SIGNAL_SHORT
    vibe_rows = [r for r in sig_rows if r["label_class"] == "vibe-coded"]
    hum_rows = [r for r in sig_rows if r["label_class"] == "human-written"]
    if vibe_rows:
        v_proto = mean_vec(vibe_rows, keys)
    else:
        tail = sorted(sig_rows, key=lambda r: -r["overall_ai_prob"])[: max(1, len(sig_rows) // 4)]
        v_proto = mean_vec(tail, keys)
    if hum_rows:
        h_proto = mean_vec(hum_rows, keys)
    else:
        head = sorted(sig_rows, key=lambda r: r["overall_ai_prob"])[: max(1, len(sig_rows) // 4)]
        h_proto = mean_vec(head, keys)

    sampled = stratified_unlabeled(pool, matched_names, ref_time, P3_SAMPLE)
    extra_rows: list[dict] = []
    for p in sampled:
        if budget.total >= API_TOTAL or not budget.pr_detail_ok():
            break
        pr = int(p["number"])
        if any(int(r["pr_number"]) == pr for r in sig_rows):
            continue
        row = {
            "pr_number": pr,
            "label_class": "unlabeled",
            "title": (p.get("title") or "").replace("\t", " "),
            "author": (p.get("author") or {}).get("login") or "",
            "merged": p.get("mergedAt") or "",
            "additions": p.get("additions") or 0,
        }
        dp, _ = fetch_pr_detail(repo, budget, "3", pr, diff_dir)
        if dp is None:
            continue
        vj = run_vibe(dp)
        if not vj:
            continue
        sig = extract_signals(vj)
        vec = [sig[k] for k in keys]
        sv = cosine_sim(vec, v_proto)
        sh = cosine_sim(vec, h_proto)
        ratio = (sv / sh) if sh > 1e-9 else 99.0
        if ratio > 2.0:
            pl = "likely-vibe-coded"
        elif ratio < 0.5:
            pl = "likely-human"
        else:
            pl = "ambiguous"
        extra_rows.append(
            {
                **signals_row(pr, "unlabeled", sig),
                "pseudo_label": pl,
                "similarity_ratio": f"{ratio:.4f}",
                "author": row["author"],
                "merged": row["merged"],
                "additions": row["additions"],
            }
        )

    exp_headers = base_headers + ["pseudo_label", "similarity_ratio", "author", "merged", "additions"]
    expanded: list[dict] = []
    for r in sig_rows:
        expanded.append(
            {
                **{k: r[k] for k in base_headers},
                "pseudo_label": r["label_class"],
                "similarity_ratio": "",
                "author": r.get("author", ""),
                "merged": r.get("merged", ""),
                "additions": r.get("additions", 0),
            }
        )
    expanded.extend(extra_rows)
    write_tsv(out / "expanded_dataset.tsv", exp_headers, expanded)

    summary = phase4(sig_rows, expanded, out, low_conf)
    summary["api_calls_used"] = budget.total
    summary["gh_errors"] = budget.errors[:50]
    (out / "dataset_summary.json").write_text(json.dumps(summary, separators=(",", ":")))

    with (out / "RUN_SUMMARY.txt").open("w") as f:
        f.write(
            f"out_dir={out}\nlabeled_prs={len(labeled)} signals_n={len(sig_rows)} "
            f"expanded_n={len(expanded)} api_calls={budget.total} pr_detail={budget.pr_detail}\n"
        )
        if low_conf:
            f.write("WARN: labeled PRs < 10; LOW confidence for calibration.\n")
        for e in budget.errors[:20]:
            f.write(f"ERR: {e}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
