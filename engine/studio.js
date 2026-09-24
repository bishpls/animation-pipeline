// engine/studio.js: the timeline and the page API the renderer drives.
//
//   shots([[t0, fn], [t1, fn], ...])     fn(t, lt, dur) paints the WHOLE frame into the inks (pure function of t).
//                                        It may return an object; PROJECT.overlay(t, ret, shot) runs after it (lyrics).
//   LOOPS.name = t => {...}; LOOPS.name.len = 4      standalone loops / test boards (?loop=name, --loop=name)
// Page API used by engine/render.mjs: window.ready, renderAt(t, mime, q), renderSheet(ts, cols, w, crop), frameInfo(t).

const SHOTS = [];
const LOOPS = {};
function shots(list) { SHOTS.push(...list); SHOTS.sort((a, b) => a[0] - b[0]); }
function shotAt(t) {
  let i = 0; while (i + 1 < SHOTS.length && t >= SHOTS[i + 1][0]) i++;
  const t0 = SHOTS[i][0], t1 = i + 1 < SHOTS.length ? SHOTS[i + 1][0] : DUR;
  return { i, fn: SHOTS[i][1], t0, t1, name: SHOTS[i][1].name };
}
function sectionAt(t) { for (const s of C.sections || []) if (t >= s.t0 && t < s.t1) return s.name; return ''; }

function drawFrame(t) {
  NOW = t;
  risoClear();
  let ret, printOpts = {};
  if (window.LOOP) ret = window.LOOP(t);
  else if (SHOTS.length) {
    const s = shotAt(t);
    ret = s.fn(t, t - s.t0, s.t1 - s.t0) || {};
    resetT();
    if (window.PROJECT && PROJECT.overlay) PROJECT.overlay(t, ret, s);
  }
  resetT();
  if (ret && ret.print) printOpts = ret.print;
  risoPrint(t, printOpts);
}

window.renderAt = (t, mime = 'image/jpeg', q = .95) => { drawFrame(t); return RISO.out.toDataURL(mime, q); };
window.frameInfo = t => ({ t, bar: barPos(t), beat: beatPos(t), section: sectionAt(t), shot: SHOTS.length ? shotAt(t).name : '' });
window.renderSheet = (ts, cols = 4, w = 480, crop = null) => {
  const [cx, cy, cw, ch] = crop || [0, 0, W, H];
  const h = Math.round(w * ch / cw), rows = Math.ceil(ts.length / cols);
  const S = document.createElement('canvas'); S.width = cols * w; S.height = rows * (h + 18);
  const x = S.getContext('2d'); x.fillStyle = '#111'; x.fillRect(0, 0, S.width, S.height);
  const ms = [];
  ts.forEach((t, i) => {
    const t0 = performance.now(); drawFrame(t); ms.push(Math.round(performance.now() - t0));
    const X = (i % cols) * w, Y = Math.floor(i / cols) * (h + 18);
    x.drawImage(RISO.out, cx, cy, cw, ch, X, Y + 18, w, h);
    const fi = frameInfo(t);
    x.fillStyle = '#ffe14d'; x.font = '12px ui-monospace, monospace';
    x.fillText(`${t.toFixed(2)}s  f${Math.round(t * FPS)}  bar ${fi.bar.toFixed(2)}  ${fi.shot}`, X + 4, Y + 13);
  });
  return { url: S.toDataURL('image/jpeg', .88), ms };
};

// interactive studio: scrub, play with audio (studio.html without ?render)
async function studioUI() {
  if (location.search.includes('render')) return;
  const q = new URLSearchParams(location.search);
  if (q.get('loop') && LOOPS[q.get('loop')]) window.LOOP = LOOPS[q.get('loop')];
  const len = window.LOOP ? window.LOOP.len : DUR;
  const bar = document.createElement('div'); bar.className = 'bar';
  bar.innerHTML = `<button id="pl">play</button><input id="sc" type="range" min="0" max="${len}" step="${1 / FPS}" value="${q.get('t') || 0}"><span id="tt"></span>`;
  document.body.appendChild(bar);
  const sc = bar.querySelector('#sc'), tt = bar.querySelector('#tt'), pl = bar.querySelector('#pl');
  const au = window.PROJECT && PROJECT.audio && !window.LOOP ? new Audio(PROJECT.audio) : null;
  const show = t => { drawFrame(t); const f = frameInfo(t); tt.textContent = `${t.toFixed(2)}s  bar ${f.bar.toFixed(2)}  ${f.section} · ${f.shot}`; };
  sc.oninput = () => { if (au) au.currentTime = +sc.value; show(+sc.value); };
  let playing = false, start = 0, from = 0;
  pl.onclick = () => { playing = !playing; pl.textContent = playing ? 'pause' : 'play'; from = +sc.value; start = performance.now(); if (au) { au.currentTime = from; playing ? au.play() : au.pause(); } if (playing) loop(); };
  const loop = () => { if (!playing) return; const t = au ? au.currentTime : from + (performance.now() - start) / 1000; sc.value = t % len; show(t % len); requestAnimationFrame(loop); };
  show(+sc.value);
}
