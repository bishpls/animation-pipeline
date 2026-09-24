// engine/render.mjs: render a project page in headless Chrome (GPU). Adapted from JohnHeibel/ClaudeAnimationBase.
// Run from the repo root. The project is a folder with index.html (see projects/open-all-night).
//
//   LOOK (open the images with the Read tool):
//     node engine/render.mjs P --sheet=1,2.5,4 [--cols=4] [--w=480] [--out=P/board/a.jpg]    contact sheet of chosen times
//     node engine/render.mjs P --strip=2.0:2.5 [--step=1]                                     every frame (or every Nth) of a stretch
//     node engine/render.mjs P --sheet=2.1 --crop=760,300,400,400 --w=800                     full-res detail crops
//     node engine/render.mjs P --stills=1.2,3.4                                               full-res PNGs -> P/board/stills
//     node engine/render.mjs P --shots [--per=4]                                              first/mid/last of every shot, one sheet
//   MAKE:
//     node engine/render.mjs P --frames [--range=0:8] [--workers=6]                           frames -> P/out/frames (parallel, resumable)
//     node engine/render.mjs P --encode [--out=P/out/video.mp4]                               frames + P/assets/song audio -> MP4
//     node engine/render.mjs P --clip=10:14 [--out=...]                                       quick MP4 of a range, with audio
//   DEBUG: node engine/render.mjs P --eval='LINES.map(l => [l.t0, l.text])'     evaluate an expression in the page
//   SERVE: node engine/render.mjs P --serve   -> open the printed URL in Chrome to scrub/play with sound
//   Add --loop=name to render a standalone loop instead of the timeline.
import puppeteer from 'puppeteer-core';
import { spawn } from 'node:child_process';
import http from 'node:http';
import { mkdirSync, writeFileSync, existsSync, statSync, renameSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import { dirname, resolve, extname, join } from 'node:path';

const argv = process.argv.slice(2);
const PROJ = argv.find(a => !a.startsWith('--')) || 'projects/open-all-night';
const args = Object.fromEntries(argv.filter(a => a.startsWith('--')).map(a => { const b = a.replace(/^--/, ''), i = b.indexOf('='); return i < 0 ? [b, true] : [b.slice(0, i), b.slice(i + 1)]; }));
const CHROME = [args.chrome, process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium'].find(p => p && existsSync(p));
const fps = +(args.fps || 24), FRAMES = args.framesdir || `${PROJ}/out/frames`;
const run = (cmd, a) => new Promise((ok, bad) => { const p = spawn(cmd, a, { stdio: 'inherit' }); p.on('close', c => c ? bad(new Error(cmd + ' exited ' + c)) : ok()); });
const times = s => String(s).split(',').map(Number);
const span = s => String(s).split(':').map(Number);
const audioOf = () => args.audio || [`${PROJ}/assets/mix.wav`, `${PROJ}/assets/song.wav`, `${PROJ}/assets/song.mp3`].find(existsSync);

if (args.encode) {
  const out = args.out || `${PROJ}/out/video.mp4`, n = readdirSync(FRAMES).filter(f => f.endsWith('.jpg') || f.endsWith('.png')).length, audio = audioOf();
  const ext = existsSync(`${FRAMES}/f00000.png`) ? 'png' : 'jpg';
  console.log(`encoding ${n} frames -> ${out}${audio ? ' with ' + audio : ''}`);
  const from = +(args.from || 0), f0 = Math.round(from * fps);          // --from=seconds: start the cut later (trims picture and audio together)
  await run('ffmpeg', ['-y', '-loglevel', 'error', '-stats', '-framerate', String(fps), '-start_number', String(f0), '-i', `${FRAMES}/f%05d.${ext}`,
    ...(audio ? ['-ss', String(f0 / fps), '-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '320k', '-shortest'] : []),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', String(args.crf || 14), '-tune', 'grain', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]);
  console.log('wrote ' + out);
  process.exit(0);
}

// ---- static server at the repo root (fonts, cues and audio load over http, not file://)
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.ttf': 'font/ttf', '.otf': 'font/otf',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.css': 'text/css', '.svg': 'image/svg+xml' };
const server = http.createServer((req, res) => {
  const p = join(process.cwd(), decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(process.cwd()) || !existsSync(p) || statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': MIME[extname(p)] || 'application/octet-stream', 'cache-control': 'no-store' });
  res.end(readFileSync(p));
});
await new Promise(r => server.listen(+(args.port || 0), '127.0.0.1', r));
const URL0 = `http://127.0.0.1:${server.address().port}/${PROJ}/index.html`;
if (args.serve) { console.log(`studio: ${URL0}${args.loop ? '?loop=' + args.loop : ''}`); await new Promise(() => {}); }

const gpu = process.platform === 'darwin' ? ['--use-angle=metal'] : ['--use-gl=angle'];
const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, protocolTimeout: 0,
  args: ['--ignore-gpu-blocklist', ...gpu, '--enable-gpu-rasterization', '--window-size=1920,1080', '--disable-renderer-backgrounding', '--disable-background-timer-throttling', '--autoplay-policy=no-user-gesture-required'] });
async function openPage(tag = '') {
  const page = await browser.newPage();
  page.on('console', m => { if (['error', 'warn', 'log'].includes(m.type()) && !m.text().includes('GPU stall')) console.log(`[page${tag}]`, m.text()); });
  page.on('pageerror', e => console.log(`[page error${tag}]`, e.message));
  await page.goto(URL0 + '?render' + (args.loop ? '&loop=' + args.loop : ''), { waitUntil: 'load' });
  await page.waitForFunction('window.ready === true || window.failed', { timeout: 120000 });
  if (args.loop) await page.evaluate(n => { window.LOOP = LOOPS[n]; }, args.loop);
  return page;
}
const frameOf = async (page, t, mime, q) => { const url = await page.evaluate((t, m, q) => window.renderAt(t, m, q), t, mime, q); return Buffer.from(url.slice(url.indexOf(',') + 1), 'base64'); };
const lengthOf = page => page.evaluate(() => (window.LOOP ? window.LOOP.len : DUR));

if (args.eval) {
  const page = await openPage();
  console.log(JSON.stringify(await page.evaluate(e => eval(e), args.eval), null, 1));
} else if (args.sheet || args.strip || args.shots) {
  const page = await openPage(), out = args.out || `${PROJ}/board/sheet.jpg`; mkdirSync(dirname(out), { recursive: true });
  let ts;
  if (args.strip) { const [a, b] = span(args.strip), st = +(args.step || 1); ts = []; for (let i = Math.round(a * fps); i <= Math.round(b * fps); i += st) ts.push(i / fps); }
  else if (args.shots) {
    const per = +(args.per || 3);
    ts = (await page.evaluate(() => SHOTS.map((s, i) => [s[0], i + 1 < SHOTS.length ? SHOTS[i + 1][0] : DUR]))).flatMap(([a, b]) => Array.from({ length: per }, (_, k) => +(a + (b - a) * (k + .5) / per).toFixed(3)));
  } else ts = times(args.sheet);
  const crop = args.crop ? times(args.crop) : null;
  const { url, ms } = await page.evaluate((ts, c, w, crop) => window.renderSheet(ts, c, w, crop), ts, +(args.cols || (args.strip ? 6 : args.shots ? +(args.per || 3) * 2 : 3)), +(args.w || (args.strip ? 320 : args.shots ? 320 : 640)), crop);
  writeFileSync(out, Buffer.from(url.slice(url.indexOf(',') + 1), 'base64'));
  console.log(`${out}  (${ts.length} frames)  ms/frame avg ${(ms.reduce((a, b) => a + b, 0) / ms.length).toFixed(0)}`);
} else if (args.stills) {
  const page = await openPage(), out = args.out || `${PROJ}/board/stills`; mkdirSync(out, { recursive: true });
  for (const s of times(args.stills)) { const f = `${out}/t${s.toFixed(2).replace('.', '_')}.png`; writeFileSync(f, await frameOf(page, s, 'image/png')); console.log(f); }
} else if (args.frames) {
  const probe = await openPage(), len = await lengthOf(probe); await probe.close();
  const [a, b] = args.range ? span(args.range) : [0, len], workers = +(args.workers || 6), ext = args.png ? 'png' : 'jpg';
  if (args.clean) rmSync(FRAMES, { recursive: true, force: true });
  mkdirSync(FRAMES, { recursive: true });
  const first = Math.round(a * fps), last = Math.min(Math.ceil(len * fps) - 1, Math.round(b * fps) - 1);
  const todo = []; for (let i = first; i <= last; i++) { const f = `${FRAMES}/f${String(i).padStart(5, '0')}.${ext}`; if (!existsSync(f) || statSync(f).size < 1000) todo.push(i); }
  console.log(`${todo.length} frames to render (${last - first + 1 - todo.length} done), ${workers} workers`);
  let next = 0, done = 0; const start = Date.now();
  await Promise.all(Array.from({ length: workers }, async (_, w) => {
    const page = await openPage('#' + w);
    while (next < todo.length) {
      const i = todo[next++], f = `${FRAMES}/f${String(i).padStart(5, '0')}.${ext}`;
      const buf = await frameOf(page, i / fps, ext === 'png' ? 'image/png' : 'image/jpeg', .96);
      writeFileSync(f + '.tmp', buf); renameSync(f + '.tmp', f);
      if (++done % 48 === 0 || done === todo.length) { const el = (Date.now() - start) / 1000; console.log(`${done}/${todo.length}  ${(el / done * 1000).toFixed(0)} ms/frame eff  eta ${((todo.length - done) * el / done / 60).toFixed(1)} min`); }
    }
  }));
} else if (args.clip) {
  const page = await openPage(), len = await lengthOf(page);
  const [a, b] = typeof args.clip === 'string' ? span(args.clip) : [0, len];
  const audio = args.noaudio ? null : audioOf(), out = args.out || `${PROJ}/out/clip.mp4`; mkdirSync(dirname(out), { recursive: true });
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    ...(audio ? ['-ss', String(a), '-t', String(b - a), '-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '256k', '-shortest'] : []),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.round((b - a) * fps), start = Date.now();
  for (let i = 0; i < n; i++) {
    const buf = await frameOf(page, a + i / fps, 'image/jpeg', .94);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 48 === 0) console.log(`frame ${i + 1}/${n}  ${((Date.now() - start) / (i + 1)).toFixed(0)} ms/frame`);
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r));
  console.log(`wrote ${out}`);
} else console.log('nothing to do: see the usage at the top of engine/render.mjs');
await browser.close(); server.close();
