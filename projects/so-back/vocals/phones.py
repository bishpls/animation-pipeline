"""wav2vec2 phoneme CTC (facebook/wav2vec2-lv-60-espeak-cv-ft, espeak IPA) on announcer audio: free phone decoding with
timestamps, forced alignment of a known IPA string, and slot-wise forced choice (phonecheck.py's method, generalised).
A judge only: nothing it outputs is audio. Frames are 20 ms."""
import os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np, torch, librosa
import torchaudio.functional as TAF
from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor
from huggingface_hub import hf_hub_download

MODEL = 'facebook/wav2vec2-lv-60-espeak-cv-ft'
_m = {}
PAD_S = 0.1          # silence padded on both sides before recognition
HOP = 0.02

def _load():
    if not _m:
        _m['fe'] = Wav2Vec2FeatureExtractor.from_pretrained(MODEL)
        _m['model'] = Wav2Vec2ForCTC.from_pretrained(MODEL).eval()
        _m['vocab'] = json.load(open(hf_hub_download(MODEL, 'vocab.json')))
        _m['inv'] = {v: k for k, v in _m['vocab'].items()}
    return _m

def logprobs(x, sr):
    m = _load()
    y = librosa.resample(np.asarray(x, float), orig_sr=sr, target_sr=16000)
    pad = np.zeros(int(PAD_S * 16000))
    y = np.concatenate([pad, y, pad])
    inp = m['fe'](y, sampling_rate=16000, return_tensors='pt')
    with torch.no_grad():
        return torch.log_softmax(m['model'](inp.input_values).logits[0], -1)

def decode(lp):
    """Greedy CTC: [(phone, t0, t1, mean prob)] in source time."""
    m = _load(); blank = m['vocab']['<pad>']
    ids = lp.argmax(-1).numpy(); pr = lp.exp().max(-1).values.numpy()
    out, prev = [], blank
    for i, k in enumerate(ids):
        if k != blank and k != prev:
            out.append([m['inv'][int(k)], i, i + 1, [pr[i]]])
        elif k != blank and k == prev and out:
            out[-1][2] = i + 1; out[-1][3].append(pr[i])
        prev = k
    return [(p, round(a * HOP - PAD_S, 3), round(b * HOP - PAD_S, 3), round(float(np.mean(q)), 3)) for p, a, b, q in out]

def align(lp, ipa):
    """Forced alignment of a space-separated IPA string: [(phone, t0, t1, score)] in source time. t1 is extended to the
    next phone's start (CTC spikes are narrow), except across long blank runs (>= 60 ms), which are kept as gaps."""
    m = _load(); v = m['vocab']
    seq = ipa.split()
    tgt = torch.tensor([[v[p] for p in seq]], dtype=torch.int32)
    al, sc = TAF.forced_align(lp[None], tgt, blank=v['<pad>'])
    al, sc = al[0].numpy(), sc[0].exp().numpy()
    spans = []  # token spans
    i, n = 0, len(al)
    blank = v['<pad>']
    while i < n:
        if al[i] == blank: i += 1; continue
        j = i
        while j + 1 < n and al[j + 1] == al[i]: j += 1
        spans.append([int(al[i]), i, j + 1, float(sc[i:j + 1].mean())])
        i = j + 1
    # merge repeated identical adjacent tokens only when the target had a repeat (forced_align separates them by blank)
    assert len(spans) == len(seq), (len(spans), len(seq), ipa)
    out = []
    for k, (tok, a, b, s) in enumerate(spans):
        nxt = spans[k + 1][1] if k + 1 < len(spans) else b
        end = nxt if (nxt - b) * HOP < 0.06 else b + 1
        out.append((seq[k], round(a * HOP - PAD_S, 3), round(end * HOP - PAD_S, 3), round(s, 3)))
    return out

def score(lp, ipa):
    v = _load()['vocab']
    ids = torch.tensor([[v[p] for p in ipa.split()]])
    return -torch.nn.functional.ctc_loss(lp[:, None, :], ids, torch.tensor([lp.shape[0]]), torch.tensor([ids.shape[1]]),
                                         blank=v['<pad>'], reduction='sum').item()

def choice(lp, target, alts):
    """Softmax over CTC log-likelihoods of target and alternative IPA strings -> (P(target), best alt, P(best alt))."""
    cands = [target] + [a for a in alts if a != target]
    s = np.array([score(lp, c) for c in cands]); p = np.exp(s - s.max()); p /= p.sum()
    k = int(np.argmax(p[1:])) + 1
    return float(p[0]), cands[k], float(p[k])

def slots(lp, words, i, opts):
    """Slot check: vary phone i of the phone list `words` over opts, others fixed; returns sorted [(opt, p)]."""
    s = []
    for o in opts:
        seq = words[:i] + ([o] if o else []) + words[i + 1:]
        s.append(score(lp, ' '.join(seq)))
    s = np.array(s); p = np.exp(s - s.max()); p /= p.sum()
    return sorted(zip(opts, p.tolist()), key=lambda z: -z[1])

def _feat(x, sr):
    """MFCC (c1..c12) and log energy at a 5 ms hop."""
    n_fft = 256 if sr <= 16000 else 1024
    M = librosa.feature.mfcc(y=np.asarray(x, float), sr=sr, n_mfcc=13, n_fft=n_fft, win_length=int(0.02 * sr),
                             hop_length=int(0.005 * sr), n_mels=40, fmax=min(6000, sr / 2), center=True)
    return M[1:], M[0]

def refine(x, sr, al):
    """Move each boundary between consecutive aligned phones to the point of greatest spectral change between their CTC
    spikes (MFCC distance across +-15 ms, plus a level-change term). Returns [(phone, t0, t1, score)]; the first phone
    starts at its spike (or the clip's onset if earlier), the last ends where the level falls 35 dB below the peak."""
    M, E = _feat(x, sr)
    T = M.shape[1]; hop = 0.005
    k = 3
    d = np.zeros(T)
    for t in range(k, T - k):
        d[t] = np.linalg.norm(M[:, t + k] - M[:, t - k]) + 0.6 * abs(E[t + k] - E[t - k])
    starts = [a for _, a, _, _ in al]
    bounds = []
    for i in range(len(al) - 1):
        a = max(starts[i], 0.0); b = max(starts[i + 1], a)
        ia, ib = int(a / hop) + 1, int(b / hop) + 1
        if ib - ia < 3:
            bounds.append(b)
        else:
            j = ia + int(np.argmax(d[ia:ib]))
            bounds.append(j * hop)
    # clip end: level 35 dB under the peak frame
    n = int(0.02 * sr); h = int(0.005 * sr)
    e = np.array([np.sqrt(np.mean(x[i:i + n] ** 2) + 1e-12) for i in range(0, max(1, len(x) - n), h)])
    le = 20 * np.log10(e); kk = np.where(le > le.max() - 35)[0]
    end = (kk[-1] * h + n) / sr if len(kk) else len(x) / sr
    t0 = max(0.0, min(starts[0], (kk[0] * h) / sr if len(kk) else 0.0))
    edges = [t0] + bounds + [max(end, bounds[-1] + 0.02 if bounds else end)]
    return [(p, round(edges[i], 3), round(edges[i + 1], 3), s) for i, (p, _, _, s) in enumerate(al)]
