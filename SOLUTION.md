# EV Billing

## Architecture

- `src/ev_billing/models.py` defines the dataclasses: `Charger`,
  `MeterReading`, `ChargingSession`, `BillingInterval`, `InvoiceLine`, and
  `Invoice`.
- `src/ev_billing/network.py` provides `ChargingNetwork`, which registers
  chargers, manages sessions and readings, stops sessions, and calculates
  invoices.
- `src/ev_billing/tariffs.py` maps a timestamp to a `Decimal` per-kWh rate.
- `src/ev_billing/billing.py` prepares readings and creates tariff-split
  billing intervals.
- `examples/demo.py` demonstrates three chargers, eight sessions, tariff
  boundaries, midnight crossing, rollback filtering, and invoice output.
- `tests/test_billing.py` contains the pytest coverage.

## Installation, tests, and demo

Python 3.10 or newer is supported. From the project root:

```powershell
python -m pip install -r requirements.txt
python -m pytest
$env:PYTHONPATH = "src"
python .\examples\demo.py
```

The `src` layout and pytest settings are configured in `pyproject.toml`.

## Tariffs and billing

Rates use half-open time ranges:

| Period | Time | Rate |
|---|---|---:|
| Off-peak | 22:00–06:00 | $0.18/kWh |
| Mid-peak | 06:00–16:00 and 21:00–22:00 | $0.28/kWh |
| Peak | 16:00–21:00 | $0.42/kWh |

Consecutive valid cumulative readings define an interval. Power is assumed
constant between readings, so energy is allocated proportionally by elapsed
time. Intervals split at readings and tariff boundaries; midnight alone is
not a split point.

Invoice generation prepares readings, builds intervals, rounds each line's
energy to three decimal places using `Decimal` `ROUND_HALF_UP`, calculates
the line amount from that rounded energy and rate, and rounds the amount to
two decimal places with the same mode. Rounded line amounts are summed and a
fixed `$1.00` session fee is added. No energy is estimated after the last
valid reading.

## Meter reading rules

`recordMeterReading()` rejects unknown sessions, readings before session
start, readings after the stop time, and readings for stopped sessions.
Readings are retained in insertion order. A reading with an existing
timestamp replaces that entry and increments `replacement_count`.

`stopSession()` rejects unknown sessions and stop times before the session
start. Invalid stops leave the session unchanged. A valid stop removes
readings later than the stop time and changes the status to `"stopped"`.

Invoice preparation sorts a copy of the session readings by timestamp and
discards cumulative-kWh rollbacks. Each candidate is compared with the last
accepted reading, and the original list is not modified. Rollback validation
is intentionally handled during invoice preparation rather than by
`recordMeterReading()`.

## Important choices and assumptions

- `Decimal` is used for meter values, rates, amounts, and fees; binary floats
  are not used for billing calculations.
- Meter readings are assumed to have comparable timestamps and cumulative
  kWh values. Billing preparation assumes readings are chronologically sorted
  after preprocessing.
- Sessions with fewer than two valid readings produce no energy lines but
  still receive the `$1.00` session fee.
- Invoice generation is available only after a session is stopped.