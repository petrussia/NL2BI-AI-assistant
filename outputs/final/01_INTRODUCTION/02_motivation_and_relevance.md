# 1.2 Мотивация и актуальность

## 1.2.1 Индустриальный контекст: «BI задаёт SQL»

Самый частотный класс data-engineering задач в современных компаниях — это **ad-hoc business intelligence queries**: сотрудник marketing / product / finance / operations задаёт data-аналитику вопрос вида «какова конверсия по канонам за последние 12 месяцев в разрезе платных vs органических» — и ждёт CSV-результат за день-два. По публичным оценкам Pinterest (Pinterest Tech Blog, 2024), на одной только их платформе обрабатывается порядка **миллионов BI-запросов в неделю**, причём подавляющее большинство — повторные вариации одних и тех же 20-30 шаблонов запросов с разными фильтрами.

Это создаёт классическое **bottleneck**: аналитик становится reactive-узлом, через который проходит каждое business-решение. Сокращение latency «вопрос → ответ» в 10× меняет операционную скорость компании. Именно поэтому крупные tech-компании в 2024–2026 годах инвестируют в **internal NL2BI tools**:

| Компания | Продукт / инициатива | Источник |
|---|---|---|
| Pinterest | QueryGPT — NL2SQL для warehouse | Pinterest Tech Blog (2024); упоминается в research dossier |
| Uber | Internal NL2SQL agent | Uber blog post (2024) |
| Snowflake | Cortex Analyst — fully managed NL2SQL над Snowflake данными | Snowflake docs (2024-2025) |
| Microsoft | Copilot for Power BI | Microsoft docs (2024) |
| Google | Vertex AI Conversational Analytics | Google Cloud blog (2024) |

Однако все эти системы либо закрытые (Snowflake Cortex, Microsoft Copilot, Vertex AI), либо построены на закрытых LLM (Pinterest QueryGPT использует GPT-4 классом моделей внутри). Их недостатки очевидны:

1. **Privacy / data residency**: данные warehouse уходят на серверы провайдера LLM.
2. **Cost**: per-query стоимость в production масштабах накапливается.
3. **Vendor lock-in**: API могут меняться, deprecate-ить модели, повышать цены.
4. **Reproducibility for science**: исследовательски невоспроизводимы — закрытая модель сегодня и через год могут быть совершенно разными артефактами.

Поэтому открытый рыночный вопрос: **насколько хорош лучший open-weight стэк ≤30B параметров на realistic enterprise NL2BI бенчмарках, если scaffolding (схема-линкер, валидатор, dialect post-processor) сделан качественно?** Если результат окажется в зоне «можно ставить в production самостоятельно» — это создаёт альтернативу всему вышеперечисленному. Если нет — мы количественно показываем gap и обозначаем, что именно scaffolding не решает (и тогда мы знаем, какую возможность модели нужно ждать).

## 1.2.2 Технический контекст: переход от Spider 1.0 к Spider 2.0 family

Литература по NL2SQL после 2023 года столкнулась с тем, что Spider 1.0 — исторический «золотой стандарт» — был **в значительной степени решён** LLM-based системами. Текущие top entries на Spider 1.0 leaderboard демонстрируют 89-94% execution accuracy. Многие из них используют closed API.

Однако Spider 1.0 — синтетический бенчмарк: 200 однотипных университетских и demo-баз, все таблицы хорошо нормализованы, все колонки имеют осмысленные имена. **В реальной enterprise warehouse-схеме ничего из этого не гарантируется.** Это обнажилось при появлении **Spider 2.0 family** (Lei et al., 2025), состоящей из четырёх sub-benchmarks:

- **Spider2-Lite** (547 задач, разделённых между BigQuery, Snowflake и SQLite lanes) — single-shot SQL над live cloud-warehouse,
- **Spider2-Snow** (547 задач, чистый Snowflake) — расширение Lite-Snow с полным разнообразием Spider 2.0 databases,
- **Spider2-DBT** (~93 задачи) — multi-file edits в DBT-проекте с DuckDB-execution,
- **Spider2 (default)** — full agent setting, требующая навигации по файлам, выполнения SQL, использования tools.

На момент написания (май 2026) Spider 2.0 — **самый сложный публично доступный NL2BI бенчмарк**, и SOTA на нём — далеко не «решена»:

