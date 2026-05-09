# Spider2 Phase 16 → Phase 17 — recommendation

_Generated: 2026-05-08_

## What Phase 16 changed

- **BQ schema_valid 1/10 → 6/10** with constrained identifier
  substitution. First non-DBT Spider2 lane to clear the schema_valid
  gate.
- Snow stayed at the 0-1/10 floor — substitution doesn't help when
  hallucinations are semantic (not typo-shaped).
- Wall time on BQ pilot dropped from 1232s (v12) → 739s (v16) —
  deterministic repair faster than LLM repair.
- Root-cause audit table now exists: 95.7% of all historical failures
  are true_hallucination — confirms ceiling for engineering-only fixes.

## What Phase 16 did NOT change

- **parse_ok still 0/10 on BQ** — 5/6 schema-valid candidates fail
  BQ live `dry_run` with `object_not_found`. Catalog/live divergence,
  NOT validator bug.
- Snow stays at 0% — same blockers as Phase 11–15.
- No FULL benchmark launched (gates not cleared).

## Recommended order for Phase 17

### (1) BQ catalog refresh from live `INFORMATION_SCHEMA` (highest leverage)
Cheap, deterministic, no model lift needed. Replaces stale JSON
metadata with what BigQuery actually exposes to our SA. Expected:
parse_ok 0/10 → 3-5/10 on the same v16 pilot. If parse_ok ≥ 30% AND
schema_valid stays ≥ 30%, BQ FULL gate clears. ~1-2h code.

### (2) Snow INT4 Coder-32B sanity (model-quality test)
On A100-40GB. Run Snow v16 pilot10 with Qwen2.5-Coder-32B-Instruct-AWQ.
- Goal: see if schema_valid jumps to 3+/10.
- If yes: model size is the lever; FULL becomes reachable on a
  stronger generator.
- If no: model size is NOT the lever; constrained decoding or hybrid
  retrieval becomes the path.
GPU note: L4 22.5GB is marginal for 32B-AWQ even — better to wait
for A100 access (Pro+ subscription).

### (3) Hybrid retrieval with gold metadata
Inject Spider2's per-task `gold_columns` list (where available) as
the catalog filter. Marks results clearly as "oracle retrieval", NOT
official EX. Useful as upper-bound check on what's achievable with
perfect retrieval.

### (4) Constrained decoding (research lift)
Token-mask generation in identifier positions to catalog substrings.
Significant engineering. Only viable if (1)–(3) don't clear gates.

## What goes into ВКР NOW (after Phase 16 + push)

| signal | source |
|---|---|
| Spider2-DBT FULL 68 = 13.2% task_success | Phase 11 (commit 09abb5a) |
| Spider2-Snow canonical 547 dataset acquisition + sha256 manifest | Phase 11 |
| v9 dialect normalizer (wrong_dialect 2/3 → 0/10) | Phase 12 |
| v11 schema-grounding validator (object_not_found AT engine 7-10/10 → 0/10 on both lanes) | Phase 13 |
| v12 BQ validator hardening (struct/wildcard/4-part, +1 schema_valid) | Phase 14 |
| **v16 constrained identifier substitution (BQ schema_valid 1 → 6 on n=10)** | **Phase 16, this commit** |
| Root-cause audit table: 95.7% true_hallucination across 117 attempts | Phase 16 |
| Discipline: gate policy + no FULL on partial + per-lane separation | Phases 11-16 master matrices |

## What MUST NOT go into ВКР

- Any Snow / Lite-BQ / Lite-SF FULL number (no FULL run, all gated).
- The 6/10 BQ v16 schema_valid framed as a benchmark result — it is
  a pipeline-completion signal, not a quality result. Live BQ
  rejected all 6.
- Any "Spider2 average" across DBT + Lite + Snow.

## Operational reminders

- All commits stay local until explicit user push.
- GCP SA test key rotated before any external publish.
- DBT FULL 68 is the only publishable Spider2 number; everything else
  is pilot-engineering.
