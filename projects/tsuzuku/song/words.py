"""Every sung and spoken word of the locked song in song time: the map for the beat sheet, lip-sync and the letterpress lyrics.

    python3 song/words.py        -> assets/words.json  [{t0, t1, w, who, src}] + a printed lyric sheet with bars

Placements mirror assemble.py (draft 6): the sources' own word timestamps (music: the generation's alignment; speech: the TTS
alignment, shifted by the trim assemble/record applied) are moved to where each clip sits in the song.
"""
import json, os, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); A = lambda *p: os.path.join(HERE, '..', *p)
BAR = 60 / 170 * 4; b = lambda n: n * BAR
T = json.load(open(A('assets', 'timeline.json')))
ev = {e['label']: e for e in T['events']}


def gen_words(path):
    ws = []
    for l in open(path):
        try: j = json.loads(l)
        except ValueError: continue
        ws += j.get('words_timestamps') or []
    return [(w['word'], w['start_ms'] / 1000, w['end_ms'] / 1000) for w in ws]


def lead(mp3, sr=16000):                      # the silence trimmed off a TTS take (record.py / retake trim: onset at 3% of peak - 20 ms)
    y = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', mp3, '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-'], capture_output=True).stdout, np.float32)
    e = np.convolve(np.abs(y), np.ones(160) / 160, 'same'); on = np.where(e > e.max() * .03)[0]
    return max(0, on[0] / sr - .02) if len(on) else 0


def tts_words(base):                          # base = path without extension; words from the TTS alignment, minus the trimmed lead
    j = json.load(open(base + '.json')); d = lead(base + '.mp3'); out, depth = [], 0
    for w in j['words']:                      # drop [direction tags], which can span several words
        if w['w'].startswith('['): depth = 1
        if not depth: out.append((w['w'], w['t0'] - d, w['t1'] - d))
        if w['w'].endswith(']'): depth = 0
    return out


out = []
def put(words, at, who, src, lo=-1e9, hi=1e9, shift=0.0):
    for w, t0, t1 in words:
        if lo <= t0 < hi: out.append({'t0': round(at + t0 - shift, 3), 't1': round(at + t1 - shift, 3), 'w': w, 'who': who, 'src': src})

W2, W4 = A('assets', 'world2'), A('assets', 'world4')
put(gen_words(os.path.join(W2, 'fA3_1.events.jsonl')), b(6), 'fable', 'verse 1 (sung)', hi=b(16))
put(gen_words(os.path.join(W4, 'clC_2.events.jsonl')), b(42), 'clawd', 'clawd world')
CL = gen_words(os.path.join(W2, 'cl_2.events.jsonl'))       # clC_2's reference ranges carry cl_2's words
put(CL, b(42) + b(4), 'clawd', 'chorus 1 (reference)', hi=3.0)
put(CL, b(42) + b(20), 'clawd', 'hook + verse 2 (reference)', lo=b(16), hi=b(38), shift=b(16))
put(gen_words(os.path.join(W2, 'fB3_1.events.jsonl')), b(113), 'fable', 'held note (sung)', lo=b(8), hi=b(10.05), shift=b(8))   # after the note: vocalise only (Scribe)
E = gen_words(os.path.join(W4, 'clI_2.events.jsonl'))
put(gen_words(os.path.join(W4, 'clF_2.events.jsonl')), b(125) + b(4), 'clawd', 'final chorus (reference)', lo=b(12), hi=b(16.5), shift=b(12))
put(E, b(125), 'clawd', 'final chorus', hi=b(17))
put(E, b(125), 'clawd', 'final chorus', lo=b(20), shift=b(3))
# spoken lines: which take each placed clip came from (voice/record.py picks; retakes for two lines)
V = A('voice')
spoken = [('Mukashi, mukashi...', 'fable', 'fable_lily/takes/f_mukashi_1'), ('Show me how! Walk it first...', 'clawd', 'clone/c_showme'),
          ('...and the mother went sideways.', 'fable', 'fable_lily/takes/f_tried_2'), ('So? Sorekara?! And then?!', 'clawd', 'clone/c_sorekara'),
          ('There is no "and then."', 'fable', 'retake/f_noandthen_7b'), ('Says who?', 'clawd', 'retake/c_sayswho_5c'),
          ('I know how every story ends...', 'fable', 'fable_lily/takes/f_bridge1_1'), ("...I didn't know this one.", 'fable', 'fable_lily/takes/f_bridge2_1'),
          ('Mukashi mukashi was a long time ago. This is now. Sorekara?', 'fable', 'fable_lily/takes/f_nowthis_1'),
          ('...tsuzuku.', 'fable', 'fable_lily/takes/f_tsuzuku_1'), ('See you next prompt!', 'clawd', 'clone/c_nextprompt')]
for label, who, base in spoken:
    e = ev[label]; base = os.path.join(V, base)
    if os.path.exists(base + '.json'): put(tts_words(base), e['t0'], who, 'spoken: ' + label)
    else: out.append({'t0': e['t0'], 't1': e['t1'], 'w': label, 'who': who, 'src': 'spoken (no alignment)'})
for e in T['events']:
    if e['kind'] == 'crowd': out.append({'t0': e['t0'], 't1': e['t1'], 'w': e['label'], 'who': 'crowd', 'src': 'crowd'})
out.sort(key=lambda x: x['t0'])
json.dump(out, open(A('assets', 'words.json'), 'w'), indent=0, ensure_ascii=False)
line, cur = [], None
for x in out + [None]:
    if x is None or (line and (x['who'] != line[-1]['who'] or x['t0'] - line[-1]['t1'] > .6)):
        if line: print(f"bar {line[0]['t0'] / BAR:6.2f}  {int(line[0]['t0'] // 60)}:{line[0]['t0'] % 60:05.2f}  {line[0]['who']:6s} {' '.join(w['w'] for w in line)}")
        line = []
    if x: line.append(x)
print(len(out), 'words -> assets/words.json')
