# The World on One Page — Tuesday, 24 November 2026

A 35-story broadsheet of the day's world news in a single 1024×1024 cream-newsprint
image, drawn entirely by [`main.py`](main.py) with nothing but the Python standard
library.

[![make.fun](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/bounty/news-image-20261124)
[![rank](https://make.fun/badge/news-image-20261124/Zentium-404/news-image-20261124/rank.svg)](https://make.fun/bounty/news-image-20261124)
[![reward](https://make.fun/badge/news-image-20261124/Zentium-404/news-image-20261124/reward.svg)](https://make.fun/bounty/news-image-20261124)

Entry for [make.fun's news-image-20261124 bounty](https://make.fun/bounty/news-image-20261124):
sum up 24 November 2026's world news in one image. The winner's picture becomes make.fun's
picture of the day.

## What the image shows

- **Masthead** — "THE WORLD ON ONE PAGE · DAY 328 OF 2026 · EVERY STORY DATED TUESDAY 24 NOV"
- **Summary strip** — 35 stories across 7 regions: Europe 6, Middle East 4, Asia 8,
  Africa 3, Americas 8, Oceania 4, Global 2.
- **4 hero stories**, each with a big figure and a mini Natural Earth map marking where
  it happened: Nvidia reinstates Huang (+30%), tankers hit mines in the Strait of Hormuz
  (3 of 4), Ukraine's refinery strikes cut Russian refining capacity (−45%), and COP31
  Antalya ends with no deal.
- **8-story grid** — Canada, South Korea, Estonia, Sudan, Singapore, Hodeidah, Brazil, Meta.
- **24-story ALSO wire** in two columns.
- **Methodology footer** — every story dated Tuesday 24 November 2026 (UTC), checked
  against the named outlets' reporting of the day.

## How it works

`python3 main.py` writes `entry.png` (or `/output/entry.png`). No network, no
dependencies, two runs write identical bytes (verified: same sha256 on repeat runs).
The program:

- embeds a DejaVu Sans glyph subset (flat contours, 64-unit em) and the Natural Earth
  110m land rings as gzip + base64 blobs in `gen/blobs.py`, loaded at runtime;
- renders everything with a scanline even-odd polygon fill into an RGB framebuffer;
- writes a minimal PNG by hand (zlib + CRC32, standard library).

## Run

```sh
python3 main.py   # writes entry.png, or /output/entry.png when /output exists
```

## License

[MIT](LICENSE)
