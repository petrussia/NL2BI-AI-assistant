"""spider2_snow_schema_render_v10 — H1 fix: clean SF identifier rendering.

Problem (v9 pilot10): `render_table_block` produced a single-quoted
fully-qualified name `"DB.SCHEMA.TABLE"` and ALSO leaked the
`table_fullname` field into the prompt. Coder-7B reacted by emitting
4-part identifiers with a duplicated schema segment, e.g.
`"GA4"."GA4_OBFUSCATED_SAMPLE_ECOMMERCE"."GA4_OBFUSCATED_SAMPLE_ECOMMERCE"."EVENTS_20201225"`.

Fix:
1. Render identifier ONCE, unquoted, as `DB.SCHEMA.TABLE` (Snowflake
   uppercases unquoted identifiers — the JSON files already use
   uppercase, so this is safe).
2. Never expose `table_fullname` to the prompt; the only canonical
   reference is the unquoted 3-part name printed at the head of the
   table block.
3. Strict prompt rule lines warning the model NOT to duplicate any
   identifier segment and NOT to wrap segments in extra quotes.
4. Companion identifier normalizer
   `normalize_identifiers_v10(sql, idx)` post-processes generated SQL:
   - `"A"."B"."B"."C"` → `A.B.C` (drop duplicated middle segment)
   - `"A.B.C"` (whole blob quoted) → `A.B.C`
   - 4-part with a known-bad duplicated schema → 3-part canonical
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from spider2_sf_schema_index_v8 import SfSchemaIndex, SfTable


_HEADER_NOTE = (
    "-- Snowflake schema. Identifiers shown UNQUOTED in canonical "
    "DB.SCHEMA.TABLE form. Use them VERBATIM. Do NOT wrap segments "
    "in extra quotes. Do NOT repeat segments. Use 3-part names only "
    "(DB.SCHEMA.TABLE) — never 4-part."
)


def render_table_block_v10(t: SfTable, *, max_cols: int = 25,
                              include_samples: bool = True) -> str:
    """Render a single table — v10 form.

    Header is the canonical unquoted 3-part identifier. Followed by
    columns with type + (truncated) description + sample values.
    No `table_fullname`. No outer quotes around the fq_name.
    """
    head = t.fq_name  # e.g. GA4.GA4_OBFUSCATED_SAMPLE_ECOMMERCE.EVENTS_20201225
    lines = [head]
    if t.description:
        lines.append(f'  -- {t.description[:180]}')
    cols = t.columns[:max_cols]
    for c in cols:
        line = f'  {c.name} {c.dtype}'
        if c.description:
            line += f'  -- {c.description[:100]}'
        if include_samples and c.sample_values:
            line += f'  /* eg. {", ".join(c.sample_values[:3])} */'
        lines.append(line)
    if len(t.columns) > max_cols:
        lines.append(f'  -- ...{len(t.columns) - max_cols} more columns')
    return '\n'.join(lines)


def render_subset_v10(idx: SfSchemaIndex, table_keys: list[str], *,
                          max_cols: int = 25,
                          include_samples: bool = True) -> str:
    if not idx.tables:
        return f'-- (empty index for {idx.db_id})'
    out: list[str] = [_HEADER_NOTE, f'-- DB: {idx.db_id}']
    seen: set[str] = set()
    for key in table_keys:
        kU = key.upper()
        for t in idx.tables:
            if t.fq_name.upper() == kU or t.table_name.upper() == kU:
                if t.fq_name in seen: break
                seen.add(t.fq_name)
                out.append(render_table_block_v10(t, max_cols=max_cols,
                                                       include_samples=include_samples))
                break
    if not seen:
        for t in idx.tables[:5]:
            out.append(render_table_block_v10(t, max_cols=max_cols,
                                                   include_samples=include_samples))
    return '\n\n'.join(out)


# ---- identifier post-normalizer ------------------------------------------

# Match a 4-part dotted identifier optionally per-segment quoted, e.g.
#   "A"."B"."B"."C"   or   A.B.B.C
# We're conservative: only collapse if segment 2 == segment 3.
_QUOT = r'"([^"]+)"|([A-Za-z_][\w$]*)'
_DOT_4PART_RE = re.compile(
    fr'(?:{_QUOT})\.(?:{_QUOT})\.(?:{_QUOT})\.(?:{_QUOT})'
)


def _seg(m: re.Match, base: int) -> str:
    """Pull either the quoted or unquoted alternative from a (q1|u1) pair."""
    return m.group(base) or m.group(base + 1)


def collapse_dup_schema_in_4part(sql: str) -> tuple[str, int]:
    """Replace `A.B.B.C` (with optional per-segment quoting) → `A.B.C`.
    Returns (new_sql, n_replacements).
    """
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        s1 = _seg(m, 1)
        s2 = _seg(m, 3)
        s3 = _seg(m, 5)
        s4 = _seg(m, 7)
        if s2 and s3 and s2.upper() == s3.upper():
            n += 1
            return f'{s1}.{s2}.{s4}'
        return m.group(0)

    out = _DOT_4PART_RE.sub(repl, sql)
    return out, n


# Match a single fully-quoted blob like  "DB.SCHEMA.TABLE"  (one pair of
# quotes around the whole 3-part). Unwrap to unquoted segments.
_QUOTED_3PART_BLOB_RE = re.compile(
    r'"([A-Za-z_][\w$]*\.[A-Za-z_][\w$]*\.[A-Za-z_][\w$]*)"'
)


def unwrap_quoted_3part_blob(sql: str) -> tuple[str, int]:
    n = 0
    def repl(m: re.Match) -> str:
        nonlocal n
        n += 1
        return m.group(1)
    out = _QUOTED_3PART_BLOB_RE.sub(repl, sql)
    return out, n


@dataclass
class IdentifierNormResult:
    sql: str
    n_4part_collapsed: int = 0
    n_quoted_blob_unwrapped: int = 0

    def applied(self) -> bool:
        return self.n_4part_collapsed > 0 or self.n_quoted_blob_unwrapped > 0


def normalize_identifiers_v10(sql: str) -> IdentifierNormResult:
    if not sql:
        return IdentifierNormResult(sql=sql or '')
    cur = sql
    cur, n1 = collapse_dup_schema_in_4part(cur)
    cur, n2 = unwrap_quoted_3part_blob(cur)
    return IdentifierNormResult(sql=cur, n_4part_collapsed=n1,
                                  n_quoted_blob_unwrapped=n2)
