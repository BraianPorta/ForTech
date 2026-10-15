"""Comprueba que el progreso describe acciones reales y se conserva en CSV."""
from pathlib import Path
import tempfile
import unittest

from game_session import GameSession, ProgressStore

ROOT = Path(__file__).resolve().parents[1]


class SessionTests(unittest.TestCase):
    def test_counts_changes_and_freezes_time(self):
        now = [10.0]
        session = GameSession("RC-01", "Sensor", clock=lambda: now[0])
        self.assertFalse(session.change("C", 470, 470))
        self.assertTrue(session.change("C", 470, 560))
        self.assertTrue(session.change("R", 1000, 680))
        with self.assertRaises(ValueError):
            session.change("R", 680, 1234)
        session.attempts = 2
        now[0] = 25.5
        record = session.complete()
        now[0] = 100
        self.assertEqual(session.elapsed, 15.5)
        self.assertEqual(record["cambios_total"], 2)
        self.assertEqual(record["cambios_r"], 1)
        self.assertEqual(record["pruebas"], 2)
        self.assertFalse(session.change("C", 560, 470))

    def test_history_survives_reload_without_duplicate_completion(self):
        (ROOT / "output").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "output") as folder:
            path = Path(folder) / "progreso.csv"
            store = ProgressStore(path)
            session = GameSession("RC-01", "Sensor")
            record = session.complete()
            store.append(record)
            store.append(record)
            restored = ProgressStore(path)
            self.assertEqual(len(restored.records), 1)
            self.assertEqual(restored.records[0]["reto_id"], "RC-01")


if __name__ == "__main__":
    unittest.main()
