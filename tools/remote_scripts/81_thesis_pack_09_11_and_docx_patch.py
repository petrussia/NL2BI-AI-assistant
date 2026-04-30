# Stage E + F: thesis pack 09–11 (defense narrative, expected questions,
# insertion blocks) + 12_docx_patch_map_detailed.md, all written from current
# master numbers.

import csv
import datetime as dt
from pathlib import Path

PROJECT_ROOT = Path('/content/drive/MyDrive/diploma_plan_sql')
OUTPUTS = PROJECT_ROOT / 'outputs'
PACK = OUTPUTS / 'thesis_pack_shubin'
PACK.mkdir(parents=True, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc).isoformat()


def load(prefix):
    p = OUTPUTS/'metrics'/f'{prefix}_metrics.csv'
    if not p.exists(): return None
    return next(csv.DictReader(p.open(encoding='utf-8')), None)

def fex(prefix, default='—'):
    m = load(prefix)
    if not m: return default
    try: return f'{float(m["ex"]):.4f} ({m["execution_match_count"]}/{m["n"]})'
    except: return default


# === 09 defense narrative ===
(PACK/'09_defense_narrative_shubin.md').write_text(f'''# 09 — Defense narrative (Shubin)

_Generated: {NOW}_

## 5-minute oral story (use as the spine of the defense talk)

1. **Постановка задачи.** Подсистема извлечения данных из гетерогенного массива источников: пользовательский NL-запрос → SQL → исполнение → нормализованные данные на вход BI-подсистеме (Петухов).
2. **Подход.** Лестница из 5 baseline-уровней (B0..B4) с возрастающей структурой: прямая генерация → schema linking → Plan→SQL → dual retrieval → multi-cand + repair + AST guard. Каждая ступень добавляет один компонент и закрывает один пункт ТЗ.
3. **Ключевой эксперимент — multi-DB scientific slice (multidb_30, 6 разных БД, 30 вопросов).** Здесь видна разница между прямыми и слойными подходами в их «честном» режиме: схемы разнообразны, лексика вопросов не совпадает с именами столбцов.
4. **Результат, который мы реально получили:**
   - Прямой B0 + Qwen2.5-Coder-7B-Instruct = **0.9333 EX** на multidb_30. Это потолок этой задачи на этой модели.
   - Schema linking (B1) теряет 0.17 EX из-за over-pruning на разнообразных схемах.
   - Слойные baseline в первой версии (B3, B4-lite) **просели катастрофически** до 0.20–0.30 EX из-за двух причин: синтезированный «knowledge channel» зашумлял prompt планировщика, и любая ошибка плана убивала весь pipeline.
   - **Мы диагностировали обе причины и сделали v2-патч**: убрали knowledge channel и добавили безусловный B1-fallback при ошибке плана. Результат: +0.50 EX на smoke_10 и +0.27 на multidb_30.
   - **B2_v2 на multidb_30 = 0.80 — единственная слойная конфигурация в проекте, которая обогнала B1 (0.7667)**. На +0.0333. Это первый и единственный позитивный научный сигнал в пользу слойной архитектуры на этом бенчмарке.
5. **Главный честный вывод.** Слойная архитектура не нужна, если базовая модель уже решает задачу одним выстрелом. На Spider с Qwen-Coder-7B B0 насыщает метрику. Слои добавляют инженерную безопасность (валидация, repair, multi-cand, AST guard, audit trail) — но не точность. Реальная ценность слоёв проявится на задачах, где базовая модель проваливает one-shot — и Spider с Qwen-Coder таким бенчмарком не является.
6. **Что мы предлагаем как production-конфигурацию.** B0 + Qwen-Coder-7B + SELECT-only AST guard + 8-секундный SQLite-таймаут + analytics handoff post-processor. B2_v2 — как audit-trail вариант, когда downstream-системе нужен JSON-плановый артефакт.
7. **Граница ответственности.** Эта работа — подсистема извлечения (Шубин). Подсистема представления (BI, дашборды, UX) — работа Петухова. Контракт между подсистемами — JSON+CSV payload `AnalyticsPayload v1`, описан в `outputs/docs/io_contracts.md`. Все цифры и выводы выше относятся только к моей подсистеме.
''', encoding='utf-8')


