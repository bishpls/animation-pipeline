"""ElevenLabs text-to-speech with character timestamps (for subtitles and lip/type sync).

    .venv/bin/python tools/tts.py "text" OUT_BASENAME [--voice JBFqnCBsd6RMkjVDRZzb] [--model eleven_v3] [--stability .5]

Writes OUT.mp3 and OUT.json: { text, chars:[...], starts:[s...], ends:[s...], words:[{w,t0,t1}] }. Logged to tools/ledger.jsonl.
"""
import base64, json, os, sys, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = next(l.strip().split('=', 1)[1] for l in open(os.path.join(ROOT, '.env')) if l.startswith('ELEVENLABS_API_KEY='))


def tts(text, out, voice='JBFqnCBsd6RMkjVDRZzb', model='eleven_v3', stability=.5, style=None, speed=None):
    vs = {'stability': stability, 'similarity_boost': .8}
    if style is not None: vs['style'] = style
    if speed is not None: vs['speed'] = speed
    r = requests.post(f'https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_192',
                      headers={'xi-api-key': KEY}, json={'text': text, 'model_id': model, 'voice_settings': vs}, timeout=300)
    if r.status_code != 200:
        print(r.status_code, r.text[:600]); sys.exit(1)
    j = r.json()
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    open(out + '.mp3', 'wb').write(base64.b64decode(j['audio_base64']))
    al = j.get('normalized_alignment') or j.get('alignment') or {}
    chars, st, en = al.get('characters', []), al.get('character_start_times_seconds', []), al.get('character_end_times_seconds', [])
    words, cur = [], None
    for c, a, b in zip(chars, st, en):
        if c.isspace():
            if cur: words.append(cur); cur = None
            continue
        if cur is None: cur = {'w': '', 't0': a, 't1': b}
        cur['w'] += c; cur['t1'] = b
    if cur: words.append(cur)
    json.dump({'text': text, 'chars': chars, 'starts': st, 'ends': en, 'words': words}, open(out + '.json', 'w'))
    with open(os.path.join(ROOT, 'tools', 'ledger.jsonl'), 'a') as f:
        f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'service': 'elevenlabs', 'op': 'tts', 'model': model, 'voice': voice, 'chars': len(text), 'out': out}) + '\n')
    print('wrote', out + '.mp3', f'{words[-1]["t1"] if words else 0:.2f}s', len(words), 'words')


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    tts(a[0], a[1], opt('--voice', 'JBFqnCBsd6RMkjVDRZzb'), opt('--model', 'eleven_v3'), float(opt('--stability', .5)),
        float(opt('--style')) if opt('--style') else None, float(opt('--speed')) if opt('--speed') else None)
