import sys, tarfile, gzip, json, re, numpy as np, pandas as pd
types = json.loads(re.sub(r'^[^{]*', '', open('aircraft_types.txt').read()).rstrip(';\n '))
def desc_of(t):
    d = types.get(t or '')
    return (d.get('desc') if isinstance(d, dict) else d) or ''
rows = []; n = 0
tf = tarfile.open(fileobj=sys.stdin.buffer, mode='r|')
for m in tf:
    if not m.isfile() or 'trace_full' not in m.name: continue
    b = tf.extractfile(m).read(); n += 1
    if b[:2] == b'\x1f\x8b': b = gzip.decompress(b)
    d = json.loads(b); t = d.get('t'); desc = desc_of(t)
    if len(desc) == 3 and desc[2] == 'J': continue          # drop known jets
    ts0 = d['timestamp']
    for p in d['trace']:
        alt = p[3]
        if alt == 'ground' or alt is None or alt > 12000: continue
        lat, lon = p[1], p[2]
        if not (24 < lat < 50 and -125 < lon < -66): continue
        rows.append((d['icao'], t or '', desc, ts0 + p[0], lat, lon, alt, p[10] if len(p) > 10 else None, p[4], p[5], p[7]))
    if n % 20000 == 0: print(n, len(rows), file=sys.stderr, flush=True)
df = pd.DataFrame(rows, columns=['icao', 'type', 'desc', 't', 'lat', 'lon', 'alt', 'alt_geom', 'gs', 'track', 'vrate'])
df.to_parquet('props_conus.parquet'); print(n, len(df), df.icao.nunique())
