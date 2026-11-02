from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class Charger:
    """A charger that can provide energy to a vehicle."""

    charger_id: str
    site_id: str


@dataclass
class MeterReading:
    """A meter reading recorded during a charging session."""

    timestamp: datetime
    cumulative_kwh: Decimal


@dataclass
class BillingInterval:
    """A period billed at one tariff rate."""

    start_time: datetime
    end_time: datetime
    energy: Decimal
    rate: Decimal


@dataclass
class InvoiceLine:
    """A rounded billing interval line."""

    start_time: datetime
    end_time: datetime
    energy: Decimal
    rate: Decimal
    amount: Decimal


@dataclass
class Invoice:
    """An invoice for a completed charging session."""

    session_id: str
    lines: list[InvoiceLine] = field(default_factory=list)
    session_fee: Decimal = Decimal("1.00")
    total: Decimal = Decimal("0.00")


@dataclass
class ChargingSession:
    """A charging session and its readings in insertion order."""

    session_id: str
    charger_id: str
    driver_id: str
    started_at: datetime
    stopped_at: datetime | None = None
    meter_readings: list[MeterReading] = field(default_factory=list)
    replacement_count: int = 0
    status: str = "running"
    