"""Modelo de carga de un circuito RC ideal, independiente de la interfaz.

Unidades internas: voltios, ohmios, faradios y segundos (SI).
Ecuación: dVc/dt = (Vs - Vc)/(R*C), con Vc(0) = 0.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp


@dataclass(frozen=True)
class Challenge:
    """Especificaciones de un reto; la capacidad de entrada se expresa en µF."""

    identifier: str
    name: str
    voltage: float
    resistance: float
    capacitance_uf: float
    target_voltage: float
    target_time: float
    tolerance: float
    description: str


@dataclass(frozen=True)
class Simulation:
    """Muestras de la simulación, medida de control y criterio de aceptación."""

    time: np.ndarray
    voltage: np.ndarray
    current_ma: np.ndarray
    target_time: float
    measured_voltage: float
    target_voltage: float
    tolerance: float
    tau: float

    @property
    def passed(self) -> bool:
        """Indica si el error absoluto está dentro de la tolerancia."""
        return abs(self.measured_voltage - self.target_voltage) <= self.tolerance


def load_challenges(path: str | Path) -> list[Challenge]:
    """Lee un CSV UTF-8 y valida todas las filas antes de devolver los retos.

    Los identificadores deben ser únicos. Los parámetros físicos deben ser
    finitos y positivos, y la tensión objetivo debe ser menor que la fuente.
    """
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype={"id": str})
    required = ["id", "nombre", "voltaje_v", "resistencia_ohm", "capacidad_uf",
                "objetivo_v", "tiempo_objetivo_s", "tolerancia_v", "descripcion"]
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError("Faltan columnas: " + ", ".join(sorted(missing)))
    if frame.empty:
        raise ValueError("El archivo debe contener al menos un reto.")
    result = []
    identifiers = set()
    for index, row in frame.iterrows():
        try:
            texts = [str(row[k]).strip() if pd.notna(row[k]) else ""
                     for k in ("id", "nombre", "descripcion")]
            if not all(texts):
                raise ValueError("id, nombre y descripcion son obligatorios")
            identifier, name, description = texts
            if identifier in identifiers:
                raise ValueError("identificador duplicado")
            values = [float(row[k]) for k in required[2:8]]
            if not all(np.isfinite(v) and v > 0 for v in values):
                raise ValueError("los valores numéricos deben ser finitos y positivos")
            voltage, resistance, capacity, target, time, tolerance = values
            if target >= voltage:
                raise ValueError("objetivo_v debe ser menor que voltaje_v")
            if not 1 <= resistance <= 1e6 or not 1 <= capacity <= 1e6:
                raise ValueError("R y C deben estar entre 1 y 1000000 (Ω y µF)")
            if not 0.001 <= time <= 1000:
                raise ValueError("tiempo_objetivo_s debe estar entre 0.001 y 1000")
            result.append(Challenge(identifier, name, voltage, resistance,
                                    capacity, target, time, tolerance, description))
            identifiers.add(identifier)
        except (ValueError, TypeError, OverflowError) as error:
            raise ValueError(f"Fila {index + 2}: {error}") from error
    return result


def simulate(challenge: Challenge, resistance: float, capacitance_uf: float) -> Simulation:
    """Integra la carga RC y evalúa el objetivo usando interpolación densa.

    Se integra en tiempo normalizado u=t/(RC), hasta u=40 como máximo;
    después de ese punto la respuesta se considera igual a la fuente a
    precisión de máquina. Esto evita rigidez artificial con escalas extremas.
    """
    if not all(np.isfinite(v) and v > 0 for v in (resistance, capacitance_uf)):
        raise ValueError("La resistencia y la capacidad deben ser positivas y finitas.")
    tau = resistance * capacitance_uf * 1e-6
    duration = max(challenge.target_time * 2.5, tau * 5)
    time = np.linspace(0, duration, 600)
    solution = solve_ivp(lambda _u, v: challenge.voltage - v, (0, 40), [0.0],
                         rtol=1e-9, atol=1e-11, dense_output=True)
    if not solution.success:
        raise RuntimeError("No se ha podido integrar el modelo RC.")
    voltage = solution.sol(np.minimum(time / tau, 40))[0]
    voltage = np.where(time / tau > 40, challenge.voltage, voltage)
    measured = (float(solution.sol(challenge.target_time / tau)[0])
                if challenge.target_time / tau <= 40 else challenge.voltage)
    current = (challenge.voltage - voltage) / resistance * 1000
    return Simulation(time, voltage, current, challenge.target_time, measured,
                      challenge.target_voltage, challenge.tolerance, tau)


def save_simulation(path: str | Path, result: Simulation, challenge: Challenge,
                    resistance: float, capacitance_uf: float) -> None:
    """Exporta muestras y parámetros suficientes para reproducir el resultado."""
    pd.DataFrame({
        "tiempo_s": result.time, "voltaje_v": result.voltage,
        "corriente_ma": result.current_ma, "reto_id": challenge.identifier,
        "fuente_v": challenge.voltage, "resistencia_ohm": resistance,
        "capacidad_uf": capacitance_uf, "objetivo_v": challenge.target_voltage,
        "tiempo_objetivo_s": challenge.target_time,
        "tolerancia_v": challenge.tolerance,
        "voltaje_en_objetivo_v": result.measured_voltage,
        "cumple_objetivo": result.passed,
    }).to_csv(path, index=False, encoding="utf-8-sig")
