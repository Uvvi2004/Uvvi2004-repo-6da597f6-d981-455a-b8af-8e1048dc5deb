from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from .models import Charger, ChargingSession, MeterReading


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

        session.stopped_at = stopped_at
        session.status = "stopped"