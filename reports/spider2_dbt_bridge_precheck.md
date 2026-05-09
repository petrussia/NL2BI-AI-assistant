# Spider2-DBT bridge — server precheck

_Generated locally; SSH passwordless to `denis@103.54.18.91` (resolves to
`petrthefirst24.fvds.ru`)._

## SSH

```
ssh -o BatchMode=yes -o ConnectTimeout=10 denis@103.54.18.91 "echo SSH_OK && whoami && hostname && pwd"
SSH_OK
denis
petrthefirst24.fvds.ru
/home/denis
```

## `./scripts/check_env.sh` (server)

- Host: `petrthefirst24.fvds.ru`, project root `/home/denis/dbt`
- Python venv: 3.11.15 + pip 26.1.1 (system python 3.12.3 also present)
- Git: 2.43.0; branch tracking `main…origin/main`
- Docker: 29.2.1 (works as `denis`); 7 containers running (gitlab, monitoring,
  amnezia VPN, etc — none related to Spider2)
- dbt-core: 1.10.8 (1.11.8 available; not required)
- dbt-duckdb: 1.10.1
- duckdb python: 1.5.2
- Spider2 repo: present at `/home/denis/dbt/vendor/Spider2`, commit `01a4c67c`
- Spider2-DBT task list: present, **task records: 67** (one less than the
  declared 68; the .jsonl has 67 lines; the 70 example dirs include
  framework boilerplate)
- `.duckdb` files: 133 across the example dirs
- API keys: **all unset** on the server (`OPENAI_API_KEY`, `AZURE_API_KEY`,
  `GEMINI_API_KEY` not exported) — exactly the regime we want.

## `./scripts/test_dbt_duckdb.sh` (server)

- `dbt debug` → all green
- `dbt run` on the smoke project → 1 model PASS, 0 errors
- DuckDB query of resulting table returns `[(1, 'duckdb-ok')]`

## Spider2-DBT layout that matters for the bridge

| Path | Notes |
|---|---|
| `vendor/Spider2/spider2-dbt/examples/spider2-dbt.jsonl` | 67 task records: `{instance_id, instruction, type}` |
| `vendor/Spider2/spider2-dbt/examples/<instance_id>/` | per-task dbt project: `dbt_project.yml`, `models/`, `profiles.yml`, `<db>.duckdb`, sometimes `dbt_packages/`, `packages.yml` |
| `vendor/Spider2/spider2-dbt/evaluation_suite/evaluate.py` | offline evaluator (compares dbt output vs gold) |
| `vendor/Spider2/spider2-dbt/evaluation_suite/gold/` | gold reference SQL/results — NEVER expose to model prompt |
| `vendor/Spider2/methods/spider-agent-dbt/run.py` | upstream agent runner; calls `PromptAgent` → `predict()` → `call_llm()` |
| `vendor/Spider2/methods/spider-agent-dbt/spider_agent/agent/models.py` | `call_llm(payload)` dispatcher: OpenAI / Azure / Gemini / Groq / dashscope by model prefix. **Not used in the bridge.** |

## Where the LLM is called and how to bypass it

- The LLM is invoked exclusively from
  `spider_agent/agent/models.py::call_llm(payload)`.
- `payload['model']` prefix decides provider (`gpt`, `azure`, `gemini`,
  `qwen`, `claude`, etc.).
- Required env vars on the server **only if** you run `run.py`:
  `OPENAI_API_KEY` / `AZURE_API_KEY` / `GEMINI_API_KEY` etc.
- The bridge architecture skips `run.py` entirely. The server side
  performs no LLM calls. Inference happens on the local/Colab side.
  Server is just dbt + DuckDB + evaluator.

## Conclusion: ready to wire the bridge

- SSH path confirmed
- dbt + DuckDB working
- 67 tasks discovered with stable `instance_id` keys
- No API keys present (and we won't put any there)
- Server ready to receive a write-only `colab_bridge/` folder under
  `/home/denis/dbt/colab_bridge/` with no impact on `vendor/Spider2`.
