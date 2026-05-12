"""Statistics layer for the master matrix.

Pure-Python (no scipy required). Produces:
- Wilson CI for a binomial proportion (EX rate).
- Bootstrap CI for a delta in EX between two paired runs.
- McNemar paired off-diagonal counts (n01, n10) and exact two-sided p (binomial).
- Latency p50/p95 from per-item logs.

Designed to operate over our existing predictions JSONL files.
"""
from __future__ import annotations
import math
import random
from pathlib import Path
import json
from typing import Iterable


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (default 95% CI)."""
    if n == 0: return (0.0, 1.0)
    p = successes / n
    denom = 1 + z*z/n
    centre = (p + z*z/(2*n)) / denom
    half = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_delta_ci(matches_a: list[int], matches_b: list[int],
                       n_boot: int = 2000, alpha: float = 0.05,
                       seed: int = 0) -> tuple[float, float, float]:
    """Paired bootstrap CI for delta = mean(b) - mean(a). matches_*: 0/1 lists.
    Returns (delta_point, ci_low, ci_high)."""
    assert len(matches_a) == len(matches_b)
    n = len(matches_a)
    if n == 0: return (0.0, 0.0, 0.0)
    delta_point = sum(matches_b)/n - sum(matches_a)/n
    rng = random.Random(seed)
    deltas = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        a = sum(matches_a[i] for i in idx) / n
        b = sum(matches_b[i] for i in idx) / n
        deltas.append(b - a)
    deltas.sort()
    lo = deltas[int(n_boot * alpha/2)]
    hi = deltas[int(n_boot * (1 - alpha/2)) - 1]
    return (delta_point, lo, hi)


def _binom_two_sided_p(n01: int, n10: int) -> float:
    """Exact two-sided binomial p for McNemar (under H0: p=0.5).
    Conditional on n01+n10."""
    n = n01 + n10
    if n == 0: return 1.0
    k = min(n01, n10)
    # P(X <= k) under Bin(n, 0.5), times 2
    log_half_n = -n * math.log(2)
    log_choose = lambda nn, kk: (math.lgamma(nn+1) - math.lgamma(kk+1) - math.lgamma(nn-kk+1))
    s = 0.0
    for j in range(k+1):
        s += math.exp(log_choose(n, j) + log_half_n)
    return min(1.0, 2 * s)


def mcnemar_paired(matches_a: list[int], matches_b: list[int]) -> dict:
    """McNemar paired counts. n01: a wrong, b right; n10: a right, b wrong.
    Returns dict with n01, n10, p_value (two-sided exact binomial)."""
    n01 = sum(1 for a, b in zip(matches_a, matches_b) if not a and b)
    n10 = sum(1 for a, b in zip(matches_a, matches_b) if a and not b)
    return {"n01": n01, "n10": n10, "p_value": _binom_two_sided_p(n01, n10)}


def percentile(values: list[float], p: float) -> float:
    """Simple linear-interp percentile p in [0, 100]."""
    if not values: return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo = int(math.floor(k)); hi = int(math.ceil(k))
    if lo == hi: return s[lo]
    return s[lo] * (hi - k) + s[hi] * (k - lo)


def load_matches_from_jsonl(p: str | Path) -> list[int]:
    out = []
    for line in open(p, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try:
            obj = json.loads(line)
            out.append(1 if obj.get("execution_match") else 0)
        except Exception:
            pass
    return out


def summarize_run(prefix: str, predictions_dir: Path) -> dict:
    """Compute Wilson CI for one run from its predictions jsonl."""
    p = predictions_dir / f"{prefix}_predictions.jsonl"
    matches = load_matches_from_jsonl(p) if p.exists() else []
    n = len(matches); succ = sum(matches)
    ex = succ / n if n else 0.0
    lo, hi = wilson_ci(succ, n)
    return {
        "prefix": prefix, "n": n, "ex": ex,
        "wilson_ci_low": lo, "wilson_ci_high": hi, "successes": succ,
    }


def paired_compare(prefix_a: str, prefix_b: str, predictions_dir: Path) -> dict:
    """Bootstrap CI for delta + McNemar counts. Items are paired by idx; we
    use the shortest list to keep the lengths equal."""
    pa = predictions_dir / f"{prefix_a}_predictions.jsonl"
    pb = predictions_dir / f"{prefix_b}_predictions.jsonl"
    if not pa.exists() or not pb.exists():
        return {"delta": None, "ci_low": None, "ci_high": None,
                "n01": None, "n10": None, "p_value": None,
                "n_paired": 0, "note": "missing one of the prediction files"}
    a = load_matches_from_jsonl(pa)
    b = load_matches_from_jsonl(pb)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    delta, lo, hi = bootstrap_delta_ci(a, b)
    mc = mcnemar_paired(a, b)
    return {"delta": delta, "ci_low": lo, "ci_high": hi,
            "n01": mc["n01"], "n10": mc["n10"], "p_value": mc["p_value"],
            "n_paired": n}
