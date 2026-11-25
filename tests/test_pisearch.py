import os
import sys

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication

from pisearch.app import MainWindow, PiWorker
from pisearch.canvas import Mode
from pisearch.pi_compute import Cancelled, compute_pi_digits, has_expected_digit_count
from pisearch.resources import (
    MEMORY_RESERVE_BYTES,
    UNKNOWN_MEMORY_MAX_DIGITS,
    estimated_peak_bytes,
    resource_warning,
)
from pisearch import search as S
from pisearch.widgets import DIGIT_CHOICES

PI_50 = "14159265358979323846264338327950288419716939937510"
_APP = QApplication.instance() or QApplication([])


def _digits_for_letters(text):
    return "".join(f"{ord(letter) - ord('A'):02d}" for letter in text)


def test_digit_choices_reach_one_billion():
    assert DIGIT_CHOICES[-1] == 1_000_000_000
    assert DIGIT_CHOICES == sorted(set(DIGIT_CHOICES))


def test_memory_budget_blocks_requests_that_exceed_available_ram():
    required = estimated_peak_bytes(1_000_000)
    assert resource_warning(1_000_000, required) is None
    warning = resource_warning(1_000_000, required - 1)
    assert warning is not None
    assert "page-file" in warning


def test_memory_budget_reserves_headroom_and_falls_back_conservatively():
    assert estimated_peak_bytes(0) == MEMORY_RESERVE_BYTES
    assert resource_warning(UNKNOWN_MEMORY_MAX_DIGITS, None) is None
    assert resource_warning(UNKNOWN_MEMORY_MAX_DIGITS + 1, None) is not None


def test_digits_known_prefix():
    assert compute_pi_digits(50) == PI_50


def test_computed_output_must_match_requested_digit_count():
    assert has_expected_digit_count("12345", 5)
    assert not has_expected_digit_count("1234", 5)
    assert not has_expected_digit_count("123456", 5)


def test_pi_computation_supports_cooperative_cancellation():
    with pytest.raises(Cancelled):
        compute_pi_digits(1000, cancel_check=lambda: True)


def test_worker_emits_cancelled_without_emitting_partial_digits():
    worker = PiWorker(1000)
    events = []
    worker.done.connect(lambda _digits: events.append("done"))
    worker.cancelled.connect(lambda: events.append("cancelled"))

    worker.cancel()
    worker.run()

    assert events == ["cancelled"]


def test_back_to_start_clears_computed_digits_and_derived_data():
    window = MainWindow()
    window.canvas.set_data("314159265358979323846")
    window.canvas._tex["test"] = object()
    window.canvas._adv_cache[12] = object()
    window.canvas.set_mode(Mode.LETTERS)
    window.toolbar.edit.setText("12345")
    window.card.show_card("found", "FOUND", "test result")
    window.stack.setCurrentIndex(1)

    window.explorer.back.click()

    assert window.stack.currentWidget() is window.start
    assert not window.canvas.has_data()
    assert window.canvas.digits == ""
    assert window.canvas.darr is None
    assert window.canvas.frames == {"A": "", "B": ""}
    assert window.canvas._tex == {}
    assert window.canvas._adv_cache == {}
    assert window.canvas.mode == Mode.NUMBERS
    assert window.toolbar.edit.text() == ""
    assert window.card.isHidden()


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
    m = S.search_word(d, word)
    assert m.found and m.digit_pos <= 2 * 100 + 1
    assert m.expected == 26 ** 4 * 2


def test_word_search_finds_match_past_letter_preview_limit():
    digit_prefix = "00" * 100_000
    digits = digit_prefix + _digits_for_letters("PIE") + "00"

    match = S.search_word(digits, "PIE", chunk_size=16_384)

    assert match.found
    assert (match.frame, match.position, match.digit_pos) == ("A", 100_001, 200_001)
    assert match.searched == len(digits) // 2


def test_word_search_finds_matches_crossing_chunk_boundaries():
    digits = _digits_for_letters("ABCDE")

    match = S.search_word(digits, "CDE", chunk_size=4)

    assert match.found
    assert (match.frame, match.position, match.digit_pos) == ("A", 3, 5)


def test_word_search_counts_overlapping_occurrences():
    match = S.search_word(_digits_for_letters("AAAAA"), "AAA", chunk_size=2)

    assert match.found
    assert (match.position, match.count) == (1, 3)


def test_word_search_falls_back_to_second_frame():
    match = S.search_word("7485260574", "WAI", chunk_size=2)

    assert match.found
    assert (match.frame, match.position, match.digit_pos) == ("B", 1, 2)


def test_word_match_beyond_preview_navigates_to_digit_pairs():
    digits = "00" * 100_000 + _digits_for_letters("PIE") + "00"
    window = MainWindow()
    window.canvas.set_data(digits)
    match = S.search_word(digits, "PIE", chunk_size=16_384)

    window.show_result(match)

    assert window.canvas.mode == Mode.NUMBERS
    assert window.canvas.highlight is not None
    assert window.canvas.highlight.kind == "digits"
    assert window.canvas.highlight.indices.tolist() == list(range(200_000, 200_006))
    assert "Beyond the letter preview" in window.card.body.text()


def test_not_found_expected_depth():
    d = compute_pi_digits(5000)
    m = S.search_word(d, "SPACE")
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
    pie = S.search_word(d, "PIE")
    assert (pie.frame, pie.position, pie.digit_pos) == ("A", 10_962, 21_923)
    cat = S.search_word(d, "CAT")
    assert (cat.frame, cat.position, cat.digit_pos) == ("A", 22_731, 45_461)
    nate = S.search_word(d, "NATE")
    assert (nate.frame, nate.position, nate.digit_pos) == ("A", 161_942, 323_883)
    assert S.search_word(d, "MATH").position == 91_682
    assert S.search_digits(d, "05111995").position == 875_183
    assert S.search_digits(d, "3773894514").position == 1_193_680
