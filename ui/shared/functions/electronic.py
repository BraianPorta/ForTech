"""Ecuaciones y cálculos científicos utilizados por los ejercicios."""
# ---------------------------------------------------------------
# 1. LIBRERÍAS Y MODELO DE RESULTADO COMPARTIDO
# ---------------------------------------------------------------
from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from data import Challenge, CircuitComponent


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


# ---------------------------------------------------------------
# 2. ELECTRÓNICA: CATÁLOGOS Y CÁLCULOS
# ---------------------------------------------------------------
# Catálogos de resistencias, potencias y resistencias nominales de bombilla.
RESISTANCE_CANDIDATES = (330, 680, 1000, 1500, 2200, 3300)
BULB_POWER_CANDIDATES = (3, 6, 12)
BULB_RESISTANCE_CANDIDATES = (12, 24, 48)


# Calcula primero cada rama en serie y después combina las ramas en paralelo.
def calculateEquivalentResistance(rows: Sequence[Sequence[float]]) -> float:
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


# Convierte la potencia de cada bombilla a resistencia mediante R = V²/P.
def challengeResistance(
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
            elif component.kind == "bombilla_ohm":
                resistance_branch.append(component.correct_value)
            else:
                raise ValueError(f"Tipo de componente no admitido: {component.kind}")
        resistance_rows.append(resistance_branch)
    return calculateEquivalentResistance(resistance_rows)


# Compara la configuración elegida con la resistencia objetivo del reto.
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
    equivalent_resistance = challengeResistance(
        [
            [
                CircuitComponent(component.kind, value)
                for component, value in zip(branch, selected_values)
            ]
            for branch, selected_values in zip(challenge.rows, rows)
        ],
        challenge.voltage,
    )
    measured_value = equivalent_resistance
    if challenge.result_unit == "W":
        if challenge.voltage is None:
            raise ValueError("El cálculo de potencia requiere una tensión de alimentación.")
        measured_value = challenge.voltage ** 2 / equivalent_resistance
    passed = None
    if challenge.result_min is not None and challenge.result_max is not None:
        passed = challenge.result_min <= measured_value <= challenge.result_max
    return Simulation(
        measured_value,
        challenge.result,
        challenge.result_unit,
        passed_override=passed,
    )
