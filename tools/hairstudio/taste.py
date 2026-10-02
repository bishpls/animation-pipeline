"""The taste loop (Michael, 2026-10-02: find the intersection between Claude's eye and ours). A local page serves pairs of
builds (stills or clips), blind (labelled A and B); Michael picks with the keyboard; each judgment saves on the key
press (taste/judgments.jsonl); then the page reveals which builds they were and Claude's prediction, made before and
stored with the pair, with its reason. Over time the judgments calibrate the measures (a measure is kept when it
orders his pairs) and Claude's prediction hit-rate shows where the two eyes agree.

    python taste.py serve [--port 8790]       the page (127.0.0.1 only)
    python taste.py stills TAG [TAG ...]       the four-view stills for builds (from studio/TAG.png's row of ours)
Pairs: taste/pairs.json  [{id, kind: still|clip, a, b, predict: {pick: a|b|same, why}}]
"""
import json, os, sys, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
TD = os.path.join(HERE, 'taste')
os.makedirs(TD, exist_ok=True)
PAIRS, JUDG = os.path.join(TD, 'pairs.json'), os.path.join(TD, 'judgments.jsonl')

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Taste</title><style>
:root{--bg:#f3f3f5;--fg:#1c1c20;--card:#fff;--line:#d8d8de;--acc:#c0562e}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#151518;--fg:#ececf0;--card:#222226;--line:#3a3a42}}
body{background:var(--bg);color:var(--fg);font:15px/1.4 -apple-system,system-ui,sans-serif;margin:0;padding:12px}
.top{display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}.prog{opacity:.7}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.side{background:var(--card);border:2px solid var(--line);border-radius:10px;padding:8px}
.side.pick{border-color:var(--acc)} .side h2{margin:0 0 6px;font-size:18px}
.side img,.side video{width:100%;border-radius:6px;background:#fff}
.keys{opacity:.75;font-size:13px}.reveal{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;margin-top:10px;display:none}
textarea{width:100%;min-height:44px;font:inherit;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px}
button{font:inherit;padding:6px 12px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
@media (max-width:700px){.pair{grid-template-columns:1fr}}
</style></head><body>
<div class="top"><h1 style="margin:0;font-size:20px">Which looks better?</h1><span class="prog" id="prog"></span>
<span class="keys"><b>&larr;</b> A &nbsp; <b>&rarr;</b> B &nbsp; <b>&darr;</b> same &nbsp; <b>N</b> note &nbsp; <b>Z</b> undo &nbsp; <b>Enter</b> next &nbsp; <b>Space</b> replay clips</span></div>
<div class="pair"><div class="side" id="A"><h2>A</h2><div id="ma"></div></div><div class="side" id="B"><h2>B</h2><div id="mb"></div></div></div>
<div style="margin-top:8px"><textarea id="note" placeholder="optional note (N to focus, Esc to leave)"></textarea></div>
<div class="reveal" id="rev"></div>
<script>
let pair=null, judged=false;
function media(kind,src){return kind==='clip'?`<video src="${src}" autoplay loop muted playsinline></video>`:`<img src="${src}">`}
async function next(){
  const r=await fetch('/api/next'); const d=await r.json();
  document.getElementById('prog').textContent=d.done+' judged, '+d.left+' left';
  if(!d.pair){document.getElementById('ma').innerHTML='';document.getElementById('mb').innerHTML='<p>All done - thank you.</p>';return}
  pair=d.pair; judged=false; document.getElementById('rev').style.display='none'; document.getElementById('note').value='';
  for(const s of ['A','B']) document.getElementById(s).classList.remove('pick');
  document.getElementById('ma').innerHTML=media(pair.kind,pair.a_media); document.getElementById('mb').innerHTML=media(pair.kind,pair.b_media);
}
async function judge(pick){
  if(!pair||judged) return; judged=true;
  if(pick!=='same') document.getElementById(pick.toUpperCase()).classList.add('pick');
  const r=await fetch('/api/judge',{method:'POST',body:JSON.stringify({id:pair.id,pick,note:document.getElementById('note').value})});
  const d=await r.json(); const rv=document.getElementById('rev'); rv.style.display='block';
  rv.innerHTML=`<b>A</b> = ${d.a} &nbsp; <b>B</b> = ${d.b}<br>Claude predicted <b>${d.predict.pick.toUpperCase()}</b>: ${d.predict.why}<br>${d.agree?'&#10003; same call':'&#10007; different call - this is the useful one'} &nbsp; <span class="keys">Enter for the next pair</span>`;
}
async function undo(){await fetch('/api/undo',{method:'POST'}); next()}
document.addEventListener('keydown',e=>{
  const ta=document.getElementById('note'); if(document.activeElement===ta){ if(e.key==='Escape') ta.blur(); return }
  if(e.key==='ArrowLeft') judge('a'); else if(e.key==='ArrowRight') judge('b'); else if(e.key==='ArrowDown') judge('same');
  else if(e.key==='Enter'&&judged) next(); else if(e.key==='n'||e.key==='N'){e.preventDefault(); ta.focus()}
  else if(e.key==='z'||e.key==='Z') undo(); else if(e.key===' '){e.preventDefault(); document.querySelectorAll('video').forEach(v=>{v.currentTime=0;v.play()})}
});
document.getElementById('A').onclick=()=>judge('a'); document.getElementById('B').onclick=()=>judge('b');
next();
</script></body></html>"""


def load_pairs():
    return json.load(open(PAIRS)) if os.path.exists(PAIRS) else []


def load_judg():
    if not os.path.exists(JUDG):
        return []
    return [json.loads(l) for l in open(JUDG) if l.strip()]


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, *a):
        pass

    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            b = PAGE.encode(); self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b); return
        if self.path.startswith('/api/next'):
            P, J = load_pairs(), load_judg()
            done = {j['id'] for j in J}
            left = [p for p in P if p['id'] not in done]
            p = left[0] if left else None
            out = None
            if p:
                out = dict(id=p['id'], kind=p['kind'], a_media=p['a_media'], b_media=p['b_media'])
            return self._json(dict(pair=out, done=len(done), left=len(left)))
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n) or b'{}')
        if self.path.startswith('/api/judge'):
            P = {p['id']: p for p in load_pairs()}
            p = P[body['id']]
            rec = dict(id=p['id'], kind=p['kind'], a=p['a'], b=p['b'], pick=body['pick'], note=body.get('note', ''),
                       predict=p['predict'], agree=p['predict']['pick'] == body['pick'], at=time.strftime('%Y-%m-%d %H:%M:%S'))
            with open(JUDG, 'a') as f:
                f.write(json.dumps(rec) + '\n')
            return self._json(rec)
        if self.path.startswith('/api/undo'):
            J = load_judg()
            with open(JUDG, 'w') as f:
                for j in J[:-1]:
                    f.write(json.dumps(j) + '\n')
            return self._json(dict(ok=True))


def stills(tags):
    """quiet stills (Michael: "test page is very noisy"): front and three-quarter only, plus the silhouettes (front,
    three-quarter, profile, back) as solid shapes underneath."""
    from PIL import Image
    import numpy as np
    for t in tags:
        a = Image.open(os.path.join(HERE, 'studio', t + '.png'))
        top = a.crop((0, 660, 1200, 1320))
        z = np.load(os.path.join(HERE, 'studio', t + '_ours.npz'))
        sil = []
        for v in ('front', 'three_quarter', 'profile', 'back'):
            m = z[v + '_hair']
            im = np.full(m.shape + (3,), 245, np.uint8); im[m] = (40, 32, 30)
            sil.append(im)
        s = Image.fromarray(np.concatenate(sil, 1)).resize((1200, 330))
        out = Image.new('RGB', (1200, 1000), (245, 245, 247)); out.paste(top, (0, 0)); out.paste(s, (0, 668))
        out.save(os.path.join(TD, t + '_still.png'))


if __name__ == '__main__':
    if sys.argv[1] == 'serve':
        port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 8790
        print('http://127.0.0.1:%d/' % port)
        ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
    elif sys.argv[1] == 'stills':
        stills(sys.argv[2:])
