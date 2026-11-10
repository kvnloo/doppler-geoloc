import numpy as np, soundfile as sf, scipy.signal as ss, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
x, sr = sf.read('full.wav'); x = x.mean(1)
y = ss.decimate(ss.decimate(x, 6), 4); fs = sr / 24          # 2 kHz
np.save('mono2k.npy', y.astype(np.float32))
f, t, S = ss.spectrogram(y, fs, nperseg=4096, noverlap=3072)
S = 10 * np.log10(S + 1e-20); S -= np.median(S, axis=1, keepdims=True)  # whiten stationary hum
np.savez_compressed('spec.npz', f=f, t=t, S=S.astype(np.float16))
for lo, hi, name in [(20, 400, 'a'), (400, 1000, 'b')]:
    m = (f >= lo) & (f <= hi)
    fig, axs = plt.subplots(6, 1, figsize=(22, 24))
    for k, ax in enumerate(axs):
        tm = (t >= k * 600) & (t < (k + 1) * 600)
        ax.pcolormesh(t[tm], f[m], S[m][:, tm], vmin=0, vmax=12, cmap='magma', shading='auto'); ax.set_ylabel('Hz')
    plt.tight_layout(); plt.savefig(f'spec_{name}.png', dpi=60)
print(S.shape, fs)
