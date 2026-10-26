"""Métricas del jugador y persistencia CSV, independientes de Qt y de la física."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from time import perf_counter
from typing import Callable
from uuid import uuid4

from data import PROGRESS_COLUMNS
from ui.shared.functions.electronic import (
    BULB_POWER_CANDIDATES,
    BULB_RESISTANCE_CANDIDATES,
    RESISTANCE_CANDIDATES,
)

# Catálogos usados para validar las elecciones de los componentes.
CATALOG = {
    "R": RESISTANCE_CANDIDATES,
    "B": BULB_POWER_CANDIDATES,
    "BΩ": BULB_RESISTANCE_CANDIDATES,
}


@dataclass
class GameSession:
    """Cronómetro por misión; solo cuentan sustituciones de valor efectivas.

    El tiempo continúa al consultar ayuda o estadísticas. Se detiene al resolver
    la misión. Reiniciar crea una sesión nueva y descarta la no completada.
    """

    difficulty: int
    device: str
    clock: Callable[[], float] = field(default=perf_counter, repr=False)
    changes: dict = field(default_factory=lambda: {"R": 0, "C": 0, "B": 0, "P": 0})
    attempts: int = 0
    finished: float | None = None
    paused_at: float | None = field(default=None, init=False)
    paused_duration: float = field(default=0.0, init=False)
    identifier: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        """Registra el instante inicial del cronómetro de la misión."""
        self.started = self.clock()

    @property
    def elapsed(self) -> float:
        """Devuelve el tiempo activo, excluyendo pausas y respetando el fin."""
        stop = self.finished
        if stop is None:
            stop = self.paused_at if self.paused_at is not None else self.clock()
        return max(0.0, stop - self.started - self.paused_duration)

    def pause(self) -> None:
        """Detiene temporalmente el cronómetro si la misión sigue activa."""
        if self.finished is None and self.paused_at is None:
            self.paused_at = self.clock()

    def resume(self) -> None:
        """Reanuda el cronómetro y acumula la duración de la pausa."""
        if self.finished is None and self.paused_at is not None:
            self.paused_duration += self.clock() - self.paused_at
            self.paused_at = None

    @property
    def totalChanges(self) -> int:
        """Suma los cambios realizados en todos los tipos de componente."""
        return sum(self.changes.values())

    def change(self, kind: str, old: float | None, new: float) -> bool:
        """Valida el valor elegido y cuenta cada selección o cambio efectivo."""
        valid_parameter = kind == "P" and isfinite(new) and new > 0
        if not valid_parameter and (kind not in CATALOG or new not in CATALOG[kind]):
            raise ValueError("El componente debe pertenecer al catálogo del nivel.")
        if self.finished is not None or old == new:
            return False
        change_kind = "B" if kind == "BΩ" else kind
        self.changes[change_kind] += 1
        return True

    def complete(self) -> dict:
        """Congela el tiempo y construye la fila de estadísticas de esta partida."""
        if self.finished is None:
            self.finished = self.paused_at if self.paused_at is not None else self.clock()
        return dict(zip(PROGRESS_COLUMNS, [
            self.identifier, datetime.now(timezone.utc).isoformat(),
            self.difficulty, self.device, round(self.elapsed, 3),
            self.changes["R"] + self.changes["B"] + self.changes["P"],
            self.changes["C"],
            self.totalChanges, self.attempts,
        ]))
