"""Lightweight NL query analysis layer (closes ТЗ 2.2.1).

Rule-based analyzer that maps a natural-language question into a structured
QueryAnalysis object. Used before planner / SQL synthesizer to provide
explicit signals (aggregation, distinct, limit, ordering, time constraints,
comparison operators).

Optionally LLM-assisted: an `enrich_with_llm(...)` hook is provided that takes
a callable `gen_fn` and asks the model to refine the predicted intent. Default
caller path (`analyze`) does NOT call the LLM, keeping this layer cheap.
"""
from __future__ import annotations
import re
from typing import Any, Callable, Optional


STOP = {"a","an","the","of","in","on","at","for","to","from","by","with","is","are","was","were",
        "what","which","who","whom","whose","how","much","show","list","find","give","me",
        "all","each","every","any","do","does","did","that","this","there","their","them","they"}

AGG_PATTERNS = {
    "count":   re.compile(r"\b(count|number\s+of|how\s+many|total\s+number)\b", re.I),
    "sum":     re.compile(r"\b(sum|total|aggregate)\b", re.I),
    "avg":     re.compile(r"\b(average|avg|mean)\b", re.I),
    "max":     re.compile(r"\b(maximum|max|highest|largest|biggest|most)\b", re.I),
    "min":     re.compile(r"\b(minimum|min|lowest|smallest|least|youngest|earliest)\b", re.I),
}

ORDER_PATTERNS = {
    "order_desc": re.compile(r"\b(top|highest|largest|most|descending|desc|biggest)\b", re.I),
    "order_asc":  re.compile(r"\b(bottom|lowest|smallest|ascending|asc|youngest|earliest|least)\b", re.I),
    "sort":       re.compile(r"\b(sort(ed)?|order(ed)?\s+by|ranked?)\b", re.I),
}

DISTINCT_PATTERN = re.compile(r"\b(distinct|unique|different|various)\b", re.I)

LIMIT_PATTERN = re.compile(r"\b(top|first|last|bottom)\s+(\d+)\b", re.I)
LIMIT_ONE_PATTERN = re.compile(r"\b(the\s+youngest|the\s+oldest|the\s+highest|the\s+lowest|the\s+biggest|the\s+smallest|the\s+most|the\s+least)\b", re.I)

TIME_PATTERNS = {
    "year_filter":   re.compile(r"\b(in|of|since|before|after)\s+(\d{4})\b", re.I),
    "date_filter":   re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    "year_keyword":  re.compile(r"\byear(s)?\b", re.I),
    "month_keyword": re.compile(r"\bmonth(s)?\b", re.I),
    "before_after":  re.compile(r"\b(before|after|since|until)\b", re.I),
}

COMP_PATTERNS = {
    ">":  re.compile(r"\b(greater\s+than|more\s+than|above|over|exceeding)\b", re.I),
    "<":  re.compile(r"\b(less\s+than|fewer\s+than|below|under|smaller\s+than)\b", re.I),
    ">=": re.compile(r"\b(at\s+least|no\s+less\s+than)\b", re.I),
    "<=": re.compile(r"\b(at\s+most|no\s+more\s+than)\b", re.I),
    "=":  re.compile(r"\b(equal\s+to|equals|is\s+equal)\b", re.I),
    "!=": re.compile(r"\b(not\s+equal|different\s+from|other\s+than)\b", re.I),
}

JOIN_HINT_PATTERN = re.compile(r"\b(for\s+each|per\s+\w+|along\s+with|with\s+their|grouped\s+by)\b", re.I)


def _tokenize(question: str) -> list[str]:
    parts = re.split(r"[\s,;.?!]+", str(question).lower())
    return [p for p in parts if p and p not in STOP and len(p) > 1]


def detect_aggregations(q: str) -> list[str]:
    return [name for name, pat in AGG_PATTERNS.items() if pat.search(q)]


def detect_ordering(q: str) -> list[str]:
    found = []
    for name, pat in ORDER_PATTERNS.items():
        if pat.search(q):
            found.append(name)
    return found


def detect_distinct(q: str) -> bool:
    return bool(DISTINCT_PATTERN.search(q))


def detect_limit(q: str) -> Optional[int]:
    m = LIMIT_PATTERN.search(q)
    if m:
        try: return int(m.group(2))
        except Exception: return None
    if LIMIT_ONE_PATTERN.search(q):
        return 1
    return None


