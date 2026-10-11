"""Wait-guard threshold from the waits still in queue."""

from __future__ import annotations

import statistics


def drop_extremes(waits: list[float]) -> list[float]:
    """Drop the upper tail once the sample is large enough.

    With fewer than 8 waits, every wait stays in the sample. At 8 or more,
    waits above the 95th percentile are removed. If that would empty the
    sample, the original waits are kept.
    """
    if len(waits) < 8:
        return list(waits)
    ordered = sorted(waits)
    cut = ordered[int(0.95 * (len(ordered) - 1))]
    kept = [wait for wait in waits if wait <= cut]
    return kept or list(waits)


def threshold_seconds(queue_waits: list[float], buffer_seconds: float = 60) -> float | None:
    """Return mean + 2 * population stdev + buffer.

    Fewer than 4 waits is not enough mass to force an ordinary route, so the
    threshold is None and nothing is breached.
    """
    if buffer_seconds < 0:
        raise ValueError("buffer_seconds must be >= 0")
    if any(wait < 0 for wait in queue_waits):
        raise ValueError("waits must be >= 0")
    if len(queue_waits) < 4:
        return None
    cleaned = drop_extremes(queue_waits)
    if len(cleaned) < 2:
        return None
    mean = statistics.fmean(cleaned)
    stdev = statistics.pstdev(cleaned)
    return mean + 2 * stdev + buffer_seconds


def is_breached(wait_seconds: float, limit: float | None) -> bool:
    if wait_seconds < 0:
        raise ValueError("wait_seconds must be >= 0")
    if limit is None:
        return False
    return wait_seconds > limit
