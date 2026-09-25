"""Draft 5: the duet goes section-level. Clawd's choruses are regenerated without Fable's counter-lines (those become margin
notes in the picture), in place, with Clawd's real sections as context so the voice and production carry over; the final chorus
splits at bar 8 and Fable's own singer takes the second half (her verse as the voice reference).

    python3 song/build_sections.py      -> song/plan_clC.json (Clawd world A) + song/plan_clD.json (final chorus)

Song ids are re-uploads to this account (assets/world4/uploaded.json): cl_2 = the Clawd world, fA3_1 = Fable's verse.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
U = json.load(open(os.path.join(HERE, '..', 'assets', 'world4', 'uploaded.json')))
BAR = 60 / 170 * 4
ms = lambda bars: round(bars * BAR * 1000)
ref = lambda sid, b0, b1, t0=0.0: {'song_id': sid, 'range': {'start_ms': round(t0 * 1000) + ms(b0), 'end_ms': round(t0 * 1000) + ms(b1)}}
L = json.load(open(os.path.join(HERE, 'sections.json')))       # the lyrics (Fable's and Clawd's), kept apart from the plumbing

WORLD = ['170 BPM', 'straight 4/4, four-on-the-floor', 'slap bass', 'sparkling synth brass and arpeggios', 'bright J-pop idol']
CLAWD = 'bright high mezzo idol lead, forward, a smile in the tone, upward leaps on hooks'
NEG = ['6/8', 'waltz', 'folk', 'autotune', 'instrumental']
SOLO = ['second voice', 'duet', 'harmony vocals answering']       # Clawd sings alone now; the crowd answers


def chunk(text, bars, styles, neg=NEG):
    return {'text': text, 'duration_ms': ms(bars), 'positive_styles': styles, 'negative_styles': neg, 'context_adherence': 'high'}


build = chunk('[Intro - build up]', 4, WORLD + ['C major', 'live crowd', 'instrumental build-up that starts sparse and quiet',
              'snare roll accelerating', 'rising riser sweep', 'crowd cheering swells', 'filter sweep opening up', 'explodes into the chorus'], ['vocals', 'singing'])
breakdown = chunk('[Ending - breakdown]', 4, WORLD + ['C major', 'live crowd', 'the band breaks down after the chorus', 'drums drop out',
                  'a final sustained chord', 'slowing down like a tape stop', 'fades to silence', 'instrumental'], ['vocals', 'singing', 'new chorus'])
# Clawd world A: build | chorus 1 (bars 0-2 are the original, then regenerated) | hook + verse 2 (original) | chorus 2 (bars 0-2
# original, then regenerated) | breakdown. Keeping each chorus's first two bars pins Clawd's voice before the new material.
clC = {'chunks': [build, {'song_id': U['cl_2'], 'range': {'start_ms': 0, 'end_ms': 3000}},   # >= 3 s (2 bars is 2.82): ends where her line began
                  chunk(L['chorus1'], 16 - 3 / BAR, WORLD + ['C major', 'live crowd calls in the mix', CLAWD, 'crowd call-and-response fills the gaps'], NEG + SOLO),
                  ref(U['cl_2'], 16, 38),                  # one range: two adjacent refs to the same song returned HTTP 500
                  chunk(L['chorus2'], 6, WORLD + ['C major', 'live crowd calls in the mix', CLAWD, 'crowd call-and-response fills the gaps'], NEG + SOLO),
                  breakdown]}
# Final chorus: Fable's verse and Clawd's chorus 2 as voice references (cut away afterwards), then the key-change pickup, Clawd's
# 8 bars, Fable's 8 bars.
FABLE = L['fable_direction']
clD = {'chunks': [ref(U['fA3_1'], 4, 16), ref(U['cl_2'], 36, 44),
                  chunk('[Pickup - key change build]', 4, WORLD + ['D major', 'instrumental drum fill and riser', 'building to the final chorus', 'crowd roar swells'], ['vocals', 'singing']),
                  chunk(L['final_clawd'], 8, WORLD + ['D major, key change up a whole step', 'biggest chorus, maximum joy', 'crowd screaming the calls', CLAWD], NEG + SOLO),
                  chunk(L['final_fable'], 8, WORLD + ['D major', 'biggest chorus, maximum joy', 'crowd screaming the calls', FABLE, 'a different singer takes the lead: the low contralto from the opening verse'],
                        NEG + ['high mezzo', 'bright idol lead'])]}
for n, p in [('plan_clC', clC), ('plan_clD', clD)]:
    json.dump(p, open(os.path.join(HERE, n + '.json'), 'w'), indent=1)
    print(n, sum(c.get('duration_ms', c.get('range', {}).get('end_ms', 0) - c.get('range', {}).get('start_ms', 0)) for c in p['chunks']) / 1000, 's')

# Fable's half, generated with her voice as the NEAREST context (in clD the model kept Clawd's singer for both halves).
# E1: her verse only. E2: Clawd's new half first (continuity), then her verse, then her half.
fable_half = chunk(L['final_fable'], 8, WORLD + ['D major', 'biggest chorus, maximum joy', 'crowd screaming the calls', FABLE,
                   'the same low contralto singer as the previous section, now over the pop band'], NEG + ['high mezzo', 'bright idol lead'])
if 'clD_1' in U:
    for n, p in [('plan_clE1', {'chunks': [ref(U['fA3_1'], 4, 16), fable_half]}),
                 ('plan_clE2', {'chunks': [ref(U['clD_1'], 20, 32), ref(U['fA3_1'], 4, 16), fable_half]})]:
        json.dump(p, open(os.path.join(HERE, n + '.json'), 'w'), indent=1); print(n)
    # E3: only the verse's last 4 bars as the voice reference, so the band (Clawd's half) dominates the groove
    json.dump({'chunks': [ref(U['clD_1'], 20, 32), ref(U['fA3_1'], 12, 16), fable_half]}, open(os.path.join(HERE, 'plan_clE3.json'), 'w'), indent=1)

# Key check (measured): the model does not reliably follow key instructions. The CURRENT final chorus (clB) is in C, not D, and
# clD_1's "D major" Clawd half came out in A minor. So the final chorus stays in C, like everything the model gives this world.
# F: pickup + Clawd's half, in C, with chorus 2 (C) as context.
json.dump({'chunks': [ref(U['cl_2'], 36, 44),
                      chunk('[Pickup - build]', 4, WORLD + ['C major', 'instrumental drum fill and riser', 'building to the final chorus', 'crowd roar swells'], ['vocals', 'singing', 'key change']),
                      chunk(L['final_clawd'], 8, WORLD + ['C major', 'biggest chorus, maximum joy', 'crowd screaming the calls', CLAWD], NEG + SOLO + ['key change'])]},
          open(os.path.join(HERE, 'plan_clF.json'), 'w'), indent=1)
# G: Fable's half in C: Clawd's C half (clF_2: pickup + half = bars 8-20) for continuity, then her verse as the nearest voice.
if 'clF_2' in U:
    fh = dict(fable_half, positive_styles=[s if s != 'D major' else 'C major' for s in fable_half['positive_styles']], negative_styles=fable_half['negative_styles'] + ['key change'])
    json.dump({'chunks': [ref(U['clF_2'], 8, 20), ref(U['fA3_1'], 4, 16), fh]}, open(os.path.join(HERE, 'plan_clG.json'), 'w'), indent=1)

# H: the whole ending as ONE generation, so the model writes every transition: the tail of the assembled bridge (lead-in, cut away),
# a sparse build that rises out of "Sorekara?", Clawd's half, a crowd vamp for the hand-off (the hall asks "and then?", Fable
# answers "And I'm made of 'and then.'"), Fable's half, and an ending where the band hits and stops on her dash.
# Grid: Bb = 125 in song_d5. Final chorus bars: Clawd 0-4.5 | vamp to 7 | Fable 7-15 | ending 15-18.
if 'song_d5' in U and 'clG_2' in U:
    Bb = 125
    H = {'chunks': [ref(U['song_d5'], Bb - 6, Bb),
                    chunk('[Build]', 4, WORLD + ['C major', 'live crowd', 'instrumental build-up that starts sparse and quiet, rising out of the quiet bridge',
                          'snare roll accelerating', 'rising riser sweep', 'crowd cheering swells', 'filter sweep opening up', 'explodes into the chorus'], ['vocals', 'singing']),
                    ref(U['clF_2'], 12, 16.5),
                    chunk('[Crowd chant]\n(So-re-ka-ra?! So-re-ka-ra?!)\n(So-re-ka-ra?!)', 2.78, WORLD + ['C major', 'the band keeps driving', 'crowd chant with claps, a whole hall shouting',
                          'building anticipation for the next singer'], ['lead vocals', 'solo singer', 'folk', '6/8']),
                    ref(U['clG_2'], 24.28, 32),
                    chunk('[Ending]', 3, WORLD + ['C major', 'the band hits one final accented chord on the downbeat and stops dead', 'the chord rings out and fades',
                          'crowd roar fading', 'silence'], ['vocals', 'singing', 'new section', 'drums continuing'])]}
    json.dump(H, open(os.path.join(HERE, 'plan_clH.json'), 'w'), indent=1); print('plan_clH', [c.get('duration_ms') or c['range'] for c in H['chunks']])
    # H2: the same without the bridge lead-in. Measured: a build only rises (-64 -> -13 dB) when it is the FIRST chunk of a
    # generation; after a reference it continues at full level. Our own bridge bed hands over to it, as before.
    json.dump({'chunks': H['chunks'][1:]}, open(os.path.join(HERE, 'plan_clH2.json'), 'w'), indent=1)

# I: the final chorus is Clawd's alone (draft 6: Fable's singer crossing over sounded like another song). The build first (so
# it rises), then Clawd's existing first half (the voice anchor), then her continuation, then the stop on the dash.
if 'clF_2' in U:
    I = {'chunks': [H['chunks'][1], ref(U['clF_2'], 12, 16.5),
                    chunk(L['final_clawd_rest'], 11.5, WORLD + ['C major', 'biggest chorus, maximum joy', 'crowd screaming the calls', CLAWD], NEG + SOLO + ['key change']),
                    H['chunks'][5]]}
    json.dump(I, open(os.path.join(HERE, 'plan_clI.json'), 'w'), indent=1)
