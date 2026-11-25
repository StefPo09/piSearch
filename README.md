# piSearch

π Explorer: compute pi on your machine (Chudnovsky algorithm + binary splitting,
nothing pre-stored), then search **numbers, dates and words** in its digits and
fly to them on a zoomable canvas.

## Install

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

`gmpy2` is optional (it is only a speed-up). Without it 1M digits take ~12 s instead of <1 s.
If `gmpy2` fails to install on your system, run `pip install PySide6 numpy Pillow` instead.

## Run

```bash
python main.py            # or: python -m pisearch
python main.py --digits 2000000   # skip the start screen
```

## Using it

* **Start screen** - choose up to 1 billion digits and press COMPUTE. Large
  selections need substantial memory and can take a very long time. Number/date
  searches scan the full computed digit string.
* **Tabs** - 01 Numbers, 02 Letters, 03 Colors, 04 Black & White.
* **Mouse** - drag to pan, wheel to zoom, double-click to zoom in. Keys: arrows, `+`/`-`, Home.
* **Search** - `ANY NUMBER` (digits), `DATE` (DD/MM/YYYY -> `DDMMYYYY`), `WORD` (letters tab).
  Press Enter or SEARCH. Positions are counted in the decimals of pi (1 = the first digit after "3.").
* **Letters** - every pair of digits becomes a letter (`value mod 26`, 00=A, 01=B, 02=C...).
  Frame A reads pairs from the first decimal, Frame B starts one digit later. Frame A is searched first,
  up to 100,000 letters per frame.
* **SHAPE** - paint a small pattern with digit colours; it is searched in the COLORS grid.
* **REC** - records the canvas to an animated GIF in `recordings/` (30 s max).
* **+HUD** - overlay with view, zoom, position and FPS.
* **Ctrl+N** - back to the start screen, **Ctrl+L** - focus the search box.

## Tests

```bash
pip install pytest
python -m pytest -q tests
```