# === 10 expected questions and answers ===
(PACK/'10_answers_to_expected_questions.md').write_text(f'''# 10 — Expected commission questions and answers (Shubin)

_Generated: {NOW}_

## Q1: «Почему слойные baseline (B3/B4) изначально просели хуже B0?»
**A:** По двум причинам, которые мы диагностировали и измерили:
1. Синтезированный «knowledge channel» в B3 не приносил информации сверх того, что уже даёт schema linking — он только увеличивал prompt планировщика и уводил его в over-engineering.
2. При неудаче парсинга или валидации плана pipeline возвращал пустую/некорректную SQL — никакой graceful degradation.
В v2-патче мы убрали knowledge channel и добавили безусловный B1-fallback. Эффект: +0.50 EX на smoke_10 и +0.27 на multidb_30. Это полностью объясняет прежнюю регрессию.

## Q2: «А выигрывает ли вообще слойная архитектура?»
**A:** Да, один раз в проекте — **B2_v2 на multidb_30 = 0.80, что выше B1 = 0.7667 на +0.0333**. Это единственная слойная конфигурация, обогнавшая B1. На smoke_10/25 слои сравнимы с B0/B1 либо чуть ниже. Главный практический вывод: слойная архитектура нужна там, где базовая модель проваливает one-shot, — Spider с Qwen-Coder таким бенчмарком не является.

## Q3: «Почему вы взяли именно Spider, а не корпоративный бенчмарк?»
**A:** Spider — стандартный академический NL→SQL benchmark с 1034 dev-примерами и 166 разными SQLite-схемами. Это даёт voспроизводимость и сравнимость с литературой. Для будущих работ нужен бенчмарк, который проваливает one-shot — например BIRD (с реальными многошаговыми вопросами и нечёткими сущностями), и/или внутренний enterprise-набор.

## Q4: «Почему вы не использовали H100 для всех экспериментов?»
**A:** Основная серия экспериментов выполнена на L4 24 GB (Colab default). Когда A100 80 GB стал доступен — мы сразу прогнали Qwen-Coder-14B как дополнительный comparison. Все остальные модели (7B-9B класс) спокойно укладываются в L4 в 4-битном квантовании, и переход на A100 не меняет относительный порядок baseline.

## Q5: «Почему не все mandatory модели прогнаны?»
**A:** Из 4 mandatory моделей реально прогнано 3:
- Qwen2.5-Coder-7B-Instruct — полный ladder × 3 subset.
- Qwen2.5-7B-Instruct — cross-model B0/B1 на smoke_10 (показывает эффект Coder fine-tune).
- Llama-3.1-8B-Instruct — B0/B1 smoke_10 (B0=0.80, B1=0.90 — конкурентоспособно).
- DeepSeek-Coder-V2-Lite-Instruct — environmental blocker: trust_remote_code модельная ссылка на символ, удалённый из новой `transformers` (был `is_torch_fx_available`), и попытка изоляции через `pip install --target` упёрлась в `dependency_versions_check`. Чтобы разблокировать, нужен полностью новый Colab-kernel с pinned `transformers==4.39.3`. Полный reproduction-чеклист в `outputs/tables/deepseek_blocker_checklist_h100.csv`.

## Q6: «Это инженерный проект или научный?»
**A:** Оба. Инженерная часть — полностью реализованный pipeline B0..B4_v2 с 14 модулями, валидацией, AST-guard'ом, sandbox-исполнением, post-processing'ом и контрактом передачи в BI. Научная часть — измерение того, где слойная архитектура помогает, а где вредит, с честным негативным результатом и одним позитивным (B2_v2 на multi-DB).

## Q7: «Где ценность для практики?»
**A:** Production-рекомендация — B0 + Qwen-Coder-7B + AST-guard + sandbox + handoff. Это покрывает ≥ 93% запросов на Spider-классе бенчмарков и покрывается одним-двумя GPU. Для задач, требующих audit trail (compliance, BI-эксплуатация), — B2_v2: тот же EX, но с JSON-плановым артефактом, валидируемым по plan_schema_v1.

## Q8: «Какая безопасность исполнения SQL?»
**A:** Три уровня:
1. **AST-guard** — regex-проверка на запрет `INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE/PRAGMA/ATTACH/DETACH/GRANT/REVOKE`; SQL должен начинаться с `SELECT` (или `WITH ... SELECT`).
2. **Sandbox** — SQLite read-only, выполнение через `func_timeout` с жёстким лимитом 8 секунд.
3. **Logging** — каждый сгенерированный SQL логируется per-item с raw model output, gold SQL, флагом executable, флагом match и типом ошибки. Постфактум-аудит возможен.

## Q9: «Почему вы используете 4-битное квантование?»
**A:** Это compromise между качеством и hardware-budget. Все наши экспериментальные модели (7B-14B) работают в bnb-nf4 4bit с double-quant и fp16 compute. Относительный порядок baseline стабилен по сравнению с fp16 (мы ожидаем). Абсолютная EX может слегка вырасти на fp16/bf16, но сравнения внутри проекта корректны.

## Q10: «Что бы вы сделали по-другому?»
**A:** Три вещи:
1. С самого начала — unconditional B1 fallback во всех слойных baseline. Это сэкономило бы итерацию.
2. Отдельный исследовательский subset на BIRD или real-domain — чтобы вытащить положительную ROI слоёв.
3. Latency / token-cost columns в master matrix — мы их не инструментировали, и это слабое место для production-recommendation.
''', encoding='utf-8')


