"""Gemini as a critic, with every call logged to tools/ledger.jsonl (tools/gemini.py doesn't log). Same upload path.

    .venv/bin/python projects/t/critic.py FILE [FILE ...] --prompt "..." [--out notes.md] [--op label]
"""
import json, os, sys, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gemini import upload, KEY, BASE  # noqa: E402

MODEL = 'gemini-3.1-pro-preview'


def ask(files, prompt, op):
    parts = []
    for p in files:
        for attempt in range(4):              # a video can come back before it's ACTIVE, and processing sometimes FAILs: re-upload
            uri, mime = upload(p)
            for _ in range(100):
                st = requests.get(f'{BASE}/v1beta/files/{uri.rsplit("/", 1)[1]}?key={KEY}').json().get('state')
                if st in ('ACTIVE', 'FAILED'):
                    break
                time.sleep(3)
            if st == 'ACTIVE':
                break
            time.sleep(5)
        parts +=[{'text': f'[{os.path.basename(p)}]'}, {'file_data': {'mime_type': mime, 'file_uri': uri}}]
    parts.append({'text': prompt})
    t0 = time.time()
    r = requests.post(f'{BASE}/v1beta/models/{MODEL}:generateContent?key={KEY}', json={'contents': [{'parts': parts}]}, timeout=900)
    j = r.json()
    u = j.get('usageMetadata', {})
    with open(os.path.join(ROOT, 'tools', 'ledger.jsonl'), 'a') as f:
        f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'service': 'gemini', 'op': op, 'model': MODEL, 'film': 't',
                            'files': [os.path.relpath(p, ROOT) for p in files], 'input_tokens': u.get('promptTokenCount'),
                            'output_tokens': (u.get('candidatesTokenCount') or 0) + (u.get('thoughtsTokenCount') or 0),
                            'wall': round(time.time() - t0)}) + '\n')
    try:
        return ''.join(p.get('text', '') for p in j['candidates'][0]['content']['parts'])
    except Exception:
        return json.dumps(j, indent=1)[:3000]


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    files = [x for i, x in enumerate(a) if not x.startswith('--') and (i == 0 or not a[i - 1].startswith('--'))]
    out = ask(files, opt('--prompt'), opt('--op', 'review'))
    if opt('--out'):
        open(opt('--out'), 'w').write(out)
    print(out)
