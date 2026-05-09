"""structured_plan_v18 — Qwen3-Coder structured planner.

v18.1 patches:
  - validate_plan: wildcard date-shard recognition (`<table>_YYYYMMDD`
    accepted when the pack lists a sibling shard); leaf/root struct
    path normalization; hyphenated project names handled by checking
    the bare project token, not split-by-hyphen pieces.
  - plan(): validator-feedback retry — when the first attempt fails
    closed-set validation, the second attempt re-prompts the planner
    with the exact validation reasons appended, asking it to correct
    the specific identifiers rather than blind regenerate.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


_REQUIRED_KEYS = (
    'selected_database', 'selected_schema',
    'selected_tables', 'selected_columns',
    'metrics', 'filters', 'time_constraints',
    'grouping', 'sorting', 'limit',
    'ambiguity_points', 'expected_shape',
)

_DATE_SHARD_RE = re.compile(r'^(?P<base>.+?)_(?P<date>\d{6,8})$')


@dataclass
class PlanValidation:
    ok: bool
    reasons: list = field(default_factory=list)
    closed_set_db: set = field(default_factory=set)
    closed_set_schemas: set = field(default_factory=set)
    closed_set_tables: set = field(default_factory=set)
    closed_set_columns: set = field(default_factory=set)


def _closed_sets(pack: dict) -> tuple:
    """Return rich identifier sets including wildcard families."""
    dbs = {d['name'] for d in pack.get('databases', [])}
    schemas = set()
    project_dataset = set()
    for d in pack.get('databases', []):
        for s in d.get('schemas', []):
            schemas.add(s)
            project_dataset.add(f"{d.get('name','')}.{s}")
    tables = set()
    wildcard_bases = set()
    for t in pack.get('tables', []):
        tables.add(t['table'])
        m = _DATE_SHARD_RE.match(t['table'])
        if m:
            wildcard_bases.add(m.group('base'))
    columns = set()  # full names + roots + leaves
    for t in pack.get('tables', []):
        for c in t.get('columns', []):
            cn = c['name']
            columns.add(cn)
            if '.' in cn:
                columns.add(cn.split('.')[0])
                columns.add(cn.split('.')[-1])
            else:
                columns.add(cn)
    return dbs, schemas, project_dataset, tables, wildcard_bases, columns


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_HYPH_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*")


def _table_in_pack(name: str, tables: set, wildcard_bases: set) -> bool:
    if name in tables:
        return True
    if name.endswith('_*') and name[:-2] in wildcard_bases:
        return True
    m = _DATE_SHARD_RE.match(name)
    if m and m.group('base') in wildcard_bases:
        return True
    return False


def _column_in_pack(name: str, columns: set) -> bool:
    if name in columns:
        return True
    leaf = name.split('.')[-1] if '.' in name else name
    root = name.split('.')[0] if '.' in name else name
    return leaf in columns or root in columns


def validate_plan(plan: dict, pack: dict) -> PlanValidation:
    reasons = []
    dbs, schemas, project_dataset, tables, wildcard_bases, columns = _closed_sets(pack)

    for k in _REQUIRED_KEYS:
        if k not in plan:
            reasons.append(f'missing_key:{k}')

    # selected_database / selected_schema: tolerate either bare project,
    # bare dataset, or "project.dataset" composite.
    sd = plan.get('selected_database') or ''
    if sd and sd not in dbs and sd not in project_dataset:
        # if dotted, accept if at least the project part is in dbs
        if '.' in sd:
            head = sd.split('.', 1)[0]
            if head in dbs:
                pass  # ok
            else:
                reasons.append(f'unknown_database:{sd}')
        else:
            reasons.append(f'unknown_database:{sd}')

    ss = plan.get('selected_schema') or ''
    if ss and ss not in schemas:
        # accept if it's a "project.dataset" path with a known dataset tail
        if '.' in ss:
            tail = ss.rsplit('.', 1)[-1]
            if tail in schemas:
                pass
            else:
                reasons.append(f'unknown_schema:{ss}')
        else:
            reasons.append(f'unknown_schema:{ss}')

    for t in plan.get('selected_tables', []) or []:
        # accept FQN forms by stripping prefix to bare table name
        bare = t.split('.')[-1] if '.' in t else t
        if not _table_in_pack(bare, tables, wildcard_bases):
            reasons.append(f'unknown_table:{t}')

    for c in plan.get('selected_columns', []) or []:
        if not _column_in_pack(c, columns):
            reasons.append(f'unknown_column:{c}')

    # SQL keyword whitelist for free-form expressions
    sql_keywords = {
        'SELECT','FROM','WHERE','GROUP','BY','ORDER','HAVING','AS','AND','OR',
        'NOT','IN','LIKE','BETWEEN','IS','NULL','TRUE','FALSE','LIMIT',
        'DISTINCT','ON','JOIN','LEFT','RIGHT','INNER','OUTER','UNION',
        'COUNT','SUM','AVG','MIN','MAX','CAST','EXTRACT','DATE','TIMESTAMP',
        'INT','INT64','FLOAT','STRING','ARRAY','STRUCT','UNNEST','SAFE_CAST',
        'OVER','PARTITION','WITH','EXISTS','TRY_CAST','THEN','CASE','WHEN','ELSE','END',
        'INTERVAL','CURRENT_DATE','CURRENT_TIMESTAMP','LATERAL','FLATTEN','INPUT',
        'DATETIME','TIME','BOOL','BOOLEAN','BYTES','NUMERIC','BIGNUMERIC','DESC','ASC',
        'YEAR','MONTH','DAY','QUARTER','WEEK','HOUR','MINUTE','SECOND',
        'DATE_DIFF','DATE_ADD','DATE_SUB','TIMESTAMP_DIFF','UNIX_SECONDS','UNIX_MILLIS',
        'COALESCE','IFNULL','NULLIF','GREATEST','LEAST','ROW_NUMBER','RANK','DENSE_RANK',
        '_TABLE_SUFFIX','TABLE_SUFFIX','APPROX_COUNT_DISTINCT','PERCENTILE_CONT',
    }
    for which in ('metrics', 'filters', 'sorting'):
        for item in plan.get(which, []) or []:
            expr = item.get('expr', '') if isinstance(item, dict) else str(item)
            # Use the hyphen-tolerant tokenizer so 'bigquery-public-data'
            # is one token, not three.
            for tok in _HYPH_IDENT_RE.findall(expr):
                if tok.upper() in sql_keywords:
                    continue
                if tok in dbs or tok in schemas or tok in tables or tok in columns:
                    continue
                if tok in wildcard_bases:
                    continue
                if tok.lower() in {'true', 'false', 'null'}:
                    continue
                if tok.isdigit() or len(tok) <= 1:
                    continue
                # Tolerate single-letter+digit aliases (e1, t2, etc.)
                if re.fullmatch(r'[a-z]\d?', tok):
                    continue
                # leaf/root of dotted ident
                if '.' in tok:
                    leaf = tok.split('.')[-1]
                    if leaf in columns:
                        continue
                # date shard <table>_YYYYMMDD
                m = _DATE_SHARD_RE.match(tok)
                if m and m.group('base') in wildcard_bases:
                    continue
                reasons.append(f'unknown_ident_in_{which}:{tok}')

    ok = not reasons
    return PlanValidation(ok=ok, reasons=reasons,
                            closed_set_db=dbs, closed_set_schemas=schemas,
                            closed_set_tables=tables,
                            closed_set_columns=columns)


def parse_plan(raw_text: str) -> dict:
    """Parse LLM output into a JSON plan."""
    s = raw_text.strip()
    if '```' in s:
        m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', s)
        if m:
            s = m.group(1)
    if not s.startswith('{'):
        m = re.search(r'(\{[\s\S]*\})\s*$', s)
        if m:
            s = m.group(1)
    return json.loads(s)


def plan_with_loaded_model(prompt: str, *, max_new: int = 1100) -> str:
    """Call the loaded HF model+tokenizer to generate the plan text."""
    g = globals()
    if g.get('_GEN_READY') is not True:
        raise NotImplementedError(
            'Model not loaded; call model_registry_v17.load_model_and_tokenizer first.')
    import torch
    nt = bool(g.get('_MODEL_PROFILE', {}).get('non_thinking_mode', False))
    msgs = [{'role': 'user', 'content': prompt}]
    extra = {'enable_thinking': False} if nt else {}
    try:
        enc = g['_TOK'].apply_chat_template(
            msgs, return_tensors='pt', add_generation_prompt=True,
            return_dict=True, **extra)
    except TypeError:
        enc = g['_TOK'].apply_chat_template(
            msgs, return_tensors='pt', add_generation_prompt=True,
            return_dict=True)
    enc = {k: v.to(g['_MDL'].device) for k, v in enc.items()}
    with torch.no_grad():
        out = g['_MDL'].generate(**enc, max_new_tokens=max_new,
                                    do_sample=False, temperature=0.0,
                                    pad_token_id=g['_TOK'].eos_token_id)
    gen = out[0][enc['input_ids'].shape[1]:]
    return g['_TOK'].decode(gen, skip_special_tokens=True)


def _retry_prompt(original_prompt: str, reasons: list, prev_plan: Optional[dict]) -> str:
    """Append the validator's complaint list to the prompt for a second
    attempt. The model gets the explicit reasons and is asked to fix
    only those identifiers, not regenerate the whole plan."""
    fb = ['', '---', 'Your previous JSON plan failed validation. Issues:']
    for r in reasons[:12]:
        fb.append(f'  - {r}')
    if prev_plan is not None:
        fb.append('')
        fb.append('Previous plan was:')
        try:
            fb.append(json.dumps(prev_plan, indent=2)[:1500])
        except Exception:
            pass
    fb.append('')
    fb.append('Return a corrected JSON plan that uses ONLY identifiers from the')
    fb.append('Available identifiers list above. Same JSON shape, no prose.')
    return original_prompt + '\n'.join(fb)


def plan(prompt: str, pack: dict, *, max_attempts: int = 2) -> dict:
    """High-level entry: generate -> parse -> validate, with v18.1
    feedback-retry. Returns dict {'plan', 'validation', 'raw',
    'attempts', 'last_parse_err', 'retry_used'}."""
    raw = ''
    last_err = None
    last_plan = None
    last_val = None
    retry_used = False
    cur_prompt = prompt
    for attempt in range(1, max_attempts + 1):
        raw = plan_with_loaded_model(cur_prompt)
        try:
            cand = parse_plan(raw)
        except Exception as e:
            last_err = f'parse_err:{type(e).__name__}:{str(e)[:200]}'
            continue
        v = validate_plan(cand, pack)
        last_plan = cand
        last_val = v
        if v.ok:
            return {'plan': cand, 'validation': v, 'raw': raw,
                      'attempts': attempt, 'retry_used': retry_used}
        if attempt < max_attempts:
            cur_prompt = _retry_prompt(prompt, v.reasons, cand)
            retry_used = True
    return {'plan': last_plan, 'validation': last_val, 'raw': raw,
              'attempts': max_attempts, 'last_parse_err': last_err,
              'retry_used': retry_used}
