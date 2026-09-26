// origami.js: verse 1 into the exchange (LOOPS.origami, on the song's own clock, song 24.0-36.0 s): the little crab, folded
// from one square of clay-orange paper, side-steps on the floor ("why d'you scuttle side to side?"), looks up ("and the little
// one looked up, and said—"), and on "Show me how!" unfolds in stop-motion (crab -> folded base -> the flat sheet -> her
// outline, three drawings each) into Clawd's riveted cut-paper puppet, who sings. Fable, seated, tells it.
async function ORIGAMI_INIT() { window.ORI = await PUPPET.loadShapes('rig/clawd_paper/origami/origami.json'); }
{
  const B = 60 / 170 * 4, bar = n => n * B, S0 = 24.0, FLOOR = 962;
  const PAPER_GEL = 'rgba(236, 118, 58, .92)', CREASE = 'rgba(128, 42, 12, .8)';
  // Counted in drawings (12 fps) back from EYES, the first drawing on the first syllable of "Show" (31.30 s). Fable's order:
  // crab -> folded base -> the flat square (held, silent) -> her figure pencilled on the sheet -> the cut (orange silhouette)
  // -> black keyline, rods rising -> every rivet in one drawing ('tk') -> on "Show", the eye-slits light and the jaw opens.
  const f = 1 / 12, EYES = Math.ceil(31.30 * 12 - 1e-6) / 12;
  const D = n => EYES - n * f;                                         // the drawing n before EYES
  const UNFOLD = D(12), SQUARE = D(6), PENCIL = D(4), CUT = D(3), KEYLINE = D(2), RIVETS = D(1);
  const unfold = PUPPET.morphs([[0, 'ocrab'], [UNFOLD, 'obase'], [UNFOLD + 3 * f, 'osquare']], { hold: 1 });
  const DONE = KEYLINE;
  const CX = 1250, SC = .16;                                           // where she stands; her scale (the little one)
  const crabX = ts => { const u = Math.max(0, Math.min(1, (ts - bar(17.5)) / bar(2))); return CX + 110 * Math.sin(Math.PI * 2 * u) * (1 - u * .3); };
  const LOOK = bar(20.3);                                              // "and the little one looked up": the shell tips back, two drawings, hold
  const lookAt = ts => ts < LOOK ? 0 : ts < LOOK + f ? .5 : 1;
  const fable = PUPPET.snap([[0, { head: -10, forearm: 0, hand: 0 }], [28.59 - 2 / 12, { head: 3 }], [bar(21.25), { head: 9, forearm: 12, hand: -6 }]]);   // the mother's voice (head up) to "does."; the narrator (level) from "And the little one"; she looks down at it
  const WSTART = 31.30;
  const jawAt = ts => { for (const w of (window.WORDS || [])) if (w.who === 'clawd' && w.t0 >= WSTART - .05 && ts >= w.t0 && ts < w.t1) return (ts - w.t0) / Math.max(.08, w.t1 - w.t0) < .7 ? 9 : 4; return 0; };
  const clawd = PUPPET.snap([[0, { head: 0, upperarm_R: 0, forearm_R: 0 }], [EYES, { head: -8 }], [EYES + .25, { upperarm_R: -95, forearm_R: -30, claw_R: -10 }], [bar(24.2), { upperarm_R: 0, forearm_R: 0, claw_R: 0, head: 0 }]]);
  const RIV = [[850, 1044], [716, 1272], [552, 1494], [1304, 1044], [1434, 1272], [1604, 1494], [894, 1962], [894, 2160], [1254, 1962], [1260, 2160]];
  const EYE_PTS = [[956, 704], [1187, 713]];
  const allCover = pts => Object.fromEntries(CLAWDP.parts.map(q => [q.name, pts]));
  PAPER_SFX.push(() => { const E = [[UNFOLD, 'paper_fold', -28], [UNFOLD + 3 * f, 'paper_fold', -28], [CUT, 'snip', -26], [RIVETS, 'rivet', -28]];   // SFX_CUES: silence on the held square
    for (let k = 1; k <= 4; k++) E.push([bar(17.5) + k * B / 2, 'paper_tap', -35]); return E; });                                // her side-steps
  LOOPS.origami = t => {
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;                   // song time, on twos
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(ts, { stops: FABLE_LAMP, tex: .32 });
    if (window.SHORE) shore(ts, { floor: FLOOR });
    const fpose = tt => { const p = { ...fable(Math.floor(tt * 12 + 1e-6) / 12), _ghost: {} }; p.hair = -(p.head || 0) * .85; return p; }, pf = fpose(ts), TF = { x: 560, y: 960, s: .2, origin: [1150, 2760] };
    shadow(c => {
      seatedRibbon(c, fpose, TF, ts);
      if (window.VERSE_SET) VERSE_SET(c, ts);                        // the mother and the line, where the telling set them
      FABLE.draw(c, pf, TF, { props: [fanProp(() => ['fan_closed', 'fan_closed', 1], ts)], rods: FABLE_RODS });
      ORIGAMI_DRAW(c, ts);
      if (!window.SHORE) { c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10); }
    }, 0);
    if (window.VERSE_ROW) VERSE_ROW(ts);                               // V3: everybody else, walking straight
    if (window.pageVellum) pageVellum(ts);                              // the page's vellum ink (the strip: stage())
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  // the little one and her unfolding, at song time ts, into a shadow() layer (shared with the verse's continuous timeline)
  window.ORIGAMI_DRAW = (c, ts) => {
      c.globalCompositeOperation = 'source-over';
      if (ts < CUT) {
        const [a, b, u] = unfold(ts), sh = PUPPET.shapeAt(ORI, a, b, u);   // the creases lead (the fold lines appear before the paper moves)
        const hopping = ts > bar(17.5) && ts < bar(19.5), ph = ((ts - bar(17.5)) / (B / 2)) % 1;
        const x = ts < UNFOLD ? crabX(ts) : CX, y = FLOOR - (hopping ? 14 * Math.sin(Math.PI * ph) : 0), rock = hopping ? 5 * Math.sin(2 * Math.PI * ph) : 0;
        const lk = ts < UNFOLD ? lookAt(ts) : 0;                           // tipped back on its rear legs: shorter, lifted a little
        const M = new DOMMatrix().translate(x, y - 16 * lk).rotate(rock).scale(SC, SC * (1 - .16 * lk));
        PUPPET.drawShape(c, sh, M, null, { gel: PAPER_GEL, crease: CREASE });
        if (ts >= PENCIL) {                                                // she is drawn before she is cut: one faint pencil line on the sheet
          const o = ORI.S.opuppet.o; c.save(); c.setTransform(M); c.beginPath(); c.moveTo(o[0][0], o[0][1]); for (const q of o) c.lineTo(q[0], q[1]); c.closePath();
          c.strokeStyle = 'rgba(70,40,24,.45)'; c.lineWidth = 7; c.stroke(); c.restore();
        }
      } else if (ts < KEYLINE) {                                           // the cut: her silhouette in the orange paper, one snip
        PUPPET.drawShape(c, PUPPET.shapeAt(ORI, 'opuppet', 'opuppet', 1), new DOMMatrix().translate(CX, FLOOR).scale(SC), null, { gel: PAPER_GEL, crease: 'rgba(0,0,0,0)' });
      } else {
        const p = { ...clawd(ts), jaw: ts >= EYES ? jawAt(ts) : 0, _ghost: {} };
        const cover = ts < RIVETS ? allCover([...RIV, ...EYE_PTS]) : ts < EYES ? allCover(EYE_PTS) : {};   // rivets punched, then the eyes light
        CLAWDP.draw(c, p, { x: CX, y: FLOOR, s: SC, origin: [1076, 2800] }, { gel: CLAWD_GEL, misreg: [1.5, 1], cover,
          rods: [{ part: 'torso', at: [1076, 1200], w: 5 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 30 }] });
      }
  };
  window.ORIGAMI = { CX, SC, EYES, UNFOLD, FLOOR };
  LOOPS.origami.len = 12;
}
