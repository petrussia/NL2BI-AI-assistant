# Operations Manual — v2 (defense-final)

**Date:** 2026-04-30T14:50:05.209628+00:00
**Author:** Шубин Денис Алексеевич

## 1. Inputs / outputs

**Input.** NL question (Russian or English) + db_id (Spider-style — имя БД из `tables.json`).

**Output (production):** один JSON+CSV `AnalyticsPayload v1` со схемой:

```json
{
  "metadata": {
    "query": "<NL question>",
    "db_id": "<source DB>",
    "intent": "<select_count|select_aggregate|...>",
    "generated_sql": "<final SQL>",
    "execution_time_seconds": <float>,
    "timestamp_utc": "<ISO 8601>"
  },
  "rows": [<normalized result rows>],
  "summary": {
    "row_count": <int>,
    "distinct_values": {...},
    "min_max": {...}
  }
}
```

CSV-вариант — табличная развёртка `rows` с заголовками из `metadata.columns`.

## 2. Runtime requirements

- **GPU:** NVIDIA L4 24 GB (минимум) — Qwen-Coder-7B/Llama-8B в 4-bit. A100 40+ GB — для Coder-14B.
- **Python:** 3.10+ (тестировано на 3.12.13).
- **Key deps:** `transformers>=4.45`, `bitsandbytes>=0.46.1`, `accelerate`, `func_timeout`, `jsonschema`, `sentencepiece`, `safetensors`.
- **Disk:** ~30 GB на cache моделей.
- **HF_TOKEN:** для Llama (gated repo).

## 3. Safety guard

`is_safe_select(sql)` — regex проверка:
1. SQL не пустой.
2. SQL не содержит `INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|PRAGMA|ATTACH|DETACH|GRANT|REVOKE`.
3. SQL начинается с `SELECT` (или `WITH … SELECT`).

При нарушении → SQL **не исполняется**, executable=False, error_type='unsafe:<reason>'.

## 4. Timeout policy

- Жёсткий лимит **8 секунд** на каждое исполнение SQL через `func_timeout`.
- При таймауте → error_type='timeout', returns empty rows.
- Лимит выбран эмпирически: > 99% корректных SQL на Spider укладываются в 1-2 сек; 8 сек — запас на сложные joins.

## 5. Fallback logic

| Situation | Action |
|---|---|
| Plan unparsable / fails jsonschema validation | → B1 single-shot SQL |
| All candidate SQL fail to execute | → B1 single-shot SQL |
| B1 itself fails (model error) | → record failure, return empty payload |

## 6. Что делать, если planner failed

- **Smoke test:** запустить `_peek_b3v2.py` и проверить, есть ли в логе `path=b1_fallback_invalid_plan`. Это **штатная работа safety net**, не ошибка.
- Если все 30 элементов из multidb_30 идут через fallback → planner prompt slozhilsya unstable, нужно проверить совместимость модели и шаблона chat-template.
- Если жалуется на jsonschema — проверить `repo/docs/plan_schema_v1.json` (`additionalProperties:false`).

## 7. Что делать, если schema linking over-prunes

- Проверить `outputs/predictions/*.jsonl` поле `selected_tables` — если меньше 2 таблиц, а gold SQL содержит JOIN, линкер over-pruned.
- Поднять `min_score` в `lexical_schema_linking()` (default 0.5 → 0.3) или вернуть fallback на full schema.
- Альтернатива: использовать B0 (full schema) для этого DB.

## 8. Что делать, если модель недоступна

- **Llama-3.1-8B (gated):** проверить, что `HF_TOKEN` установлен в env.
- **DeepSeek-Coder-V2-Lite:** environmental blocker, см. `outputs/logs/deepseek_blocker_final_h100.md`. Использовать fresh notebook с `transformers==4.39.3`.
- **Qwen-Coder-14B на L4:** OOM при квантизации; использовать A100 80 GB или остаться на Coder-7B (он сильнее на multi-DB).

## 9. Handoff to analytics subsystem

После исполнения SQL и postprocess'a:
1. Сохранить JSON в `outputs/analytics_handoff/<run_id>_<idx>.json`.
2. Сохранить CSV в `outputs/analytics_handoff/<run_id>_<idx>.csv`.
3. (Production) emit на message bus / API endpoint для подсистемы Петухова.
4. Контракт фиксирован в `outputs/docs/io_contracts.md` — изменения требуют двустороннего согласования.

## 10. End-to-end recipe (reproduction)

1. `python tools/exec_remote.py --health` — bridge ok?
2. `30_kernel_bootstrap.py` — bootstrap helpers + load Qwen-Coder-7B.
3. Run desired BG (e.g., `74_b2v2_smoke10_multidb30_bg.py`).
4. `_peek_b3v2.py` для polling.
5. После завершения: `65_final_consolidation_v2.py` (master matrix, plot).
6. `59_final_tarball.py` — tarball.

## 11. Honest blockers (кратко)

- **DeepSeek** — environmental, fresh-notebook unblock checklist в `outputs/tables/deepseek_blocker_reproduction_checklist.csv`.
- **Editorial polish ВКР** — human writing, ~2-3 ч.

## 12. Where things live

| Artifact | Path |
|---|---|
| Master matrix | `outputs/tables/final_experiment_master_matrix.{csv,md}` |
| Master plots | `outputs/plots/*.png` |
| REPORT | `outputs/REPORT.md` |
| Thesis pack (Shubin) | `outputs/thesis_pack_shubin/` |
| Latest tarball | `/content/drive/MyDrive/diploma_plan_sql/exports/latest_tz_closure.tar.gz` |
| Local mirror | `d:\HSE\Диплом\NL2BI-AI-assistant\` |
