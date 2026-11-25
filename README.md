# piSearch

**piSearch** is a desktop π explorer. It computes decimal digits of π on your
computer, lets you search those digits for numbers, dates, and words, and
visualizes the results on a zoomable canvas. The digits are generated when you
request them; the project does not ship with a precomputed digit database.

## What it does

- Computes a selected number of decimal digits of π using the Chudnovsky
  algorithm with binary splitting.
- Searches the computed digits for number strings and dates.
- Converts digit pairs into letters (`00 → A`, `01 → B`, ..., using the pair's
  value modulo 26) and searches words in two overlapping alignments:
  - **Frame A** starts with the first decimal digit.
  - **Frame B** starts with the second decimal digit.
  - WORD searches cover all computed pairs in both frames; Frame A is prioritized
    if the word occurs in both. The letter canvas preview is limited to 100,000
    letters per frame to bound display memory. A match beyond the preview is
    shown as its digit pairs in the Numbers view.
- Searches for painted patterns in the Colors grid.
- Displays digits in Numbers, Letters, Colors, and Black & White views. Pan with
  the mouse, zoom with the wheel, and navigate to search results.
- Records the canvas to an animated GIF (requires Pillow).
- Lets you cancel a computation and start a new search. Returning to the start
  screen clears the current digits and their derived display data from the
  application's references; the digits are not saved for reuse between runs.

## Requirements

- Python 3.10 or later
- PySide6 for the desktop UI
- NumPy for digit arrays, visualization, and chunked word search
- Pillow for GIF recording (optional at runtime)
- `gmpy2` for faster big-integer arithmetic (optional; pure-Python integers are
  used if it is unavailable)

The dependencies are listed in `requirements.txt`. `gmpy2` is an optional
runtime accelerator, though installing it is recommended for faster
computation.

## Install

From the project directory, create and activate a virtual environment, then
install dependencies.

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If installing `gmpy2` fails, the app can run without it. Install the core
packages directly:

```bash
python -m pip install PySide6 numpy Pillow
```

Pillow can also be omitted if GIF recording is not needed.

## Start the application

From the project directory with the virtual environment activated:

```bash
python main.py
```

Alternatively, run it as a module:

```bash
python -m pisearch
```

On the start screen, choose a digit count and select **COMPUTE**. The command
line can skip the start screen and begin computing a chosen count immediately:

```bash
python main.py --digits 2000000
```

## Using the app

1. Select the number of decimal digits to compute, then press **COMPUTE**.
2. Wait for the calculation to finish. Press **CANCEL** to request cooperative
   cancellation; the current large-integer operation may need to finish first.
3. Use the tabs to switch views. Drag to pan, use the mouse wheel to zoom, or
   double-click to zoom in.
4. Search from the bottom toolbar:
   - **ANY NUMBER** searches the digits you type. Spaces and punctuation are
     ignored.
   - **DATE** accepts dates such as `05/11/1995` and searches their digits in
     day-month-year order (`05111995`).
   - **WORD** accepts letters A–Z and searches both letter frames across all
     computed digits. A word's reported position is its 1-based letter index;
     the card also shows the corresponding digit position in π.
   - Press Enter or **SEARCH** to submit.
5. Select **SHAPE** to paint a small pattern and search for it in the Colors
   grid.
6. Select **← NEW SEARCH** to return to the start page and clear the current
   digits from the app's data structures.

Positions for number searches are 1-based, with position 1 being the first digit
after `3.`. Word positions are 1-based within the reported frame.

Other controls:

- **REC** records up to 30 seconds of the canvas to a GIF in `recordings/`.
- **+HUD** toggles the on-canvas view, zoom, position, and FPS information.
- **Ctrl+N** returns to the start page and clears computed data.
- **Ctrl+L** focuses the search input.
- **Home** returns the canvas to its home view. Arrow keys pan; `+`/`-` zoom.

## How it is made

The application is written in Python. Its main components are:

| File | Responsibility |
| --- | --- |
| `main.py`, `pisearch/__main__.py` | Application entry points |
| `pisearch/app.py` | Main window, background computation worker, and UI workflow |
| `pisearch/pi_compute.py` | Chudnovsky π computation with binary splitting |
| `pisearch/search.py` | Number, date, word, and shape search logic |
| `pisearch/resources.py` | Available-memory check and conservative computation budget |
| `pisearch/canvas.py` | Zoomable canvas, rendering, and result highlighting |
| `pisearch/widgets.py` | Start page, toolbar, tabs, and result card |
| `pisearch/shape_dialog.py` | Shape drawing dialog |
| `pisearch/recorder.py` | Canvas-to-GIF recording |
| `pisearch/theme.py` | Colors, fonts, and Qt stylesheet |

The UI uses **PySide6 (Qt)**. **NumPy** handles digit arrays and canvas
visualization. **gmpy2/GMP** accelerates arbitrary-precision integer arithmetic
when installed; the computation has a pure-Python integer fallback. **Pillow**
encodes recordings as GIFs.

## Large computations and storage

The start page offers selections up to one billion digits, but large values can
take a long time and require substantial memory. Before computing, piSearch
estimates a working-memory budget of 64 bytes per requested digit plus 1 GiB
reserved for the operating system. It blocks a request if the estimate exceeds
currently available physical RAM. If available RAM cannot be detected, it
limits a run to 100,000 digits.

This estimate is a guardrail, not a guarantee: actual peak memory depends on the
Python/runtime and computation stages, and Windows may still use its page file.
Choose a count appropriate for your computer and leave additional RAM available
for other applications.

Computed digits are kept in memory while you explore them. They are not written
to a database or cache file, so closing the app or starting a new search means
you will need to compute them again. Returning to the start screen clears the
app's references to the digits and derived canvas data; Python and the operating
system decide when released memory becomes available for reuse.

## Tests

Install pytest if needed, then run the test suite from the project directory:

```bash
python -m pip install pytest
python -m pytest -q tests
```
