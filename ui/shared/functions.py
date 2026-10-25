"""Ecuaciones y cálculos científicos utilizados por los ejercicios."""
from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from data import Challenge, CircuitComponent

RESISTANCE_CANDIDATES = (330, 680, 1000, 1500, 2200, 3300)
BULB_POWER_CANDIDATES = (3, 6, 12)


@dataclass(frozen=True)
class Simulation:
    """Resultado calculado del circuito y comparación con el objetivo."""

    measured_value: float
    target_value: float
    unit: str = "Ω"
    passed_override: bool | None = None

    @property
    def passed(self) -> bool:
        """Aplica una tolerancia numérica a la resistencia equivalente."""
        if self.passed_override is not None:
            return self.passed_override
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


def challenge_resistance(
    rows: Sequence[Sequence[CircuitComponent]],
    voltage: float | None,
) -> float:
    """Calcula la resistencia equivalente de las resistencias o bombillas elegidas."""
    resistance_rows: list[list[float]] = []
    for branch in rows:
        resistance_branch = []
        for component in branch:
            if component.kind == "ohm":
                resistance_branch.append(component.correct_value)
            elif component.kind == "bombilla":
                if voltage is None:
                    raise ValueError("El reto de bombillas requiere una tensión de alimentación.")
                resistance_branch.append(voltage ** 2 / component.correct_value)
            else:
                raise ValueError(f"Tipo de componente no admitido: {component.kind}")
        resistance_rows.append(resistance_branch)
    return calculate_equivalent_resistance(resistance_rows)


def simulate(
    challenge: Challenge,
    rows: Sequence[Sequence[float]],
) -> Simulation:
    """Calcula la resistencia equivalente de las piezas elegidas por el jugador."""
    if len(rows) != len(challenge.rows) or any(
        len(values) != len(components)
        for values, components in zip(rows, challenge.rows)
    ):
        raise ValueError("La configuración no coincide con los componentes del reto.")
    result = challenge_resistance(
        [
            [
                CircuitComponent(component.kind, value)
                for component, value in zip(branch, selected_values)
            ]
            for branch, selected_values in zip(challenge.rows, rows)
        ],
        challenge.voltage,
    )
    return Simulation(result, challenge.result)


def initial_configuration(challenge: Challenge) -> list[list[float]]:
    """Genera valores iniciales distintos de los correctos y del resultado."""
    catalogs = {
        "ohm": RESISTANCE_CANDIDATES,
        "bombilla": BULB_POWER_CANDIDATES,
    }
    correct = [[component.correct_value for component in branch] for branch in challenge.rows]
    current = []
    for branch in challenge.rows:
        current.append([
            catalogs[component.kind][
                (catalogs[component.kind].index(component.correct_value) + 1)
                % len(catalogs[component.kind])
            ]
            for component in branch
        ])
    if not Simulation(
        challenge_resistance(
            [
                [
                    CircuitComponent(component.kind, value)
                    for component, value in zip(branch, values)
                ]
                for branch, values in zip(challenge.rows, current)
            ],
            challenge.voltage,
        ),
        challenge.result,
    ).passed:
        return current

    for row_index, branch in enumerate(correct):
        for component_index, correct_value in enumerate(branch):
            component = challenge.rows[row_index][component_index]
            for candidate in catalogs[component.kind]:
                if candidate == correct_value:
                    continue
                alternative = [values[:] for values in current]
                alternative[row_index][component_index] = candidate
                if not Simulation(
                    challenge_resistance(
                        [
                            [
                                CircuitComponent(item.kind, value)
                                for item, value in zip(component_branch, values)
                            ]
                            for component_branch, values in zip(challenge.rows, alternative)
                        ],
                        challenge.voltage,
                    ),
                    challenge.result,
                ).passed:
                    return alternative
    raise ValueError(
        f"No se pueden generar valores iniciales incorrectos para la dificultad "
        f"{challenge.difficulty}."
    )
