"""Audit interval energy at the DC input and mechanical output of one actuator."""

import argparse
import csv
import json
import math

FIELDS = ("duration_s", "bus_voltage_V", "bus_current_A", "torque_Nm", "speed_rad_s")
CATEGORIES = ("motoring", "stationary_or_unloaded", "regenerating", "braking_no_export")


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def audit(rows):
    draw, export, delivered, absorbed, motoring_draw, hold_draw, losses = ([] for _ in range(7))
    durations = {key: [] for key in CATEGORIES}
    for row_number, values in enumerate(rows, start=2):
        duration, voltage, current, torque, speed = values
        if not all(math.isfinite(value) for value in values) or duration <= 0 or voltage <= 0:
            raise ValueError(f"row {row_number}: require finite values and positive duration and voltage")
        bus = voltage * current
        shaft = torque * speed
        bus_j = bus * duration
        shaft_j = shaft * duration
        loss = bus_j - shaft_j
        if not all(map(math.isfinite, (bus_j, shaft_j, loss))):
            raise ValueError(f"row {row_number}: power or interval energy exceeds numeric range")
        if loss < 0:
            raise ValueError(
                f"row {row_number}: shaft power exceeds bus power; check signs, units, "
                "alignment and whether stored energy changed"
            )
        if shaft > 0:
            mode = "motoring"
            motoring_draw.append(bus_j)
        elif shaft == 0:
            mode = "stationary_or_unloaded"
            hold_draw.append(bus_j)
        elif bus < 0:
            mode = "regenerating"
        else:
            mode = "braking_no_export"
        durations[mode].append(duration)
        draw.append(max(bus_j, 0.0))
        export.append(max(-bus_j, 0.0))
        delivered.append(max(shaft_j, 0.0))
        absorbed.append(max(-shaft_j, 0.0))
        losses.append(loss)
    if not draw:
        raise ValueError("no intervals found")
    used, returned, work, brake = map(math.fsum, (draw, export, delivered, absorbed))
    return {
        "intervals": len(draw),
        "mode_seconds": {mode: math.fsum(seconds) for mode, seconds in durations.items()},
        "bus_draw_J": used,
        "bus_export_J": returned,
        "bus_net_draw_J": used - returned,
        "shaft_delivered_J": work,
        "shaft_absorbed_J": brake,
        "zero_shaft_power_draw_J": math.fsum(hold_draw),
        "motoring_efficiency": ratio(work, math.fsum(motoring_draw)),
        "braking_bus_recovery_fraction": ratio(returned, brake),
        "unaccounted_boundary_energy_J": math.fsum(losses),
    }


def read_intervals(stream):
    rows = csv.reader(stream, strict=True)
    if tuple(next(rows, ())) != FIELDS:
        raise ValueError("CSV header must be: " + ",".join(FIELDS))
    for line_number, row in enumerate(rows, start=2):
        if len(row) != len(FIELDS):
            raise ValueError(f"row {line_number}: expected {len(FIELDS)} columns")
        try:
            yield tuple(float(value) for value in row)
        except ValueError:
            raise ValueError(f"row {line_number}: expected numeric values") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="UTF-8 interval CSV; columns and signs are documented in README.md")
    args = parser.parse_args()
    try:
        with open(args.csv_path, encoding="utf-8-sig", newline="") as stream:
            result = audit(read_intervals(stream))
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError, OverflowError, csv.Error) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
