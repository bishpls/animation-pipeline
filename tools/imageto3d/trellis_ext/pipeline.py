"""Box side: TRELLIS.2 image-to-3D run in stages, wrapping the upstream pipeline without editing it.

    run(pipe, [img, ...], seed=1, pipeline_type='1024_cascade', texture=True, mv_mode='multidiffusion')
      -> dict(mesh, fields, res, views, timings)

* Multi-view conditioning. TRELLIS.2 (unlike TRELLIS v1's run_multi_image) takes one image. With several images of the
  same object (a turnaround: front, three-quarter, side, back) we condition one sample on all of them the way v1 did,
  inside each flow sampler (sparse structure, shape, texture):
    'stochastic'      (default) one view per step, cycling from the first (same cost as one image)
    'multidiffusion'  every step, the (weighted) mean of the model's predictions under each view's condition, then
                      classifier-free guidance against the unconditional one (V+1 model calls a step where guidance is
                      on, V where it's off); with `mv_rescale` the averaged clean-sample prediction keeps the views' std
  The views carry no camera: the model infers each image's pose, as in v1. The first image is the primary (use it for
  the front); `mv_stages` limits multi-view to some stages (the others use the first image only).
* Stages timed (cuda-synchronised) and VRAM measured two ways (torch's allocator peak, and the device-wide peak polled
  from cudaMemGetInfo, which also sees CuMesh's and nvdiffrast's own allocations).
* The texture stage is optional (texture=False: structure + shape only, and the fields have no colours).
* The decoded fields are kept: the shape decoder's per-voxel dual vertices, edge-crossing logits and split weights, and
  the texture decoder's per-voxel PBR attributes on the same voxels (trellis_ext.field writes and reads them).
"""
import contextlib
import threading
import time
import numpy as np
import torch
import torch.nn.functional as F

AABB = [[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]]
STAGES = {'ss': 'sparse_structure_sampler', 'shape': 'shape_slat_sampler', 'tex': 'tex_slat_sampler'}


class VramPeak:
    """peak GPU memory over a block. torch_gb: torch's allocator; device_gb: the whole device (the CUDA context, torch's
    cache, and allocations torch doesn't see), polled every `dt` seconds."""

    def __init__(self, dt=0.02):
        self.dt = dt

    def __enter__(self):
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        self._dev = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return self

    def _poll(self):
        free, total = torch.cuda.mem_get_info()
        self._dev = max(self._dev, total - free)

    def _loop(self):
        while not self._stop.is_set():
            self._poll()
            time.sleep(self.dt)

    def __exit__(self, *exc):
        torch.cuda.synchronize()
        self._stop.set()
        self._t.join()
        self._poll()
        self.torch_gb = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        self.device_gb = round(self._dev / 1e9, 2)


class Clock:
    """named stage timings (seconds, cuda-synchronised); `with clk('shape'): ...`"""

    def __init__(self):
        self.t = {}

    @contextlib.contextmanager
    def __call__(self, name):
        torch.cuda.synchronize()
        t0 = time.time()
        yield
        torch.cuda.synchronize()
        self.t[name] = round(self.t.get(name, 0.0) + time.time() - t0, 2)


def _f(a):
    return a.feats if hasattr(a, 'feats') else a


class MultiViewModel:
    """a flow model driven by V view conditions (the rows of `cond`) for one sample. The sampler calls it like the model;
    the positive condition is recognised by identity (the sampler passes the tensor through untouched), the negative
    (unconditional, zeros) one is cut to one row. `rescale` (multidiffusion): the averaged clean-sample prediction is
    scaled back to the views' mean standard deviation each step, like CFG-rescale. Without it the texture stage came out
    as a near-black mask on Clawd's head (front + three-quarter), even with only the shape stages multi-view; with it the
    texture is as clean as single view (charkit/out/i3d/ext/compare_multiview.png). The final latents' std is about the
    same either way (0.92), so the difference is in the trajectory, not the endpoint's scale."""

    def __init__(self, model, cond, mode='multidiffusion', weights=None, rescale=True, sigma_min=1e-5):
        self.model, self.cond, self.mode = model, cond, mode
        self.rescale, self.sigma_min = rescale, sigma_min
        self.V = int(cond.shape[0])
        w = np.ones(self.V) if weights is None else np.asarray(weights, float)[:self.V]
        self.w = (w / w.sum()).tolist()
        self.step = 0

    def __call__(self, x, t, cond, **kw):
        if cond is not self.cond:
            return self.model(x, t, cond[:1], **kw)
        if self.mode == 'first' or self.V == 1:
            return self.model(x, t, cond[:1], **kw)
        if self.mode == 'stochastic':
            i = self.step % self.V
            self.step += 1
            return self.model(x, t, cond[i:i + 1], **kw)
        if self.mode != 'multidiffusion':
            raise ValueError(f'unknown multi-view mode {self.mode!r}')
        preds = [self.model(x, t, cond[i:i + 1], **kw) for i in range(self.V)]
        self.step += 1
        if not self.rescale:
            out = preds[0] * self.w[0]
            for p, w in zip(preds[1:], self.w[1:]):
                out = out + p * w
            return out
        sm = self.sigma_min
        sig = sm + (1 - sm) * float(t.flatten()[0]) / 1000                  # the sampler passes 1000 t
        x0s = [x * (1 - sm) - p * sig for p in preds]
        x0 = x0s[0] * self.w[0]
        for a, w in zip(x0s[1:], self.w[1:]):
            x0 = x0 + a * w
        target = sum(float(_f(a).float().std()) * w for a, w in zip(x0s, self.w))
        x0 = x0 * (target / max(float(_f(x0).float().std()), 1e-8))
        return (x * (1 - sm) - x0) / sig


