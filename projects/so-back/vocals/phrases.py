"""The announcer's whole phrases, used as-is: trimmed, level-matched (active RMS -> REF_DB, peak-limited by gain only)
and measured (onset, syllable nuclei with F0, duration). Writes W/phrases/<name>.wav and vocals/phrases.json.
    .venv/bin/python projects/so-back/vocals/phrases.py"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from hf0 import hf0
from lexicon import ipa_words, VOWELS
import phones

REF_DB = -11.3
PHRASES = {
    'game': 'name_37', 'go': 'name_38', 'ready': 'name_44', 'failure': 'nr_1p_08', 'defeated': 'name_34',
    'game_over': 'nr_1p_03', 'no_contest': 'nr_vs_00', 'continue': 'nr_1p_02', 'five': 'name_35', 'four': 'name_36',
    'three': 'name_46', 'two': 'name_48', 'one': 'name_39', 'success': 'name_45', 'complete': 'nr_1p_06',
    'a_new_record': 'nr_1p_00', 'congratulations': 'nr_1p_01', 'wow_incredible': 'nr_1p_05',
    'choose_your_character': 'nr_select_04', 'super_smash_brothers_melee': 'nr_title_01', 'sudden_death': 'nr_vs_01',
    'super_sudden_death': 'nr_select_12', 'this_games_winner_is': 'nr_vs_05', 'wins': 'nr_vs_06', 'hurry': 'name_14',
    'time': 'name_47', 'team': 'name_49', 'versus': 'nr_1p_10', 'and': 'nr_1p_04',
    # extras worth having in the kit
    'melee': 'nr_select_05', 'smash_brothers': 'nr_title_03', 'nintendo_all_star': 'nr_title_00', 'all_star': 'nr_select_03',
    'break_the_targets': 'name_50', 'grab_the_coins': 'nr_select_07', 'survival': 'nr_select_08', 'metal': 'name_23',
    'giant': 'name_07', 'bonus_stage': 'nr_1p_07', 'race_to_the_finish': 'nr_1p_09', 'computer_player': 'name_51',
    'winner_drops_out': 'nr_select_21', 'single_button': 'nr_select_17', 'game_set_jp': 'jp_37', 'time_up_jp': 'jp_48',
}
# what's under the voice, read off the spectrogram sheets (plots/sheet_phrases*.png) and the crowd measure below
UNDER = {
    'complete': 'a crowd cheer under and after the word (from ~0.6 s to the end, 2.7 s): trim at ~0.65 s for the dry word',
    'a_new_record': 'a crowd cheer under and after the words (from ~0.8 s to the end, 2.7 s): trim at ~1.0 s for the dry words',
    'super_smash_brothers_melee': "the title shout: 'Super Smash Brothers' 0-2.4 s, then 'Melee' held ~4 s with a rising, "
                                  'processed sustain (part of the original recording, no band music under it)',
    'smash_brothers': "the Japanese title's 'Smash Brothers': 'Smash' held ~1.4 s and 'Brothers' ~3.8 s, both on rising, "
                      'processed sustains (clean voice, no music)',
}

TEXT_JP = {'game_set_jp': 'Game set! (Japanese bank)', 'time_up_jp': 'Time up! (Japanese bank)'}

def crowd_db(x, t_end_speech):
    """Level of broadband (1-5 kHz) noise after the speech ends, relative to the speech: a crowd/SFX indicator."""
    import librosa
    S = np.abs(librosa.stft(x, n_fft=256, hop_length=60))
    f = librosa.fft_frequencies(sr=SR, n_fft=256); band = (f > 1000) & (f < 5000)
    t = np.arange(S.shape[1]) * 60 / SR
    after = S[:, t > t_end_speech + 0.25]
    if after.shape[1] < 3: return None
    flat = librosa.feature.spectral_flatness(S=after[band]).mean()
    return round(float(flat), 3)

def main():
    os.makedirs(f'{W}/phrases', exist_ok=True)
    out = {}
    for name, key in PHRASES.items():
        x = load(key); on = onset(x); te = tail_end(x, floor_db=-45)
        a = max(0, int((on - 0.005) * SR)); b = min(len(x), int(te * SR) + int(0.01 * SR))
        y = x[a:b].copy(); f = int(0.01 * SR); y[-f:] *= np.cos(np.linspace(0, np.pi / 2, f)) ** 2
        g = REF_DB - db(y); pk = np.abs(y).max() * 10 ** (g / 20)
        if pk > 0.95: g -= 20 * np.log10(pk / 0.95)
        y *= 10 ** (g / 20)
        write(f'{W}/phrases/{name}.wav', y)
        # nuclei from forced alignment (+-20 ms), F0 by hf0 over each vowel span
        lp = phones.logprobs(y, SR)
        ws = ipa_words(REG[key]['text']) if REG[key]['text'] else []
        al = phones.refine(y, SR, phones.align(lp, ' '.join(p for _, ps in ws for p in ps))) if ws else []
        t, f0, sc, v = hf0(y, SR, hop=0.005, fmin=85, fmax=480)
        syl = []
        i = 0
        for w, ps in ws:
            for p, t0, t1, s in al[i:i + len(ps)]:
                if p in VOWELS:
                    k = v & (t >= t0) & (t <= t1)
                    syl.append(dict(word=w, vowel=p, t0=t0, t1=t1,
                                    f0=round(float(np.median(f0[k])), 1) if k.sum() > 1 else None,
                                    midi=round(float(69 + 12 * np.log2(np.median(f0[k]) / 440)), 1) if k.sum() > 1 else None))
            i += len(ps)
        speech_end = al[-1][1] if al else len(y) / SR
        out[name] = dict(src=key, text=REG[key]['text'] or TEXT_JP.get(name), file=f'phrases/{name}.wav', dur=round(len(y) / SR, 3),
                         onset=round(on - a / SR, 3), gain_db=round(g, 1), syllables=syl,
                         under=UNDER.get(name, 'clean: voice and its own reverb only'))
        print(name, out[name]['dur'], [(s['vowel'], s['t0'], s['f0']) for s in syl], flush=True)
    jdump(out, os.path.join(HERE, 'phrases.json'))

if __name__ == '__main__':
    main()
