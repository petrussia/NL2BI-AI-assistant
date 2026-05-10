# Prompt 06 — Codex: frontend chat artifacts

Ты работаешь в `petrussia/NL2BI-AI-assistant` на ветке `integration/server-colab-nl2chart-mvp`.

## Цель

Подключить chat UI к server `POST /api/nl2chart` и научить чат показывать результат: таблицу, график/spec/image, warnings/errors.

Server-runtime — dev+prod. Colab используется только сервером через `/api/nl2chart`; frontend не должен ходить в Colab напрямую.

## Жёсткие ограничения

1. Frontend не вызывает Colab URL напрямую.
2. Frontend вызывает только server API.
3. Не показывать пользователю raw SQL по умолчанию.
4. Debug SQL можно показывать только в technical mode.
5. Не показывать raw stack traces.
6. При Colab unavailable показывать понятную ошибку.

## Реализовать

### Chat flow

When user sends message:

```text
POST /api/chats/{session_id}/messages
```

Backend may call `/api/nl2chart` internally, or frontend can call `/api/nl2chart` depending on current architecture. Prefer backend orchestrated chat flow if existing chat persistence is ready.

Assistant message should include artifacts:

```json
{
  "role": "assistant",
  "content": "Построил график по вашему запросу.",
  "artifacts": [
    {
      "artifact_type": "chart_spec",
      "title": "Выручка по месяцам",
      "payload": {"spec": {}, "request_id": "..."}
    }
  ]
}
```

### Artifact types

Support:

- `table`;
- `chart_spec`;
- `chart_image`;
- `warning`;
- `error`;
- `debug_sql` only in technical mode.

### UI states

- loading: «Обрабатываю запрос…»;
- extraction running: «Получаю данные…»;
- visualization running: «Строю визуализацию…»;
- Colab unavailable: «Модель извлечения данных временно недоступна. Можно попробовать mock/demo режим.»;
- empty result: «Запрос выполнен, но данные не найдены.»;
- metadata incomplete: show non-blocking warning.

### Rendering

For MVP:

- table artifact: render HTML table with max rows;
- chart_spec artifact: render simple Vega-Lite if existing dependency is available, otherwise show JSON/spec card and image if available;
- chart_image: render image;
- error/warning: render cards.

Do not add huge frontend dependencies unless needed. Keep implementation minimal and stable.

## Tests/checks

If frontend tests exist, add/update them. Otherwise add manual smoke checklist.

Run:

```bash
npm run build
curl -X POST http://127.0.0.1:8100/api/nl2chart \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"Покажи топ категорий по продажам","data_source_id":"demo_sales"}'
```

Manual UI scenarios:

1. mock time series -> chart artifact visible;
2. mock category -> chart/table artifact visible;
3. empty result -> safe message;
4. Colab unavailable -> safe error;
5. technical mode -> debug SQL visible, business mode -> hidden.

## Acceptance criteria

- Chat can display artifact from `/api/nl2chart`.
- Frontend never calls Colab directly.
- User-safe errors visible.
- Warnings visible but not blocking.
- Build passes or failures are documented.
- Existing login/chat flow not broken.

## Итоговый отчёт

Output:

1. Changed files.
2. Artifact UI mapping.
3. Build/test output.
4. Example assistant message JSON.
5. Manual smoke results.
6. Screenshot instructions or screenshot path if available.
7. What to send to ChatGPT after this stage.
