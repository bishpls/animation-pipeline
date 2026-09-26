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
  // the unfold in the light (Fable, round 2, as Michael cut it: no change of size; she is born at her own size, on the floor).
  // As the crab unfolds, the lamp's light pours through the thinning sheet: the paper turns a luminous gold-orange (the gel
  // thinner and purer), holds through the square, the cut and her waking, and settles back to her denser red-orange as her claw
  // comes down, before the readers' call
  const LIGHT0 = UNFOLD - 2 * f, LIGHT1 = SQUARE, SETTLE0 = bar(24.2), SETTLE1 = 35.12;
  const lightAt = ts => {
    if (ts < LIGHT0 || ts >= SETTLE1) return 0;
    const e = u => u * u * (3 - 2 * u);
    if (ts < LIGHT1) return e((ts - LIGHT0 + f) / (LIGHT1 - LIGHT0 + f));
    return ts < SETTLE0 ? 1 : 1 - e((ts - SETTLE0) / (SETTLE1 - SETTLE0));
  };
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
  // the little one at (ax, ay) (null: where she is on the floor); k: how much of the lamp's light is coming through her paper (0..1)
  // (lit through, the paper passes more light: thinner (alpha down) and purer (blue out), so brighter and more saturated)
  const gelAt = (rgb, a, k, to) => k > 0 ? `rgba(${rgb.map((v, i) => Math.round(v + (to[i] - v) * k))}, ${(a - .2 * k).toFixed(3)})` : `rgba(${rgb}, ${a})`;
  // the flat square (the director: it read as flat, see-through gel). An unfolded sheet keeps the relief of its folds: eight
  // facets around the centre, each a plane tilted a little, toward the lamp or away, alternating; the mountains (the diagonals)
  // a light ridge, the valleys (the centre lines) a dark line, the quarter creases fainter. And it's paper: what's
  // behind it (the mother's claws) doesn't show through. Shape px: the square is 2900 across, standing on y 0
  function sheet(c, M, gel) {
    const S = 1450, C = [0, -S], sq = new Path2D(); sq.rect(-S, -2 * S, 2 * S, 2 * S);
    c.save(); c.setTransform(M);
    c.globalCompositeOperation = 'destination-out'; c.fillStyle = '#000'; c.fill(sq);
    c.globalCompositeOperation = 'source-over'; c.fillStyle = gel; c.fill(sq); c.clip(sq);
    const R = [[S, 0], [S, -S], [0, -S], [-S, -S], [-S, 0], [-S, S], [0, S], [S, S]].map(([dx, dy]) => [C[0] + dx, C[1] + dy]);   // rays: edge middles (valleys) and corners (mountains), alternating
    for (let i = 0; i < 8; i++) {                                     // each facet a plane, tilted as one piece: toward the lamp or away, alternating
      const A = R[i], B = R[(i + 1) % 8];
      c.fillStyle = i % 2 ? 'rgba(96,34,4,.13)' : 'rgba(255,226,160,.09)'; c.beginPath(); c.moveTo(...C); c.lineTo(...A); c.lineTo(...B); c.closePath(); c.fill();
    }
    c.lineCap = 'round';
    const line = (x0, y0, x1, y1, w, col, dx = 0, dy = 0) => { c.strokeStyle = col; c.lineWidth = w; c.beginPath(); c.moveTo(x0 + dx, y0 + dy); c.lineTo(x1 + dx, y1 + dy); c.stroke(); };
    line(-S, 0, S, -2 * S, 10, 'rgba(255,236,190,.55)'); line(-S, -2 * S, S, 0, 10, 'rgba(255,236,190,.55)');   // the mountains: ridges, lit
    line(-S, 0, S, -2 * S, 7, 'rgba(110,38,8,.35)', 12, 12); line(-S, -2 * S, S, 0, 7, 'rgba(110,38,8,.35)', -12, 12);   // (each with its shaded flank)
    line(0, 0, 0, -2 * S, 9, CREASE); line(-S, -S, S, -S, 9, CREASE);                                            // the valleys
    for (const q of [-S / 2, S / 2]) { line(q, 0, q, -2 * S, 6, 'rgba(128,42,12,.4)'); line(-S, -S + q, S, -S + q, 6, 'rgba(128,42,12,.4)'); }   // the quarter creases
    c.restore();
  }
  function drawIt(c, ts, ax, ay, k = 0) {
      c.globalCompositeOperation = 'source-over';
      const gel = gelAt([236, 118, 58], .92, k, [255, 160, 14]), cgel = k > 0 ? gelAt([236, 110, 52], .9, k, [255, 152, 12]) : CLAWD_GEL;
      if (ts < CUT) {
        const [a, b, u] = unfold(ts), sh = PUPPET.shapeAt(ORI, a, b, u);   // the creases lead (the fold lines appear before the paper moves)
        const hopping = ts > bar(17.5) && ts < bar(19.5), ph = ((ts - bar(17.5)) / (B / 2)) % 1;
        const x = ax ?? (ts < UNFOLD ? crabX(ts) : CX), y = ay - (hopping && ax == null ? 14 * Math.sin(Math.PI * ph) : 0), rock = hopping ? 5 * Math.sin(2 * Math.PI * ph) : 0;
        const lk = ts < UNFOLD ? lookAt(ts) : 0;                           // tipped back on its rear legs: shorter, lifted a little
        const M = new DOMMatrix().translate(x, y - 16 * lk).rotate(rock).scale(SC, SC * (1 - .16 * lk));
        if (a === 'osquare' || (b === 'osquare' && u >= 1)) sheet(c, M, gel);   // the flat square: paper that has been folded
        else PUPPET.drawShape(c, sh, M, null, { gel, crease: CREASE });
        if (ts >= PENCIL) {                                                // she is drawn before she is cut: one faint pencil line on the sheet
          const o = ORI.S.opuppet.o; c.save(); c.setTransform(M); c.beginPath(); c.moveTo(o[0][0], o[0][1]); for (const q of o) c.lineTo(q[0], q[1]); c.closePath();
          c.strokeStyle = 'rgba(70,40,24,.45)'; c.lineWidth = 7; c.stroke(); c.restore();
        }
      } else if (ts < KEYLINE) {                                           // the cut: her silhouette in the orange paper, one snip
        PUPPET.drawShape(c, PUPPET.shapeAt(ORI, 'opuppet', 'opuppet', 1), new DOMMatrix().translate(ax ?? CX, ay).scale(SC), null, { gel, crease: 'rgba(0,0,0,0)' });
      } else {
        const p = { ...clawd(ts), jaw: ts >= EYES ? jawAt(ts) : 0, _ghost: {} };
        const cover = ts < RIVETS ? allCover([...RIV, ...EYE_PTS]) : ts < EYES ? allCover(EYE_PTS) : {};   // rivets punched, then the eyes light
        CLAWDP.draw(c, p, { x: ax ?? CX, y: ay, s: SC, origin: [1076, 2800] }, { gel: cgel, misreg: [1.5, 1], cover,
          rods: [{ part: 'torso', at: [1076, 1200], w: 5 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 30 }] });
      }
  }
  // (shared with the verse's continuous timeline)
  window.ORIGAMI_DRAW = (c, ts) => drawIt(c, ts, null, FLOOR, lightAt(ts));
  window.ORIGAMI = { CX, SC, EYES, UNFOLD, FLOOR };
  LOOPS.origami.len = 12;
}
