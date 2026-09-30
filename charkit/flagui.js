// charkit review flags (charkit/flags.py): on any picture of a preview page, press F (or the Flag button), click a point
// or drag a box, pick a severity (0 praise, 1 minor, 2 clear, 3 severe) and type a note. Flags are saved by the local
// server (`python -m charkit preview serve`) to charkit/out/previews/flags.jsonl, anchored on the board the picture shows,
// and drawn as markers on every picture of that board. Opened as a file, the page works as before and says so.
(function () {
  'use strict';
  if (window.__charkitFlags) return;
  window.__charkitFlags = true;
  var SEV = [
    { n: 0, name: 'praise', color: '#1f9d55' },
    { n: 1, name: 'minor', color: '#c9a400' },
    { n: 2, name: 'clear', color: '#e07000' },
    { n: 3, name: 'severe', color: '#d42a2a' }
  ];
  var served = /^https?:$/.test(location.protocol);
  var state = { on: false, flags: {}, info: {}, wraps: [], pop: null };

  function css() {
    var s = document.createElement('style');
    s.textContent =
      '.ckf-wrap{position:relative;display:inline-block;line-height:0}' +
      '.ckf-wrap img{display:block}' +
      '.ckf-layer{position:absolute;left:0;top:0;right:0;bottom:0;pointer-events:none}' +
      '.ckf-on .ckf-layer{pointer-events:auto;cursor:crosshair;outline:2px dashed rgba(224,112,0,.55);outline-offset:-2px}' +
      '.ckf-dot{position:absolute;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;border:2px solid #fff;' +
      'box-shadow:0 0 0 1px rgba(0,0,0,.45);pointer-events:auto;cursor:pointer;font:bold 10px/12px system-ui,sans-serif;' +
      'color:#fff;text-align:center}' +
      '.ckf-box{position:absolute;border:2px solid;box-shadow:0 0 0 1px rgba(255,255,255,.7);pointer-events:auto;cursor:pointer}' +
      '.ckf-band{position:absolute;border:1px dashed #e07000;background:rgba(224,112,0,.12)}' +
      '.ckf-bar{position:fixed;top:10px;right:10px;z-index:9999;background:#fff;border:1px solid #ccc;border-radius:8px;' +
      'padding:6px 10px;font:13px/1.4 -apple-system,system-ui,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.15);color:#222}' +
      '.ckf-bar button{font:inherit;margin-left:6px;cursor:pointer}' +
      '.ckf-bar .ckf-mode{font-weight:600}' +
      '.ckf-pop{position:absolute;z-index:10000;background:#fff;border:1px solid #bbb;border-radius:8px;padding:10px;width:300px;' +
      'box-shadow:0 4px 16px rgba(0,0,0,.2);font:13px/1.4 -apple-system,system-ui,sans-serif;color:#222}' +
      '.ckf-pop textarea{width:100%;box-sizing:border-box;height:64px;font:inherit;margin:6px 0}' +
      '.ckf-pop .ckf-sev button{font:inherit;margin:0 4px 4px 0;padding:2px 8px;border:2px solid transparent;border-radius:12px;' +
      'color:#fff;cursor:pointer;opacity:.55}' +
      '.ckf-pop .ckf-sev button.sel{opacity:1;border-color:#222}' +
      '.ckf-k{color:#666;font-size:12px;word-break:break-word}' +
      '.ckf-pop .ckf-act{display:flex;gap:6px;justify-content:flex-end;margin-top:4px}' +
      '.ckf-list{max-height:40vh;overflow:auto;margin-top:6px;border-top:1px solid #eee;padding-top:4px;max-width:420px}' +
      '.ckf-list div{cursor:pointer;padding:2px 0;border-bottom:1px solid #f2f2f2}' +
      '.ckf-note{position:fixed;bottom:10px;right:10px;z-index:9999;background:#fffbe6;border:1px solid #e6d27a;' +
      'border-radius:6px;padding:6px 10px;font:12px/1.4 -apple-system,system-ui,sans-serif;color:#444;max-width:420px}';
    document.head.appendChild(s);
  }

  function note(msg) {
    var n = document.createElement('div');
    n.className = 'ckf-note';
    n.innerHTML = msg;
    document.body.appendChild(n);
  }

  function rel(img) {
    // the picture's path under charkit/out/previews (the server's root)
    try { return decodeURIComponent(new URL(img.src, location.href).pathname).replace(/^\//, ''); }
    catch (e) { return null; }
  }

  function api(method, path, body) {
    return fetch(path, {
      method: method, headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body)
    }).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; });
    });
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function wrap(img) {
    if (img.parentNode && img.parentNode.classList && img.parentNode.classList.contains('ckf-wrap')) return;
    var w = document.createElement('span');
    w.className = 'ckf-wrap';
    img.parentNode.insertBefore(w, img);
    w.appendChild(img);
    var layer = document.createElement('div');
    layer.className = 'ckf-layer';
    w.appendChild(layer);
    var item = { img: img, wrap: w, layer: layer, path: rel(img) };
    state.wraps.push(item);
    bindDraw(item);
  }

  function natural(item, ev) {
    var r = item.img.getBoundingClientRect();
    var sx = item.img.naturalWidth / r.width, sy = item.img.naturalHeight / r.height;
    return [Math.max(0, Math.min(item.img.naturalWidth, (ev.clientX - r.left) * sx)),
            Math.max(0, Math.min(item.img.naturalHeight, (ev.clientY - r.top) * sy))];
  }

  function bindDraw(item) {
    var start = null, band = null;
    item.layer.addEventListener('mousedown', function (ev) {
      if (!state.on || ev.button !== 0 || ev.target !== item.layer) return;
      ev.preventDefault();
      start = { n: natural(item, ev), x: ev.clientX, y: ev.clientY };
      band = document.createElement('div');
      band.className = 'ckf-band';
      item.layer.appendChild(band);
    });
    window.addEventListener('mousemove', function (ev) {
      if (!start) return;
      var r = item.layer.getBoundingClientRect();
      var x0 = Math.min(start.x, ev.clientX) - r.left, y0 = Math.min(start.y, ev.clientY) - r.top;
      band.style.left = x0 + 'px'; band.style.top = y0 + 'px';
      band.style.width = Math.abs(ev.clientX - start.x) + 'px'; band.style.height = Math.abs(ev.clientY - start.y) + 'px';
    });
    window.addEventListener('mouseup', function (ev) {
      if (!start) return;
      var s = start; start = null;
      if (band) { band.remove(); band = null; }
      var e = natural(item, ev);
      var moved = Math.abs(ev.clientX - s.x) + Math.abs(ev.clientY - s.y) > 6;
      var draft = moved ? { box: [Math.min(s.n[0], e[0]), Math.min(s.n[1], e[1]), Math.max(s.n[0], e[0]), Math.max(s.n[1], e[1])] }
                        : { px: s.n };
      popup(item, draft, ev.pageX, ev.pageY);
    });
    // in flag mode a click on a picture never follows its link
    item.layer.addEventListener('click', function (ev) { if (state.on) { ev.preventDefault(); ev.stopPropagation(); } });
  }

  function closePop() { if (state.pop) { state.pop.remove(); state.pop = null; } }

  function popup(item, f, x, y) {
    closePop();
    var p = document.createElement('div');
    p.className = 'ckf-pop';
    p.style.left = Math.min(x + 12, window.scrollX + document.documentElement.clientWidth - 320) + 'px';
    p.style.top = (y + 12) + 'px';
    var info = state.info[item.path] || {};
    var sev = f.severity == null ? 2 : f.severity;
    var where = (f.id ? '' : (f.box ? 'box' : 'point')) + ' on <b>' + esc(f.board || info.board || item.path) + '</b>' +
      (f.view || info.view ? ' (' + esc(f.view || info.view) + ')' : '');
    var part = f.id ? ('part: <b>' + esc(f.part || 'null') + '</b>' + (f.region ? ' (' + esc(f.region) + ')' : '') +
      (f.parts ? '<br>in the box: ' + esc(Object.keys(f.parts).sort(function (a, b) { return f.parts[b] - f.parts[a]; })
        .map(function (k) { return k + ' ' + Math.round(100 * f.parts[k]) + '%'; }).join(', ')) : '') +
      '<br><span class="ckf-k">' + esc(f.part_source || '') + '</span>') : '';
    p.innerHTML = '<div class="ckf-k">' + (f.id ? esc(f.id) + ' &middot; ' + esc(f.t) + (f.edited ? ' (edited ' + esc(f.edited) + ')' : '') + '<br>' : '') +
      where + '</div>' + (part ? '<div class="ckf-k" style="margin-top:4px">' + part + '</div>' : '') +
      '<div class="ckf-sev" style="margin-top:6px">' + SEV.map(function (s) {
        return '<button data-s="' + s.n + '" style="background:' + s.color + '">' + s.n + ' ' + s.name + '</button>';
      }).join('') + '</div><textarea placeholder="note (what is wrong, or right)">' + esc(f.note || '') + '</textarea>' +
      '<div class="ckf-act">' + (f.id ? '<button class="ckf-del">Delete</button>' : '') +
      '<button class="ckf-cancel">Cancel</button><button class="ckf-save"><b>Save</b></button></div>' +
      '<div class="ckf-k">0-3 severity &middot; Cmd/Ctrl-Enter saves &middot; Esc cancels</div>';
    document.body.appendChild(p);
    state.pop = p;
    var ta = p.querySelector('textarea');
    function pick(n) {
      sev = n;
      p.querySelectorAll('.ckf-sev button').forEach(function (b) { b.classList.toggle('sel', +b.dataset.s === n); });
    }
    pick(sev);
    p.querySelectorAll('.ckf-sev button').forEach(function (b) { b.onclick = function () { pick(+b.dataset.s); }; });
    p.querySelector('.ckf-cancel').onclick = closePop;
    function save() {
      var req = f.id ? api('POST', '/api/flags/' + f.id, { severity: sev, note: ta.value })
                     : api('POST', '/api/flags', { image: item.path, px: f.px || null, box: f.box || null, severity: sev, note: ta.value });
      req.then(function (saved) {
        closePop();
        refresh().then(function () {
          if (!f.id) popupSaved(item, saved, x, y);
        });
      }).catch(function (e) { alert('flag not saved: ' + e.message); });
    }
    p.querySelector('.ckf-save').onclick = save;
    if (f.id) p.querySelector('.ckf-del').onclick = function () {
      if (!confirm('Delete this flag?')) return;
      api('DELETE', '/api/flags/' + f.id).then(function () { closePop(); refresh(); })
        .catch(function (e) { alert('not deleted: ' + e.message); });
    };
    p.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') closePop();
      else if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) save();
      else if (/^[0-3]$/.test(ev.key) && ev.target !== ta) pick(+ev.key);
    });
    ta.focus();
  }

  function popupSaved(item, f, x, y) {
    // the saved flag, with the part the server found under it
    var n = document.createElement('div');
    n.className = 'ckf-pop';
    n.style.left = Math.min(x + 12, window.scrollX + document.documentElement.clientWidth - 320) + 'px';
    n.style.top = (y + 12) + 'px';
    n.innerHTML = '<b>saved</b> ' + esc(f.id) + '<br>' + esc(f.board || '') + (f.view ? ' (' + esc(f.view) + ')' : '') +
      '<br>part: <b>' + esc(f.part || 'null') + '</b>' + (f.region ? ' (' + esc(f.region) + ')' : '') +
      '<div class="ckf-k">' + esc(f.part_source || '') + '</div>';
    document.body.appendChild(n);
    state.pop = n;
    setTimeout(function () { if (state.pop === n) closePop(); }, 3500);
  }

  function draw() {
    state.wraps.forEach(function (item) {
      item.layer.querySelectorAll('.ckf-dot,.ckf-box').forEach(function (e) { e.remove(); });
      var info = state.info[item.path];
      if (!info || !item.img.naturalWidth) return;
      var W = item.img.naturalWidth, H = item.img.naturalHeight;
      info.flags.forEach(function (f, i) {
        var at = f.at || {};
        var col = SEV[f.severity].color;
        var el;
        if (at.box) {
          el = document.createElement('div');
          el.className = 'ckf-box';
          el.style.left = (100 * at.box[0] / W) + '%'; el.style.top = (100 * at.box[1] / H) + '%';
          el.style.width = (100 * (at.box[2] - at.box[0]) / W) + '%'; el.style.height = (100 * (at.box[3] - at.box[1]) / H) + '%';
          el.style.borderColor = col;
        } else if (at.px) {
          el = document.createElement('div');
          el.className = 'ckf-dot';
          el.style.left = (100 * at.px[0] / W) + '%'; el.style.top = (100 * at.px[1] / H) + '%';
          el.style.background = col;
          el.textContent = f.severity;
        } else return;
        if (at.px && (at.px[0] < 0 || at.px[1] < 0 || at.px[0] > W || at.px[1] > H)) return;   // off this crop
        el.title = SEV[f.severity].name + ': ' + (f.note || '') + (f.part ? ' [' + f.part + ']' : '');
        el.addEventListener('mousedown', function (ev) { ev.stopPropagation(); });
        el.addEventListener('click', function (ev) {
          ev.preventDefault(); ev.stopPropagation();
          popup(item, f, ev.pageX, ev.pageY);
        });
        item.layer.appendChild(el);
      });
    });
    var n = 0, seen = {};
    Object.keys(state.info).forEach(function (k) {
      state.info[k].flags.forEach(function (f) { if (!seen[f.id]) { seen[f.id] = 1; n++; } });
    });
    var c = document.querySelector('.ckf-count');
    if (c) c.textContent = n + ' flag' + (n === 1 ? '' : 's') + ' here';
    list();
  }

  function list() {
    var box = document.querySelector('.ckf-list');
    if (!box || box.style.display === 'none') return;
    var rows = [], seen = {};
    state.wraps.forEach(function (item) {
      var info = state.info[item.path];
      (info ? info.flags : []).forEach(function (f) {
        if (seen[f.id]) return;
        seen[f.id] = 1;
        rows.push({ f: f, item: item });
      });
    });
    rows.sort(function (a, b) { return b.f.severity - a.f.severity || (a.f.t < b.f.t ? -1 : 1); });
    box.innerHTML = rows.length ? '' : '<i>no flags on this page</i>';
    rows.forEach(function (r) {
      var d = document.createElement('div');
      d.innerHTML = '<span style="color:' + SEV[r.f.severity].color + '">&#9679;</span> <b>' + r.f.severity + '</b> ' +
        esc(r.f.board || '') + ' &middot; ' + esc(r.f.part || 'no part') + ' &middot; ' + esc((r.f.note || '').slice(0, 80));
      d.onclick = function () { r.item.wrap.scrollIntoView({ behavior: 'smooth', block: 'center' }); };
      box.appendChild(d);
    });
  }

  function refresh() {
    var paths = state.wraps.map(function (w) { return w.path; }).filter(Boolean);
    return api('POST', '/api/view', { images: paths }).then(function (j) {
      state.info = j;
      draw();
    });
  }

  function toggle(on) {
    state.on = on === undefined ? !state.on : on;
    document.documentElement.classList.toggle('ckf-on', state.on);
    var b = document.querySelector('.ckf-mode');
    if (b) b.textContent = state.on ? 'Flag mode: ON (F)' : 'Flag mode: off (F)';
    if (!state.on) closePop();
  }

  function bar() {
    var b = document.createElement('div');
    b.className = 'ckf-bar';
    b.innerHTML = '<span class="ckf-mode">Flag mode: off (F)</span> <span class="ckf-count ckf-k"></span>' +
      '<button class="ckf-t">Flag</button><button class="ckf-l">List</button>' +
      '<div class="ckf-list" style="display:none"></div>';
    document.body.appendChild(b);
    b.querySelector('.ckf-t').onclick = function () { toggle(); };
    b.querySelector('.ckf-l').onclick = function () {
      var l = b.querySelector('.ckf-list');
      l.style.display = l.style.display === 'none' ? 'block' : 'none';
      list();
    };
    document.addEventListener('keydown', function (ev) {
      if (ev.target.tagName === 'TEXTAREA' || ev.target.tagName === 'INPUT' || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      if (ev.key === 'f' || ev.key === 'F') toggle();
      if (ev.key === 'Escape') { closePop(); toggle(false); }
    });
  }

  function init() {
    css();
    if (!served) {
      note('Review flags need the flag server: <code>python -m charkit preview serve</code>, then open ' +
           '<a href="http://localhost:8765/">http://localhost:8765/</a>. This page works as before without it.');
      return;
    }
    api('GET', '/api/ping').then(function () {
      var imgs = Array.prototype.slice.call(document.querySelectorAll('img'));
      imgs.forEach(function (img) {
        wrap(img);                                   // markers need the natural size: drawn again once it loads
        if (!img.complete) img.addEventListener('load', draw, { once: true });
      });
      bar();
      refresh();
      window.addEventListener('resize', draw);
    }).catch(function () {
      note('The flag server is not answering: <code>python -m charkit preview serve</code>. This page works without it.');
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
