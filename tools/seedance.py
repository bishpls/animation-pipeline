"""Seedance 2.5 via the Higgsfield SDK. Credentials: HF_KEY in .env.local (never printed).

    .venv/bin/python tools/seedance.py                                       # the setup check: "A cinematic scene at sunset", 5 s, 720p, 16:9
    .venv/bin/python tools/seedance.py "prompt" OUT.mp4 [--duration 5] [--res 720p] [--aspect 16:9] [--no-audio] [--image start.png [--end end.png]]

One request at a time: the account rejects parallel generations.

Reports failed / cancelled / moderated (NSFW) requests as failures, never as success. Logged to tools/ledger.jsonl.
"""
import json, os, sys, time, urllib.request
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, '.env.local'))
import higgsfield_client as hf  # noqa: E402  (reads HF_KEY from the environment)

MODEL = 'bytedance/seedance-2.5/text-to-video'


def generate(prompt, out=None, duration=5, resolution='720p', aspect='16:9', audio=True, image=None, end_image=None):
    t0, last = time.time(), {'s': None}
    model = MODEL
    args = {'prompt': prompt, 'duration': duration, 'resolution': resolution, 'aspect_ratio': aspect, 'generate_audio': audio}
    if image:                                               # image-to-video: start frame (+ optional end frame); aspect follows the image
        model = 'bytedance/seedance-2.5/image-to-video'
        args.pop('aspect_ratio')
        args['image_url'] = hf.upload_file(image)
        if end_image: args['end_image_url'] = hf.upload_file(end_image)
    try:
        result = hf.subscribe(model, arguments=args, on_enqueue=lambda rid: print('queued', rid),
                              on_queue_update=lambda s: last.__setitem__('s', s))
    except Exception as e:                                   # the SDK raises on failed / cancelled / moderated results
        print(f'FAILED ({type(last["s"]).__name__ if last["s"] else "error"}): {e}'); return None
    st = last['s']
    if st is not None and not isinstance(st, hf.Completed):
        print(f'NOT COMPLETED: {type(st).__name__}'); return None
    video = (result or {}).get('video') or {}
    url = video.get('url') if isinstance(video, dict) else video
    if not url:
        print('no video URL in result:', json.dumps(result)[:400]); return None
    print('video url:', url, f'({time.time() - t0:.0f}s)')
    if out:
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        urllib.request.urlretrieve(url, out); print('saved', out)
    with open(os.path.join(ROOT, 'tools', 'ledger.jsonl'), 'a') as f:
        f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'service': 'higgsfield', 'op': model, 'seconds': duration, 'res': resolution, 'out': out}) + '\n')
    return url


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if not a:
        generate('A cinematic scene at sunset', None, 5, '720p', '16:9')
    else:
        generate(a[0], a[1] if len(a) > 1 and not a[1].startswith('--') else None, int(opt('--duration', 5)), opt('--res', '720p'), opt('--aspect', '16:9'), '--no-audio' not in a, opt('--image'), opt('--end'))
