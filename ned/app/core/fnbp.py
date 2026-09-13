"""FNBP — Fuyuki Notification Branch Predictor.

A pure easter egg, kept in the Lab tab because it is not an analysis. It models
the well-known phenomenon of waiting for one specific person's message and
mispredicting every single notification as being from them, with the CPU-style
consequences: mispredict, pipeline flush, wasted cycles.

``Fuyuki`` is a fictional internal codename used by NED's test harness. It is
not a real person, and this module analyses nobody.
"""

from __future__ import annotations

from ned.app.core.models import (
    FnbpNotification,
    FnbpRequest,
    FnbpResult,
)
from ned.app.core.rules import RuleBook
from ned.app.core.verdict import VerdictEngine

#: Branch predictor warm-up: confidence in the expected sender after k hits.
BASE_CONFIDENCE = 0.60
CONFIDENCE_CEILING = 0.99
LEARNING_RATE = 0.5

#: Cost model for a mispredicted notification, in imaginary cycles.
FLUSH_FIXED_COST = 17
FLUSH_PER_INDEX_COST = 3


class NotificationBranchPredictor:
    """Deterministic simulation of a one-target branch predictor."""

    def __init__(self, book: RuleBook) -> None:
        self.book = book
        self.verdicts = VerdictEngine(book)

    def confidence_after(self, hits: int, base_rate: float | None = None) -> float:
        """Confidence that the next notification is from the expected sender."""

        base = BASE_CONFIDENCE if base_rate is None else max(0.0, min(1.0, base_rate))
        confidence = base + (CONFIDENCE_CEILING - base) * (1.0 - LEARNING_RATE**hits)
        return round(min(CONFIDENCE_CEILING, confidence), 4)

    def run(self, request: FnbpRequest, language: str = "zh") -> FnbpResult:
        """Predict every notification and count the damage."""

        senders = [sender for sender in request.actual_senders if sender.strip()] or ["未知"]
        per_notification: list[FnbpNotification] = []
        hits = 0
        flushes = 0
        wasted = 0

        for index in range(1, request.notifications + 1):
            confidence = self.confidence_after(hits, request.base_rate)
            actual = senders[(index - 1) % len(senders)]
            hit = actual.strip() == request.expected_sender.strip()
            if hit:
                hits += 1
            else:
                flushes += 1
                wasted += FLUSH_FIXED_COST + FLUSH_PER_INDEX_COST * index
            per_notification.append(
                FnbpNotification(
                    index=index,
                    predicted_sender=request.expected_sender,
                    predicted_probability=round(confidence * 100.0, 2),
                    actual_sender=actual,
                    hit=hit,
                    pipeline_flushed=not hit,
                )
            )

        misses = request.notifications - hits
        mispredict_rate = round(100.0 * misses / request.notifications, 4)
        verdict = self.verdicts.fnbp_verdict(
            "hit" if misses == 0 else "mispredict",
            language,
            {"hits": hits, "misses": misses, "rate": mispredict_rate},
        )
        note = self.book.fnbp_note.get(language) or self.book.fnbp_note.get("default", "")
        return FnbpResult(
            expected_sender=request.expected_sender,
            notifications=request.notifications,
            prediction_hits=hits,
            prediction_misses=misses,
            mispredict_rate=mispredict_rate,
            pipeline_flushes=flushes,
            wasted_cycles=wasted,
            per_notification=per_notification,
            verdict=verdict,
            codename_note=note,
            disclaimer=self.book.disclaimer,
        )


__all__ = ["NotificationBranchPredictor"]
