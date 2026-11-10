import sys, json, numpy as np, scipy.signal as ss, scipy.ndimage as nd
from scipy.optimize import least_squares
from fit_doppler import spec, model, C

def track(f, t, S, t_seed, f_seed, span, tol=1.8):
    D = S - nd.median_filter(S, size=(1, 241))            # remove horizontal (stationary) lines, ~15 s
    D = nd.gaussian_filter(D, (1.5, 2))
    df = f[1] - f[0]; dt = t[1] - t[0]
    i0 = int(np.argmin(abs(t - t_seed)))
    pts = {}
    for direction in (1, -1):
        fi, slope, i = f_seed, 0.0, i0
        hist = []
        while abs(t[i] - t_seed) < span and 0 <= i + direction < len(t):
            pred = fi + slope * direction * dt
            lo, hi = int((pred - tol - f[0]) / df), int((pred + tol - f[0]) / df) + 1
            k = lo + int(np.argmax(D[lo:hi, i])); fk = f[k]
            if D[k, i] > 1.0:
                pts[t[i]] = (fk, D[k, i]); hist.append((t[i], fk))
                if len(hist) > 30:
                    a = np.polyfit([h[0] for h in hist[-30:]], [h[1] for h in hist[-30:]], 1); slope = a[0] * direction
                fi = fk
            else:
                fi = pred
            i += direction
    tt = np.array(sorted(pts)); ff = np.array([pts[x][0] for x in tt]); ww = np.array([pts[x][1] for x in tt])
    return tt, ff, ww, D

def fit_pts(tt, ff, ww, tc0):
    def res(p): return (model(tt, *p) - ff) * np.sqrt(ww)
    best = None
    for v0 in (50, 70, 90, 110):
        for d0 in (300, 800, 1500, 3000):
            r = least_squares(res, [np.median(ff), v0, d0, tc0], loss='soft_l1', f_scale=1.0,
                              bounds=([20, 20, 50, tc0 - 40], [500, 200, 15000, tc0 + 40]))
            if best is None or r.cost < best.cost: best = r
    J = best.jac; cov = np.linalg.pinv(J.T @ J) * (2 * best.cost / max(1, len(tt) - 4))
    return best.x, np.sqrt(np.diag(cov)), np.sqrt(np.mean((model(tt, *best.x) - ff) ** 2))

if __name__ == '__main__':
    t0, t1, ts, fs_, span, name = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
    f, t, S = spec(t0, t1, nper=4096)
    tt, ff, ww, D = track(f, t, S, ts, fs_, span)
    p, sd, rms = fit_pts(tt, ff, ww, ts)
    f0, v, d, tc = p
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    m = (f > ff.min() - 30) & (f < ff.max() + 30)
    fig, ax = plt.subplots(2, 1, figsize=(16, 12))
    for a, Z in zip(ax, (S, D)):
        a.pcolormesh(t, f[m], Z[m], vmin=0, vmax=12, cmap='magma', shading='auto')
    ax[1].plot(tt, ff, 'g.', ms=2); ax[1].plot(t, model(t, *p), 'c-', lw=1)
    plt.savefig(f'track_{name}.png', dpi=60)
    np.savez(f'track_{name}.npz', tt=tt, ff=ff, ww=ww, p=p)
    print(json.dumps(dict(n=len(tt), t_range=[round(tt.min(), 1), round(tt.max(), 1)], f0=round(f0, 2), v=round(v, 1), d=round(d),
                          tc=round(tc, 2), sd=[round(x, 2) for x in sd], rms_hz=round(rms, 2))))
