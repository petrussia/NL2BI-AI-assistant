# Spider2 Preflight vNext — 2026-05-07T22:50:31+00:00

**8/8 checks passed.**

| lane | check | ok | wall_s | detail |
|---|---|:---:|---:|---|
| `bridge` | `health` | ✅ | 0.56 | pid=1139 url=https://mathematical-selecting-belkin-marketing.trycloudflare.com |
| `colab` | `hf_token` | ✅ | 0.48 | HF_OK |
| `bigquery` | `bq_full` | ✅ | 1.86 | project=project-0e0fc8a5-27b1-4e00-912 dry=0B live_n=164656 cap=52428800 |
| `snowflake` | `sf_full` | ✅ | 30.07 | role=PARTICIPANT wh=COMPUTE_WH_PARTICIPANT db=PATENTS | ALL_OK=True | PATENTS.tables=64 |
| `spider2_lite` | `dataset` | ✅ | 0.86 | n=547 lanes={'bigquery': 205, 'snowflake': 207, 'sqlite': 135} dbs=158 gold=3 res_dbs=3 |
| `spider2_snow` | `dataset` | ✅ | 0.5 | sf_subset_n=207 dbs=58 snow_dir_present=False |
| `spider2_dbt` | `env` | ✅ | 3.37 | ssh=True dbt='Core:' DUCKDB= 1.5.2 examples=70 eval_suite=yes |
| `security` | `no_secrets_in_git` | ✅ | 0.03 | tracked_risky=['tools/.bridge_url'] (note: tools/.bridge_url is non-credential, ephemeral URL only) |

## Lane readiness
| lane | ready |
|---|:---:|
| `colab_bridge` | ✅ |
| `colab_inference` | ✅ |
| `bq` | ✅ |
| `sf` | ✅ |
| `s2lite` | ✅ |
| `s2snow` | ✅ |
| `s2dbt` | ✅ |
| `security` | ✅ |

## Notes
- Spider2-Snow on this Drive copy is the SF-prefix subset of Spider2-Lite (207 SF tasks). The official Spider2-Snow benchmark is a separate 547-task release; if a separate `spider2-snow.jsonl` is required, it must be downloaded before Phase 1 FULL.
- `tools/.bridge_url` is tracked but contains only an ephemeral Cloudflare quick-tunnel URL, not a credential.
- `snowflake_setup/.env` and `secrets/spider2_bq_sa.json` are NOT in git.