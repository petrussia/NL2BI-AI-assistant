"""
exec_remote.py — talk to the Colab kernel directly via the bridge tunnel.

The notebook cell ``AGENT_BRIDGE_SETUP`` (cell id 7f6bca53) starts a Flask
server in the kernel and exposes it via a free Cloudflare tunnel. Run that
cell once per session; it prints ``BRIDGE_URL: https://...trycloudflare.com``.

This script then POSTs Python code, downloads files, or lists directories
without ever touching VS Code SendKeys, so notebook focus does not matter.

Usage:
  python exec_remote.py --health
  python exec_remote.py --code "print(1+1)"
  python exec_remote.py --code-file path/to/script.py
  python exec_remote.py --ls /content/drive/MyDrive/diploma_plan_sql/outputs
  python exec_remote.py --download /content/drive/.../tarball.tar.gz --to ./local.tar.gz

URL is read from (in order):
  1. --url <https://...> CLI flag
  2. tools/.bridge_url file
  3. environment variable BRIDGE_URL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Force UTF-8 stdout/stderr; avoids UnicodeEncodeError in cp1251 Windows console.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

URL_FILE = Path(r"D:\HSE\Диплом\NL2BI-AI-assistant\tools\.bridge_url")


def resolve_url(cli_url: str | None) -> str:
    if cli_url:
        return cli_url.rstrip("/")
    # Phase 26: per-session URL via env BRIDGE_URL_FILE (e.g., tools/.bridge_url_dbt)
    env_file = os.environ.get("BRIDGE_URL_FILE")
    if env_file:
        p = Path(env_file)
        if p.exists():
            return p.read_text(encoding="utf-8").strip().rstrip("/")
    if URL_FILE.exists():
        return URL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
    env = os.environ.get("BRIDGE_URL")
    if env:
        return env.rstrip("/")
    print("error: bridge URL not provided. Either pass --url, write to "
          f"{URL_FILE}, or set BRIDGE_URL env var.", file=sys.stderr)
    sys.exit(2)


def http_post_json(url: str, payload: dict, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except Exception:
            return {"ok": False, "http_status": e.code, "body": body}


def http_get_json(url: str, timeout: int = 60) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except Exception:
            return {"ok": False, "http_status": e.code, "body": body}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="Bridge URL override")
    ap.add_argument("--health", action="store_true",
                    help="GET /health to verify bridge is up")
    ap.add_argument("--code", help="Python code to exec remotely")
    ap.add_argument("--code-file", help="Path to .py file whose contents to exec")
    ap.add_argument("--ls", help="List a remote directory")
    ap.add_argument("--download", help="Remote file path to download")
    ap.add_argument("--to", help="Local destination for --download")
    ap.add_argument("--timeout", type=int, default=600, help="HTTP timeout (s)")
    args = ap.parse_args()

    base = resolve_url(args.url)

    if args.health:
        result = http_get_json(f"{base}/health")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("ok") else 1)

    if args.code or args.code_file:
        code = args.code if args.code else Path(args.code_file).read_text(encoding="utf-8")
        result = http_post_json(f"{base}/exec", {"code": code}, timeout=args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("ok") else 1)

    if args.ls:
        url = f"{base}/ls?path=" + urllib.parse.quote(args.ls)
        result = http_get_json(url, timeout=args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("ok") else 1)

    if args.download:
        if not args.to:
            print("error: --to is required with --download", file=sys.stderr)
            sys.exit(2)
        url = f"{base}/file?path=" + urllib.parse.quote(args.download)
        out = Path(args.to)
        out.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=args.timeout) as r:
            with out.open("wb") as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
        size = out.stat().st_size
        print(json.dumps({"ok": True, "downloaded_to": str(out),
                          "size_bytes": size}, ensure_ascii=False, indent=2))
        sys.exit(0)

    ap.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