@contextlib.contextmanager
def multiview(pipe, mode='stochastic', weights=None, stages=('ss', 'shape', 'tex'), rescale=True):
    """inside, the pipeline's three samplers accept a condition batch of V views for one sample."""
    patched = []
    for key, attr in STAGES.items():
        s = getattr(pipe, attr)
        m = mode if key in stages else 'first'

        def sample(model, noise, *a, _orig=s.sample, _m=m, _s=s, **kw):
            c = kw.get('cond')
            if torch.is_tensor(c) and c.shape[0] > 1:
                model = MultiViewModel(model, c, _m, weights, rescale, getattr(_s, 'sigma_min', 1e-5))
            return _orig(model, noise, *a, **kw)
        s.sample = sample
        patched.append(s)
    try:
        yield
    finally:
        for s in patched:
            del s.sample


def decode_shape(pipe, slat, res):
    """the shape decoder, keeping its per-voxel outputs (upstream's FlexiDualGridVaeDecoder.forward, eval branch, with
    the fields returned). -> (Mesh after fill_holes, fields dict of numpy arrays (quantised as trellis_ext.field reads
    them), subs for the texture decoder, voxel coords tensor)."""
    from trellis2.models.sc_vaes.sparse_unet_vae import SparseUnetVaeDecoder
    from trellis2.representations import Mesh
    from o_voxel.convert import flexible_dual_grid_to_mesh
    dec = pipe.models['shape_slat_decoder']
    dec.set_resolution(res)
    if pipe.low_vram:
        dec.to(pipe.device)
        dec.low_vram = True
    h, subs = SparseUnetVaeDecoder.forward(dec, slat, return_subs=True)
    if pipe.low_vram:
        dec.cpu()
        dec.low_vram = False
    assert int(h.coords[:, 0].max()) == 0, 'one sample at a time'
    f = h.feats.float()
    m = dec.voxel_margin
    dual = (1 + 2 * m) * torch.sigmoid(f[:, 0:3]) - m
    edge_logit = f[:, 3:6]
    split = F.softplus(f[:, 6:7])
    coords = h.coords[:, 1:].contiguous()
    v, fc = flexible_dual_grid_to_mesh(coords, dual, edge_logit > 0, split, aabb=AABB, grid_size=res, train=False)
    mesh = Mesh(v, fc)
    mesh.fill_holes()
    fields = dict(
        res=np.int32(res), voxel_size=np.float32(1.0 / res), aabb=np.array(AABB, np.float32),
        coords=coords.cpu().numpy().astype(np.uint16),
        # quantised as field.py reads them: dual -0.5..1.5 in 255 steps (the decoder's margin is 0.5), logits x10 as int8
        dual=(((dual + 0.5) / 2 * 255).round().clamp(0, 255).to(torch.uint8) if m == 0.5 else dual.half()).cpu().numpy(),
        edge_logit=(edge_logit * 10).round().clamp(-127, 127).to(torch.int8).cpu().numpy(),
        split=split[:, 0].clamp(max=6e4).cpu().numpy().astype(np.float16),
    )
    return mesh, fields, subs, coords


def align_attrs(coords, tex, res):
    """the texture decoder's per-voxel features on the shape decoder's voxels (same subdivision, so normally identical;
    matched by voxel index otherwise). -> (N, C) float tensor, bool mask of matched voxels."""
    tc = tex.coords[:, 1:]
    if tc.shape == coords.shape and torch.equal(tc, coords):
        return tex.feats.float(), None
    def key(c):
        c = c.long()
        return (c[:, 0] * res + c[:, 1]) * res + c[:, 2]
    ks, order = torch.sort(key(tc))
    kq = key(coords)
    pos = torch.searchsorted(ks, kq).clamp(max=len(ks) - 1)
    hit = ks[pos] == kq
    out = torch.zeros(len(coords), tex.feats.shape[1], device=tex.feats.device)
    out[hit] = tex.feats[order[pos[hit]]].float()
    return out, hit


