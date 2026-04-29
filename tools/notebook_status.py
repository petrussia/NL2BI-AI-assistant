"""
notebook_status.py — quick view of notebook cell states.

Usage:
  python notebook_status.py                      # all cells, terse
  python notebook_status.py --cell-id ad703bcf   # specific cell(s), repeatable
  python notebook_status.py --last-lines 5       # show last 5 lines of each output
  python notebook_status.py --json               # machine-readable snapshot
  python notebook_status.py --full ad703bcf      # full output of one cell

Use case: after the agent kicks off a cell, this gives a one-screen view of
which cells have run, which errored, and what the last few lines of output were.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

NB = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\notebooks\example.ipynb")


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
            parts.append(f"\n[ERROR] {o.get('ename', '')}: {o.get('evalue', '')}\n")
            for line in o.get("traceback", []):
                parts.append(line + "\n")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell-id", action="append", help="Show only this cell id (repeatable)")
    ap.add_argument("--last-lines", type=int, default=3, help="Lines of last output to show (terse mode)")
    ap.add_argument("--json", action="store_true", help="Emit JSON snapshot of selected cells to stdout")
    ap.add_argument("--save-json", default=None, help="Save JSON snapshot to this file path")
    ap.add_argument("--full", help="Print full output of one specific cell id")
    args = ap.parse_args()

    nb = json.loads(NB.read_text(encoding="utf-8"))

    if args.full:
        for c in nb.get("cells", []):
            if c.get("id") == args.full:
                print(f"=== cell {args.full} (idx={nb['cells'].index(c)}, exec={c.get('execution_count')}) ===")
                print(cell_outputs_text(c))
                return
        print(f"cell '{args.full}' not found")
        return

    rows = []
    for i, c in enumerate(nb.get("cells", [])):
        cid = c.get("id", "?")
        if args.cell_id and cid not in args.cell_id:
            continue
        outs = c.get("outputs", [])
        text = cell_outputs_text(c)
        last_lines = text.strip().splitlines()[-args.last_lines:] if text.strip() else []
        has_error = any(o.get("output_type") == "error" for o in outs)
        rows.append({
            "idx": i,
            "id": cid,
            "type": c["cell_type"],
            "exec": c.get("execution_count"),
            "outputs": len(outs),
            "error": has_error,
            "last_lines": last_lines,
        })

    if args.save_json:
        from pathlib import Path as _P
        _P(args.save_json).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved snapshot: {args.save_json}")

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    for r in rows:
        err_marker = " [ERROR]" if r["error"] else ""
        exec_str = "None" if r["exec"] is None else str(r["exec"])
        print(f"{r['idx']:>2} | {r['id']:>10} | {r['type']:>8} | exec={exec_str:>5} | outs={r['outputs']:>2}{err_marker}")
        for ln in r["last_lines"]:
            print(f"        > {ln}")


if __name__ == "__main__":
    main()
