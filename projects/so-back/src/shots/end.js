// SO BACK: the end (beat 64 on, 25.65-28.8). "THIS GAME'S WINNER IS..." (drop2) -> "YOU!" on the final stab (Michael):
//   25.65  YOU!: the game's own Game! slams on the stab (lane 1's real one-stock match, Falcon's winning KO): the 4:3 game
//          screen framed in the vertical frame (the game itself, honestly), its blurred copy filling the rest
//   26.10  Falcon's taunt close-up: he turns to the lens, raises an open palm, and his own voice answers the announcer:
//          "Show me ya moves!" (Michael: "fantastic"). Voice onset 26.28, the palm's peak 26.48
//   27.00  his victory screen (the B pose, chosen in the lab): the flying kick lands into a low guard, palm out, facing the viewer
//   28.80  the last frame goes white; frame 0 is the knee (the loop). No end-card text (Michael).
const END = {
  game: () => keyedPlate('assets/plates/soback_end_game/v43', 215),
  taunt: () => vplate('sacred_taunt', 90),
  victory: () => vplate('end_victory', 160),
  slam: pf(104),                    // the end_game frame where Game! slams in
  taunt0: 26.10, tauntClip0: .25,   // the taunt clip's time at taunt0 (its voice onset is clip .433, the palm's peak .633)
  vic0: 27.00, vicClip0: pf(20),    // the victory clip from frame 20 (after the emblem sweep): the guard holds from ~28.3
  t1: 28.8,
};
const endPl = {}; const endPlate = k => endPl[k] || (endPl[k] = END[k]());

function END_GAME(t) {
  const K = endPlate('game'), pt = END.slam + (t - bt(64)) * .9;
  const sw = W, sh = W * 3 / 4, sy = H * .5 - sh / 2;            // the 4:3 screen, 1080 x 810, centred
  const z = punch(t, bt(64), .1, .35);
  const b = scene(() => {
    X.save(); X.filter = 'blur(28px) brightness(.45) saturate(1.3)'; drawPlate(K, pt, (W - H * 4 / 3) / 2, 0, H * 4 / 3, H); X.restore();
    X.save(); zoomAt(W / 2, sy + sh / 2, z);
    X.fillStyle = PAL.ink; X.fillRect(-14, sy - 14, sw + 28, sh + 28);                      // the bezel
    drawPlate(K, pt, 0, sy, sw, sh);
    X.restore();
  });
  if (NEED) return;
  present(b, 'saturate(1.1)', 9 * Math.exp(-Math.max(0, t - bt(64)) * 14));
  return { cap: { y: 330, finale: { y: 300 } } };
}

function END_TAUNT(t) {
  const K = endPlate('taunt'), pt = END.tauntClip0 + (t - END.taunt0);
  const peak = END.taunt0 + (.633 - END.tauntClip0), z = 1.04 + .08 * E.out2(clamp((t - END.taunt0) / .8));
  const b = scene(() => { X.save(); zoomAt(W * .4, H * .32, z * punch(t, peak, .06, .3)); drawPlate(K, pt); X.restore(); });
  if (NEED) return;
  present(b, 'saturate(1.18) contrast(1.05)', t < peak ? 0 : 8 * Math.exp(-(t - peak) * 8));
  return { cap: { y: 1330 } };                                     // his face and palm are high: the words sit on his chest
}

function END_VICTORY(t) {
  const K = endPlate('victory'), pt = Math.min(pf(160), END.vicClip0 + (t - END.vic0));
  const z = 1.02 + .05 * clamp((t - END.vic0) / 1.8);
  const b = scene(() => { X.save(); zoomAt(W / 2, H * .55, z); drawPlate(K, pt); X.restore(); });
  if (NEED) return;
  present(b, 'saturate(1.15)', 8 * Math.exp(-(t - END.vic0) * 8));
  flash(1 - clamp((END.t1 - t) / (1 / 60)));                     // the loop: the last frame goes white, frame 0 is the knee
  return { cap: { y: 330 } };
}

shots([
  [bt(64), END_GAME],
  [END.taunt0, END_TAUNT],
  [END.vic0, END_VICTORY],
]);

// the game's own sound: his taunt voice (the clip from .25, the voice from .433). The Game! and victory clips carry the
// announcer's own "GAME!" and "This game's winner is... CAPTAIN FALCON!", which would talk over our "YOU!": left out.
SFX.push(
  [END.taunt0, 'sacred_taunt', END.tauntClip0, 1.0, 4, 'post', '"Show me ya moves!"'],
);
