"""Diálogo general de estadísticas del jugador."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton

from ui.shared.motion import WidgetMotion
from ui.shared.style import BG, EDGE, MUTED, ORANGE, PANEL, TEAL, TEXT
from ui.shared.widgets import label


class StatisticsDialog(QDialog):
    """Gráficas de partidas reales, mostradas únicamente al consultar el progreso."""

    def __init__(self, records, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QLabel#hero { font-size: 30px; font-weight: 700; }")
        self.setWindowTitle("Circuit Quest · Mi progreso")
        self.resize(1000, 610)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(label("TU RECORRIDO", "eyebrow"))
        layout.addWidget(label("Mi progreso", "hero"))
        self.canvas = None
        if not records:
            layout.addStretch()
            empty = label("Completa tu primer nivel.", "muted", True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
            layout.addStretch()
        else:
            import numpy as np
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            from matplotlib.ticker import MaxNLocator

            missions = "misión resuelta" if len(records) == 1 else "misiones resueltas"
            layout.addWidget(label(f"{len(records)} {missions} · Últimas 10 partidas", "muted"))
            rows = records[-10:]
            figure = Figure(figsize=(9, 3.6), facecolor=BG, layout="constrained")
            self.canvas = FigureCanvasQTAgg(figure)
            axes = figure.subplots(1, 2)
            x = np.arange(len(rows))
            captions = [
                f"{i + 1 + len(records) - len(rows):02d}\n{r['reto_id']}"
                for i, r in enumerate(rows)
            ]
            for ax in axes:
                ax.set_facecolor(BG)
                ax.spines[["top", "right"]].set_visible(False)
                for spine in ax.spines.values():
                    spine.set_color(EDGE)
                ax.tick_params(colors=MUTED, labelsize=9)
                ax.set_xticks(x, captions)
                ax.set_xlabel("Partida / misión", color=MUTED)
                ax.grid(axis="y", color=EDGE, alpha=0.5)
                ax.set_axisbelow(True)
            axes[0].bar(x, [r["tiempo_s"] for r in rows], color=TEAL, width=0.55)
            axes[0].set_title("Tiempo para resolver la misión", color=TEXT, pad=15)
            axes[0].set_ylabel("Segundos", color=MUTED)
            axes[1].bar(x - 0.17, [r["cambios_r"] for r in rows], width=0.34,
                        color=TEAL, label="Resistencia")
            axes[1].bar(x + 0.17, [r["cambios_c"] for r in rows], width=0.34,
                        color=ORANGE, label="Condensador")
            axes[1].set_title("Cambios de componentes", color=TEXT, pad=15)
            axes[1].set_ylabel("Número de cambios", color=MUTED)
            axes[1].yaxis.set_major_locator(MaxNLocator(integer=True))
            axes[1].legend(facecolor=PANEL, edgecolor=EDGE, labelcolor=TEXT)
            layout.addWidget(self.canvas, 1)
            latest = rows[-1]
            layout.addWidget(label(
                f"Última misión: {latest['pruebas']} pruebas · "
                f"{latest['cambios_total']} cambios · {latest['tiempo_s']:.1f} s",
                "muted",
            ))
        close = QPushButton("VOLVER AL JUEGO")
        close.clicked.connect(lambda: self.motion.dismiss(self.accept))
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.motion = WidgetMotion(self)

    def showEvent(self, event):
        super().showEvent(event)
        self.motion.reveal(distance=0, duration=280)
