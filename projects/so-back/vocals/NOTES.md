# SO BACK vocals: the announcer as the singer

All vocals come from the Melee announcer's own recordings on Michael's US 1.02 disc. They are decoded from the disc's sound banks
(into `~/games/melee/work/announcer/`), and this code only reads from there. The only edits are:
- cuts, crossfades and gains;
- Praat PSOLA pitch and duration changes, driven by our `hf0` tracker;
- resampling, gates, and a harmonic exciter at the 48 kHz lift.

No TTS, voice cloning or voice conversion is used, and nothing paid is called. The local recognizers (Whisper small.en,
medium.en and turbo, and wav2vec2 phoneme CTC) are used only as judges.

**I can't listen.** Every judgement below is from speech-to-text, a phoneme model and signal measurements. Michael's ears
overrule all of it.

Audio lives in `W = ~/games/melee/work/soback/vocals/`, because game-derived audio never goes in the repo. Code and
measurements live here.

## Files

| what | where |
|---|---|
| Inventory of every clip (words, phones, syllable nuclei with F0, loudness, tail end, three STT passes) and the phone inventory | `INVENTORY.md`, `inventory.json` (built by `inventory.py`) |
| Whole phrases trimmed and level-matched (active RMS −11.3 dB), with syllable nuclei and F0 | `W/phrases/<name>.wav`, `phrases.json` (built by `phrases.py`) |
| Spliced words, one file per recipe | `W/words/<kind>_<recipe>.wav` (`words.py`, `quick_words.py`) |
| Spliced phrases, ranked, each also as separate words 0.30 s apart | `W/spliced/<phrase>_<rank>_<recipe>_<native or tuned>[_words].wav`, `phrases_eval.json` (`build_phrases.py final`) |
| Auditions, the candidates in rank order 0.5 s apart | `W/audition_its_so_over.wav`, `W/audition_were_so_back.wav` (labels below) |
| Sung demos (48 kHz) | `W/demo_its_so_over_sung.wav`, `W/demo_were_so_back_sung.wav`, `W/demo_its_so_over_sung_lowover.wav` (a known merge), `W/demo_chops.wav` (`demo.py`) |
| Song-build library | `vox.py` |
| Judges | `judge.py` (Whisper free and forced choice, seams), `phones.py` (CTC alignment and choice), `specs.py` (targets and near misses) |
| My eyes (spectrograms) | `spec.py`, `zoom.py`, `sheet.py` → `W/plots/` |

`splice.py` and `hf0.py` come from an earlier name-call splice. The only change is that `splice.load` reads registry keys.

## 1. What the banks hold

