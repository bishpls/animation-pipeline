"""ElevenLabs stem separation: .venv/bin/python tools/stems.py IN.mp3 [OUTDIR]  -> OUTDIR/{vocals,drums,bass,guitar,piano,other}.mp3
Also: --pitch prints the vocal stem's pitch range (pyin), for checking a singer's register."""
import io, json, os, subprocess, sys, time, zipfile
import requests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = next(l.strip().split('=', 1)[1] for l in open(os.path.join(ROOT, '.env')) if l.startswith('ELEVENLABS_API_KEY='))

def separate(path, out=None):
    out = out or os.path.splitext(path)[0] + '_stems'
    if not os.path.exists(os.path.join(out, 'vocals.mp3')):
        r = requests.post('https://api.elevenlabs.io/v1/music/stem-separation?output_format=mp3_44100_192', headers={'xi-api-key': KEY}, files={'file': open(path, 'rb')}, timeout=900)
        if r.status_code != 200: print(r.status_code, r.text[:400]); sys.exit(1)
        os.makedirs(out, exist_ok=True); zipfile.ZipFile(io.BytesIO(r.content)).extractall(out)
        with open(os.path.join(ROOT, 'tools', 'ledger.jsonl'), 'a') as f: f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'service': 'elevenlabs', 'op': 'stems', 'in': path}) + '\n')
    return out

def pitch(path):
    import numpy as np, librosa
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', '22050', '-'], capture_output=True).stdout
    y = np.frombuffer(raw, np.float32); f0, v, _ = librosa.pyin(y, fmin=70, fmax=1100, sr=22050)
    f = f0[~np.isnan(f0)]
    return {k: librosa.hz_to_note(float(np.percentile(f, q))) for k, q in [('p5', 5), ('median', 50), ('p95', 95)]}

if __name__ == '__main__':
    a = sys.argv[1:]; out = separate(a[0], a[1] if len(a) > 1 and not a[1].startswith('--') else None)
    print('stems ->', out)
    if '--pitch' in a: print('vocal range', pitch(os.path.join(out, 'vocals.mp3')))
