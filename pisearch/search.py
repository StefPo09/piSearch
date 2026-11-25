"""Search logic: numbers, dates, words (digit pairs -> letters) and pixel shapes.

Conventions
-----------
* ``digits`` is the string of decimals of pi (the leading "3" is not included).
* Positions shown to the user are 1-based.
* Letters: every pair of digits (00..99) becomes a letter (value mod 26, so
  00 -> A, 01 -> B, 02 -> C ...).  Two "frames" exist: frame A starts reading
  pairs at the first decimal, frame B one digit later.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

LETTER_LIMIT = 100_000  # letters kept per frame ("first 100,000 letters of either frame")
WORD_SEARCH_CHUNK = 1_000_000
FRAMES = ("A", "B")


# --------------------------------------------------------------------------- #
# Letters
# --------------------------------------------------------------------------- #
def digits_to_array(digits: str) -> np.ndarray:
    return np.frombuffer(digits.encode("ascii"), dtype=np.uint8) - 48


def build_letter_frames(digits: str, limit: int = LETTER_LIMIT) -> dict:
    """Return {"A": "...", "B": "..."} with up to ``limit`` letters per frame."""
    d = digits_to_array(digits).astype(np.int32)
    frames = {}
    for name, offset in (("A", 0), ("B", 1)):
        usable = (len(d) - offset) // 2
        usable = max(0, min(usable, limit))
        a = d[offset : offset + 2 * usable : 2]
        b = d[offset + 1 : offset + 1 + 2 * usable : 2]
        vals = (a * 10 + b) % 26
        frames[name] = (vals + 65).astype(np.uint8).tobytes().decode("ascii")
    return frames


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
@dataclass
class Match:
    """A search result.

    kind        'digits' | 'letters' | 'shape'
    query       what was searched (normalised)
    found       True/False
    position    1-based position shown on the card (digit or letter index)
    digit_pos   1-based digit position (for letters this is the digit of pi)
    frame       'A' / 'B' for letters
    indices     flat 0-based cell indices that must be highlighted
                (digit indices for 'digits'/'shape', letter indices for 'letters')
    count       total number of occurrences
    searched    amount of digits (or letters per frame) that were searched
    expected    expected depth (in digits) where the query should first appear
    cells       number of cells of a shape
    """

    kind: str
    query: str
    found: bool
    position: int = 0
    digit_pos: int = 0
    frame: Optional[str] = None
    indices: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    count: int = 0
    searched: int = 0
    expected: int = 0
    cells: int = 0
    error: str = ""


def _count_overlapping(haystack: str, needle: str) -> int:
    if not needle:
        return 0
    count = 0
    start = haystack.find(needle)
    while start != -1:
        count += 1
        start = haystack.find(needle, start + 1)
    return count


# --------------------------------------------------------------------------- #
# Numbers & dates
# --------------------------------------------------------------------------- #
def normalize_number(text: str) -> str:
    """Keep only digits (spaces, commas, dots... are ignored)."""
    return re.sub(r"\D", "", text)


def normalize_date(text: str) -> str:
    """'05/11/1995', '5.11.1995', '05-11-95' ... -> '05111995' (DDMMYYYY).

    Input with no separators is used as typed (so '05111995' stays as is).
    """
    parts = [p for p in re.split(r"\D+", text.strip()) if p]
    if len(parts) == 3:
        day, month, year = parts
        return day.zfill(2) + month.zfill(2) + (year if len(year) != 1 else year.zfill(2))
    return "".join(parts)


def search_digits(digits: str, query: str) -> Match:
    if not query:
        return Match("digits", query, False, error="Type some digits first.")
    n = len(digits)
    first = digits.find(query)
    expected = 10 ** len(query)
    if first == -1:
        return Match("digits", query, False, searched=n, expected=expected)
    return Match(
        "digits",
        query,
        True,
        position=first + 1,
        digit_pos=first + 1,
        indices=np.arange(first, first + len(query), dtype=np.int64),
        count=_count_overlapping(digits, query),
        searched=n,
        expected=expected,
    )


def _search_word_in_frames(frames: Mapping[str, str], word: str, expected: int) -> Match:
    searched = max(len(frames["A"]), len(frames["B"]))
    for name, offset in (("A", 0), ("B", 1)):
        text = frames[name]
        i = text.find(word)
        if i != -1:
            return Match(
                "letters",
                word,
                True,
                position=i + 1,
                digit_pos=offset + 2 * i + 1,
                frame=name,
                indices=np.arange(i, i + len(word), dtype=np.int64),
                count=_count_overlapping(text, word),
                searched=searched,
                expected=expected,
            )
    return Match("letters", word, False, searched=searched, expected=expected)


def _search_word_in_digit_frame(
    digits: str, offset: int, word: bytes, chunk_size: int
) -> Tuple[Optional[int], int, int]:
    """Return (first letter index, occurrence count, frame length)."""
    frame_length = max(0, (len(digits) - offset) // 2)
    step = max(chunk_size, len(word))
    carry = b""
    first = None
    count = 0
    letter_start = 0

    while letter_start < frame_length:
        letter_end = min(frame_length, letter_start + step)
        digit_start = offset + letter_start * 2
        digit_end = offset + letter_end * 2
        pairs = np.frombuffer(
            digits[digit_start:digit_end].encode("ascii"), dtype=np.uint8
        ) - 48
        codes = ((pairs[::2] * 10 + pairs[1::2]) % 26 + 65).astype(np.uint8)
        chunk = carry + codes.tobytes()
        values = np.frombuffer(chunk, dtype=np.uint8)
        starts = len(values) - len(word) + 1
        if starts > 0:
            matches = np.ones(starts, dtype=bool)
            for i, value in enumerate(word):
                matches &= values[i : i + starts] == value
            matches_count = int(np.count_nonzero(matches))
            if matches_count:
                if first is None:
                    first = letter_start - len(carry) + int(np.argmax(matches))
                count += matches_count

        carry = chunk[-(len(word) - 1) :] if len(word) > 1 else b""
        letter_start = letter_end

    return first, count, frame_length


def search_word(
    digits_or_frames: Union[str, Mapping[str, str]],
    query: str,
    chunk_size: int = WORD_SEARCH_CHUNK,
) -> Match:
    word = re.sub(r"[^A-Za-z]", "", query).upper()
    if not word:
        return Match("letters", query, False, error="Letters only (A-Z).")
    expected = (26 ** len(word)) * 2

    if not isinstance(digits_or_frames, str):
        return _search_word_in_frames(digits_or_frames, word, expected)

    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    digits = digits_or_frames
    word_bytes = word.encode("ascii")
    searched = len(digits) // 2
    # Search all of frame A before frame B, preserving the original priority.
    for name, offset in (("A", 0), ("B", 1)):
        first, count, _frame_length = _search_word_in_digit_frame(
            digits, offset, word_bytes, chunk_size
        )
        if first is not None:
            return Match(
                "letters",
                word,
                True,
                position=first + 1,
                digit_pos=offset + 2 * first + 1,
                frame=name,
                indices=np.arange(first, first + len(word), dtype=np.int64),
                count=count,
                searched=searched,
                expected=expected,
            )
    return Match("letters", word, False, searched=searched, expected=expected)


# --------------------------------------------------------------------------- #
# Shapes (pixel patterns drawn with digit colours)
# --------------------------------------------------------------------------- #
ShapeCells = Sequence[Tuple[int, int, int]]  # (row, col, digit)


def shape_bbox(cells: ShapeCells) -> Tuple[int, int]:
    return max(r for r, _c, _d in cells) + 1, max(c for _r, c, _d in cells) + 1


def search_shape(digits_arr: np.ndarray, width: int, cells: ShapeCells) -> Match:
    """Find the first place of the pi colour grid (``width`` columns) where all the
    painted cells of the shape match."""
    label = f"{len(cells)} cells"
    if not cells:
        return Match("shape", label, False, error="Paint at least one cell first.")
    n = len(digits_arr)
    rows = n // width
    h, w = shape_bbox(cells)
    expected = 10 ** len(cells)
    if rows < h or width < w:
        return Match("shape", label, False, searched=n, expected=expected, cells=len(cells))
    grid = digits_arr[: rows * width].reshape(rows, width)
    mask = np.ones((rows - h + 1, width - w + 1), dtype=bool)
    for r, c, d in cells:
        mask &= grid[r : r + rows - h + 1, c : c + width - w + 1] == d
    hits = np.argwhere(mask)
    if len(hits) == 0:
        return Match("shape", label, False, searched=n, expected=expected, cells=len(cells))
    r0, c0 = hits[0]
    idx = np.array([(r0 + r) * width + (c0 + c) for r, c, _d in cells], dtype=np.int64)
    first = int(min(idx))
    return Match(
        "shape",
        label,
        True,
        position=first + 1,
        digit_pos=first + 1,
        indices=idx,
        count=int(len(hits)),
        searched=n,
        expected=expected,
        cells=len(cells),
    )
