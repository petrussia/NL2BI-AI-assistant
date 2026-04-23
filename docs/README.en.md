# VS Code Colab Notebook Runner

`run_colab_notebook.ps1` presses Jupyter notebook commands in Microsoft Visual Studio Code on Windows. It is intended for notebooks already connected to a runtime such as Google Colab, where an agent can edit `.ipynb` files but cannot click notebook run buttons directly.

## Requirements

- Windows desktop session.
- Microsoft Visual Studio Code, not Cursor or Windsurf.
- Microsoft Jupyter extension installed in VS Code.
- The target `.ipynb` is openable in VS Code and already connected to the desired kernel/runtime.

## Examples

Run all cells:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action run-all
```

Run the current focused cell:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action current-cell
```

Run a specific cell by 0-based index:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 2
```

Run a specific cell by notebook cell id:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellId setup-cell
```

Run a specific cell whose source contains a unique marker:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellText "TRAINING_MARKER"
```

Preview what would be done without touching VS Code:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 0 -DryRun -Json
```

Disable saving after the action:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action current-cell -SaveAfterRun:$false
```

Skip reloading the notebook editor from disk:

```powershell
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellIndex 0 -ReloadFromDisk:$false
```

## Notes

- `-Action cell` reads the notebook JSON, resolves the requested cell to an index, focuses it with notebook keyboard navigation, and runs it with the standard current-cell shortcut.
- By default, when `-NotebookPath` is provided, the script closes and reopens the active notebook editor before dispatching an action. This makes external `.ipynb` edits visible in the VS Code notebook UI before execution.
- `run-all` uses a keyboard loop over notebook cells because this proved more reliable in the tested VS Code/Colab setup than the Command Palette action.
- `-CellText` must match exactly one cell source.
- The script temporarily uses the text clipboard to paste paths and command titles. It restores the previous text clipboard when possible.
- If VS Code uses a non-English UI, `-PaletteLanguage auto` tries to detect it. You can override it, for example `-PaletteLanguage ru`.
