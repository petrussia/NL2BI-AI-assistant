# Local Helper Script Audit

- Local path: `D:\HSE\??????\NL2BI-AI-assistant\scripts\run_colab_notebook.ps1`
- Found: yes
- Purpose: drives VS Code Jupyter notebook UI on Windows through `WScript.SendKeys`.
- Can read notebook: partially, yes. It reads `.ipynb` JSON to resolve `CellIndex`, `CellId`, and `CellText` selectors.
- Can execute cells: yes. Supports `current-cell`, `current-cell-and-advance`, `cell`, `run-all`, `restart-and-run-all`, `run-above`, `run-current-and-below`, `interrupt-kernel`, and `restart-kernel`.
- Can rerun cells: yes, by selecting the same cell and sending the run shortcut again.
- Can modify cells: no. It is an execution/focus helper, not a notebook editor.
- Safety behavior: checks that exactly one active VS Code notebook window matches the target notebook; non-notebook tabs are allowed.
- Output modes: plain text or JSON via `-Json`.
- Relevant options: `-NotebookPath`, `-Action`, `-CellIndex`, `-CellId`, `-CellText`, `-WaitSeconds`, `-ReloadFromDisk`, `-SaveAfterRun`, `-DryRun`, `-Json`.
