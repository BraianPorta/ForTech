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
    identifier: str = ""
    voltage: float | None = None
    exercise_type: str = ""


def _parse_circuit(tokens: list[str]) -> tuple[tuple[CircuitComponent, ...], ...]:
    from ui.shared.functions import BULB_POWER_CANDIDATES, RESISTANCE_CANDIDATES

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
            if kind in {"ohm", "resistencia"}:
                component_kind = "ohm"
                candidates = RESISTANCE_CANDIDATES
                value_name = "resistencias"
            elif kind in {"bombilla", "bombilla_w", "bulb_w"}:
                component_kind = "bombilla"
                candidates = BULB_POWER_CANDIDATES
                value_name = "potencias de bombilla"
            else:
                raise ValueError(f"tipo de componente no admitido: {kind!r}")
            if not isfinite(value) or value <= 0:
                raise ValueError(f"los valores de {value_name} deben ser positivos y finitos")
            if value not in candidates:
                raise ValueError(
                    f"{value:g} no está en el catálogo de {value_name} "
                    f"({', '.join(str(candidate) for candidate in candidates)})"
                )
            components.append(CircuitComponent(component_kind, value))
            index += 2
        if not components:
            raise ValueError(f"fila_{row_id} no contiene ninguna resistencia")
        rows.append(tuple(components))
    if not rows:
        raise ValueError("el reto debe contener al menos una fila de circuito")
    return tuple(rows)


def _challenge_columns(frame: pd.DataFrame) -> tuple[dict, dict, list[int]]:
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
    if not pair_numbers:
        fluid_only = (
            "tipo_ejercicio" in frame.columns
            and frame["modo"].astype(str).str.strip().eq("1").all()
        )
        if fluid_only:
            return type_columns, value_columns, pair_numbers
        raise ValueError("Las columnas de circuito deben empezar en tipo_1/valor_1 y no tener saltos.")
    if pair_numbers != list(range(1, len(pair_numbers) + 1)):
        raise ValueError("Las columnas de circuito deben empezar en tipo_1/valor_1 y no tener saltos.")
    for number in pair_numbers:
        if number not in type_columns or number not in value_columns:
            raise ValueError(f"Falta la columna tipo_{number} o valor_{number}.")
    return type_columns, value_columns, pair_numbers


