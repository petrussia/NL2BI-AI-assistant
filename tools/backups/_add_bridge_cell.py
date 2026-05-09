"""Insert AGENT_BRIDGE_SETUP cell at the end of the notebook."""
import json
import uuid
from pathlib import Path

NB = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\notebooks\example.ipynb")

SRC = '''# AGENT_BRIDGE_SETUP
# Run this ONCE per Colab session. It starts a Flask server in this kernel and
# exposes it via a free Cloudflare tunnel (no auth needed). The agent then talks
# to the kernel directly over HTTP — no SendKeys, no VS Code focus issues.
#
# Output to look for:
#   BRIDGE_URL: https://<random>.trycloudflare.com
#   BRIDGE_READY
#
# To stop: restart the kernel.

import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

MARKER = 'AGENT_BRIDGE_SETUP'
print(MARKER)

# 1. Install Flask if missing
try:
    import flask  # noqa
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'flask'], check=True)

from flask import Flask, jsonify, request, send_file
import base64
import contextlib
import io
import traceback

# 2. Download cloudflared binary if missing
CF_BIN = Path('/content/cloudflared')
if not CF_BIN.exists():
    print('Downloading cloudflared...')
    urllib.request.urlretrieve(
        'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64',
        str(CF_BIN),
    )
    CF_BIN.chmod(0o755)
    print(f'cloudflared at {CF_BIN}, size={CF_BIN.stat().st_size}')

# 3. Build Flask app
app = Flask(__name__)
_SHARED_GLOBALS = {'__name__': 'bridge_remote'}

@app.route('/health')
def health():
    return jsonify({'ok': True, 'pid': os.getpid()})

@app.route('/exec', methods=['POST'])
def execute_remote():
    payload = request.get_json(force=True, silent=True) or {}
    code = payload.get('code', '')
    if not code:
        return jsonify({'ok': False, 'error': 'no code'}), 400
    out_buf, err_buf = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            exec(code, _SHARED_GLOBALS)
        return jsonify({
            'ok': True,
            'stdout': out_buf.getvalue(),
            'stderr': err_buf.getvalue(),
        })
    except Exception:
        return jsonify({
            'ok': False,
            'stdout': out_buf.getvalue(),
            'stderr': err_buf.getvalue(),
            'traceback': traceback.format_exc(),
        }), 500

@app.route('/file')
def get_file():
    path = request.args.get('path', '')
    p = Path(path)
    if not path or not p.exists() or not p.is_file():
        return jsonify({'ok': False, 'error': 'not_found', 'path': path}), 404
    return send_file(str(p), as_attachment=True, download_name=p.name)

@app.route('/ls')
def ls():
    path = request.args.get('path', '/content')
    p = Path(path)
    if not p.exists():
        return jsonify({'ok': False, 'error': 'not_found', 'path': path}), 404
    items = []
    if p.is_dir():
        for x in sorted(p.iterdir()):
            items.append({
                'name': x.name,
                'type': 'dir' if x.is_dir() else 'file',
                'size': x.stat().st_size if x.is_file() else None,
            })
    else:
        items.append({'name': p.name, 'type': 'file', 'size': p.stat().st_size})
    return jsonify({'ok': True, 'path': str(p), 'items': items})

# 4. Start Flask in background thread
PORT = 5000

def _serve():
    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False, threaded=True)

if 'BRIDGE_THREAD' not in globals():
    BRIDGE_THREAD = threading.Thread(target=_serve, daemon=True, name='bridge-flask')
    BRIDGE_THREAD.start()
    time.sleep(2)
    print(f'flask started on 127.0.0.1:{PORT}')
else:
    print(f'flask already started on 127.0.0.1:{PORT}')

# 5. Start cloudflared tunnel and capture URL
if 'BRIDGE_PROC' in globals() and BRIDGE_PROC.poll() is None:
    print(f'cloudflared already running (pid={BRIDGE_PROC.pid}); restart kernel to refresh')
else:
    BRIDGE_PROC = subprocess.Popen(
        [str(CF_BIN), 'tunnel', '--url', f'http://127.0.0.1:{PORT}', '--no-autoupdate'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        bufsize=1, text=True,
    )
    print(f'cloudflared started (pid={BRIDGE_PROC.pid})')

# 6. Read tunnel output, extract URL
url = None
deadline = time.time() + 60
url_re = re.compile(r'(https://[a-z0-9-]+\\.trycloudflare\\.com)')
while time.time() < deadline:
    line = BRIDGE_PROC.stdout.readline()
    if not line:
        if BRIDGE_PROC.poll() is not None:
            print('cloudflared exited unexpectedly')
            break
        time.sleep(0.1)
        continue
    print('[cloudflared]', line.rstrip())
    m = url_re.search(line)
    if m:
        url = m.group(1)
        break

if url:
    print()
    print(f'BRIDGE_URL: {url}')
    bridge_marker = Path('/content/drive/MyDrive/diploma_plan_sql/.bridge_url')
    bridge_marker.parent.mkdir(parents=True, exist_ok=True)
    bridge_marker.write_text(url)
    print(f'wrote bridge URL marker to {bridge_marker}')
    print('BRIDGE_READY')
else:
    print('BRIDGE_FAILED: could not extract tunnel URL within 60s')
'''

# Need to escape: re module pattern uses backslash-period
SRC_FIXED = SRC.replace("\\\\.", r"\.")

nb = json.loads(NB.read_text(encoding="utf-8"))

# Avoid duplicate
existing = next((c for c in nb["cells"] if "AGENT_BRIDGE_SETUP" in "".join(c.get("source", []))), None)
if existing:
    existing["source"] = SRC_FIXED.splitlines(keepends=True)
    existing["outputs"] = []
    existing["execution_count"] = None
    cid = existing["id"]
    print(f"Updated existing AGENT_BRIDGE_SETUP cell id={cid}")
else:
    new_cell = {
        "cell_type": "code",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "outputs": [],
        "execution_count": None,
        "source": SRC_FIXED.splitlines(keepends=True),
    }
    nb["cells"].append(new_cell)
    print(f"Inserted AGENT_BRIDGE_SETUP cell id={new_cell['id']} at end")

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"Total cells now: {len(nb['cells'])}")
