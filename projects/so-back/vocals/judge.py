"""Objective judges for spliced phrases (a name-call splice method, generalised to phrases):
  1. Whisper free transcription (small.en, medium.en, turbo), alone and in context (after a real announcer phrase);
  2. Whisper forced choice: teacher-forced log-likelihood of the target phrase (and its spellings) against near-miss
     strings, softmaxed over the set -> P(hit);
  3. wav2vec2 phoneme CTC: the target IPA against near-miss IPA strings, and per-slot choices;
  4. seams: MFCC distance across +-10 ms as a percentile of all natural 20 ms steps in the announcer's real clips, and
     the F0 step across each seam.
Judges only; neither of us can listen. The user decides by ear."""
import os, sys, glob, json, warnings
warnings.filterwarnings('ignore')
import numpy as np, soundfile as sf, librosa, torch, whisper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from hf0 import hf0
import phones

_models = {}
def model(name):
    if name not in _models:
        _models[name] = whisper.load_model(name, device='cpu')
    return _models[name]

def transcribe(x, name, sr=SR):
    y = librosa.resample(np.asarray(x, np.float32), orig_sr=sr, target_sr=16000) if sr != 16000 else np.asarray(x, np.float32)
    r = model(name).transcribe(y.astype(np.float32), fp16=False, language='en', temperature=0.0)
    return r['text'].strip()

def forced(x, hits, misses, name='small.en', sr=SR):
    m = model(name)
    tok = whisper.tokenizer.get_tokenizer(multilingual=m.is_multilingual, language='en', task='transcribe')
    y = librosa.resample(np.asarray(x, np.float32), orig_sr=sr, target_sr=16000)
    audio = whisper.pad_or_trim(torch.tensor(y, dtype=torch.float32))
    mel = whisper.log_mel_spectrogram(audio, n_mels=m.dims.n_mels)[None]
    with torch.no_grad():
        enc = m.encoder(mel)
        scores = {}
        for text in hits + misses:
            ids = list(tok.sot_sequence_including_notimestamps) + tok.encode(text) + [tok.eot]
            t = torch.tensor([ids])
            lp = torch.log_softmax(m.decoder(t[:, :-1], enc), -1)[0]
            n0 = len(tok.sot_sequence_including_notimestamps)
            scores[text] = sum(lp[i - 1, ids[i]].item() for i in range(n0, len(ids)))
    v = np.array(list(scores.values())); p = np.exp(v - v.max()); p /= p.sum()
    probs = dict(zip(scores, p))
    best_miss = max(misses, key=lambda k: scores[k])
    return float(sum(probs[h] for h in hits)), best_miss.strip(), float(probs[best_miss])

def mfcc_frames(x, sr=SR):
    return librosa.feature.mfcc(y=np.asarray(x, float), sr=sr, n_mfcc=13, n_fft=256, win_length=240, hop_length=24,
                                n_mels=40, fmax=6000, center=True)[1:]

_nat = None
def natural_dist():
    """MFCC distances between frames 20 ms apart inside all real US announcer clips (voiced or not, above -20 dB)."""
    global _nat
    if _nat is None:
        cache = os.path.join(W, 'natural_mfcc_steps.npy')
        if os.path.exists(cache):
            _nat = np.load(cache)
        else:
            d = []
            for k in REG:
                if k.startswith('jp_'): continue
                x = load(k); M = mfcc_frames(x)
                e = librosa.feature.rms(y=x, frame_length=240, hop_length=24)[0]
                for i in range(0, M.shape[1] - 10):
                    if e[i] > 0.1 * e.max() and e[i + 10] > 0.1 * e.max():
                        d.append(np.linalg.norm(M[:, i] - M[:, i + 10]))
            _nat = np.sort(np.array(d)); np.save(cache, _nat)
    return _nat

def seam(x, t):
    M = mfcc_frames(x); i = int(round(t * SR / 24)); a, b = i - 5, i + 5
    if a < 0 or b >= M.shape[1]: return None, None
    d = float(np.linalg.norm(M[:, a] - M[:, b])); nat = natural_dist()
    return round(d, 1), round(100.0 * np.searchsorted(nat, d) / len(nat), 1)

def seam_pitch(x, t):
    tt, f0, sc, v = hf0(x, SR, hop=0.005, fmin=85, fmax=480)
    def med(lo, hi):
        k = (tt >= lo) & (tt <= hi) & v
        return float(np.median(f0[k])) if k.sum() else None
    fa, fb = med(t - 0.030, t - 0.005), med(t + 0.005, t + 0.030)
    return (round(12 * np.log2(fb / fa), 2) if fa and fb else None)

CTX = 'nr_1p_02'    # "Continue?" as the context phrase (not a source of any recipe)

def evaluate(x, spec, models=('small.en', 'medium.en', 'turbo'), forced_models=('small.en', 'medium.en'), joins=()):
    """spec: dict(hits=[...], misses=[...], ipa='...', ipa_alts=[...])"""
    r = {}
    for mname in models:
        r['stt_' + mname] = transcribe(x, mname)
    ctx = np.concatenate([load(CTX), np.zeros(int(0.35 * SR)), x])
    for mname in models:
        r['ctx_' + mname] = transcribe(ctx, mname)
    for mname in forced_models:
        ph, bm, pm = forced(x, spec['hits'], spec['misses'], mname)
        r['phit_' + mname] = round(ph, 3); r['miss_' + mname] = f'{bm} ({pm:.2f})'
    lp = phones.logprobs(x, SR)
    pt, alt, pa = phones.choice(lp, spec['ipa'], spec['ipa_alts'])
    r['phone_p'] = round(pt, 3); r['phone_alt'] = f'{alt} ({pa:.2f})'
    r['seams'] = [dict(t=round(t, 3), pct=seam(x, t)[1], f0_st=seam_pitch(x, t)) for t in joins]
    return r

def hit(text, targets):
    t = ''.join(c for c in text.lower() if c.isalpha() or c == ' ').split()
    t = ' '.join(t)
    return any(g in t for g in targets)

def rank(x, texts, name='small.en', sr=SR):
    """Softmax over teacher-forced log-likelihoods of each text (one encoder pass): [(p, text)] best first."""
    p, _, _ = None, None, None
    m = model(name)
    tok = whisper.tokenizer.get_tokenizer(multilingual=m.is_multilingual, language='en', task='transcribe')
    y = librosa.resample(np.asarray(x, np.float32), orig_sr=sr, target_sr=16000)
    mel = whisper.log_mel_spectrogram(whisper.pad_or_trim(torch.tensor(y, dtype=torch.float32)), n_mels=m.dims.n_mels)[None]
    with torch.no_grad():
        enc = m.encoder(mel); s = []
        for text in texts:
            ids = list(tok.sot_sequence_including_notimestamps) + tok.encode(text) + [tok.eot]
            t = torch.tensor([ids]); lp = torch.log_softmax(m.decoder(t[:, :-1], enc), -1)[0]
            n0 = len(tok.sot_sequence_including_notimestamps)
            s.append(sum(lp[i - 1, ids[i]].item() for i in range(n0, len(ids))))
    s = np.array(s); p = np.exp(s - s.max()); p /= p.sum()
    return sorted(zip(p.tolist(), texts), reverse=True)
