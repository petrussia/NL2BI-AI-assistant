# Stage 8: large LLM JSON-validator baseline

Stage 8 запускает Hugging Face модели через тот же строгий контур, что и Stage 6/7:

- модель генерирует один компактный Vega-Lite JSON;
- validator проверяет синтаксис JSON, `mark`, `encoding`, поля схемы, типы и агрегации;
- при ошибке модель получает текст ошибки и подсказку, как исправить ответ;
- максимум три повторные попытки;
- невалидный JSON не проходит в метрики как нормальный prediction.

## Файлы

- `configs/stage8_large_llm_models.json` - список моделей, method names, квантизация и минимальная VRAM.
- `scripts/run_stage8_large_llm.py` - единый runner для одной Stage 8 модели.
- `notebooks/06_run_stage8_large_llms.ipynb` - Colab notebook с отдельной ячейкой на каждую модель.

## Модели

| key | HF model | quantization | заметка |
|---|---|---|---|
| `gemma4_e2b_it` | `google/gemma-4-E2B-it` | bitsandbytes 4-bit NF4 | маленький контрольный Stage 8 baseline |
| `qwen3_14b` | `Qwen/Qwen3-14B` | bitsandbytes 4-bit NF4 | замена Qwen3.6-35B-A3B для A100 40GB |
| `gemma3_12b_it` | `google/gemma-3-12b-it` | bitsandbytes 4-bit NF4 | замена Gemma 4 26B-A4B MTP для A100 40GB |
| `mistral_small_32_24b_bnb4` | `unsloth/Mistral-Small-3.2-24B-Instruct-2506-bnb-4bit` | pre-quantized bitsandbytes 4-bit | квантизованный Mistral Small 3.2 |

## Colab Pro+ GPU

- `qwen3_14b` и `gemma3_12b_it`: `A100 40GB` с запасом; `L4 24GB` тоже должен подойти для sample20.
- `mistral_small_32_24b_bnb4`: используй `A100 40GB`. `L4 24GB` лучше не тратить на полный прогон.
- `gemma4_e2b_it`: можно запускать на `L4 24GB`; на `A100 40GB` он быстрый, но карта избыточна.

Runner сам проверяет `min_vram_gb` перед загрузкой весов и падает раньше, чем Colab убьет runtime из-за OOM. Обойти проверку можно только через `STAGE8_ALLOW_LOW_VRAM=1`.

## Запуск через VS Code/Colab runner

Сначала открой `notebooks/06_run_stage8_large_llms.ipynb` как единственный активный notebook в VS Code и подключи нужный Colab runtime.

Setup:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\06_run_stage8_large_llms.ipynb `
  -Action cell `
  -CellId stage8-setup `
  -WaitForCellCompletion `
  -CompletionText STAGE8_SETUP_OK `
  -WaitSeconds 1800 `
  -ReloadFromDisk:$false `
  -Json
```

Проверить список моделей и текущую GPU:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\06_run_stage8_large_llms.ipynb `
  -Action cell `
  -CellId stage8-list-models `
  -WaitForCellCompletion `
  -CompletionText STAGE8_MODELS_OK `
  -WaitSeconds 600 `
  -ReloadFromDisk:$false `
  -Json
```

Пример запуска Qwen3-14B:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\06_run_stage8_large_llms.ipynb `
  -Action cell `
  -CellId stage8-run-qwen3-14b `
  -WaitForCellCompletion `
  -CompletionText STAGE8_QWEN3_14B_OK `
  -WaitSeconds 7200 `
  -ReloadFromDisk:$false `
  -Json
```

Для полного запуска на 200 примерах в Colab перед ячейкой выставь:

```python
import os
os.environ["STAGE8_SAMPLE_SIZE"] = "200"
os.environ["STAGE8_RENDER_LIMIT"] = "0"
```

По умолчанию Stage 8 запускается на 20 примерах, чтобы сначала проверить валидность, скорость и память.
