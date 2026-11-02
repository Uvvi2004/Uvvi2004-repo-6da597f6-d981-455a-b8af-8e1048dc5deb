from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from .billing import build_billing_intervals, prepare_meter_readings
from .models import Charger, ChargingSession, Invoice, InvoiceLine, MeterReading


class ChargingNetwork:
    """Registry of chargers and charging sessions."""

    def __init__(self) -> None:
        self.chargers: dict[str, Charger] = {}
        self.sessions: dict[str, ChargingSession] = {}

    def registerCharger(self, charger_id: str, site_id: str) -> Charger:
        """Register a charger by its identifier."""
        if charger_id in self.chargers:
            raise ValueError(f"Charger already registered: {charger_id}")

        charger = Charger(
            charger_id = charger_id,
            site_id = site_id
        )

        self.chargers[charger_id] = charger
        return charger

    def startSession(
        self,
        driver_id: str,
        charger_id: str,
        started_at: datetime,
    ) -> str:
        """Create and store a running session for a registered charger."""
        if charger_id not in self.chargers:
            raise ValueError(f"Charger is not registered: {charger_id}")

        session_id = str(uuid4())
        session = ChargingSession(
            session_id=session_id,
            charger_id=charger_id,
            driver_id=driver_id,
            started_at=started_at,
        )
        self.sessions[session_id] = session
        return session_id

    def recordMeterReading(
        self,
        session_id: str,
        at: datetime,
        cumulative_Kwh: Decimal,
    ) -> MeterReading:
        """Record or replace a meter reading for a charging session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session is not registered: {session_id}")

        session = self.sessions[session_id]
        if session.status == "stopped":
            raise ValueError(f"Session is already stopped: {session_id}")
        if at < session.started_at:
            raise ValueError("Meter reading cannot be before session start")
        if session.stopped_at is not None and at > session.stopped_at:
            raise ValueError("Meter reading cannot be after session stop")

        reading = MeterReading(timestamp=at, cumulative_kwh=cumulative_Kwh)
        for index, existing in enumerate(session.meter_readings):
            if existing.timestamp == at:
                session.meter_readings[index] = reading
                session.replacement_count += 1
                return reading

        session.meter_readings.append(reading)
        return reading

    def stopSession(self, session_id: str, stopped_at: datetime) -> None:
        """Stop a session at the given time."""
        if session_id not in self.sessions:
            raise ValueError(f"Session is not registered: {session_id}")

        session = self.sessions[session_id]
        if stopped_at < session.started_at:
            raise ValueError("Session cannot stop before it starts")

        session.meter_readings = [
            reading
            for reading in session.meter_readings
            if reading.timestamp <= stopped_at
        ]
        session.stopped_at = stopped_at
        session.status = "stopped"

    def calculateInvoice(self, session_id: str) -> Invoice:
        """Calculate an invoice for a stopped charging session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session is not registered: {session_id}")

        session = self.sessions[session_id]
        if session.status != "stopped":
            raise ValueError(f"Session has not stopped: {session_id}")

        readings = prepare_meter_readings(session.meter_readings)
        intervals = build_billing_intervals(readings)
        lines: list[InvoiceLine] = []
        subtotal = Decimal("0.00")

        for interval in intervals:
            energy = interval.energy.quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP
            )
            amount = (energy * interval.rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            lines.append(
                InvoiceLine(
                    start_time=interval.start_time,
                    end_time=interval.end_time,
                    energy=energy,
                    rate=interval.rate,
                    amount=amount,
                )
            )
            subtotal += amount

        session_fee = Decimal("1.00")
        return Invoice(
            session_id=session_id,
            lines=lines,
            session_fee=session_fee,
            total=subtotal + session_fee,
        )