// engine/warp.js: draw a canvas (or image) through a deformed mesh (WebGL2), for paper that bends and cards that breathe.
//   WARP.draw(X, src, (u, v) => [x, y], { cols, rows, shade: (u, v) => k })
// (u, v) in 0..1 over the source; the function returns canvas px. `shade` (optional) multiplies the colour per vertex (1 = as is):
// a fold's highlight (> 1) and the dimming of paper turned from the light (< 1).
const WARP = (() => {
  let cv = null, gl = null, prog = null, tex = null, bufs = null;
  const VS = `#version 300 es
    in vec2 p; in vec2 uv; in float k; uniform vec2 res; out vec2 v; out float s;
    void main() { v = uv; s = k; gl_Position = vec4(p.x / res.x * 2. - 1., 1. - p.y / res.y * 2., 0, 1); }`;
  const FS = `#version 300 es
    precision highp float; in vec2 v; in float s; uniform sampler2D t; out vec4 o;
    void main() { vec4 c = texture(t, v); o = vec4(min(c.rgb * s, vec3(1.)), c.a); }`;
  function init(w, h) {
    if (!cv) {
      cv = document.createElement('canvas'); gl = cv.getContext('webgl2', { premultipliedAlpha: false, antialias: true, preserveDrawingBuffer: true });
      const sh = (ty, src) => { const s = gl.createShader(ty); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw gl.getShaderInfoLog(s); return s; };
      prog = gl.createProgram(); gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog);
      tex = gl.createTexture(); bufs = { p: gl.createBuffer(), uv: gl.createBuffer(), k: gl.createBuffer(), i: gl.createBuffer() };
    }
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    gl.viewport(0, 0, w, h); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); gl.useProgram(prog);
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.uniform2f(gl.getUniformLocation(prog, 'res'), w, h);
  }
  function draw(X, src, f, o = {}) {
    const W = X.canvas.width, H = X.canvas.height, C = o.cols || 48, R = o.rows || 36; init(W, H);
    gl.bindTexture(gl.TEXTURE_2D, tex); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, src);
    gl.generateMipmap(gl.TEXTURE_2D); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const P = [], UV = [], K = [], I = [];
    for (let j = 0; j <= R; j++) for (let i = 0; i <= C; i++) { const u = i / C, v = j / R, [x, y] = f(u, v); P.push(x, y); UV.push(u, v); K.push(o.shade ? o.shade(u, v) : 1); }
    for (let j = 0; j < R; j++) for (let i = 0; i < C; i++) { const a = j * (C + 1) + i, b = a + 1, c = a + C + 1, d = c + 1; I.push(a, b, c, b, d, c); }
    const att = (name, buf, data, n) => { const l = gl.getAttribLocation(prog, name); gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.DYNAMIC_DRAW); gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, n, gl.FLOAT, false, 0, 0); };
    att('p', bufs.p, P, 2); att('uv', bufs.uv, UV, 2); att('k', bufs.k, K, 1);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, bufs.i); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array(I), gl.DYNAMIC_DRAW);
    gl.drawElements(gl.TRIANGLES, I.length, gl.UNSIGNED_INT, 0);
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.drawImage(cv, 0, 0); X.restore();
  }
  return { draw };
})();
