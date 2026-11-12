# reuse-checked: site_assets_v2.py (static hero_e1.jpg crop) -- the live hero needs the raw whitened
# spectrogram as a small greyscale data texture plus the fitted curve as numbers, so the page can
# draw the real ridge being "heard" in sync with an animated flyover. Uses fit_doppler.spec/model.
import json, sys, numpy as np
from PIL import Image
from fit_doppler import spec, model
OUT = sys.argv[1]
z = np.load('track_e1.npz'); f0, v, d, tc = map(float, z['p'])
W = 70
f, t, S = spec(tc - W, tc + W, nper=4096)
m = (f > 60) & (f < 220)
S = S[m][::-1]                                  # low frequency at the bottom
img = Image.fromarray(np.uint8(np.clip((S - 1) / 11, 0, 1) ** 0.8 * 255)).resize((700, 240), Image.LANCZOS)
img.save(f'{OUT}/hero_spec.png', optimize=True)
tt = np.linspace(tc - W, tc + W, 281)
json.dump({'event': 'e1', 'f0': round(f0, 2), 'v': round(v, 1), 'd': round(d), 'window_s': W,
           'f_lo': 60, 'f_hi': 220, 'curve_hz': [round(float(x), 2) for x in model(tt, f0, v, d, tc)]},
          open(f'{OUT}/hero_curve.json', 'w'))
print('ok', img.size, f0, v, d)
