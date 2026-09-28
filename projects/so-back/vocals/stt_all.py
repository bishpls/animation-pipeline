"""First pass: Whisper word timestamps (turbo) for every announcer clip -> W/stt_turbo.json."""
import whisper, glob, os, json, warnings, sys
warnings.filterwarnings('ignore')
A = os.path.expanduser('~/games/melee/work/announcer')
W = os.path.expanduser('~/games/melee/work/soback/vocals')
files = sorted(glob.glob(A + '/names/nr_name_*.wav'))
for b in ['nr_select', 'nr_vs', 'nr_1p', 'nr_title', 'nr_name_jp']:
    files += sorted(glob.glob(f'{A}/banks/{b}/*.wav'))
import soundfile as sf
files += [f for f in sorted(glob.glob(A + '/banks/main/*.wav')) if sf.info(f).samplerate == 12000]
if os.environ.get('US_ONLY'):
    files = [f for f in files if '/nr_name_jp/' not in f and '/main/' not in f]
m = whisper.load_model(sys.argv[1] if len(sys.argv) > 1 else 'turbo', device='cpu')
out = {}
for f in files:
    key = os.path.relpath(f, A)
    r = m.transcribe(f, fp16=False, language='en', temperature=0.0, word_timestamps=True)
    words = [dict(w=w['word'].strip(), t0=round(w['start'], 3), t1=round(w['end'], 3), p=round(w['probability'], 3))
             for s in r['segments'] for w in s['words']]
    out[key] = dict(text=r['text'].strip(), words=words)
    print(key, '|', r['text'].strip(), flush=True)
json.dump(out, open(f'{W}/stt_{sys.argv[1] if len(sys.argv) > 1 else "turbo"}.json', 'w'), indent=1)
