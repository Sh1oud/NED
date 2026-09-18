"""PR-6M4B: partial-precision time as windows in a declared frame.

A recorded event time is never turned into a timestamp. ``2026-03`` stays "the whole of March",
``2026`` stays "the whole year": a **window** plus the **frame** the window is read in.

Frames
------
``zoned``   the value carried a zone and was normalised to UTC, so its window is a UTC window.
``naive``   the value carried no zone: a *local* wall-clock reading. Two naive readings are read
            in one frame - the reader's own - which is the only frame this product ever had.
``unknown`` no window at all (no declared time, a relative clue, an unparsable value).

The safety envelope, and why it is exactly this
-----------------------------------------------
A naive reading ``L`` denotes UTC ``L - offset`` for an offset in ``[-12h, +14h]`` - the whole
real-world range, from UTC-12:00 to UTC+14:00. So the set of UTC instants a naive window
``[lo, hi)`` can denote is exactly::

    [lo - MAX_OFFSET_EAST, hi + MAX_OFFSET_WEST)        # [lo - 14h, hi + 12h)

That is not a threshold chosen by taste: it is the image of the local window under the legal
offsets, so a *mixed* comparison (one zoned value against one naive value) may be decided if and
only if that widened window is disjoint from the zoned one. The two halves are used on their own
side - 14h on the early side, 12h on the late side - which is the tight bound, not a round number.
``ZONE_ENVELOPE`` (their sum, 26h) is the same quantity the exploratory audit quoted; it is the
width of the whole envelope, and it is only ever used as documentation.

Nothing here reads ``saved_at``: :class:`TemporalWindow` is built from the declared event time
alone, so filing time can never order anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

#: The extremes of the world's zone offsets, and therefore the whole envelope: UTC-12:00 and
#: UTC+14:00. A local reading is at most 14h behind UTC (east of it) and 12h ahead of UTC (west).
MAX_OFFSET_EAST = timedelta(hours=14)  # UTC+14:00
MAX_OFFSET_WEST = timedelta(hours=12)  # UTC-12:00
#: The full width of the envelope: the earliest and the latest UTC instant one local reading can
#: denote are ``ZONE_ENVELOPE`` apart. Documented for readers; the comparison uses the halves.
ZONE_ENVELOPE = MAX_OFFSET_EAST + MAX_OFFSET_WEST


class Frame(StrEnum):
    """Which clock a window belongs to."""

    ZONED = "zoned"
    NAIVE = "naive"
    UNKNOWN = "unknown"


class Order(StrEnum):
    """The only four answers the comparator may give."""

    BEFORE = "before"
    AFTER = "after"
    SAME = "same"
    NOT_COMPARABLE = "not_comparable"


class OrderReason(StrEnum):
    """Why an order was decided - or refused. Machine-readable, so callers can explain it."""

    DISJOINT_UTC = "disjoint_utc"
    DISJOINT_LOCAL = "disjoint_local"
    DISJOINT_BEYOND_ZONE_ENVELOPE = "disjoint_beyond_zone_envelope"
    CONTAINMENT = "containment"
    ZONE_FRAME_MISMATCH = "zone_frame_mismatch"
    NO_DERIVED_WINDOW = "no_derived_window"
    SAME_RECORDED_VALUE = "same_recorded_value"


#: The precision ladder, and the shape each rung stores. A value must match its own rung: the
#: store already validates this, and the comparator refuses anything it cannot read exactly.
SHAPES: dict[str, re.Pattern[str]] = {
    "year": re.compile(r"^(\d{4})$"),
    "month": re.compile(r"^(\d{4})-(\d{2})$"),
    "day": re.compile(r"^(\d{4})-(\d{2})-(\d{2})$"),
    "hour": re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2})(Z?)$"),
    "minute": re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(Z?)$"),
    "second": re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(Z?)$"),
}


@dataclass(frozen=True)
class Comparison:
    """One answer, with its reason."""

    order: Order
    reason: OrderReason

    @property
    def decided(self) -> bool:
        return self.order in (Order.BEFORE, Order.AFTER)

    @property
    def undecided(self) -> bool:
        return self.order is Order.NOT_COMPARABLE


@dataclass(frozen=True)
class TemporalWindow:
    """A recorded event time: a window, and the frame it is read in.

    ``window`` is a half-open interval ``[lo, hi)``: in UTC when the frame is ``zoned``, in local
    wall-clock when the frame is ``naive``, and ``None`` when there is no window at all.
    """

    value: str | None
    precision: str
    source: str
    frame: Frame
    window: tuple[datetime, datetime] | None

    @property
    def comparable(self) -> bool:
        return self.frame is not Frame.UNKNOWN and self.window is not None

    def utc_span(self) -> tuple[datetime, datetime] | None:
        """The set of UTC instants this record can denote, widened only when it must be.

        A zoned window is already UTC. A naive window becomes its image under every legal offset -
        which is what makes a mixed comparison provable rather than lucky.
        """

        if self.window is None:
            return None
        low, high = self.window
        if self.frame is Frame.ZONED:
            return low, high
        return low - MAX_OFFSET_EAST, high + MAX_OFFSET_WEST

    @classmethod
    def of(cls, value: str | None, precision: str, source: str) -> TemporalWindow:
        """Build the window for one recorded triple (value, precision, source)."""

        if source != "user" or value is None or precision not in SHAPES:
            return cls(value, precision, source, Frame.UNKNOWN, None)
        match = SHAPES[precision].match(value)
        if match is None:
            return cls(value, precision, source, Frame.UNKNOWN, None)
        groups = tuple(group for group in match.groups() if group and group.isdigit())
        digits = [int(group) for group in groups[:6]]
        # A missing month/day is the first of it; a missing time-of-day is midnight - never "01".
        padded = [*digits]
        while len(padded) < 6:
            padded.append(1 if len(padded) < 3 else 0)
        year, month, day, hour, minute, second = padded
        try:
            low = datetime(year, month, day, hour, minute, second)
        except ValueError:
            return cls(value, precision, source, Frame.UNKNOWN, None)
        if precision == "year":
            high = low.replace(year=low.year + 1)
        elif precision == "month":
            high = (low.replace(day=1) + timedelta(days=32)).replace(day=1)
        elif precision == "day":
            high = low + timedelta(days=1)
        elif precision == "hour":
            high = low + timedelta(hours=1)
        elif precision == "minute":
            high = low + timedelta(minutes=1)
        else:
            high = low + timedelta(seconds=1)
        # The shapes only ever allow "Z" as a trailing marker, and it is the whole difference
        # between a UTC window and a local one.
        frame = Frame.ZONED if value.endswith("Z") else Frame.NAIVE
        return cls(value, precision, source, frame, (low, high))


def _disjoint(first: tuple[datetime, datetime], second: tuple[datetime, datetime]) -> Order | None:
    """``BEFORE`` / ``AFTER`` when the two intervals are disjoint, else ``None``."""

    if first[1] <= second[0]:
        return Order.BEFORE
    if second[1] <= first[0]:
        return Order.AFTER
    return None


def compare(left: TemporalWindow, right: TemporalWindow) -> Comparison:
    """The one comparator the whole review uses. Never guesses, never pads a value."""

    if not left.comparable or not right.comparable:
        # Two unreadable records are not "the same record": there is nothing to compare at all.
        return Comparison(Order.NOT_COMPARABLE, OrderReason.NO_DERIVED_WINDOW)
    if left == right:
        return Comparison(Order.SAME, OrderReason.SAME_RECORDED_VALUE)
    if left.frame is right.frame:
        assert left.window is not None and right.window is not None
        decided = _disjoint(left.window, right.window)
        if decided is None:
            return Comparison(Order.NOT_COMPARABLE, OrderReason.CONTAINMENT)
        reason = (
            OrderReason.DISJOINT_UTC if left.frame is Frame.ZONED else OrderReason.DISJOINT_LOCAL
        )
        return Comparison(decided, reason)
    # One zoned, one naive. The naive side is read in every zone it could have been written in;
    # only a disjointness that survives all of them is a proof.
    left_utc, right_utc = left.utc_span(), right.utc_span()
    assert left_utc is not None and right_utc is not None
    decided = _disjoint(left_utc, right_utc)
    if decided is None:
        return Comparison(Order.NOT_COMPARABLE, OrderReason.ZONE_FRAME_MISMATCH)
    return Comparison(decided, OrderReason.DISJOINT_BEYOND_ZONE_ENVELOPE)


def strictly_before(left: TemporalWindow, right: TemporalWindow) -> bool:
    """True only when ``left`` is provably earlier than ``right``."""

    return compare(left, right).order is Order.BEFORE


def undecidable(left: TemporalWindow, right: TemporalWindow) -> bool:
    """True when the two cannot be ordered at all - the honest "I do not know"."""

    return compare(left, right).order is Order.NOT_COMPARABLE


__all__ = [
    "MAX_OFFSET_EAST",
    "MAX_OFFSET_WEST",
    "SHAPES",
    "ZONE_ENVELOPE",
    "Comparison",
    "Frame",
    "Order",
    "OrderReason",
    "TemporalWindow",
    "compare",
    "strictly_before",
    "undecidable",
]
