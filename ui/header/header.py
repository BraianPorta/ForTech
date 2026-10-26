"""Cabecera del juego con identidad, métricas y acceso al progreso."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ui.shared.style import TEXT
from ui.shared.widgets import label

# Estilos tipográficos y de superficie de la cabecera y sus métricas.
HEADER_STYLE = f"""
QLabel#title {{ color: #6042a6; font-size: 28px; font-weight: 700; letter-spacing: -1px; }}
QLabel#levelBadge {{ background: #7252ba; color: white; border-radius: 18px; padding: 14px; font-size: 20px; font-weight: 700; }}
QLabel#metric {{ color: {TEXT}; font-family: 'DejaVu Sans Mono'; font-size: 21px; font-weight: 700; }}
QFrame#hud {{ background: #ffffff; border: 2px solid #e0d7ee; border-bottom: 5px solid #e0d7ee; border-radius: 20px; }}
"""


class GameHeader(QWidget):
    """Muestra la marca, métricas de partida y acceso al menú."""

    def __init__(self, parent=None):
        """Construye la cabecera con sus indicadores y botón de menú."""
        super().__init__(parent)
        self.setStyleSheet(HEADER_STYLE)
        top = QHBoxLayout(self)
        top.setContentsMargins(0, 0, 0, 0)
        mark = label("ϟ", "levelBadge")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(56, 56)
        top.addWidget(mark)
        top.addSpacing(8)
        top.addWidget(label("ForTech", "title"))
        top.addStretch()

        hud = QFrame()
        hud.setObjectName("hud")
        metrics = QHBoxLayout(hud)
        metrics.setContentsMargins(20, 9, 20, 10)
        metrics.setSpacing(24)
        self.timer_label = label("00:00", "metric")
        self.changes_label = label("00", "metric")
        self.attempts_label = label("00", "metric")
        for title, value in (
            ("TIEMPO", self.timer_label),
            ("CAMBIOS", self.changes_label),
            ("INTENTOS", self.attempts_label),
        ):
            column = QVBoxLayout()
            column.setSpacing(0)
            column.addWidget(label(title, "eyebrow"))
            column.addWidget(value)
            metrics.addLayout(column)
        top.addWidget(hud)
        top.addSpacing(8)

        self.menu_button = QPushButton("☰")
        self.menu_button.setObjectName("quiet")
        self.menu_button.setAccessibleName("Abrir menú")
        self.menu_button.setToolTip("Menú")
        self.menu_button.setFixedWidth(56)
        top.addWidget(self.menu_button)
