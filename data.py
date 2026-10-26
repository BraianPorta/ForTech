"""Lectura y escritura de los datos y archivos del juego."""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from pathlib import Path
import re
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ui.shared.functions.electronic import Simulation

# ---------------------------------------------------------------
# CONFIGURACIÓN Y MODELOS DE DATOS
# ---------------------------------------------------------------

# Orden estable de las columnas guardadas para cada reto completado.
PROGRESS_COLUMNS = [
    "partida_id", "fecha_utc", "dificultad", "dispositivo", "tiempo_s",
    "cambios_r", "cambios_c", "cambios_total", "pruebas",
]
# Estos patrones permiten localizar en los CSV las ramas y los pares de componentes.
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
    result_unit: str = "Ω"  # Unidad de medida para el objetivo del reto.
    result_min: float | None = None  # Límite inferior inclusivo, si el objetivo es un intervalo.
    result_max: float | None = None  # Límite superior inclusivo, si el objetivo es un intervalo.


# ---------------------------------------------------------------
# LECTURA Y VALIDACIÓN DE RETOS
# ---------------------------------------------------------------

def parseCircuit(tokens: list[str]) -> tuple[tuple[CircuitComponent, ...], ...]:
    """Convierte la secuencia tipo/valor del CSV en ramas de circuito."""
    from ui.shared.functions.electronic import (
        BULB_POWER_CANDIDATES,
        BULB_RESISTANCE_CANDIDATES,
        RESISTANCE_CANDIDATES,
    )

    # Cada marcador fila_X inicia una rama paralela; los componentes siguientes
    # hasta el próximo marcador pertenecen a esa rama y van conectados en serie.
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
            # Normaliza los alias del CSV al tipo interno usado por la simulación.
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
            elif kind in {"bombilla_ohm", "bulb_ohm"}:
                component_kind = "bombilla_ohm"
                candidates = BULB_RESISTANCE_CANDIDATES
                value_name = "resistencias de bombilla"
            else:
                raise ValueError(f"tipo de componente no admitido: {kind!r}")
            # Evita que los retos carguen valores que la interfaz no permita elegir.
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


