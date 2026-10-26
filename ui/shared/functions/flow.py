"""Datos y cálculos de los ejercicios de mecánica de fluidos."""
from dataclasses import dataclass
from math import isfinite, log10, pi, sqrt
from typing import Mapping


# ---------------------------------------------------------------
# MECÁNICA DE FLUIDOS
# ---------------------------------------------------------------

@dataclass(frozen=True)
class FlowParameter:
    """Opción seleccionable de un parámetro de un ejercicio de fluidos."""

    key: str
    label: str
    options: tuple[float, ...]
    unit: str
    initial: float


@dataclass(frozen=True)
class FlowExercise:
    """Enunciado, modelo físico y presentación de un ejercicio de fluidos."""

    title: str
    prompt: str
    objective: str
    formula: str
    constants: str
    parameters: tuple[FlowParameter, ...]
    diagram: str
    unit: str


# Definiciones disponibles de ejercicios, parámetros y sus criterios de éxito.
FLOW_EXERCISES = {
    "laminar_flow": FlowExercise(
        title="Régimen de flujo",
        prompt=(
            "Tenemos un tubo por el que circula agua. ¿Qué combinación de velocidad "
            "y diámetro produce un flujo laminar?"
        ),
        objective="Re < 2300",
        formula="Re = (ρ · v · D) / μ",
        constants=(
            "Agua a 20 °C: ρ = 998,2 kg/m³ · μ = 1,002 × 10⁻³ Pa·s\n"
            "Laminar: Re < 2300 · transición: 2300 ≤ Re ≤ 4000 · turbulento: Re > 4000"
        ),
        parameters=(
            FlowParameter("v", "Velocidad v", (0.20, 0.30, 0.10), "m/s", 0.30),
            FlowParameter("D", "Diámetro D", (0.010, 0.015, 0.020), "m", 0.020),
        ),
        diagram="flow",
        unit="Re",
    ),
    "heat_transfer": FlowExercise(
        title="Convección natural",
        prompt=(
            "Un tubo de 1 m pierde calor al aire exterior. Elige la temperatura del "
            "agua y el diámetro para disipar entre 30 W y 60 W."
        ),
        objective="30 W ≤ Q ≤ 60 W",
        formula=(
            "A = π·D·L · Tf = (Ts + T∞)/2\n"
            "RaD = [g·β·(Ts−T∞)·D³/ν²]·Pr\n"
            "NuD = {0,60 + 0,387·RaD^(1/6) / "
            "[1 + (0,559/Pr)^(9/16)]^(8/27)}²\n"
            "h = NuD·k/D · Q = h·A·(Ts−T∞)"
        ),
        constants=(
            "L = 1 m · T∞ = 20 °C · propiedades del aire a 40 °C: "
            "k = 0,0266 W/(m·K) · "
            "ν = 1,71 × 10⁻⁵ m²/s · Pr = 0,725 · β = 1/313,15 K⁻¹"
        ),
        parameters=(
            FlowParameter("Ts", "Temperatura Ts", (50, 45, 80), "°C", 45),
            FlowParameter("D", "Diámetro D", (0.050, 0.060, 0.070), "m", 0.070),
        ),
        diagram="heat",
        unit="W",
    ),
    "pressure_loss": FlowExercise(
        title="Pérdida de carga",
        prompt=(
            "Elige el diámetro y la longitud de la tubería de PVC para obtener una "
            "pérdida de presión entre 30 kPa y 60 kPa."
        ),
        objective="30 kPa ≤ ΔP ≤ 60 kPa",
        formula=(
            "Re = (ρ·v·D)/μ\n"
            "1/√f = −1,8·log₁₀[((ε/D)/3,7)^1,11 + 6,9/Re]\n"
            "hf = f·(L/D)·[v²/(2g)] · ΔP = ρ·g·hf"
        ),
        constants=(
            "Agua a 20 °C: ρ = 998,2 kg/m³ · μ = 1,002 × 10⁻³ Pa·s · "
            "v = 2 m/s · εPVC = 1,5 × 10⁻⁶ m"
        ),
        parameters=(
            FlowParameter("L", "Longitud L", (50, 60, 100), "m", 60),
            FlowParameter("D", "Diámetro D", (0.050, 0.060, 0.040), "m", 0.040),
        ),
        diagram="pressure",
        unit="kPa",
    ),
}


def isFlowExercise(exercise_type: str) -> bool:
    """Indica si el identificador corresponde a un ejercicio de fluidos."""
    return exercise_type in FLOW_EXERCISES


def calculateFlowResult(exercise_type: str, values: Mapping[str, float]) -> float:
    """Calcula Reynolds, calor disipado o pérdida de presión según el ejercicio."""
    if exercise_type not in FLOW_EXERCISES:
        raise ValueError(f"Tipo de ejercicio de fluidos no admitido: {exercise_type!r}")
    exercise = FLOW_EXERCISES[exercise_type]
    expected_keys = {parameter.key for parameter in exercise.parameters}
    if set(values) != expected_keys:
        raise ValueError("Los parámetros no coinciden con el ejercicio.")
    for parameter in exercise.parameters:
        value = values[parameter.key]
        if not isfinite(value) or value not in parameter.options:
            raise ValueError(f"{parameter.label} debe ser una de las opciones disponibles.")

    if exercise_type == "laminar_flow":
        reynolds = 998.2 * values["v"] * values["D"] / 1.002e-3
        return reynolds

    if exercise_type == "heat_transfer":
        ts, diameter = values["Ts"], values["D"]
        ambient = 20.0
        delta_temperature = ts - ambient
        rayleigh = (
            9.81 * (1 / 313.15) * delta_temperature * diameter**3
            / (1.71e-5**2) * 0.725
        )
        nusselt = (
            0.60
            + 0.387 * rayleigh ** (1 / 6)
            / (1 + (0.559 / 0.725) ** (9 / 16)) ** (8 / 27)
        ) ** 2
        coefficient = nusselt * 0.0266 / diameter
        area = pi * diameter * 1.0
        return coefficient * area * delta_temperature

    length, diameter = values["L"], values["D"]
    velocity = 2.0
    density = 998.2
    viscosity = 1.002e-3
    reynolds = density * velocity * diameter / viscosity
    roughness = 1.5e-6
    inverse_sqrt_friction = -1.8 * log10(
        ((roughness / diameter) / 3.7) ** 1.11 + 6.9 / reynolds
    )
    friction = 1 / inverse_sqrt_friction**2
    head_loss = friction * (length / diameter) * velocity**2 / (2 * 9.81)
    return density * 9.81 * head_loss / 1000


def simulateFlow(exercise_type: str, values: Mapping[str, float]):
    """Devuelve el resultado calculado y si satisface el criterio del reto."""
    from ui.shared.functions.electronic import Simulation

    result = calculateFlowResult(exercise_type, values)
    if exercise_type == "laminar_flow":
        passed = result < 2300
        target = 2300.0
    else:
        passed = 30 <= result <= 60
        target = 45.0
    return Simulation(
        result,
        target,
        FLOW_EXERCISES[exercise_type].unit,
        passed_override=passed,
    )
