"""error_taxonomy_v2 — classify candidate-SQL outcomes for verifier_ranker.

Used by verifier_ranker_v2 to turn a candidate's (parse, safe, exec, rows, gold-free
checks) into a small set of categorical buckets that downstream scoring can
weigh and that consolidation can aggregate.

Categories are intentionally compact (one per row) so the JSONL stays small.
"""
from __future__ import annotations

# Final per-row outcome (what the executor / verifier saw)
SUCCESS = 'success'
RESULT_MISMATCH = 'result_mismatch'
EMPTY_RESULT = 'empty_result'                  # exec ok but rows == []
NULL_DOMINANT = 'null_dominant'                # exec ok but mostly null
PARSE_ERROR = 'parse_error'
UNSAFE_BLOCKED = 'unsafe_blocked'
OP_NO_SUCH_TABLE = 'op_no_such_table'
OP_NO_SUCH_COLUMN = 'op_no_such_column'
OP_AMBIGUOUS_COL = 'op_ambiguous_column'
OP_SYNTAX = 'op_syntax_error'
OP_OTHER = 'op_other'
RUNTIME_TYPE = 'runtime_type_error'
RUNTIME_TIMEOUT = 'runtime_timeout'
GOLD_MISSING = 'gold_missing'
PIPELINE_EXCEPTION = 'pipeline_exception'
NO_EVAL_ENGINE = 'no_execution_engine'

ALL_CATEGORIES = (
    SUCCESS, RESULT_MISMATCH, EMPTY_RESULT, NULL_DOMINANT,
    PARSE_ERROR, UNSAFE_BLOCKED,
    OP_NO_SUCH_TABLE, OP_NO_SUCH_COLUMN, OP_AMBIGUOUS_COL,
    OP_SYNTAX, OP_OTHER,
    RUNTIME_TYPE, RUNTIME_TIMEOUT,
    GOLD_MISSING, PIPELINE_EXCEPTION, NO_EVAL_ENGINE,
)


def classify_outcome(*,
                      execution_match: bool | None,
                      executable: bool | None,
                      safe_select: bool,
                      error_type: str,
                      error_message: str,
                      rows: list | None = None) -> str:
    et = (error_type or '').strip()
    em = (error_message or '').strip()
    if execution_match: return SUCCESS
    if not safe_select and (et.startswith('unsafe') or et.startswith('regex_')):
        return UNSAFE_BLOCKED
    if et.startswith('parse_error'): return PARSE_ERROR
    if et == 'no_gold': return GOLD_MISSING
    if et == 'no_execution_engine': return NO_EVAL_ENGINE
    if et.startswith('pipeline_exception'): return PIPELINE_EXCEPTION
    if et == 'timeout': return RUNTIME_TIMEOUT
    if et == 'TypeError': return RUNTIME_TYPE
    if et == 'OperationalError':
        l = em.lower()
        if 'no such table' in l: return OP_NO_SUCH_TABLE
        if 'no such column' in l: return OP_NO_SUCH_COLUMN
        if 'syntax' in l: return OP_SYNTAX
        if 'ambiguous' in l: return OP_AMBIGUOUS_COL
        return OP_OTHER
    if et == 'result_mismatch':
        if isinstance(rows, list):
            if len(rows) == 0: return EMPTY_RESULT
        return RESULT_MISMATCH
    if et == '' and execution_match is False:
        return RESULT_MISMATCH
    return OP_OTHER


# Pure verifier-side checks (no gold). Used inside verifier_ranker_v2 to score
# a candidate without leaking gold information.

def quick_health(*, executable: bool | None, safe_select: bool, rows: list | None) -> dict:
    """Three-component quick health: parses_safe (1 if both safe and exec).
    rows_present (1 if rows is a non-empty list)."""
    parses_safe = bool(safe_select)
    runs = bool(executable)
    rows_present = bool(rows) and len(rows) > 0
    rows_count = (len(rows) if isinstance(rows, list) else 0)
    return {
        'parses_safe': int(parses_safe),
        'runs': int(runs),
        'rows_present': int(rows_present),
        'rows_count': rows_count,
    }