def _parse_challenge_row(
    row: pd.Series,
    type_columns: dict,
    value_columns: dict,
    pair_numbers: list[int],
    path: Path,
) -> Challenge:
    from ui.shared.functions import challenge_resistance

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
        exercise_type = str(row.get("tipo_ejercicio", "")).strip()
        if mode == 1:
            from ui.shared.flow import is_flow_exercise

            if not is_flow_exercise(exercise_type):
                raise ValueError("tipo_ejercicio debe identificar un ejercicio de fluidos válido")
            if any(
                str(row[type_columns[number]]).strip()
                or str(row[value_columns[number]]).strip()
                for number in pair_numbers
            ):
                raise ValueError("los ejercicios de fluidos no admiten componentes de circuito")
            if str(row.get("tension_v", "")).strip():
                raise ValueError("tension_v no se usa en ejercicios de fluidos")
            identifier = str(row.get("id", "")).strip()
            return Challenge(
                difficulty, mode, prompt, target, (), identifier, None, exercise_type
            )
        if exercise_type:
            raise ValueError("tipo_ejercicio solo se usa en los retos del modo Unai")
        voltage = None
        raw_voltage = str(row.get("tension_v", "")).strip()
        if raw_voltage:
            try:
                voltage = float(raw_voltage)
            except ValueError as error:
                raise ValueError("tension_v debe ser un voltaje en voltios") from error
            if not isfinite(voltage) or voltage <= 0:
                raise ValueError("tension_v debe ser positivo y finito")
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
        has_bulbs = any(
            component.kind == "bombilla"
            for branch in circuit_rows
            for component in branch
        )
        if has_bulbs and voltage is None:
            raise ValueError("tension_v es obligatorio para retos con bombillas")
        if not has_bulbs and voltage is not None:
            raise ValueError("tension_v solo se usa en retos con bombillas")
        calculated = challenge_resistance(circuit_rows, voltage)
        if not isclose(calculated, target, rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError(
                f"resultado ({target:g} Ω) no coincide con el circuito correcto "
                f"({calculated:g} Ω)"
            )
        identifier = str(row.get("id", "")).strip()
        return Challenge(difficulty, mode, prompt, target, circuit_rows, identifier, voltage)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError(f"{path.name}: {error}") from error


def _load_challenge_file(path: Path) -> Challenge:
    """Lee y valida un reto CSV con pares de columnas `tipo_X` y `valor_X`.

    Los marcadores de fila se escriben en `tipo_X` y dejan vacío su `valor_X`.
    Las filas del CSV pueden terminar en el último dato disponible, sin añadir
    separadores para las columnas que no usan.
    """
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    type_columns, value_columns, pair_numbers = _challenge_columns(frame)
    if len(frame) != 1:
        raise ValueError("Cada archivo debe contener exactamente un reto.")
    return _parse_challenge_row(
        frame.iloc[0], type_columns, value_columns, pair_numbers, path
    )


def load_challenges(path: str | Path) -> list[Challenge]:
    """Carga retos de CSV independientes o de un CSV unificado con columna `id`."""
    source = Path(path)
    if source.is_dir():
        files = sorted(source.glob("*.csv"))
    else:
        files = [source]
    if not files:
        raise ValueError(f"No se encontraron archivos CSV en {source}.")
    challenges = []
    for csv_path in files:
        frame = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        type_columns, value_columns, pair_numbers = _challenge_columns(frame)
        if "id" in frame.columns:
            if frame.columns[0] != "id":
                raise ValueError(f"{csv_path.name}: la primera columna debe ser 'id'.")
            identifiers = frame["id"].str.strip()
            if (identifiers.empty or identifiers.eq("").any()
                    or not identifiers.str.fullmatch(r"\d+").all()
                    or any(int(identifier) < 1 for identifier in identifiers)
                    or identifiers.duplicated().any()):
                raise ValueError(f"{csv_path.name}: cada reto debe tener un id numérico único y no vacío.")
            challenges.extend(
                _parse_challenge_row(row, type_columns, value_columns, pair_numbers, csv_path)
                for _, row in frame.iterrows()
            )
        else:
            if len(frame) != 1:
                raise ValueError(f"{csv_path.name}: cada archivo de import debe contener un único reto.")
            challenges.append(_parse_challenge_row(
                frame.iloc[0], type_columns, value_columns, pair_numbers, csv_path
            ))
    return sorted(
        challenges,
        key=lambda challenge: (
            challenge.difficulty,
            int(challenge.identifier) if challenge.identifier.isdigit() else 0,
        ),
    )


def prepare_exercises(import_path: str | Path, exercises_path: str | Path) -> Path:
    """Importa CSV individuales al archivo unificado y elimina el origen al confirmar."""
    import_dir = Path(import_path)
    files = sorted(import_dir.glob("*.csv"))
    destination = Path(exercises_path)
    destination_frame = None
    rewrite_existing = False
    if destination.exists():
        destination_frame = pd.read_csv(
            destination, encoding="utf-8-sig", dtype=str, keep_default_na=False
        )
        if destination_frame.empty:
            raise ValueError(f"{destination.name}: no contiene retos.")
        if "id" not in destination_frame.columns or destination_frame.columns[0] != "id":
            raise ValueError(f"{destination.name}: la primera columna debe ser 'id'.")
        type_columns, value_columns, pair_numbers = _challenge_columns(destination_frame)
        for _, row in destination_frame.iterrows():
            _parse_challenge_row(
                row, type_columns, value_columns, pair_numbers, destination
            )
        ids = destination_frame["id"].str.strip()
        if not ids.str.fullmatch(r"\d+").all():
            destination_frame = destination_frame.copy()
            destination_frame["id"] = [str(index) for index in range(1, len(ids) + 1)]
            rewrite_existing = True
        elif ids.duplicated().any() or any(int(value) < 1 for value in ids):
            raise ValueError(f"{destination.name}: los ids deben ser positivos y únicos.")
        elif (
            any(str(int(value)) != value for value in ids)
            or [int(value) for value in ids] != list(range(1, len(ids) + 1))
        ):
            destination_frame = destination_frame.copy()
            destination_frame["id"] = [
                str(index) for index in range(1, len(ids) + 1)
            ]
            rewrite_existing = True

    if not files:
        if destination.exists():
            if rewrite_existing:
                _write_unified_exercises(destination, destination_frame)
            return destination
        raise ValueError(f"No hay retos en {import_dir} ni un archivo existente en {destination}.")

    for source in files:
        _load_challenge_file(source)
        frame = pd.read_csv(source, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        if "id" in frame.columns:
            raise ValueError(f"{source.name}: los archivos de import no deben incluir columna 'id'.")
        pair_numbers = [
            int(match.group(1))
            for column in frame.columns
            if (match := TYPE_COLUMN.fullmatch(column))
        ]
        max_pair = max(pair_numbers, default=0)
        if destination_frame is not None:
            for column in destination_frame.columns:
                match = TYPE_COLUMN.fullmatch(column)
                if match:
                    max_pair = max(max_pair, int(match.group(1)))

        columns = [
            "id", "modo", "dificultad", "enunciado", "resultado",
            "tension_v", "tipo_ejercicio",
        ]
        for number in range(1, max_pair + 1):
            columns.extend((f"tipo_{number}", f"valor_{number}"))
        frame.insert(0, "id", "")
        if destination_frame is None:
            destination_frame = pd.DataFrame(columns=columns)
        next_id = max((int(value) for value in destination_frame["id"]), default=0) + 1
        frame.loc[frame.index[0], "id"] = str(next_id)
        unified = pd.concat([destination_frame, frame], ignore_index=True).reindex(
            columns=columns, fill_value=""
        )
        _write_unified_exercises(destination, unified)
        destination_frame = unified
        source.unlink()

    return destination


def _write_unified_exercises(destination: Path, frame: pd.DataFrame) -> None:
    """Valida y reemplaza atómicamente el CSV unificado."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    try:
        frame.to_csv(temporary, index=False, encoding="utf-8-sig")
        load_challenges(temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


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
