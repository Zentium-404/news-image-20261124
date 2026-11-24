# The World — Tuesday, 24 November 2026

One page. One map. The day's world news in a single 1024×1024 image, drawn entirely by
[`main.py`](main.py) with nothing but the Python standard library.

[![make.fun](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/bounty/news-image-20261124)
[![rank](https://make.fun/badge/news-image-20261124/Zentium-404/news-image-20261124/rank.svg)](https://make.fun/bounty/news-image-20261124)
[![reward](https://make.fun/badge/news-image-20261124/Zentium-404/news-image-20261124/reward.svg)](https://make.fun/bounty/news-image-20261124)

Entry for [make.fun's news-image-20261124 bounty](https://make.fun/bounty/news-image-20261124):
sum up 24 November 2026's world news in one image. The winner's picture becomes make.fun's
picture of the day.

## What the image shows

An equirectangular world map with five numbered markers where the day's stories happened, a
headline, and six stories across four regions and three fields:

1. **Iran** — a fourth oil tanker in two days hits a naval mine in the Strait of Hormuz; the
   IRGC says US escorts failed. Brent holds near $89.
2. **Ukraine** — naval drones sink the corvette *Merkury* off Libya, the first confirmed
   sinking of a Russian warship beyond the Black Sea.
3. **Tech** — Nvidia reinstates Jensen Huang as CEO; shares surge 31.5%, a record $952bn in
   one day.
4. **Gaza** — Israeli strikes kill Hamas internal-security chief Na'im Abu Nahl in Gaza City.
5. **Pacific** — the Solomon Islands end their security pact with China, realigning toward
   Australia.
6. **Space** — NATO vows to counter any Russian nuclear weapon placed in orbit.

Every fact was first reported on 24 November 2026 and verified across at least two sources
(AP, Reuters, The Guardian, CNBC, Anadolu).

## How it works

`python3 main.py` writes `entry.png` (or `$MAKEFUN_OUTPUT_DIR/entry.png`). No network, no
dependencies, two runs write identical bytes. The program:

- embeds two typefaces (DejaVu Sans for text, DejaVu Serif Bold for the masthead and
  headline) as flat glyph contours extracted from the TTF files, and the Natural Earth 110m
  land polygons, both gzip + base64 packed;
- renders everything with a scanline even-odd polygon fill into an RGB framebuffer;
- writes a minimal PNG by hand (zlib + CRC32, standard library).

## Run

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## License

[MIT](LICENSE)
