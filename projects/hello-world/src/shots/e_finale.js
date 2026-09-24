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


  // ---------------------------------------------------------------- the kid (40): Neko-Arc SD human, seated; (x, y) = the desk line
  const KH = '#6B4636', KHD = '#4E3226', KSW = '#AFCBFF', KSWD = '#8AAEF0';
  function kid(x, y, s, o = {}) {
    const t = NOW, hy = -222, lk = o.look || [0, 0];
    X.save(); X.translate(x, y); X.scale(s, s);
    // back hair: a soft bob to the chin
    X.save(); X.translate(0, hy); X.rotate(o.tilt || 0);
    sh2(wob(blob([[-104, -30], [-116, 40], [-104, 104], [-70, 84], [0, 96], [70, 84], [104, 104], [116, 40], [104, -30], [0, -120]], 5), 81, .6), KHD);
    X.restore();
    // torso: a pastel sweater with a round white collar (the desk hides the rest)
    sh2(wob(blob([[-66, -122], [66, -122], [96, 20], [-96, 20]], 2), 82, .5), KSW);
    sh2(wob(blob([[-40, -124], [0, -92], [40, -124], [22, -130], [0, -110], [-22, -130]], 3), 83, .4), C_.white);
    // far arm resting on the desk
    lin([[-60, -96], [-96, -30], [-70, 0]], 24, LN); lin([[-60, -96], [-96, -30], [-70, 0]], 24 - LNW, KSW);
    sh2(wob(circle(-66, -2, 24, 22), 84, .4), C_.skin);
    // head
    X.save(); X.translate(0, hy); X.rotate(o.tilt || 0);
    const face = wob(blob([[-86, -24], [-76, -78], [0, -98], [76, -78], [86, -24], [80, 34], [46, 78], [0, 88], [-46, 78], [-80, 34]], 5), 85, .6);
    sh2(face, C_.skin);
    // fringe: pointed bob locks
    const fr = [[-116, -20], [-110, -86], [-60, -132], [16, -140], [90, -120], [118, -66], [116, -16], [94, -46], [80, -8], [60, -60], [40, -12], [20, -66], [0, -18], [-22, -68], [-42, -14], [-62, -64], [-82, -10], [-98, -50]];
    sh2(wob(fr, 86, .6), KH);
    for (const side of [-1, 1]) sh2(wob(blob([[side * 78, -70], [side * 116, -10], [side * 108, 60], [side * 92, 90], [side * 84, 30]], 4), 87 + side, .5), KH);
    X.save(); X.lineCap = 'round'; X.strokeStyle = 'rgba(255,230,210,.4)'; X.lineWidth = 10; X.beginPath(); X.arc(0, -30, 100, Math.PI * 1.18, Math.PI * 1.62); X.stroke(); X.restore();
    // a pink hair bow
    X.save(); X.translate(-78, -104); X.rotate(-.35);
    sh2(blob([[0, 0], [-34, -20], [-36, 16]], 3), C_.pink); sh2(blob([[0, 0], [34, -20], [36, 16]], 3), C_.pink); sh2(circle(0, 0, 9, 14), C_.pinkD);
    X.restore();
    // eyes: big calm white ovals, round dark pupils (human)
    for (const side of [-1, 1]) {
      const cx = side * 38, cy = 6;
      if (o.eyes === 'happy') { lin(arcPts2(cx, cy + 12, 24, 20, Math.PI * 1.12, Math.PI * 1.88), 4.5, LN); continue; }
      const ep = ellipse(cx, cy, 32, 27, side * -.05);
      sh2(ep, C_.white, 4);
      clipTo(ep, () => { const px = cx + lk[0] * 12, py = cy + lk[1] * 9; fil(circle(px, py, 13, 20), '#3A2A30'); fil(circle(px + 5, py - 5, 4, 10), C_.white); });
    }
    const bl = o.blush ?? .5; X.globalAlpha = bl; for (const side of [-1, 1]) fil(ellipse(side * 56, 44, 15, 8), C_.pink); X.globalAlpha = 1;
    if (o.mouth === 'o') sh2(ellipse(2, 56, 6, 8), C_.pinkD, 3); else lin(arcPts2(0, 48, 11, 7, Math.PI * .2, Math.PI * .8), 3.5, LN);
    X.restore();
    X.restore();
  }
  // the writing arm + mitten + crayon, drawn after the desk and paper (hand in desk-line coords)
  function kidHand(x, y, s, hand) {
    X.save(); X.translate(x, y); X.scale(s, s);
    const S = [60, -96], Ep = [96, -46], Wr = hand;
    lin([S, Ep, Wr], 24, LN); lin([S, Ep, Wr], 24 - LNW, KSW);
    X.save(); X.translate(Wr[0] + 10, Wr[1] - 6); X.rotate(-.7); sh2(rrect(-9, -62, 18, 70, 6), '#FF5FA0', 3.5); fil(rect(-9, -40, 18, 10), '#FFFFFF'); X.restore();
    sh2(wob(circle(Wr[0], Wr[1], 26, 22), 88, .4), C_.skin);
    X.restore();
  }

  // ---------------------------------------------------------------- 40: the mirror softens into learning
  const BEATS40 = [121.77, 122.13, 122.48, 122.83, 123.19];
  function learning(t, sc = 1) {              // pastel desk scene, drawn about the screen centre at scale sc
    X.save(); zoomAt(W / 2, H / 2, sc); zoomAt(W / 2, 660, 1.28);
    flat('#FFF1DE');
    dots('#FFD2E4', 34, 7, .5);
    for (let i = 0; i < 7; i++) { const x = 200 + i * 260, y = 180 + (i % 2) * 90 + Math.sin(t * .8 + i) * 10; shp(wob(blob([[x - 60, y], [x - 20, y - 36], [x + 30, y - 30], [x + 64, y], [x + 20, y + 22], [x - 40, y + 20]], 4), i, .8), '#FFFFFF', 4); }
    const tt = tw(t);
    // the child (left): a small human kid in the same SD language as the idol, drawing with a crayon
    const cxk = 640, write = Math.sin(tt * 18) * 6, look = t > 123.25, smile = t > 123.35;
    kid(cxk, 780, 1, { look: look ? [1, -.3] : [.2, .7], eyes: smile ? 'happy' : 'open', mouth: smile ? 'smile' : 'o', hand: [100 + write, -18 + Math.cos(tt * 18) * 4], tilt: look ? .06 : -.05, blush: look ? .9 : .5 });
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
    kidHand(cxk, 780, 1, [100 + write, -18 + Math.cos(tt * 18) * 4]);     // her writing hand, over the paper
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
  const KC_CLIP0 = 128.49, KC_CUT = 128.885;     // explosion (source 1.35 s) lands on "Hello," 129.9; the crouch enters on beat 365
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
    const dance = (ph) => (tq) => { const b = beatPos(tq) + ph, up = Math.abs(Math.sin(b * Math.PI)); return { hop: 26 * up, pincer: true, snip: frac(b) < .5 ? 1 : 0, armL: .5 + .7 * up, armR: .5 + .7 * Math.abs(Math.sin((b + .5) * Math.PI)), eyes: 'happy', mouth: 'cat', blush: 1 }; };
    withNow(tt, () => {
      troupe(tt, [150, 1770], 815, .66, (tq, i) => dance(.25 + i * .5)(tq), { hats: ['party', 'tophat'], lag: 0 });
      troupe(tt, [390, 1530], 812, .9, (tq, i) => ({ ...dance(i * .5)(tq), holdR: i ? 'fan' : 'penlight', penCol: C_.pink }), { hats: ['headband', 'crown'], lag: 0 });
    });
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
    (t, lt, c) => { stripes(c[0], c[1], 70, -.5, lt * 200); termWin(360, 160, 1200, 560, c[1]); pop('> Hello, world!', 440, 360, { font: 'arch', size: 96, fill: C_.lemon, lw: 0 }); withNow(tw(t), () => { [300, 600, 1320, 1620].forEach((x, i) => { const k = E.back(clamp((lt - .06 - i * .05) / .2)); if (k > 0) clawd(x, 1000, .72 * k, { hat: ['bow', 'crown', 'cap', 'party'][i], eyes: 'happy', hop: 30 * Math.abs(Math.sin((lt * 3 + i * .3) * Math.PI)), pincer: true, snip: i % 2, armL: 1, armR: 1, blush: 1, seed: 40 + i }); }); clawd(960, 820, 1.3 * E.back(clamp(lt / .25)), { eyes: 'happy', hop: 20, armL: 1, armR: 1, blush: 1 }); }); },
    (t, lt, c) => { checker(90, c[0], c[1], .2, lt * 120); shp(wob(blob([[240, 140], [900, 120], [920, 360], [620, 380], [560, 460], [520, 380], [260, 370]], 4), 2, 1), C_.white, LW); pop('(What do you like?)', 580, 290, { font: 'round', size: 64, align: 'center', fill: C_.ink, lw: 0 }); withNow(tw(t), () => idol(1350, 1000, 1.05, { ...pose('point'), eyes: 'happy', mouth: 'grin' })); pop('YOU!', 1350, 360, { font: 'dela', size: 170 * slamK(t, t - lt + .05), align: 'center', fill: C_.pink, lw: 12, shadow: [10, 10, C_.ink] }); },
    (t, lt, c) => { sunburst(W / 2, H * .45, c[0], c[1], 22, t * .3); for (let i = 0; i < 9; i++) { const x = 140 + i * 205, y = 700 + (i % 2) * 60 + Math.sin(t * 6 + i) * 10; lin([[x, 1100], [x, y]], 40, C_.skin); shp(wob(rrect(x - 55, y - 170, 110, 180, 16), i, .8), C_.ink, 5); fil(rrect(x - 44, y - 158, 88, 150, 10), C_.cream); withNow(tw(t), () => { X.save(); X.translate(x, y - 40); X.scale(.17, .17); idol(0, 0, 1, { eyes: 'happy', mouth: 'open' }); X.restore(); }); } },
    (t, lt, c) => { dots(c[1], 40, 10, .5); flat(c[0]); dots(c[1], 40, 10, .5); withNow(tw(t), () => idol(960, 1030, 1.4, { ...pose('cupEar'), eyes: 'side', look: [1, 0], mouth: 'o' })); for (let i = 0; i < 3; i++) { const k = frac(lt * 2 + i / 3); X.save(); X.globalAlpha = 1 - k; lin(arcPts2(1240, 420, 60 + k * 200, 90 + k * 260, -.6, .6), 12, C_.white); X.restore(); } },
    (t, lt, c) => { sunburst(W / 2, H, c[0], c[1], 20, -t * .2); withNow(tw(t), () => idol(760, 1020, 1.2, { ...pose('wave'), eyes: 'happy', mouth: 'open', lean: .1 })); for (let i = 0; i < 8; i++) { const k = seg(lt, i * .04, i * .04 + .6), p = arcPt([900, 450], [1200 + i * 90, 900], 300, E.out2(k)); if (k > 0) spark8(p[0], p[1], 34, C_.lemon, 5, t * 4 + i); } },
    (t, lt, c) => { flat(c[0]); crowd(t, { y: 700, rows: 4, cols: [C_.clay, C_.clay, C_.lemon] }); for (let i = 0; i < 10; i++) spark8(120 + i * 190, 360 + Math.sin(i * 2) * 60 - lt * 80, 30, C_.lemon, 5, t * 3); withNow(tw(t), () => troupe(t, [240, 720, 1200, 1680], 1110, .8, (tq, i) => ({ hop: 18 * Math.abs(Math.sin((beatPos(tq) + i * .25) * Math.PI)), armR: 1.3, holdR: 'penlight', penCol: [C_.pink, C_.cyan, C_.lemon, C_.pink][i], eyes: 'star', blush: 1 }), { hats: ['headband', 'bow', 'headband', 'cap'] })); },
    (t, lt, c) => { stripes(c[0], c[1], 60, .4, lt * 150); shp(wob(rrect(640, 60, 640, 960, 60), 3, 1), C_.ink, LW); fil(rrect(670, 150, 580, 780, 20), C_.white); withNow(tw(t), () => { X.save(); X.translate(960, 780); X.scale(.9, .9); idol(0, 0, 1, { ...pose('wave'), eyes: 'happy', mouth: 'open' }); X.restore(); }); for (let i = 0; i < 9; i++) { const k = frac(lt * 1.3 + i / 9); X.save(); X.globalAlpha = 1 - k; pop('♡', 1180 + Math.sin(i * 3) * 50, 880 - k * 700, { font: 'round', size: 60, fill: C_.pink, lw: 6 }); X.restore(); } pop('SOUL', 960, 300, { font: 'dela', size: 150 * slamK(t, t - lt + .1), align: 'center', fill: C_.pink, lw: 10, shadow: [8, 8, C_.ink] }); },
    (t, lt, c) => { flat(C_.night); dots('#3E2C6E', 36, 5, .5); for (let j = 0; j < 8; j++) { const k = seg(lt, j * .06, j * .06 + .6), fx = 180 + j * 225, fy = 220 + (j % 3) * 120; if (k > 0 && k < 1) { glow(fx, fy, 260 * E.out3(k), [C_.lemon, C_.pink, C_.cyan][j % 3], .35 * (1 - k)); for (let i = 0; i < 14; i++) { const a = i / 14 * TAU, r = 20 + 240 * E.out3(k); spark8(fx + Math.cos(a) * r, fy + Math.sin(a) * r, 24 * (1 - k * .5), [C_.lemon, C_.pink, C_.cyan][(i + j) % 3], 3, a); } } }
      withNow(tw(t), () => troupe(t, [180, 440, 700, 1220, 1480, 1740], 1070, .75, (tq, i) => ({ armR: 1.35, holdR: 'penlight', penCol: [C_.cyan, C_.pink, C_.lemon][i % 3], eyes: 'star', blush: 1, hop: 10 * Math.abs(Math.sin((beatPos(tq) + i * .2) * Math.PI)) }), { hats: ['party', 'crown', 'bow', 'cap', 'headband', 'beret'] }));
      withNow(tw(t), () => idol(960, 1040, 1.0, { ...pose('up'), eyes: 'star', mouth: 'open', turn: -.2 }));
    },
    (t, lt, c) => {                                     // the mirror high-five: her palm, its pincer, one sparkle burst
      sunburst(1180, 520, c[0], c[1], 22, t * .3);
      const glassP = ellipse(1260, 540, 330, 430, 0, 80);
      shp(ellipse(1260, 540, 356, 456, 0, 80), C_.lemon, LW); clipTo(glassP, () => { flat('#BFF4FF'); for (let i = 0; i < 3; i++) fil([[1000 + i * 150, 60], [1060 + i * 150, 60], [880 + i * 150, 1040], [820 + i * 150, 1040]], 'rgba(255,255,255,.5)'); });
      const touch = E.back(clamp((lt - .04) / .18));
      withNow(tw(t), () => {
        clipTo(glassP, () => clawd(1330, 860, 1.25, { armL: lerp(.2, 1.1, touch), pincer: true, snip: lt > .3 ? 1 : 0, eyes: lt > .3 ? 'happy' : 'wide', blush: 1, hat: 'bow' }));
        idol(560, 1030, 1.2, { armL: [.2, -.1], armR: [lerp(.3, 1.45, touch), .1], handL: 'mitt', handR: 'open', eyes: lt > .3 ? 'happy' : 'open', mouth: lt > .3 ? 'open' : 'o', turn: .5, look: [1, 0], blush: .7 });
      });
      if (lt > .22) { const k = seg(lt, .22, .7), p = [950, 690]; for (let i = 0; i < 10; i++) { const a = i / 10 * TAU; sparkle(p[0] + Math.cos(a) * 220 * E.out3(k), p[1] + Math.sin(a) * 220 * E.out3(k), 26 * (1 - k), C_.white, a); } sparkle(p[0], p[1], 90 * Math.sin(Math.PI * k) + 12, C_.white, t * 3); X.save(); X.globalAlpha = 1 - k; X.strokeStyle = C_.white; X.lineWidth = 10; X.beginPath(); X.arc(p[0], p[1], 40 + 260 * E.out3(k), 0, TAU); X.stroke(); X.restore(); }
      if (lt > .26) pop('HI-5!', 950, 300, { font: 'dela', size: 150 * slamK(t, t - lt + .26), align: 'center', fill: C_.white, lw: 11, shadow: [9, 9, C_.ink] });
    },
    (t, lt, c) => { checker(100, c[0], c[1], -.2, -lt * 150); const snap = Math.floor(beatPos(t) * 2) % 2 === 0; withNow(tw(t), () => { troupe(t, [140, 400, 1520, 1780], 700, .55, (tq, i) => { const sn = Math.floor(beatPos(tq) * 2) % 2 === 0; return { pincer: true, snip: sn ? 0 : 1, armL: sn ? 1.3 : .6, armR: sn ? 1.3 : .6, hop: sn ? 14 : 0, eyes: 'happy', blush: 1 }; }, { hats: ['beret', 'cap', 'crown', 'hardhat'], lag: .08 }); idol(700, 1030, 1.15, { ...pose(snap ? 'claw' : 'clawOpen'), eyes: 'star', mouth: 'grin' }); clawd(1320, 900, 1.25, { pincer: true, snip: snap ? 0 : 1, armL: snap ? 1.2 : .5, armR: snap ? 1.2 : .5, eyes: 'happy', blush: 1, hop: snap ? 16 : 0 }); }); pop('SNIP-SNIP!', 960, 200, { font: 'dela', size: 120, align: 'center', fill: C_.white, lw: 10, shadow: [8, 8, C_.ink] }); },
    (t, lt, c) => { sunburst(W / 2, H * .6, c[0], c[1], 22, t * .15); const b = E.io2(clamp(lt / .4)); withNow(tw(t), () => { troupe(t, [120, 330, 1590, 1800], 760, .55, (tq, i) => ({ bow: E.io2(clamp((lt - .05 - i * .05) / .35)), eyes: 'closed', blush: 1 }), { hats: ['tophat', 'bow', 'party', 'halo'], lag: 0 }); idol(700, 1010, 1.15, { ...pose('bow'), eyes: 'closed', mouth: 'smile', lean: .0, tilt: .25 * b, bob: 18 * b }); clawd(1300, 880, 1.3, { bow: b, eyes: 'closed', blush: 1 }); }); },
    (t, lt, c) => { stage(t, { hue: [c[0], C_.lemon] }); withNow(tw(t), () => troupe(t, [300, 560, 1360, 1620], 800, .6, (tq, i) => ({ hop: 24 * Math.abs(Math.sin((beatPos(tq) + i * .25) * Math.PI)), pincer: true, snip: frac(beatPos(tq)) < .5 ? 1 : 0, armL: 1.2, armR: 1.2, eyes: 'happy', blush: 1 }), { hats: ['crown', 'headband', 'bow', 'party'], lag: .06 })); crowd(t, { y: 880, rows: 3 }); withNow(tw(t), () => idol(960, 800, .95, { ...pose('up'), eyes: 'happy', mouth: 'open', hop: 30 * Math.abs(Math.sin(beatPos(t) * Math.PI)) })); confetti(t, 46, 70, undefined, t - lt, 1); },
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
    withNow(tt, () => {
      // the curtain-call line: every costume, bowing in a ripple outward from the centre, then all hop up with pincers on "(FOR YOU!)"
      const hats = ['tophat', 'party', 'bow', 'crown', 'headband', 'cap', 'beret', 'hardhat'], xs = [150, 350, 550, 750, 1170, 1370, 1570, 1770];
      xs.forEach((x, i) => {
        const d = Math.abs(x - 960) / 820, b = seg(t, 149.6 + d * .35, 149.9 + d * .35) * (1 - seg(t, 150.7 + d * .2, 151.0 + d * .2)), up = t > 152.15 ? Math.sin(Math.PI * seg(t, 152.15 + d * .06, 152.47 + d * .06)) : 0;
        clawd(x, 800, .58, { hat: hats[i], seed: 60 + i, bow: b, eyes: b > .3 ? 'closed' : 'happy', blush: 1, hop: 36 * up, pincer: t > 152.1, snip: up > .3 ? 1 : 0, armL: t > 152.1 ? 1.3 : .3, armR: t > 152.1 ? 1.3 : .3, holdR: i === 2 ? { sign: 'FOR YOU!', size: 34 } : null, bowtie: i === 0 });
      });
      clawd(470, 900, 1.05, { bow, eyes: bow > .3 ? 'closed' : 'happy', blush: 1, hop: t > 152.15 ? 30 * Math.sin(Math.PI * seg(t, 152.15, 152.47)) : 0 }); idol(1180, 1010, 1.2, { ...P, ...ex, blush: .5 });
    });
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

  // ---------------------------------------------------------------- 49: see you next prompt — poof, hop into the terminal, hello_world() spawns the troupe
  // 154.2 wave ("see you next prompt") · 154.55 poof · 154.62–154.85 hop in · 154.86 types hello_world() · 155.03+ each output line pops out a costumed Clawd
  // · beats 440/441 (155.34, 155.69): everyone snaps together · 156.0 "> Hello, world!▌" · 156.7 end card · cursor blinks to the end
  const T49 = { poof: 154.55, hop0: 154.62, hop1: 154.85, type0: 154.86, type1: 155.02, pop0: 155.03, popDt: .022, popDur: .17, snap1: beatT(440), snap2: beatT(441), fin0: 156.0, card: 156.7 };
  const OUT = [['bow', 'hello, bow!'], ['crown', 'hello, crown!'], ['headband', 'hello, headband!'], ['cap', 'hello, cap!'], ['party', 'hello, party!'], ['beret', 'hello, beret!'], ['hardhat', 'hello, hardhat!'], ['tophat', 'hello, top hat!']];
  const ROWX = [150, 375, 600, 825, 1095, 1320, 1545, 1770], ROWY = 900;
  function s49(t, lt, dur) {
    flat('#0D0A12');
    X.save(); X.globalAlpha = .07; X.fillStyle = '#FFFFFF'; for (let y = 0; y < H; y += 6) X.fillRect(0, y, W, 2); X.restore();
    const win = [440, 50, 1040, 560];
    const pulse1 = t > T49.snap1 ? Math.exp(-(t - T49.snap1) * 8) : 0, pulse2 = t > T49.snap2 ? Math.exp(-(t - T49.snap2) * 8) : 0;
    X.save(); zoomAt(W / 2, H / 2, 1 + .02 * (pulse1 + pulse2));
    termWin(win[0], win[1], win[2], win[3], C_.clay);
    fil(rect(win[0] + 8, win[1] + 58, win[2] - 16, win[3] - 66), '#15101C');
    const mono = (txt, x, y, size, fill) => pop(txt, x, y, { font: 'arch', size, fill, lw: 0 });
    mono('$ claude --debut', win[0] + 50, win[1] + 120, 34, '#8C7FA6');
    mono('* debut complete. 1 new friend(s) made.', win[0] + 50, win[1] + 168, 28, '#8C7FA6');
    // the command
    const cmd = '>>> hello_world()', nC = Math.floor(clamp((t - T49.type0) / (T49.type1 - T49.type0)) * cmd.length);
    const Lc = t > T49.type0 - .05 ? mono(cmd.slice(0, nC), win[0] + 50, win[1] + 236, 40, C_.cyan) : null;
    // output lines, one per Clawd
    OUT.forEach(([hat, line], i) => { const ti = T49.pop0 + i * T49.popDt; if (t >= ti) mono(line, win[0] + 70 + (i % 2) * 460, win[1] + 290 + Math.floor(i / 2) * 44, 30, [C_.lemon, C_.pink, C_.cyan, '#C9B8FF'][i % 4]); });
    // the final line + the cursor
    const fin = 'Hello, world!', nF = Math.floor(clamp((t - T49.fin0) / .55) * fin.length);
    const Lf = mono('> ' + (t >= T49.fin0 ? fin.slice(0, nF) : ''), win[0] + 50, win[1] + 500, 56, C_.lemon);
    const typing = (t > T49.type0 && t < T49.type1) || (t > T49.fin0 && t < T49.fin0 + .6);
    const cur = t < T49.fin0 ? (Lc ? [Lc.x1 + 8, win[1] + 204, 22, 42] : null) : [Lf.x1 + 10, win[1] + 454, 30, 60];
    if (cur && (typing || Math.floor(t * 2.2) % 2 === 0)) fil(rect(...cur), t < T49.fin0 ? C_.cyan : C_.lemon);
    X.restore();
    const tt = tw(t);
    // her wave, the poof, and block Clawd's hop into the terminal (it sits by the command line)
    if (t < T49.poof + .05) withNow(tt, () => idol(960, 1030, 1.0, { ...pose('wave'), eyes: 'happy', mouth: 'open' }));
    const hopU = seg(t, T49.hop0, T49.hop1);
    if (t >= T49.poof + .05) {
      if (hopU < 1) { const p = arcPt([960, 980], [1380, win[1] + 250], 240, E.io2(hopU)), sc = lerp(1.0, .4, E.in2(hopU)); withNow(tt, () => clawd(p[0], p[1], sc, { eyes: 'happy', armL: .8, armR: .8, sq: hopU > 0 && hopU < .15 ? .2 : -.1 * Math.sin(Math.PI * hopU), blush: 1 })); }
      else { const land = spring(t, T49.hop1, 4, .3); withNow(tt, () => clawd(1380, win[1] + 250, .4, { eyes: t > T49.type1 ? 'star' : 'happy', sq: .25 * (1 - land), armR: t < T49.type1 ? .3 + .6 * Math.abs(Math.sin(t * 30)) : .9 + .3 * Math.sin(t * 9), armL: .4, blush: 1 })); }
    }
    puff(960, 880, 180, seg(t, T49.poof, T49.poof + .35), C_.white);
    // the troupe: each pops out of its output line on an arc and lands in a row; then two snaps together on the beats
    OUT.forEach(([hat, line], i) => {
      const ti = T49.pop0 + i * T49.popDt, u = seg(t, ti, ti + T49.popDur); if (u <= 0) return;
      const src = [win[0] + 140 + (i % 2) * 460, win[1] + 280 + Math.floor(i / 2) * 44], dst = [ROWX[i], ROWY];
      const p = arcPt(src, dst, 220 + (i % 3) * 60, E.out2(u)), sc = lerp(.15, .66, E.out3(u));
      const land = u >= 1 ? spring(t, ti + T49.popDur, 4, .3) : 0, sq = u >= 1 ? .3 * (1 - land) : -.15;
      const s1 = t > T49.snap1 ? Math.exp(-(t - T49.snap1) * 5) : 0, s2 = t > T49.snap2 ? Math.exp(-(t - T49.snap2) * 5) : 0, snapK = Math.max(s1, s2);
      const armUp = t > T49.snap1 - .12, open = (t > T49.snap1 - .12 && t < T49.snap1) || (t > T49.snap2 - .12 && t < T49.snap2);
      const bob = t > T49.snap2 + .4 ? 14 * Math.abs(Math.sin((beatPos(tt) + i * .12) * Math.PI)) : 0;
      withNow(tt, () => clawd(p[0], p[1], sc, { hat, seed: 90 + i, sq: sq + .15 * snapK, hop: 40 * snapK + bob, pincer: true, snip: open ? 1 : 0, armL: armUp ? 1.35 : .5, armR: armUp ? 1.35 : .5, eyes: snapK > .2 ? 'star' : (u < 1 ? 'wide' : 'happy'), blush: 1, mouth: 'cat', bowtie: hat === 'tophat', holdR: hat === 'party' ? 'penlight' : null, penCol: C_.pink }));
      if (u > 0 && u < .35) sparkle(src[0] + 120, src[1] - 10, 30 * (1 - u / .35), C_.white, i);
    });
    // snap sparks
    for (const ts of [T49.snap1, T49.snap2]) { const k = seg(t, ts, ts + .4); if (k > 0 && k < 1) ROWX.forEach((x, i) => { spark8(x - 80, ROWY - 190 - 50 * k, 18 * (1 - k), C_.lemon, 3, t * 3 + i); spark8(x + 80, ROWY - 190 - 50 * k, 18 * (1 - k), C_.lemon, 3, -t * 3 + i); }); }
    // end card
    if (t > T49.card) { const a = clamp((t - T49.card) / .4); X.save(); X.globalAlpha = a; pop('unofficial fan work · made by Claude', W / 2, 1050, { font: 'roundB', size: 30, align: 'center', fill: '#8C7FA6', lw: 0 }); X.restore(); }
    if (lt < 2 / 24) flash(1);
    return { calls: false, karaoke: t < 156.3 ? { y: 1040, size: 48 } : false, after: () => {
      if (t < 155.28 || t > 156.5) return;
      const k = slamK(t, 155.28, .12), out = clamp((t - 156.2) / .3);
      X.save(); X.translate(W / 2, 700); X.rotate(-.05); X.scale(k, k); X.globalAlpha = 1 - out;
      pop('CLAWD! CLAWD!', 0, 0, { font: 'dela', size: 96, align: 'center', fill: C_.cyan, lw: 9, shadow: [8, 8, C_.ink] });
      X.restore();
    } };
  }
  s49.label = 'terminal'; SHOT['49'] = s49;
})();
