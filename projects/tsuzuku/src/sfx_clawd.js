// sfx_clawd.js: Clawd's world's sound effects (world A 61.0-131.29, the final chorus 177.8-202.59), registered into the paper
// world's stem (src/paper.js PAPER_SFX -> sound/mix.py: levels relative to the song around each cue, no ducking). One clock: every
// time comes from the picture's own keys: Clawd's performed channels (her pinch hands are the snips), Fable's cue sheets
// (FABLESEAT.cue: her brush and her claps; FABLESTAGE.ST / ROOM: the set-down, the walk, the hops), the stage's constants. Where a
// module doesn't expose a key yet, the fallback is its current value (marked).
// Restraint: the song carries Clawd's world. Snips sit at the music's level, taps and Fable's room sounds under it.
{
  const BR = 60 / 170 * 4, BT = BR / 4, b2t = b => b * BR, FR = 1 / 24;
  // each sound's own peak (s from its start, measured from sound/lib/*.wav): a cue is placed so the PEAK lands on the picture's key
  const PK = { snip: .11, paper_tap: .30, page_whoosh: .65, page_turn: .13, blaze: .85, geta: .02, press: .04, lantern_set: .07 };
  const at = (t, name, g) => [t - (PK[name] || 0), name, g];
  const IS = () => (typeof IDOLSTAGE !== 'undefined' ? IDOLSTAGE : {});
  PAPER_SFX.push(() => {
    if (!window.RIGS || !window.CHOREO || !CHOREO.clawdA) return [];
    const S = IS(), KICK = S.KICK ?? .05, E = [];
    // the stage powers up where the card tore (the build: K1's screens coming on in sections), and the glitch ticks (MV layer)
    E.push([61.05, 'led_on', -27]);
    for (const bb of (S.GLITCH || [[43.22], [90.0]]).map(g => g[0] ?? g)) E.push([b2t(bb) + KICK, 'glitch', -33]);   // (fallback: idolstage GLITCH)
    // her snips: every onset of a pinch hand (the hook's snipSnip on the crowd's claps; the claws sections), a frame after it closes
    const snips = (P, b0, b1) => { let prev = false;
      for (let t = b2t(b0); t < b2t(b1); t += FR) { const q = P(t), pin = q.handL === 'pinch' || q.handR === 'pinch';
        if (pin && !prev) E.push(at(t + FR, 'snip', -30)); prev = pin; } };
    snips(CHOREO.clawdA.P(), 45, 93);
    if (CHOREO.clawdF) snips(CHOREO.clawdF.P(), 128, 141);                             // (the finale's call and claws)
    // the crab troupe lands the downbeats for her (Fable's rule): a soft wooden tap, under the song, where they dance (not in the
    // hook, where the snips are the sound)
    for (let bb = 46; bb < 90; bb++) if (bb < 62 || bb >= 66) E.push(at(b2t(bb) + KICK, 'paper_tap', -40));
    for (let bb = 129; bb < 141; bb++) E.push(at(b2t(bb) + KICK, 'paper_tap', -40));
    // the page-wipes (63, 65, 76): the page's whoosh, peaking mid-wipe (the wipe runs 1.6 beats from its bar)
    for (const bb of S.WIPES || [63, 65, 76]) E.push(at(b2t(bb) + .8 * BT, 'page_whoosh', -28));                // (fallback: WIPE1-3)
    // Fable's page turns in the over-the-shoulder cuts: six drawings landing at each card's bar; the rustle starts with the lift
    for (const [bb] of S.CARD_TURNS || [[67.5], [70.45]]) E.push(at(b2t(bb) - 3 / 12, 'page_turn', -29));       // (fallback: CARD_TURNS; the peak mid-turn)
    // Fable in her room (FABLESEAT's cue sheet): the brush as each margin note is written; her claps in chorus 2 (quieter than the hall)
    if (typeof FABLESEAT !== 'undefined') {
      let pp = null, w0 = null;
      for (let t = b2t(45); t < b2t(93); t += FR) {
        const c = FABLESEAT.cue(t), b = t / BR;
        if (c.pose === 'write' && pp !== 'write') w0 = t;
        if (pp === 'write' && c.pose !== 'write' && w0 !== null && t - w0 > .45) E.push([w0 + 2 * FR, 'brush', -34]);   // (not the wipe's brief prep)
        if (c.pose === 'clap' && pp !== 'clap' && b >= 82 && b < 90) E.push([t, 'clap', -35]);
        pp = c.pose;
      }
    }
    // ---- the final chorus
    const F = typeof FABLESTAGE !== 'undefined' ? FABLESTAGE : {}, ROOM = F.ROOM || { setdown: 178.2, walk: 179.2, step: .3 };
    const ST = F.ST || { enter: [128.25, 128.75], dance: 129 }, FIN = (window.CHOREO.clawdF && CHOREO.clawdF.keys) || {};
    E.push(at(178.65, 'blaze', -28));                                                  // the window blazes: starts on the cut (light makes no sound in Fable's world), blooms as she stands illustrated
    E.push(at(ROOM.setdown + 1 / 12, 'lantern_set', -30));                             // the lantern set on her cushion
    for (let k = 0; k < 4; k++) E.push(at(ROOM.walk + (k + 1 / 1.4) * ROOM.step, 'geta', -30 - 2 * k));   // she walks out right (each hop lands at 1/1.4)
    const hop = (ST.dance - ST.enter[0] - .08) / 2;                                    // her two hops onto Clawd's stage, geta landing
    for (let i = 1; i <= 2; i++) E.push(at(b2t(ST.enter[0] + i * hop), 'geta', -28));
    for (const [t0] of FIN.notes || [[189.11], [193.39]]) E.push(at(t0 + .06, 'press', -31));   // F4, F6: her lines pressed in full ink  (fallback: finale NOTES)
    E.push([(FIN.tf ?? 199.07) + .04, 'ring', -37]);                                   // the freeze: the room's air, a faint ring-out  (fallback: TF)
    return E;
  });
}
