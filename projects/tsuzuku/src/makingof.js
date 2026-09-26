// makingof.js: stills for MAKING-OF.md ("one frame, how it's built"). The same song time, taken apart: the stage alone (code:
// LEDs, lights, floor, the hall's readers), then Clawd's rig on it inside Fable's washi card (the card camera, no room), then the
// film's own frame (LOOPS.film: the card filmed in Fable's butai, with her in the room). Not part of the film.
//   node engine/render.mjs projects/tsuzuku --loop=mo_stage --sheet=74.12 --w=1920
{
  const CARD = { cx: 960, cy: 560, z: 1.02, room: null, ots: false };        // (the card's full-body camera, no room around it)
  const troupe = (t, i) => { const ph = (t % (60 / 170)) / (60 / 170); return { hop: 16 * Math.sin(Math.PI * ph), sq: .14 * Math.max(0, 1 - ph / .22) }; };
  const ROWS = [{ xs: [370, 610, 1360, 1670], y: 800, s: .8, seed: 3, lag: .06 }, { xs: [330, 560, 1500, 1810], y: 930, s: 1.05, lag: .04 }];
  LOOPS.mo_stage = t => IDOLSTAGE.frame(t, () => {}, { cam: CARD, notes: { list: [], clear: 1e9 } });
  LOOPS.mo_card = t => {
    const P = CHOREO.clawdA.P();
    IDOLSTAGE.frame(t, (W2S, c) => {
      if (window.mascotTroupe) mascotTroupe(t, troupe, ROWS);
      const q = P(t), [x, y] = W2S(960 + (q.rootX || 0) * .27, 1040); RIGS.clawd.draw(X, t, P, { x, y, s: .27 * c.z });
    }, { cam: CARD });
  };
  LOOPS.mo_stage.len = LOOPS.mo_card.len = 220;
}