| Бенчмарк | Текущий SOTA (closed/large) | Текущий best open-weight ≤30B | Источник |
|---|---|---|---|
| Spider2-Snow | ReFoRCE + o3 ≈ 62.89% EX | Spider-Agent + Qwen3-Coder ≈ 31.08% EX | research dossier из Phase 27 strategy doc |
| Spider2-Lite (BQ) | ReFoRCE-class ≈ 50-60% | Spider-Agent + Coder-32B class ≈ 30-35% | research dossier |
| Spider2-DBT | Spider-Agent ≈ 13.2% (полный agent setting) | Аналогично ≈ 13.2% | xlang-ai/Spider2 baseline |

Видно, что **gap между closed-API top-tier и open-weight ≤30B составляет 2× по EX на Snow lane**. Это значит, что закрыть его — нетривиальный исследовательский вызов: либо нужна сильно более мощная open-weight модель (что вне нашего контроля), либо нужно качественно лучше scaffolding-ить уже доступные модели.

## 1.2.3 Гипотеза работы: scaffolding > model scale (в рамках доступной размерности)

Главная рабочая гипотеза, которая ведёт диссертацию:

> **При фиксированном open-weight стэке моделей ≤30B параметров большая часть оставшегося gap-а до closed-API SOTA на Spider2-Snow закрывается не дальнейшим увеличением модели, а целевыми интервенциями в scaffolding: точная live-catalog схема-линкер, three-part identifier grounding, dialect-specific post-processing над выводом эмиттера, и self-refine loop поверх engine-error feedback.**

Эта гипотеза не очевидна, потому что в литературе (DAIL-SQL, CHESS, DTS-SQL, MAC-SQL) часто проводится противоположная парадигма: «больше модель = лучше результат», и большинство paper-овых результатов получены с GPT-4-class API. На Spider 1.0 это работало — но Spider 2.0 family — другой режим: схемы настолько большие, что **error не в способности модели рассуждать, а в том, что нужная таблица не попала в pack**, или **нужная колонка имена которой модель не знает**, или **выход модели — синтаксически верный SQL, который не выполняется из-за dialect-specific quirk**. Все эти три категории — scaffolding-уровневые, не model-уровневые.

Серия наших Phase-экспериментов (см. полностью [06_EXPERIMENTAL_PROGRESSION/](../06_EXPERIMENTAL_PROGRESSION/)) — последовательное эмпирическое тестирование этой гипотезы:
- Phase 17 показал, что **family > scale** в выборе моделей (Coder-family превосходит Mistral и Llama при equal или larger size).
- Phase 18-22 показали, что **schema-first ranking + closed-set planning** двигают EX больше, чем смена модели.
- Phase 23 показал, что **concurrent inference на A100-80GB ведёт к OOM** — orchestration matter.
- Phase 24 показал, что **engine-compat rewrites** (BQ-only) метрически нейтральны без правильного error feedback.
- Phase 27 (F1) показал, что **catalog identifier grounding** через AST guard + three-part name rendering — это то, что отделяет 0% от 10% на Snow lane.
- Phase 28 (F4) показал, что **post-processor для NUMBER/VARIANT → DATE cast** разблокирует F4 wraps, которые «лежали без работы» из-за F2a regression. Это пример **layered interventions** в scaffolding.

## 1.2.4 Социальный и научный смысл

С прикладной точки зрения, конечный результат работы — артефакт, состоящий из:

1. Открытого кода всей pipeline (`repo/src/evaluation/`),
2. Воспроизводимых результатов на четырёх Spider2 sub-benchmarks,
3. Набора верифицированных интервенций и их измеренного contribution,
4. Документированных failure mode-ов с конкретными примерами SQL и error message-ами.

С научной точки зрения — это **методологический вклад в NL2SQL-литературу**:

- Систематический ablation pattern «pilot10 → pilot50 → FULL» для предотвращения нелетающего compute waste.
- Catalog probe finding: гипотезы о dialect failure нужно проверять данными catalog, а не парсингом error message (Phase 28 §6 — empirical falsification).
- Per-task BM25 partitioning vs global global ranking: показано на 587K-колонок catalog-е, что 200/40 retrieval window недостаточен, а partitioning делает 200/40 достаточным.

