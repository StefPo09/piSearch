import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pisearch.pi_compute import compute_pi_digits
from pisearch import search as S
from pisearch.widgets import DIGIT_CHOICES

PI_50 = "14159265358979323846264338327950288419716939937510"


def test_digit_choices_reach_one_billion():
    assert DIGIT_CHOICES[-1] == 1_000_000_000
    assert DIGIT_CHOICES == sorted(set(DIGIT_CHOICES))


def test_digits_known_prefix():
    assert compute_pi_digits(50) == PI_50


def test_known_tail_1000():
    assert compute_pi_digits(1000)[-10:] == "2164201989"


def test_feynman_point():
    d = compute_pi_digits(2000)
    m = S.search_digits(d, "999999")
    assert m.found and m.position == 762


def test_normalize_date():
    assert S.normalize_date("05/11/1995") == "05111995"
    assert S.normalize_date("5.1.1995") == "05011995"
    assert S.normalize_date("05111995") == "05111995"


def test_letter_mapping_and_positions():
    d = compute_pi_digits(5000)
    frames = S.build_letter_frames(d)
    # pairs 14 15 92 65 ... -> mod 26
    assert frames["A"][:4] == "".join(chr(65 + int(d[i : i + 2]) % 26) for i in (0, 2, 4, 6))
    assert frames["B"][:2] == "".join(chr(65 + int(d[i : i + 2]) % 26) for i in (1, 3))
    word = frames["A"][100:104]
    m = S.search_word(frames, word)
    assert m.found and m.digit_pos <= 2 * 100 + 1
    assert m.expected == 26 ** 4 * 2


def test_not_found_expected_depth():
    d = compute_pi_digits(5000)
    frames = S.build_letter_frames(d)
    m = S.search_word(frames, "SPACE")
    assert (not m.found) and m.expected == 23_762_752


def test_shape_search():
    arr = S.digits_to_array(compute_pi_digits(20000))
    cells = [(0, 0, 3), (0, 1, 1), (1, 0, 4)]
    m = S.search_shape(arr, 100, cells)
    assert m.found
    i = m.indices
    assert arr[i[0]] == 3 and arr[i[1]] == 1 and arr[i[2]] == 4
    assert i[2] - i[0] == 100


def test_frame_a_has_priority():
    # values taken from the original demo (2,000,000 digits)
    d = compute_pi_digits(2_000_000)
    frames = S.build_letter_frames(d)
    pie = S.search_word(frames, "PIE")
    assert (pie.frame, pie.position, pie.digit_pos) == ("A", 10_962, 21_923)
    cat = S.search_word(frames, "CAT")
    assert (cat.frame, cat.position, cat.digit_pos, cat.count) == ("A", 22_731, 45_461, 4)
    nate = S.search_word(frames, "NATE")
    assert (nate.frame, nate.position) == ("B", 84_252)
    assert S.search_word(frames, "MATH").position == 91_682
    assert S.search_digits(d, "05111995").position == 875_183
    assert S.search_digits(d, "3773894514").position == 1_193_680