def detect_time(q: str) -> list[dict]:
    out = []
    for kind, pat in TIME_PATTERNS.items():
        m = pat.search(q)
        if m:
            out.append({"kind": kind, "match": m.group(0)})
    return out


def detect_comparisons(q: str) -> list[str]:
    return [op for op, pat in COMP_PATTERNS.items() if pat.search(q)]


def detect_join_hint(q: str) -> bool:
    return bool(JOIN_HINT_PATTERN.search(q))


def predict_intent(signals: dict) -> tuple[str, float]:
    """Map signals to coarse intent + a heuristic confidence in [0, 1]."""
    aggs = signals.get("aggregations", [])
    distinct = signals.get("distinct", False)
    ordering = signals.get("ordering", [])
    limit = signals.get("limit", None)
    comps = signals.get("comparisons", [])
    join_hint = signals.get("join_hint", False)

    if "count" in aggs and not ordering:
        return "select_count", 0.9
    if any(a in aggs for a in ("sum","avg","max","min")) and not ordering:
        return "select_aggregate", 0.85
    if distinct:
        return "select_distinct", 0.85
    if ordering or limit is not None:
        return "select_orderby", 0.8
    if join_hint:
        return "select_groupby", 0.7
    if comps:
        return "select_filter", 0.75
    return "select_other", 0.4


def analyze(question: str) -> dict:
    """Main entry point. Pure rule-based. Returns a QueryAnalysis dict."""
    q = str(question)
    tokens = _tokenize(q)
    signals = {
        "aggregations": detect_aggregations(q),
        "distinct": detect_distinct(q),
        "ordering": detect_ordering(q),
        "limit": detect_limit(q),
        "time": detect_time(q),
        "comparisons": detect_comparisons(q),
        "join_hint": detect_join_hint(q),
    }
    intent, confidence = predict_intent(signals)
    return {
        "raw_question": q,
        "tokens": tokens,
        "signals": signals,
        "predicted_intent": intent,
        "confidence": confidence,
        "method": "rule_based_v1",
    }


def enrich_with_llm(question: str, base_analysis: dict, gen_fn: Callable[[str], str]) -> dict:
    """Optional LLM hook. Asks the model to confirm/correct intent.

    `gen_fn(prompt: str) -> raw text`. Caller is responsible for token caps.
    Returns the analysis object with `llm_intent` and `llm_notes` added; original
    `predicted_intent` is preserved (we do not silently overwrite the rule output).
    """
    prompt = (
        "Classify the intent of the following question into one of:\n"
        "select_count, select_aggregate, select_filter, select_join, select_groupby,\n"
        "select_orderby, select_distinct, select_other.\n"
        "Output JSON only: {\"intent\": <one of above>, \"notes\": <short>}.\n\n"
        f"Question: {question}\n"
        f"Rule-based suggestion: {base_analysis['predicted_intent']} ({base_analysis['confidence']}).\n"
        "JSON:"
    )
    try:
        raw = gen_fn(prompt)
        import json as _json
        m = re.search(r"\{[^{}]*\}", raw or "")
        if m:
            obj = _json.loads(m.group(0))
            return {**base_analysis, "llm_intent": obj.get("intent"), "llm_notes": obj.get("notes","")}
    except Exception as exc:
        return {**base_analysis, "llm_intent": None, "llm_notes": f"llm_failed: {type(exc).__name__}: {exc}"}
    return {**base_analysis, "llm_intent": None, "llm_notes": "no_llm_match"}


def to_prompt_prefix(analysis: dict) -> str:
    """Render an analyzed query as a prompt prefix for downstream B2/B3/B4 prompts."""
    lines = ["Query analysis:"]
    lines.append(f"- Predicted intent: {analysis['predicted_intent']} (confidence={analysis['confidence']})")
    sig = analysis["signals"]
    if sig["aggregations"]: lines.append(f"- Aggregations: {sig['aggregations']}")
    if sig["distinct"]:    lines.append(f"- Distinct: yes")
    if sig["ordering"]:    lines.append(f"- Ordering hints: {sig['ordering']}")
    if sig["limit"] is not None: lines.append(f"- Limit: {sig['limit']}")
    if sig["comparisons"]: lines.append(f"- Comparison operators: {sig['comparisons']}")
    if sig["time"]:         lines.append(f"- Time constraints: {sig['time']}")
    if sig["join_hint"]:   lines.append(f"- Join/groupby hint: yes")
    return "\n".join(lines)
