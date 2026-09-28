"""ElevenLabs Music: compose a song from a composition plan, keeping audio + word timestamps + metadata.

    .venv/bin/python tools/music.py compose PLAN.json OUT_DIR/take_name [--model music_v2_5]
    .venv/bin/python tools/music.py plan "prompt" 60000          # ask the model for a starting plan

Uses the detailed streaming endpoint so every take arrives with its word timestamps (lyric sync for free).
Every call is appended to tools/ledger.jsonl.
"""
import base64, json, os, sys, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = 'https://api.elevenlabs.io/v1'


def env(k):
    for line in open(os.path.join(ROOT, '.env')):
        if line.startswith(k + '='):
            return line.strip().split('=', 1)[1]
    return os.environ.get(k)


KEY = env('ELEVENLABS_API_KEY')


def ledger(**kw):
    with open(os.path.join(ROOT, 'tools', 'ledger.jsonl'), 'a') as f:
        f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), **kw}) + '\n')


def compose(plan_path, out, model='music_v2_5'):
    plan = json.load(open(plan_path))
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    # store_for_inpainting: keep a song_id so a single flubbed section/word can be regenerated later without redoing the take
    # (HELLO, WORLD!'s mispronounced 'arigatou' was unfixable only because this was off). song_id lands in OUT.events.jsonl.
    body = {'composition_plan': plan, 'model_id': model, 'with_timestamps': True, 'store_for_inpainting': True}
    t0 = time.time()
    r = requests.post(f'{API}/music/detailed/stream?output_format=mp3_48000_320', headers={'xi-api-key': KEY},
                      json=body, stream=True, timeout=900)
    if r.status_code != 200:
        print(r.status_code, r.text[:2000]); sys.exit(1)
    audio, events = bytearray(), []
    raw = open(out + '.events.jsonl', 'w')
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith('data:'):
            continue
        data = line[5:].strip()
        try:
            ev = json.loads(data)
        except Exception:
            continue
        # audio arrives base64 in some field; keep everything else verbatim
        for k in ('audio', 'audio_base64', 'chunk'):
            if isinstance(ev.get(k), str) and len(ev[k]) > 200:
                audio += base64.b64decode(ev[k]); ev[k] = f'<{len(ev[k])} b64>'
        raw.write(json.dumps(ev) + '\n'); events.append(ev)
    raw.close()
    open(out + '.mp3', 'wb').write(audio)
    dur = sum(c.get('duration_ms', 0) for c in plan['chunks']) / 1000
    ledger(service='elevenlabs', op='music.compose', model=model, seconds=dur, out=out, wall=round(time.time() - t0))
    print(f'wrote {out}.mp3 ({len(audio) / 1e6:.1f} MB), {len(events)} events, {time.time() - t0:.0f}s')


def plan(prompt, ms, model='music_v2_5'):
    r = requests.post(f'{API}/music/plan', headers={'xi-api-key': KEY},
                      json={'prompt': prompt, 'music_length_ms': int(ms), 'model_id': model})
    print(json.dumps(r.json(), indent=2))


if __name__ == '__main__':
    a = sys.argv[1:]
    model = a[a.index('--model') + 1] if '--model' in a else 'music_v2_5'
    if a[0] == 'compose':
        compose(a[1], a[2], model)
    elif a[0] == 'plan':
        plan(a[1], a[2], model)
