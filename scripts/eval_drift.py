#!/usr/bin/env python3
"""
Replay drift decisions on historical telemetry under a threshold grid.

Inputs:
  --jsonl   vibe_check_telemetry.jsonl  (rows with "signals", "timestamp")
  --labels  CSV with columns: week_bucket,is_drift  (1 = real drift week, 0 = stable)
  --buckets week  (default) | day
  --metrics psi,sinkhorn,mean_shift  (default all)
  --out-dir ./eval_drift_run_<ts>/

Outputs:
  grid_results.tsv  (bucket,metric,threshold,status,label,correct)
  metric_roc.tsv    (metric,threshold,precision,recall,mcc,n_buckets)
  summary.json      (best (metric, threshold) by F1 and by precision@recall>=0.5)

Stdlib only. Offline. Does not mutate vibe_check state.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj.get("signals"), dict) and obj.get("timestamp"):
                rows.append(obj)
    return rows


def bucketize(ts: str, granularity: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    if granularity == "day":
        return dt.strftime("%Y-%m-%d")
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def histogram_01(vals: Iterable[float], n_bins: int = 20) -> list[float]:
    h = [0.0] * n_bins
    n = 0
    for v in vals:
        n += 1
        v = max(0.0, min(1.0, float(v)))
        h[min(n_bins - 1, int(v * n_bins))] += 1.0
    s = sum(h) or 1.0
    return [x / s for x in h]


def psi(expected: list[float], actual: list[float], epsilon: float = 1e-4) -> float:
    e = histogram_01(expected)
    a = histogram_01(actual)
    score = 0.0
    for ei, ai in zip(e, a):
        ei = max(ei, epsilon)
        ai = max(ai, epsilon)
        score += (ai - ei) * math.log(ai / ei)
    return score


def mean_shift(expected: list[float], actual: list[float]) -> float:
    if len(expected) < 3 or len(actual) < 3:
        return 0.0
    mu_e = sum(expected) / len(expected)
    var_e = sum((v - mu_e) ** 2 for v in expected) / len(expected)
    std_e = math.sqrt(var_e) or 1e-4
    mu_a = sum(actual) / len(actual)
    return abs(mu_a - mu_e) / std_e


def sinkhorn_1d(expected: list[float], actual: list[float], reg: float = 0.06, iters: int = 60) -> float:
    e = histogram_01(expected)
    a = histogram_01(actual)
    n = len(e)
    c = [[abs(i - j) / float(n - 1) for j in range(n)] for i in range(n)]
    k = [[math.exp(-c[i][j] / reg) for j in range(n)] for i in range(n)]
    u = [1.0 / n] * n
    v = [1.0 / n] * n
    for _ in range(iters):
        u = [e[i] / (sum(k[i][j] * v[j] for j in range(n)) or 1e-12) for i in range(n)]
        v = [a[j] / (sum(k[i][j] * u[i] for i in range(n)) or 1e-12) for j in range(n)]
    cost = 0.0
    for i in range(n):
        for j in range(n):
            cost += u[i] * k[i][j] * v[j] * c[i][j]
    return cost


def mcc(tp: int, fp: int, tn: int, fn: int) -> float:
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / den if den > 0 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", type=Path, required=True)
    ap.add_argument("--labels", type=Path, required=True, help="CSV: week_bucket,is_drift")
    ap.add_argument("--buckets", choices=["day", "week"], default="week")
    ap.add_argument("--metrics", default="psi,sinkhorn,mean_shift")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--grid", default=None, help="Comma-separated thresholds (overrides metric defaults)")
    args = ap.parse_args()

    out = args.out_dir or (args.jsonl.parent / f"eval_drift_run_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    out.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(args.jsonl)
    if len(rows) < 30:
        print(f"Need >= 30 telemetry rows, got {len(rows)}", file=sys.stderr)
        sys.exit(1)

    labels: dict[str, int] = {}
    with args.labels.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            labels[r["week_bucket"].strip()] = 1 if str(r.get("is_drift", "")).strip() in ("1", "true", "TRUE") else 0
    if not labels:
        print("No labels loaded", file=sys.stderr)
        sys.exit(1)

    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_bucket[bucketize(r["timestamp"], args.buckets)].append(r)

    baseline_rows = rows[: max(30, int(0.4 * len(rows)))]

    signal_keys = sorted({k for r in rows for k in r["signals"].keys()})

    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]
    default_grids = {
        "psi": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50],
        "sinkhorn": [0.06, 0.10, 0.14, 0.18, 0.22, 0.28, 0.34],
        "mean_shift": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
    }
    if args.grid:
        override_grid = [float(x) for x in args.grid.split(",") if x.strip()]
        default_grids = {m: override_grid for m in metrics}

    grid_rows = []
    metric_fns = {"psi": psi, "sinkhorn": sinkhorn_1d, "mean_shift": mean_shift}
    per_metric_threshold_stats: dict[tuple, dict] = {}

    for bucket, bucket_rows in sorted(by_bucket.items()):
        if bucket not in labels:
            continue
        label = labels[bucket]
        for metric in metrics:
            fn = metric_fns[metric]
            per_signal_scores = []
            for sig in signal_keys:
                b = [r["signals"].get(sig, 0.0) for r in baseline_rows]
                a = [r["signals"].get(sig, 0.0) for r in bucket_rows]
                if len(a) < 3:
                    continue
                per_signal_scores.append(fn(b, a))
            global_score = sum(per_signal_scores) / len(per_signal_scores) if per_signal_scores else 0.0
            for threshold in default_grids[metric]:
                status = "TRIGGER" if global_score > threshold else "CONTINUE"
                correct = int((status == "TRIGGER") == bool(label))
                grid_rows.append((bucket, metric, threshold, round(global_score, 5), status, label, correct))
                key = (metric, threshold)
                stats = per_metric_threshold_stats.setdefault(key, {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "n": 0})
                stats["n"] += 1
                if status == "TRIGGER" and label == 1:
                    stats["tp"] += 1
                elif status == "TRIGGER" and label == 0:
                    stats["fp"] += 1
                elif status == "CONTINUE" and label == 1:
                    stats["fn"] += 1
                else:
                    stats["tn"] += 1

    grid_path = out / "grid_results.tsv"
    with grid_path.open("w") as w:
        w.write("bucket\tmetric\tthreshold\tglobal\tstatus\tlabel\tcorrect\n")
        for row in grid_rows:
            w.write("\t".join(str(x) for x in row) + "\n")

    roc_rows = []
    best_by_mcc: tuple | None = None
    for (metric, threshold), s in sorted(per_metric_threshold_stats.items()):
        tp, fp, tn, fn = s["tp"], s["fp"], s["tn"], s["fn"]
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        m = mcc(tp, fp, tn, fn)
        roc_rows.append((metric, threshold, round(prec, 4), round(rec, 4), round(f1, 4), round(m, 4), s["n"]))
        if best_by_mcc is None or m > best_by_mcc[5]:
            best_by_mcc = (metric, threshold, round(prec, 4), round(rec, 4), round(f1, 4), round(m, 4), s["n"])

    with (out / "metric_roc.tsv").open("w") as w:
        w.write("metric\tthreshold\tprecision\trecall\tf1\tmcc\tn_buckets\n")
        for row in roc_rows:
            w.write("\t".join(str(x) for x in row) + "\n")

    (out / "summary.json").write_text(
        json.dumps(
            {
                "best_by_mcc": {
                    "metric": best_by_mcc[0] if best_by_mcc else None,
                    "threshold": best_by_mcc[1] if best_by_mcc else None,
                    "precision": best_by_mcc[2] if best_by_mcc else None,
                    "recall": best_by_mcc[3] if best_by_mcc else None,
                    "f1": best_by_mcc[4] if best_by_mcc else None,
                    "mcc": best_by_mcc[5] if best_by_mcc else None,
                    "n_buckets": best_by_mcc[6] if best_by_mcc else None,
                },
                "n_rows": len(rows),
                "n_labeled_buckets": sum(1 for b in by_bucket if b in labels),
            },
            indent=2,
        )
    )
    print(json.dumps({"out_dir": str(out), "rows": len(rows), "best_by_mcc": best_by_mcc}, default=str))


if __name__ == "__main__":
    main()