def challengeColumns(frame: pd.DataFrame) -> tuple[dict, dict, list[int]]:
    """Valida las columnas obligatorias y encuentra pares tipo/valor contiguos."""
    required = {"dificultad", "modo", "enunciado", "resultado"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("Faltan columnas: " + ", ".join(sorted(missing)))
    # Conserva el nombre real de las columnas para poder leer cada fila aunque
    # las columnas opcionales aparezcan en distinto orden.
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
        # Los retos de fluidos pueden omitir completamente las columnas eléctricas.
        fluid_only = (
            "tipo_ejercicio" in frame.columns
            and frame["modo"].astype(str).str.strip().eq("1").all()
        )
        if fluid_only:
            return type_columns, value_columns, pair_numbers
        raise ValueError("Las columnas de circuito deben empezar en tipo_1/valor_1 y no tener saltos.")
    if pair_numbers != list(range(1, len(pair_numbers) + 1)):
        raise ValueError("Las columnas de circuito deben empezar en tipo_1/valor_1 y no tener saltos.")
    # Exige que cada índice tenga ambas columnas para evitar componentes incompletos.
    for number in pair_numbers:
        if number not in type_columns or number not in value_columns:
            raise ValueError(f"Falta la columna tipo_{number} o valor_{number}.")
    return type_columns, value_columns, pair_numbers


def parseChallengeRow(
    row: pd.Series,
    type_columns: dict,
    value_columns: dict,
    pair_numbers: list[int],
    path: Path,
) -> Challenge:
    """Valida una fila del CSV y crea el reto eléctrico o de fluidos."""
    from ui.shared.functions.electronic import challengeResistance

    try:
        # Los campos comunes identifican el reto y su criterio de éxito.
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
            raise ValueError("resultado debe ser un valor numérico") from error
        if not isfinite(target) or target <= 0:
            raise ValueError("resultado debe ser positivo y finito")
        result_unit = str(row.get("unidad_resultado", "Ω")).strip() or "Ω"
        if result_unit not in {"Ω", "W"}:
            raise ValueError("unidad_resultado debe ser Ω o W")
        # Los objetivos por intervalo deben tener los dos límites y contener el
        # valor de referencia; ambos extremos se consideran válidos.
        raw_min = str(row.get("resultado_min", "")).strip()
        raw_max = str(row.get("resultado_max", "")).strip()
        if bool(raw_min) != bool(raw_max):
            raise ValueError("resultado_min y resultado_max deben indicarse juntos")
        result_min = result_max = None
        if raw_min:
            try:
                result_min, result_max = float(raw_min), float(raw_max)
            except ValueError as error:
                raise ValueError("resultado_min y resultado_max deben ser numéricos") from error
            if (
                not isfinite(result_min)
                or not isfinite(result_max)
                or result_min <= 0
                or result_max < result_min
            ):
                raise ValueError("El intervalo de resultado debe ser positivo y estar ordenado")
            if not result_min <= target <= result_max:
                raise ValueError("resultado debe estar dentro del intervalo indicado")
        if result_unit == "W" and (result_min is None or result_max is None):
            raise ValueError("Los resultados en W requieren resultado_min y resultado_max")
        exercise_type = str(row.get("tipo_ejercicio", "")).strip()
        if mode == 1:
            # El modo de fluidos usa su propio modelo y no admite piezas eléctricas.
            from ui.shared.functions.flow import isFlowExercise

            if not isFlowExercise(exercise_type):
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
        # En modo eléctrico, tensión solo se admite cuando el reto incluye bombillas.
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
        # Convierte las celdas de la fila a una secuencia que parseCircuit entiende:
        # fila_1, tipo, valor, tipo, valor, fila_2, ...
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
        circuit_rows = parseCircuit(tokens)
        has_bulbs = any(
            component.kind in {"bombilla", "bombilla_ohm"}
            for branch in circuit_rows
            for component in branch
        )
        if has_bulbs and voltage is None:
            raise ValueError("tension_v es obligatorio para retos con bombillas")
        if not has_bulbs and voltage is not None:
            raise ValueError("tension_v solo se usa en retos con bombillas")
        # Comprueba que el circuito declarado como solución cumple el objetivo
        # o el intervalo antes de aceptar el reto en el catálogo.
        calculated = challengeResistance(circuit_rows, voltage)
        measured = voltage ** 2 / calculated if result_unit == "W" else calculated
        matches_target = (
            result_min <= measured <= result_max
            if result_min is not None and result_max is not None
            else isclose(measured, target, rel_tol=1e-6, abs_tol=1e-6)
        )
        if not matches_target:
            raise ValueError(
                f"resultado ({target:g} {result_unit}) no coincide con el circuito correcto "
                f"({measured:g} {result_unit})"
            )
        identifier = str(row.get("id", "")).strip()
        return Challenge(
            difficulty, mode, prompt, target, circuit_rows, identifier, voltage,
            result_unit=result_unit, result_min=result_min, result_max=result_max,
        )
    except (ValueError, TypeError, OverflowError) as error:
        # Añade el archivo de origen para localizar el dato incorrecto en el CSV.
        raise ValueError(f"{path.name}: {error}") from error


def loadChallengeFile(path: Path) -> Challenge:
    """Lee y valida un reto CSV con pares de columnas `tipo_X` y `valor_X`.

    Los marcadores de fila se escriben en `tipo_X` y dejan vacío su `valor_X`.
    Las filas del CSV pueden terminar en el último dato disponible, sin añadir
    separadores para las columnas que no usan.
    """
    # Se leen los datos como texto para validar los valores y vacíos explícitamente.
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    type_columns, value_columns, pair_numbers = challengeColumns(frame)
    if len(frame) != 1:
        raise ValueError("Cada archivo debe contener exactamente un reto.")
    return parseChallengeRow(
        frame.iloc[0], type_columns, value_columns, pair_numbers, path
    )


def loadChallenges(path: str | Path) -> list[Challenge]:
    """Carga retos de CSV independientes o de un CSV unificado con columna `id`."""
    source = Path(path)
    # Una carpeta representa importaciones individuales; un archivo es el catálogo unificado.
    if source.is_dir():
        files = sorted(source.glob("*.csv"))
    else:
        files = [source]
    if not files:
        raise ValueError(f"No se encontraron archivos CSV en {source}.")
    challenges = []
    for csv_path in files:
        frame = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        type_columns, value_columns, pair_numbers = challengeColumns(frame)
        if "id" in frame.columns:
            # El catálogo unificado exige identificadores numéricos, únicos y estables.
            if frame.columns[0] != "id":
                raise ValueError(f"{csv_path.name}: la primera columna debe ser 'id'.")
            identifiers = frame["id"].str.strip()
            if (identifiers.empty or identifiers.eq("").any()
                    or not identifiers.str.fullmatch(r"\d+").all()
                    or any(int(identifier) < 1 for identifier in identifiers)
                    or identifiers.duplicated().any()):
                raise ValueError(f"{csv_path.name}: cada reto debe tener un id numérico único y no vacío.")
            challenges.extend(
                parseChallengeRow(row, type_columns, value_columns, pair_numbers, csv_path)
                for _, row in frame.iterrows()
            )
        else:
            # Cada archivo pendiente de importación debe describir un solo reto.
            if len(frame) != 1:
                raise ValueError(f"{csv_path.name}: cada archivo de import debe contener un único reto.")
            challenges.append(parseChallengeRow(
                frame.iloc[0], type_columns, value_columns, pair_numbers, csv_path
            ))
    # Mantiene el orden de juego por dificultad y luego por identificador.
    return sorted(
        challenges,
        key=lambda challenge: (
            challenge.difficulty,
            int(challenge.identifier) if challenge.identifier.isdigit() else 0,
        ),
    )


# ---------------------------------------------------------------
# IMPORTACIÓN Y ESCRITURA DE RETOS
# ---------------------------------------------------------------

def prepareExercises(import_path: str | Path, exercises_path: str | Path) -> Path:
    """Importa CSV individuales al archivo unificado y elimina el origen al confirmar."""
    import_dir = Path(import_path)
    files = sorted(import_dir.glob("*.csv"))
    destination = Path(exercises_path)
    destination_frame = None
    rewrite_existing = False
    if destination.exists():
        # Valida primero el catálogo para no mezclar importaciones con datos dañados.
        destination_frame = pd.read_csv(
            destination, encoding="utf-8-sig", dtype=str, keep_default_na=False
        )
        if destination_frame.empty:
            raise ValueError(f"{destination.name}: no contiene retos.")
        if "id" not in destination_frame.columns or destination_frame.columns[0] != "id":
            raise ValueError(f"{destination.name}: la primera columna debe ser 'id'.")
        type_columns, value_columns, pair_numbers = challengeColumns(destination_frame)
        for _, row in destination_frame.iterrows():
            parseChallengeRow(
                row, type_columns, value_columns, pair_numbers, destination
            )
        ids = destination_frame["id"].str.strip()
        if not ids.str.fullmatch(r"\d+").all():
            # Migra catálogos antiguos asignando IDs secuenciales antes de añadir retos.
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
                writeUnifiedExercises(destination, destination_frame)
            return destination
        raise ValueError(f"No hay retos en {import_dir} ni un archivo existente en {destination}.")

    for source in files:
        # Valida el reto aislado antes de modificar el catálogo de destino.
        loadChallengeFile(source)
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
            "tension_v", "tipo_ejercicio", "unidad_resultado",
            "resultado_min", "resultado_max",
        ]
        for number in range(1, max_pair + 1):
            columns.extend((f"tipo_{number}", f"valor_{number}"))
        frame.insert(0, "id", "")
        if destination_frame is None:
            destination_frame = pd.DataFrame(columns=columns)
        # El nuevo ID se asigna al final del catálogo; se conserva el orden previo.
        next_id = max((int(value) for value in destination_frame["id"]), default=0) + 1
        frame.loc[frame.index[0], "id"] = str(next_id)
        unified = pd.concat([destination_frame, frame], ignore_index=True).reindex(
            columns=columns, fill_value=""
        )
        writeUnifiedExercises(destination, unified)
        destination_frame = unified
        # Borra el origen solo cuando el catálogo unificado ya se escribió y validó.
        source.unlink()

    return destination


