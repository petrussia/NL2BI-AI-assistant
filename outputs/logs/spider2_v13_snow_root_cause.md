# Spider2-Snow v13 — root cause memo

_Generated: 2026-05-08_

## Symptom

Snow v13 pilot10: 9 predictions written (runner crashed on task 10),
**all 9 with schema_valid=False**.

Engineering bug: `len(it["external_knowledge"])` in trace-write where
the field was None for some Spider2-Snow tasks. Crash isolated to
trace-line writing; predictions for tasks 1-9 are valid. Fix: replace
`d.get("external_knowledge", "")` with `d.get("external_knowledge") or ""`.

## What v13 added vs v12

- **Rich render restored**: column descriptions + sample values + table
  descriptions returned to the prompt (v12 had stripped them).
- **`external_knowledge` injected** in all three candidate prompts.
- **3-round repair** kept (r1 unknown-id → r2 syntax → r3 regenerate).
- **Variant/array column-ref skip** in validator (column refs whose
  qualifier is a VARIANT column are no longer flagged unknown).
- **Self-recovery on `/content/` wipe** kept.

## Outcome

None of the v13 additions moved schema_valid above 0. The richer
prompt did not stop the model from inventing column names.

## Aggregate Snow evidence

| pilot | schema_valid | render | repair |
|---|---:|---|---|
| v10 | 0/10 | rich, no validator | none |
| v11 | 1/10 | rich | 1-round, lexical only |
| v12 | 0/10 | strict compact | 3-round (unknown-id → syntax → regen) |
| **v13** | **0/9** | rich + ext_knowledge | 3-round (same as v12) |

Across 4 Snow pilots × 10 tasks × 3+ candidates per task, only
**1 chosen schema-valid** result has emerged — the v11 single hit.
This is consistent with model-quality dominance: Coder-7B BF16
hallucinates identifiers even with explicit suggestions.

## Conclusion

Schema-grounding direction is exhausted on Snow with this generator.
Levers remaining:
1. **Constrained identifier substitution** (deterministic post-process,
   no LLM repair) — user-stated fallback. Phase 16.
2. INT4 Coder-32B sanity (bigger model).
3. Hybrid retrieval with gold metadata where available.

## Bug-fix backlog

- Trace-write line `"ext_knowledge_chars": len(ek)` must use
  `len(ek or "")`. Trivially fixable in next runner.
