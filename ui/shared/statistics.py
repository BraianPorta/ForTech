"""
Estilo de juego de cada sesión
==============================
Lee todos los CSV de una carpeta (uno por sesión), resume cada sesión en 3 números
(tiempo, cambios e intentos medios por nivel), agrupa las sesiones parecidas con KMeans
y pone nombre a cada grupo según su estilo de juego.

Uso:
    1. Cada CSV de data/results/session debe tener una fila por nivel y las columnas
       Tiempo, Cambios e Intentos.
    2. La comparación se guarda en data/results/comparison/comparison.csv.
"""

# ---------------------------------------------------------------
# 1. LIBRERÍAS Y CONFIGURACIÓN
# ---------------------------------------------------------------
import glob, os                                   # glob/os: buscar archivos en una carpeta
from pathlib import Path

import numpy as np                                # cálculo numérico
import pandas as pd                               # tablas (DataFrames)
import matplotlib.pyplot as plt                   # gráficas
from sklearn.preprocessing import StandardScaler  # escalado de variables
from sklearn.cluster import KMeans                # algoritmo de agrupamiento
from sklearn.metrics import silhouette_score      # medida de calidad de los grupos
from sklearn.decomposition import PCA             # reducción a 2 dimensiones (solo para dibujar)

BASE = Path(__file__).resolve().parents[2]
# Carpetas donde se guardan los CSV de sesiones y de comparación.
CARPETA = BASE / "data" / "results" / "session"
CARPETA_COMPARACION = BASE / "data" / "results" / "comparison"

# ---------------------------------------------------------------
# 2. LEER LOS CSV Y RESUMIR CADA SESIÓN
# ---------------------------------------------------------------
# Nombres de las columnas que se usan de cada CSV (una fila por nivel)
COL_TIEMPO   = "Tiempo"
COL_CAMBIOS  = "Cambios"
COL_INTENTOS = "Intentos"
VARS = ["tiempo_nivel", "cambios_nivel", "intentos_nivel"]
COLUMNAS_COMPARACION = ["sesion", "n_niveles", *VARS, "grupo", "estilo"]

