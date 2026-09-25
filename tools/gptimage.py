"""OpenAI GPT Image: references, rig art and illustrated keys (code rigs and animates them; never used as finished frames).

    .venv/bin/python tools/gptimage.py "prompt" OUT.png [--model gpt-image-2.5-sunburst] [--size 2160x3840] [--quality high]
                                        [--transparent] [--ref in.png ...] [--n 1]

With --ref the edits endpoint is used (one or more reference images, `image[]`). Sizes: WxH, multiples of 16, long edge
<= 3840, up to 8.29 MP (above 2560x1440 is "experimental"). Quality: low | medium | high | xhigh | max | auto.
Models (Sept 2026): gpt-image-2.5-sunburst (editing precision), gpt-image-2.5-flare (fast), gpt-image-2. Logged to ledger.jsonl.
"""
import base64, json, os, sys, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = next(l.strip().split('=', 1)[1] for l in open(os.path.join(ROOT, '.env')) if l.startswith('OPENAI_API_KEY='))


def generate(prompt, out, model='gpt-image-2.5-sunburst', size='1024x1536', quality='high', transparent=False, refs=(), n=1):
    H = {'Authorization': 'Bearer ' + KEY}
    fields = {'model': model, 'prompt': prompt, 'size': size, 'quality': quality, 'n': str(n), 'output_format': 'png'}
    if transparent: fields['background'] = 'transparent'
    t0 = time.time()
    if refs:
        files = [('image[]', (os.path.basename(r), open(r, 'rb'), 'image/png')) for r in refs]
        r = requests.post('https://api.openai.com/v1/images/edits', headers=H, data=fields, files=files, timeout=900)
    else:
        r = requests.post('https://api.openai.com/v1/images/generations', headers=H, json={**fields, 'n': n}, timeout=900)
    j = r.json(); outs = []
    for k, d in enumerate(j.get('data', [])):
        p = out if n == 1 else out.replace('.png', f'_{k + 1}.png')
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True); open(p, 'wb').write(base64.b64decode(d['b64_json'])); outs.append(p)
    with open(os.path.join(ROOT, 'tools', 'ledger.jsonl'), 'a') as f:
        f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'service': 'openai', 'op': 'image', 'model': model, 'size': size, 'quality': quality,
                            'n': n, 'out': out, 'ok': bool(outs), 'usage': j.get('usage')}) + '\n')
    print(('wrote ' + ', '.join(outs)) if outs else 'FAILED ' + json.dumps(j)[:800], f'{time.time() - t0:.0f}s')
    return outs


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    generate(a[0], a[1], opt('--model', 'gpt-image-2.5-sunburst'), opt('--size', '1024x1536'), opt('--quality', 'high'), '--transparent' in a,
             [a[i + 1] for i, x in enumerate(a) if x == '--ref'], int(opt('--n', 1)))
