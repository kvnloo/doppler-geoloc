import json, numpy as np, pandas as pd
from scipy.spatial import cKDTree
from search import ecef, elev, cell_center, C, CFG
tr = pd.read_parquet('tracks_1s.parquet')
P = pd.read_parquet('stage2_pairs.parquet')
E = {k: {a: b for a, b in np.load(f'track_{k}.npz').items()} for k in ('e1', 'e2')}
tc1, tc2 = CFG['e1']['tc'], CFG['e2']['tc']

# ---- stage 3: silence between the two events ----
import os
def stage3(P):
    lat, lon = cell_center(P.cell.values); P['lat'], P['lon'] = lat, lon
    G = ecef(lat, lon, elev(lat, lon) + 2)
    lo, hi = P.T1.min() + 45, P.T2.max() - 45
    raw = pd.read_parquet('props_conus.parquet', columns=['icao', 't', 'lat', 'lon', 'alt', 'alt_geom'])
    raw['alt_m'] = np.where(raw.alt_geom.notna(), raw.alt_geom, raw.alt).astype(float) * 0.3048
    W = raw[(raw.t > lo - 30) & (raw.t < hi)].reset_index(drop=True)
    X = ecef(W.lat.values, W.lon.values, W.alt_m.values); tree = cKDTree(X)
    rad = CFG['silence_radius_m']; keep = np.ones(len(P), bool)
    for s0 in range(0, len(P), 20000):
        sl = slice(s0, s0 + 20000)
        for i, idx in zip(range(s0, min(s0 + 20000, len(P))), tree.query_ball_point(G[sl], rad, workers=-1)):
            if not idx: continue
            idx = np.array(idx); heard = W.t.values[idx] + np.linalg.norm(X[idx] - G[i], axis=1) / C
            if np.any((heard > P.T1.values[i] + 45) & (heard < P.T2.values[i] - 45)): keep[i] = False
    P3 = P[keep].reset_index(drop=True); P3.to_parquet('stage3_pairs.parquet')
    print('stage3 survivors', len(P3), 'cells', P3.cell.nunique(), flush=True)
    del raw, W, X, tree; import gc; gc.collect()

    return P3

if os.path.exists('stage3_pairs.parquet'):
    P3 = pd.read_parquet('stage3_pairs.parquet'); print('stage3 (cached)', len(P3), flush=True)
else:
    P3 = stage3(P)

# ---- stage 4: locked two-event Doppler scoring ----
TR = {k: g.sort_values('t') for k, g in tr[tr.icao.isin(set(P3.icao1) | set(P3.icao2))].groupby('icao')}
def curve(icao, T, g):
    q = TR[icao]; q = q[(q.t > T - 200) & (q.t < T + 200)]
    if len(q) < 30: return None
    Pq = ecef(q.lat.values, q.lon.values, q.alt.values); r = np.linalg.norm(Pq - g, axis=1)
    vt = -np.gradient(r, q.t.values)
    return q.t.values + r / C, 1 / (1 - vt / C)           # reception time, f/f0 shape

def score(icao1, icao2, T1, T2, g):
    c1, c2 = curve(icao1, T1, g), curve(icao2, T2, g)
    if c1 is None or c2 is None: return np.inf, None
    base = ((T1 - tc1) + (T2 - tc2)) / 2; best = (np.inf, None)
    for T0 in np.arange(base - 15, base + 15, 0.5):
        tot = 0; f0s = []
        for (trc, sh), e in ((c1, E['e1']), (c2, E['e2'])):
            ta = T0 + e['tt']
            if ta.min() < trc.min() or ta.max() > trc.max(): tot = np.inf; break
            s = np.interp(ta, trc, sh); w = e['ww']
            f0 = np.sum(w * s * e['ff']) / np.sum(w * s * s); f0s.append(f0)
            tot += np.sum(w * (f0 * s - e['ff']) ** 2) / np.sum(w)
        if tot < best[0]: best = (tot, (T0, *f0s))
    return np.sqrt(best[0] / 2), best[1]

def score_row(r):
    g = ecef(np.array([r[1]]), np.array([r[2]]), elev(np.array([r[1]]), np.array([r[2]])) + 2)[0]
    s, p = score(r[3], r[4], r[5], r[6], g)
    return (*r, s, *(p or (None,) * 3))

import multiprocessing as mp
items = list(zip(P3.cell, P3.lat, P3.lon, P3.icao1, P3.icao2, P3.T1, P3.T2))
with mp.get_context('fork').Pool(max(1, mp.cpu_count() - 4)) as pool:
    rows = pool.map(score_row, items, chunksize=200)
S = pd.DataFrame(rows, columns=['cell', 'lat', 'lon', 'icao1', 'icao2', 'T1', 'T2', 'rms_hz', 'T0', 'f01', 'f02']).sort_values('rms_hz')
S.to_parquet('stage4_scores.parquet')
print(S.head(15).to_string())

# ---- refinement around top distinct flight pairs ----
ref = []
top = S.drop_duplicates(['icao1', 'icao2']).head(5)
for r in top.itertuples():
    best = (np.inf, None)
    for dy in np.arange(-500, 501, 25):
        for dx in np.arange(-500, 501, 25):
            la = r.lat + dy / 111195.0; lo_ = r.lon + dx / (111195.0 * np.cos(np.radians(r.lat)))
            g = ecef(np.array([la]), np.array([lo_]), elev(np.array([la]), np.array([lo_])) + 2)[0]
            s, p = score(r.icao1, r.icao2, r.T1, r.T2, g)
            if s < best[0]: best = (s, (la, lo_, p))
    ref.append(dict(icao1=r.icao1, icao2=r.icao2, coarse_rms=float(r.rms_hz), rms=float(best[0]),
                    lat=best[1][0], lon=best[1][1], T0=float(best[1][2][0]), f01=float(best[1][2][1]), f02=float(best[1][2][2])))
    print(ref[-1], flush=True)
json.dump(ref, open('refined.json', 'w'), indent=1)
