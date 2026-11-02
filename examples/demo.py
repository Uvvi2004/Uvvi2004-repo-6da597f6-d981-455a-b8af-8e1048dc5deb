from datetime import datetime
from decimal import Decimal

from ev_billing.network import ChargingNetwork


def add_session(
    network: ChargingNetwork,
    driver_id: str,
    charger_id: str,
    readings: list[tuple[datetime, str]],
    stopped_at: datetime,
) -> str:
    session_id = network.startSession(
        driver_id,
        charger_id,
        min(timestamp for timestamp, _ in readings),
    )
    for timestamp, cumulative_kwh in readings:
        network.recordMeterReading(
            session_id, timestamp, Decimal(cumulative_kwh)
        )
    network.stopSession(session_id, stopped_at)
    return session_id


def print_invoice(network: ChargingNetwork, session_id: str) -> None:
    session = network.sessions[session_id]
    invoice = network.calculateInvoice(session_id)

    print(f"Session: {session_id}")
    print(f"  Charger: {session.charger_id}")
    for line in invoice.lines:
        print(
            f"  Line {line.start_time} - {line.end_time}: "
            f"{line.energy} kWh at ${line.rate}/kWh = ${line.amount}"
        )
    print(f"  Session fee: ${invoice.session_fee}")
    print(f"  Total: ${invoice.total}")
    print()


def main() -> None:
    network = ChargingNetwork()
    for charger_id, site_id in (
        ("charger-1", "downtown"),
        ("charger-2", "airport"),
        ("charger-3", "highway"),
    ):
        network.registerCharger(charger_id, site_id)

    sessions = [
        add_session(
            network,
            "driver-1",
            "charger-1",
            [
                (datetime(2026, 1, 1, 15, 30), "0"),
                (datetime(2026, 1, 1, 16, 30), "40"),
            ],
            datetime(2026, 1, 1, 16, 30),
        ),
        add_session(
            network,
            "driver-2",
            "charger-2",
            [
                (datetime(2026, 1, 1, 20, 30), "0"),
                (datetime(2026, 1, 1, 21, 30), "12"),
            ],
            datetime(2026, 1, 1, 21, 30),
        ),
        add_session(
            network,
            "driver-3",
            "charger-3",
            [
                (datetime(2026, 1, 1, 21, 30), "0"),
                (datetime(2026, 1, 2, 6, 30), "54"),
            ],
            datetime(2026, 1, 2, 6, 30),
        ),
        add_session(
            network,
            "driver-4",
            "charger-1",
            [
                (datetime(2026, 1, 2, 8, 0), "0"),
                (datetime(2026, 1, 2, 9, 0), "10"),
            ],
            datetime(2026, 1, 2, 9, 0),
        ),
        add_session(
            network,
            "driver-5",
            "charger-2",
            [
                (datetime(2026, 1, 2, 10, 0), "0"),
                (datetime(2026, 1, 2, 11, 0), "7.5"),
            ],
            datetime(2026, 1, 2, 11, 0),
        ),
        add_session(
            network,
            "driver-6",
            "charger-3",
            [
                (datetime(2026, 1, 2, 17, 0), "0"),
                (datetime(2026, 1, 2, 18, 0), "8"),
            ],
            datetime(2026, 1, 2, 18, 0),
        ),
        add_session(
            network,
            "driver-7",
            "charger-1",
            [
                (datetime(2026, 1, 3, 22, 30), "0"),
                (datetime(2026, 1, 3, 23, 30), "6"),
            ],
            datetime(2026, 1, 3, 23, 30),
        ),
        add_session(
            network,
            "driver-8",
            "charger-2",
            [
                (datetime(2026, 1, 4, 11, 0), "8"),
                (datetime(2026, 1, 4, 10, 0), "10"),
                (datetime(2026, 1, 4, 12, 0), "14"),
            ],
            datetime(2026, 1, 4, 12, 0),
        ),
    ]

    print(f"Registered chargers: {len(network.chargers)}")
    print(f"Charging sessions: {len(sessions)}")
    print()
    for session_id in sessions:
        print_invoice(network, session_id)


if __name__ == "__main__":
    main()