<#
.SYNOPSIS
Runs Jupyter/Colab notebook cells in Microsoft Visual Studio Code on Windows.

.DESCRIPTION
This script drives the VS Code UI with WScript.SendKeys. It is meant for cases
where a notebook is connected to a remote runtime, such as Google Colab, and an
agent can edit the .ipynb file but cannot press notebook run buttons directly.

The target notebook must already be open and active in VS Code. In strict
single-notebook mode, the script refuses to continue unless exactly one active
VS Code notebook window is visible and it matches the target notebook title.
Non-notebook tabs such as README files or scripts do not need to be closed.

The script supports running the current cell, all cells, kernel commands, and a
specific cell selected by 0-based index, notebook cell id, or a source-text
substring. It resolves localized Jupyter command titles from the installed
Microsoft Jupyter extension and falls back to English titles.

.PARAMETER NotebookPath
Path to the .ipynb file. This is the preferred way to target a notebook.

.PARAMETER NotebookTitle
Window/tab title fragment to find or focus when NotebookPath is not provided.

.PARAMETER Action
The notebook action to dispatch. Use "cell" together with CellIndex, CellId, or
CellText to run a specific cell without relying on the current notebook focus.

.PARAMETER CellIndex
0-based notebook cell index used with -Action cell.

.PARAMETER CellId
Notebook cell id used with -Action cell.

.PARAMETER CellText
Source-code substring used with -Action cell. The match must be unique.

.PARAMETER PaletteLanguage
Command palette language. "auto" reads the running VS Code language and then
falls back to the extension bundle and English.

.PARAMETER DryRun
Resolve paths, commands, and cell selectors without opening VS Code or sending
keyboard input.

.PARAMETER ReloadFromDisk
Retained for compatibility. In strict single-notebook mode the runner does not
close or reopen the active notebook editor because doing so can switch focus to
the wrong notebook. Pass -ReloadFromDisk:$false in agent loops to make this
explicit in the command line and trace.

.PARAMETER Json
Print a machine-readable JSON result.

.EXAMPLE
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action run-all

.EXAMPLE
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellId setup-cell -Json

.EXAMPLE
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action cell -CellText "TRAINING_MARKER" -WaitSeconds 20

.EXAMPLE
.\scripts\run_colab_notebook.ps1 -NotebookPath .\notebooks\example.ipynb -Action current-cell -SaveAfterRun:$false
#>
[CmdletBinding()]
param(
    [ValidateSet(
        'current-cell',
        'current-cell-and-advance',
        'cell',
        'run-all',
        'restart-and-run-all',
        'run-above',
        'run-current-and-below',
        'interrupt-kernel',
        'restart-kernel'
    )]
    [string]$Action = 'run-all',

    [string]$NotebookPath,

    [string]$NotebookTitle,

    [int]$CellIndex = -1,

    [string]$CellId,

    [string]$CellText,

    [string]$PaletteLanguage = 'auto',

    [int]$WaitSeconds = 12,

    [int]$ActivateDelayMs = 300,

    [int]$PaletteDelayMs = 500,

    [int]$OpenDelayMs = 1200,

    [int]$CellMoveDelayMs = 120,

    [switch]$ReloadFromDisk = $true,

    [switch]$SaveAfterRun = $true,

    [switch]$DryRun,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:IsDryRun = [bool]$DryRun
$script:OutputJson = [bool]$Json
$script:Trace = New-Object 'System.Collections.Generic.List[string]'

function Add-Trace {
    param([string]$Message)
    $script:Trace.Add($Message) | Out-Null
}

function Assert-Windows {
    if (-not [System.Environment]::OSVersion.Platform.ToString().StartsWith('Win')) {
        throw 'This script requires an interactive Windows desktop session.'
    }
}

function Initialize-WindowApi {
    if ('ColabRunner.WindowApi' -as [type]) {
        return
    }

    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace ColabRunner {
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    public static class WindowApi {
        [DllImport("user32.dll")]
        public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        public static extern bool SetForegroundWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

        [DllImport("user32.dll")]
        public static extern bool GetWindowRect(IntPtr hWnd, out Rect rect);

        [DllImport("user32.dll")]
        public static extern bool SetCursorPos(int x, int y);

        [DllImport("user32.dll")]
        public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
    }
}
'@
}

function Resolve-NotebookFullPath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction Stop
    $fullPath = $resolved.ProviderPath

    if ([System.IO.Path]::GetExtension($fullPath) -ne '.ipynb') {
        throw "NotebookPath must point to an .ipynb file: $fullPath"
    }

    return $fullPath
}

