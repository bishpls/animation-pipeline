// SO BACK: the cut. Every shot is on the song clock (150 BPM, beat 0 at 0.05 s; see STORYBOARD.md). Unbuilt shots are slates.

// the cut: this file registers the spine's sections (src/shots/spine.js, mine); src/shots/drop.js registers beats 35-48,
// src/shots/drop2.js beats 48-64 and src/shots/end.js from beat 64 on, each in its own file (one owner per file)
shots([
  [0, COLD],
  [TS1, OVER],
  [bt(24), TURN],
  [SP.punch, PUNCH],
]);

PROJECT.overlay = (t, ret) => captions(t, ret);
