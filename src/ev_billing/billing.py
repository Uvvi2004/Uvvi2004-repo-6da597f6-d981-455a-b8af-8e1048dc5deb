from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Sequence

from .models import BillingInterval, MeterReading
from .tariffs import rate_for_timestamp


_TARIFF_BOUNDARIES = (time(6, 0), time(16, 0), time(21, 0), time(22, 0))


def prepare_meter_readings(
    readings: Sequence[MeterReading],
) -> list[MeterReading]:
    """Sort a copy of readings and discard cumulative rollback readings."""
    prepared: list[MeterReading] = []
    for reading in sorted(readings, key=lambda item: item.timestamp):
        if not prepared or reading.cumulative_kwh >= prepared[-1].cumulative_kwh:
            prepared.append(reading)
    return prepared


def _next_tariff_boundary(at: datetime, end: datetime) -> datetime:
    candidates = []
    for day_offset in (0, 1):
        boundary_date = at.date() + timedelta(days=day_offset)
        for boundary_time in _TARIFF_BOUNDARIES:
            boundary = datetime.combine(
                boundary_date, boundary_time, tzinfo=at.tzinfo
            )
            if at < boundary <= end:
                candidates.append(boundary)
    return min(candidates, default=end)


def _elapsed_as_decimal(start: datetime, end: datetime) -> Decimal:
    delta = end - start
    return (
        Decimal(delta.days) * Decimal(86400)
        + Decimal(delta.seconds)
        + (Decimal(delta.microseconds) / Decimal(1_000_000))
    )


def build_billing_intervals(
    readings: Sequence[MeterReading],
) -> list[BillingInterval]:
    """Build tariff intervals from chronologically sorted meter readings."""
    intervals: list[BillingInterval] = []

    for previous, current in zip(readings, readings[1:]):
        total_duration = _elapsed_as_decimal(
            previous.timestamp, current.timestamp
        )
        energy = current.cumulative_kwh - previous.cumulative_kwh
        segment_start = previous.timestamp

        while segment_start < current.timestamp:
            segment_end = _next_tariff_boundary(segment_start, current.timestamp)
            segment_duration = _elapsed_as_decimal(segment_start, segment_end)
            segment_energy = energy * segment_duration / total_duration
            intervals.append(
                BillingInterval(
                    start_time=segment_start,
                    end_time=segment_end,
                    energy=segment_energy,
                    rate=rate_for_timestamp(segment_start),
                )
            )
            segment_start = segment_end

    return intervals
