from datetime import datetime
from decimal import Decimal

import pytest

from ev_billing.models import ChargingSession, MeterReading
from ev_billing.network import ChargingNetwork
from ev_billing.tariffs import rate_for_timestamp


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


def _network_with_session():
    network = ChargingNetwork()
    network.registerCharger("charger-1", "site-1")
    session_id = network.startSession(
        "driver-1", "charger-1", datetime(2026, 1, 1, 12, 0)
    )
    return network, session_id


def test_record_meter_reading_rejects_unknown_session():
    with pytest.raises(ValueError, match="not registered"):
        ChargingNetwork().recordMeterReading(
            "unknown", datetime(2026, 1, 1, 12, 1), Decimal("1.0")
        )


def test_record_meter_reading_rejects_time_before_session_start():
    network, session_id = _network_with_session()

    with pytest.raises(ValueError, match="before session start"):
        network.recordMeterReading(
            session_id, datetime(2026, 1, 1, 11, 59), Decimal("1.0")
        )


def test_record_meter_reading_rejects_time_after_session_stop():
    network, session_id = _network_with_session()
    network.sessions[session_id].stopped_at = datetime(2026, 1, 1, 12, 30)

    with pytest.raises(ValueError, match="after session stop"):
        network.recordMeterReading(
            session_id, datetime(2026, 1, 1, 12, 31), Decimal("2.0")
        )


def test_record_meter_reading_rejects_stopped_session():
    network, session_id = _network_with_session()
    network.sessions[session_id].status = "stopped"

    with pytest.raises(ValueError, match="already stopped"):
        network.recordMeterReading(
            session_id, datetime(2026, 1, 1, 12, 1), Decimal("1.0")
        )


def test_record_meter_reading_preserves_insertion_order():
    network, session_id = _network_with_session()
    later = datetime(2026, 1, 1, 12, 10)
    earlier = datetime(2026, 1, 1, 12, 1)

    network.recordMeterReading(session_id, later, Decimal("2.0"))
    network.recordMeterReading(session_id, earlier, Decimal("1.0"))

    readings = network.sessions[session_id].meter_readings
    assert [reading.timestamp for reading in readings] == [later, earlier]


def test_record_meter_reading_replaces_same_timestamp_and_counts_replacement():
    network, session_id = _network_with_session()
    timestamp = datetime(2026, 1, 1, 12, 1)

    network.recordMeterReading(session_id, timestamp, Decimal("1.0"))
    replacement = network.recordMeterReading(session_id, timestamp, Decimal("1.5"))

    session = network.sessions[session_id]
    assert session.meter_readings == [replacement]
    assert replacement.cumulative_kwh == Decimal("1.5")
    assert session.replacement_count == 1


def test_stop_session_rejects_unknown_session():
    with pytest.raises(ValueError, match="not registered"):
        ChargingNetwork().stopSession(
            "unknown", datetime(2026, 1, 1, 12, 1)
        )


def test_stop_session_rejects_time_before_start_without_changing_session():
    network, session_id = _network_with_session()
    session = network.sessions[session_id]

    with pytest.raises(ValueError, match="before it starts"):
        network.stopSession(session_id, datetime(2026, 1, 1, 11, 59))

    assert session.stopped_at is None
    assert session.status == "running"


def test_stop_session_sets_stop_time_and_status():
    network, session_id = _network_with_session()
    stopped_at = datetime(2026, 1, 1, 12, 30)

    network.stopSession(session_id, stopped_at)

    session = network.sessions[session_id]
    assert session.stopped_at == stopped_at
    assert session.status == "stopped"


@pytest.mark.parametrize(
    ("hour", "minute", "expected_rate"),
    [
        (5, 59, Decimal("0.18")),
        (6, 0, Decimal("0.28")),
        (15, 59, Decimal("0.28")),
        (16, 0, Decimal("0.42")),
        (20, 59, Decimal("0.42")),
        (21, 0, Decimal("0.28")),
        (21, 59, Decimal("0.28")),
        (22, 0, Decimal("0.18")),
    ],
)
def test_rate_for_timestamp_boundaries_and_adjacent_times(
    hour, minute, expected_rate
):
    assert rate_for_timestamp(datetime(2026, 1, 1, hour, minute)) == expected_rate