- **names/** (52 clips): the character calls, plus Defeated, Five to One, Game!, Go!, Hurry!, Player 1-4, Ready?, Success!,
  Team, Time!, Break the targets!, Computer player.
- **nr_select** (23): the menu calls, including "Choose your character!", Survival!, "Grab the coins!", "Super Sudden Death!",
  "Single Button!", "Winner drops out!".
  - idx 05 is probably "Melee!" (the STT hears "ME!" and "Mitty!").
  - idx 06 is unresolved (all three models hear "Decision!").
- **nr_vs** (7): No contest!, Sudden death, Blue/Green/Red team!, "This game's winner is...", WINS!
- **nr_1p** (11): A new record!, Congratulations!, Continue?, Game over., And..., "Wow, incredible!", Complete!, Bonus stage!,
  Failure, versus, and **idx 09 "Race to the Finish!"** (the old label "W E T T..." was wrong: turbo hears "Rence to the finish!"
  and the free phones read /s t ə f ɪ n ɪ ʃ/).
- **nr_title** (5): Nintendo All-Star!; the US title shout "Super Smash Brothers Melee!" (6.7 s); and the Japanese title's
  parts: Dairantou, Smash Brothers, "Smash Brothers Melee".
  - These are drawn out. "Melee", "Smash" and "Brothers" sit on long, rising, processed sustains (3-4 s).
  - That's the voice itself, with no band music under it.
- **nr_name_jp** (54): the Japanese-language names. Useful extras: **"Game set!" (jp_37)** and **"Time up!" (jp_48)**, the original
  Japanese calls.
- **main.ssm** (246 sounds) holds no announcer lines. Its 12 kHz clips 136-139 are short crowd shouts ("HUAH!", "Ha ha!"),
  usable as SFX. 146 and 147 are unclear.

**Not clean:**
- `complete` (nr_1p_06) and `a_new_record` (nr_1p_00) carry a crowd cheer under and after the words, from about 0.6 s and
  0.8 s to their 2.7 s ends. Trim at about 0.65 s and 1.0 s for dry words.
- Every other clip is the voice plus its own heavy reverb, which is baked in: the level almost never drops more than about
  15 dB inside a clip. `phrases.json` has an `under` field per phrase.

## 2. Whole phrases (use as-is)

`W/phrases/`: game, go, ready, failure, defeated, game_over, no_contest, continue, five, four, three, two, one, success,
complete, a_new_record, congratulations, wow_incredible, choose_your_character, super_smash_brothers_melee, sudden_death,
super_sudden_death, this_games_winner_is, wins, hurry, time, team, versus, and.

Extras: melee, smash_brothers, nintendo_all_star, all_star, break_the_targets, grab_the_coins, survival, metal, giant,
bonus_stage, race_to_the_finish, computer_player, winner_drops_out, single_button, game_set_jp, time_up_jp.

About the measurements:
- Every clip starts on its first sample (onset 0.00; the bank trims them) and ends in its own reverb tail.
- The nuclei in `phrases.json` come from forced alignment (±20 ms).
- F0 is ±1 semitone, with occasional octave slips in creaky tails. Defeated's last 474 Hz is one.
- Register: stressed syllables sit at about 300-370 Hz; finals and "down" words (Game over, Continue, Team) sit at about 110-180 Hz.

## 3. Spliced phrases

### Recipes (source times in seconds, read off `W/plots/z_*.png` and the forced alignment)

| word | recipe | pieces |
|---|---|---|
| it's | `is+t` | "winner **i**s" 1.10-1.25 · 35 ms closure · the final **s** of "target**s**" 1.26-1.52 |
| | `targets` | "tar**gets**" 1.035-1.56 (/ɪts/ after the g burst) |
| | `this+ts` | "th**i**s" 0.035-0.14 · 30 ms · "targe**ts**" 1.23-1.52 |
| | `this+t` | "th**i**s" · 35 ms · "thi**s**" (weakest) |
| so | `sudden+no` | **S**udden 0.02-0.185 + "**N**o contest" o 0.09-0.38 (12 ms crossfade; the n→o place matches s→o) |
| | `single+no`, `surv+no` | **S**ingle 0.01-0.155 or **S**urvival 0.0-0.095 + the same o |
| | `*+go` | + the o of "Go!": heard as "soul" (don't use) |
| over | `gameover` | "Game **over**." 1.10-2.09: the sad, low one (o ~110 Hz, ver ~165 Hz) |
| we're | `winner-n` | "**Wi**nner drops out" 0.0-0.33 + its "-**er**" 0.49-0.69, dropping the n |
| | `wins+master` | "**WI**NS" 0.0-0.19 + "Mast**er**" 0.42-0.50 |
| | `wins+player`, `wins+winner` | as above with "Play**er**" or "winn**er** is" (the latter drags in "is") |
| back | `break+hand+complete` | **B**reak burst 0.085-0.115 + "h**a**nd" 0.56-0.74 · 60 ms closure (the vowel fades over 30 ms) · the word-initial /k/ of "**C**omplete" 0-0.045, −4 dB |
| | `bonus+hand+kirby` | **B**onus 0-0.022 + h**a**nd + the /k/ of "**K**irby" 0-0.05 |
| | `button+smash+continue` | B**u**tton's b 0.70-0.725 + "Sm**a**sh" (title) 1.035-1.20 (recorded at ~370 Hz) + the /k/ of "**C**ontinue" |
| | `button+smash+continue.k0` | the same with the /k/ at full level: **the sung default** |

**Why a word-initial /k/:** the final /k/ in "Sheik" and "Link" is buried in reverb, so a released final k sounded like a
second syllable ("DIE", "HUH", "BLEH"). The first 45-50 ms of a clip that starts with k is a clean burst plus aspiration with
no reverb before it.

The /æ/ and /k/ choices come from a 200-way grid (`back_grid.py`): 5 b × 5 æ × 4 k × 2 closures, scored in the phrase by
Whisper forced choice. Mean P(hit) by æ: and .88, hand .76, captain .74, smash .72, man .03. By k: kirby .68, complete .68,
continue .62, captain .54. The b and the closure length barely matter.

### Ranking: spoken ("native": each piece at its recorded pitch)

Columns:
- **free** is hits over 6 transcriptions: 3 Whisper sizes, alone and after a real "Continue?".
- **P(hit)** is Whisper forced choice against about 30 near misses ("It's over", "It's sober", "We're so bad", "We're so big"...),
  for small.en and medium.en.

| # | it's so over | free | P(hit) s / m | what the models wrote |
|---|---|---|---|---|
| 1 | `is+t` · `sudden+no` · `gameover` | 6/6 | .981 / .966 | "It's so over!" ×6 |
| 2 | `targets` · `single+no` · `gameover` | 6/6 | .976 / .936 | "It's so over!" ×6 |
| 3 | `targets` · `sudden+no` · `gameover` | 6/6 | .984 / .924 | "It's so over!" ×6 |
| 4 | `is+t` · `surv+no` · `gameover` | 6/6 | .953 / .914 | "It's so over!" ×6 |
| 5 | `this+ts` · `sudden+no` · `gameover` | 5/6 | .951 / .923 | once "Continue this song over!" |

| # | we're so back | free | P(hit) s / m | what the models wrote |
|---|---|---|---|---|
| 1 | `winner-n` · `single+no` · `break+hand+complete` | 6/6 | .990 / .975 | "We're so back." / turbo "Winner, so back!" |
| 2 | `wins+master` · `surv+no` · `break+hand+complete` | 6/6 | .974 / .981 | "WE'RE SO BACK!" ×6 |
| 3 | `winner-n` · `single+no` · `button+smash+continue` | 5/6 | .960 / .956 | once "Winner sold back!" |
| 4 | `winner-n` · `sudden+no` · `bonus+hand+kirby` | 4/6 | .986 / .986 | "Winner, so big!" / "peck" |
| 5 | `wins+player` · `sudden+no` · `bonus+hand+kirby` | 4/6 | .980 / .987 | "BECKED", "Where's some heck?" |
| 7 | `wins+winner` · `sudden+no` · `bonus+and+kirby` | 0/6 | .978 / .980 | "Where it's so eck!" (don't use) |

- **"Tuned" variants all fail** (0-3/6; "It's song over", "We're so rick"). Each was PSOLA'd to one speech contour in a single
  register, which moved "so" by about 12 semitones. Keep every syllable within about ±5-7 semitones of where it was recorded.
- **Seams:** the only vowel-to-vowel seam, we're's "Wi|er" in `winner-n`, sits at the 64th percentile of the announcer's natural
  20 ms steps. Consonant-to-vowel seams (s|o, b|æ) score 93-100, which is what natural consonant-to-vowel boundaries score
  (natural boundaries score 97-99). The F0 "jumps" listed at s|o are the s's reverb, not the vowel.

### Auditions (listen here first)

`W/audition_its_so_over.wav` (each entry starts at the time shown):

| time | entry |
|---|---|
| 0.00 | #1 |
| 2.57 | #2 |
| 5.19 | #3 |
| 7.84 | #4 |
| 10.33 | #5 |
| 12.88, 15.50, 18.00, 20.54, 23.19 | the tuned variants (bad) |

`W/audition_were_so_back.wav`:

| time | entry |
|---|---|
| 0.00 | #1 |
| 1.95 | #2 |
| 3.58 | #3 (the high "Smash" back) |
| 5.51 | #4 |
| 7.47 | #5 |
| 9.29 | #1 tuned |
| 11.24 | #7 (bad) |
| 13.05-20.24 | the other tuned variants (bad) |

Every candidate is also in `W/spliced/` as one take and as `_words.wav`: the words 0.30 s apart, for placing on beats.

## 4. Sung (vox.sing, hard-tuned) findings, from the demos

- **"so" and "over" merge when they sit close in pitch.** On the brief's E4 D4 C4 A3, straight on the beats, STT hears
  "It's over" (P(hit) .17 / .22). A leap up on "so" plus a 16th rest before "over" fixes it:
  - E4 **A4** · C4 A3, "so" 0.75 beat, "over" on beat 2.25;
  - result: "It's so over!" ×3, P(hit) .90 / .95.
- **Sung "back" wants the high-register vowel.** The spoken winner, `break+hand+complete`, sung on A4 C#5 E5 gives P(hit)
  .95 / .04 ("What's up, baby?"). `button+smash+continue`, whose "Smash" /æ/ was recorded at about 370 Hz, gives .96 / .91.
  Its /k/ at full level (`.k0`) gives .97 / .95 and turbo "We're so back!". At −4 dB it drifts to "We're so bad!".
  - The low register (A3 C#4 E4) fails with every recipe.
  - `demo_were_so_back_sung.wav`: free STT "WE'RE SO C-" / "We're so bad!" / "We're so bad!", P(hit) .97 / .92. Sung, "back"
    vs "bad" is the weak point. Keep the /k/ loud and consider doubling it with a percussive hit.
- **Words need their own time.** At 150 BPM, 8th notes for "it's so" smear the long /s/ tails into the next word.
  `vox.line()` cuts each word where the next starts. `sing(..., fit_to=)` also squeezes the consonants (never below 40%).
- `demo_chops.wav` ("s-s-so" on 16ths, octave-up "back" retriggered, "over" into a tape stop) reads as "S-S-S..." to STT.
  That's expected for chops; judge it by ear.

## 5. vox.py API (float64 mono numpy; 12 kHz unless stated)

- `clip(key)` → a whole announcer clip. `load_word(name, sub='words')` → a built word or phrase from W.
- `sing(y, notes, syl=None, durs=None, glide=.025, vibrato=(0, 5.5), scoop=0, fit_to=None)` → PSOLA onto MIDI notes, one per
  syllable span `syl` [(t0, t1)]:
  - the pitch is flat per note, with `glide` seconds between notes;
  - `durs` time-scales each syllable, keeping pitch; consonants are never pitched;
  - `voiced_spans(y)` finds the spans.
- `stutter(y, n, slice_s, gap_s)`, `repeat(y, n, every_s, length_s, decay_db)`, `tape_stop(y, dur_s, curve)`, `reverse(y)`.
- `pitch_shift(y, semis, formant=None)`:
  - with `formant=None` it's plain PSOLA, and the formants stay put;
  - with `formant=r` it uses Praat's **Change Gender** (PSOLA plus a resample that moves formants by r). This is what
    `demo_chops` uses for the octave-up (+12, r = 1.25).
- `gate(y, bpm, pattern='1011', div=16, offset_s)`: a rhythmic gate with smooth edges.
- `to48k(y, bright=.3)` (12 kHz in, 48 kHz out): a soxr resample plus an exciter.
  - The 3-6 kHz band is soft-clipped, and only its harmonics above 6 kHz are mixed back.
  - A plain upsample leaves nothing above 6 kHz and sounds like a phone next to a modern mix. `bright=0` is the plain resample.
- `line([(y48, t_s), ...])` (48 kHz): a monophonic line, where each word is cut, with a fade, where the next begins.
  `place(track, y, t_s, sr=48000, gain_db)`: mix y in at t_s.
- `midi2hz`, `hz2midi`.

## 6. Uncertainties

- **The judges are imperfect.**
  - Forced choice saturates near 1 for spoken candidates, because the language prior favours the real phrase. Free STT
    separates them better.
  - The phoneme CTC "P(target)" came out near 0 for every candidate: my target IPA doubled the s and o at the word joins, so
    it isn't discriminative. The best-alternative strings (in `phrases_eval.json`) show the vowels are read right.
- **Stop closures are digital silence** (60 ms in "back", 30-35 ms in "it's"). In this reverberant voice, a real closure would
  keep the room tail. If it sounds gated, try a shorter closure (40 ms) or let the vowel's own continuation fade under it.
- **Measurement limits.** Word and phone times from forced alignment are ±20 ms, and pitch figures are ±1 semitone.

## 7. Round 2 (Michael's first listen: the hook and the sad "so" were shrill), plus "YOU!"

**Judged in the whole song.** For each candidate, `round2.py`:
1. rebuilds arrange.py's stem with only that slot swapped (`build_stem`, which is arrange.main() made pluggable; arrange.py
   itself is untouched);
2. runs mix.py's chain on it (duck, tape stop, SFX stem if present, limiter, vox −2.5 dB);
3. transcribes the **full 28.9 s mix** with Whisper small.en and medium.en (word stamps; the slot's words are quoted below);
4. runs a **full-context forced choice**: the model's own full transcript, with the slot's words swapped for each candidate
   string ("We're so back!" against "We're so bad/black/big/glad...", "Winner so back"...);
5. measures a shrillness proxy on the sung words alone: spectral centroid, % of energy above 3 kHz, and median F0.

Full mixes: `W/round2/mix_<name>.wav`. Results: `round2_hooks.json`, `round2_sos.json`.

**Reproducibility fix:** Praat's overlap-add PSOLA draws random numbers for unvoiced stretches (s, k, closures).
- Two identical `vox.sing` calls differed by up to 0.1-0.3 of full scale on "back".
- `vox._seed()` now seeds Praat before every resynthesis (`sing`, `pitch_shift`, Change Gender; also `splice.psola`).
  Identical inputs now give identical output.
- The consequence: the current `W/stem.wav` (built before the fix) can't be rebuilt bit for bit. `round2.py check` shows the
  only differences are the sung words' noise, while seeded rebuilds are identical. Round 2's "current" baseline (H0/S0) is
  therefore rebuilt through the same harness as every candidate.

### Hook: "we're so back" (b0, b33, b40, b52 stutter)

Centroid, >3 kHz and F0 are the vocal alone at b33, over the sung words.

| # | variant | full-mix STT at b33 (small / medium) | forced P(hit) b33 · b40 · b0 · b52 (small/medium) | centroid Hz | >3 kHz | F0 med |
|---|---|---|---|---|---|---|
| — | **H0 current**: sung G4 C5 Eb5, octave-up formant ×1.25 double at −8/−9 dB, bright .3 | "WE'RE SO BACK!" / "We're so back!" | .99/1.0 · 1.0/1.0 · .99/1.0 · .89/.99 | 1028 | 7.6% | 507 |
| 1 | **H2 spoken #2, tuned**: `wins+master`, `surv+no`, `break+hand+complete` at their own lengths, each hard-tuned to the nearest C minor tone. That lands on **we're Eb3 · so F4 · back C3**, the name-call cadence ending on the tonic. bright .1, shelf −3 dB @ 3.5 kHz, no double | "We're so back!" / "We're so back" (all 4 slots, both models) | 1.0/1.0 · .98/.99 · 1.0/1.0 · .97/.995 | **788** | **3.3%** | 158 |
| 2 | H11: as H2, with "so" sung and held on Eb4 (D4 at b40) | "Wear some back" / "We're so back" | .99/1.0 · .04/1.0 · .85/1.0 · .04/.99 | 748 | 3.4% | 158 |
| 3 | H9: "we're so" sung C4 Eb4 (sung recipes), then H2's spoken "back" tuned to C3 | "We're so back!" / "We're so bad" | 1.0/.003 · .96/0 · 1.0/.002 · .99/.01 | 790 | 3.1% | 262 |
| ✗ | H3 sung C4 Eb4 G4 · H4 sung Eb4 F4 G4 | "We're so glad!" / "We're so black!" | ≤ .12 everywhere | 792 | 3.1% | 297 |
| ✗ | H5: H3 plus an octave-down double at −5 | "Wear some blood!" / "We're so black!" | ≤ .17 | — | — | — |
| ✗ | H7: H3 plus a dry spoken "back" layered at −6 | "We're so bad!" / "We're so black!" | ~0 | 790 | 3.1% | 269 |
| ✗ | H8: sung C4 Eb4, then "back" on G3 with the low "hand" /æ/ | "We're so bad" | ~0 | — | — | — |
| ✗ | H6: the current melody an octave down (G3 C4 Eb4), low "winner" | "some the", "Whether it's over" | ≤ .68 | — | — | — |
| ✗ | H1 spoken #1, tuned | "Winner so bad!" / "We're so bad" | ~0 | — | — | — |
| ✗ | H10: H2 tuned to +2 st | "WE'RE SO PICK" / "We're so big" | ~0 | — | — | — |

**Finding: any sung, stretched "back" below the old register turns into "glad/black/bad".** None of these rescued it:
- a louder /k/ (`.k0`);
- another /æ/ ("hand");
- a dry spoken layer;
- an octave-down double.

"Back" survives low only as a *spoken* word at its own length, where the /k/ follows the vowel within about 100 ms.

Recommended: **H2**. It uses Michael's chest register (the tuned notes are Eb3 F4 C3), the hard tuning supplies the
hyperpop, and it's the only low variant both models hear as "We're so back" in every slot. Compared with the current take,
the centroid drops from 1028 to 788 Hz and the >3 kHz share from 7.6% to 3.3%.

### Sad "so" (b8 "it's so over", and the b21 spoken echo)

Measured on the "so" alone.

| # | variant | STT at b8 (small / medium) | P(hit) small/medium | F0 | centroid | >3 kHz |
|---|---|---|---|---|---|---|
| — | **S0 current**: `sudden+no` (the shouted "NO contest" o) sung G4 | "It's so over!" / "It's so over." | .999/.999 | 388 | 884 | 6.1% |
| 1 | **S9**: `sudden+overo` ("Game Over"'s own soft o, recorded ~111 Hz) sung **G3**, len 1.0, shelf −3. The current melody an octave down | "It's so over..." / "It's so over." | .994/.999 | 198 | **490** | 1.5% |
| 2 | **S7**: the same o sung **Eb3** (+6 st from its recording, the gentlest shift) | "It's so over..." ×2 | .998/.990 | 156 | 496 | 1.3% |
| 3 | S11: Falco's final o (recorded 220→150 Hz) sung Eb3, len 1.2 | "It's so over..." ×2 | .996/.976 | 158 | 587 | 1.3% |
| 4 | S10: Falco's o sung Bb3 | "It's. So. Over." / "It's so over..." | .990/.984 | 234 | 590 | 1.4% |
| 5 | S4: Falco's o sung G3 | "It's... So... Over..." / "It's so over..." | .956/.974 | 198 | 589 | 1.3% |
| 6 | S1: the No o softened (shorter, −3 dB s, 60 ms fade-in, shelf −4) sung Eb4 | "It's... So..." / "It's so over" | .002/.941 | 312 | 603 | 1.1% |

Failed:
- Mario's o reads "all/fall" ("It's all over", .00 medium).
- Bonus's o reads "swap/smok".
- `sudden+overo` on F3 reads "Soul" to small.en.

The s is the same everywhere: Sudden 0.07-0.185 at −3 dB.

"Game Over"'s own o does **not** merge with "over" here, because they sit on different beats (9.25 vs 11) and "over" is +3 st
above its recording.

### YOU! (final stab, bt(64) = 25.65, after the real "This game's winner is..." at bt(60))

`you.py`. Isolated judging: 3 Whisper sizes alone, and after the real "This game's winner is...", plus forced choice against
Ew, Hugh, True, New, Two, Yo, Ooh, You're, Who, Mew... Then **in the song**: the final line swapped into the full mix, judged
in full context.

| # | recipe | isolated free (6) | isolated P small/medium (ctx) | **in the song** (small / medium) | song P | F0 head→fall | centroid |
|---|---|---|---|---|---|---|---|
| 1 | **mew+tail**: "Mewtwo!" with the m cut. Its "Mew" is /juː/ already falling 340→230 Hz (0.115-0.44), with the name's own reverberant tail (its "-two" vowel from 0.72, where its pitch meets the Mew's end, skipping the t) crossfaded on over 40 ms | 6/6 | .98/.985 (.993/.999) | "...winner is... You!" / "...winner is you!" | .994/.999 | 314→171 | 554 |
| 2 | mew: the "Mew" alone, ending in an 80 ms fade (no tail) | 6/6 | .987/.981 (1.0/1.0) | "You!" / "you!" | .994/.999 | 314→205 | 684 |
| 3 | young+two: the j of "Young" + "Two!" after its t | 6/6 | .992/.983 (.999/1.0) | "...winner is..." / "...winner is!" (lost under the stab) | .25/.48 | 261→161 | 330 |
| 4 | yoshi+two: the j of "Yoshi" + "Two!" (an 11.9 st F0 jump at the seam) | 6/6 | .97/.84 | lost ("Two!") | .14/.38 | 350→143 | 325 |
| 5 | continue: "-nue" re-contoured to the fall | 6/6 | .91/.90 | not rendered in the song | — | 346→254 | — |
| ✗ | computer+tail, your+tail | "Thank you." / "OOO", "Who?" | ≤ .67 | — | — | — | — |

Recommended: **mew+tail**.
- It's a real name call's own /juː/ in the name-call cadence (≈ −7 st), with his real reverberant tail.
- Its seam, vowel into vowel, scores at the 97th percentile of natural steps, with a −0.6 st pitch step.
- It's the softest in the song (centroid 554 Hz).

### Drop-in for arrange.py (the winners; all helpers are importable from round2.py / you.py)

```python
from vox import shelf                         # RBJ high shelf on a 48 kHz vocal (same filter round2 used)
import you                                    # light: no Whisper import
# hook (H2): spoken #2, each word at its own length, hard-tuned to the nearest C minor tone (Eb3 . F4 . C3); no doubles
HOOK = ('wins+master', 'surv+no', 'break+hand+complete')
def hook_line(beats):
    out = []
    for kind, rec, b in zip(('were', 'so', 'back'), HOOK, beats):
        y = word(kind, rec); syl = word_syl(kind, y)
        out.append((shelf(up(tune(kind, y), bright=.1), -3, 3500), bt(b) - syl[0][0]))
    return out
#  b0:  hook = hook_line((0, 1, 2)); clamp hook[0] >= 0; y, t0 = vline(hook); bus.add(y, t0, 0, send=.25, rt60=1.2)
#       b4 echo (replaces the chipmunk): bus.add(lowpass(y, 2500), t0 + 4 * BEAT, -8, pan=-.35, send=.3, rt60=1.2)
#  b33 / b40: y, t = vline(hook_line((33, 34, 35)))  /  hook_line((40, 41, 42)); bus.add(y, t, 0, send=.2, rt60=1.2); no dbl
#  b52 stutter: p = hook_line((52, 53, 54)); st = [p[0], (p[0][0], p[0][1] + .5 * BEAT), p[1], (p[1][0], p[1][1] + .5 * BEAT), p[2]]
# sad line (S9; S7 = same with Eb3 = 51):
#  over = sung([('its', SUNG['its'], [Eb4], [8], [.6]), ('so', 'sudden+overo', [G3], [9.25], [1.0])])
#  over[1] = (shelf(over[1][0], -3, 3500), over[1][1])      # then 'over' exactly as now
#  b21 echo (instead of reading the spliced file; this is what build_phrases.build does):
#  e, _, _ = words.phrase([(words.word(k, r)[0], []) for k, r in zip(('its', 'so', 'over'), ('is+t', 'sudden+overo', 'gameover'))], [.05, .05])
# final line: YOU!
#  yy, _ = you.build('mew+tail'); bus.add(shelf(up(yy, bright=.1), -2, 3500), bt(64) - you.LEAD, -1.5, send=.35, rt60=2.2)
```

### Auditions (48 kHz float WAVs)

`W/round2/audition_hook.wav` is the drop's hook, 4 s each (12.65-16.65 s of the song):

| time | variant |
|---|---|
| 0.0 | H0 current |
| 4.8 | H2 |
| 9.6 | H11 |
| 14.4 | H9 |
| 19.2 | H3, low sung (STT: "glad") |
| 24.0 | H7, low sung plus spoken layer ("bad") |
| 28.8 | H5, low sung plus octave-down double ("blood") |

`W/round2/audition_so.wav` is the sad line, 4.2 s each (3.10-7.30 s):

| time | variant |
|---|---|
| 0.0 | S0 current |
| 5.0 | S9 (G3) |
| 10.0 | S7 (Eb3) |
| 15.0 | S11 (Falco o, Eb3) |
| 20.0 | S10 (Falco o, Bb3) |
| 25.0 | S4 (Falco o, G3) |
| 30.0 | S1 (softened No, Eb4) |

`W/you/audition_you.wav` runs from just before "This game's winner is..." through the final stab's ring-out (23.7-28.8 s):

| time | variant |
|---|---|
| 0.0 | current "CAPTAIN FALCON!" |
| 5.9 | mew+tail |
| 11.8 | young+two |
| 17.7 | mew |
| 23.6 | yoshi+two |
