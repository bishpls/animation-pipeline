"""Cut the taunt close-up ("Show me ya moves!") out of the delivered spine plates: stage-on and keyed, with its audio.
    .venv/bin/python projects/so-back/director/taunt_deliver.py
Film frames 960 (the cut to the front-on close-up) to 1050; voice timing measured on the capture's audio (voice band)."""
import json, os, shutil
import soundfile as sf

F0, F1, PRE = 960, 1050, 60
P = os.path.expanduser('~/games/melee/plates')
VOICE_ON, VOICE_OFF, PEAK = 986, 1025, 998          # film frames: "Sh-" onset, end of "moves!", the hand at its highest
for src, dst, keyed in (('soback_sacred', 'soback_sacred_taunt', False), ('soback_sacred_key', 'soback_sacred_taunt_key', True)):
    sd, dd = os.path.join(P, src, 'v'), os.path.join(P, dst, 'v')
    if not os.path.exists(os.path.join(sd, 'info.json')): print('skip', src); continue
    os.makedirs(dd, exist_ok=True)
    for k, fr in enumerate(range(F0, F1), 1):
        shutil.copy(os.path.join(sd, f'f{fr + PRE + 1:05d}.jpg'), os.path.join(dd, f'f{k:05d}.jpg'))
        if keyed: shutil.copy(os.path.join(sd, f'm{fr + PRE + 1:05d}.png'), os.path.join(dd, f'm{k:05d}.png'))
    a, sr = sf.read(os.path.join(sd, 'audio.wav'))
    sf.write(os.path.join(dd, 'audio.wav'), a[int((F0 + PRE) / 60 * sr):int((F1 + PRE) / 60 * sr)], sr)
    t = lambda fr: round((fr - F0) / 60, 4)
    json.dump(dict(n=F1 - F0, fps=60, pre=0.0, keyed=keyed, w=1080, h=1920,
                   source=dict(plates=sd, film_frames=[F0, F1]),
                   events=[dict(label='voice onset ("Show...")', frame=VOICE_ON - F0 + 1, t=t(VOICE_ON)),
                           dict(label='gesture peak: the raised open hand, palm to the lens, beside his face', frame=PEAK - F0 + 1, t=t(PEAK)),
                           dict(label='voice end ("...moves!")', frame=VOICE_OFF - F0 + 1, t=t(VOICE_OFF))],
                   voice=dict(line='Show me your moves!', onset_t=t(VOICE_ON), end_t=t(VOICE_OFF), clean_preroll=[0.0, t(VOICE_ON)]),
                   notes=("Captain Falcon's taunt, front-on and chest-up. In Melee his taunt turns him to face INTO the stage "
                          "(-z), away from the game's own camera, so this lens sits behind the stage. The gesture is a raised "
                          "open hand beside his face (a 'bring it'), in the picture plane: it faces the lens rather than "
                          "pointing down it. The voice is his only taunt line (one run heard: 'Show me your moves!'). "
                          f"Everything before t={t(VOICE_ON)} is voice-free (the stage's ambience only).")),
              open(os.path.join(dd, 'info.json'), 'w'), indent=1)
    print(dst, F1 - F0, 'frames')