function Get-VSCodeCommandPath {
    $knownPaths = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\bin\code.cmd'),
        (Join-Path $env:ProgramFiles 'Microsoft VS Code\bin\code.cmd')
    )

    $programFilesX86 = [System.Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if (-not [string]::IsNullOrWhiteSpace($programFilesX86)) {
        $knownPaths += (Join-Path $programFilesX86 'Microsoft VS Code\bin\code.cmd')
    }

    foreach ($path in $knownPaths) {
        if (Test-Path -LiteralPath $path) {
            return (Resolve-Path -LiteralPath $path).ProviderPath
        }
    }

    $commands = @(Get-Command code.cmd -All -ErrorAction SilentlyContinue)
    foreach ($command in $commands) {
        if ($command.Source -like '*Microsoft VS Code*') {
            return $command.Source
        }
    }

    throw 'Could not find Microsoft Visual Studio Code command line tool (code.cmd).'
}

function Get-VSCodeWindowProcess {
    param([string]$Title)

    $processes = @(Get-Process -Name Code -ErrorAction SilentlyContinue |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.MainWindowTitle) })

    if ($processes.Count -eq 0) {
        throw 'Could not find an active Microsoft Visual Studio Code window.'
    }

    if (-not [string]::IsNullOrWhiteSpace($Title)) {
        $matching = @($processes | Where-Object { $_.MainWindowTitle -like "*$Title*" })
        if ($matching.Count -gt 0) {
            return ($matching | Sort-Object StartTime -Descending | Select-Object -First 1)
        }
        throw "Could not find an active Microsoft Visual Studio Code window with title containing '$Title'."
    }

    return ($processes | Sort-Object StartTime -Descending | Select-Object -First 1)
}

function Wait-VSCodeWindowProcess {
    param(
        [string]$Title,
        [int]$TimeoutMs = 8000
    )

    $deadline = (Get-Date).AddMilliseconds($TimeoutMs)
    $lastError = $null

    do {
        try {
            return (Get-VSCodeWindowProcess -Title $Title)
        } catch {
            $lastError = $_.Exception.Message
            Start-Sleep -Milliseconds 250
        }
    } while ((Get-Date) -lt $deadline)

    throw $lastError
}

function Assert-SingleTargetNotebookWindow {
    param([string]$NotebookTitle)

    if ([string]::IsNullOrWhiteSpace($NotebookTitle)) {
        throw 'NotebookTitle or NotebookPath is required for strict notebook UI preflight.'
    }

    $notebookWindows = @(Get-Process -Name Code -ErrorAction SilentlyContinue |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.MainWindowTitle) -and $_.MainWindowTitle -like '*.ipynb*' })

    $targetWindows = @($notebookWindows | Where-Object { $_.MainWindowTitle -like "*$NotebookTitle*" })

    if ($notebookWindows.Count -ne 1 -or $targetWindows.Count -ne 1) {
        $windowList = if ($notebookWindows.Count -gt 0) {
            ($notebookWindows | ForEach-Object { $_.MainWindowTitle }) -join '; '
        } else {
            '(no active VS Code notebook window)'
        }

        throw (
            "BLOCKER: the active VS Code editor must be the target notebook '$NotebookTitle'. " +
            "Current active notebook window(s): $windowList. " +
            "Agent must stop now, activate the target notebook, close extra notebook tabs/windows if any are active, then rerun this cell. " +
            "Non-notebook tabs such as README or scripts do not need to be closed."
        )
    }

    return $targetWindows[0]
}

function Get-InstalledJupyterExtensionPath {
    $root = Join-Path $env:USERPROFILE '.vscode\extensions'
    if (-not (Test-Path -LiteralPath $root)) {
        throw "VS Code extensions directory was not found: $root"
    }

    $candidates = @()
    foreach ($directory in Get-ChildItem -LiteralPath $root -Directory -ErrorAction Stop) {
        if ($directory.Name -match '^ms-toolsai\.jupyter-(\d+\.\d+\.\d+)(?:-.+)?$') {
            $candidates += [pscustomobject]@{
                Path    = $directory.FullName
                Version = [version]$Matches[1]
            }
        }
    }

    if ($candidates.Count -eq 0) {
        throw 'Microsoft Jupyter extension was not found in the VS Code extensions directory.'
    }

    return ($candidates | Sort-Object Version -Descending | Select-Object -First 1).Path
}

function Get-VSCodeRuntimeLanguage {
    $commandLines = @(Get-CimInstance Win32_Process -Filter "Name='Code.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match '--lang=([A-Za-z-]+)' } |
        ForEach-Object { $Matches[1] })

    if ($commandLines.Count -gt 0) {
        return $commandLines[0].ToLowerInvariant()
    }

    $localeFiles = @(
        (Join-Path $env:APPDATA 'Code\User\locale.json'),
        (Join-Path $env:APPDATA 'Code\User\argv.json')
    )

    foreach ($localeFile in $localeFiles) {
        if (Test-Path -LiteralPath $localeFile) {
            $content = Get-Content -LiteralPath $localeFile -Raw
            $match = [regex]::Match($content, '"locale"\s*:\s*"([^"]+)"')
            if ($match.Success) {
                return $match.Groups[1].Value.ToLowerInvariant()
            }
        }
    }

    return [System.Globalization.CultureInfo]::CurrentUICulture.Name.ToLowerInvariant()
}