class SessionStatistics:
    """Guarda las actividades completadas y compara las sesiones completas."""

    def __init__(self, session_dir=CARPETA, comparison_dir=CARPETA_COMPARACION):
        self.session_dir = Path(session_dir)
        self.comparison_dir = Path(comparison_dir)

    def begin_session(self) -> int:
        """Reserva un número para la sesión que se inicia."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        counter = self.session_dir / ".last_session"
        last_number = 0
        if counter.exists():
            raw_number = counter.read_text(encoding="utf-8").strip()
            if not raw_number.isdecimal():
                raise ValueError(f"{counter.name}: el número de sesión no es válido.")
            last_number = int(raw_number)
        csv_numbers = [
            int(path.stem) for path in self.session_dir.glob("*.csv")
            if path.stem.isdecimal()
        ]
        session_number = max([last_number, *csv_numbers], default=0) + 1
        temporary = counter.with_suffix(".tmp")
        try:
            temporary.write_text(str(session_number), encoding="utf-8")
            temporary.replace(counter)
        finally:
            temporary.unlink(missing_ok=True)
        return session_number

    def save_session(self, session_number: int, records: list[dict]) -> Path:
        """Guarda una fila por nivel con las columnas que lee este análisis."""
        if not records:
            raise ValueError("No se puede guardar una sesión sin actividades.")
        destination = self.session_dir / f"{session_number}.csv"
        if destination.exists():
            raise FileExistsError(
                f"Las estadísticas de la sesión {session_number} ya existen."
            )
        rows = [
            {
                COL_TIEMPO: record["tiempo_s"],
                COL_CAMBIOS: record["cambios_total"],
                COL_INTENTOS: record["pruebas"],
            }
            for record in records
        ]
        self.session_dir.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        try:
            pd.DataFrame(
                rows, columns=[COL_TIEMPO, COL_CAMBIOS, COL_INTENTOS]
            ).to_csv(temporary, index=False, encoding="utf-8-sig")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def build_comparison(self):
        """Resume las sesiones completas y guarda el CSV comparativo."""
        # Lista ordenada de todos los CSV de la carpeta.
        rutas = sorted(
            glob.glob(os.path.join(str(self.session_dir), "*.csv")),
            key=lambda path: int(Path(path).stem) if Path(path).stem.isdecimal() else -1,
        )
        rutas = [ruta for ruta in rutas if Path(ruta).stem.isdecimal()]
        if not rutas:
            raise FileNotFoundError(
                f"No se ha encontrado ningún .csv en la carpeta '{self.session_dir}'"
            )

        sesiones = {}   # número de sesión -> tabla completa de niveles
        filas = []      # una fila-resumen por sesión

        # Lee y resume cada CSV: cada archivo corresponde a una sesión completa.
        for ruta in rutas:
            df = pd.read_csv(ruta)    # DataFrame con todos los niveles de esta sesión
            columnas = {COL_TIEMPO, COL_CAMBIOS, COL_INTENTOS}
            if not columnas.issubset(df.columns):
                faltan = ", ".join(sorted(columnas - set(df.columns)))
                raise ValueError(f"{Path(ruta).name}: faltan columnas {faltan}.")
            if df.empty:
                raise ValueError(f"{Path(ruta).name}: no contiene actividades.")
            for columna in (COL_TIEMPO, COL_CAMBIOS, COL_INTENTOS):
                df[columna] = pd.to_numeric(df[columna], errors="raise")
                if not np.isfinite(df[columna]).all() or df[columna].lt(0).any():
                    raise ValueError(
                        f"{Path(ruta).name}: {columna} debe contener números "
                        "finitos no negativos."
                    )
            numero_sesion = int(Path(ruta).stem)
            sesiones[numero_sesion] = df

            # Resumen de la sesión: media por nivel de cada variable (redondeada a 2 decimales).
            filas.append({
                "sesion":          numero_sesion,
                "n_niveles":      len(df),                         # nº de niveles jugados
                "tiempo_nivel":   round(df[COL_TIEMPO].mean(), 2),  # tiempo medio por nivel
                "cambios_nivel":  round(df[COL_CAMBIOS].mean(), 2), # cambios medios por nivel
                "intentos_nivel": round(df[COL_INTENTOS].mean(), 2),# intentos medios por nivel
            })

        # Tabla final: una fila por sesión.
        resumen = pd.DataFrame(filas)

        # Variables que usará el análisis.
        resumen["grupo"] = -1
        resumen["estilo"] = "Datos insuficientes para agrupar"
        sil = {}   # k -> silhouette obtenido
        scaler = None
        kmeans = None
        nombres = []

        # ---------------------------------------------------------------
        # 3. ESCALAR Y ELEGIR K
        # ---------------------------------------------------------------
        # Hay que tener al menos 3 sesiones para calcular silhouette.
        if len(resumen) >= 3 and resumen[VARS].drop_duplicates().shape[0] >= 2:
            # Escalado: (valor - media) / desviación típica, para que ninguna variable pese más que otra.
            scaler = StandardScaler()
            X = scaler.fit_transform(resumen[VARS])   # X: matriz escalada (una fila por sesión)

            # Valores de k a probar: de 2 a 5, sin superar (nº de sesiones - 1).
            ks = list(range(2, min(6, len(resumen))))

            for k in ks:
                # n_init=10: se repite el KMeans 10 veces desde cero y se queda con el mejor resultado.
                km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(X)
                # Se mide qué tan bien separados quedan los grupos con esas etiquetas.
                if 1 < len(set(km.labels_)) < len(resumen):
                    sil[k] = silhouette_score(X, km.labels_)

            if sil:
                # k elegido: el que tiene mejor silhouette.
                K = max(sil, key=lambda k: sil[k])
                print(
                    "silhouette por k:",
                    {k: round(v, 3) for k, v in sil.items()},
                    "-> k elegido =", K,
                )

                # Aviso sobre la fiabilidad de los grupos según el silhouette.
                if sil[K] < 0.25:
                    print("Aviso: los grupos casi no están separados, los estilos son poco fiables.")
                elif sil[K] < 0.5:
                    print("Grupos débiles: interprétalos con cuidado.")
                else:
                    print("Grupos bien definidos.")

                # ---------------------------------------------------------------
                # 4. AGRUPAR (KMEANS) Y NOMBRAR LOS GRUPOS
                # ---------------------------------------------------------------
                # KMeans final con el k elegido; cada sesión recibe una etiqueta de grupo.
                kmeans = KMeans(n_clusters=K, n_init=10, random_state=0).fit(X)
                resumen["grupo"] = [int(grupo) for grupo in kmeans.labels_]

                # Mediana de cada variable en TODAS las sesiones: es la referencia para nombrar.
                med = resumen[VARS].median()

                # Centroides en las unidades originales (se deshace el escalado) para poder interpretarlos.
                centros = pd.DataFrame(
                    scaler.inverse_transform(kmeans.cluster_centers_), columns=VARS
                )

                def nombrar(c):
                    """Devuelve el nombre de un grupo a partir de su centroide c."""
                    # Velocidad: tiempo del grupo frente a la mediana.
                    vel = "Rápido" if c["tiempo_nivel"] < med["tiempo_nivel"] else "Lento"
                    # Error: cambios e intentos relativos a su mediana (2 = justo en la mediana).
                    err = 0.0
                    for variable in ("cambios_nivel", "intentos_nivel"):
                        mediana = med[variable]
                        err += (
                            c[variable] / mediana
                            if mediana else float(c[variable] > 0)
                        )
                    return f"{vel} y {'preciso' if err < 2 else 'impreciso'}"

                # Calcular el nombre de cada grupo.
                for i in range(len(centros)):          # i = 0, 1, 2... (nº de grupo)
                    centroide = centros.iloc[i]       # fila del grupo i
                    nombre = nombrar(centroide)       # p. ej. "Rápido y preciso"
                    nombres.append(nombre)            # lo guardamos en la lista

                # Si algún nombre se repite, añadir el nº de grupo para distinguirlos.
                # Con pocos datos, dos centroides pueden tener características parecidas.
                nombres_finales = []
                for i in range(len(nombres)):
                    nombre = nombres[i]
                    if nombres.count(nombre) > 1:     # ¿este nombre aparece más de una vez?
                        nombre = f"{nombre} (grupo {i})"
                    nombres_finales.append(nombre)

                nombres = nombres_finales
                resumen["estilo"] = [
                    nombres[grupo] for grupo in resumen["grupo"]
                ]
                centros.index = nombres
                print(centros.round(2))              # perfil medio de cada grupo

        print(f"{len(resumen)} sesiones cargadas")
        print(resumen)

        # Guarda los datos comparativos usados por la gráfica.
        self.comparison_dir.mkdir(parents=True, exist_ok=True)
        destino = self.comparison_dir / "comparison.csv"
        temporal = destino.with_suffix(".tmp")
        try:
            resumen.reindex(columns=COLUMNAS_COMPARACION).to_csv(
                temporal, index=False, encoding="utf-8-sig"
            )
            temporal.replace(destino)
        finally:
            temporal.unlink(missing_ok=True)

        # ---------------------------------------------------------------
        # 5. GRÁFICAS
        # ---------------------------------------------------------------
        # Una figura con dos gráficas, una al lado de la otra
        _, axs = plt.subplots(1, 2, figsize=(13, 5))

        # --- Gráfica izquierda: silhouette para cada k probado ---
        if sil:
            axs[0].plot(list(sil), list(sil.values()), "o-")
            K = max(sil, key=lambda k: sil[k])
            axs[0].axvline(K, color="red", ls="--", label=f"k elegido = {K}")
            axs[0].set_xlabel("Número de grupos (k)")
            axs[0].set_ylabel("Silhouette")
            axs[0].set_title("Elección de k")
            axs[0].legend()
        else:
            axs[0].set_title("Elección de k")
            axs[0].text(
                0.5, 0.5, "Se necesitan más sesiones para agrupar.",
                ha="center", va="center", transform=axs[0].transAxes,
            )

        # --- Gráfica derecha: sesiones y centroides proyectados a 2 dimensiones ---
        if kmeans is not None and scaler is not None:
            X = scaler.transform(resumen[VARS])
            pca = PCA(n_components=2).fit(X)             # PCA aprende las 2 direcciones que mejor resumen los datos
            P = pca.transform(X)                         # coordenadas 2D de cada sesión
            C = pca.transform(kmeans.cluster_centers_)   # coordenadas 2D de los centroides

            cols = plt.cm.tab10                            # paleta de colores, uno por grupo
            nombres_grupo = resumen.groupby("grupo")["estilo"].first().to_dict()
            for g in range(len(kmeans.cluster_centers_)):
                m = (resumen["grupo"] == g).to_numpy()    # máscara: True para las sesiones del grupo g
                axs[1].scatter(
                    P[m, 0], P[m, 1], color=cols(g), edgecolor="black",
                    s=80, label=nombres_grupo[g],
                )

            # Centroides como X negras
            axs[1].scatter(C[:, 0], C[:, 1], marker="X", s=250, color="black", label="Centroides")
            axs[1].legend()
        else:
            axs[1].text(
                0.5, 0.5, "Los grupos aparecerán al completar más sesiones.",
                ha="center", va="center", transform=axs[1].transAxes,
            )
        axs[1].set_xlabel("PC1")
        axs[1].set_ylabel("PC2")
        axs[1].set_title("Sesiones agrupadas por estilo de juego")

        plt.tight_layout()
        plt.show()
        return resumen, sil, scaler, kmeans
