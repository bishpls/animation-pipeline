"""Reference images (art direction only: style targets, model/pose sheets). Never used as frames.

    .venv/bin/python tools/imagegen.py "prompt" OUT.png [--model gemini-3-pro-image] [--ref in.png ...]

Gemini image models (nano-banana-pro = gemini-3-pro-image). Logged to tools/ledger.jsonl.
"""
import base64, json, mimetypes, os, sys, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = next(l.strip().split('=', 1)[1] for l in open(os.path.join(ROOT, '.env')) if l.startswith('GEMINI_API_KEY='))

a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
prompt, out = a[0], a[1]
model = opt('--model', 'gemini-3-pro-image')
refs = [a[i + 1] for i, x in enumerate(a) if x == '--ref']
parts = [{'inline_data': {'mime_type': mimetypes.guess_type(r)[0], 'data': base64.b64encode(open(r, 'rb').read()).decode()}} for r in refs]
parts.append({'text': prompt})
body = {'contents': [{'parts': parts}], 'generationConfig': {'responseModalities': ['IMAGE', 'TEXT'], 'imageConfig': {'aspectRatio': opt('--aspect', '16:9')}}}
t0 = time.time()
r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={KEY}', json=body, timeout=600)
j = r.json()
ok = False
for p in j.get('candidates', [{}])[0].get('content', {}).get('parts', []):
    if 'inlineData' in p or 'inline_data' in p:
        d = p.get('inlineData') or p.get('inline_data')
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        open(out, 'wb').write(base64.b64decode(d['data'])); ok = True
    elif 'text' in p:
        print(p['text'][:500])
with open(os.path.join(ROOT, 'tools', 'ledger.jsonl'), 'a') as f:
    f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'service': 'gemini', 'op': 'image', 'model': model, 'out': out, 'ok': ok}) + '\n')
print('wrote' if ok else 'FAILED', out, f'{time.time() - t0:.0f}s', '' if ok else json.dumps(j)[:800])