function Get-CommandSpec {
    param([string]$ActionName)

    $dispatchAction = $ActionName
    if ($ActionName -eq 'cell') {
        $dispatchAction = 'current-cell'
    }

    switch ($dispatchAction) {
        'current-cell' {
            return [pscustomobject]@{
                RequestedAction = $ActionName
                DispatchAction  = $dispatchAction
                CommandId       = 'jupyter.runcurrentcell'
                NlsKey          = 'jupyter.command.jupyter.runcurrentcell.title'
                FallbackTitle   = 'Run Current Cell'
            }
        }
        'current-cell-and-advance' {
            return [pscustomobject]@{
                RequestedAction = $ActionName
                DispatchAction  = $dispatchAction
                CommandId       = 'jupyter.runcurrentcelladvance'
                NlsKey          = 'jupyter.command.jupyter.runcurrentcelladvance.title'
                FallbackTitle   = 'Run Current Cell And Advance'
            }
        }
        'run-all' {
            return [pscustomobject]@{
                RequestedAction = $ActionName
                DispatchAction  = $dispatchAction
                CommandId       = 'jupyter.runallcells'
                NlsKey          = 'jupyter.command.jupyter.runallcells.title'
                FallbackTitle   = 'Run All Cells'
            }
        }
        'restart-and-run-all' {
            return [pscustomobject]@{
                RequestedAction = $ActionName
                DispatchAction  = $dispatchAction
                CommandId       = 'jupyter.restartkernelandrunallcells'
                NlsKey          = 'jupyter.command.jupyter.restartkernelandrunallcells.title'
                FallbackTitle   = 'Restart Kernel and Run All Cells'
            }
        }
        'run-above' {
            return [pscustomobject]@{
                RequestedAction = $ActionName
                DispatchAction  = $dispatchAction
                CommandId       = 'jupyter.runallcellsabove.palette'
                NlsKey          = 'jupyter.command.jupyter.runallcellsabove.palette.title'
                FallbackTitle   = 'Run Cells Above Current Cell'
            }
        }
        'run-current-and-below' {
            return [pscustomobject]@{
                RequestedAction = $ActionName
                DispatchAction  = $dispatchAction
                CommandId       = 'jupyter.runcurrentcellandallbelow.palette'
                NlsKey          = 'jupyter.command.jupyter.runcurrentcellandallbelow.palette.title'
                FallbackTitle   = 'Run Current Cell and Below'
            }
        }
        'interrupt-kernel' {
            return [pscustomobject]@{
                RequestedAction = $ActionName
                DispatchAction  = $dispatchAction
                CommandId       = 'jupyter.interruptkernel'
                NlsKey          = 'jupyter.command.jupyter.interruptkernel.title'
                FallbackTitle   = 'Interrupt Kernel'
            }
        }
        'restart-kernel' {
            return [pscustomobject]@{
                RequestedAction = $ActionName
                DispatchAction  = $dispatchAction
                CommandId       = 'jupyter.restartkernel'
                NlsKey          = 'jupyter.command.jupyter.restartkernel.title'
                FallbackTitle   = 'Restart Kernel'
            }
        }
    }

    throw "Unsupported action: $ActionName"
}

function Get-JsonStringValue {
    param(
        [string]$FilePath,
        [string]$Key
    )

    if (-not (Test-Path -LiteralPath $FilePath)) {
        return $null
    }

    $content = Get-Content -LiteralPath $FilePath -Raw
    $escapedKey = [regex]::Escape($Key)
    $pattern = '"' + $escapedKey + '"\s*:\s*"((?:\\.|[^"\\])*)"'
    $match = [regex]::Match($content, $pattern)

    if (-not $match.Success) {
        return $null
    }

    $jsonString = '"' + $match.Groups[1].Value + '"'
    try {
        return ($jsonString | ConvertFrom-Json)
    } catch {
        return [regex]::Unescape($match.Groups[1].Value)
    }
}

