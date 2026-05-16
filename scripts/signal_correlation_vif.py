#!/usr/bin/env python3
"""
Offline correlation + VIF for vibe_check telemetry JSONL (or TSV with signal columns).

No third-party deps. Feathers-style: read-only on telemetry; writes optional reports
next to input (or --out-dir). Does not modify vibe_check.py weights automatically.

Usage:
  python3 scripts/signal_correlation_vif.py --jsonl ./telemetry/vibe_check_telemetry.jsonl
  python3 scripts/signal_correlation_vif.py --jsonl ./t.jsonl --out-dir ./reports/vif_run1

Outputs: correlation.tsv, vif.json, summary.txt (and optional weights_suggestion.json fragment).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from statistics import mean, pstdev

# Must match keys logged in log_telemetry (vibe_check signal_summary names)
DEFAULT_SIGNAL_ORDER = [
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


def load_rows_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            sig = obj.get("signals")
            if isinstance(sig, dict) and sig:
                rows.append(sig)
    return rows


def correlation_matrix(data: list[list[float]], keys: list[str]) -> tuple[list[str], list[list[float]]]:
    """Pearson correlation over observations in rows; returns (keys, matrix)."""
    n = len(data)
    if n < 2:
        return [], []
    m = len(data[0])
    mus = [mean(data[j][i] for j in range(n)) for i in range(m)]
    sigs = []
    for i in range(m):
        col = [data[j][i] for j in range(n)]
        s = pstdev(col) if n > 1 else 0.0
        sigs.append(s if s > 1e-12 else 1e-12)
    corr = [[0.0] * m for _ in range(m)]
    for i in range(m):
        corr[i][i] = 1.0
        for j in range(i + 1, m):
            num = sum((data[k][i] - mus[i]) * (data[k][j] - mus[j]) for k in range(n))
            den = (n - 1) * sigs[i] * sigs[j]
            r = num / den if den else 0.0
            r = max(-1.0, min(1.0, r))
            corr[i][j] = corr[j][i] = r
    return keys, corr


def ols_r2_predict_column(z: list[list[float]], target_idx: int) -> float:
    """R^2 regressing standardized column target_idx on other columns (no intercept)."""
    n = len(z)
    m = len(z[0])
    cols = [i for i in range(m) if i != target_idx]
    p = len(cols)
    if p == 0 or n < p + 2:
        return 0.0
    y = [z[r][target_idx] for r in range(n)]
    sst = sum((yi - mean(y)) ** 2 for yi in y) or 1e-12
    # X^T X and X^T y
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    for r in range(n):
        row = [z[r][c] for c in cols]
        for i in range(p):
            xty[i] += row[i] * y[r]
            for j in range(p):
                xtx[i][j] += row[i] * row[j]
    try:
        inv_xtx = matrix_inverse(xtx)
    except Exception:
        return 0.0
    beta = [sum(inv_xtx[i][j] * xty[j] for j in range(p)) for i in range(p)]
    yhat = [sum(beta[i] * z[r][cols[i]] for i in range(p)) for r in range(n)]
    sse = sum((y[r] - yhat[r]) ** 2 for r in range(n))
    return max(0.0, min(1.0, 1.0 - sse / sst))


def vif_from_standardized(z: list[list[float]]) -> list[float]:
    """VIF_j = 1/(1-R^2_j) with R^2 from OLS of column j on others (small-m exact)."""
    m = len(z[0]) if z else 0
    out = []
    for j in range(m):
        r2 = ols_r2_predict_column(z, j)
        denom = max(1e-9, 1.0 - r2)
        out.append(round(min(1.0 / denom, 999.0), 4))
    return out


def standardize_rows(data: list[list[float]]) -> list[list[float]]:
    m = len(data[0])
    n = len(data)
    mus = [mean(data[j][i] for j in range(n)) for i in range(m)]
    sigs = []
    for i in range(m):
        col = [data[j][i] for j in range(n)]
        s = pstdev(col) if n > 1 else 0.0
        sigs.append(s if s > 1e-12 else 1.0)
    return [[(data[r][i] - mus[i]) / sigs[i] for i in range(m)] for r in range(n)]


def matrix_inverse(a: list[list[float]]) -> list[list[float]]:  # noqa: C901 — small p≤10 only
    """Gauss-Jordan invert square matrix a in-place copy."""
    n = len(a)
    aug = [row[:] + [0.0] * n for row in a]
    for i in range(n):
        aug[i][n + i] = 1.0
    for col in range(n):
        pivot = col
        for r in range(col + 1, n):
            if abs(aug[r][col]) > abs(aug[pivot][col]):
                pivot = r
        if abs(aug[pivot][col]) < 1e-12:
            return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        aug[col], aug[pivot] = aug[pivot], aug[col]
        div = aug[col][col]
        for j in range(2 * n):
            aug[col][j] /= div
        for r in range(n):
            if r == col:
                continue
            f = aug[r][col]
            if abs(f) < 1e-15:
                continue
            for j in range(2 * n):
                aug[r][j] -= f * aug[col][j]
    return [row[n:] for row in aug]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", type=Path, required=True, help="vibe_check_telemetry.jsonl")
    ap.add_argument("--out-dir", type=Path, default=None, help="Default: same dir as jsonl")
    ap.add_argument("--min-rows", type=int, default=30)
    args = ap.parse_args()

    out_dir = args.out_dir or args.jsonl.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    rows_dicts = load_rows_jsonl(args.jsonl)
    if len(rows_dicts) < args.min_rows:
        print(f"Need >= {args.min_rows} rows with signals; got {len(rows_dicts)}", file=sys.stderr)
        sys.exit(1)

    keys = list(rows_dicts[0].keys())
    for d in rows_dicts[1:]:
        keys = [k for k in keys if k in d]
    if not keys:
        keys = DEFAULT_SIGNAL_ORDER
    else:
        keys = [k for k in DEFAULT_SIGNAL_ORDER if k in keys] or keys

    data = [[float(r.get(k, 0)) for k in keys] for r in rows_dicts]
    _, corr = correlation_matrix(data, keys)
    z = standardize_rows(data)
    vifs = vif_from_standardized(z) if z else []

    # TSV correlation
    tsv_path = out_dir / "correlation.tsv"
    with tsv_path.open("w") as w:
        w.write("signal\t" + "\t".join(keys) + "\n")
        for i, ki in enumerate(keys):
            w.write(ki + "\t" + "\t".join(f"{corr[i][j]:.6f}" for j in range(len(keys))) + "\n")

    vif_path = out_dir / "vif.json"
    vif_obj = {"signals": keys, "vif": dict(zip(keys, vifs)) if vifs else {}, "n_rows": len(rows_dicts)}
    vif_path.write_text(json.dumps(vif_obj, indent=2))

    # Deflation suggestion: weight' = weight / vif, renorm (informational only)
    suggestion = {}
    for k, v in zip(keys, vifs):
        suggestion[k] = round(1.0 / max(v, 1.0), 6)
    ssum = sum(suggestion.values()) or 1.0
    suggestion = {k: round(v / ssum, 6) for k, v in suggestion.items()}
    (out_dir / "weights_suggestion_renorm.json").write_text(json.dumps({"weights": suggestion}, indent=2))

    summary = [
        f"n_rows={len(rows_dicts)}",
        f"signals={keys}",
        "VIF>5 suggests strong collinearity (rule-of-thumb; Liao-style diagnostics).",
        "This script does not write calibration_override.json — merge manually after review.",
    ]
    (out_dir / "summary.txt").write_text("\n".join(summary) + "\n")
    print(json.dumps({"out_dir": str(out_dir), "n": len(rows_dicts), "vif": vif_obj["vif"]}, indent=2))


if __name__ == "__main__":
    main()