С образовательной точки зрения, эта работа — пример **«долгого эксперимента»**: 28 phase reports, каждый с своими гипотезами, falsifying tests, и выводами. Это редкая в курсовых/дипломных работах структура — обычно встречается формат «попробовали 1-2 идеи, замерили, написали». Здесь же показан процесс реального исследования, включая 2 ложных гипотезы (Phase 22 «join-aware Family C решит проблему», Phase 28 «mixed-case quoting объясняет invalid_identifier»), которые были эмпирически опровергнуты.

## 1.2.5 Текущая обстановка на leaderboard-ах (май 2026)

Согласно research dossier (полная таблица в [09_RESULTS_ANALYSIS/05_leaderboard_position.md](../09_RESULTS_ANALYSIS/05_leaderboard_position.md)):

```
Spider2-Snow leaderboard (xlang-ai/Spider2, fetched May 2026):
  1. ReFoRCE + o3            62.89%   (closed, OpenAI o3)
  2. ReFoRCE + Claude-3.5    19.34%   (closed)
  3. Spider-Agent + Qwen3-Coder 31.08% (open-weight top)
  ...
  Our v28-revert-A pilot10:  4/10 = 40% EXPLAIN-pass (*) (pilot10 не сравнима с FULL leaderboard)
  Our v28-revert-A FULL 547: 130/547 = 23.76% Snowflake EXPLAIN-pass (*) — plan-level acceptance, row-match audit deferred to Phase 28b
                             (cross-metric vs leaderboard row-match — see 11_APPENDIX/07_critical_metric_caveat.md)
```

Спираль наблюдений:
- Spider2-Snow leaderboard в зоне «реальный challenge». Closed-API top-tier при ReFoRCE + o3 даёт 62%, у нас же 4× более маленькая модель (3B активных параметров MoE vs закрытая trillion-class модель). Если scaffolding-only оптимизация довела нас, скажем, до 20-25%, это значит **3× compression в параметрах по сравнению с closed top** при той же task scope.
- Spider2-DBT — единственный lane, где общий ceiling ≈ 13.2%, и open и closed одинаково плохи. Это говорит про **гэп в edit-formats** (отдельная Phase 31 territory).

## 1.2.6 Что эта работа НЕ обещает

Чтобы предотвратить overselling, явно фиксируем что НЕ заявляется:

- **Не достижение SOTA на Spider2 family** в абсолютном выражении. Closed-API top-tier остаётся вне досягаемости open-weight ≤30B стэка.
- **Не production-ready system**. Даже наш best result имеет 75-80% запросов, которые не выполняются — это не товар для конечного пользователя.
- **Не universal NL2BI agent**. Все интервенции откалиброваны под Spider2 family и могут не переноситься на принципиально другие бизнес-сценарии (financial reporting с regulatory constraints, healthcare с HIPAA, etc.).

Что заявляется — см. [04_thesis_contributions.md](./04_thesis_contributions.md).

---

## Ссылки на источники для этого раздела

| Утверждение | Источник |
|---|---|
| Pinterest QueryGPT, ~миллионы BI-запросов в неделю | Pinterest Tech Blog (2024) — research dossier |
| Snowflake Cortex Analyst | Snowflake docs (2024-2025) |
| Spider2-Snow top entries ReFoRCE+o3 и Spider-Agent+Qwen3-Coder | research dossier из Phase 27 strategy, leaderboard fetch May 2026 |
| Spider2-DBT 13.2% baseline | xlang-ai/Spider2 README + наш Phase 11 reproduction |
| 587K columns в Spider2-Snow catalog | замер в `tools/remote_scripts/_phase27_step1_diagnostic.py` |
| Phase 17 «family > scale» | `outputs/REPORT_PHASE17_*.md` (сводка в `memory/spider2_phase17_findings.md`) |
| Phase 28 catalog probe finding | `outputs/REPORT_PHASE28_F2A_F4_DIALECT.md` §6 |

---

## Что дальше

→ [03_research_questions.md](./03_research_questions.md) — три research questions, разъединяющие гипотезу на проверяемые claims
→ [02_RELATED_WORK/02_sota_systems_2024_2026.md](../02_RELATED_WORK/02_sota_systems_2024_2026.md) — детальный обзор current SOTA
