"""motion quality (Michael: "bottom strands are very straightforwardly jerky"): rest stability (tip speed before the
move), high-frequency jitter (tips off their 5-frame average), tip speed p95."""
import sys, os, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.expanduser('~/animation-pipeline-3d'))
import clip


def jitter(bdir):
    A = np.load(os.path.join(bdir, 'arrays.npz')); M = json.load(open(os.path.join(bdir, 'bundle.json')))
    rig = clip.build_rig(A, M); clip.collider(A, M); clip.radial_collider(A, M)
    sim = clip.simulate(rig, 72)
    D = np.array([d for (_, _, _, d) in sim]); tip = D[:, :, -1]
    vel = np.linalg.norm(np.diff(tip, axis=0), axis=2) * 100
    from scipy.signal import savgol_filter
    hf = []
    for c in range(tip.shape[1]):
        x = tip[:, c]; sm = savgol_filter(x, 7, 3, axis=0)
        hf.append(np.linalg.norm(x[3:-3] - sm[3:-3], axis=1).mean() * 100)
    # spectral: the share of each tip's motion power above 6 Hz (real swing lives below; buzz above)
    F = np.fft.rfftfreq(tip.shape[0], 1 / 24.0)
    hfs = []
    for c in range(tip.shape[1]):
        x = tip[:, c] - tip[:, c].mean(0)
        Pw = (np.abs(np.fft.rfft(x * np.hanning(len(x))[:, None], axis=0)) ** 2).sum(1)
        hfs.append(Pw[F > 6].sum() / max(Pw[F > 0.3].sum(), 1e-18))
    return dict(hf_share=round(float(np.mean(hfs)), 4), hf_share_max=round(float(np.max(hfs)), 4), rest_speed=round(float(vel[:10].max()), 3), jitter_mean=round(float(np.mean(hf)), 3),
                jitter_max=round(float(np.max(hf)), 3), speed_p95=round(float(np.percentile(vel, 95)), 2))


if __name__ == '__main__':
    print(json.dumps(jitter(sys.argv[1])))
