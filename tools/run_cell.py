"""
run_cell.py v3 — convenient cell-runner for agent ↔ Colab notebook.

Usage:
  python run_cell.py CELL_ID [--max-wait SEC] [--poll SEC] [--initial-wait SEC]
                             [--quiet] [--log-file PATH]

Pipeline:
  1. Read notebook JSON, snapshot cell's pre-run execution_count.
  2. Force-focus notebook tab in VS Code via `code -r <nb>`.
  3. Invoke PowerShell helper with `-Action cell -CellId X -WaitSeconds N`.
     Helper focuses the cell in VS Code and sends Shift+Enter, then Ctrl+S.
  4. Poll notebook JSON every `--poll` seconds.
  5. When execution_count changes to a new non-None integer, do a stability
     re-read after a short pause (absorbs VS Code mid-write race), then dump
     the cell's outputs and exit.
  6. Periodically dump partial output (every ~30 s) so long-running cells are
     observable.
  7. On timeout: if helper rc was 0 but exec_count never changed, log explicit
     "SUSPECT FOCUS FAILURE" diagnostic; dump whatever output exists; exit 3.

Exit codes / status field:
  0 / "ok"               cell completed without error
  1 / "cell_error"       cell ran but contains an error output (traceback)
  2 / "invocation_failed" could not find cell or helper failed to invoke
  3 / "timeout"          timed out waiting for execution_count to change
  3 / "focus_suspect"    timeout AND helper rc=0 — likely focus misroute

Logs:
  Every invocation writes:
    tools/logs/run_cell_<cellid>_<UTC>.log     full transcript
    tools/logs/run_cell_<cellid>_<UTC>.json    structured status sidecar

v3 changes vs v2.1: LOG_DIR moved from .claude/logs to tools/logs;
status JSON sidecar; explicit focus-failure suspicion on timeout-after-rc0.
See run_cell_changelog.md for full diff.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

NB = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\notebooks\example.ipynb")
HELPER = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\scripts\run_colab_notebook.ps1")
LOG_DIR = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\tools\logs")


def load_nb():
    return json.loads(NB.read_text(encoding="utf-8"))


def find_cell(nb_data, cell_id):
    for i, c in enumerate(nb_data.get("cells", [])):
        if c.get("id") == cell_id:
            return i, c
    return None, None


def cell_outputs_text(cell):
    parts = []
    for o in cell.get("outputs", []):
        ot = o.get("output_type")
        if ot == "stream":
            parts.append("".join(o.get("text", [])))
        elif ot == "execute_result":
            data = o.get("data", {})
            if "text/plain" in data:
                parts.append("".join(data["text/plain"]))
        elif ot == "error":
            ename = o.get("ename", "")
            evalue = o.get("evalue", "")
            parts.append(f"\n[CELL ERROR] {ename}: {evalue}\n")
            for line in o.get("traceback", []):
                parts.append(line + "\n")
    return "".join(parts)


def has_error_outputs(cell):
    return any(o.get("output_type") == "error" for o in cell.get("outputs", []))


def focus_notebook(log):
    """Force VS Code to focus the notebook tab.

    Required because the agent's PowerShell-tool output gets opened as a
    readonly tab in VS Code, which steals focus from the notebook tab and
    causes the helper's SendKeys to misroute (helper trace shows
    ``mouse click editor surface at 1028,-999`` when wrong tab is focused).

    Returns True on success, False if no `code` CLI was usable.
    """
    candidates = [
        r"D:\Programs\Microsoft VS Code\bin\code.cmd",
        "code.cmd",
        "code",
    ]
    for code_cmd in candidates:
        try:
            r = subprocess.run([code_cmd, "-r", str(NB)],
                               capture_output=True, text=True, timeout=10)
            log(f"focused notebook via `{code_cmd} -r` (rc={r.returncode})")
            time.sleep(1.5)  # let VS Code process the focus change
            return True
        except FileNotFoundError:
            continue
        except Exception as exc:
            log(f"WARNING: `{code_cmd} -r` failed: {exc!r}")
            return False
    log("WARNING: no `code` CLI found, cannot pre-focus notebook tab")
    return False


def invoke_helper(cell_id, initial_wait, log):
    focus_ok = focus_notebook(log)
    cmd = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", str(HELPER),
        "-NotebookPath", str(NB),
        "-Action", "cell",
        "-CellId", cell_id,
        "-WaitSeconds", str(initial_wait),
    ]
    log(f"invoking helper: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        log("helper TIMED OUT after 180s")
        return None, "helper_timeout", focus_ok
    log(f"helper rc={res.returncode}")
    if res.returncode != 0:
        log(f"helper stdout (first 500): {res.stdout[:500]!r}")
        log(f"helper stderr (first 500): {res.stderr[:500]!r}")
        return res, "helper_failed", focus_ok
    return res, "ok", focus_ok


def write_status_sidecar(json_path, status_obj):
    json_path.write_text(json.dumps(status_obj, ensure_ascii=False, indent=2),
                         encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Run a notebook cell and wait for completion.")
    ap.add_argument("cell_id", help="Notebook cell id (8-char hex)")
    ap.add_argument("--max-wait", type=int, default=300, help="Max seconds to wait for completion (default 300)")
    ap.add_argument("--poll", type=int, default=5, help="Poll interval seconds (default 5)")
    ap.add_argument("--initial-wait", type=int, default=8, help="WaitSeconds passed to helper (default 8)")
    ap.add_argument("--quiet", action="store_true", help="Suppress agent-side log lines (cell output still printed)")
    ap.add_argument("--log-file", default=None, help="Override log file path")
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = Path(args.log_file) if args.log_file else LOG_DIR / f"run_cell_{args.cell_id}_{ts}.log"
    json_path = log_path.with_suffix(".json")
    log_lines = []
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    t_start = time.time()

    def log(msg):
        line = f"[{dt.datetime.now(dt.timezone.utc).isoformat()}] {msg}"
        log_lines.append(line)
        if not args.quiet:
            print(line, flush=True)

    def flush_log():
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    def finalize(status, exit_code, **extra):
        flush_log()
        sidecar = {
            "cell_id": args.cell_id,
            "status": status,
            "exit_code": exit_code,
            "started_at": started_at,
            "ended_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "elapsed_seconds": round(time.time() - t_start, 2),
            "max_wait": args.max_wait,
            "poll": args.poll,
            "initial_wait": args.initial_wait,
            "log_path": str(log_path),
            **extra,
        }
        write_status_sidecar(json_path, sidecar)
        sys.exit(exit_code)

    log(f"START cell={args.cell_id} max_wait={args.max_wait} poll={args.poll} init={args.initial_wait}")
    nb = load_nb()
    idx, cell = find_cell(nb, args.cell_id)
    if cell is None:
        log(f"FAIL: cell '{args.cell_id}' not found in {NB}")
        finalize("invocation_failed", 2, reason="cell_not_found")

    pre_exec = cell.get("execution_count")
    pre_outputs_count = len(cell.get("outputs", []))
    log(f"cell idx={idx} pre_exec={pre_exec} pre_outputs={pre_outputs_count}")

    res, status, focus_ok = invoke_helper(args.cell_id, args.initial_wait, log)
    helper_rc = res.returncode if res is not None else None
    if status != "ok":
        log(f"helper status={status} -> aborting")
        finalize("invocation_failed", 2, reason=status, helper_rc=helper_rc)

    deadline = time.time() + args.max_wait
    waited = 0
    last_partial = 0

    while time.time() < deadline:
        time.sleep(args.poll)
        waited += args.poll
        try:
            nb2 = load_nb()
        except json.JSONDecodeError:
            log(f"  notebook JSON decode error at {waited}s — VS Code mid-write, retrying")
            continue
        _, cell2 = find_cell(nb2, args.cell_id)
        if cell2 is None:
            log(f"  cell vanished at {waited}s")
            continue
        new_exec = cell2.get("execution_count")
        new_outputs_count = len(cell2.get("outputs", []))

        if new_exec is not None and new_exec != pre_exec:
            time.sleep(min(args.poll, 2))
            try:
                nb3 = load_nb()
                _, cell3 = find_cell(nb3, args.cell_id)
            except json.JSONDecodeError:
                log(f"  exec changed but JSON unstable at {waited}s, will retry")
                continue
            if cell3 is None or cell3.get("execution_count") != new_exec:
                log(f"  exec changed but unstable at {waited}s, continuing")
                continue
            txt = cell_outputs_text(cell3)
            err = has_error_outputs(cell3)
            log(f"DONE after ~{waited}s, new_exec={new_exec}, has_error={err}, outputs={len(cell3.get('outputs', []))}")
            log("--- CELL OUTPUT (last 8000 chars) ---")
            log(txt[-8000:])
            log("--- END OUTPUT ---")
            if not args.quiet:
                print("\n--- CELL OUTPUT ---", flush=True)
                print(txt, flush=True)
                print("--- END ---", flush=True)
            finalize(
                "cell_error" if err else "ok",
                1 if err else 0,
                pre_exec=pre_exec, new_exec=new_exec, helper_rc=helper_rc,
                output_chars=len(txt), output_tail=txt[-300:],
            )

        if waited - last_partial >= 30:
            partial = cell_outputs_text(cell2)
            preview = partial[-600:].replace("\n", " | ") if partial else "(no output yet)"
            log(f"  [{waited}s] still running; pre_exec={pre_exec} cur_exec={new_exec} outputs={new_outputs_count}")
            log(f"  partial tail: {preview!r}")
            last_partial = waited

    # Timeout path
    log(f"TIMEOUT after {waited}s, no exec_count change")

    suspect_focus = (helper_rc == 0)
    if suspect_focus:
        log("SUSPECT FOCUS FAILURE: helper rc=0 but execution_count did not change.")
        log("  Likely cause: PowerShell-tool readonly tab stole focus from the notebook tab.")
        log("  Fix: ensure `code -r` focused the notebook (check focus_notebook log line above);")
        log("       consider closing extra readonly tabs in VS Code, or run cell manually once.")

    try:
        nb_final = load_nb()
        _, cell_final = find_cell(nb_final, args.cell_id)
    except Exception as exc:
        cell_final = None
        log(f"  could not load notebook on timeout: {exc!r}")

    output_tail = ""
    if cell_final:
        txt = cell_outputs_text(cell_final)
        output_tail = txt[-300:]
        log("--- PARTIAL CELL OUTPUT ON TIMEOUT (last 8000 chars) ---")
        log(txt[-8000:])
        log("--- END PARTIAL ---")
        if not args.quiet:
            print("\n--- PARTIAL CELL OUTPUT (timeout) ---", flush=True)
            print(txt, flush=True)
            print("--- END ---", flush=True)

    print(f"[run_cell] log saved to {log_path}", flush=True)
    print(f"[run_cell] status sidecar: {json_path}", flush=True)
    finalize(
        "focus_suspect" if suspect_focus else "timeout",
        3,
        pre_exec=pre_exec, helper_rc=helper_rc, focus_ok=focus_ok,
        output_tail=output_tail,
    )


if __name__ == "__main__":
    main()
