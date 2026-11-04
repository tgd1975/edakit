"""The E-series of IEC 60063 – the values a derivation rule proposes from (circuit-dsl-language.md section 7).

    values("E24")         the mantissas of one decade, 1.0 … 9.1
    nearest(260, "E24")   270: the value of the series nearest by ratio, |ln(candidate / value)| smallest
    window(260, "E24")    (240, 300): the neighbours of the nearest value – one step of the series around it

The table is catalog/tables/series.toml, with its source.
"""

from __future__ import annotations

import math
from functools import lru_cache

from ..catalog import table

NAMES = ("E6", "E12", "E24", "E96")


@lru_cache(maxsize=None)
def _table():
    return table("series")


def names():
    return list(NAMES)


def values(name):
    """The mantissas of series `name`, one decade from 1.0."""
    if name not in NAMES:
        raise ValueError(f"no series {name!r} – one of {', '.join(NAMES)}")
    return list(_table()[name]["mantissas"])


def tolerance(name):
    values(name)
    return _table()[name]["tolerance"]


def _clean(x):
    return float(f"{x:.6g}")


def _ladder(value, name):
    """The series' values from the decade below the value's to the decade above, ascending."""
    if not (isinstance(value, (int, float)) and value > 0 and math.isfinite(value)):
        raise ValueError(f"a series value needs a positive number, not {value!r}")
    e = math.floor(math.log10(value))
    return [_clean(m * 10.0 ** k) for k in (e - 1, e, e + 1) for m in values(name)]


def nearest(value, name):
    """The value of the series nearest to `value` by ratio."""
    return min(_ladder(value, name), key=lambda c: abs(math.log(c / value)))


def window(value, name):
    """(below, above): the neighbours of the nearest value of the series."""
    ladder = _ladder(value, name)
    i = ladder.index(nearest(value, name))
    return ladder[i - 1], ladder[i + 1]
