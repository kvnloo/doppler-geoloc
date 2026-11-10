# doppler-geoloc

Open recreation of [colsto's experiment](https://www.youtube.com/watch?v=UytYrhYLOKI) ([IBTimes write-up](https://www.ibtimes.co.uk/inaudible-aircraft-sounds-reveal-recording-location-1829800)): find inaudible propeller-plane Doppler curves in a recording, then match them against public ADS-B flight tracks to locate where it was recorded.

**Demo:** https://kvnloo.github.io/doppler-geoloc/

## Status: partial reproduction

| stage | colsto | this rebuild |
|---|---|---|
| Doppler curves found in [raw recording](https://youtu.be/4CxVxuMVkMc) | 2, 920 s apart | 2, 917.2 s apart (fit rms 0.35 / 0.72 Hz) |
| candidates heard both flyovers at the right gap | ~73,000 | 450,749 location/flight pairs (wider windows) |
| after silence filter | ~15,000 | 325,378 |
| final scoring | one clear winner, ~100 m | **no clear winner**: top 5 scores 5.82 / 5.63 / 5.59 / 5.56 / 5.56 |

The press-named area (Oyster Bay, NY) survives every filter, but its best candidate ranks #129. That town was used only to grade the result, never as a search prior. See the demo's "What's missing" section for the likely gaps.

## Layout

- `pipeline/`: the stages, run in order from a work dir holding the audio and ADS-B data. See [`pipeline/README.md`](pipeline/README.md).
- `docs/`: the GitHub Pages demo (static HTML, `assets/results.json` produced by `pipeline/site_assets.py`).

## Data

- Audio: the uploader's raw recording, fetched with `yt-dlp`, not redistributed.
- ADS-B: [adsb.lol globe_history_2026](https://github.com/adsblol/globe_history_2026), release `v2026.09.08-planes-readsb-prod-0`.
- Aircraft types: [tar1090-db](https://github.com/wiedehopf/tar1090-db) `icao_aircraft_types.js`.
- Terrain: [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) (terrarium, z8).

MIT licensed.
