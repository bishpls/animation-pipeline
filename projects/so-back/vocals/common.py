"""SO BACK vocals: shared paths, the announcer clip registry and the analysis helpers.

Every sound here is the Melee announcer's own recording (Michael's US 1.02 disc, decoded from the disc's sound banks into
~/games/melee/work/announcer, which this code only reads). Audio outputs go to ~/games/melee/work/soback/vocals
(game-derived audio never enters the repo). Local recognizers (Whisper, wav2vec2 phoneme CTC) are used only to judge.
"""
import os, json, glob, warnings
import numpy as np, soundfile as sf
warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.expanduser('~/games/melee/work/announcer')      # read-only (the decoded banks)
W = os.path.expanduser('~/games/melee/work/soback/vocals')  # our audio outputs
os.makedirs(W, exist_ok=True)
SR = 12000                                                  # the bank's native rate

# the registry: short key -> (path relative to A, true text). Texts are corrected by ear-proxy (three Whisper
# models) and by the game's own context (menu names); see INVENTORY.md for the raw STT.
def _names():
    out = {}
    for line in open(os.path.join(A, 'names', 'INDEX.tsv')).read().splitlines()[1:]:
        c = line.split('\t')
        out['name_%02d' % int(c[0])] = ('names/' + c[1], c[5])
    return out

TEXT_FIX = {
    'names/nr_name_09_id1485.wav': 'Giga Koopa', 'names/nr_name_17_id1493.wav': 'Koopa',
}
OTHER = {
    'nr_select': ['Multi-Man Melee!', 'Home-Run Contest!', 'Training Mode!', 'All-Star!', 'Choose your character!',
                  'Melee!', 'Event Match!', 'Grab the coins!', 'Survival!', 'Tournament Mode!', 'Camera Mode!',
                  'Stamina Mode!', 'Super Sudden Death!', 'Giant Melee!', 'Tiny Melee!', 'Invisible Melee!',
                  'Fixed Camera!', 'Single Button!', 'How to play!', 'Computer player!', 'Stock player removed.',
                  'Winner drops out!', 'Loser drops out.'],
    'nr_vs': ['No contest!', 'Sudden death.', 'Blue team!', 'Green team!', 'Red team!', "This game's winner is...",
              'WINS!'],
    'nr_1p': ['A new record!', 'Congratulations!', 'Continue?', 'Game over.', 'And...', 'Wow, incredible!',
              'Complete!', 'Bonus stage!', 'Failure.', 'Race to the Finish!', 'versus'],
    'nr_title': ['Nintendo All-Star!', 'Super Smash Brothers Melee!', 'Dairantou!', 'Smash Brothers!',
                 'Smash Brothers Melee!'],
}

def registry():
    reg = {}
    for k, (p, t) in _names().items():
        reg[k] = dict(path=p, text=TEXT_FIX.get(p, t))
    for bank, texts in OTHER.items():
        fs = sorted(glob.glob(os.path.join(A, 'banks', bank, '*.wav')), key=lambda f: int(f.split('_')[-2]))
        for f, t in zip(fs, texts):
            reg[os.path.basename(f)[:-4].rsplit('_id', 1)[0]] = dict(path=os.path.relpath(f, A), text=t)
    for f in sorted(glob.glob(os.path.join(A, 'banks', 'nr_name_jp', '*.wav'))):
        reg['jp_' + os.path.basename(f)[8:10]] = dict(path=os.path.relpath(f, A), text=None)  # JP names: STT only
    return reg

REG = registry()
_cache = {}

def load(key):
    """A registry key (or a path) -> float64 mono at 12 kHz."""
    if key not in _cache:
        p = os.path.join(A, REG[key]['path']) if key in REG else key
        x, sr = sf.read(p)
        if x.ndim > 1: x = x.mean(1)
        assert sr == SR, (key, sr)
        _cache[key] = x.astype(np.float64)
    return _cache[key]

def db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12)

def env_db(x, sr=SR, win=0.02, hop=0.005):
    n, h = int(win * sr), int(hop * sr)
    T = max(1, 1 + (len(x) - n) // h)
    e = np.array([np.sqrt(np.mean(x[i * h:i * h + n] ** 2) + 1e-12) for i in range(T)])
    return np.arange(T) * hop + win / 2, 20 * np.log10(e)

def tail_end(x, sr=SR, floor_db=-50):
    """Where the reverb tail falls below floor_db (relative to the clip's peak frame level)."""
    t, e = env_db(x, sr)
    k = np.where(e > e.max() + floor_db)[0]
    return float(t[k[-1]]) if len(k) else float(len(x) / sr)

def onset(x, sr=SR, rel_db=-30):
    t, e = env_db(x, sr)
    k = np.where(e > e.max() + rel_db)[0]
    return float(max(0.0, t[k[0]] - 0.01)) if len(k) else 0.0

def write(path, y, sr=SR):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.clip(y, -1, 1), sr, subtype='PCM_16')

def jdump(obj, path):
    json.dump(obj, open(path, 'w'), indent=1, ensure_ascii=False)
