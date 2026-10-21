"""Lectura y escritura de los datos y archivos del juego."""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from pathlib import Path
import re
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ui.shared.functions import Simulation

PROGRESS_COLUMNS = [
    "partida_id", "fecha_utc", "dificultad", "dispositivo", "tiempo_s",
    "cambios_r", "cambios_c", "cambios_total", "pruebas",
]
ROW_MARKER = re.compile(r"fila_(\d+)", re.IGNORECASE)
TYPE_COLUMN = re.compile(r"tipo_(\d+)", re.IGNORECASE)
VALUE_COLUMN = re.compile(r"valor_(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class CircuitComponent:
    """Componente de circuito y valor correcto definido para el reto."""

    kind: str
    correct_value: float


@dataclass(frozen=True)
class Challenge:
    """Reto cargado desde un CSV, con hasta tres ramas en paralelo."""

    difficulty: int
    mode: int
    prompt: str
    result: float
    rows: tuple[tuple[CircuitComponent, ...], ...]


def _parse_circuit(tokens: list[str]) -> tuple[tuple[CircuitComponent, ...], ...]:
    from ui.shared.functions import RESISTANCE_CANDIDATES

    rows: list[tuple[CircuitComponent, ...]] = []
    index = 0
    while index < len(tokens):
        marker = ROW_MARKER.fullmatch(tokens[index])
        if marker is None:
            raise ValueError(f"se esperaba un marcador fila_X, no {tokens[index]!r}")
        row_id = int(marker.group(1))
        if row_id != len(rows) + 1:
            raise ValueError("las filas deben aparecer una sola vez y en orden desde fila_1")
        if row_id > 3:
            raise ValueError("el circuito admite un máximo de 3 filas en paralelo")
        index += 1
        components = []
        while index < len(tokens) and ROW_MARKER.fullmatch(tokens[index]) is None:
            kind = tokens[index].strip().casefold()
            if index + 1 >= len(tokens) or ROW_MARKER.fullmatch(tokens[index + 1]):
                index += 1
                break
            raw_value = tokens[index + 1].strip()
            try:
                value = float(raw_value)
            except ValueError as error:
                raise ValueError(f"valor no numérico para el componente {kind!r}") from error
            if kind not in {"ohm", "resistencia"}:
                raise ValueError(f"tipo de componente no admitido: {kind!r}; por ahora usa 'ohm'")
            if not isfinite(value) or value <= 0:
                raise ValueError("los valores de resistencia deben ser positivos y finitos")
            if value not in RESISTANCE_CANDIDATES:
                raise ValueError(
                    f"{value:g} Ω no está en el catálogo de valores candidatos "
                    f"({', '.join(str(candidate) for candidate in RESISTANCE_CANDIDATES)})"
                )
            components.append(CircuitComponent("ohm", value))
            index += 2
        if not components:
            raise ValueError(f"fila_{row_id} no contiene ninguna resistencia")
        rows.append(tuple(components))
    if not rows:
        raise ValueError("el reto debe contener al menos una fila de circuito")
    return tuple(rows)


def _load_challenge_file(path: Path) -> Challenge:
    """Lee y valida un reto CSV con pares de columnas `tipo_X` y `valor_X`.

    Los marcadores de fila se escriben en `tipo_X` y dejan vacío su `valor_X`.
    Las filas del CSV pueden terminar en el último dato disponible, sin añadir
    separadores para las columnas que no usan.
    """
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    required = {"dificultad", "modo", "enunciado", "resultado"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("Faltan columnas: " + ", ".join(sorted(missing)))
    type_columns = {}
    value_columns = {}
    for name in frame.columns:
        match = TYPE_COLUMN.fullmatch(name)
        if match:
            type_columns[int(match.group(1))] = name
            continue
        match = VALUE_COLUMN.fullmatch(name)
        if match:
            value_columns[int(match.group(1))] = name
    pair_numbers = sorted(set(type_columns) | set(value_columns))
    if not pair_numbers or pair_numbers != list(range(1, len(pair_numbers) + 1)):
        raise ValueError("Las columnas de circuito deben empezar en tipo_1/valor_1 y no tener saltos.")
    for number in pair_numbers:
        if number not in type_columns or number not in value_columns:
            raise ValueError(f"Falta la columna tipo_{number} o valor_{number}.")
    if len(frame) != 1:
        raise ValueError("Cada archivo debe contener exactamente un reto.")

    from ui.shared.functions import calculate_equivalent_resistance

    row = frame.iloc[0]
    try:
        try:
            difficulty = int(row["dificultad"])
        except ValueError as error:
            raise ValueError("dificultad debe ser 1, 2 o 3") from error
        if difficulty not in (1, 2, 3):
            raise ValueError("dificultad debe ser 1, 2 o 3")
        prompt = row["enunciado"].strip()
        if not prompt:
            raise ValueError("enunciado es obligatorio")
        try:
            mode = int(row["modo"])
        except ValueError as error:
            raise ValueError("modo debe ser 0 (Leire) o 1 (Unai)") from error
        if mode not in (0, 1):
            raise ValueError("modo debe ser 0 (Leire) o 1 (Unai)")
        try:
            target = float(row["resultado"])
        except ValueError as error:
            raise ValueError("resultado debe ser una resistencia en ohmios") from error
        if not isfinite(target) or target <= 0:
            raise ValueError("resultado debe ser positivo y finito")
        tokens = []
        found_empty_pair = False
        for number in pair_numbers:
            raw_kind = row[type_columns[number]]
            raw_value = row[value_columns[number]]
            kind = "" if pd.isna(raw_kind) else str(raw_kind).strip()
            value = "" if pd.isna(raw_value) else str(raw_value).strip()
            if not kind and not value:
                found_empty_pair = True
                continue
            if found_empty_pair:
                raise ValueError(f"hay un par tipo/valor vacío antes de tipo_{number}")
            if not kind:
                raise ValueError(f"falta tipo_{number} para su valor")
            if ROW_MARKER.fullmatch(kind):
                if value:
                    raise ValueError(f"tipo_{number} es un marcador de fila y no debe tener valor")
            elif not value:
                raise ValueError(f"falta valor_{number} para el tipo {kind!r}")
            tokens.append(kind)
            if value:
                tokens.append(value)
        circuit_rows = _parse_circuit(tokens)
        calculated = calculate_equivalent_resistance(
            [[component.correct_value for component in branch] for branch in circuit_rows]
        )
        if not isclose(calculated, target, rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError(
                f"resultado ({target:g} Ω) no coincide con el circuito correcto "
                f"({calculated:g} Ω)"
            )
        return Challenge(difficulty, mode, prompt, target, circuit_rows)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError(f"{path.name}: {error}") from error


def load_challenges(path: str | Path) -> list[Challenge]:
    """Carga un reto por cada CSV de una carpeta, o un único CSV."""
    source = Path(path)
    files = sorted(source.glob("*.csv")) if source.is_dir() else [source]
    if not files:
        raise ValueError(f"No se encontraron archivos CSV en {source}.")
    challenges = [_load_challenge_file(csv_path) for csv_path in files]
    return sorted(challenges, key=lambda challenge: challenge.difficulty)
    return result


def save_simulation(path: str | Path, result: Simulation, challenge: Challenge,
                    rows: list[list[float]]) -> None:
    """Exporta el circuito seleccionado y su resultado calculado."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "dificultad": challenge.difficulty,
        "modo": challenge.mode,
        "resultado_objetivo_ohm": challenge.result,
        "resistencia_equivalente_ohm": result.measured_value,
        "cumple_objetivo": result.passed,
    }
    for row_index, branch in enumerate(rows, start=1):
        for component_index, value in enumerate(branch, start=1):
            record[f"fila_{row_index}_R{component_index}_ohm"] = value
    pd.DataFrame([record]).to_csv(path, index=False, encoding="utf-8-sig")


class ProgressStore:
    """Historial de misiones resueltas, con guardado atómico y sin duplicados."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.records = []
        if self.path.exists():
            frame = pd.read_csv(self.path)
            if "reto_id" in frame.columns and "dificultad" not in frame.columns:
                frame = frame.rename(columns={"reto_id": "dificultad"})
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
