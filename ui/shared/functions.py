"""Ecuaciones y cálculos científicos utilizados por los ejercicios."""
from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from data import Challenge

RESISTANCE_CANDIDATES = (330, 680, 1000, 1500, 2200, 3300)


@dataclass(frozen=True)
class Simulation:
    """Resultado calculado del circuito y comparación con el objetivo."""

    measured_value: float
    target_value: float
    unit: str = "Ω"

    @property
    def passed(self) -> bool:
        """Aplica una tolerancia numérica a la resistencia equivalente."""
        return abs(self.measured_value - self.target_value) <= max(
            1e-6, abs(self.target_value) * 1e-6
        )


def calculate_equivalent_resistance(rows: Sequence[Sequence[float]]) -> float:
    """Suma resistencias en serie por fila y combina las filas en paralelo."""
    if not 1 <= len(rows) <= 3:
        raise ValueError("El circuito debe tener entre 1 y 3 filas en paralelo.")
    branch_resistances = []
    for row in rows:
        if not row:
            raise ValueError("Cada fila debe contener al menos una resistencia.")
        if not all(isfinite(value) and value > 0 for value in row):
            raise ValueError("Las resistencias deben ser positivas y finitas.")
        branch_resistances.append(sum(row))
    return 1 / sum(1 / resistance for resistance in branch_resistances)


def simulate(
    challenge: Challenge,
    rows: Sequence[Sequence[float]],
) -> Simulation:
    """Calcula la resistencia equivalente de las piezas elegidas por el jugador."""
    result = calculate_equivalent_resistance(rows)
    return Simulation(result, challenge.result)


def initial_configuration(challenge: Challenge) -> list[list[float]]:
    """Genera valores iniciales distintos de los correctos y del resultado."""
    correct = [
        [component.correct_value for component in branch]
        for branch in challenge.rows
    ]
    current = [
        [
            RESISTANCE_CANDIDATES[
                (RESISTANCE_CANDIDATES.index(value) + 1) % len(RESISTANCE_CANDIDATES)
            ]
            for value in branch
        ]
        for branch in correct
    ]
    if not Simulation(calculate_equivalent_resistance(current), challenge.result).passed:
        return current

    for row_index, branch in enumerate(correct):
        for component_index, correct_value in enumerate(branch):
            for candidate in RESISTANCE_CANDIDATES:
                if candidate == correct_value:
                    continue
                alternative = [values[:] for values in current]
                alternative[row_index][component_index] = candidate
                if not Simulation(
                    calculate_equivalent_resistance(alternative),
                    challenge.result,
                ).passed:
                    return alternative
    raise ValueError(
        f"No se pueden generar valores iniciales incorrectos para la dificultad "
        f"{challenge.difficulty}."
    )