@torch.no_grad()
def run(pipe, images, seed=1, pipeline_type='1024_cascade', texture=True, mv_mode='stochastic', mv_weights=None,
        mv_stages=('ss', 'shape', 'tex'), mv_rescale=True, max_num_tokens=49152, params=None, preprocess=True):
    """one sample from one or more images (PIL). -> dict(mesh: MeshWithVoxel (texture) or Mesh, fields: numpy arrays for
    trellis_ext.field.save, res, views: the preprocessed condition images, timings: seconds per stage)."""
    from trellis2.representations import MeshWithVoxel
    params = params or {}
    M = pipe.models
    clk = Clock()
    with clk('preprocess'):
        views = [pipe.preprocess_image(im) if preprocess else im for im in images]
    torch.manual_seed(seed)
    with clk('cond'):
        cond_512 = pipe.get_cond(views, 512)
        cond_1024 = pipe.get_cond(views, 1024) if pipeline_type != '512' else None
    ss_res = {'512': 32, '1024': 64, '1024_cascade': 32, '1536_cascade': 32}[pipeline_type]
    with multiview(pipe, mv_mode, mv_weights, mv_stages, mv_rescale):
        with clk('structure'):
            ss_coords = pipe.sample_sparse_structure(cond_512, ss_res, 1, params.get('ss', {}))
        with clk('shape'):
            if pipeline_type == '512':
                shape_slat = pipe.sample_shape_slat(cond_512, M['shape_slat_flow_model_512'], ss_coords,
                                                    params.get('shape', {}))
                res = 512
            elif pipeline_type == '1024':
                shape_slat = pipe.sample_shape_slat(cond_1024, M['shape_slat_flow_model_1024'], ss_coords,
                                                    params.get('shape', {}))
                res = 1024
            else:
                hi = 1024 if pipeline_type == '1024_cascade' else 1536
                shape_slat, res = pipe.sample_shape_slat_cascade(
                    cond_512, cond_1024, M['shape_slat_flow_model_512'], M['shape_slat_flow_model_1024'], 512, hi,
                    ss_coords, params.get('shape', {}), max_num_tokens)
        tex_slat = None
        if texture:
            with clk('texture'):
                tm, tc = ((M['tex_slat_flow_model_512'], cond_512) if pipeline_type == '512'
                          else (M['tex_slat_flow_model_1024'], cond_1024))
                tex_slat = pipe.sample_tex_slat(tc, tm, shape_slat, params.get('tex', {}))
    stats = dict(shape_latent_std=_latent_std(shape_slat, pipe.shape_slat_normalization))
    if tex_slat is not None:
        stats['tex_latent_std'] = _latent_std(tex_slat, pipe.tex_slat_normalization)
    torch.cuda.empty_cache()
    with clk('decode_shape'):
        mesh, fields, subs, coords = decode_shape(pipe, shape_slat, res)
    if texture:
        with clk('decode_texture'):
            tex = pipe.decode_tex_slat(tex_slat, subs)
            a, hit = align_attrs(coords, tex, res)
            a8 = (a.clamp(0, 1) * 255).round().to(torch.uint8).cpu().numpy()
            L = pipe.pbr_attr_layout
            fields.update(base_color=a8[:, L['base_color']], metallic=a8[:, L['metallic']][:, 0],
                          roughness=a8[:, L['roughness']][:, 0], alpha=a8[:, L['alpha']][:, 0])
            if hit is not None:
                fields['attr_matched'] = hit.cpu().numpy()
            mesh = MeshWithVoxel(mesh.vertices, mesh.faces, origin=AABB[0], voxel_size=1 / res,
                                 coords=tex.coords[:, 1:], attrs=tex.feats,
                                 voxel_shape=torch.Size([*tex.shape, *tex.spatial_shape]), layout=L)
    fields['ss_coords'] = ss_coords[:, 1:].cpu().numpy().astype(np.uint8)
    fields['ss_res'] = np.int32(ss_res)
    return dict(mesh=mesh, fields=fields, res=int(res), views=views, timings=clk.t, stats=stats)


def _latent_std(slat, norm):
    """the std of a latent in the flow's normalised space (about 1 when the sample is in distribution)."""
    std = torch.tensor(norm['std'])[None].to(slat.device)
    mean = torch.tensor(norm['mean'])[None].to(slat.device)
    return round(float(((slat.feats - mean) / std).std()), 3)
