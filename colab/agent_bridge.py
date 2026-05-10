"""Agent bridge — runs inside the Colab kernel, exposes /exec over an ngrok tunnel.

Lets the agent push arbitrary Python into the running Colab session without a
human clicking "Run cell". Adapted from `experiments/denis` branch
(`tools/backups/_add_bridge_cell.py`) — that version used a cloudflared quick
tunnel; this version reuses the existing `NGROK_AUTHTOKEN` so we don't depend
on a second tunneling vendor.

Endpoints (all exposed under the bridge URL):
    GET  /health                 -> {"ok": true, "pid": <kernel pid>}
    POST /exec                   -> exec(payload["code"], _SHARED_GLOBALS); returns
                                    stdout/stderr; non-200 on exception.
                                    If env BRIDGE_TOKEN is set, requires header
                                    X-Bridge-Token: <token> on every request.
    GET  /file?path=...          -> raw file download
    GET  /ls?path=...            -> directory listing
    POST /restart_uvicorn        -> kills any process on COLAB_PORT (default 8000)
                                    and respawns uvicorn for
                                    colab.text_to_sql_colab_server:app. Convenience
                                    wrapper — same effect as POSTing matching code
                                    to /exec.

The bridge boots on 127.0.0.1:5050 by default and is published via pyngrok using
the same `NGROK_AUTHTOKEN` as the main FastAPI service. The bridge URL is also
written to `/content/drive/MyDrive/nl2bi_colab/.bridge_url` so the FastAPI app
can re-publish it through `/admin/bridge_url`.

Security: /exec is intentionally an RCE endpoint. Set BRIDGE_TOKEN in your
Drive .env to require auth. The ngrok URL itself should be treated as a
credential — don't paste it anywhere public.
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

try:
    from flask import Flask, jsonify, request, send_file
except ImportError as exc:  # pragma: no cover - deps installed by notebook
    raise SystemExit(
        "flask is required: `pip install flask`. "
        "The Colab notebook installs it via colab/requirements-colab.txt."
    ) from exc


_BRIDGE_PORT = int(os.environ.get("COLAB_BRIDGE_PORT", "5050"))
_DEFAULT_MARKER = Path("/content/drive/MyDrive/nl2bi_colab/.bridge_url")
_TOKEN_FILE_CANDIDATES = (
    Path("/content/drive/MyDrive/nl2bi_colab/.bridge_token"),
    Path("/content/drive/MyDrive/.bridge_token"),
)

_app = Flask(__name__)
_SHARED_GLOBALS: dict[str, object] = {"__name__": "bridge_remote"}
_BRIDGE_THREAD: threading.Thread | None = None
_BRIDGE_TUNNEL_URL: str | None = None


def _resolve_expected_token() -> str | None:
    """Pick the bridge auth token from env (BRIDGE_TOKEN) first, then Drive.

    Drive fallback exists because the claude.ai Drive MCP scope can only
    write into folders the app created — so I deposit the token at MyDrive
    root and read it back here. None disables auth (open /exec).
    """
    env_token = os.environ.get("BRIDGE_TOKEN")
    if env_token:
        return env_token
    for candidate in _TOKEN_FILE_CANDIDATES:
        if candidate.exists():
            try:
                text = candidate.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if text:
                return text
    return None


def _check_token() -> tuple[bool, str | None]:
    """Fail-closed: if no token is configured, every authed route rejects.

    /exec must NEVER be reachable without a configured BRIDGE_TOKEN (env or
    Drive-fallback file). Previously this returned `ok=True` when nothing was
    set — that opened an RCE surface. The bridge now refuses both at startup
    (see start_bridge) and per-request as a defense in depth.
    """
    expected = _resolve_expected_token()
    if not expected:
        return False, "BRIDGE_TOKEN not configured on the server"
    received = request.headers.get("X-Bridge-Token")
    if received and received == expected:
        return True, None
    return False, "missing or invalid X-Bridge-Token"


@_app.before_request
def _auth() -> object | None:
    if request.path == "/health":
        return None
    ok, err = _check_token()
    if not ok:
        return jsonify({"ok": False, "error": err}), 401
    return None


@_app.route("/health")
def _health():
    return jsonify({"ok": True, "pid": os.getpid()})


@_app.route("/exec", methods=["POST"])
def _execute_remote():
    payload = request.get_json(force=True, silent=True) or {}
    code = payload.get("code", "")
    if not code:
        return jsonify({"ok": False, "error": "no code"}), 400
    out_buf, err_buf = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            exec(code, _SHARED_GLOBALS)  # noqa: S102 — RCE is the whole point
        return jsonify(
            {
                "ok": True,
                "stdout": out_buf.getvalue(),
                "stderr": err_buf.getvalue(),
            }
        )
    except Exception:
        return (
            jsonify(
                {
                    "ok": False,
                    "stdout": out_buf.getvalue(),
                    "stderr": err_buf.getvalue(),
                    "traceback": traceback.format_exc(),
                }
            ),
            500,
        )


@_app.route("/file")
def _get_file():
    path = request.args.get("path", "")
    p = Path(path)
    if not path or not p.exists() or not p.is_file():
        return jsonify({"ok": False, "error": "not_found", "path": path}), 404
    return send_file(str(p), as_attachment=True, download_name=p.name)


@_app.route("/ls")
def _ls():
    path = request.args.get("path", "/content")
    p = Path(path)
    if not p.exists():
        return jsonify({"ok": False, "error": "not_found", "path": path}), 404
    items: list[dict[str, object]] = []
    if p.is_dir():
        for child in sorted(p.iterdir()):
            items.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else None,
                }
            )
    else:
        items.append({"name": p.name, "type": "file", "size": p.stat().st_size})
    return jsonify({"ok": True, "path": str(p), "items": items})


@_app.route("/restart_uvicorn", methods=["POST"])
def _restart_uvicorn():
    """Kill anything on COLAB_PORT and respawn uvicorn for the FastAPI app.

    Useful after the agent has done `git pull` and wants to pick up code
    changes without reloading the model in-process (uvicorn --reload would
    rebuild the FastAPI module, re-loading Qwen 7B from scratch — too slow).
    """
    port = int(os.environ.get("COLAB_PORT", "8000"))
    repo_dir = os.environ.get("COLAB_REPO_DIR", "/content/nl2bi-colab")

    log_dir = Path(os.environ.get("COLAB_LOG_DIR", "/content/drive/MyDrive/nl2bi_colab/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "uvicorn.stdout.log"
    stderr_path = log_dir / "uvicorn.stderr.log"

    killed = False
    try:
        result = subprocess.run(
            ["fuser", "-k", f"{port}/tcp"], capture_output=True, text=True
        )
        killed = result.returncode == 0
    except FileNotFoundError:
        result = subprocess.run(
            ["bash", "-c", f"lsof -ti tcp:{port} | xargs -r kill -9"],
            capture_output=True,
            text=True,
        )
        killed = bool(result.stdout.strip())

    if killed:
        time.sleep(1)

    env = os.environ.copy()
    env["PYTHONPATH"] = repo_dir + ((":" + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")

    stdout_handle = stdout_path.open("ab", buffering=0)
    stderr_handle = stderr_path.open("ab", buffering=0)
    stdout_handle.write(f"\n--- bridge-restart {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode())
    stderr_handle.write(f"\n--- bridge-restart {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode())

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "colab.text_to_sql_colab_server:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=repo_dir,
        env=env,
        stdout=stdout_handle,
        stderr=stderr_handle,
    )
    return jsonify(
        {
            "ok": True,
            "killed_prior": killed,
            "uvicorn_pid": proc.pid,
            "port": port,
            "stdout_log": str(stdout_path),
            "stderr_log": str(stderr_path),
        }
    )


def _resolve_bridge_url_via_pyngrok(port: int) -> str | None:
    """Open an ngrok HTTP tunnel for `port` reusing NGROK_AUTHTOKEN.

    Returns the https:// public URL, or None on failure.
    """
    token = os.environ.get("NGROK_AUTHTOKEN")
    if not token:
        print("BRIDGE: NGROK_AUTHTOKEN missing; bridge will only be local")
        return None
    try:
        from pyngrok import ngrok, conf
    except ImportError:
        print("BRIDGE: pyngrok missing; install via colab/requirements-colab.txt")
        return None

    conf.get_default().auth_token = token
    # Tear down any old bridge tunnel that points at the same port.
    for tunnel in list(ngrok.get_tunnels()):
        try:
            if str(port) in (tunnel.config or {}).get("addr", ""):
                ngrok.disconnect(tunnel.public_url)
        except Exception:
            continue
    tunnel = ngrok.connect(port, "http")
    return tunnel.public_url.replace("http://", "https://")


def start_bridge(
    *,
    port: int = _BRIDGE_PORT,
    bridge_url_marker: Path | None = _DEFAULT_MARKER,
    timeout_seconds: int = 30,
) -> str | None:
    """Boot the Flask bridge in a daemon thread and publish via ngrok.

    Refuses to start when no BRIDGE_TOKEN is configured (env or Drive
    fallback file). This makes it impossible to accidentally publish an
    unauthenticated /exec to the internet.

    Idempotent: re-runs do not start a second flask thread or a second
    tunnel on the same port.

    Returns the public URL, or None on startup failure.
    """
    global _BRIDGE_THREAD, _BRIDGE_TUNNEL_URL

    if not _resolve_expected_token():
        print(
            "BRIDGE_REFUSED: BRIDGE_TOKEN not configured. Set BRIDGE_TOKEN in "
            f"env, or place a non-empty file at one of {[str(p) for p in _TOKEN_FILE_CANDIDATES]}. "
            "Refusing to start an open /exec endpoint."
        )
        return None

    if _BRIDGE_THREAD is None or not _BRIDGE_THREAD.is_alive():
        def _serve() -> None:
            _app.run(
                host="127.0.0.1",
                port=port,
                debug=False,
                use_reloader=False,
                threaded=True,
            )

        _BRIDGE_THREAD = threading.Thread(target=_serve, daemon=True, name="agent-bridge-flask")
        _BRIDGE_THREAD.start()
        time.sleep(2)
        print(f"BRIDGE: flask started on 127.0.0.1:{port}")
    else:
        print(f"BRIDGE: flask already running on 127.0.0.1:{port}")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.5)

    url = _resolve_bridge_url_via_pyngrok(port)
    _BRIDGE_TUNNEL_URL = url

    if url and bridge_url_marker is not None:
        try:
            bridge_url_marker.parent.mkdir(parents=True, exist_ok=True)
            bridge_url_marker.write_text(url + "\n", encoding="utf-8")
            print(f"BRIDGE: wrote URL marker to {bridge_url_marker}")
        except OSError as exc:
            print(f"BRIDGE: could not write marker: {exc}")

    if url:
        print()
        print(f"BRIDGE_URL: {url}")
        # Don't reveal where the token came from — only that auth is on.
        print("BRIDGE_AUTH: X-Bridge-Token header required on all routes except /health")
        print("BRIDGE_READY")
    else:
        print("BRIDGE_FAILED: tunnel could not be opened (check NGROK_AUTHTOKEN)")
    return url


def get_bridge_url_marker(marker: Path = _DEFAULT_MARKER) -> str | None:
    if not marker.exists():
        return None
    text = marker.read_text(encoding="utf-8").strip()
    return text or None


if __name__ == "__main__":
    start_bridge()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("agent bridge shutdown")
