"""Quantities of the circuit language: numbers with multiplier and unit, ranges and tolerances (language 4).

    parse("4k7")             Quantity(4700, 4700, None)    the multiplier stands in for the decimal point
    parse("10 mA")           Quantity(0.01, 0.01, "A")
    parse("0..5.5 V")        Quantity(0, 5.5, "V")         a range; the unit may stand on the second end only
    parse("10 mA ± 20 %")    Quantity(0.008, 0.012, "A")   a tolerance is a range
    parse("10 mA", unit="V") UnitError: a voltage is expected
    format(q)                the canonical text: "330 Ω", "0..5.5 V", "2 mA..15 mA"

A text that is no quantity – a word such as `green` or `1N4148` – gives None; a text that is one but does not fit –
two units in a range, a lower end above the upper – raises UnitError. The multipliers are edakit/circuit.py's. A
lone `m` after a number is the metre; `mA`, `mm` and `ms` are milli. A plain number where a unit is expected takes
that unit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from ..circuit import si

# The language's units with their aliases (language 4); `R` as in `2R2` and `330R` is the ohm.
UNITS = {"V": "V", "A": "A", "W": "W", "Ω": "Ω", "ohm": "Ω", "ohms": "Ω", "Ohm": "Ω", "Ohms": "Ω", "R": "Ω",
         "F": "F", "H": "H", "Hz": "Hz", "°C": "°C", "s": "s", "m": "m", "%": "%"}
WHAT = {"V": "a voltage", "A": "a current", "W": "a power", "Ω": "a resistance", "F": "a capacitance",
        "H": "an inductance", "Hz": "a frequency", "°C": "a temperature", "s": "a time", "m": "a length",
        "%": "a share in %"}
# Multipliers as powers of ten (circuit.MULTIPLIERS without R and Ω, which are the ohm here).
POWERS = {"p": -12, "n": -9, "u": -6, "µ": -6, "μ": -6, "m": -3, "k": 3, "K": 3, "M": 6, "G": 9}

_NUMBER = r"[-+]?\d+(?:\.\d+)?"
_INFIX = re.compile(r"^([-+]?\d+)([pnuµμmkKMGR])(\d+)\s*(.*)$")       # 4k7, 2R2, 4k7 Ω
_PLAIN = re.compile(rf"^({_NUMBER})\s*(.*)$")


class UnitError(ValueError):
    """A quantity that does not fit: two units in a range, a unit where another is expected."""


@dataclass(frozen=True)
class Quantity:
    lo: float
    hi: float
    unit: str | None = None

    @property
    def point(self):
        return self.lo == self.hi

    @property
    def centre(self):
        return _clean((self.lo + self.hi) / 2)

    def __str__(self):
        return format(self)


def _clean(x):
    return float(f"{x:.12g}")


def _scaled(number, power):
    return float(Decimal(number).scaleb(power))


def _suffix(rest):
    """(power, unit) of what follows a number – a unit, a multiplier, both or nothing – or None."""
    rest = rest.strip()
    if rest == "":
        return 0, None
    if rest in UNITS:
        return 0, UNITS[rest]
    if rest[0] in POWERS and (rest[1:] in UNITS or rest[1:] == "") and rest[1:] != "R":
        return POWERS[rest[0]], UNITS.get(rest[1:])
    return None


def _end(text):
    """(value, unit) of one end of a range, or None when the text is no quantity."""
    text = text.strip()
    m = _INFIX.match(text)
    if m:
        whole, mult, frac, rest = m.groups()
        tail = _suffix(rest)
        if tail is None or tail[0] != 0:
            return None
        number = f"{whole}.{frac}"
        if mult == "R":
            if tail[1] not in (None, "Ω"):
                return None
            return _scaled(number, 0), "Ω"
        return _scaled(number, POWERS[mult]), tail[1]
    m = _PLAIN.match(text)
    if not m:
        return None
    number, rest = m.groups()
    tail = _suffix(rest)
    if tail is None:
        return None
    return _scaled(number, tail[0]), tail[1]


def _range(text):
    if ".." not in text:
        end = _end(text)
        return None if end is None else Quantity(end[0], end[0], end[1])
    left, _, right = text.partition("..")
    a, b = _end(left), _end(right)
    if a is None or b is None:
        return None
    unit = a[1] or b[1]
    if a[1] and b[1] and a[1] != b[1]:
        raise UnitError(f"{text.strip()}: the ends are in different units, {a[1]} and {b[1]}")
    if a[0] > b[0]:
        raise UnitError(f"{text.strip()}: the lower end above the upper – a bare number takes the other end's unit, "
                        "not its multiplier")
    return Quantity(a[0], b[0], unit)


def parse(text, unit=None):
    """The quantity of a text (language 4), or None when it is no quantity; UnitError when it does not fit or is
    not in `unit`."""
    text = str(text or "").strip()
    if not text or text[0] not in "-+0123456789":
        return None
    tol = re.split(r"\s*(?:±|\+/-)\s*", text, maxsplit=1)
    if len(tol) == 2:
        base, p = _range(tol[0]), _end(tol[1])
        if base is None or p is None:
            return None
        if p[1] != "%":
            raise UnitError(f"{text}: a tolerance in % – `10 mA ± 20 %`")
        f = p[0] / 100
        q = Quantity(_clean(base.lo * (1 - f)), _clean(base.hi * (1 + f)), base.unit)
    else:
        q = _range(text)
    if q is None:
        return None
    if unit is not None:
        if q.unit is None:
            return Quantity(q.lo, q.hi, unit)
        if q.unit != unit:
            raise UnitError(f"{text}: {WHAT.get(unit, unit)} is expected, in {unit} – not {q.unit}")
    return q


def _number(x):
    return f"{_clean(x):g}"


def _prefix(x, unit):
    """The multiplier si() writes for x – '' for none."""
    text = si(x, unit)
    return text.split(" ", 1)[1][: -len(unit)] if unit else ""


def format(q):
    """The canonical text of a quantity: `330 Ω`, `10 mA`, `0..5.5 V`, `2 mA..15 mA`; without a unit the number."""
    if q.unit is None:
        return _number(q.lo) if q.point else f"{_number(q.lo)}..{_number(q.hi)}"
    if q.point:
        return si(q.lo, q.unit) if q.lo else f"0 {q.unit}"
    hi = si(q.hi, q.unit)
    if q.lo == 0 or (_prefix(q.lo, q.unit) == "" and _prefix(q.hi, q.unit) == ""):
        return f"{_number(q.lo)}..{hi}"
    return f"{si(q.lo, q.unit)}..{hi}"
