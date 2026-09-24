"""ElevenLabs sound effects: .venv/bin/python tools/sfx.py "prompt" OUT.mp3 [seconds] [influence]"""
import json, os, sys, time, requests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = next(l.strip().split('=', 1)[1] for l in open(os.path.join(ROOT, '.env')) if l.startswith('ELEVENLABS_API_KEY='))
prompt, out = sys.argv[1], sys.argv[2]
body = {'text': prompt, 'model_id': 'eleven_text_to_sound_v2', 'prompt_influence': float(sys.argv[4]) if len(sys.argv) > 4 else .6}
if len(sys.argv) > 3: body['duration_seconds'] = float(sys.argv[3])
r = requests.post('https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_192', headers={'xi-api-key': KEY}, json=body, timeout=300)
if r.status_code != 200: print(r.status_code, r.text[:500]); sys.exit(1)
open(out, 'wb').write(r.content)
with open(os.path.join(ROOT, 'tools', 'ledger.jsonl'), 'a') as f: f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'service': 'elevenlabs', 'op': 'sfx', 'out': out}) + '\n')
print('wrote', out, len(r.content))
