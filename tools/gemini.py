"""Second opinion from Gemini on any media file (audio, video, image): upload + prompt.

    .venv/bin/python tools/gemini.py FILE [FILE ...] --prompt "..." [--model gemini-3.1-pro-preview] [--out notes.md]

Gemini hears audio and watches video. Treat it as a critic, not an oracle: it's useful for catching
things you can't perceive directly (vocal clarity, mix problems, seams, pacing felt at full speed).
"""
import json, mimetypes, os, sys, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = next(l.strip().split('=', 1)[1] for l in open(os.path.join(ROOT, '.env')) if l.startswith('GEMINI_API_KEY='))
BASE = 'https://generativelanguage.googleapis.com'


def upload(path):
    mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    size = os.path.getsize(path)
    r = requests.post(f'{BASE}/upload/v1beta/files?key={KEY}', headers={
        'X-Goog-Upload-Protocol': 'resumable', 'X-Goog-Upload-Command': 'start',
        'X-Goog-Upload-Header-Content-Length': str(size), 'X-Goog-Upload-Header-Content-Type': mime,
        'Content-Type': 'application/json'}, json={'file': {'display_name': os.path.basename(path)}})
    url = r.headers['X-Goog-Upload-URL']
    r = requests.post(url, headers={'X-Goog-Upload-Offset': '0', 'X-Goog-Upload-Command': 'upload, finalize'},
                      data=open(path, 'rb').read())
    f = r.json()['file']
    while f.get('state') == 'PROCESSING':
        time.sleep(3)
        f = requests.get(f'{BASE}/v1beta/{f["name"]}?key={KEY}').json()
    return f['uri'], mime


def ask(files, prompt, model='gemini-3.1-pro-preview'):
    parts = []
    for p in files:
        uri, mime = upload(p)
        parts += [{'text': f'[{os.path.basename(p)}]'}, {'file_data': {'mime_type': mime, 'file_uri': uri}}]
    parts.append({'text': prompt})
    r = requests.post(f'{BASE}/v1beta/models/{model}:generateContent?key={KEY}',
                      json={'contents': [{'parts': parts}]}, timeout=900)
    j = r.json()
    try:
        return ''.join(p.get('text', '') for p in j['candidates'][0]['content']['parts'])
    except Exception:
        return json.dumps(j, indent=1)[:3000]


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    files = [x for i, x in enumerate(a) if not x.startswith('--') and (i == 0 or not a[i - 1].startswith('--'))]
    out = ask(files, opt('--prompt'), opt('--model', 'gemini-3.1-pro-preview'))
    if opt('--out'):
        open(opt('--out'), 'w').write(out)
    print(out)
