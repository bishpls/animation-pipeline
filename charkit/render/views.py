"""The board cameras and each view's look, in the glTF frame, as Blender renders the boards (no Blender needed).

The views mirror charkit.scene.boards (its 'views' and 'body' sets) and the camera charkit.qa._aim puts there: azimuth
az degrees round her (0 in front, + toward her left), `dist` out and `height` up from the target, lens mm on a 36 mm
sensor fitted to the picture's longer side, or orthographic with its scale on the longer side. The look per view is
charkit.shade's own (imported, not copied): view_light (a camera key turns with the camera) and line_width (screen lines:
frac of the picture's height at the view's metres per pixel, times the region's factor).

    from charkit.render import views
    V = views.board_views(M, which=('views', 'body'), eye_z=..., L=...)   # [BoardView], as scene.boards renders them
    cam = views.camera(V[0])                                             # view / projection matrices, m_per_px, light
"""
import math
from dataclasses import dataclass

import numpy as np

from .model import C3, to_gltf

SENSOR = 36.0                          # mm, Blender's default sensor width, fitted to the longer side (AUTO)
NEAR, FAR = 0.05, 100.0
BG = (0.86, 0.86, 0.90)                # charkit.scene.reset's world colour (linear), the boards' background


@dataclass
class BoardView:
    name: str                          # face_000, body_035, ...
    target: tuple                      # Blender world (x, y, z)
    az: float
    dist: float
    height: float
    res: tuple                         # (width, height) px
    lens: float = 50.0
    ortho: float = None
    features: bool = False             # the features laid through the hair (qa.features_through), as scene.boards does


def board_views(M, which=('views', 'body'), eye_z=None, L=None, height_m=None, covers=True):
    """scene.boards' views for a model: 'views' (the head at 0, 30, 60, 90, 150 degrees, 900 x 900, 85 mm, the features
    through the hair when there are covers) and 'body' (0, 35, 90, 180 degrees, 600 x 1000, orthographic).
    eye_z, L: the head's (charkit.bundle's assembly meta; default the export's head centre and length). height_m: the
    spec's body height (default the export's `height`, else 1.6)."""
    hd = M.head
    if L is None:
        L = float(hd['L'])
    if eye_z is None:
        eye_z = float(hd['centre'][1])             # glTF y = Blender z (the head centre: charkit.bundle's eye_z on code heads)
    H = float(height_m if height_m is not None else M.root.get('height', 1.6))
    out = []
    if 'views' in which:
        for az in (0, 30, 60, 90, 150):
            out.append(BoardView(f'face_{az:03d}', (0.0, 0.0, eye_z + 0.06 * L), az, 1.0, 0.0, (900, 900), lens=85,
                                 features=covers))
    if 'body' in which:
        for az in (0, 35, 90, 180):
            out.append(BoardView(f'body_{az:03d}', (0.0, 0.0, H * 0.52), az, 6.0, 0.0, (600, 1000), ortho=H * 1.12))
    return out


@dataclass
class Camera:
    view: np.ndarray                   # 4x4 world -> view (glTF frame, camera looking down -z)
    proj: np.ndarray                   # 4x4 view -> clip (WebGPU: z in [0, 1])
    eye: np.ndarray                    # glTF
    back: np.ndarray                   # unit, toward the camera (for orthographic views)
    ortho: bool
    m_per_px: float                    # charkit.qa._aim's: metres per pixel at the target
    res: tuple

    @property
    def viewproj(self):
        return self.proj @ self.view


def camera(v):
    """BoardView -> Camera, as charkit.qa._aim places Blender's (eye = target + (sin az, -cos az) dist + height z)."""
    a = math.radians(v.az)
    tb = np.asarray(v.target, float)
    eye_b = tb + np.array([math.sin(a) * v.dist, -math.cos(a) * v.dist, v.height])
    t, e = to_gltf(tb), to_gltf(eye_b)
    f = t - e
    dist = np.linalg.norm(f)
    f = f / dist
    up = np.array([0.0, 1.0, 0.0])
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    Vm = np.eye(4)
    Vm[0, :3], Vm[1, :3], Vm[2, :3] = r, u, -f
    Vm[:3, 3] = -Vm[:3, :3] @ e
    W, H = v.res
    big = max(W, H)
    P = np.zeros((4, 4))
    if v.ortho:
        hx, hy = v.ortho / 2 * W / big, v.ortho / 2 * H / big
        P[0, 0], P[1, 1] = 1 / hx, 1 / hy
        P[2, 2], P[2, 3] = -1 / (FAR - NEAR), -NEAR / (FAR - NEAR)
        P[3, 3] = 1
        mpp = v.ortho / big
    else:
        tx = SENSOR / 2 / v.lens * W / big                      # tan of the half field of view, each axis
        ty = SENSOR / 2 / v.lens * H / big
        P[0, 0], P[1, 1] = 1 / tx, 1 / ty
        P[2, 2], P[2, 3] = FAR / (NEAR - FAR), NEAR * FAR / (NEAR - FAR)
        P[3, 2] = -1
        mpp = dist * SENSOR / v.lens / big
    return Camera(view=Vm, proj=P, eye=e, back=-f, ortho=bool(v.ortho), m_per_px=mpp, res=(W, H))


def look_of(M):
    """the look charkit.shade reads (light, lines) from the export's root, in shade's own terms (Blender frame)."""
    R = M.root
    lt = R.get('light') or {}
    light = {'mode': 'camera', 'key': list(lt['key'])} if lt.get('mode') == 'camera' and lt.get('key') else \
        {'dir': list(C3.T @ np.asarray(lt.get('direction', to_gltf([-0.45, -0.55, 0.70])), float))}
    look = {'light': light}
    if (R.get('lines') or {}).get('mode') == 'screen':
        look['lines'] = dict(R['lines'])
    return look


def view_light(M, v, look=None):
    """toward the key light for BoardView v, glTF frame (charkit.shade.view_light)."""
    from charkit import shade
    d = shade.view_light(v.az, look or look_of(M))
    return to_gltf(d)


def line_width(outline, cam, look):
    """an outline's width (m) in a view (charkit.shade.line_width: build width, or screen lines at this view's scale)."""
    from charkit import shade
    return shade.line_width({'ck_line_w': float(outline['width']), 'ck_line_region': outline.get('region', 'skin')},
                            cam.m_per_px, cam.res[1], look)
