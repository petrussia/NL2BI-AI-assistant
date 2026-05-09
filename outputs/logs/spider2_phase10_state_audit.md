# Spider2 Phase 10 — state audit

_Generated: 2026-05-08 | branch: `experiments/denis`_

## Git state

- **Current branch**: `experiments/denis`
- **HEAD**: `a5cdbfe` — _Phase 10 Spider2 full benchmark execution — Snow, Lite, DBT agent v8_
- **a5cdbfe locally present**: ✅ yes (`git rev-parse a5cdbfe` resolves)
- **a5cdbfe pushed to origin**: ❌ **NOT pushed**. `git log origin/experiments/denis..HEAD` shows `a5cdbfe` is local-only. Per instructions, no `git push` triggered.
- **Remote**: `https://github.com/petrussia/NL2BI-AI-assistant.git`

### Last 10 commits

```
a5cdbfe Phase 10 Spider2 full benchmark execution — Snow, Lite, DBT agent v8
ac84d20 Add Spider2 DBT vNext experiment strategy
8f57eea Spider2-DBT prompt ablation V1/V2/V4 — V4 (diff-form) wins +1 score, +2 clean compiles
2d4697d Spider2-DBT: first real-model end-to-end run on asana001 (score 0/1, pipeline green)
16345f9 Snowflake setup for Spider2-Lite SF subset (no run, prep only)
af8d411 Spider2-DBT bridge — local generates, server (denis@103.54.18.91) evaluates
e7d0032 Snowflake setup for Spider2-Lite SF subset (no run, prep only)
54e060c Phase 10 spider2_bq agent_v8 — multi-candidate BQ agent; +24.9pp exec, +0.49pp EX vs v7
0f70a5c Phase 9 spider2_lite agent_v7 — lane-aware multi-engine agent; honest BQ EX vs gold
1a74b4b Add NEW_AGENT_BRIEFING.md — self-contained briefing for next agent (Priority 4 Spider2-Lite)
```

## Working tree

- **283 entries** in `git status --short` total.
- Modified (`M`) — pre-existing tracked files from earlier sessions:
  - `notebooks/example.ipynb`, `outputs/REPORT.md`, `outputs/logs/final_*.md`,
    `outputs/plots/final_experiment_master_overview.png`,
    `outputs/snowflake/readiness/databases_visible.{json,md}`,
    `outputs/tables/final_experiment_master_matrix.{csv,md}`,
    `spider2_dbt_bridge/run_dbt_ablation.py`,
    `tools/remote_scripts/_run_dbt_inference.py`.
- Untracked (`??`): a large set of derived artifacts from prior sessions —
  `data/spider2_dbt/tasks/*` workspace files, `outputs/dbt_ablation/*`,
  `outputs/exports/*`, `outputs/joint_vkr_export_pack_v10/*`, dozens of
  `outputs/logs/b0_*runlog.txt`, `tools/remote_scripts/_*.py` scratch.
  None of these were created in this Phase 11 / v9 session.

## Secrets scan

- Staged: nothing staged at audit time.
- Untracked: no `.env`, no `*sa.json`, no `BEGIN ...PRIVATE KEY...` strings
  found in any file matched by `git status` (verified earlier with `git diff
  --cached`). `.gitignore` from commit `a5cdbfe` already lists
  `snowflake_setup/.env`, `**/*sa.json`, `**/secrets/`, and
  `tools/.bridge_url`.
- The GCP service-account key remains on Drive at
  `/content/drive/MyDrive/diploma_plan_sql/secrets/spider2_bq_sa.json`
  (not in repo).

## Spider2 datasets actually present (after STEP 2)

| dataset | location | rows | status |
|---|---|---:|---|
| Spider2-Lite 547 | Drive `external_benchmarks/spider2_lite/raw/Spider2/spider2-lite/spider2-lite.jsonl` + local `data/spider2_lite/raw/spider2-lite.jsonl` | 547 | ✅ both Drive and local |
| Spider2-Snow canonical 547 | Drive `external_benchmarks/spider2_snow/processed/spider2_snow_547.jsonl` + local `data/spider2_snow/raw/spider2-snow.jsonl` | 547 | ✅ acquired in this session via `xlang-ai/Spider2` tarball |
| Spider2-DBT 68 | server `/home/denis/dbt/vendor/Spider2/spider2-dbt/examples` (70 dirs, 68 are tasks) | 68 | ✅ |

Spider2-Snow canonical schema differs from Spider2-Lite:

| Spider2-Lite field | Spider2-Snow field |
|---|---|
| `db` | `db_id` |
| `question` | `instruction` |
| `external_knowledge` | `external_knowledge` |
| `instance_id` | `instance_id` |

The v8 Snow runner reads `question`/`db` and **MUST be adapted for the
canonical Snow schema** before STEP 4 FULL. v9 runner does this.

## Snow canonical first-3 / per-DB

- First instance_id: `sf_bq011` (db_id=None on first row??) / corrected
  per-row scan: every Snow item is `sf_*` prefix; **152 unique db_ids**;
  top by row count: `CRYPTO=20, THELOOK_ECOMMERCE=19, GA4=17, PATENTS=15,
  GITHUB_REPOS=15, STACKOVERFLOW=15, IDC=15, BANK_SALES_TRADING=15`.
- Manifest at Drive `manifests/spider2_snow_manifest.json` records:
  - source: `https://github.com/xlang-ai/Spider2/tree/main/spider2-snow`
  - tarball sha256, tarball size 327 575 607 bytes
  - jsonl sha256, jsonl size 245 274 bytes
  - 547 rows / 152 unique dbs
  - acquired_at UTC

## Background task

- `outputs/spider2_dbt/_full68.log` — Spider2-DBT FULL 68 (v4) running in
  background as of audit time (~8/68 done). Output collected once finished.

## What this session is NOT doing

- ❌ No `git push`. `a5cdbfe` stays local-only until explicit command.
- ❌ No FULL claim made on PILOT data.
- ❌ No mixing of Spider2-Snow and Spider2-Lite metrics.
- ❌ No write of leaked secrets from chat to disk.