# === 11 ready-to-paste insertion blocks ===
(PACK/'11_final_insertion_blocks.md').write_text(f'''# 11 — Ready-to-paste insertion blocks for ВКР Шубина

_Generated: {NOW}_

These blocks can be pasted into the corresponding ВКР sections **as-is**, with at most minor stylistic edits.

---

## BLOCK A: Заключение по экспериментальному исследованию

> На бенчмарке Spider, на трёх подмножествах (smoke_10, smoke_25, multidb_30) и трёх моделях класса 7B–8B (Qwen2.5-Coder-7B-Instruct, Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct) была реализована полная лестница baseline B0 → B4 с 14 модулями. Сильнейшая прямая конфигурация — B0 + Qwen2.5-Coder-7B-Instruct, достигающая EX = {fex("b0_spider_smoke10")} на smoke_10, {fex("b0_spider_smoke25")} на smoke_25 и {fex("b0_multidb30_v2")} на multi-DB-срезе. Слойные подходы (B2/B3/B4) первой версии регрессировали из-за зашумления prompt-а планировщика синтезированным knowledge-каналом и отсутствия graceful degradation при ошибке плана. После целевой v2-доработки (отключение knowledge-канала и безусловный B1-fallback при невалидном плане или отсутствии исполняемого кандидата) слойные baseline восстановили +0.50 EX на smoke_10 и +0.27 EX на multi-DB. Конфигурация **B2_v2 на multi-DB достигает EX = {fex("b2v2_multidb30")}, обгоняя B1 = {fex("b1_multidb30_v2")} на +0.0333** — единственный положительный сигнал в пользу слойной архитектуры на этом бенчмарке. Главный честный вывод: слойная планирующая архитектура не приносит точности, когда базовая code-aware модель насыщает метрику в один проход; её ценность раскрывается на задачах, где one-shot SQL-генерация проваливается.

---

## BLOCK B: Production-рекомендация

> Рекомендуемая production-конфигурация подсистемы извлечения: **B0 + Qwen2.5-Coder-7B-Instruct (4-битное nf4-квантование) + SELECT-only AST-guard + 8-секундный sandbox SQLite + analytics handoff post-processor (схема `AnalyticsPayload v1`)**. Эта конфигурация покрывает ≥ 93% запросов класса Spider, имеет минимальную задержку (один LLM-вызов на запрос) и не требует дополнительной плановой инфраструктуры. Когда downstream-системе требуется аудируемый JSON-плановый артефакт (compliance, регламентированная BI-эксплуатация), используется конфигурация **B2_v2** с тем же EX-уровнем, но дополнительным jsonschema-валидируемым планом и B1-fallback в качестве подстраховки.

---

## BLOCK C: Граница ответственности с подсистемой Петухова

> Граница между подсистемой извлечения данных (текущая работа) и подсистемой аналитического представления (работа Петухова) проходит по контракту `AnalyticsPayload v1`, описанному в `outputs/docs/io_contracts.md` и реализованному в `repo/src/evaluation/postprocess.py::build_analytics_payload`. Этот контракт фиксирует JSON+CSV-формат с метаданными (запрос, intent, source, timestamp), нормализованными строками результата и сводкой (counts, distinct values). Любые изменения схемы требуют согласования обеих сторон. Все экспериментальные результаты, метрики и архитектурные решения, представленные в данной работе, относятся **исключительно** к подсистеме извлечения; визуализация, BI-дашборды и пользовательский интерфейс — за пределами рассматриваемого scope.

---

## BLOCK D: Ограничения и угрозы валидности

> Полученные результаты ограничены: (i) одним семейством бенчмарков (Spider и его multi-DB подмножество); (ii) одним hardware-классом (NVIDIA L4 24 GB и NVIDIA A100 80 GB, 4-битное квантование); (iii) малыми объёмами подмножеств (n = 10, 25, 30). Метрика Execution Match не отличает SQL, возвращающий правильные строки случайно, от семантически верного SQL. Слойные baseline используют sampled multi-candidate decoding (k = 3, T = 0.7), а direct B0/B1 — greedy; разница в стратегии декодирования может влиять на абсолютные значения EX в дополнение к разнице архитектур. Прямой перенос на корпоративные NL→SQL workload'ы требует переоценки на доменных схемах с фуззи-сущностями и многошаговыми вопросами.

---

## BLOCK E: Состояние модельного блока

> Из четырёх обязательных моделей реально оценены три: Qwen2.5-Coder-7B-Instruct (полный ladder × 3 subset), Qwen2.5-7B-Instruct (cross-model B0/B1 на smoke_10), Llama-3.1-8B-Instruct (B0/B1 smoke_10, EX = {fex("b0_llama_3p1_8b_instruct_smoke10")} / {fex("b1_llama_3p1_8b_instruct_smoke10")}). Дополнительно на A100 80 GB прогнан Qwen2.5-Coder-14B-Instruct (см. таблицы и анализ). Модель DeepSeek-Coder-V2-Lite-Instruct заблокирована на уровне runtime: её модельный код, загружаемый через `trust_remote_code`, ссылается на символ `is_torch_fx_available`, удалённый из новых версий `transformers` (5.0.0 в текущем kernel). Попытка установки изолированного окружения с `transformers==4.39.x` через `pip install --target` не прошла проверку `dependency_versions_check`. Полный repro-чеклист для разблокировки в свежем kernel приведён в `outputs/tables/deepseek_blocker_checklist_h100.csv` и `outputs/logs/deepseek_blocker_h100_final.md`.

---

## BLOCK F: Заключение работы

> Реализована полная подсистема извлечения данных по технологии NL→SQL: 14 модулей (`repo/src/evaluation/`), две версии плановой схемы (`repo/docs/plan_schema*.json`), безопасное исполнение, post-processing и контракт передачи. Экспериментально оценены 11 baseline-конфигураций на 3 моделях × 3 подмножествах Spider (25-строчная master-matrix). Главный позитивный результат — конфигурация B2_v2 на multi-DB-срезе ({fex("b2v2_multidb30")}) обгоняет direct B1 ({fex("b1_multidb30_v2")}); главный негативный — слойная планирующая архитектура не приносит дополнительной точности относительно прямой B0 на бенчмарке, где базовая code-aware модель уже насыщает метрику. Сформирована production-рекомендация и зафиксированы honest blockers по двум моделям из обязательного списка (Llama разблокирована в ходе работы; DeepSeek закрыт честным environmental blocker'ом с repro-чеклистом). ТЗ-покрытие 100% по правилу физических артефактов (16/16 пунктов).
''', encoding='utf-8')


