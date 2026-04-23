# VS Code Colab Notebook Runner

`run_colab_notebook.ps1` нажимает Jupyter-команды в Microsoft Visual Studio Code на Windows. Скрипт нужен для ноутбуков, которые уже подключены к runtime, например Google Colab, когда агент может редактировать `.ipynb`, но не может сам нажимать кнопки запуска ячеек.

## Требования

- Интерактивная Windows-сессия.
- Microsoft Visual Studio Code, не Cursor и не Windsurf.
- Установленное расширение Microsoft Jupyter для VS Code.
- Целевой `.ipynb` открывается в VS Code и уже подключён к нужному kernel/runtime.

## Примеры

Запустить все ячейки:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action run-all
```

Запустить текущую сфокусированную ячейку:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action current-cell
```

Запустить конкретную ячейку по 0-based индексу:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 2
```

Запустить конкретную ячейку по notebook cell id:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellId setup-cell
```

Запустить конкретную ячейку, source которой содержит уникальный маркер:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellText "TRAINING_MARKER"
```

Посмотреть, что будет сделано, без нажатий в VS Code:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 0 -DryRun -Json
```

Отключить сохранение после action:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action current-cell -SaveAfterRun:$false
```

Не перезагружать notebook editor с диска:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 0 -ReloadFromDisk:$false
```

## Заметки

- `-Action cell` читает JSON ноутбука, превращает выбранную ячейку в индекс, фокусирует её через notebook keyboard navigation и запускает стандартным shortcut текущей ячейки.
- По умолчанию при `-NotebookPath` скрипт закрывает и заново открывает активный notebook editor перед запуском action. Так внешние изменения `.ipynb` становятся видимыми в UI VS Code перед выполнением.
- `run-all` использует keyboard-loop по ячейкам, потому что в проверенной связке VS Code/Colab это оказалось надёжнее, чем action через Command Palette.
- `-CellText` должен совпадать ровно с одной ячейкой.
- Скрипт временно использует текстовый clipboard для вставки путей и названий команд. Если возможно, прежний текстовый clipboard восстанавливается.
- Если VS Code использует неанглийский UI, `-PaletteLanguage auto` пытается определить язык. Его можно задать явно, например `-PaletteLanguage ru`.
