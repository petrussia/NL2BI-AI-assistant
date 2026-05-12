"""Read the latest BRIDGE_URL from notebook cell outputs and write it to
tools/.bridge_url. The notebook stores cell outputs in the .ipynb JSON;
since the IDE on Windows runs/saves the notebook, the freshest BRIDGE_URL
printed by cell 07_AGENT_BRIDGE_SETUP_FIXED is right there in the file.

Usage:
    python tools/sync_bridge_url_from_notebook.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_NB = REPO / 'notebooks' / 'example_agent_setup_clean.ipynb'
DEFAULT_OUT = REPO / 'tools' / '.bridge_url'

URL_RE = re.compile(r'https://[-a-zA-Z0-9.]+\.trycloudflare\.com')


def iter_output_text(cell):
    for o in cell.get('outputs', []) or []:
        # Stream outputs (stdout)
        if o.get('output_type') == 'stream' and isinstance(o.get('text'), (list, str)):
            txt = o['text']
            yield ''.join(txt) if isinstance(txt, list) else txt
        # Execute_result / display_data with text/plain
        for key in ('data', ):
            data = o.get(key) or {}
            tp = data.get('text/plain')
            if isinstance(tp, list):
                yield ''.join(tp)
            elif isinstance(tp, str):
                yield tp


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--notebook', default=str(DEFAULT_NB))
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    args = ap.parse_args()
    NB = Path(args.notebook)
    OUT = Path(args.out)

    if not NB.is_file():
        print(f'Notebook not found: {NB}')
        return 2
    with NB.open(encoding='utf-8') as f:
        nb = json.load(f)

    candidate_urls: list[str] = []
    for c in nb.get('cells', []):
        cid = c.get('id') or ''
        # ONLY look at the canonical bridge setup cell. Other cells (08
        # readiness, 04 BQ probe, etc.) may have stale URL prints from
        # prior runs and would mislead us.
        if cid != '07-agent-bridge-setup':
            continue
        for txt in iter_output_text(c):
            for m in URL_RE.finditer(txt or ''):
                candidate_urls.append(m.group(0))

    if not candidate_urls:
        print(f'NO_URL_FOUND in notebook outputs of bridge cells: {NB}')
        print('Re-run cell 07_AGENT_BRIDGE_SETUP_FIXED in your IDE so the')
        print('output (containing BRIDGE_URL: https://...trycloudflare.com)')
        print('is saved into the .ipynb file. Then run me again.')
        return 1

    # Take the LAST URL — outputs are appended in run order; the latest run
    # produces the freshest URL.
    url = candidate_urls[-1]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prev = OUT.read_text(encoding='utf-8').strip() if OUT.is_file() else ''
    OUT.write_text(url + '\n', encoding='utf-8')
    print(f'WROTE {OUT}')
    print(f'  prev: {prev or "(none)"}')
    print(f'  new:  {url}')
    if len(candidate_urls) > 1:
        print(f'  (found {len(candidate_urls)} candidates in cell outputs; took the last)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
