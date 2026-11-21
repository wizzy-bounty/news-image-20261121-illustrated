# THE WORLD IN ONE DAY — Saturday 21 November 2026

An illustrated one-page broadsheet summing up the world's news of
**Saturday 21 November 2026**, drawn entirely in code.

[![Competition](https://make.fun/badge/news-image-20261121.svg)](https://make.fun/bounty/news-image-20261121)
[![Rank](https://make.fun/badge/news-image-20261121/wizzy-bounty/news-image-20261121-illustrated/rank.svg)](https://make.fun/bounty/news-image-20261121)
[![Reward](https://make.fun/badge/news-image-20261121/wizzy-bounty/news-image-20261121-illustrated/reward.svg)](https://make.fun/bounty/news-image-20261121)

## What the page shows

- A masthead and red date banner naming the day, plus an eight-figure
  numbers strip (EU €7.9bn to Ukraine, the $120bn COP31 adaptation ask,
  the S&P 500's −3.7%, a 235-month sentence, a 306-run win, 62 cheetahs,
  310 media partners, October at 1.8 °C).
- Three illustrated hero stories: Russian missiles and a jet drone down
  in Poland (drawn night-sky scene with smoke trails, bursts and houses),
  COP31 running into overtime in Antalya (globe, thermometer, factory,
  "NO DEAL YET" placards), and Wall Street's correction (candlesticks, a
  plunging line and a lit skyline).
- A hand-coded world map with 12 numbered markers and a legend.
- Twenty story cards with drawn pictogram icons, grouped by region.

## How it works

`main.py` (Python 3, standard library only, no network) renders the page
with its own rasteriser at 2× supersampling: polygon-filled continents,
procedural illustrations, and baked glyph data (`fontdata.py`, DejaVu)
blitted as alpha maps. It writes a deterministic 1024×1024 PNG to
`/output/entry.png` (or `$MAKEFUN_OUTPUT_DIR/entry.png`) — two runs
produce byte-identical output.

## Run it

```sh
python3 main.py            # writes /output/entry.png
```

## License

MIT — see `LICENSE`.