function Resolve-PaletteCommandTitle {
    param(
        [object]$CommandSpec,
        [string]$ExtensionPath,
        [string]$RequestedLanguage
    )

    $languages = New-Object 'System.Collections.Generic.List[string]'

    if ([string]::IsNullOrWhiteSpace($RequestedLanguage) -or $RequestedLanguage -eq 'auto') {
        $runtimeLanguage = Get-VSCodeRuntimeLanguage
        if (-not [string]::IsNullOrWhiteSpace($runtimeLanguage)) {
            $languages.Add($runtimeLanguage) | Out-Null
        }
    } else {
        $languages.Add($RequestedLanguage.ToLowerInvariant()) | Out-Null
    }

    $currentCulture = [System.Globalization.CultureInfo]::CurrentCulture.Name.ToLowerInvariant()
    if (-not [string]::IsNullOrWhiteSpace($currentCulture)) {
        $languages.Add($currentCulture) | Out-Null
    }

    $languages.Add('en') | Out-Null

    $seen = @{}
    foreach ($language in $languages) {
        $normalized = $language.ToLowerInvariant()
        $short = ($normalized -split '-')[0]
        foreach ($candidate in @($normalized, $short)) {
            if ($seen.ContainsKey($candidate)) {
                continue
            }
            $seen[$candidate] = $true

            if ($candidate -eq 'en') {
                $bundlePath = Join-Path $ExtensionPath 'package.nls.json'
            } else {
                $bundlePath = Join-Path $ExtensionPath ("package.nls.{0}.json" -f $candidate)
            }

            $title = Get-JsonStringValue -FilePath $bundlePath -Key $CommandSpec.NlsKey
            if (-not [string]::IsNullOrWhiteSpace($title)) {
                return [pscustomobject]@{
                    Title      = $title
                    BundlePath = $bundlePath
                    Language   = $candidate
                }
            }
        }
    }

    return [pscustomobject]@{
        Title      = $CommandSpec.FallbackTitle
        BundlePath = $null
        Language   = 'fallback-en'
    }
}

function Read-NotebookCells {
    param([string]$Path)

    $notebook = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($null -eq $notebook.cells) {
        throw "Notebook does not contain a cells array: $Path"
    }

    return @($notebook.cells)
}

function Get-CellSourceText {
    param([object]$Cell)

    if ($null -eq $Cell.source) {
        return ''
    }

    if ($Cell.source -is [array]) {
        return [string]::Join('', @($Cell.source))
    }

    return [string]$Cell.source
}

function Get-CellId {
    param([object]$Cell)

    $property = $Cell.PSObject.Properties['id']
    if ($null -eq $property -or $null -eq $property.Value) {
        return ''
    }

    return [string]$property.Value
}

function Resolve-CellSelection {
    param(
        [string]$Path,
        [int]$Index,
        [string]$Id,
        [string]$Text
    )

    $selectorCount = 0
    if ($Index -ge 0) { $selectorCount++ }
    if (-not [string]::IsNullOrWhiteSpace($Id)) { $selectorCount++ }
    if (-not [string]::IsNullOrWhiteSpace($Text)) { $selectorCount++ }

    if ($selectorCount -ne 1) {
        throw 'Use exactly one of -CellIndex, -CellId, or -CellText with -Action cell.'
    }

    $cells = Read-NotebookCells -Path $Path
    $resolvedIndex = -1
    $matchReason = $null

    if ($Index -ge 0) {
        if ($Index -ge $cells.Count) {
            throw "CellIndex $Index is out of range. Notebook has $($cells.Count) cells."
        }
        $resolvedIndex = $Index
        $matchReason = 'index'
    } elseif (-not [string]::IsNullOrWhiteSpace($Id)) {
        $matches = @()
        for ($i = 0; $i -lt $cells.Count; $i++) {
            if ((Get-CellId -Cell $cells[$i]) -eq $Id) {
                $matches += $i
            }
        }
        if ($matches.Count -eq 0) {
            throw "No notebook cell with id '$Id' was found."
        }
        if ($matches.Count -gt 1) {
            throw "Cell id '$Id' is not unique. Matching indexes: $($matches -join ', ')"
        }
        $resolvedIndex = $matches[0]
        $matchReason = 'id'
    } else {
        $matches = @()
        for ($i = 0; $i -lt $cells.Count; $i++) {
            $source = Get-CellSourceText -Cell $cells[$i]
            if ($source.Contains($Text)) {
                $matches += $i
            }
        }
        if ($matches.Count -eq 0) {
            throw "No notebook cell source contains '$Text'."
        }
        if ($matches.Count -gt 1) {
            throw "CellText '$Text' is not unique. Matching indexes: $($matches -join ', ')"
        }
        $resolvedIndex = $matches[0]
        $matchReason = 'text'
    }

    $cell = $cells[$resolvedIndex]
    $targetSource = Get-CellSourceText -Cell $cell
    $searchText = Get-UniqueCellSearchText -Cells $cells -Index $resolvedIndex -PreferredText $Text
    $sourcePreview = $targetSource.Replace("`r", '').Replace("`n", '\n')
    if ($sourcePreview.Length -gt 160) {
        $sourcePreview = $sourcePreview.Substring(0, 160)
    }

    return [pscustomobject]@{
        Index         = $resolvedIndex
        CellCount     = $cells.Count
        Id            = Get-CellId -Cell $cell
        CellType      = [string]$cell.cell_type
        MatchReason   = $matchReason
        SearchText    = $searchText
        FocusStrategy = 'keyboard-navigation'
        SourcePreview = $sourcePreview
    }
}

