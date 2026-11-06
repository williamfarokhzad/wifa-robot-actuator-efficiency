# Robot actuator efficiency from a DC energy log

Audit a simulated robot actuator with no hardware or external Python packages. The script separates electrical draw, bus export, shaft work, and energy drawn at zero shaft power. It compares energy totals over a cycle instead of averaging efficiency percentages.

[Full WIFA tutorial: Robot actuator efficiency from a DC energy log](https://wifarobotics.com/learn/robot-actuator-efficiency/)

## Start here

1. Install Python 3.12 or newer from [python.org](https://www.python.org/downloads/). On Windows, verify with `py -3 --version`; on Linux or macOS, use `python3 --version`.
2. On the GitHub repository page, choose **Code → Download ZIP** and extract it. Or clone with `git clone https://github.com/williamfarokhzad/wifa-robot-actuator-efficiency.git`.
3. Open a terminal in the extracted project folder (the folder containing `efficiency.py`). The examples work offline. Use `py -3` instead of `python3` on Windows.
4. Run one case and then the tests:

```sh
python3 efficiency.py examples/pick-cycle.csv
python3 -m unittest discover -s tests -v
```

## Examples to try

| Command after `python3 efficiency.py` | What to verify |
| --- | --- |
| `examples/pick-cycle.csv` | 180 J drawn, 36 J exported, 144 J net drawn; motoring efficiency 0.6667. |
| `examples/hold-only.csv` | 24 J drawn and no shaft work; motoring efficiency is JSON `null`. |
| `examples/weighted.csv` | Motoring efficiency 0.60; the unweighted mean of the two interval efficiencies is 0.65. |
| `examples/braking.csv` | 40 J of mechanical energy absorbed; 12 J exported; recovery fraction 0.30. |
| `examples/invalid-sign.csv` | Exit code 2 and a row 2 error because the shaft delivers power while the bus receives power. |

Copy an example before editing it. Each CSV row is one constant interval, and the five headers are:

```csv
duration_s,bus_voltage_V,bus_current_A,torque_Nm,speed_rad_s
4,24,1.25,2,10
```

Use seconds, volts, amps, newton metres and radians per second. Convert rpm to rad/s by multiplying by 2π/60. Voltage is positive; current is positive into the drive and negative out of it. Torque is exerted by the actuator on the load, and speed and torque use the same positive rotation direction. A torque sensor with the opposite convention must be reinterpreted before export. Use one joint output boundary and one actuator DC input boundary throughout.

## Interpret the results

Electrical power is voltage × current. Mechanical power is torque × angular velocity. Multiply each by the interval duration to get joules. `motoring_efficiency` is the positive shaft energy divided by the DC draw in the same motoring intervals. `braking_bus_recovery_fraction` divides the exported DC energy by all absorbed shaft energy, including intervals with no export. Neither ratio exists with a zero denominator. Bus export may charge a capacitor, feed another drive, or be dissipated; it is not proof of battery charging.

`unaccounted_boundary_energy_J` is the net DC input minus the net shaft output. The model assumes negligible change in internal energy storage within every interval. Under that assumption this difference is loss inside the chosen boundary. The script rejects inconsistent rows; it never clamps them to fabricate plausible efficiency. Real measurements require synchronized calibrated power channels and a storage model or steady state windows. The tool does not size wiring, brakes, motors or protective equipment.

## Troubleshooting

If Python cannot find `efficiency.py`, confirm the terminal is inside the extracted project folder. For a header error, compare column spelling and save a comma separated UTF-8 file. If power seems too large by about 9.55×, check whether rpm was passed as rad/s. If a row violates the power balance, check signs, alignment, sensor offsets, unit scaling and changing stored energy before using any result. Do not remove or relabel a real interval solely to make the audit pass.

The two original diagrams and their editable SVG files are in `diagrams/`. The worked numbers are invented for teaching and verified in the tests; no physical motor or controller was tested.
