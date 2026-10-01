// Drive a labelling page (charkit.label) headless and screenshot it: Chrome's DevTools protocol over Node's built-in
// WebSocket (no packages). Real key and mouse events go through the page's own handlers, so the server saves exactly
// what a person's keys would.
//
//   node tools/label/drive.mjs URL STEPS.json OUTDIR [--size 1600x1000]
//
// STEPS: [{"shot": "name"}, {"key": "Enter" | "y" | "ArrowLeft" | ..., "shift": false}, {"click": {"view": "profile",
//         "region": "S:31.1", "pane": "over" | "close", "shift": false}}, {"clickSel": "#b_undo"}, {"wait": 300},
//         {"eval": "js expression"} (its value printed), {"size": "1280x800"}, {"reload": true}, {"note": "text"}]
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, readFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [url, stepsPath, outDir, ...rest] = process.argv.slice(2);
const sizeArg = rest.includes('--size') ? rest[rest.indexOf('--size') + 1] : '1600x1000';
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const steps = JSON.parse(readFileSync(stepsPath, 'utf8'));
mkdirSync(outDir, { recursive: true });
const port = 9300 + Math.floor(Math.random() * 500);
const prof = mkdtempSync(join(tmpdir(), 'labeldrive-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function target() {
  for (let i = 0; i < 100; i++) {
    try { const r = await fetch(`http://127.0.0.1:${port}/json/list`); const j = await r.json();
      const p = j.find(t => t.type === 'page'); if (p) return p.webSocketDebuggerUrl; } catch (e) { }
    await sleep(100);
  }
  throw new Error('chrome did not start');
}
const ws = new WebSocket(await target());
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let seq = 0; const pending = new Map();
ws.addEventListener('message', ev => { const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const [res, rej] = pending.get(m.id); pending.delete(m.id); m.error ? rej(new Error(m.error.message)) : res(m.result); } });
// every call answers within 15 s or the run fails (a hung page must not hang the harness)
const cdp = (method, params = {}) => new Promise((res, rej) => { const id = ++seq;
  const tm = setTimeout(() => { pending.delete(id); rej(new Error('timeout: ' + method)); }, 15000);
  pending.set(id, [v => { clearTimeout(tm); res(v); }, e => { clearTimeout(tm); rej(e); }]); ws.send(JSON.stringify({ id, method, params })); });
async function evaluate(expr) { const r = await cdp('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' ' + JSON.stringify(r.exceptionDetails.exception || {})); return r.result.value; }
async function setSize(s) { const [w, h] = s.split('x').map(Number);
  await cdp('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false }); }
async function settle() {        // two frames drawn (or 600 ms: a headless page can stall its frames)
  await evaluate('new Promise(r => { requestAnimationFrame(() => requestAnimationFrame(r)); setTimeout(r, 600); })'); await sleep(120); }

const KEYS = { Enter: [13, 'Enter', '\r'], Tab: [9, 'Tab', ''], Backspace: [8, 'Backspace', ''], Escape: [27, 'Escape', ''],
  ArrowLeft: [37, 'ArrowLeft', ''], ArrowRight: [39, 'ArrowRight', ''], ArrowUp: [38, 'ArrowUp', ''], ArrowDown: [40, 'ArrowDown', ''] };
async function key(k, shift) {
  let vk, code, text;
  if (KEYS[k]) [vk, code, text] = KEYS[k];
  else if (k === '?') { vk = 191; code = 'Slash'; text = '?'; }
  else if (/^[0-9]$/.test(k)) { vk = 48 + +k; code = 'Digit' + k; text = k; }
  else { vk = k.toUpperCase().charCodeAt(0); code = 'Key' + k.toUpperCase(); text = shift ? k.toUpperCase() : k; }
  const mods = shift ? 8 : 0;
  await cdp('Input.dispatchKeyEvent', { type: text ? 'keyDown' : 'rawKeyDown', key: k.length === 1 && shift ? k.toUpperCase() : k, code,
    windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, text, unmodifiedText: text, modifiers: mods });
  await cdp('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, modifiers: mods });
}
async function clickAt(x, y, shift) {
  const mods = shift ? 8 : 0;
  await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, modifiers: mods });
  await cdp('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1, modifiers: mods });
  await cdp('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1, modifiers: mods });
}
async function regionPoint(view, rid, pane) {
  return evaluate(`(() => { const col = document.querySelector('.vcol[data-view="${view}"]');
    const svg = col.querySelector('svg.${pane || 'over'}'); const g = [...svg.querySelectorAll('g.reg')].find(e => e.dataset.rid === ${JSON.stringify(rid)});
    const r = S.T.regions['${view}'].find(q => q.id === ${JSON.stringify(rid)}); const m = svg.getScreenCTM();
    const p = svg.createSVGPoint(); p.x = r.anchor[0]; p.y = r.anchor[1]; const q = p.matrixTransform(m);
    col.scrollIntoView({block: 'nearest'}); const q2 = p.matrixTransform(svg.getScreenCTM());
    return [q2.x, q2.y]; })()`);
}

const log = [];
const t0 = Date.now();
await setSize(sizeArg);
await cdp('Page.enable'); await cdp('Runtime.enable');
await cdp('Page.navigate', { url });
await sleep(800); await evaluate("new Promise(r => { const f = () => (typeof S !== 'undefined' && S.T) ? r() : setTimeout(f, 50); f(); })"); await settle();
let n = 0;
process.on('unhandledRejection', e => { console.error('FAILED:', e.message); try { chrome.kill(); } catch (_) { } process.exit(2); });
for (const s of steps) {
  const t = Date.now();
  if (process.env.DRIVE_VERBOSE) console.log('step', JSON.stringify(s));
  if (s.shot) { await settle(); const r = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: !!s.full });
    const f = join(outDir, `${String(++n).padStart(2, '0')}_${s.shot}.png`); writeFileSync(f, Buffer.from(r.data, 'base64')); log.push({ shot: f }); }
  else if (s.key) { await key(s.key, s.shift); await sleep(s.wait ?? 60); }
  else if (s.click) { const [x, y] = await regionPoint(s.click.view, s.click.region, s.click.pane); await clickAt(x, y, s.click.shift); await sleep(s.wait ?? 120); }
  else if (s.clickSel) { const [x, y] = await evaluate(`(() => { const e = document.querySelector(${JSON.stringify(s.clickSel)}); const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
    await clickAt(x, y); await sleep(s.wait ?? 120); }
  else if (s.hover) { const [x, y] = await regionPoint(s.hover.view, s.hover.region, s.hover.pane); await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y }); await sleep(150); }
  else if (s.wait) await sleep(s.wait);
  else if (s.eval) { const v = await evaluate(s.eval); log.push({ eval: s.eval, value: v }); console.log('eval', s.eval.slice(0, 60), '->', JSON.stringify(v)); }
  else if (s.size) { await setSize(s.size); await settle(); }
  else if (s.reload) { await cdp('Page.reload'); await sleep(800); await evaluate("new Promise(r => { const f = () => (typeof S !== 'undefined' && S.T) ? r() : setTimeout(f, 50); f(); })"); await settle(); }
  else if (s.note) console.log('--', s.note);
  if (!s.shot && !s.eval) log.push({ step: s, ms: Date.now() - t });
}
writeFileSync(join(outDir, 'drive.json'), JSON.stringify({ url, steps: log, total_ms: Date.now() - t0 }, null, 1));
console.log('done', n, 'shots in', outDir, (Date.now() - t0) + ' ms');
ws.close(); chrome.kill();
process.exit(0);
