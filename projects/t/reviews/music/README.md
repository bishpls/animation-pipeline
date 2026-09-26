# Choosing the song

Everything here was blind. Files were renamed at random (`key.json` maps names to takes), shuffled for each comparison, and
scored against measurements. Gemini's claims were checked before they counted.

- **Takes a, b, c and d** (`song/plan.json`, 32 s at 120 BPM):
  - `ind*`: each take scored alone, twice.
  - `cmp*`: three shuffled four-way rankings (Borda: a 6, d 6, b 4, c 2).
  - `pair*`: a against d, in both orders. The second file won both times: position bias.
- **Measured** (see `../../README.md`):
  - Stem separation found no vocal energy in a or d (≤ −115 dB), so Gemini's "phantom vocals" were false.
  - No clicks in either tail.
- **Picked d:** its acts land on bars 5, 9 and 13, and its chord rang to silence at 30 s.
- **Takes e1 and e2** (`song/plan_end.json`): d's first 24.057 s as a reference, plus a new ending that carries the groove to a
  final hit on the 30 s downbeat, where the film's clock stops.
  - `epair*`: e1 against e2, in both orders. e1 won both, citing a seam at 0:24 and a "sigh" in e2's tail.
  - `eind*`: scored alone, which said the opposite.
  - Measured:
    - No seam in either: the spectral jump at 24.057 s is smaller than at the neighbouring downbeats.
    - No vocal energy in either tail: both are a piano chord and cymbal.
    - e2 has the fuller ring (−18 vs −22 dB at 30.2 s), the tighter grid (6 ms) and the closest match to d (envelope
      correlation 0.994).
- **Picked e2.** It's `assets/song.mp3`.
