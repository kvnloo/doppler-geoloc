import json, sys, numpy as np, pandas as pd, scipy.ndimage as nd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from fit_doppler import spec, model
OUT = sys.argv[1]
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.facecolor': '#0c0c0a', 'figure.facecolor': '#0c0c0a',
                     'axes.edgecolor': '#555', 'text.color': '#ddd', 'axes.labelcolor': '#ddd', 'xtick.color': '#aaa', 'ytick.color': '#aaa'})
ev = {}
for k, (t0, t1) in {'e1': (2040, 2270), 'e2': (2960, 3190)}.items():
    z = np.load(f'track_{k}.npz'); p = z['p']; f0, v, d, tc = p
    f, t, S = spec(t0, t1, nper=4096)
    lo, hi = f0 / (1 + v / 343) - 25, f0 / (1 - v / 343) + 25
    m = (f > lo) & (f < hi)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
    for a, title in zip(ax, ('spectrogram (whitened)', 'fitted Doppler model')):
        a.pcolormesh(t - tc, f[m], S[m], vmin=0, vmax=14, cmap='magma', shading='auto', rasterized=True)
        a.set_xlabel('seconds from closest approach (heard)'); a.set_title(title, color='#ddd')
    ax[0].set_ylabel('Hz')
    ax[1].plot(z['tt'] - tc, z['ff'], '.', color='#5ef', ms=1.2, alpha=.5)
    tt = np.linspace(t0, t1, 800); ax[1].plot(tt - tc, model(tt, *p), '-', color='#ffd166', lw=1.4)
    plt.tight_layout(); plt.savefig(f'{OUT}/{k}.png', dpi=90); plt.close()
    rms = float(np.sqrt(np.mean((model(z['tt'], *p) - z['ff']) ** 2)))
    ev[k] = dict(f0_hz=round(float(f0), 2), speed_ms=round(float(v), 1), cpa_slant_m=round(float(d)),
                 heard_cpa_s=round(float(tc), 2), rms_hz=round(rms, 2), n_points=int(len(z['tt'])),
                 f_approach_hz=round(float(f0 / (1 - v / 343)), 1), f_recede_hz=round(float(f0 / (1 + v / 343)), 1))
# overview strip
f, t, S = spec(1800, 3300, nper=2048); m = (f > 60) & (f < 260)
fig = plt.figure(figsize=(13, 3.4)); plt.pcolormesh(t, f[m], S[m], vmin=0, vmax=12, cmap='magma', shading='auto', rasterized=True)
for k in ev: plt.axvline(ev[k]['heard_cpa_s'], color='#5ef', lw=.8, ls='--')
plt.xlabel('seconds into recording'); plt.ylabel('Hz'); plt.tight_layout(); plt.savefig(f'{OUT}/overview.png', dpi=80); plt.close()

S5 = pd.read_parquet('stage5_scores.parquet')
top = S5.drop_duplicates(['icao1', 'icao2']).head(25)
cands = [dict(rank=int(r.rank5), lat=round(float(r.lat), 2), lon=round(float(r.lon), 2), score=round(float(r.energy), 2),
              lsq_rms_hz=round(float(r.rms_hz), 2)) for r in top.itertuples()]
near = S5[S5.km_to_town < 15].iloc[0]
data = dict(
    source=dict(article='https://www.ibtimes.co.uk/inaudible-aircraft-sounds-reveal-recording-location-1829800',
                video='https://www.youtube.com/watch?v=UytYrhYLOKI', recording='https://youtu.be/4CxVxuMVkMc',
                adsb='https://github.com/adsblol/globe_history_2026/releases/tag/v2026.09.08-planes-readsb-prod-0'),
    events=ev, gap_s=round(ev['e2']['heard_cpa_s'] - ev['e1']['heard_cpa_s'], 1), gap_colsto_s=920,
    funnel=[dict(stage='ADS-B points, non-jet, CONUS, <12k ft', n=26392809), dict(stage='aircraft', n=34284),
            dict(stage='cells that could hear event 2 (speed+distance)', n=220734578),
            dict(stage='…and event 1 ~917 s earlier', n=450749), dict(stage='…and silence in between', n=325378),
            dict(stage='scored with locked two-event Doppler fit', n=272115), dict(stage='re-scored on spectrogram', n=int(len(S5)))],
    colsto=dict(stage2=73000, stage3=15000),
    top_candidates=cands, top_scores=[c['score'] for c in cands[:5]],
    reported_area=dict(name='Oyster Bay, NY (as named in press)', best_rank=int(near.rank5), best_score=round(float(near.energy), 2)))
json.dump(data, open(f'{OUT}/results.json', 'w'), indent=1)
print(json.dumps({k: data[k] for k in ('events', 'gap_s', 'top_scores', 'reported_area')}, indent=1))
