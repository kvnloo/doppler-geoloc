"""Stages: 1) per-event CPA loci from prop ADS-B (speed + slant-distance windows, DEM-corrected)
2) pair cells heard event1 then event2 dt seconds later  3) silence filter  4) locked two-event Doppler scoring."""
import json, math, sys, numpy as np, pandas as pd
from scipy.spatial import cKDTree
R = 6371000.0; C = 343.0; KT = 0.514444; FT = 0.3048
CFG = json.load(open('events.json'))
dem = np.load('dem_conus.npz'); DEM = dem['M']; Z = int(dem['Z']); X0 = int(dem['X0']); Y0 = int(dem['Y0'])

def elev(lat, lon):
    n = 2 ** Z
    px = ((lon + 180) / 360 * n - X0) * 256
    py = ((1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n - Y0) * 256
    e = DEM[np.clip(py.astype(int), 0, DEM.shape[0] - 1), np.clip(px.astype(int), 0, DEM.shape[1] - 1)]
    return np.maximum(e, 0).astype(np.float64)

def ecef(lat, lon, h):
    la, lo = np.radians(lat), np.radians(lon); r = R + h
    return np.stack([r * np.cos(la) * np.cos(lo), r * np.cos(la) * np.sin(lo), r * np.sin(la)], -1)

def load_tracks(step=1.0):
    df = pd.read_parquet('props_conus.parquet')
    df['alt_m'] = np.where(df.alt_geom.notna(), df.alt_geom, df.alt).astype(float) * FT
    df = df.sort_values(['icao', 't']).dropna(subset=['gs', 'track'])
    out = []
    fast = set(df.icao[df.gs * KT >= min(CFG['e1']['v'][0], CFG['e2']['v'][0]) - 5])
    df = df[df.icao.isin(fast)]
    for icao, g in df.groupby('icao', sort=False):
        t = g.t.values
        if len(t) < 5: continue
        seg = np.r_[0, np.cumsum(np.diff(t) > 60)]
        for s in np.unique(seg):
            m = seg == s
            if m.sum() < 5: continue
            tt = t[m]; ti = np.arange(tt[0], tt[-1], step)
            if len(ti) < 5: continue
            trk = np.degrees(np.unwrap(np.radians(g.track.values[m])))
            gs = np.interp(ti, tt, g.gs.values[m]) * KT
            k = gs >= min(CFG['e1']['v'][0], CFG['e2']['v'][0]) - 10       # keep only fast rows (memory)
            if k.sum() < 5: continue
            ti = ti[k]
            out.append(pd.DataFrame(dict(icao=icao, seg=s, t=ti,
                       lat=np.interp(ti, tt, g.lat.values[m]), lon=np.interp(ti, tt, g.lon.values[m]),
                       alt=np.interp(ti, tt, g.alt_m.values[m]).astype(np.float32), gs=gs[k].astype(np.float32),
                       trk=(np.interp(ti, tt, trk) % 360).astype(np.float32))))
    return pd.concat(out, ignore_index=True)

CELL = 200.0
M_PER_DEG = R * math.pi / 180
def cell_of(lat, lon):
    ci = np.round(lat * M_PER_DEG / CELL).astype(np.int64)
    cj = np.round(lon * M_PER_DEG * np.cos(np.radians(ci * CELL / M_PER_DEG)) / CELL).astype(np.int64)
    return ci * (1 << 32) + (cj + (1 << 31))

def cell_center(cell):
    ci = cell >> 32; cj = (cell & ((1 << 32) - 1)) - (1 << 31)
    lat = ci * CELL / M_PER_DEG
    return lat, cj * CELL / (M_PER_DEG * np.cos(np.radians(lat)))

def loci(tr, ev, chunk=200_000):
    """cells whose CPA to a qualifying flight point has slant distance in ev['d'] (perpendicular offsets)."""
    p = tr[(tr.gs >= ev['v'][0]) & (tr.gs <= ev['v'][1]) & (tr.alt < ev['d'][1])]
    offs = np.r_[np.arange(-ev['d'][1], 0, 100.0), np.arange(0, ev['d'][1] + 1, 100.0)]
    res = []
    for i in range(0, len(p), chunk):
        q = p.iloc[i:i + chunk]
        b = np.radians(q.trk.values + 90)[:, None]; x = offs[None, :]
        lat = q.lat.values[:, None] + np.degrees(x * np.cos(b) / R)
        lon = q.lon.values[:, None] + np.degrees(x * np.sin(b) / (R * np.cos(np.radians(q.lat.values[:, None]))))
        h = q.alt.values[:, None] - elev(lat, lon)
        d = np.sqrt(x ** 2 + h ** 2)
        ok = (d >= ev['d'][0]) & (d <= ev['d'][1]) & (h > 30)
        ii, jj = np.nonzero(ok)
        res.append(pd.DataFrame(dict(cell=cell_of(lat[ii, jj], lon[ii, jj]), icao=q.icao.values[ii],
                                     T=q.t.values[ii] + d[ii, jj] / C, d=d[ii, jj].astype(np.float32), v=q.gs.values[ii]))
                   .groupby(['cell', 'icao']).agg(T=('T', 'median'), d=('d', 'median'), v=('v', 'median')).reset_index())
    L = pd.concat(res, ignore_index=True)
    return L.groupby(['cell', 'icao']).agg(T=('T', 'median'), d=('d', 'median'), v=('v', 'median')).reset_index()

def e1_check(tr, L2, ev, DT, TOL, bucket=60.0):
    """for each E2 locus cell, find flights whose heard-CPA (slant d, speed v in ev ranges) is DT+-TOL s earlier."""
    p = tr[(tr.gs >= ev['v'][0]) & (tr.gs <= ev['v'][1]) & (tr.alt < ev['d'][1])].reset_index(drop=True)
    lat, lon = cell_center(L2.cell.values)
    G = ecef(lat, lon, elev(lat, lon) + 2)
    b = np.floor(L2['T'].values / bucket).astype(int); out = []
    pt = p.t.values
    for bk in np.unique(b):
        ci = np.nonzero(b == bk)[0]
        t_hi = (bk + 1) * bucket - DT + TOL; t_lo = bk * bucket - DT - TOL - ev['d'][1] / C - 60
        w = np.nonzero((pt >= t_lo) & (pt <= t_hi + 60))[0]
        if len(w) == 0: continue
        X = ecef(p.lat.values[w], p.lon.values[w], p.alt.values[w].astype(np.float64)); tree = cKDTree(X)
        hits = tree.query_ball_point(G[ci], ev['d'][1] * 1.05)
        rows_c, rows_p = [], []
        for k, h in enumerate(hits):
            if h: rows_c += [ci[k]] * len(h); rows_p += h
        if not rows_c: continue
        rc = np.array(rows_c); rp = np.array(rows_p)
        dist = np.linalg.norm(X[rp] - G[rc], axis=1)
        H = pd.DataFrame(dict(c=rc, pi=w[rp], icao=p.icao.values[w[rp]], dist=dist, heard=pt[w[rp]] + dist / C, v=p.gs.values[w[rp]]))
        H = H.loc[H.groupby(['c', 'icao']).dist.idxmin()]                 # CPA per (candidate, flight)
        H = H[(H.dist >= ev['d'][0]) & (H.dist <= ev['d'][1])]
        H = H[((L2['T'].values[H.c] - H.heard) - DT).abs() <= TOL]
        # true CPA: not at the edge of the time window of that flight's available fast points
        H = H[(pt[H.pi] > t_lo + 5) & (pt[H.pi] < t_hi + 55)]
        out.append(H)
    if not out: return pd.DataFrame(columns=['cell', 'icao1', 'T1', 'd1', 'v1', 'icao2', 'T2', 'd2', 'v2'])
    H = pd.concat(out, ignore_index=True)
    R2 = L2.iloc[H.c.values].reset_index(drop=True)
    return pd.DataFrame(dict(cell=R2.cell, icao1=H.icao.values, T1=H.heard.values, d1=H.dist.values, v1=H.v.values,
                             icao2=R2.icao, T2=R2['T'], d2=R2.d, v2=R2.v))

if __name__ == '__main__':
    import os
    if os.path.exists('tracks_1s.parquet'): tr = pd.read_parquet('tracks_1s.parquet')
    else: tr = load_tracks(); tr.to_parquet('tracks_1s.parquet')
    print('interp points', len(tr), 'flights', tr.icao.nunique(), flush=True)
    E1, E2, DT, TOL = CFG['e1'], CFG['e2'], CFG['dt'], CFG['dt_tol']
    parts = []; nl = 0
    for b0 in np.arange(np.floor(tr.t.min() / 1800) * 1800, tr.t.max(), 1800):   # 30-min blocks bound memory
        L2 = loci(tr[(tr.t >= b0) & (tr.t < b0 + 1800)], E2); nl += len(L2)
        if len(L2) == 0: continue
        Pb = e1_check(tr[(tr.t >= b0 - DT - 200) & (tr.t < b0 + 1800 - DT + 100)], L2, E1, DT, TOL)
        parts.append(Pb[Pb.icao1 != Pb.icao2])
        print(pd.Timestamp(b0, unit='s'), 'e2 loci', len(L2), 'pairs', len(parts[-1]), flush=True)
    P = pd.concat(parts, ignore_index=True)
    P.to_parquet('stage2_pairs.parquet')
    print('stage1 e2 loci total', nl, 'stage2 pairs', len(P), 'cells', P.cell.nunique(), flush=True)
