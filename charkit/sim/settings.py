"""The cloth solver's settings from a style profile (charkit/styles: the `physics` section, declared ahead of the
solvers). Physics is the baseline; every departure is a named, deterministic dial (docs/CHARKIT_HANDOFF.md, "Production
principles": liberties are dials, tuned in code).

The profile's physics keys and what they mean here:
  gravity          gravity scale (1: g = 9.81 m/s2)
  cloth_stiffness  bending stiffness as a textile bending length c = cloth_stiffness * BEND_LENGTH_MAX (L): the
                   flexural rigidity B = rho g c^3 (Peirce's cantilever: a strip overhanging 2c droops 41.5 deg;
                   test_sim.test_bending_length_is_peirces checks the solver means it)
  cloth_damping    velocity damping, cloth_damping * DAMP_MAX (1/s)
  hold_shape       the anime dial: each vertex held toward its template (drawn) position carried by the rig, as a spring
                   under which it would sag (1 - hold) / hold * HOLD_SAG (L) under its own weight. 0: pure physics
Dials with no profile key yet (DIALS, all at their physical value; a profile's physics section may set them by name):
  hang             hang time: gravity scaled by (1 - hang) while a vertex rises (cloth that floats up and falls late)
  mu_s, mu_k       static and kinetic friction against the body
  stretch          stretch compliance (m/N): 0 inextensible
  regions          {region: bending-length multiplier} (stiffness per region; the caller labels vertices)
  substeps         substeps per frame (small steps: one constraint pass each)
  iterations       constraint passes per substep, the multipliers accumulated (a rest drape: few substeps, many
                   passes, which converges to the equilibrium; motion: many substeps, one pass)
  density          area density (kg/m2); cancels against gravity in the bending and hold mappings
  tethers          long-range attachments to the pins (no stretch past the rest distance along the cloth)
"""
from .. import styles

BEND_LENGTH_MAX = 0.5          # L: cloth_stiffness 1 -> a bending length of half a head
DAMP_MAX = 10.0                # 1/s at cloth_damping 1
HOLD_SAG = 0.1                 # L: the sag scale of the hold spring
G = 9.81                       # m/s2
BEND_K = 0.5                   # the discrete hinge's constant: Peirce's cantilever (overhang 2c) droops 42.8 deg at h 0.08 c, 43.8 at 0.053 c (Peirce 42.9)
DIALS = dict(hang=0.0, mu_s=0.4, mu_k=0.3, stretch=0.0, regions={}, substeps=30, iterations=1, density=0.2, tethers=True)


def physics(style='anime', **over):
    """the profile's physics section with the solver's dials: -> dict."""
    S = styles.load(style) if isinstance(style, str) else style
    P = dict(DIALS)
    P.update(S.get('physics') or {})
    P.update(over)
    return P


def cloth(cloth_, style='anime', L=1.0, region_of=None, radius=0.0, **over):
    """the Solver settings for a Cloth in a style: per-hinge bending compliance, per-vertex hold compliance, gravity,
    damping, friction, substeps. L: the character's head length in the world's units (m). region_of: per vertex a region
    name (for `regions`). radius: the collision radius per vertex or scalar (m)."""
    import numpy as np
    P = physics(style, **over)
    g = G * float(P.get('gravity', 1.0))
    rho = float(P['density'])
    c = float(P['cloth_stiffness']) * BEND_LENGTH_MAX * L
    scale = np.ones(cloth_.n)
    if region_of is not None and P.get('regions'):
        for k, r in enumerate(region_of):
            scale[k] = float(P['regions'].get(r, 1.0))
    cl = c * scale[cloth_.H].mean(1) if len(cloth_.H) else np.zeros(0)
    B = rho * G * cl ** 3                                   # (flexural rigidity per hinge, N m)
    bend = np.where(B > 0, 1.0 / np.maximum(BEND_K * B * cloth_.hinge_weight, 1e-300), -1.0)
    hold = float(P.get('hold_shape', 0.0))
    if hold <= 0:
        a_hold = None
    elif hold >= 1:
        a_hold = np.zeros(cloth_.n)
    else:
        a_hold = (1 - hold) / hold * HOLD_SAG * L / (cloth_.mass * G)     # sag = m g alpha
    return dict(gravity=(0.0, 0.0, -g), substeps=int(P['substeps']), iterations=int(P['iterations']), stretch=float(P['stretch']), bend=bend,
                hold=a_hold, damping=float(P['cloth_damping']) * DAMP_MAX, hang=float(P['hang']),
                mu_s=float(P['mu_s']), mu_k=float(P['mu_k']), radius=radius, tethers=bool(P['tethers']), physics=P)
