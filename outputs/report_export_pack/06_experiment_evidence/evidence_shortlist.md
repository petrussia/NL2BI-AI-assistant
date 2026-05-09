# Evidence shortlist for joint report

_Generated: 2026-04-30T19:42:45.696599+00:00_

Только representative набор файлов, реально подтверждающих текст.

### `b0_qwen7b_smoke10_strongest_direct.jsonl`
_Strongest direct baseline (Qwen-Coder-7B B0 smoke_10, EX=1.0). Per-item evidence что простейший pipeline дает идеальный EX._

### `b0_qwen7b_multidb30_strongest_direct.jsonl`
_Strongest direct baseline на главном научном slice (Qwen-Coder-7B B0 multi-DB, EX=0.9333)._

### `b2v2_qwen7b_multidb30_strongest_layered.jsonl`
_Strongest layered baseline (B2_v2 multi-DB EX=0.80, побеждает B1=0.7667). Главный позитивный layered результат._

### `b0_qwen7b_bird_strongest_external.jsonl`
_Strongest external-validation result (Qwen-Coder-7B B0 BIRD, EX=0.27). Подтверждает что направление работает на harder benchmark._

### `b3_qwen7b_smoke10_negative_case.jsonl`
_Negative case: B3 smoke_10 EX=0.20 (катастрофическая регрессия v1 layered baseline до v2-фикса)._

### `b0_qwen14b_multidb_rightsizing_neg.jsonl`
_Right-sizing negative case: 14B B0 multi-DB EX=0.8667 проигрывает 7B = 0.9333._

### `analytics_payload_v1_example.json`
_Integration / contract example: AnalyticsPayload v1 — точка передачи в подсистему Петухова._

### `analytics_payload_v1_example.csv`
_CSV-вариант контракта._

### `deepseek_blocker_evidence.md`
_Honest blocker case: DeepSeek environmental ABI, документировано с repro-чеклистом._
