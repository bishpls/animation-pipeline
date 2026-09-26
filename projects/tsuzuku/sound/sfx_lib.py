"""The paper world's sound library (ElevenLabs sound effects, tools/sfx.py; logged). One file per sound, cached: delete one to
regenerate it. Each is trimmed of lead silence into sound/lib/<name>.wav (48 kHz mono). Quiet, dry, close: this is a tabletop
paper theatre, not a stage (SFX_CUES.md: "the song is locked; these sit quietly on top").

    ../../../.venv/bin/python sfx_lib.py
"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LIB = {  # name: (prompt, seconds)
 'match':      ('a single wooden match struck on a matchbox, crisp scrape and flare, then a tiny flame, close and dry, quiet room', 1.6),
 'paper_fold': ('one soft fold of stiff paper card, a dry crisp crease, close microphone, quiet room', .6),
 'fan_flick':  ('a Japanese folding paper fan flicked open in one quick motion, crisp paper ribs, close, dry', .6),
 'fan_shut':   ('a Japanese folding paper fan snapped shut, one crisp clack of bamboo ribs, close, dry', .5),
 'paper_tap':  ('one tiny tap of a small cut-paper puppet landing on a wooden rail, very light, dry, close', .3),
 'paper_slide':('a large sheet of card paper slid sideways out of a wooden frame, a smooth dry paper whisper, close', 1.2),
 'paper_tear': ('a large sheet of washi paper torn slowly then ripped apart, fibrous tearing, close and dramatic', 1.4),
 'snip':       ('a single snip of small paper scissors, one crisp cut, close, dry', .4),
 'rivet':      ('a tiny single punch click, a small hole punched in card, one sharp tick, close', .3),
 'geta':       ('one wooden geta sandal step on a wooden floor, a single hollow wooden clack, close, dry room', .5),
 'doors_open': ('two small wooden cabinet doors swung open, a soft wooden creak of little hinges, close, quiet', 1.2),
 'doors_shut': ('two small wooden cabinet doors swung closed, a soft wooden creak then a gentle wooden knock as they meet', 1.4),
 'stamp':      ('a small stone seal stamp pressed firmly onto paper, one soft muffled thock, close', .5),
 'lantern':    ('the bamboo handle ring of a paper lantern creaking softly as it is lifted, a small dry creak, close', .6),
 'lantern_set':('a paper lantern set down gently on a wooden floor, a soft light wooden tap, close', .4),
 'card_rack':  ('a stiff card slid into a wooden rack and set down, a soft dry wooden tap, close', .5),
 'led_off':    ('a small electric sign switching off, a tiny soft click and hum fading, close', .6),
 'cloth':      ('heavy cotton clothing rustling as someone kneels down on a cushion, a soft settle, close, quiet', 1.0),
 'hop':        ('a small paper puppet hopping, a light paper flutter then a soft tap landing, close, dry', .5),
 'press':      ("(not generated: the song's own letterpress thud, assets/sfx/press.mp3, copied in)", .5),
}

def gen(name):
    p, secs = LIB[name]; mp3 = os.path.join(HERE, 'lib', name + '.mp3')
    if not os.path.exists(mp3):
        subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'sfx.py'), p, mp3, str(max(.5, secs)), '.7'], check=True, capture_output=True)
    y = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', mp3, '-f', 'f32le', '-ac', '1', '-ar', '48000', '-'], capture_output=True).stdout, np.float32).copy()
    e = np.convolve(np.abs(y), np.ones(480) / 480, 'same'); on = np.where(e > e.max() * .05)[0]; tail = np.where(e > e.max() * .01)[0]
    y = y[max(0, on[0] - 96):min(len(y), tail[-1] + 7200)] if len(on) else y   # the lead trimmed hard, the decay kept to 1% + 150 ms
    n = min(len(y), 7200); y[-n:] *= np.linspace(1, 0, n)                     # fade the tail
    sf.write(os.path.join(HERE, 'lib', name + '.wav'), y, 48000)
    return name, len(y) / 48000

if __name__ == '__main__':
    names = sys.argv[1:] or list(LIB)
    with ThreadPoolExecutor(4) as ex:
        for n, d in ex.map(gen, names): print(f'{n:12s} {d:5.2f}s')
