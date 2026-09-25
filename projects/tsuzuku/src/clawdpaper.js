// clawdpaper.js: Clawd's cut-paper puppet in Fable's world (LOOPS.clawdpaper): black paper, one clay-orange cellophane plate
// (misregistered), eye slits of lantern light, a hinged paper jaw on her words, rivets. Stop-motion on twos: holds, one
// in-between, a drawing past, the pose; Reiniger hops (the knees tuck in the air, one dip on landing).
async function CLAWDP_INIT() { window.CLAWDP = await PUPPET.load('rig/clawd_paper/puppet.json'); }
const CLAWD_GEL = 'rgba(236, 110, 52, .9)';
{
  const B = 60 / 170 * 4, b = n => n * B, f = 1 / 12;
  // "Show me how! Walk it first, and I'll walk right behind!" (words.json, from 31.30 s), replayed from bar 1
  const WSTART = 31.30, OFF = WSTART - b(1);
  const jawAt = tq => {
    const W = (window.WORDS || []).filter(w => w.who === 'clawd' && w.t0 >= WSTART - .05 && w.t0 < WSTART + 3.5);
    for (const w of W) { const a = w.t0 - OFF, z = w.t1 - OFF; if (tq >= a && tq < z) { const u = (tq - a) / Math.max(.08, z - a); return u < .7 ? 9 : 4; } }
    return 0;
  };
  const pose = PUPPET.snap([
    [0,        { head: 0, torso: 0, upperarm_L: 0, forearm_L: 0, claw_L: 0, upperarm_R: 0, forearm_R: 0, claw_R: 0 }],
    [b(.6),    { head: -6 }],                                                            // she looks up
    [b(1),     { upperarm_R: -95, forearm_R: -30, claw_R: -10, head: 4 }],               // "Show me how!": the claw goes up
    [b(2),     { upperarm_L: 40, forearm_L: 20, torso: -3 }],                            // "walk it first": points the way
    [b(2.75),  { upperarm_R: 0, forearm_R: 0, claw_R: 0, upperarm_L: 0, forearm_L: 0, torso: 0, head: 0 }],
    [b(4),     { upperarm_L: 95, forearm_L: 30, upperarm_R: -95, forearm_R: -30, head: -5 }],   // both claws up: "Sorekara?!"
    [b(5),     { upperarm_L: 0, forearm_L: 0, upperarm_R: 0, forearm_R: 0, head: 0 }],
  ]);
  // hops: [t, height px]: a take-off drawing (knees dip), three air drawings (knees tucked), a landing dip, then the stand
  const HOPS = [[b(1), 60], [b(3.25), 40], [b(3.6), 40], [b(4), 90]];
  const hop = tq => {
    const p = { dy: 0, thigh_L: 0, thigh_R: 0, shin_L: 0, shin_R: 0, 'shin_L.y': 0, 'shin_R.y': 0 };
    for (const [t0, h] of HOPS) {
      const d = Math.round((tq - t0) * 12);
      // a front-facing puppet can't fold its knees back: the dip bends the knees a little outward, and in the air the legs come
      // together and the boots lift (shin 'lift' along the thigh), so the silhouette reads as a tucked hop, not a frog kick
      if (d === 0 || d === 5) { p.dy = 10; p.thigh_L = -5; p.thigh_R = 5; p.shin_L = 8; p.shin_R = -8; }       // dip
      else if (d >= 1 && d <= 4) { p.dy = -h * Math.sin(Math.PI * d / 5); p.thigh_L = 4; p.thigh_R = -4; p['shin_L.y'] = -70; p['shin_R.y'] = -70; }
    }
    return p;
  };
  LOOPS.clawdpaper = t => {
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(tq, { stops: FABLE_LAMP, tex: .32 });
    const p = { ...pose(tq), ...hop(tq), jaw: jawAt(tq), _ghost: {} };
    const T = { x: 960, y: 950, s: .26, origin: [1076, 2800] };
    shadow(c => { c.globalCompositeOperation = 'source-over';
      CLAWDP.draw(c, p, T, { gel: CLAWD_GEL, misreg: [2, 1.5], ghosts: ['upperarm_R', 'upperarm_L'],
        rods: [{ part: 'torso', at: [1076, 1200], w: 6 }, { part: 'claw_R', at: [1640, 1600], w: 3, lean: 40 }, { part: 'claw_L', at: [512, 1600], w: 3, lean: -40 }] });
      c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, 952, 1620, 10);
    }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(tq * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.clawdpaper.len = b(6);
}
