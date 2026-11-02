from datetime import datetime
from decimal import Decimal

import pytest

from ev_billing.models import BillingInterval, ChargingSession, MeterReading
from ev_billing.network import ChargingNetwork
from ev_billing.tariffs import rate_for_timestamp
from ev_billing.billing import build_billing_intervals, prepare_meter_readings


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


def test_stop_session_discards_readings_after_stop_time():
    network, session_id = _network_with_session()
    before_stop = datetime(2026, 1, 1, 12, 30)
    after_stop = datetime(2026, 1, 1, 13, 30)
    network.recordMeterReading(session_id, before_stop, Decimal("1"))
    network.recordMeterReading(session_id, after_stop, Decimal("2"))

    network.stopSession(session_id, datetime(2026, 1, 1, 13, 0))

    assert network.sessions[session_id].meter_readings == [
        MeterReading(before_stop, Decimal("1"))
    ]


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


def test_build_billing_intervals_splits_at_peak_boundary():
    readings = [
        MeterReading(datetime(2026, 1, 1, 15, 30), Decimal("0")),
        MeterReading(datetime(2026, 1, 1, 16, 30), Decimal("40")),
    ]

    intervals = build_billing_intervals(readings)

    assert intervals == [
        BillingInterval(
            datetime(2026, 1, 1, 15, 30),
            datetime(2026, 1, 1, 16, 0),
            Decimal("20"),
            Decimal("0.28"),
        ),
        BillingInterval(
            datetime(2026, 1, 1, 16, 0),
            datetime(2026, 1, 1, 16, 30),
            Decimal("20"),
            Decimal("0.42"),
        ),
    ]


def test_build_billing_intervals_crosses_midnight_at_tariff_boundaries():
    readings = [
        MeterReading(datetime(2026, 1, 1, 21, 30), Decimal("0")),
        MeterReading(datetime(2026, 1, 2, 6, 30), Decimal("54")),
    ]

    intervals = build_billing_intervals(readings)

    assert intervals == [
        BillingInterval(
            datetime(2026, 1, 1, 21, 30),
            datetime(2026, 1, 1, 22, 0),
            Decimal("3"),
            Decimal("0.28"),
        ),
        BillingInterval(
            datetime(2026, 1, 1, 22, 0),
            datetime(2026, 1, 2, 6, 0),
            Decimal("48"),
            Decimal("0.18"),
        ),
        BillingInterval(
            datetime(2026, 1, 2, 6, 0),
            datetime(2026, 1, 2, 6, 30),
            Decimal("3"),
            Decimal("0.28"),
        ),
    ]


def test_prepare_meter_readings_sorts_copy_and_filters_rollbacks():
    ten_am = MeterReading(datetime(2026, 1, 1, 10, 0), Decimal("10"))
    eleven_am = MeterReading(datetime(2026, 1, 1, 11, 0), Decimal("5"))
    noon = MeterReading(datetime(2026, 1, 1, 12, 0), Decimal("8"))
    readings = [eleven_am, noon, ten_am]

    prepared = prepare_meter_readings(readings)

    assert prepared == [ten_am]
    assert readings == [eleven_am, noon, ten_am]
    assert prepared is not readings


def test_prepare_meter_readings_compares_against_last_accepted_reading():
    readings = [
        MeterReading(datetime(2026, 1, 1, 11, 0), Decimal("5")),
        MeterReading(datetime(2026, 1, 1, 10, 0), Decimal("10")),
        MeterReading(datetime(2026, 1, 1, 12, 0), Decimal("8")),
    ]

    prepared = prepare_meter_readings(readings)

    assert [reading.timestamp for reading in prepared] == [
        datetime(2026, 1, 1, 10, 0)
    ]


def test_prepare_meter_readings_keeps_billable_increase_after_rollback():
    readings = [
        MeterReading(datetime(2026, 1, 1, 11, 0), Decimal("8")),
        MeterReading(datetime(2026, 1, 1, 10, 0), Decimal("10")),
        MeterReading(datetime(2026, 1, 1, 12, 0), Decimal("14")),
    ]

    prepared = prepare_meter_readings(readings)

    assert prepared == [readings[1], readings[2]]
    assert prepared[-1].cumulative_kwh - prepared[0].cumulative_kwh == Decimal("4")


def test_calculate_invoice_rounds_lines_and_adds_session_fee():
    network, session_id = _network_with_session()
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 12, 0), Decimal("0")
    )
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 13, 0), Decimal("1.2345")
    )
    network.stopSession(session_id, datetime(2026, 1, 1, 13, 30))

    invoice = network.calculateInvoice(session_id)

    assert len(invoice.lines) == 1
    assert invoice.lines[0].energy == Decimal("1.235")
    assert invoice.lines[0].amount == Decimal("0.35")
    assert invoice.session_fee == Decimal("1.00")
    assert invoice.total == Decimal("1.35")


def test_calculate_invoice_rejects_unknown_session():
    with pytest.raises(ValueError, match="not registered"):
        ChargingNetwork().calculateInvoice("unknown")


def test_calculate_invoice_rejects_running_session():
    network, session_id = _network_with_session()

    with pytest.raises(ValueError, match="has not stopped"):
        network.calculateInvoice(session_id)


def test_calculate_invoice_does_not_estimate_after_last_reading():
    network, session_id = _network_with_session()
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 12, 0), Decimal("0")
    )
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 13, 0), Decimal("2")
    )
    network.stopSession(session_id, datetime(2026, 1, 1, 14, 0))

    invoice = network.calculateInvoice(session_id)

    assert sum(line.energy for line in invoice.lines) == Decimal("2.000")


def test_calculate_invoice_worked_peak_boundary_example():
    network, session_id = _network_with_session()
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 15, 30), Decimal("0")
    )
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 16, 30), Decimal("40")
    )
    network.stopSession(session_id, datetime(2026, 1, 1, 16, 30))

    invoice = network.calculateInvoice(session_id)

    assert [line.energy for line in invoice.lines] == [
        Decimal("20.000"),
        Decimal("20.000"),
    ]
    assert [line.rate for line in invoice.lines] == [
        Decimal("0.28"),
        Decimal("0.42"),
    ]
    assert [line.amount for line in invoice.lines] == [
        Decimal("5.60"),
        Decimal("8.40"),
    ]
    assert sum(line.amount for line in invoice.lines) == Decimal("14.00")
    assert invoice.total == Decimal("15.00")


def test_invoice_rounds_energy_half_up_at_invoice_level():
    network, session_id = _network_with_session()
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 12, 0), Decimal("0")
    )
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 13, 0), Decimal("1.2345")
    )
    network.stopSession(session_id, datetime(2026, 1, 1, 13, 0))

    invoice = network.calculateInvoice(session_id)

    assert invoice.lines[0].energy == Decimal("1.235")
    assert invoice.lines[0].amount == Decimal("0.35")


def test_invoice_rounds_line_amount_half_up_at_invoice_level():
    network, session_id = _network_with_session()
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 12, 0), Decimal("0")
    )
    network.recordMeterReading(
        session_id, datetime(2026, 1, 1, 13, 0), Decimal("0.125")
    )
    network.stopSession(session_id, datetime(2026, 1, 1, 13, 0))

    invoice = network.calculateInvoice(session_id)

    assert invoice.lines[0].energy == Decimal("0.125")
    assert invoice.lines[0].amount == Decimal("0.04")