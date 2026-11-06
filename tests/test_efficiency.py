import io
import json
import pathlib
import subprocess
import sys
import unittest

from efficiency import FIELDS, audit, read_intervals

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def example(name):
    with (EXAMPLES / f"{name}.csv").open(newline="", encoding="utf-8") as stream:
        return audit(read_intervals(stream))


class EnergyAuditTests(unittest.TestCase):
    def test_pick_cycle_separate_energy_flows(self):
        r = example("pick-cycle")
        for field, expected in {
            "bus_draw_J": 180, "bus_export_J": 36, "bus_net_draw_J": 144,
            "shaft_delivered_J": 100, "shaft_absorbed_J": 60,
            "zero_shaft_power_draw_J": 30, "unaccounted_boundary_energy_J": 104,
        }.items():
            with self.subTest(field=field):
                self.assertEqual(r[field], expected)
        self.assertAlmostEqual(r["motoring_efficiency"], 2 / 3)
        self.assertAlmostEqual(r["braking_bus_recovery_fraction"], 0.6)
        self.assertEqual(r["mode_seconds"], dict(
            motoring=6, stationary_or_unloaded=5, regenerating=3, braking_no_export=0,
        ))

    def test_standstill_consumes_energy_but_does_no_work(self):
        r = example("hold-only")
        self.assertEqual(r["zero_shaft_power_draw_J"], 24)
        self.assertEqual(r["shaft_delivered_J"], 0)
        self.assertIsNone(r["motoring_efficiency"])
        self.assertIsNone(r["braking_bus_recovery_fraction"])

    def test_duty_weighted_result_is_not_mean_of_row_ratios(self):
        r = example("weighted")
        self.assertAlmostEqual(r["motoring_efficiency"], 0.6)
        self.assertNotAlmostEqual(r["motoring_efficiency"], 0.65)

    def test_nonexporting_brake_counts_in_recovery_denominator(self):
        r = example("braking")
        self.assertEqual(r["shaft_absorbed_J"], 40)
        self.assertEqual(r["bus_export_J"], 12)
        self.assertEqual(r["bus_net_draw_J"], -6)
        self.assertAlmostEqual(r["braking_bus_recovery_fraction"], 0.3)
        self.assertEqual(r["unaccounted_boundary_energy_J"], 34)

    def test_reverse_rotation_can_motor(self):
        r = audit([(2, 24, 1, -1, -8)])
        self.assertEqual(r["shaft_delivered_J"], 16)
        self.assertAlmostEqual(r["motoring_efficiency"], 1 / 3)

    def test_splitting_an_interval_does_not_change_totals(self):
        one = audit([(9, 12, 1.5, 0.5, 12), (2, 12, -0.25, -1, 8)])
        split = audit([(3, 12, 1.5, 0.5, 12), (6, 12, 1.5, 0.5, 12), (2, 12, -0.25, -1, 8)])
        one.pop("intervals")
        split.pop("intervals")
        self.assertEqual(one, split)

    def test_generated_cases_obey_independent_energy_balance(self):
        # Independent analytic oracle: the segment energies are constructed first.
        for j in range(1, 51):
            with self.subTest(j=j):
                motoring_in, motoring_out = 8*j, 6*j
                braking_in, braking_out, hold_in = 4*j, 3*j, j
                rows = [(2, 16, motoring_in/32, 1, motoring_out/2),
                        (4, 16, -braking_out/64, 1, -braking_in/4),
                        (1, 16, hold_in/16, 2, 0)]
                r = audit(rows)
                self.assertEqual(r["bus_draw_J"], 9*j)
                self.assertEqual(r["bus_export_J"], 3*j)
                self.assertEqual(r["unaccounted_boundary_energy_J"], 4*j)
                self.assertAlmostEqual(r["motoring_efficiency"], 0.75)
                self.assertAlmostEqual(r["braking_bus_recovery_fraction"], 0.75)

    def test_rejects_inconsistent_passive_boundary(self):
        for row in [(1, 24, -0.25, 1, 10), (1, 24, -1, -1, 10), (1, 24, 0.25, 1, 10)]:
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, "shaft power exceeds bus power"):
                audit([row])

    def test_rejects_bad_inputs(self):
        for row in [(0, 24, 1, 1, 10), (1, -24, 1, 1, 10), (1, 24, float("nan"), 1, 10)]:
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, "finite values"):
                audit([row])
        with self.assertRaisesRegex(ValueError, "numeric range"):
            audit([(1e100, 1e200, 1e200, 0, 0)])
        with self.assertRaisesRegex(ValueError, "no intervals"):
            audit([])

    def test_csv_reports_bad_headers_columns_and_values(self):
        header = ",".join(FIELDS)
        for text, error in [("oops\n1", "CSV header"), (header+"\n1,2", "5 columns"),
                            (header+"\n1,2,3,x,5", "numeric values")]:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                list(read_intervals(io.StringIO(text)))

    def test_cli_reports_invalid_sign_and_emits_parseable_valid_json(self):
        cmd = [sys.executable, str(ROOT / "efficiency.py")]
        bad = subprocess.run(cmd+[str(EXAMPLES / "invalid-sign.csv")], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(bad.stdout, "")
        self.assertIn("row 2", bad.stderr)
        valid = subprocess.run(cmd+[str(EXAMPLES / "pick-cycle.csv")], check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(valid.stdout)["bus_net_draw_J"], 144)


if __name__ == "__main__":
    unittest.main()
