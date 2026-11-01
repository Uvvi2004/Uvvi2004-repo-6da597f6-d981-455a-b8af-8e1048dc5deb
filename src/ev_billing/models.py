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
class ChargingSession:
    """A charging session and its readings in insertion order."""

    session_id: str
    charger_id: str
    driver_id: str
    started_at: datetime
    stopped_at: datetime | None = None
    meter_readings: list[MeterReading] = field(default_factory=list)
    status: str = "running"
    