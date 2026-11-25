"""Compute pi at runtime with the Chudnovsky algorithm + binary splitting.

Nothing is pre-stored: every digit is computed on your machine.

If the optional ``gmpy2`` package is installed it is used for the big-integer
arithmetic (much faster).  Otherwise plain Python integers are used.
"""
from __future__ import annotations

import math
import sys
from typing import Callable, Optional

try:  # optional accelerator
    import gmpy2
    from gmpy2 import mpz

    HAVE_GMPY2 = True
except Exception:  # pragma: no cover - depends on the environment
    gmpy2 = None
    HAVE_GMPY2 = False

    def mpz(x):  # type: ignore
        return int(x)

if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)  # allow huge int <-> str conversions

# Chudnovsky constants
_A = 13591409
_B = 545140134
_C = 640320
_C3_OVER_24 = _C ** 3 // 24
_DIGITS_PER_TERM = math.log10(_C ** 3 / 1728)  # ~14.1816

ProgressCb = Callable[[float, str], None]


class Cancelled(Exception):
    """Raised when the computation is cancelled through the progress callback."""


def _bs(a: int, b: int, tick: Callable[[int], None]):
    """Binary splitting: returns (P, Q, T) for the terms [a, b)."""
    if b - a == 1:
        if a == 0:
            pab = qab = mpz(1)
        else:
            pab = mpz((6 * a - 5) * (2 * a - 1) * (6 * a - 1))
            qab = mpz(a) * mpz(a) * mpz(a) * _C3_OVER_24
        tab = pab * (_A + _B * a)
        if a & 1:
            tab = -tab
        tick(1)
        return pab, qab, tab
    m = (a + b) // 2
    pam, qam, tam = _bs(a, m, tick)
    pmb, qmb, tmb = _bs(m, b, tick)
    return pam * pmb, qam * qmb, qmb * tam + pam * tmb


def _isqrt(n):
    return gmpy2.isqrt(n) if HAVE_GMPY2 else math.isqrt(n)


def has_expected_digit_count(digits: str, expected: int) -> bool:
    """Check that a computed result contains exactly the requested decimals."""
    return len(digits) == expected


def compute_pi_digits(
    n_digits: int,
    progress: Optional[ProgressCb] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> str:
    """Return the first ``n_digits`` decimals of pi (without the leading '3').

    ``progress(fraction, message)`` is called regularly; raise ``Cancelled``
    from inside it to abort.
    """
    if n_digits < 1:
        raise ValueError("n_digits must be >= 1")
    report = progress or (lambda f, m: None)

    def check_cancelled() -> None:
        if cancel_check and cancel_check():
            raise Cancelled()

    guard = 12
    prec = n_digits + guard
    terms = int(prec / _DIGITS_PER_TERM) + 2
    done = [0]
    step = max(1, terms // 200)
    cancel_step = max(1, min(step, 4096))

    def tick(k: int) -> None:
        done[0] += k
        if done[0] % cancel_step == 0:
            check_cancelled()
        if done[0] % step == 0 or done[0] == terms:
            report(0.85 * done[0] / terms, "binary splitting")

    report(0.0, "binary splitting")
    _p, q, t = _bs(0, terms, tick)

    check_cancelled()
    report(0.86, "square root")
    one = mpz(10) ** prec
    sqrt_c = _isqrt(mpz(10005) * one * one)

    check_cancelled()
    report(0.93, "final division")
    pi_scaled = (q * 426880 * sqrt_c) // t  # pi * 10**prec

    check_cancelled()
    report(0.97, "converting to text")
    s = str(pi_scaled)
    check_cancelled()
    report(1.0, "done")
    # s == "3" + decimals
    return s[1 : 1 + n_digits]
