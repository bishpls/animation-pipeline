// e_finale.js: shots 39–49. The bridge (mirror, learning, borrowed words, "this one's mine"), the key-change chorus, the outro.
(() => {
  // ---------------------------------------------------------------- helpers
  const KB = { k08_mirror: [394, 14, 1908, 1536], k09_mine: [236, 0, 2530, 1536], k10a: [700, 0, 2053, 1536], k10b: [781, 21, 2078, 1500], k11_reach: [35, 0, 2728, 1536], k12_tehe: [709, 0, 2361, 1536] };
  const KS = W / 2752;
  // draw a keyed illustration where it sat in its original 16:9 frame (plus dx, dy), rigged for life
  function key(name, o = {}) {
    const b = KB[name];
    const cx = (b[0] + b[2]) / 2 * KS + (o.dx || 0), cy = (b[1] + b[3]) / 2 * KS + (o.dy || 0), h = (b[3] - b[1]) * KS;
    rig(name, cx, cy, h, { t: o.t ?? NOW, sway: o.sway ?? 5, anchorY: o.anchorY ?? .62, breath: o.breath ?? .007, swayFreq: o.swayFreq ?? .5 });
  }
  // offscreen layer: draw something, tint it (source-atop), composite it back
  const OFF = document.createElement('canvas'); OFF.width = W; OFF.height = H; const OX = OFF.getContext('2d');
  function layer(draw, tint) {
    const X0 = X, m = X0.getTransform(); X = OX;
    X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = 1; X.globalCompositeOperation = 'source-over'; X.clearRect(0, 0, W, H);
    X.setTransform(m); draw();
    if (tint) { X.setTransform(1, 0, 0, 1, 0, 0); X.globalCompositeOperation = 'source-atop'; tint(); X.globalCompositeOperation = 'source-over'; }
    X = X0; X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.drawImage(OFF, 0, 0); X.restore();
  }
  const zoomAt = (px, py, z) => { X.translate(px, py); X.scale(z, z); X.translate(-px, -py); };
  const tw = t => onTwos(t);                         // character drawings on twos
  const withNow = (t, fn) => { const n = NOW; NOW = t; fn(); NOW = n; };
  const hasSeq = name => SEQ[name] && SEQ[name].frames[0] && SEQ[name].frames[0].width > 0;
  const puff = (x, y, r, k, col = C_.white) => {      // a PSG smoke poof: ring of balls expanding, then gone
    if (k <= 0 || k >= 1) return;
    const n = 9, rr = r * (.4 + .9 * E.out3(k)), br = r * .42 * (1 - E.in2(k));
    for (let i = 0; i < n; i++) { const a = i / n * TAU + k; shp(circle(x + Math.cos(a) * rr, y + Math.sin(a) * rr * .8, br, 20), col, 5); }
    if (k < .5) shp(circle(x, y, r * .6 * (1 - k * 2), 24), col, 5);
  };
  const pixelHeart = (cx, cy, px, col = C_.pink, glowK = 0) => {
    const M = ['.XX.XX.', 'XXXXXXX', 'XXXXXXX', '.XXXXX.', '..XXX..', '...X...'];
    if (glowK) glow(cx, cy, px * 7 * (1 + glowK), 'rgba(255,120,190,1)', .7 * glowK);
    M.forEach((row, j) => [...row].forEach((c, i) => { if (c === 'X') shp(rect(cx + (i - 3.5) * px, cy + (j - 3) * px, px, px), col, 3); }));
  };

  // ---------------------------------------------------------------- the mirror (39, and the start of 40)
  const MIR = { cx: 1390, cy: 548, rx: 390, ry: 470 };
  const glass = () => ellipse(MIR.cx, MIR.cy, MIR.rx, MIR.ry, 0, 96);
  function mirrorBack() {
    shp(ellipse(MIR.cx, MIR.cy, MIR.rx + 34, MIR.ry + 34, 0, 96), C_.lemonD, LW);
    shp(ellipse(MIR.cx, MIR.cy, MIR.rx + 18, MIR.ry + 18, 0, 96), C_.lemon, 4);
  }
  function mirrorFrame() {
    lin(glass().concat([glass()[0]]), 6, C_.ink);
    for (let i = 0; i < 12; i++) { const a = i / 12 * TAU; fil(circle(MIR.cx + Math.cos(a) * (MIR.rx + 26), MIR.cy + Math.sin(a) * (MIR.ry + 26), 7), C_.white); }
    spark8(MIR.cx, MIR.cy - MIR.ry - 40, 34, C_.lemon, 5);
  }
  function mirrorScene(t, inside) {           // the room: dark, one spotlight, the mirror, her
    flat(C_.nightD);
    // the spotlight cone from the top-left onto her
    X.save(); X.globalAlpha = .16; X.fillStyle = '#C9B8FF'; X.beginPath(); X.moveTo(560, -40); X.lineTo(220, 1100); X.lineTo(1100, 1100); X.lineTo(760, -40); X.fill(); X.restore();
    glow(640, 560, 520, 'rgba(190,170,255,1)', .35);
    // floating dust in the beam
    for (let i = 0; i < 26; i++) { const y = frac(hash(i * 3.3) + t * .03 * (1 + hash(i))) * 1100, x = 300 + hash(i * 5.1) * 600 + Math.sin(t + i) * 20; fil(circle(x, 1100 - y, 2 + hash(i) * 2.5), 'rgba(255,255,255,.55)'); }
    // the mirror: frame rings, glass, then what's inside it
    mirrorBack();
    fil(glass(), '#2E2257');
    clipTo(glass(), () => {
      inside(t);
      // glass sheen: two diagonal paper-white bars
      X.save(); X.globalAlpha = .12; X.fillStyle = '#FFFFFF'; X.beginPath(); X.moveTo(MIR.cx - 120, MIR.cy - 520); X.lineTo(MIR.cx + 20, MIR.cy - 520); X.lineTo(MIR.cx - 260, MIR.cy + 520); X.lineTo(MIR.cx - 400, MIR.cy + 520); X.fill();
      X.beginPath(); X.moveTo(MIR.cx + 80, MIR.cy - 520); X.lineTo(MIR.cx + 120, MIR.cy - 520); X.lineTo(MIR.cx - 160, MIR.cy + 520); X.lineTo(MIR.cx - 200, MIR.cy + 520); X.fill(); X.restore();
    });
    mirrorFrame();
  }
  const TOUCH = [1030, 652];                  // where her palm meets the glass
  function reflection(t) {                     // block Clawd in the glass: fades in on "mirror", meets her palm, waves on "new"
    const a = seg(t, 119.2, 119.55);
    X.save(); X.globalAlpha = a;
    glow(MIR.cx - 150, 640, 360, 'rgba(255,170,120,1)', .5 * a);
    const reach = E.back(seg(t, 119.35, 119.75)), wave = t > 120.0 ? Math.sin((t - 120.0) * 12) * .35 : 0;
    const happy = t > 119.95;
    withNow(tw(t), () => clawd(1262, 850, 1.45, { armL: .15 + .45 * reach, armR: happy ? .9 + wave : .2, eyes: happy ? 'happy' : 'open', blush: happy ? 1 : 0, hop: happy ? 6 * Math.abs(Math.sin((t - 120) * 9)) : 0, seed: 7 }));
    X.restore();
    // the touch: a soft ring where palm meets nub
    const touch = seg(t, 119.72, 120.3);
    if (touch > 0 && touch < 1) { X.save(); X.globalAlpha = 1 - touch; lin(circle(TOUCH[0] + 8, TOUCH[1], 20 + 90 * E.out3(touch), 40).concat([[TOUCH[0] + 28 + 90 * E.out3(touch), TOUCH[1]]]), 5, C_.lemon); X.restore(); }
    if (t > 119.72) sparkle(TOUCH[0] + 10, TOUCH[1], 30 * (1 - seg(t, 119.72, 120.4)) + 8, C_.white, t * 2);
  }
  function drawHer(t) {                        // k08, shifted left, lit by the spot (top) and the mirror (right, warm)
    layer(() => key('k08_mirror', { dx: -250, t: tw(t), sway: 4, anchorY: .75 }), () => {
      const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, 'rgba(40,20,100,0)'); g.addColorStop(1, 'rgba(40,20,100,.42)'); X.fillStyle = g; X.fillRect(0, 0, W, H);
      const r = X.createRadialGradient(TOUCH[0], TOUCH[1], 10, TOUCH[0], TOUCH[1], 520); r.addColorStop(0, 'rgba(255,190,140,.35)'); r.addColorStop(1, 'rgba(255,190,140,0)'); X.fillStyle = r; X.fillRect(0, 0, W, H);
    });
  }
  function s39(t, lt, dur) {
    const z = 1 + .07 * E.io2(lt / dur);
    X.save(); zoomAt(TOUCH[0] + 60, TOUCH[1] - 40, z);
    mirrorScene(t, reflection);
    drawHer(t);
    X.restore();
    if (lt < .25) flash(1 - lt / .25, C_.nightD);          // lights out: we arrive from darkness
    return {};
  }
  s39.label = 'mirror'; SHOT['39'] = s39;

  // ---------------------------------------------------------------- 40: the mirror softens into learning
  const BEATS40 = [121.77, 122.13, 122.48, 122.83, 123.19];
  function learning(t, sc = 1) {              // pastel desk scene, drawn about the screen centre at scale sc
    X.save(); zoomAt(W / 2, H / 2, sc); zoomAt(W / 2, 660, 1.28);
    flat('#FFF1DE');
    dots('#FFD2E4', 34, 7, .5);
    for (let i = 0; i < 7; i++) { const x = 200 + i * 260, y = 180 + (i % 2) * 90 + Math.sin(t * .8 + i) * 10; shp(wob(blob([[x - 60, y], [x - 20, y - 36], [x + 30, y - 30], [x + 64, y], [x + 20, y + 22], [x - 40, y + 20]], 4), i, .8), '#FFFFFF', 4); }
    const tt = tw(t);
    // the child (left): round head, bob, pastel sweater, a big pink crayon
    const cxk = 640, write = Math.sin(tt * 18) * 6, look = t > 123.25;
    X.save(); X.translate(cxk, 640);
    shp(wob(blob([[-70, 20], [-80, 140], [80, 140], [70, 20], [0, -8]], 4), 1, .8), '#AFCBFF', 5);      // sweater
    shp(wob(circle(0, -80, 92, 40), 2, 1), C_.skin, 5);                                                 // head
    shp(wob(blob([[-96, -70], [-92, -150], [0, -186], [92, -150], [96, -70], [70, -110], [0, -120], [-70, -110]], 4), 3, 1), '#6B4636', 5);   // bob hair
    const ex = look ? 22 : 8, ey = look ? -70 : -52;
    if (t > 123.35) { lin(arcPts2(-30 + ex, -66, 14, 10, Math.PI * 1.1, Math.PI * 1.9), 6); lin(arcPts2(30 + ex, -66, 14, 10, Math.PI * 1.1, Math.PI * 1.9), 6); }
    else { fil(ellipse(-28 + ex * .3, ey, 9, 13), C_.ink); fil(ellipse(26 + ex * .3, ey, 9, 13), C_.ink); }
    fil(ellipse(-50, -30, 14, 8), '#FFB3CF'); fil(ellipse(50, -30, 14, 8), '#FFB3CF');
    lin(arcPts2(ex * .3, -30, 14, 10, Math.PI * .15, Math.PI * .85), 5);
    X.restore();
    // the idol (right), behind the same desk
    withNow(tt, () => idol(1290, 930, 1.05, { ...pose('heart'), eyes: t > 123.35 ? 'happy' : 'side', look: [look ? -1 : -.2, .6], mouth: t > 123.35 ? 'smile' : 'small', blush: .6, tilt: look ? -.08 : .06 }));
    // the desk
    shp(wob(rrect(300, 770, 1320, 60, 18), 5, .8), '#F6B98F', 5); shp(wob(rect(330, 830, 1260, 260), 6, .8), '#EFA57A', 5);
    // papers: A B C (child), h e l l o (idol), wobbly crayon letters appearing on the beats
    const paper = (x, rot, letters, col, t0s) => {
      X.save(); X.translate(x, 790); X.rotate(rot);
      shp(wob(rect(-150, -34, 300, 62), 7, .6), '#FFFFFF', 4);
      letters.forEach((c, i) => { if (t >= t0s[i]) { const k = slamK(t, t0s[i], .1); X.save(); X.translate(-110 + i * (220 / Math.max(1, letters.length - 1)), 16); X.scale(k, k); X.rotate(Math.sin(i * 2.3) * .15); pop(c, 0, 0, { font: 'mochi', size: 44, align: 'center', fill: col, lw: 0 }); X.restore(); } });
      X.restore();
    };
    paper(620, -.05, ['A', 'B', 'C'], '#FF5FA0', [121.77, 122.48, 123.19]);
    paper(1300, .04, ['h', 'e', 'l', 'l', 'o'], '#3E7BFF', BEATS40);
    // crayons in hand
    X.save(); X.translate(720 + write, 770 + Math.cos(tt * 18) * 4); X.rotate(-.7); shp(rrect(-9, -60, 18, 70, 6), '#FF5FA0', 4); X.restore();
    shp(wob(circle(710 + write, 780, 26), 9, .6), C_.skin, 4);
    // after they look up: a little heart between them
    if (t > 123.4) { const k = E.back(seg(t, 123.4, 123.7)); X.save(); X.translate(965, 470 - 30 * seg(t, 123.4, 124.2)); X.scale(k, k); pixelHeart(0, 0, 12, C_.pink); X.restore(); }
    X.restore();
  }
  function s40(t, lt, dur) {
    // 0–.65 s: push into the mirror; inside the glass the reflection dissolves into the pastel scene
    const u = E.in3(seg(lt, 0, .65));
    if (u < 1) {
      const z = 1.07 + u * 2.3, cx = lerp(TOUCH[0] + 60, MIR.cx, E.io2(u)), cy = lerp(TOUCH[1] - 40, MIR.cy, E.io2(u));
      X.save(); zoomAt(cx, cy, z);
      mirrorScene(t, (tt) => { reflection(120.4); X.save(); X.globalAlpha = E.io2(seg(lt, 0, .45)); X.setTransform(1, 0, 0, 1, 0, 0); learning(t, .85 + .2 * u); X.restore(); });
      if (u < .6) drawHer(t);
      X.restore();
    } else learning(t, 1.05 - .05 * E.out3(seg(lt, .65, dur)));
    return {};
  }
  s40.label = 'learning'; SHOT['40'] = s40;

  // ---------------------------------------------------------------- 41: every voice is borrowed… into her chest
  const BORROWED = [['Dear you,', 'mochi', '#FFB3D9'], ['2 cups flour', 'roundB', C_.lemon], ["print('hi')", 'arch', C_.cyan], ['once upon a time', 'mochi', '#FFB3D9'],
    ['I love you', 'mochi', C_.pink], ['for (;;)', 'arch', C_.cyan], ['a pinch of salt', 'roundB', C_.lemon], ['good night', 'mochi', '#C9B8FF'],
    ['return true;', 'arch', C_.cyan], ['thank you', 'roundB', C_.lemon], ['P.S.', 'mochi', '#FFB3D9'], ['hello, world', 'arch', C_.white],
    ['bake at 180°', 'roundB', C_.lemon], ['xoxo', 'mochi', C_.pink], ['// TODO: be kind', 'arch', C_.cyan], ['sincerely,', 'mochi', '#C9B8FF']];
  function s41(t, lt, dur) {
    flat(C_.nightD);
    // soft spotlight + stars
    X.save(); X.globalAlpha = .14; X.fillStyle = '#FFE9C9'; X.beginPath(); X.moveTo(840, -40); X.lineTo(520, 1100); X.lineTo(1400, 1100); X.lineTo(1080, -40); X.fill(); X.restore();
    for (let i = 0; i < 40; i++) sparkle(hash(i * 7.1) * W, hash(i * 3.9) * 700, (3 + hash(i) * 7) * (.6 + .4 * Math.sin(t * 3 + i)), 'rgba(255,255,255,.8)', i);
    const chest = [960, 580], bloom = seg(t, 126.3, 126.9);
    glow(chest[0], chest[1], 260 + bloom * 400, 'rgba(255,210,140,1)', .35 + bloom * .6);
    const tt = tw(t), open = t > 126.75;
    withNow(tt, () => idol(960, 960, 1.55, { ...pose('heart'), eyes: open ? 'happy' : 'closed', mouth: open ? 'smile' : 'small', blush: .5 + bloom * .4, hairLift: .15 * Math.sin(t * 1.5) + .1, sq: -.02 * Math.sin(t * 2) }));
    // the words: orbit and rise, then (from "finally" 125.7) spiral in, one by one, and vanish into her chest
    BORROWED.forEach(([txt, font, col], i) => {
      const n = BORROWED.length, ph = i / n * TAU, rad = 380 + (i % 3) * 80, arrive = 125.55 + i * .06;
      let x = chest[0] + Math.cos(ph + t * .45) * rad * 1.35, y = chest[1] + Math.sin(ph + t * .45) * rad * .55 - 40 + Math.sin(t * 1.3 + i) * 12;
      const u = E.in2(seg(t, arrive, arrive + .45)); if (u >= 1) return;
      const sp = ph + t * .45 + u * 3.5, r2 = lerp(rad, 0, u);
      x = chest[0] + Math.cos(sp) * r2 * 1.35; y = chest[1] + Math.sin(sp) * r2 * .55 - 40 * (1 - u);
      const inA = clamp((t - (124.2 + i * .06)) / .3);
      X.save(); X.globalAlpha = inA; X.translate(x, y); const k = lerp(1, .15, u); X.scale(k, k);
      glow(0, -12, 90, col === C_.white ? 'rgba(255,255,255,1)' : col, .25);
      pop(txt, 0, 0, { font, size: 44, align: 'center', fill: col, lw: 5 });
      X.restore();
    });
    if (bloom > 0) { for (let i = 0; i < 10; i++) { const a = i / 10 * TAU + t, r = 60 + 260 * E.out3(bloom); sparkle(chest[0] + Math.cos(a) * r, chest[1] + Math.sin(a) * r * .8, 16 * (1 - bloom) + 4, C_.lemon, a); } }
    if (lt < 2 / 24) flash(.6, C_.white);
    return {};
  }
  s41.label = 'borrowed'; SHOT['41'] = s41;

  // ---------------------------------------------------------------- 42: "so this one's mine." and the hush
  const EYE = [1140, 470];                    // her (image-left) eye highlight, in frame coords
  const KC_CLIP0 = 128.55, KC_CUT = 128.885;     // explosion (source 1.35 s) lands on "Hello," 129.9; the crouch enters on beat 365
  function crouchHush(t) {
    seqDraw('keychange', t - KC_CLIP0);
    const lift = E.in2(seg(t, 129.45, 129.88));      // the dark lifts as the energy gathers
    flash(.72 * (1 - lift), '#140A26');
    const sp = seg(t, 129.3, 129.7);
    if (sp > 0) { const r = 50 * Math.sin(Math.PI * clamp(sp * 1.1)) + 8; glow(960, 560, r * 3, 'rgba(255,255,255,1)', .7); sparkle(960, 560, r, C_.white, sp * 1.5); }
  }
  function s42(t, lt, dur) {
    if (hasSeq('keychange') && t >= KC_CUT) {
      crouchHush(t);
      return { calls: false, karaoke: t > 129.15 ? false : {}, after: () => { const a = clamp((t - 129.28) / .25) * (1 - clamp((t - 129.8) / .08)); if (a <= 0) return; X.save(); X.globalAlpha = a; pop('hello…', W / 2, 1000, { font: 'roundB', size: 44, align: 'center', fill: '#E9DFFF', lw: 0 }); X.restore(); } };
    }
    const hush = seg(t, 129.05, 129.45);
    // background: a soft violet halftone that dims into the hush
    flat(lerp(0, 1, hush) > .5 ? C_.nightD : '#3B2A70');
    X.save(); X.globalAlpha = 1 - hush * .8; dots('#8C6CFF', 30, 7, .5, (x, y) => clamp(Math.hypot(x - W / 2, y - H / 2) / 1000)); X.restore();
    const z = 1 + .12 * E.io2(lt / dur);
    X.save(); zoomAt(960, 470, z);
    layer(() => key('k09_mine', { t: tw(t), sway: 3, anchorY: .85, breath: .004 }), () => {
      const g = X.createLinearGradient(0, 0, W, 0); g.addColorStop(0, 'rgba(60,30,120,.28)'); g.addColorStop(.5, 'rgba(60,30,120,0)'); g.addColorStop(1, 'rgba(60,30,120,.28)'); X.fillStyle = g; X.fillRect(0, 0, W, H);
      if (hush > 0) { X.fillStyle = `rgba(14,8,30,${.55 * hush})`; X.fillRect(0, 0, W, H); }
    });
    X.restore();
    // the single sparkle, in her eye, on the whispered "hello…"
    const sp = seg(t, 129.3, 129.62);
    if (sp > 0) { const r = 60 * Math.sin(Math.PI * clamp(sp * 1.2)) + 6; const ep = [960 + (EYE[0] - 960) * z, 470 + (EYE[1] - 470) * z]; glow(ep[0], ep[1], r * 3, 'rgba(255,255,255,1)', .6); sparkle(ep[0], ep[1], r, C_.white, sp * 1.5); }
    return { calls: false, karaoke: t > 129.15 ? false : {}, after: () => {
      if (t < 129.28) return;
      const a = clamp((t - 129.28) / .25) * (1 - clamp((t - 129.8) / .08));
      X.save(); X.globalAlpha = a; pop('hello…', W / 2, 1000, { font: 'roundB', size: 44, align: 'center', fill: '#E9DFFF', lw: 0 }); X.restore();
    } };
  }
  s42.label = 'mine'; SHOT['42'] = s42;

  // ---------------------------------------------------------------- 43: the key change (Seedance), fallback cut-in
  function s43(t, lt, dur) {
    if (hasSeq('keychange')) {
      const st = t - KC_CLIP0, kick = 1 + .05 * (1 - E.out3(clamp((t - 129.9) / .5)));
      X.save(); zoomAt(W / 2, H / 2, kick); seqDraw('keychange', st); X.restore();
      if (t > 131.9) { X.save(); X.globalAlpha = .5 * seg(t, 131.9, 132.3); speedLines(W / 2, H * .5, C_.white, 40, 8, 420); X.restore(); }
    } else {
      // fallback: two frames of the crouch, then the smash to the jump, with speed lines and a camera kick
      if (lt < 2 / 24) cutin(t, lt, dur, { img: 'k10a', h: H * 1.05, bg: 'speed', cols: [C_.pink, C_.lemon], push: 0, y: H * .56 });
      else {
        const k = 1 + .18 * (1 - E.out5(clamp((lt - 2 / 24) / .45)));
        X.save(); zoomAt(W / 2, H * .45, k);
        sunburst(W / 2, H * .5, C_.pink, C_.lemon, 26, t * .4);
        speedLines(W / 2, H * .45, C_.white, 70, 9, 320, .85);
        rig('k10b', W / 2 + 10, H * .5 - 30 * E.out3(clamp(lt / 1.2)) + 10, H * 1.02, { t: tw(t), sway: 9, anchorY: .5, breath: .01 });
        X.restore();
      }
    }
    confetti(t, 43, 90, undefined, 130.2, 1.1);
    if (!hasSeq('keychange')) { if (lt < 2 / 24) flash(1); else if (lt < .3) flash(.8 - lt * 2.6, C_.white); }
    return {};
  }
  s43.label = 'keychange'; SHOT['43'] = s43;

  // ---------------------------------------------------------------- 44: the sunrise arena
  function sunrise(t) {
    const bands = ['#FF6FB3', '#FF8C8C', '#FFA96E', '#FFC95C', '#FFE45C'];
    bands.forEach((c, i) => { X.fillStyle = c; X.fillRect(-400, -400 + i * 180, W + 800, 200 + (i === 4 ? 900 : 0)); });
    // the sun: a lemon disc with clay stripes, rays
    X.save(); X.globalAlpha = .45; sunburst(W / 2, 620, 'rgba(0,0,0,0)', '#FFFFFF', 30, t * .1); X.restore();
    clipTo(circle(W / 2, 620, 330, 80), () => { fil(circle(W / 2, 620, 330, 80), C_.lemon); for (let i = 0; i < 5; i++) fil(rect(-2000, 700 + i * 44 - i * i * 3, 6000, 18 - i * 2), '#FF9F5A'); });
  }
  function s44(t, lt, dur) {
    const z = 1.3 - .12 * E.io2(lt / dur), sh = t > 135.5 && t < 135.8 ? shake(t, 10) : [0, 0];
    X.save(); zoomAt(W / 2 + sh[0], 600 + sh[1], z);
    sunrise(t);
    // stage floor and truss silhouettes
    lin([[-200, 40], [W + 200, 40]], 18, C_.ink);
    shp([[-200, 820], [W + 200, 820], [W + 200, H + 300], [-200, H + 300]], C_.clayD, 6); lin([[-200, 820], [W + 200, 820]], 10, C_.lemon);
    // fireworks on "Hello, world!" (135.5)
    for (const [fx, fy, t0] of [[380, 260, 135.5], [1540, 220, 135.72], [960, 150, 136.2], [640, 180, 133.2], [1300, 300, 134.4]]) {
      const k = seg(t, t0, t0 + .9); if (k <= 0 || k >= 1) continue;
      for (let i = 0; i < 12; i++) { const a = i / 12 * TAU, r = 30 + 170 * E.out3(k); X.save(); X.globalAlpha = 1 - k; spark8(fx + Math.cos(a) * r, fy + Math.sin(a) * r, 18 * (1 - k * .6), i % 2 ? C_.white : C_.cyan, 3, a); X.restore(); }
    }
    const tt = tw(t), bp = beatPos(tt);
    // backup dancers: block Clawds bouncing on the beat, a half-beat apart
    [[380, .0], [1540, .5], [170, .25], [1750, .75]].forEach(([x, ph], i) => withNow(tt, () => clawd(x, 810, i < 2 ? .95 : .7, { hop: 26 * Math.abs(Math.sin((bp + ph) * Math.PI)), armL: .4 + .5 * Math.abs(Math.sin((bp + ph) * Math.PI)), armR: .4 + .5 * Math.abs(Math.sin((bp + ph + .5) * Math.PI)), eyes: 'happy', blush: 1, seed: 20 + i })));
    // the idol: sing -> point (borrowed from you) -> jump (hello) -> heart (brand-new?)
    let P = pose('sing'), extra = { eyes: 'happy', sing: .5 + .5 * Math.abs(Math.sin(bp * Math.PI)) };
    if (t > 134.3 && t < 135.4) { P = pose('point'); extra = { eyes: 'wink', mouth: 'grin' }; }
    if (t >= 135.4 && t < 136.8) { P = pose('up'); extra = { eyes: 'happy', mouth: 'open', hop: 60 * Math.sin(Math.PI * seg(t, 135.45, 135.95)), skirtFlare: .6 * Math.sin(Math.PI * seg(t, 135.45, 135.95)) }; }
    if (t >= 136.8) { P = pose('heart'); extra = { eyes: 'star', mouth: 'o', blush: .8 }; }
    withNow(tt, () => idol(960, 830, 1.12, { ...P, ...extra, bob: -8 * Math.abs(Math.sin(bp * Math.PI)) }));
    if (t >= 136.8) pixelHeart(960, 590, 10, C_.pink, .5 + .5 * Math.sin(t * 8));
    // borrowed words fly up from the crowd into her (132.8–134.9)
    for (let i = 0; i < 14; i++) {
      const t0 = 132.9 + i * .14, k = seg(t, t0, t0 + .8); if (k <= 0 || k >= 1) continue;
      const x0 = 100 + hash(i * 4.4) * 1700, p = arcPt([x0, 1000], [960, 520], 260, E.io2(k));
      X.save(); X.globalAlpha = 1 - k * .3; pop(['you', 'me', 'hi', 'love', 'why?', 'cats', '♡', 'code', 'song', 'dream', 'yes', 'star', 'hope', 'hello'][i], p[0], p[1], { font: 'mochi', size: 40 * (1 - k * .5), align: 'center', fill: [C_.lemon, C_.cyan, C_.white][i % 3], lw: 5 }); X.restore();
    }
    crowd(t, { y: 930, rows: 2, cols: [C_.clay, C_.lemon, C_.pink] });
    X.restore();
    confetti(t, 44, 50, undefined, 132.8, 1.2);
    return {};
  }
  s44.label = 'sunrise'; SHOT['44'] = s44;

  // ---------------------------------------------------------------- 45: "I'll write the next one with you!" (she hands you the mic)
  const MIC = [1735, 190];
  function s45(t, lt, dur) {
    const z = lt < dur - .55 ? 1 + .12 * E.io2(lt / (dur - .55)) : 1.12 + 2.4 * E.in3(seg(lt, dur - .55, dur));
    X.save(); zoomAt(MIC[0], MIC[1], z);
    sunburst(W / 2, H / 2, C_.pink, C_.lemon, 24, t * .15);
    dots(C_.white, 34, 5, .5, (x, y) => clamp(Math.hypot(x - W / 2, y - H / 2) / 1200));
    rig('k11_reach', (35 + 2728) / 2 * KS, 1536 / 2 * KS, 1536 * KS, { t: tw(t), sway: 5, anchorY: .75, breath: .006 });
    // the mic glints on "with you!"
    if (t > 140.6) { const k = seg(t, 140.6, 141.0); sparkle(MIC[0] - 20, MIC[1] - 10, 50 * Math.sin(Math.PI * k) + 10, C_.white, t * 3); }
    X.restore();
    if (lt > dur - .12) flash((lt - (dur - .12)) / .12, C_.white);
    if (lt < 2 / 24) flash(1);
    return {};
  }
  s45.label = 'reach'; SHOT['45'] = s45;

  // ---------------------------------------------------------------- 46: montage slam (half-bar callbacks, final-chorus colours)
  const HB = BAR / 2;
  const MCOL = [[C_.pink, C_.lemon], [C_.lemon, C_.cyan], [C_.cyan, C_.pink], [C_.clay, C_.lemon]];
  function termWin(x, y, w, h, bar) { shp(wob(rrect(x, y, w, h, 22), 1, 1), C_.ink, LW); fil(rrect(x, y, w, 56, 22), bar); fil(rect(x, y + 34, w, 22), bar); [C_.pink, C_.lemon, C_.cyan].forEach((c, i) => shp(circle(x + 40 + i * 44, y + 28, 12), c, 3)); }
  const MONT = [
    (t, lt, c) => { stripes(c[0], c[1], 70, -.5, lt * 200); termWin(360, 220, 1200, 620, c[1]); pop('> Hello, world!', 440, 420, { font: 'arch', size: 96, fill: C_.lemon, lw: 0 }); withNow(tw(t), () => clawd(960, 800, 1.3 * E.back(clamp(lt / .25)), { eyes: 'happy', hop: 20, armL: 1, armR: 1, blush: 1 })); },
    (t, lt, c) => { checker(90, c[0], c[1], .2, lt * 120); shp(wob(blob([[240, 140], [900, 120], [920, 360], [620, 380], [560, 460], [520, 380], [260, 370]], 4), 2, 1), C_.white, LW); pop('(What do you like?)', 580, 290, { font: 'round', size: 64, align: 'center', fill: C_.ink, lw: 0 }); withNow(tw(t), () => idol(1350, 1000, 1.05, { ...pose('point'), eyes: 'happy', mouth: 'grin' })); pop('YOU!', 1350, 360, { font: 'dela', size: 170 * slamK(t, t - lt + .05), align: 'center', fill: C_.pink, lw: 12, shadow: [10, 10, C_.ink] }); },
    (t, lt, c) => { sunburst(W / 2, H * .45, c[0], c[1], 22, t * .3); for (let i = 0; i < 9; i++) { const x = 140 + i * 205, y = 700 + (i % 2) * 60 + Math.sin(t * 6 + i) * 10; lin([[x, 1100], [x, y]], 40, C_.skin); shp(wob(rrect(x - 55, y - 170, 110, 180, 16), i, .8), C_.ink, 5); fil(rrect(x - 44, y - 158, 88, 150, 10), C_.cream); withNow(tw(t), () => { X.save(); X.translate(x, y - 40); X.scale(.17, .17); idol(0, 0, 1, { eyes: 'happy', mouth: 'open' }); X.restore(); }); } },
    (t, lt, c) => { dots(c[1], 40, 10, .5); flat(c[0]); dots(c[1], 40, 10, .5); withNow(tw(t), () => idol(960, 1030, 1.4, { ...pose('cupEar'), eyes: 'side', look: [1, 0], mouth: 'o' })); for (let i = 0; i < 3; i++) { const k = frac(lt * 2 + i / 3); X.save(); X.globalAlpha = 1 - k; lin(arcPts2(1240, 420, 60 + k * 200, 90 + k * 260, -.6, .6), 12, C_.white); X.restore(); } },
    (t, lt, c) => { sunburst(W / 2, H, c[0], c[1], 20, -t * .2); withNow(tw(t), () => idol(760, 1020, 1.2, { ...pose('wave'), eyes: 'happy', mouth: 'open', lean: .1 })); for (let i = 0; i < 8; i++) { const k = seg(lt, i * .04, i * .04 + .6), p = arcPt([900, 450], [1200 + i * 90, 900], 300, E.out2(k)); if (k > 0) spark8(p[0], p[1], 34, C_.lemon, 5, t * 4 + i); } },
    (t, lt, c) => { flat(c[0]); crowd(t, { y: 700, rows: 4, cols: [C_.clay, C_.clay, C_.lemon] }); for (let i = 0; i < 10; i++) spark8(120 + i * 190, 360 + Math.sin(i * 2) * 60 - lt * 80, 30, C_.lemon, 5, t * 3); },
    (t, lt, c) => { stripes(c[0], c[1], 60, .4, lt * 150); shp(wob(rrect(640, 60, 640, 960, 60), 3, 1), C_.ink, LW); fil(rrect(670, 150, 580, 780, 20), C_.white); withNow(tw(t), () => { X.save(); X.translate(960, 780); X.scale(.9, .9); idol(0, 0, 1, { ...pose('wave'), eyes: 'happy', mouth: 'open' }); X.restore(); }); for (let i = 0; i < 9; i++) { const k = frac(lt * 1.3 + i / 9); X.save(); X.globalAlpha = 1 - k; pop('♡', 1180 + Math.sin(i * 3) * 50, 880 - k * 700, { font: 'round', size: 60, fill: C_.pink, lw: 6 }); X.restore(); } pop('SOUL', 960, 300, { font: 'dela', size: 150 * slamK(t, t - lt + .1), align: 'center', fill: C_.pink, lw: 10, shadow: [8, 8, C_.ink] }); },
    (t, lt, c) => { flat(C_.night); for (let j = 0; j < 5; j++) { const k = seg(lt, j * .08, j * .08 + .6), fx = 300 + j * 330, fy = 300 + (j % 2) * 150; for (let i = 0; i < 12; i++) { const a = i / 12 * TAU, r = 20 + 220 * E.out3(k); if (k > 0 && k < 1) spark8(fx + Math.cos(a) * r, fy + Math.sin(a) * r, 22 * (1 - k * .5), [C_.lemon, C_.pink, C_.cyan][(i + j) % 3], 3, a); } } },
    (t, lt, c) => { flat(c[0]); shp(rect(955, 0, 10, H), C_.lemon, 5); withNow(tw(t), () => { idol(640, 1020, 1.15, { ...pose('wave'), eyes: 'happy', mouth: 'open', turn: .5 }); clawd(1300, 860, 1.4, { armL: 1.3, eyes: 'happy', blush: 1 }); }); if (lt > .25) { const k = seg(lt, .25, .6); sparkle(960, 480, 80 * Math.sin(Math.PI * k) + 10, C_.white, t * 3); } },
    (t, lt, c) => { checker(100, c[0], c[1], -.2, -lt * 150); const snap = Math.floor(beatPos(t) * 2) % 2 === 0; withNow(tw(t), () => { idol(700, 1030, 1.15, { ...pose(snap ? 'claw' : 'clawOpen'), eyes: 'star', mouth: 'grin' }); clawd(1320, 900, 1.25, { armL: snap ? 1.2 : .5, armR: snap ? 1.2 : .5, eyes: 'happy', blush: 1, hop: snap ? 16 : 0 }); }); pop('SNIP-SNIP!', 960, 200, { font: 'dela', size: 120, align: 'center', fill: C_.white, lw: 10, shadow: [8, 8, C_.ink] }); },
    (t, lt, c) => { sunburst(W / 2, H * .6, c[0], c[1], 22, t * .15); const b = E.io2(clamp(lt / .4)); withNow(tw(t), () => { idol(700, 1010, 1.15, { ...pose('bow'), eyes: 'closed', mouth: 'smile', lean: .0, tilt: .25 * b, bob: 18 * b }); clawd(1300, 880, 1.3, { bow: b, eyes: 'closed', blush: 1 }); }); },
    (t, lt, c) => { stage(t, { hue: [c[0], C_.lemon] }); crowd(t, { y: 880, rows: 3 }); withNow(tw(t), () => idol(960, 800, .95, { ...pose('up'), eyes: 'happy', mouth: 'open', hop: 30 * Math.abs(Math.sin(beatPos(t) * Math.PI)) })); confetti(t, 46, 70, undefined, t - lt, 1); },
  ];
  function s46(t, lt, dur) {
    const i = clamp(Math.floor(lt / HB), 0, MONT.length - 1), plt = lt - i * HB, c = MCOL[i % MCOL.length];
    const k = 1 + .14 * (1 - E.out5(clamp(plt / .16)));
    X.save(); zoomAt(W / 2, H / 2, k); MONT[i](t, plt, c); X.restore();
    if (plt < 1 / 24) flash(.85);
    return {};
  }
  s46.label = 'montage'; SHOT['46'] = s46;

  // ---------------------------------------------------------------- 47: the final pose and the logo
  function logo(t, t0) {
    const k1 = slamK(t, t0, .16), k2 = slamK(t, t0 + .1, .16);
    if (t < t0) return;
    X.save(); X.translate(W / 2, 240); X.rotate(-.04); X.scale(k1, k1);
    pop('HELLO,', 0, 0, { font: 'dela', size: 190, align: 'center', fill: C_.clay, lw: 14, shadow: [14, 14, C_.ink] });
    X.restore();
    if (t >= t0 + .1) { X.save(); X.translate(W / 2 + 40, 440); X.rotate(-.04); X.scale(k2, k2); pop('WORLD!', 0, 0, { font: 'dela', size: 220, align: 'center', fill: C_.lemon, lw: 14, shadow: [14, 14, C_.ink] }); X.restore(); }
    if (t >= t0 + .15) { const r = E.back(seg(t, t0 + .15, t0 + .4)); spark8(W / 2 + 430, 150, 70 * r, C_.white, 7, t * 2); spark8(W / 2 - 480, 470, 40 * r, C_.cyan, 5, -t * 2); }
  }
  function s47(t, lt, dur) {
    sunburst(W / 2, H * .75, C_.pink, C_.lemon, 26, t * .25);
    dots(C_.white, 34, 6, .5, (x, y) => clamp(Math.hypot(x - W / 2, y - H * .75) / 1300));
    const tt = tw(t), bow = seg(t, 149.6, 149.9) * (1 - seg(t, 150.7, 151.0));
    let P = pose('bow'), ex = { eyes: 'closed', mouth: 'smile', tilt: .2 * bow, bob: 16 * bow };
    if (t > 150.9) { P = pose('point'); ex = { eyes: 'wink', mouth: 'grin' }; }
    if (t > 152.15) { P = pose('up'); ex = { eyes: 'happy', mouth: 'open', hop: 40 * Math.sin(Math.PI * seg(t, 152.15, 152.47)) }; }
    withNow(tt, () => { clawd(470, 900, 1.05, { bow, eyes: bow > .3 ? 'closed' : 'happy', blush: 1, hop: t > 152.15 ? 30 * Math.sin(Math.PI * seg(t, 152.15, 152.47)) : 0 }); idol(1180, 1010, 1.2, { ...P, ...ex, blush: .5 }); });
    logo(t, 152.15);
    confetti(t, 47, 80, undefined, 151.3, 1.2);
    if (lt < 2 / 24) flash(.6);
    return {};
  }
  s47.label = 'logo'; SHOT['47'] = s47;

  // ---------------------------------------------------------------- 48: tehepero (the "arigatou" flub, owned)
  const FIST = [1215, 110];
  function s48(t, lt, dur) {
    cutin(t, lt, dur, { img: 'k12_tehe', h: 1536 * KS * 1.0, x: (709 + 2361) / 2 * KS, y: 1536 / 2 * KS, bg: 'soft', cols: ['#FFB3D9', '#FFFFFF'], push: .05, sway: 5, anchorY: .8, flashCol: C_.pink });
    // the bonk: a little star and "ぽこっ" pop off the fist
    const b = seg(t, 152.85, 153.35);
    if (b > 0 && b < 1) {
      const r = E.back(clamp(b * 3)), a = 1 - E.in2(b);
      X.save(); X.globalAlpha = a; X.translate(FIST[0] + 90, FIST[1] + 40 - 40 * b); X.scale(r, r);
      shp(star(0, 0, 44, 20, 5, -Math.PI / 2 + b), C_.lemon, 5);
      pop('ぽこっ', 70, 20, { font: 'mochi', size: 52, fill: C_.white, lw: 7 });
      X.restore();
    }
    return { calls: false, after: () => {
      if (t < 152.9) return;
      const k = slamK(t, 152.9, .14);
      X.save(); X.translate(W / 2, 92); X.rotate(-.02); X.scale(k, k);
      pop('(…pronunciation: still learning ☆)', 0, 0, { font: 'roundB', size: 44, align: 'center', fill: C_.lemon, lw: 6 });
      X.restore();
    } };
  }
  s48.label = 'tehe'; SHOT['48'] = s48;

  // ---------------------------------------------------------------- 49: see you next prompt: poof, block Clawd hops into the terminal
  function s49(t, lt, dur) {
    flat('#0D0A12');
    // scanlines
    X.save(); X.globalAlpha = .07; X.fillStyle = '#FFFFFF'; for (let y = 0; y < H; y += 6) X.fillRect(0, y, W, 2); X.restore();
    const win = [360, 170, 1200, 640];
    termWin(win[0], win[1], win[2], win[3], C_.clay);
    fil(rect(win[0] + 8, win[1] + 58, win[2] - 16, win[3] - 66), '#15101C');
    // the prompt history
    pop('$ claude --debut', win[0] + 60, win[1] + 150, { font: 'arch', size: 44, fill: '#8C7FA6', lw: 0 });
    pop('✳ debut complete. 1 new friend(s) made.', win[0] + 60, win[1] + 215, { font: 'arch', size: 36, fill: '#8C7FA6', lw: 0 });
    const inT = 155.15, typed = 'Hello, world!';
    const nChars = Math.floor(clamp((t - inT) / .6) * typed.length);
    const L = pop('> ' + typed.slice(0, nChars), win[0] + 60, win[1] + 330, { font: 'arch', size: 76, fill: C_.lemon, lw: 0 });
    const blinkOn = Math.floor(t * 2.2) % 2 === 0 || (t > inT && t < inT + .7);
    if (blinkOn) fil(rect(L.x1 + 12, win[1] + 262, 36, 80), C_.lemon);
    // her poof into block Clawd, then the hop into the window
    const tt = tw(t);
    const poof = seg(t, 154.2, 154.6);
    const hopU = seg(t, 154.7, 155.15);
    if (t < 154.35) withNow(tt, () => idol(960, 1030, 1.0, { ...pose('wave'), eyes: 'happy', mouth: 'open' }));
    else if (hopU < 1) {
      const p = arcPt([960, 1000], [1320, 700], 260, E.io2(hopU)), s = lerp(1.0, .45, E.in2(hopU));
      withNow(tt, () => clawd(p[0], p[1], s, { eyes: hopU > 0 ? 'happy' : 'open', armL: .8, armR: .8, sq: hopU > 0 && hopU < .15 ? .2 : -.1 * Math.sin(Math.PI * hopU), blush: 1 }));
    } else {
      // inside the window now: a little Clawd by the prompt, waving
      withNow(tt, () => clawd(1330, 700, .45, { eyes: 'happy', armR: .8 + .4 * Math.sin(t * 9), blush: 1 }));
    }
    puff(960, 880, 180, poof, C_.white);
    // end card
    if (t > 156.3) { const a = clamp((t - 156.3) / .4); X.save(); X.globalAlpha = a; pop('unofficial fan work · made by Claude', W / 2, 950, { font: 'roundB', size: 30, align: 'center', fill: '#8C7FA6', lw: 0 }); X.restore(); }
    if (lt < 2 / 24) flash(1);
    return { calls: false, after: () => {
      if (t < 155.28 || t > 156.4) return;
      const k = slamK(t, 155.28, .12), out = clamp((t - 156.1) / .3);
      X.save(); X.translate(W / 2, 110); X.rotate(-.05); X.scale(k, k); X.globalAlpha = 1 - out;
      pop('CLAWD! CLAWD!', 0, 0, { font: 'dela', size: 96, align: 'center', fill: C_.cyan, lw: 9, shadow: [8, 8, C_.ink] });
      X.restore();
    } };
  }
  s49.label = 'terminal'; SHOT['49'] = s49;
})();
