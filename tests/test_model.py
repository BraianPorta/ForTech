"""Verificación del método numérico frente a la solución analítica del RC."""
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from scientific_model import load_challenges, save_simulation, simulate

ROOT = Path(__file__).resolve().parents[1]


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.challenge = load_challenges(ROOT / "data" / "retos.csv")[0]
        (ROOT / "output").mkdir(exist_ok=True)

    def test_numerical_solution_matches_analytical_curve(self):
        result = simulate(self.challenge, 1000, 470)
        expected = 5 * (1 - np.exp(-result.time / 0.47))
        np.testing.assert_allclose(result.voltage, expected, atol=2e-8)
        self.assertAlmostEqual(result.measured_voltage, 5 * (1 - np.exp(-0.6 / 0.47)), places=7)
        self.assertTrue(np.all(np.diff(result.voltage) >= -1e-8))
        self.assertFalse(result.passed)

    def test_demonstration_solution_passes(self):
        result = simulate(self.challenge, 1000, 560)
        self.assertTrue(result.passed)
        self.assertAlmostEqual(result.tau, 0.56)

    def test_export_contains_reproducible_parameters(self):
        result = simulate(self.challenge, 1000, 560)
        with tempfile.TemporaryDirectory(dir=ROOT / "output") as folder:
            path = Path(folder) / "resultado.csv"
            save_simulation(path, result, self.challenge, 1000, 560)
            frame = pd.read_csv(path)
            self.assertEqual(len(frame), 600)
            self.assertTrue(frame["cumple_objetivo"].all())
            self.assertEqual(frame["capacidad_uf"].iloc[0], 560)
            np.testing.assert_allclose(frame["voltaje_v"], result.voltage)

    def test_rejects_invalid_csv_and_nonphysical_values(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "output") as folder:
            path = Path(folder) / "invalido.csv"
            path.write_text("id,nombre\n1,ejemplo\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Faltan columnas"):
                load_challenges(path)
        for resistance, capacity in [(0, 470), (-1, 470), (1000, float("nan"))]:
            with self.assertRaises(ValueError):
                simulate(self.challenge, resistance, capacity)

    def test_extreme_valid_time_scales_remain_finite(self):
        for resistance, capacity in [(1, 1), (1e6, 1e6)]:
            result = simulate(self.challenge, resistance, capacity)
            self.assertTrue(np.all(np.isfinite(result.voltage)))
            self.assertGreaterEqual(result.measured_voltage, 0)
            self.assertLessEqual(result.measured_voltage, self.challenge.voltage + 1e-8)


if __name__ == "__main__":
    unittest.main()