function Get-UniqueCellSearchText {
    param(
        [array]$Cells,
        [int]$Index,
        [string]$PreferredText
    )

    if (-not [string]::IsNullOrWhiteSpace($PreferredText)) {
        return $PreferredText
    }

    $targetSource = Get-CellSourceText -Cell $Cells[$Index]
    if ([string]::IsNullOrWhiteSpace($targetSource)) {
        return $null
    }

    $lineCandidates = @($targetSource -split "`r?`n" |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_.Length -ge 8 } |
        Sort-Object Length -Descending)

    foreach ($candidate in $lineCandidates) {
        $matchCount = 0
        foreach ($cell in $Cells) {
            if ((Get-CellSourceText -Cell $cell).Contains($candidate)) {
                $matchCount++
            }
        }

        if ($matchCount -eq 1) {
            return $candidate
        }
    }

    return $null
}

function Invoke-Delay {
    param(
        [int]$Milliseconds,
        [string]$Reason
    )

    if ($Milliseconds -le 0) {
        return
    }

    Add-Trace ("wait {0} ms: {1}" -f $Milliseconds, $Reason)
    if (-not $script:IsDryRun) {
        Start-Sleep -Milliseconds $Milliseconds
    }
}

function Send-Keys {
    param(
        [System.__ComObject]$Shell,
        [string]$Keys,
        [string]$Description
    )

    Add-Trace ("send keys: {0} ({1})" -f $Description, $Keys)
    if (-not $script:IsDryRun) {
        $Shell.SendKeys($Keys)
    }
}

function Set-ClipboardText {
    param(
        [string]$Text,
        [string]$Description
    )

    Add-Trace ("set clipboard: {0}" -f $Description)
    if (-not $script:IsDryRun) {
        Set-Clipboard -Value $Text
    }
}

function Activate-Window {
    param(
        [System.__ComObject]$Shell,
        [System.Diagnostics.Process]$Process,
        [int]$DelayMs
    )

    Add-Trace ("activate VS Code PID {0}" -f $Process.Id)
    if (-not $script:IsDryRun) {
        Initialize-WindowApi

        $Process.Refresh()
        if ($Process.MainWindowHandle -eq [IntPtr]::Zero) {
            throw "VS Code PID $($Process.Id) does not expose a main window handle."
        }

        [ColabRunner.WindowApi]::ShowWindowAsync($Process.MainWindowHandle, 9) | Out-Null
        Start-Sleep -Milliseconds 100
        [ColabRunner.WindowApi]::SetForegroundWindow($Process.MainWindowHandle) | Out-Null
        Start-Sleep -Milliseconds 100
        $Shell.AppActivate($Process.Id) | Out-Null

        Invoke-Delay -Milliseconds $DelayMs -Reason 'wait after VS Code activation'

        $foregroundWindow = [ColabRunner.WindowApi]::GetForegroundWindow()
        [uint32]$foregroundPid = 0
        [ColabRunner.WindowApi]::GetWindowThreadProcessId($foregroundWindow, [ref]$foregroundPid) | Out-Null

        if ([int]$foregroundPid -ne [int]$Process.Id) {
            $rect = New-Object ColabRunner.Rect
            if ([ColabRunner.WindowApi]::GetWindowRect($Process.MainWindowHandle, [ref]$rect)) {
                $x = $rect.Left + [int](($rect.Right - $rect.Left) / 2)
                $y = $rect.Top + [int](($rect.Bottom - $rect.Top) / 2)
                Add-Trace ("fallback activation click at {0},{1}" -f $x, $y)
                [ColabRunner.WindowApi]::SetCursorPos($x, $y) | Out-Null
                Start-Sleep -Milliseconds 80
                [ColabRunner.WindowApi]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 40
                [ColabRunner.WindowApi]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 300
                $Shell.AppActivate($Process.Id) | Out-Null
                Start-Sleep -Milliseconds 300
                $foregroundWindow = [ColabRunner.WindowApi]::GetForegroundWindow()
                [ColabRunner.WindowApi]::GetWindowThreadProcessId($foregroundWindow, [ref]$foregroundPid) | Out-Null
            }
        }

        if ([int]$foregroundPid -ne [int]$Process.Id) {
            throw "Failed to activate VS Code PID $($Process.Id). Foreground PID is $foregroundPid."
        }
    }
}

