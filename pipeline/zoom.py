import sys, numpy as np, scipy.signal as ss, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
y = np.load('mono2k.npy'); fs = 2000.0
t0, t1, flo, fhi, nper, out = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
seg = y[int(t0 * fs):int(t1 * fs)]
f, t, S = ss.spectrogram(seg, fs, nperseg=nper, noverlap=nper - nper // 16)
S = 10 * np.log10(S + 1e-20); S -= np.median(S, axis=1, keepdims=True)
m = (f >= flo) & (f <= fhi)
plt.figure(figsize=(20, 9)); plt.pcolormesh(t + t0, f[m], S[m], vmin=0, vmax=15, cmap='magma', shading='auto')
plt.grid(alpha=.3); plt.xlabel('s'); plt.ylabel('Hz'); plt.tight_layout(); plt.savefig(out, dpi=70)
