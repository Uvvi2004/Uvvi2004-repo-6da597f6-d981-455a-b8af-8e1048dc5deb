from datetime import datetime, time
from decimal import Decimal


OFF_PEAK_RATE = Decimal("0.18")
MID_PEAK_RATE = Decimal("0.28")
PEAK_RATE = Decimal("0.42")


def rate_for_timestamp(at: datetime) -> Decimal:
    """Return the kWh rate for the timestamp's time of day."""
    current_time = at.time()

    if current_time >= time(22, 0) or current_time < time(6, 0):
        return OFF_PEAK_RATE
    if current_time < time(16, 0) or current_time >= time(21, 0):
        return MID_PEAK_RATE
    return PEAK_RATE