function Focus-PrimaryEditorGroup {
    param(
        [System.__ComObject]$Shell,
        [System.Diagnostics.Process]$Process
    )

    Initialize-WindowApi

    $Process.Refresh()
    $rect = New-Object ColabRunner.Rect
    if ([ColabRunner.WindowApi]::GetWindowRect($Process.MainWindowHandle, [ref]$rect)) {
        $width = $rect.Right - $rect.Left
        $height = $rect.Bottom - $rect.Top
        if ($width -gt 0 -and $height -gt 0) {
            $x = $rect.Left + [int]($width * 0.52)
            $y = $rect.Top + [int]([math]::Min([math]::Max($height * 0.40, 320), 420))
            Add-Trace ("mouse click editor surface at {0},{1}" -f $x, $y)
            if (-not $script:IsDryRun) {
                [ColabRunner.WindowApi]::SetCursorPos($x, $y) | Out-Null
                Start-Sleep -Milliseconds 80
                [ColabRunner.WindowApi]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 40
                [ColabRunner.WindowApi]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 120
            }
        }
    }

    Invoke-Delay -Milliseconds 300 -Reason 'wait after focusing primary editor group'
}

function Invoke-PaletteCommand {
    param(
        [System.__ComObject]$Shell,
        [string]$CommandTitle,
        [int]$PaletteOpenDelayMs
    )

    Set-ClipboardText -Text $CommandTitle -Description "command palette title '$CommandTitle'"
    Send-Keys -Shell $Shell -Keys '{ESC}' -Description 'leave cell edit mode'
    Invoke-Delay -Milliseconds 100 -Reason 'wait before command palette'
    Send-Keys -Shell $Shell -Keys '^+p' -Description 'open command palette'
    Invoke-Delay -Milliseconds $PaletteOpenDelayMs -Reason 'wait for command palette'
    Send-Keys -Shell $Shell -Keys '^a' -Description 'select command palette text'
    Invoke-Delay -Milliseconds 100 -Reason 'wait before paste'
    Send-Keys -Shell $Shell -Keys '^v' -Description 'paste command title'
    Invoke-Delay -Milliseconds 150 -Reason 'wait before running command'
    Send-Keys -Shell $Shell -Keys '{ENTER}' -Description 'run command palette command'
}

function Get-DispatchMethodName {
    param([object]$CommandSpec)

    if ($CommandSpec.DispatchAction -eq 'current-cell') {
        return 'shortcut-shift-enter'
    }

    if ($CommandSpec.DispatchAction -eq 'current-cell-and-advance') {
        return 'shortcut-shift-enter'
    }

    if ($CommandSpec.DispatchAction -eq 'run-all') {
        return 'keyboard-run-all-loop'
    }

    return 'command-palette'
}

function Invoke-NotebookDispatch {
    param(
        [System.__ComObject]$Shell,
        [object]$CommandSpec,
        [string]$CommandTitle,
        [int]$PaletteOpenDelayMs,
        [object]$NotebookCellCount,
        [int]$MoveDelayMs
    )

    if ($CommandSpec.DispatchAction -eq 'current-cell') {
        Send-Keys -Shell $Shell -Keys '+{ENTER}' -Description 'run focused notebook cell'
        return 'shortcut-shift-enter'
    }

    if ($CommandSpec.DispatchAction -eq 'current-cell-and-advance') {
        Send-Keys -Shell $Shell -Keys '+{ENTER}' -Description 'run focused notebook cell and advance'
        return 'shortcut-shift-enter'
    }

    if ($CommandSpec.DispatchAction -eq 'run-all' -and $null -ne $NotebookCellCount -and [int]$NotebookCellCount -gt 0) {
        $cellCount = [int]$NotebookCellCount
        Focus-NotebookCellByIndex -Shell $Shell -Index 0 -CellCount $cellCount -DelayMs $MoveDelayMs
        for ($i = 0; $i -lt $cellCount; $i++) {
            Send-Keys -Shell $Shell -Keys '^{ENTER}' -Description ("run notebook cell {0} of {1}" -f ($i + 1), $cellCount)
            Invoke-Delay -Milliseconds 300 -Reason 'wait after queueing cell run'
            if ($i -lt ($cellCount - 1)) {
                Send-Keys -Shell $Shell -Keys 'J' -Description 'move to next notebook cell for run-all loop'
                Invoke-Delay -Milliseconds $MoveDelayMs -Reason 'wait after moving to next cell'
            }
        }
        return 'keyboard-run-all-loop'
    }

    Invoke-PaletteCommand -Shell $Shell -CommandTitle $CommandTitle -PaletteOpenDelayMs $PaletteOpenDelayMs
    return 'command-palette'
}

function Focus-NotebookCellByIndex {
    param(
        [System.__ComObject]$Shell,
        [int]$Index,
        [int]$CellCount,
        [int]$DelayMs
    )

    Send-Keys -Shell $Shell -Keys '{ESC}' -Description 'leave cell edit mode'
    Invoke-Delay -Milliseconds 200 -Reason 'wait before notebook cell navigation'
    Send-Keys -Shell $Shell -Keys '^{HOME}' -Description 'move notebook focus to first cell'
    Invoke-Delay -Milliseconds ([math]::Max($DelayMs * 3, 600)) -Reason 'wait after moving to first cell'
    Send-Keys -Shell $Shell -Keys '{ESC}' -Description 'enter notebook command mode at first cell'
    Invoke-Delay -Milliseconds 200 -Reason 'wait before moving to target cell'

    for ($i = 0; $i -lt $Index; $i++) {
        Send-Keys -Shell $Shell -Keys 'J' -Description 'move to next notebook cell'
        Invoke-Delay -Milliseconds $DelayMs -Reason 'wait after moving to next cell'
    }
}

