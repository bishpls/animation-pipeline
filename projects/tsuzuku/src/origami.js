// origami.js: verse 1 into the exchange (LOOPS.origami, on the song's own clock, song 24.0-36.0 s): the little crab, folded
// from one square of clay-orange paper, side-steps on the floor ("why d'you scuttle side to side?"), looks up ("and the little
// one looked up, and said—"), and on "Show me how!" unfolds in stop-motion (crab -> folded base -> the flat sheet -> her
// outline, three drawings each) into Clawd's riveted cut-paper puppet, who sings. Fable, seated, tells it.
async function ORIGAMI_INIT() { window.ORI = await PUPPET.loadShapes('rig/clawd_paper/origami/origami.json'); }
{
  const B = 60 / 170 * 4, bar = n => n * B, S0 = 24.0, FLOOR = 962;
  const PAPER_GEL = 'rgba(236, 118, 58, .92)', CREASE = 'rgba(128, 42, 12, .8)';
  const UNFOLD = bar(21.5);                                          // song time: the unfold starts, lands on "Show me how!"
  // three drawings per fold; the flat sheet is held two more (the key image: the whole square, opened)
  const unfold = PUPPET.morphs([[0, 'ocrab'], [UNFOLD, 'obase'], [UNFOLD + 3 / 12, 'osquare'], [UNFOLD + 8 / 12, 'opuppet']], { hold: 1 });
  const DONE = UNFOLD + 11 / 12;                                      // the next drawing is the jointed puppet
  const CX = 1250, SC = .16;                                           // where she stands; her scale (the little one)
  // the crab: side-steps (small rocking hops, on twos) left and right, then settles and looks up
  const crabX = ts => { const u = Math.max(0, Math.min(1, (ts - bar(17.5)) / bar(2))); return CX + 110 * Math.sin(Math.PI * 2 * u) * (1 - u * .3); };
  const fable = PUPPET.snap([[0, { head: 0, forearm: 0, hand: 0 }], [bar(19.5), { head: 5 }], [bar(21.25), { head: 9, forearm: 12, hand: -6 }]]);   // she looks down at it
  const WSTART = 31.30;
  const jawAt = ts => { for (const w of (window.WORDS || [])) if (w.who === 'clawd' && w.t0 >= WSTART - .05 && ts >= w.t0 && ts < w.t1) return (ts - w.t0) / Math.max(.08, w.t1 - w.t0) < .7 ? 9 : 4; return 0; };
  const clawd = PUPPET.snap([[0, { head: 0, upperarm_R: 0, forearm_R: 0 }], [DONE, { head: -8 }], [DONE + .25, { upperarm_R: -95, forearm_R: -30, claw_R: -10 }], [bar(24.2), { upperarm_R: 0, forearm_R: 0, claw_R: 0, head: 0 }]]);
  LOOPS.origami = t => {
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;                   // song time, on twos
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(ts, { stops: FABLE_LAMP, tex: .32 });
    const pf = { ...fable(ts), _ghost: {} }; pf.hair = -(pf.head || 0) * .85;
    shadow(c => {
      c.globalCompositeOperation = 'source-over';
      FABLE.draw(c, pf, { x: 560, y: 960, s: .2, origin: [1150, 2760] }, { props: [fanProp(() => ['fan_closed', 'fan_closed', 1], ts)] });
      if (ts < DONE) {
        const [a, b, u] = unfold(ts), sh = PUPPET.shapeAt(ORI, a, b, u);   // the creases lead (the fold lines appear before the paper moves)
        const hopping = ts > bar(17.5) && ts < bar(19.5), ph = ((ts - bar(17.5)) / (B / 2)) % 1;
        const x = ts < UNFOLD ? crabX(ts) : CX, y = FLOOR - (hopping ? 14 * Math.sin(Math.PI * ph) : 0);
        const look = ts > bar(20.3) && ts < UNFOLD ? -14 : 0, rock = hopping ? 5 * Math.sin(2 * Math.PI * ph) : 0;
        PUPPET.drawShape(c, sh, new DOMMatrix().translate(x, y).rotate(look + rock).scale(SC), null, { gel: PAPER_GEL, crease: CREASE });
      } else {
        const p = { ...clawd(ts), jaw: jawAt(ts), _ghost: {} };
        CLAWDP.draw(c, p, { x: CX, y: FLOOR, s: SC, origin: [1076, 2800] }, { gel: CLAWD_GEL, misreg: [1.5, 1],
          rods: [{ part: 'torso', at: [1076, 1200], w: 5 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 30 }] });
      }
      c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10);
    }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.origami.len = 12;
}
