import sys, json, numpy as np, scipy.signal as ss
C = 343.0
y = np.load('mono2k.npy'); FS = 2000.0

def spec(t0, t1, nper=2048):
    seg = y[int(t0 * FS):int(t1 * FS)]
    f, t, S = ss.spectrogram(seg, FS, nperseg=nper, noverlap=nper - 128)
    S = 10 * np.log10(S + 1e-20)
    S -= np.median(S, axis=1, keepdims=True)
    return f, t + t0, np.clip(S, 0, 20)

def model(t, f0, v, d, tc):
    """observed freq at reception times t; straight line, constant speed, CPA slant distance d, heard-CPA time tc"""
    tau = np.linspace(-400, 400, 4001)                 # emission time rel. to geometric CPA
    r = np.hypot(v * tau, d)
    trx = tau + r / C                                  # reception time rel. to geometric CPA
    vt = -v * v * tau / r                              # velocity toward observer
    fo = f0 / (1 - vt / C)
    return np.interp(t - tc + d / C, trx, fo)          # tc is the heard time of CPA (= geometric CPA + d/c)

def score(p, f, t, S, harm, win):
    f0, v, d, tc = p
    m = np.abs(t - tc) < win
    tot = 0
    for h in harm:
        fi = model(t[m], f0 * h, v, d, tc)
        idx = np.clip(np.round((fi - f[0]) / (f[1] - f[0])).astype(int), 0, len(f) - 1)
        tot += S[idx, np.nonzero(m)[0]].mean()
    return tot / len(harm)

def fit(t0, t1, tc_guess, fhi, flo, harm=(1,), win=50):
    f, t, S = spec(t0, t1)
    best = (-1, None)
    df = f[1] - f[0]
    f0s = np.arange(flo, fhi, 0.5)
    for v in np.arange(40, 151, 4):
        for d in np.geomspace(150, 6000, 30):
            for tc in np.arange(tc_guess - 20, tc_guess + 20.1, 1.0):
                m = np.abs(t - tc) < win; cols = np.nonzero(m)[0]
                g = model(t[m], 1.0, v, d, tc)                       # shape factor
                tot = 0
                for h in harm:
                    idx = np.clip(np.round((np.outer(f0s * h, g) - f[0]) / df).astype(int), 0, len(f) - 1)
                    tot = tot + S[idx, cols[None, :]].mean(1)
                k = int(np.argmax(tot)); s = tot[k] / len(harm)
                if s > best[0]: best = (s, (f0s[k], v, d, tc))
    # local refine
    s0, p = best
    step = np.array([0.5, 1.5, 0.08, 0.5])
    for _ in range(6):
        for _ in range(200):
            q = np.array(p) + np.random.randn(4) * step * np.r_[1, 1, p[2], 1]
            s = score(q, f, t, S, harm, win)
            if s > s0: s0, p = s, tuple(q)
        step /= 2
    return s0, p

if __name__ == '__main__':
    t0, t1, tcg, flo, fhi = map(float, sys.argv[1:6])
    s, (f0, v, d, tc) = fit(t0, t1, tcg, fhi, flo)
    s = float(s)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    f, t, S = spec(t0, t1); m = (f > flo * 0.6) & (f < fhi * 1.5)
    plt.figure(figsize=(16, 7)); plt.pcolormesh(t, f[m], S[m], vmin=0, vmax=15, cmap='magma', shading='auto')
    plt.plot(t, model(t, f0, v, d, tc), 'c--', lw=1, alpha=.6); plt.savefig(f'fit_{int(tcg)}.png', dpi=70)
    print(json.dumps(dict(score=round(s, 3), f0=round(f0, 2), v=round(v, 1), d=round(d), tc=round(tc, 2),
                          f_hi=round(f0 / (1 - v / C), 1), f_lo=round(f0 / (1 + v / C), 1))))