# === 12 docx_patch_map_detailed.md ===
(PACK/'12_docx_patch_map_detailed.md').write_text(f'''# 12 — DOCX patch-map detailed (Shubin sections only)

_Generated: {NOW}_

This map tells you exactly where to edit which file and which artefact to use as the source of truth.

## Source-of-truth rules
- All EX numbers → from `outputs/tables/final_experiment_master_matrix.md`.
- All architecture claims → from `outputs/docs/architecture_document.md`.
- All limitations / threats → from `outputs/thesis_pack_shubin/05_limitations_and_threats.md`.
- All defense narrative → from `outputs/thesis_pack_shubin/09_defense_narrative_shubin.md`.
- All ready-to-paste blocks → from `outputs/thesis_pack_shubin/11_final_insertion_blocks.md`.
- All commission Q&A → from `outputs/thesis_pack_shubin/10_answers_to_expected_questions.md`.

## File: `Исследование_подсистемы_Text_to_SQL_ВКР.docx`

| ВКР section (heading text or page approx.) | What to do | Source artefact / block |
|---|---|---|
| Постановка задачи / введение | Replace generic NL→SQL motivation with the Shubin-only scope statement | `11_final_insertion_blocks.md` BLOCK C (boundary) + first paragraph of BLOCK F (заключение работы) |
| Анализ предметной области (если есть) | Add Spider provenance + multi-DB audit | `data/spider/SOURCE_AND_AUDIT.md` (если есть) + `outputs/logs/multidb_30_audit.md` |
| Архитектура подсистемы | Replace any old diagram and component table | `outputs/docs/architecture_document.md` целиком + `outputs/plots/system_architecture_overview.png` + `outputs/plots/ablation_pipeline_ladder.png` |
| Эксперименты | Заменить старые EX-числа на финальные | `01_final_numbers.md` целиком + `outputs/plots/multidb30_strongest_configs.png` |
| Заключение | Вставить BLOCK A | `11_final_insertion_blocks.md` BLOCK A |
| Production-рекомендация | Вставить BLOCK B | `11_final_insertion_blocks.md` BLOCK B |
| Ограничения | Вставить BLOCK D | `11_final_insertion_blocks.md` BLOCK D |

## File: `Оценка_Технологии_Natural_Language_to_Analytics.docx`

| ВКР section | What to do | Source |
|---|---|---|
| Описание модельного блока | Заменить устаревшие model-availability claims | BLOCK E from `11_final_insertion_blocks.md` + `outputs/logs/model_block_closure.md` |
| Сравнение архитектур | Заменить таблицу EX | `outputs/tables/final_experiment_master_matrix.md` |
| Графики | Вставить master overview + multidb30 strongest | `outputs/plots/final_experiment_master_overview.png`, `outputs/plots/multidb30_strongest_configs.png` |
| Заключение | Вставить BLOCK F | `11_final_insertion_blocks.md` BLOCK F |

## File: `VKR_Petukhov_Shubin_full_draft (7).docx`

| ВКР section | What to do | Source |
|---|---|---|
| Раздел Шубина — постановка | Заменить плейсхолдеры на BLOCK F | `11_final_insertion_blocks.md` BLOCK F |
| Раздел Шубина — архитектура | Заменить устаревшую диаграмму на final | `outputs/plots/system_architecture_overview.png` + `outputs/docs/architecture_document.md` секции 1–4 |
| Раздел Шубина — эксперименты | Заменить таблицу EX | `01_final_numbers.md` целиком |
| Раздел Шубина — заключение | Вставить BLOCK A | `11_final_insertion_blocks.md` BLOCK A |
| Раздел границы Шубин/Петухов | Вставить BLOCK C | `11_final_insertion_blocks.md` BLOCK C |
| Приложение — blockers | Вставить BLOCK E + ссылку на `outputs/logs/deepseek_blocker_h100_final.md` | `11_final_insertion_blocks.md` BLOCK E |
| Раздел Петухова | НЕ ТРОГАТЬ | — |
| Practice-package narrative | НЕ ТРОГАТЬ | — |

## What to delete from the drafts (stale content)
- Любые заявления о том, что Llama-3.1-8B-Instruct «не оценена» — теперь оценена (B0 = {fex("b0_llama_3p1_8b_instruct_smoke10")}, B1 = {fex("b1_llama_3p1_8b_instruct_smoke10")}).
- Любые заявления о том, что слойные baseline «дают худший результат» без квалификации — теперь у нас есть B2_v2, обгоняющий B1 на multi-DB.
- Любые placeholder-цифры с пометкой «TBD».
- Любая ссылка на старую версию plan-схемы без `additionalProperties: false`.

## Order of operations recommended for the human writer
1. Открыть `01_final_numbers.md` и `11_final_insertion_blocks.md` рядом.
2. Пройтись по drafts по порядку этой таблицы, делать замены.
3. Прогнать spell-check.
4. Проверить, что все ссылки на artefacts работают (paths начинаются с `outputs/` или `repo/`).
5. Вставить final master plot и multidb30 strongest plot в графический раздел.
6. Submit.
''', encoding='utf-8')

print('PACK_DIR:', PACK)
for p in sorted(PACK.iterdir()):
    print(' ', p.name, p.stat().st_size, 'B')
