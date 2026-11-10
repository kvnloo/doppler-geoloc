import json, numpy as np, pandas as pd, scipy.ndimage as nd
from search import ecef, elev, C, CFG
from fit_doppler import spec
import multiprocessing as mp
tr = pd.read_parquet('tracks_1s.parquet')
S = pd.read_parquet('stage4_scores.parquet')
S = S[np.isfinite(S.rms_hz)]
TOPN = 4000
lat0, lon0 = 40.872, -73.532                               # public town named in press (evaluation only)
dk = np.hypot((S.lat - lat0) * 111, (S.lon - lon0) * 111 * np.cos(np.radians(lat0)))
C5 = pd.concat([S.head(TOPN), S[dk < 15]]).drop_duplicates('cell').reset_index(drop=True)
TR = {k: g.sort_values('t') for k, g in tr[tr.icao.isin(set(C5.icao1) | set(C5.icao2))].groupby('icao')}
del tr
SP = {}
for k, ev in (('e1', CFG['e1']), ('e2', CFG['e2'])):
    f, t, Sx = spec(ev['tc'] - 170, ev['tc'] + 170, nper=4096)
    D = Sx - nd.median_filter(Sx, size=(1, 241)); D = nd.gaussian_filter(D, (1.5, 2))
    SP[k] = (f, t, np.clip(D, -2, 10))

def curve(icao, T, g):
    q = TR[icao]; q = q[(q.t > T - 260) & (q.t < T + 260)]
    if len(q) < 30: return None
    r = np.linalg.norm(ecef(q.lat.values, q.lon.values, q.alt.values) - g, axis=1)
    return q.t.values + r / C, 1 / (1 - (-np.gradient(r, q.t.values)) / C)

def ev_energy(c, k, T0, f0):
    f, t, D = SP[k]; trc, sh = c; ta = T0 + t
    m = (ta > trc.min()) & (ta < trc.max())
    if m.sum() < 0.8 * len(t): return -1
    fi = f0 * np.interp(ta[m], trc, sh)
    idx = np.clip(np.round((fi - f[0]) / (f[1] - f[0])).astype(int), 0, len(f) - 1)
    return D[idx, np.nonzero(m)[0]].mean()

def rescore(row):
    r = pd.Series(row[1:], index=C5.columns)
    g = ecef(np.array([r.lat]), np.array([r.lon]), elev(np.array([r.lat]), np.array([r.lon])) + 2)[0]
    c1, c2 = curve(r.icao1, r.T1, g), curve(r.icao2, r.T2, g)
    if c1 is None or c2 is None: return -1, None
    best = (-1, None)
    for dT in np.arange(-3, 3.01, 0.25):                     # shared (locked) offset
        e1 = max((ev_energy(c1, 'e1', r.T0 + dT, r.f01 + df), r.f01 + df) for df in np.arange(-1.5, 1.51, 0.25))
        e2 = max((ev_energy(c2, 'e2', r.T0 + dT, r.f02 + df), r.f02 + df) for df in np.arange(-1.5, 1.51, 0.25))
        s = e1[0] + e2[0]
        if s > best[0]: best = (s, (r.T0 + dT, e1[1], e2[1], e1[0], e2[0]))
    return best

with mp.get_context('fork').Pool(max(1, mp.cpu_count() - 4)) as pool:
    res = pool.map(rescore, list(C5.itertuples(name=None)), chunksize=20)
C5['energy'] = [x[0] for x in res]
C5['e1_energy'] = [x[1][3] if x[1] else np.nan for x in res]; C5['e2_energy'] = [x[1][4] if x[1] else np.nan for x in res]
C5['coarse_rank'] = C5.index + 1
C5 = C5.sort_values('energy', ascending=False).reset_index(drop=True); C5['rank5'] = C5.index + 1
C5['km_to_town'] = np.hypot((C5.lat - lat0) * 111, (C5.lon - lon0) * 111 * np.cos(np.radians(lat0)))
C5.to_parquet('stage5_scores.parquet')
cols = ['rank5', 'coarse_rank', 'lat', 'lon', 'icao1', 'icao2', 'energy', 'e1_energy', 'e2_energy', 'rms_hz', 'km_to_town']
print(C5.head(15)[cols].to_string())
print('--- best within 15 km of town ---'); print(C5[C5.km_to_town < 15].head(5)[cols].to_string())
print('distinct flight pairs in top 15:', C5.head(15)[['icao1', 'icao2']].drop_duplicates().shape[0])
