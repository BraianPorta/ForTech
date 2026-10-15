"""Métricas del jugador y persistencia CSV, independientes de Qt y de la física."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable
from uuid import uuid4

import pandas as pd

CATALOG = {"R": (330, 680, 1000, 1500, 2200, 3300),
           "C": (100, 220, 330, 470, 560, 1000)}
PROGRESS_COLUMNS = ["partida_id", "fecha_utc", "reto_id", "dispositivo",
                    "tiempo_s", "cambios_r", "cambios_c", "cambios_total", "pruebas"]


@dataclass
class GameSession:
    """Cronómetro por misión; solo cuentan sustituciones de valor efectivas.

    El tiempo continúa al consultar ayuda o estadísticas. Se detiene al resolver
    la misión. Reiniciar crea una sesión nueva y descarta la no completada.
    """

    challenge_id: str
    device: str
    clock: Callable[[], float] = field(default=perf_counter, repr=False)
    changes: dict = field(default_factory=lambda: {"R": 0, "C": 0})
    attempts: int = 0
    finished: float | None = None
    identifier: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        self.started = self.clock()

    @property
    def elapsed(self) -> float:
        return max(0.0, (self.clock() if self.finished is None else self.finished) - self.started)

    @property
    def total_changes(self) -> int:
        return sum(self.changes.values())

    def change(self, kind: str, old: float, new: float) -> bool:
        """Rechaza valores fuera del catálogo; no cuenta reseleccionar la misma pieza."""
        if kind not in CATALOG or new not in CATALOG[kind]:
            raise ValueError("El componente debe pertenecer al catálogo del nivel.")
        if self.finished is not None or old == new:
            return False
        self.changes[kind] += 1
        return True

    def complete(self) -> dict:
        """Congela el tiempo y construye la fila de estadísticas de esta partida."""
        if self.finished is None:
            self.finished = self.clock()
        return dict(zip(PROGRESS_COLUMNS, [
            self.identifier, datetime.now(timezone.utc).isoformat(),
            self.challenge_id, self.device, round(self.elapsed, 3),
            self.changes["R"], self.changes["C"], self.total_changes, self.attempts,
        ]))


class ProgressStore:
    """Historial de misiones resueltas, con guardado atómico y sin duplicados."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.records = []
        if self.path.exists():
            frame = pd.read_csv(self.path)
            if not set(PROGRESS_COLUMNS).issubset(frame.columns):
                raise ValueError("El historial no tiene el formato de progreso esperado.")
            self.records = frame[PROGRESS_COLUMNS].to_dict("records")

    def append(self, record: dict) -> None:
        if any(row["partida_id"] == record["partida_id"] for row in self.records):
            return
        rows = [*self.records, record]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            pd.DataFrame(rows, columns=PROGRESS_COLUMNS).to_csv(
                temporary, index=False, encoding="utf-8-sig")
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.records = rows
