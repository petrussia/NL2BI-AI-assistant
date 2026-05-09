# Spider2-Lite structural quality summary (Qwen2.5-Coder-7B)

Spider2-Lite was run **structural-only** (no BigQuery/Snowflake creds).
These columns describe the syntactic / structural features of generated SQL,
**not accuracy**.

| Cell | N | safe% | SELECT% | avg joins | avg WHERE | avg GROUP | avg ORDER | avg AGG | avg subq | avg len (chars) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| b0_qwen2p5_coder_7b_spider2lite_full | 547 | 100.0% | 100.0% | 1.0 | 1.133 | 0.766 | 0.656 | 2.349 | 0.722 | 469.2 |
| b3v4_qwen2p5_coder_7b_spider2lite_full | 547 | 100.0% | 100.0% | 0.984 | 1.135 | 0.764 | 0.658 | 2.349 | 0.717 | 468.7 |

## Reading

- `safe%` = passed the SELECT-only AST guard. 100% means all generations were syntactically read-only SQL.
- Use these for "the model produces plausible-looking SQL on a held-out enterprise benchmark", not "the model is X% accurate on Spider2-Lite".
- Comparison between B0 and B3_v4 here tells you whether retrieval changes SQL shape (e.g. fewer joins because retrieved schema is smaller).
