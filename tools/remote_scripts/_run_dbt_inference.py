"""Local helper: take a prompt.txt + task_id, send via bridge, decode response.

Usage:
    python tools/remote_scripts/_run_dbt_inference.py asana001 [max_new=1500]
"""
import base64, json, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: _run_dbt_inference.py <TASK_ID> [MAX_NEW]'); return 2
    iid = sys.argv[1]
    max_new = int(sys.argv[2]) if len(sys.argv) > 2 else 1500

    prompt_path = REPO / 'data' / 'spider2_dbt' / 'tasks' / iid / 'prompt.txt'
    if not prompt_path.exists():
        print(f'FAIL: {prompt_path} not found. Run build_model_prompt.py first.'); return 3
    prompt = prompt_path.read_text(encoding='utf-8')
    print(f'PROMPT chars={len(prompt)}')

    template = (REPO / 'tools' / 'remote_scripts' / '_dbt_inference_one.py').read_text(encoding='utf-8')
    code = (template
              .replace('__PROMPT_B64__',
                       base64.b64encode(prompt.encode('utf-8')).decode('ascii'))
              .replace('__TASK_ID__', iid)
              .replace('__MAX_NEW__', str(max_new)))

    proc = subprocess.run(
        [sys.executable, str(REPO / 'tools' / 'exec_remote.py'),
          '--code', code, '--timeout', '600'],
        capture_output=True, text=True, encoding='utf-8',
    )
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    if proc.returncode != 0:
        print(f'EXEC_FAIL: {proc.stdout[-2000:]}\n{proc.stderr[-500:]}')
        return 4
    envelope = json.loads(proc.stdout)
    remote = envelope.get('stdout', '')
    s = remote.find('---RESPONSE_B64_BEGIN---')
    e = remote.find('---RESPONSE_B64_END---')
    if s < 0 or e < 0:
        print('NO_MARKERS in remote stdout:'); print(remote[-2000:]); return 5
    b64 = remote[s+len('---RESPONSE_B64_BEGIN---'):e].strip()
    response = base64.b64decode(b64).decode('utf-8')
    out = REPO / 'data' / 'spider2_dbt' / 'tasks' / iid / 'model_response.txt'
    out.write_text(response, encoding='utf-8')
    # Print envelope's diagnostic lines (stripped of base64)
    for ln in remote.splitlines():
        if 'B64_BEGIN' in ln or 'B64_END' in ln: continue
        if len(ln) > 200 and not ln.startswith('FIRST'): continue
        print(ln)
    print(f'\nWROTE {out} ({len(response)} chars)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