function Focus-NotebookCell {
    param(
        [System.__ComObject]$Shell,
        [object]$CellSelection,
        [int]$FindDelayMs,
        [int]$MoveDelayMs
    )

    Focus-NotebookCellByIndex -Shell $Shell -Index $CellSelection.Index -CellCount $CellSelection.CellCount -DelayMs $MoveDelayMs
}

function Save-Notebook {
    param([System.__ComObject]$Shell)

    Send-Keys -Shell $Shell -Keys '^s' -Description 'save notebook'
}

function New-ResultObject {
    param(
        [datetime]$StartedAt,
        [string]$NotebookFullPath,
        [string]$EffectiveNotebookTitle,
        [object]$CommandSpec,
        [object]$ResolvedCommand,
        [string]$DispatchMethod,
        [object]$CellSelection,
        [string]$CodeCommandPath,
        [object]$Process
    )

    $endedAt = Get-Date
    $processInfo = $null
    if ($null -ne $Process) {
        $Process.Refresh()
        $processInfo = [pscustomobject]@{
            Id              = $Process.Id
            MainWindowTitle = $Process.MainWindowTitle
        }
    }

    return [pscustomobject]@{
        ok                    = $true
        dryRun                = [bool]$DryRun
        action                = $Action
        dispatchAction        = $CommandSpec.DispatchAction
        notebookPath          = $NotebookFullPath
        notebookTitle         = $EffectiveNotebookTitle
        selectedCell          = $CellSelection
        commandId             = $CommandSpec.CommandId
        commandTitle          = $ResolvedCommand.Title
        dispatchMethod        = $DispatchMethod
        commandLanguage       = $ResolvedCommand.Language
        commandBundlePath     = $ResolvedCommand.BundlePath
        codeCommandPath       = $CodeCommandPath
        process               = $processInfo
        waitSeconds           = $WaitSeconds
        saveAfterRun          = [bool]$SaveAfterRun
        reloadFromDisk        = [bool]$ReloadFromDisk
        startedAt             = $StartedAt.ToString('o')
        endedAt               = $endedAt.ToString('o')
        elapsedSeconds        = [math]::Round(($endedAt - $StartedAt).TotalSeconds, 3)
        trace                 = $script:Trace.ToArray()
    }
}

function Write-RunnerOutput {
    param([object]$Result)

    if ($script:OutputJson) {
        $Result | ConvertTo-Json -Depth 8
        return
    }

    Write-Output ("OK: " + $Result.ok)
    Write-Output ("Dry run: " + $Result.dryRun)
    Write-Output ("Action: " + $Result.action)
    Write-Output ("Dispatch action: " + $Result.dispatchAction)
    Write-Output ("Notebook path: " + $Result.notebookPath)
    Write-Output ("Notebook title: " + $Result.notebookTitle)
    if ($null -ne $Result.selectedCell) {
        Write-Output ("Selected cell: index={0}; id={1}; reason={2}" -f $Result.selectedCell.Index, $Result.selectedCell.Id, $Result.selectedCell.MatchReason)
    }
    Write-Output ("Command id: " + $Result.commandId)
    Write-Output ("Command title: " + $Result.commandTitle)
    Write-Output ("Dispatch method: " + $Result.dispatchMethod)
    Write-Output ("Command language: " + $Result.commandLanguage)
    if ($null -ne $Result.process) {
        Write-Output ("Target PID: " + $Result.process.Id)
        Write-Output ("Target window: " + $Result.process.MainWindowTitle)
    }
    Write-Output ("Save after run: " + $Result.saveAfterRun)
    Write-Output ("Reload from disk: " + $Result.reloadFromDisk)
    Write-Output ("Elapsed seconds: " + $Result.elapsedSeconds)
}

function Write-RunnerError {
    param(
        [datetime]$StartedAt,
        [System.Management.Automation.ErrorRecord]$ErrorRecord
    )

    $endedAt = Get-Date
    if ($script:OutputJson) {
        [pscustomobject]@{
            ok             = $false
            dryRun         = [bool]$DryRun
            action         = $Action
            error          = $ErrorRecord.Exception.Message
            startedAt      = $StartedAt.ToString('o')
            endedAt        = $endedAt.ToString('o')
            elapsedSeconds = [math]::Round(($endedAt - $StartedAt).TotalSeconds, 3)
            trace          = $script:Trace.ToArray()
        } | ConvertTo-Json -Depth 8
    } else {
        Write-Error $ErrorRecord.Exception.Message
    }
}

