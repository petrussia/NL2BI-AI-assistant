# VS Code Colab Notebook Runner

`scripts/colab/run_colab_notebook.ps1` нажимает Jupyter-команды в Microsoft Visual Studio Code на Windows. Скрипт нужен для ноутбуков, которые уже подключены к runtime, например Google Colab, когда агент может редактировать `.ipynb`, но не может сам нажимать кнопки запуска ячеек.

## Требования

- Интерактивная Windows-сессия.
- Microsoft Visual Studio Code, не Cursor и не Windsurf.
- Установленное расширение Microsoft Jupyter для VS Code.
- Целевой `.ipynb` является валидным notebook-файлом, открыт в VS Code, активен как notebook editor и уже подключён к нужному kernel/runtime. Пустые scaffold-заглушки `.ipynb` нельзя запускать, пока они не заполнены.
- В VS Code активен ровно один notebook editor: целевой notebook. Обычные вкладки с README, скриптами и другими не-notebook файлами можно не закрывать.

## Примеры

Запустить все ячейки:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action run-all
```

Запустить текущую сфокусированную ячейку:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action current-cell
```

Запустить конкретную ячейку по 0-based индексу:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 2
```

Для запуска из агента сначала явно активируйте нужный notebook в VS Code, затем вызывайте runner:

```powershell
& "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd" -r -g "$PWD\notebooks\example.ipynb:1:1"
Start-Sleep -Seconds 3
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 2 -WaitSeconds 20 -ReloadFromDisk:$false -Json
```

Запустить конкретную ячейку по notebook cell id:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellId setup-cell
```

Запустить конкретную ячейку, source которой содержит уникальный маркер:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellText "TRAINING_MARKER"
```

Посмотреть, что будет сделано, без нажатий в VS Code:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 0 -DryRun -Json
```

Сохранение отключено по умолчанию, потому что в некоторых VS Code `Ctrl+S` привязан к другой команде:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action current-cell
```

Не пытаться перезагружать notebook editor с диска:

```powershell
.\scripts\colab\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 0 -ReloadFromDisk:$false
```

## Заметки

- Перед запуском скрипт проверяет активные VS Code notebook windows. Если целевой notebook не активен или открыто несколько notebook windows, runner возвращает BLOCKER и просит агента остановиться, активировать один нужный notebook и закрыть лишние notebook-вкладки/окна. Не-notebook вкладки не мешают.
- `-Action cell` читает JSON ноутбука, превращает выбранную ячейку в индекс, фокусирует её через notebook keyboard navigation (`Ctrl+Home`, затем `J`) и запускает текущую ячейку через `Shift+Enter`.
- В strict single-notebook режиме `-ReloadFromDisk` не закрывает и не переоткрывает notebook, чтобы runner не потерял выбранную вкладку и не переключился на другой файл.
- `run-all` использует keyboard-loop по ячейкам, потому что в проверенной связке VS Code/Colab это оказалось надёжнее, чем action через Command Palette.
- `-CellText` должен совпадать ровно с одной ячейкой.
- `-CellId` работает и для notebooks, где у некоторых ячеек отсутствует поле `id`.
- `-WaitSeconds` — это верхняя граница простого ожидания, а не детектор завершения ячейки. Для длинных Colab-ячеек лучше ставить короткие окна 20-30 секунд, сохранять notebook и проверять `execution_count`, `outputs`, traceback/error-маркеры и финальные текстовые маркеры самой ячейки. Не запускайте ту же долгую ячейку повторно, пока не понятно, завершилась ли предыдущая попытка.
- Скрипт временно использует текстовый clipboard для вставки путей и названий команд. Если возможно, прежний текстовый clipboard восстанавливается.
- Если VS Code использует неанглийский UI, `-PaletteLanguage auto` пытается определить язык. Его можно задать явно, например `-PaletteLanguage ru`.
