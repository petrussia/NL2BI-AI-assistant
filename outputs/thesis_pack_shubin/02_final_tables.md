# 02 — Final tables (Shubin)

_Generated: 2026-04-30T12:28:47.260219+00:00_

## Master matrix
# Final Experiment Master Matrix
Generated: 2026-04-30T12:28:42.949200+00:00

|Run|Baseline|Model|Subset|n|EX|Executable|Plan-valid|Avg-red|Fallback|
|---|---|---|---|---|---|---|---|---|---|
|b0_llama_3p1_8b_instruct_smoke10|b0|meta-llama/Llama-3.1-8B|smoke_10|10|0.8000|10|—|—|—|
|b0_multidb30_v2|b0|Qwen2.5-Coder-7B|multidb_30|30|0.9333|30|—|—|—|
|b0_qwen_qwen2.5_7b_instruct_smoke10|b0|Qwen2.5-7B|smoke_10|10|0.6000|9|—|—|—|
|b0_spider_smoke10|b0|Qwen2.5-Coder-7B|smoke_10|10|1.0000|10|—|—|—|
|b0_spider_smoke25|b0|Qwen2.5-Coder-7B|smoke_25|25|0.9600|25|—|—|—|
|b1_llama_3p1_8b_instruct_smoke10|b1|meta-llama/Llama-3.1-8B|smoke_10|10|0.9000|10|—|0.475|—|
|b1_multidb30_v2|b1|Qwen2.5-Coder-7B|multidb_30|30|0.7667|29|—|0.5527777777777777|—|
|b1_qwen_qwen2.5_7b_instruct_smoke10|b1|Qwen2.5-7B|smoke_10|10|1.0000|10|—|0.475|—|
|b1_spider_smoke10|b1|Qwen2.5-Coder-7B|smoke_10|10|1.0000|10|—|0.475|—|
|b1_spider_smoke25|b1|Qwen2.5-Coder-7B|smoke_25|25|0.9600|25|—|0.58|—|
|b2_spider_smoke10|b2|Qwen2.5-Coder-7B|smoke_10|10|0.7000|9|9|0.475|—|
|b2v1_multidb30|b2v1|Qwen2.5-Coder-7B|multidb_30|30|0.6333|26|28|0.5527777777777777|—|
|b2v1_spider_smoke10|b2v1|Qwen2.5-Coder-7B|smoke_10|10|0.6000|8|8|0.475|—|
|b2v2_multidb30|b2v2|Qwen2.5-Coder-7B|multidb_30|30|0.8000|29|—|—|b1_on_invalid_plan|
|b2v2_spider_smoke10|b2v2|Qwen2.5-Coder-7B|smoke_10|10|0.8000|10|—|—|b1_on_invalid_plan|
|b3_spider_smoke10|b3|Qwen2.5-Coder-7B|smoke_10|10|0.2000|2|2|0.475|—|
|b3v1_multidb30|b3v1|Qwen2.5-Coder-7B|multidb_30|30|0.4667|18|18|0.5527777777777777|—|
|b3v1_spider_smoke10|b3v1|Qwen2.5-Coder-7B|smoke_10|10|0.3000|5|5|0.475|—|
|b3v2_multidb30|b3v2|Qwen2.5-Coder-7B|multidb_30|30|0.7333|29|—|0.5527777777777777|b1_on_invalid_plan|
|b3v2_spider_smoke10|b3v2|Qwen2.5-Coder-7B|smoke_10|10|0.8000|10|—|0.475|b1_on_invalid_plan|
|b4_final_multidb30|b4|Qwen2.5-Coder-7B|multidb_30|30|0.4667|18|18|0.5527777777777777|—|
|b4_final_spider_smoke10|b4|Qwen2.5-Coder-7B|smoke_10|10|0.3000|5|5|0.475|—|
|b4_spider_smoke10|b4|Qwen2.5-Coder-7B|smoke_10|10|0.2000|2|2|0.475|—|
|b4v2_multidb30|b4v2|Qwen2.5-Coder-7B|multidb_30|30|0.7333|29|—|0.5527777777777777|b1_on_invalid_or_no_executable|
|b4v2_spider_smoke10|b4v2|Qwen2.5-Coder-7B|smoke_10|10|0.8000|10|—|0.475|b1_on_invalid_or_no_executable|


