"""bridge_health_watcher — local watcher that probes the Cloudflare tunnel.

Polls /health every N seconds. Logs each result. On consecutive failures
prints a loud message that the tunnel needs to be re-armed in the Colab
notebook.

Usage (run in BG):
    python tools/bridge_health_watcher.py --interval 300
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
URL_FILE = REPO / 'tools' / '.bridge_url'
LOG_PATH = REPO / 'outputs' / 'logs' / 'bridge_health_watch.log'

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def log(msg, *, also_print=True):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    line = f'[{ts}] {msg}'
    if also_print:
        print(line, flush=True)
    with LOG_PATH.open('a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def probe_once():
    if not URL_FILE.is_file():
        return ('no_url_file', None)
    url = URL_FILE.read_text(encoding='utf-8').strip().rstrip('/')
    host = url.split('://', 1)[-1].split('/', 1)[0]
    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        return ('nxdomain', url)
    try:
        with urllib.request.urlopen(url + '/health', timeout=15) as r:
            data = json.loads(r.read().decode())
            return ('ok', data)
    except urllib.error.URLError as e:
        return ('http_err', str(e))
    except Exception as e:
        return ('exc', f'{type(e).__name__}: {e}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--interval', type=int, default=300, help='probe interval seconds')
    ap.add_argument('--quiet', action='store_true', help='only log on state change')
    args = ap.parse_args()

    log(f'bridge_health_watcher started, interval={args.interval}s')
    last_state = None
    consecutive_fails = 0
    while True:
        state, payload = probe_once()
        if state == 'ok':
            consecutive_fails = 0
            if state != last_state:
                log(f'OK pid={payload.get("pid")}', also_print=True)
            elif not args.quiet:
                log(f'OK pid={payload.get("pid")}', also_print=False)
        else:
            consecutive_fails += 1
            log(f'{state.upper()} ({consecutive_fails}× consecutive): {payload}',
                also_print=True)
            if consecutive_fails == 1:
                # Loud header on first failure
                msg = ('!!! BRIDGE TUNNEL DOWN — re-arm AGENT_BRIDGE_SETUP cell '
                        'in Colab + update tools/.bridge_url !!!')
                print('\n' + '=' * len(msg))
                print(msg)
                print('=' * len(msg) + '\n', flush=True)
        last_state = state
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
