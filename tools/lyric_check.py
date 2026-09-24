"""Objective lyric intelligibility: transcribe a take with ElevenLabs Scribe and diff it against the intended lyrics.

    .venv/bin/python tools/lyric_check.py TAKE.mp3 [TAKE2.mp3 ...]

Needs TAKE.events.jsonl (intended words + times per section). Prints per-section word accuracy and the words that
the transcriber didn't hear, with times: those are the spots a listener will stumble on too.
Caches transcripts next to the take (TAKE.stt.json).
"""
import difflib, json, os, re, sys
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = next(l.strip().split('=', 1)[1] for l in open(os.path.join(ROOT, '.env')) if l.startswith('ELEVENLABS_API_KEY='))
norm = lambda w: re.sub(r"[^a-z0-9]", '', w.lower().replace('’', "'"))


def stt(path):
    cache = re.sub(r'\.mp3$', '.stt.json', path)
    if os.path.exists(cache):
        return json.load(open(cache))
    r = requests.post('https://api.elevenlabs.io/v1/speech-to-text', headers={'xi-api-key': KEY},
                      data={'model_id': 'scribe_v2', 'timestamps_granularity': 'word', 'tag_audio_events': 'false'},
                      files={'file': open(path, 'rb')}, timeout=600)
    j = r.json()
    json.dump(j, open(cache, 'w'))
    return j


for path in sys.argv[1:]:
    j = stt(path)
    heard = [(norm(w['text']), w['start']) for w in j.get('words', []) if w.get('type') == 'word' and norm(w['text'])]
    want = []
    for line in open(re.sub(r'\.mp3$', '.events.jsonl', path)):
        e = json.loads(line)
        for w in e.get('words_timestamps', []):
            if not (w['word'].startswith('{') or w['word'].endswith('}')) and norm(w['word']):
                want.append((norm(w['word']), w['start_ms'] / 1000, e['chunk']['text'].split(']')[0][1:]))
    sm = difflib.SequenceMatcher(a=[w for w, *_ in want], b=[w for w, _ in heard], autojunk=False)
    ok = [False] * len(want)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            ok[blk.a + k] = True
    secs = {}
    for (w, t, s), g in zip(want, ok):
        secs.setdefault(s, [0, 0]); secs[s][0] += g; secs[s][1] += 1
    tot = sum(ok) / len(ok)
    print(f'\n{os.path.basename(path)}  word accuracy {tot * 100:.0f}%   ' +
          '  '.join(f'{s.split(" -")[0]}:{a}/{n}' for s, (a, n) in secs.items()))
    missed = [(t, w) for (w, t, s), g in zip(want, ok) if not g]
    print('  missed:', ' '.join(f'{t:.1f}:{w}' for t, w in missed))
