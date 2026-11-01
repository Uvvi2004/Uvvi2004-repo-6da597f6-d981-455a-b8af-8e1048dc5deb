from datetime import datetime
from decimal import Decimal

from ev_billing.models import ChargingSession, MeterReading


def test_charging_sessions_have_independent_meter_reading_lists():
    started_at = datetime(2026, 1, 1, 12, 0)
    first_session = ChargingSession("session-1", "charger-1", "driver-1", started_at)
    second_session = ChargingSession("session-2", "charger-1", "driver-2", started_at)

    first_session.meter_readings.append(
        MeterReading(started_at, Decimal("1.25"))
    )

    assert len(first_session.meter_readings) == 1
    assert second_session.meter_readings == []
    assert first_session.meter_readings is not second_session.meter_readings