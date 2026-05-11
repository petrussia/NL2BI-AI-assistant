"""Helper: send a local script to the remote bridge /exec and print result."""
import urllib.request, json, sys

def invoke(bridge_path, script_path, endpoint='/exec', timeout=120):
    url = open(bridge_path, encoding='utf-8').read().strip() + endpoint
    code = open(script_path, encoding='utf-8').read()
    req = urllib.request.Request(
        url, data=json.dumps({'code': code}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode('utf-8'))
    print(d.get('stdout', ''))
    if d.get('stderr'):
        print('STDERR:', d['stderr'][:1000])
    if d.get('traceback'):
        print('TB:', d['traceback'][:1500])

if __name__ == '__main__':
    bridge = sys.argv[1] if len(sys.argv) > 1 else r'd:/HSE/Диплом/NL2BI-AI-assistant/tools/.bridge_url'
    script = sys.argv[2] if len(sys.argv) > 2 else None
    endpoint = sys.argv[3] if len(sys.argv) > 3 else '/exec'
    if script:
        invoke(bridge, script, endpoint=endpoint)
