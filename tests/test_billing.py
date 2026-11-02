from datetime import datetime
from decimal import Decimal

import pytest

from ev_billing.models import ChargingSession, MeterReading
from ev_billing.network import ChargingNetwork


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


def test_network_registers_charger():
    network = ChargingNetwork()

    charger = network.registerCharger("charger-1", "site-1")

    assert network.chargers["charger-1"] is charger
    assert charger.site_id == "site-1"


def test_network_rejects_duplicate_charger():
    network = ChargingNetwork()
    network.registerCharger("charger-1", "site-1")

    with pytest.raises(ValueError, match="already registered"):
        network.registerCharger("charger-1", "site-2")


def test_network_starts_session_for_registered_charger():
    network = ChargingNetwork()
    network.registerCharger("charger-1", "site-1")
    started_at = datetime(2026, 1, 1, 12, 0)

    session_id = network.startSession("driver-1", "charger-1", started_at)

    session = network.sessions[session_id]
    assert session.session_id == session_id
    assert session.charger_id == "charger-1"
    assert session.driver_id == "driver-1"
    assert session.started_at == started_at
    assert session.status == "running"


def test_network_rejects_sessions_for_unknown_chargers():
    with pytest.raises(ValueError, match="not registered"):
        ChargingNetwork().startSession(
            "driver-1", "charger-1", datetime(2026, 1, 1, 12, 0)
        )