## multidb_30 strongest configs
# Strongest configs on multidb_30
_Generated: 2026-04-30T12:11:34.000322+00:00_

| Baseline | Model | n | EX | Executable | Plan-valid | Present |
|---|---|---|---|---|---|---|
| B0 | Qwen2.5-Coder-7B | 30 | 0.9333 | 30 | — | True |
| B1 | Qwen2.5-Coder-7B | 30 | 0.7667 | 29 | — | True |
| B2_v1 | Qwen2.5-Coder-7B | 30 | 0.6333 | 26 | 28 | True |
| B3_v1 | Qwen2.5-Coder-7B | 30 | 0.4667 | 18 | 18 | True |
| B3_v2 | Qwen2.5-Coder-7B | 30 | 0.7333 | 29 | — | True |
| B4_final | Qwen2.5-Coder-7B | 30 | 0.4667 | 18 | 18 | True |
| B4_v2 | Qwen2.5-Coder-7B | 30 | 0.7333 | 29 | — | True |
| B0 | Qwen2.5-Coder-14B | — | — | — | — | False |
| B1 | Qwen2.5-Coder-14B | — | — | — | — | False |


## B3_v2 vs B3_v1
```
comparison,baseline,subset,EX,executable,plan_valid,n,file
B3v2_vs_B3v1_smoke_10,B3V1,smoke_10,0.3,5,5,10,b3v1_spider_smoke10
B3v2_vs_B3v1_smoke_10,B3V2,smoke_10,0.8,10,,10,b3v2_spider_smoke10
B3v2_vs_B3v1_multidb_30,B3V1,multidb_30,0.4666666666666667,18,18,30,b3v1_multidb30
B3v2_vs_B3v1_multidb_30,B3V2,multidb_30,0.7333333333333333,29,,30,b3v2_multidb30

```

## B4_v2 vs B4_final
```
comparison,baseline,subset,EX,executable,plan_valid,n,file
B4v2_vs_B4final_smoke_10,B4,smoke_10,0.3,5,5,10,b4_final_spider_smoke10
B4v2_vs_B4final_smoke_10,B4V2,smoke_10,0.8,10,,10,b4v2_spider_smoke10
B4v2_vs_B4final_multidb_30,B4,multidb_30,0.4666666666666667,18,18,30,b4_final_multidb30
B4v2_vs_B4final_multidb_30,B4V2,multidb_30,0.7333333333333333,29,,30,b4v2_multidb30

```

## Component registry
```
layer,component,module_or_artifact,closes_tz_item,status
1. NL analysis,Query Analyzer,repo/src/evaluation/query_analysis.py,2.2.1,done
2. Source linking,Lexical Schema Linker,repo/src/evaluation/baselines.py,2.2.2,done
2b. Cross-DB retrieval,Lexical retrieval,repo/src/evaluation/retrieval.py,2.2.2,done
2c. Knowledge channel,Per-table doc proxy,repo/src/evaluation/baselines_b3.py,2.2.2 (extended),done
3. Planner,JSON Plan emitter,repo/src/evaluation/baselines_b2.py + b2_v1.py,2.2.4,done
4. Plan validator,jsonschema,repo/docs/plan_schema_v1.json,2.2.4,done
5. SQL synthesizer,plan→sql prompt,baselines_b2*.py + baselines_b3.py,2.2.3,done
6. Validation gate,SELECT-only AST guard,baselines_b4.py::is_safe_select,2.2.3 (safety),done
7. Multi-candidate + Repair,sampling + consistency,baselines_b4.py,2.2.4,done
8. Executor,SQLite + 8s timeout,func_timeout-wrapped execute_sql,2.2.3 (performance),done
9. Postprocess,normalize + summary,postprocess.py,2.2.5,done
10. Analytics handoff,v1 JSON+CSV contract,postprocess.py::build_analytics_payload,2.2.6,done
11. Bridge tooling,Flask + cloudflared + exec_remote,notebook cell 7f6bca53 + tools/exec_remote.py,infra,done

```
