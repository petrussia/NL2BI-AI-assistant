# NL2SQL на open-weight моделях — исследовательская ветка ВКР

Ветка `experiments/denis` — моя часть парного дипломного проекта NL2BI: NL2SQL-ядро и эксперименты (schema linking → planner → кандидаты → selector → dialect handlers) на Spider 1.0, BIRD и Spider 2.0. Интеграционная BI-часть проекта — в `main`.

Сводка всех фаз с метриками и 95% доверительными интервалами: [RESEARCH_SUMMARY_FINAL.md](RESEARCH_SUMMARY_FINAL.md).

| Бенчмарк (FULL), EX | Бейзлайн B0 | Лучший в исследовании (B6_v7, Qwen2.5-Coder-7B) |
|---|---:|---:|
| Spider 1.0 dev (1034) | 72.5% | **76.8%** [74.1, 79.3] |
| BIRD Mini-Dev (500) | 20.4% | **38.8%** [34.6, 43.1] |

Spider 2.0, фаза 18 — schema-first планирование по закрытому словарю схемы (live-каталог → JSON-план → детерминированный рендер SQL → валидация и dry-run): [outputs/REPORT_SPIDER2_V18.md](outputs/REPORT_SPIDER2_V18.md).

---

<details>
<summary>Служебное: раннер Colab-ноутбуков (исходный README ветки)</summary>

# VS Code Colab Notebook Runner

Windows runner for executing VS Code/Colab notebook cells from an agent. The
target notebook must already be the only active notebook editor; normal README
or script tabs can stay open.

Choose documentation language:

- [Русский](docs/README.ru.md)
- [English](docs/README.en.md)

</details>
