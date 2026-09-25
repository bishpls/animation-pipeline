// mother.js: the exchange's joke (song 37.9-46.7): "...and the mother tried. And the mother went sideways. Hm. Sideways."
// Shadow-theatre physics: 'straight' for a crab on the screen is toward us, so the mother crab (the fan's crab, larger) tries to
// walk straight: carried toward the lamp, her shadow swells and softens (depth); then she veers and scuttles sideways across
// the screen, sharp again. Fable, seated, watches; on "Hm." her head dips once. The little one (Clawd's puppet) watches too.
{
  const S0 = 37.6, TRIED = 37.92, SIDEWAYS = 40.22, HM = 42.4, SIDE2 = 44.76, FLOOR = 962;
  const fable = PUPPET.snap([[0, { head: 6 }], [HM, { head: 13 }], [HM + .5, { head: 6 }]]);
  LOOPS.mother = t => {
    const s = S0 + Math.floor(t * 12 + 1e-6) / 12, beat = 60 / 85 / 2;          // her steps on the 6/8 eighths
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(s, { stops: FABLE_LAMP, tex: .32 });
    const pf = { ...fable(s), _ghost: {} }; pf.hair = -(pf.head || 0) * .85;
    shadow(c => { c.globalCompositeOperation = 'source-over';
      FABLE.draw(c, pf, { x: 420, y: 960, s: .2, origin: [1150, 2760] }, { props: [fanProp(() => ['fan_closed', 'fan_closed', 1], s)] });
      CLAWDP.draw(c, { head: -4, _ghost: {} }, { x: 1560, y: FLOOR, s: .16, origin: [1076, 2800] }, { gel: CLAWD_GEL, misreg: [1.5, 1] });
      c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10);
    }, 0);
    // the mother: phase 1 (TRIED..SIDEWAYS) toward the lamp in stiff steps; phase 2 veers sideways, back to the screen
    const crab = PUPPET.shapeAt(FAN, 'crab', 'crab', 1);
    let x = 900, depth = 0, rock = 0, y = FLOOR;
    const step = k => Math.floor(k);                                            // stop-motion: position changes per step, held between
    if (s >= TRIED && s < SIDEWAYS) { const k = step((s - TRIED) / beat); depth = Math.min(.55, k * .07); rock = k % 2 ? 2 : -2; y = FLOOR - 6 * (k % 2); }
    else if (s >= SIDEWAYS) { const k = step((s - SIDEWAYS) / (beat / 2)); depth = Math.max(0, .55 - k * .12); x = 900 + Math.min(k, 30) * 16 * (s < SIDE2 ? 1 : -1.2) + (s >= SIDE2 ? 30 * 16 : 0); rock = 5 * (k % 2 ? 1 : -1); y = FLOOR - 10 * (k % 2); }
    // held nearer the lamp, the shadow grows about the lamp's point; lift the puppet so its shadow still stands on the floor
    const [lx, ly] = SCREEN.lamp, sp = 1 / (1 - Math.min(depth, .8) * .5), yy = ly + (y - ly) / sp;
    shadow(c => { c.globalCompositeOperation = 'source-over'; PUPPET.drawShape(c, crab, new DOMMatrix().translate(x, yy).rotate(rock).scale(.26 * 1.4)); }, depth, { penumbra: true });
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(s * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.mother.len = 9;
}