$startedAt = Get-Date

try {
    Assert-Windows

    if ($CellIndex -lt -1) {
        throw 'CellIndex must be 0 or greater.'
    }

    if ($Action -ne 'cell' -and ($CellIndex -ge 0 -or -not [string]::IsNullOrWhiteSpace($CellId) -or -not [string]::IsNullOrWhiteSpace($CellText))) {
        throw 'Cell selectors are only valid with -Action cell.'
    }

    $notebookFullPath = Resolve-NotebookFullPath -Path $NotebookPath
    $effectiveNotebookTitle = $NotebookTitle
    if ([string]::IsNullOrWhiteSpace($effectiveNotebookTitle) -and -not [string]::IsNullOrWhiteSpace($notebookFullPath)) {
        $effectiveNotebookTitle = [System.IO.Path]::GetFileName($notebookFullPath)
    }

    if ($Action -eq 'cell' -and [string]::IsNullOrWhiteSpace($notebookFullPath)) {
        throw '-Action cell requires -NotebookPath so the script can resolve the target cell.'
    }

    $cellSelection = $null
    if ($Action -eq 'cell') {
        $cellSelection = Resolve-CellSelection -Path $notebookFullPath -Index $CellIndex -Id $CellId -Text $CellText
    }

    $notebookCellCount = $null
    if (-not [string]::IsNullOrWhiteSpace($notebookFullPath)) {
        if ($null -ne $cellSelection) {
            $notebookCellCount = [int]$cellSelection.CellCount
        } else {
            $notebookCellCount = [int]((Read-NotebookCells -Path $notebookFullPath).Count)
        }
    }

    $codeCommandPath = Get-VSCodeCommandPath
    $jupyterExtensionPath = Get-InstalledJupyterExtensionPath
    $commandSpec = Get-CommandSpec -ActionName $Action
    $resolvedCommand = Resolve-PaletteCommandTitle -CommandSpec $commandSpec -ExtensionPath $jupyterExtensionPath -RequestedLanguage $PaletteLanguage
    $dispatchMethod = Get-DispatchMethodName -CommandSpec $commandSpec

    $process = $null
    $shell = $null
    $originalClipboard = $null
    $hasTextClipboard = $false

    if (-not $script:IsDryRun) {
        $process = Assert-SingleTargetNotebookWindow -NotebookTitle $effectiveNotebookTitle
        $shell = New-Object -ComObject WScript.Shell

        try {
            try {
                $originalClipboard = Get-Clipboard -Raw -ErrorAction Stop
                $hasTextClipboard = $true
            } catch {
                $hasTextClipboard = $false
            }

            Activate-Window -Shell $shell -Process $process -DelayMs $ActivateDelayMs
            Focus-PrimaryEditorGroup -Shell $shell -Process $process

            if ([bool]$ReloadFromDisk -and -not [string]::IsNullOrWhiteSpace($notebookFullPath)) {
                Add-Trace 'strict single-notebook mode: skip ReloadFromDisk to avoid changing notebook tabs'
            }

            if ($Action -eq 'cell') {
                Focus-NotebookCell -Shell $shell -CellSelection $cellSelection -FindDelayMs $PaletteDelayMs -MoveDelayMs $CellMoveDelayMs
            }

            $dispatchMethod = Invoke-NotebookDispatch `
                -Shell $shell `
                -CommandSpec $commandSpec `
                -CommandTitle $resolvedCommand.Title `
                -PaletteOpenDelayMs $PaletteDelayMs `
                -NotebookCellCount $notebookCellCount `
                -MoveDelayMs $CellMoveDelayMs
            Invoke-Delay -Milliseconds ($WaitSeconds * 1000) -Reason 'wait for notebook action'

            if ([bool]$SaveAfterRun) {
                Save-Notebook -Shell $shell
                Invoke-Delay -Milliseconds 500 -Reason 'wait after save'
            }
        } finally {
            if ($hasTextClipboard) {
                try {
                    Set-Clipboard -Value $originalClipboard
                } catch {
                    Add-Trace 'failed to restore text clipboard'
                }
            }
        }
    }

    $result = New-ResultObject `
        -StartedAt $startedAt `
        -NotebookFullPath $notebookFullPath `
        -EffectiveNotebookTitle $effectiveNotebookTitle `
        -CommandSpec $commandSpec `
        -ResolvedCommand $resolvedCommand `
        -DispatchMethod $dispatchMethod `
        -CellSelection $cellSelection `
        -CodeCommandPath $codeCommandPath `
        -Process $process

    Write-RunnerOutput -Result $result
} catch {
    Write-RunnerError -StartedAt $startedAt -ErrorRecord $_
    exit 1
}
