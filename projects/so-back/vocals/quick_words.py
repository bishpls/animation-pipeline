"""Build every word recipe, write W/words/<kind>_<name>.wav, and a first STT pass (small.en) on each word alone."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import words, judge
os.makedirs(f'{W}/words', exist_ok=True)
for kind, recipes in words.WORDS.items():
    for name in recipes:
        y, js, sp = words.word(kind, name)
        write(f'{W}/words/{kind}_{name}.wav', y)
        print(f'{kind:5s} {name:22s} {len(y)/SR:.2f}s  small:{judge.transcribe(y, "small.en")!r}', flush=True)
