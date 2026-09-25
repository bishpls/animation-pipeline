"""Singing voice conversion with Seed-VC (vendor/seed-vc, GPL-3.0 tool; not committed). Pitch-preserving: f0-conditioned.

    .venv/bin/python tools/revoice.py IN.wav REF.wav OUT.wav [--steps 30] [--semitones 0]
    .venv/bin/python tools/revoice.py --check IN.wav OUT.wav REF.wav     # measure pitch preservation + speaker similarity

Measured on the duet probe (7.4 s of sung vocal): 0-cent median offset, contour corr 0.97, 88% of frames within 50 cents;
speaker similarity to the reference rose 0.67 -> 0.89 (Resemblyzer cosine). CPU-only here (torch has no MPS on macOS 13):
about 30x real time, so convert only the lines that need it. References: projects/<film>/voice/REF_<member>.wav (<= 30 s, clean, solo).
"""
import glob, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVC = os.path.join(ROOT, 'vendor', 'seed-vc')
PY = os.path.join(SVC, '.venv', 'bin', 'python')


def convert(src, ref, out, steps=30, semitones=0):
    tmp = tempfile.mkdtemp()
    subprocess.run([PY, 'inference.py', '--source', os.path.abspath(src), '--target', os.path.abspath(ref), '--output', tmp,
                    '--diffusion-steps', str(steps), '--f0-condition', 'True', '--auto-f0-adjust', 'False',
                    '--semi-tone-shift', str(semitones), '--fp16', 'False'], cwd=SVC, check=True, capture_output=True)
    res = glob.glob(os.path.join(tmp, '*.wav'))[0]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); shutil.move(res, out); shutil.rmtree(tmp)
    return out


CHECK = r'''
import sys, subprocess, numpy as np, librosa
from resemblyzer import VoiceEncoder, preprocess_wav
src, out, ref = sys.argv[1:4]
def load(p):
    raw = subprocess.run(['ffmpeg','-v','error','-i',p,'-f','f32le','-ac','1','-ar','22050','-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32)
a, _, _ = librosa.pyin(load(src), fmin=70, fmax=1100, sr=22050); b, _, _ = librosa.pyin(load(out), fmin=70, fmax=1100, sr=22050)
m = min(len(a), len(b)); a, b = a[:m], b[:m]; k = ~np.isnan(a) & ~np.isnan(b)
d = 1200 * np.log2(b[k] / a[k]); off = np.median(d)
enc = VoiceEncoder(verbose=False); E = lambda p: enc.embed_utterance(preprocess_wav(p)); cos = lambda x, y: float(np.dot(x, y) / np.linalg.norm(x) / np.linalg.norm(y))
r = E(ref)
print(f'pitch: offset {off:+.0f}c, within 50c {np.mean(np.abs(d - off) < 50):.2f}, contour corr {np.corrcoef(a[k], b[k])[0,1]:.3f} | '
      f'speaker sim to ref: source {cos(E(src), r):.3f} -> converted {cos(E(out), r):.3f}')
'''

if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if a[0] == '--check':
        subprocess.run([PY, '-c', CHECK, a[1], a[2], a[3]], check=True)
    else:
        print('wrote', convert(a[0], a[1], a[2], int(opt('--steps', 30)), int(opt('--semitones', 0))))
