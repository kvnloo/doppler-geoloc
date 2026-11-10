# Pipeline

Run from a work directory. Each script reads and writes files in the current directory.

```bash
uv venv && uv pip install numpy scipy pandas pyarrow soundfile matplotlib pillow
yt-dlp -f bestaudio -x --audio-format wav -o 'full.%(ext)s' https://youtu.be/4CxVxuMVkMc
gh release download v2026.09.08-planes-readsb-prod-0 -R adsblol/globe_history_2026 -D adsb
curl -sL https://raw.githubusercontent.com/wiedehopf/tar1090-db/master/db/icao_aircraft_types.js | zcat > aircraft_types.txt
```

| # | script | does | output |
|---|---|---|---|
| 1 | `spec.py` | mono, decimate to 2 kHz, whitened spectrogram strips | `mono2k.npy`, `spec_*.png` |
| 2 | `zoom.py t0 t1 flo fhi nperseg out.png` | zoomed views to find curve seeds | png |
| 3 | `track_fit.py t0 t1 t_seed f_seed span name` | ridge-tracks one curve, least-squares fit (f0, v, d, tc) | `track_<name>.npz/png` |
| 4 | `extract_adsb.py` (`cat adsb/*.tar.* \| python extract_adsb.py`) | streams the tar, keeps non-jet CONUS points under 12k ft | `props_conus.parquet` |
| 5 | `dem.py` | CONUS terrain mosaic | `dem_conus.npz` |
| 6 | `search.py` | event-2 closest-approach loci on a 200 m grid, event-1 check by KD-tree, in 30-min blocks | `stage2_pairs.parquet` |
| 7 | `score.py` | silence filter, locked two-event Doppler least-squares, local refine | `stage3/4_*.parquet`, `refined.json` |
| 8 | `rescore.py` | top candidates rescored against spectrogram energy ±170 s | `stage5_scores.parquet` |
| 9 | `site_assets.py <docs/assets>` | figures + rounded `results.json` for the demo | |

`events.json` holds the per-event speed / distance windows and the time gap used by stages 6–8.

Seeds used for the published run: `track_fit.py 2030 2260 2135 140 45 e1` and `track_fit.py 2960 3180 3068 141 34 e2` (track tolerance 1.8 Hz).

Memory: stage 6 at full CONUS scale needs ~10 GB. Rasterize only the narrow event; never the wide one.