def writeUnifiedExercises(destination: Path, frame: pd.DataFrame) -> None:
    """Valida y reemplaza atómicamente el CSV unificado."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    try:
        # Escribe en un temporal y comprueba que el CSV completo se puede volver a leer.
        frame.to_csv(temporary, index=False, encoding="utf-8-sig")
        loadChallenges(temporary)
        # replace evita dejar un archivo final parcialmente escrito ante un fallo.
        temporary.replace(destination)
    finally:
        # Limpia el temporal tanto si la validación/escritura termina bien como si falla.
        temporary.unlink(missing_ok=True)


# ---------------------------------------------------------------
# EXPORTACIÓN DE SIMULACIONES
# ---------------------------------------------------------------

def saveSimulation(path: str | Path, result: Simulation, challenge: Challenge,
                    rows: list[list[float]]) -> None:
    """Exporta el circuito seleccionado y su resultado calculado."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Guarda objetivo y medición junto a cada componente, agrupado por rama.
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


# ---------------------------------------------------------------
# LECTURA Y ESCRITURA DEL PROGRESO
# ---------------------------------------------------------------

class ProgressStore:
    """Progreso de la partida actual, con guardado atómico y sin duplicados."""

    def __init__(self, path: str | Path):
        """Inicia un progreso vacío para la nueva partida."""
        self.path = Path(path)
        self.records = []
        self.reset()

    def reset(self) -> None:
        """Vacía el progreso anterior al empezar una partida nueva."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            # Mantiene la cabecera para que el CSV vacío conserve su formato esperado.
            pd.DataFrame(columns=PROGRESS_COLUMNS).to_csv(
                temporary, index=False, encoding="utf-8-sig"
            )
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.records = []

    def append(self, record: dict) -> None:
        """Añade un intento válido mediante una escritura atómica."""
        # partida_id identifica unívocamente el intento y evita duplicarlo en el CSV.
        if any(row["partida_id"] == record["partida_id"] for row in self.records):
            return
        rows = [*self.records, record]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            # Reescribe el historial completo en un temporal para evitar truncarlo.
            pd.DataFrame(rows, columns=PROGRESS_COLUMNS).to_csv(
                temporary, index=False, encoding="utf-8-sig")
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.records = rows
