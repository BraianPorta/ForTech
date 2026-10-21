"""Métricas del jugador y persistencia CSV, independientes de Qt y de la física."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Callable
from uuid import uuid4

from data import PROGRESS_COLUMNS

CATALOG = {"R": (330, 680, 1000, 1500, 2200, 3300),
           "C": (100, 220, 330, 470, 560, 1000)}


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
