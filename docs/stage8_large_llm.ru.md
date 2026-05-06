# Stage 8: large LLM JSON-validator baseline

Stage 8 запускает новые Hugging Face модели через тот же строгий контур, что и
Stage 6/7:

- модель генерирует один компактный Vega-Lite JSON;
- validator проверяет синтаксис JSON, `mark`, `encoding`, поля схемы, типы и
  агрегации;
- при ошибке model получает текст ошибки и подсказку, как исправить ответ;
- максимум три повторные попытки;
- невалидный JSON не проходит в метрики как нормальный prediction.

## Файлы

- `configs/stage8_large_llm_models.json` - список моделей, method names,
  квантизация и минимальная VRAM.
- `scripts/run_stage8_large_llm.py` - единый runner для одной Stage 8 модели.
- `notebooks/06_run_stage8_large_llms.ipynb` - Colab notebook с отдельной
  ячейкой на каждую модель.

## Модели

| key | HF model | quantization | заметка |
|---|---|---|---|
| `qwen36_35b_a3b` | `Qwen/Qwen3.6-35B-A3B` | bitsandbytes 4-bit NF4 | 35B total, 3B active |
| `qwen3_coder_next_awq4` | `bullpoint/Qwen3-Coder-Next-AWQ-4bit` | pre-quantized AWQ 4-bit | base model is `Qwen/Qwen3-Coder-Next`; quantized size is about 45GB |
| `gemma4_e2b_it` | `google/gemma-4-E2B-it` | bitsandbytes 4-bit NF4 | small smoke/quality run |
| `gemma4_26b_a4b_it_mtp` | `google/gemma-4-26B-A4B-it` + `google/gemma-4-26B-A4B-it-assistant` | target in bitsandbytes 4-bit NF4, assistant in native precision | speculative/MTP assistant model |

## Colab Pro+ GPU choice

- Для `gemma4_e2b_it`: сначала бери `L4 24GB`. `T4 16GB` должен подойти для
  smoke/small run, но будет медленнее.
- Для `gemma4_26b_a4b_it_mtp`: бери `A100 40GB`. `L4 24GB` пограничный вариант:
  может влезть только с маленьким batch/prompt, но есть риск OOM.
- Для `qwen36_35b_a3b`: бери `A100 40GB`. `L4 24GB` лучше не тратить на полный
  запуск.
- Для `qwen3_coder_next_awq4`: нужна карта примерно от 48GB VRAM. Если в Colab
  доступна только `A100 40GB`, не запускай эту ячейку без явного риска OOM.
  Практичный вариант - `A100 80GB` или `H100`, если они доступны.

Runner сам проверяет `min_vram_gb` перед загрузкой весов и падает раньше, чем
Colab убьёт runtime из-за OOM. Обойти проверку можно только через
`STAGE8_ALLOW_LOW_VRAM=1`.

## Запуск через VS Code/Colab runner

Сначала открой `notebooks/06_run_stage8_large_llms.ipynb` как единственный
активный notebook в VS Code и подключи нужный Colab runtime.

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

Пример запуска Gemma 4 E2B:

```powershell
.\scripts\colab\run_colab_notebook.ps1 `
  -NotebookPath .\notebooks\06_run_stage8_large_llms.ipynb `
  -Action cell `
  -CellId stage8-run-gemma4-e2b-it `
  -WaitForCellCompletion `
  -CompletionText STAGE8_GEMMA4_E2B_IT_OK `
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

По умолчанию Stage 8 запускается на 20 примерах, чтобы сначала проверить
валидность, скорость и память.

