"""Acciones de la partida y mensajes de resultado."""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton

from ui.shared.widgets import label

# Aspecto compartido por las acciones principales e información del resultado.
FOOTER_STYLE = """
QFrame#controls { background: transparent; border: none; }
QPushButton#primary { background: #ffd35d; color: #392d57; border: 2px solid #bd852d; border-bottom: 6px solid #bd852d; padding: 17px 32px; font-size: 16px; border-radius: 18px; }
QPushButton#primary:hover { background: #ffe38b; }
QPushButton#primary:pressed { background: #f4c34c; border-bottom-width: 2px; padding-top: 21px; }
QPushButton#primary:disabled { background: #ece3c8; border-color: #cfc3a7; color: #908773; }
QPushButton#reset { font-size: 24px; padding: 7px; }
"""


class GameFooter(QFrame):
    """Barra inferior con mensajes, reinicio y activación de la simulación."""

    def __init__(self, parent=None):
        """Crea y organiza los controles inferiores de la partida."""
        super().__init__(parent)
        self.setStyleSheet(FOOTER_STYLE)
        self.setObjectName("controls")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        self.feedback = label("", "muted", True)
        layout.addWidget(self.feedback, 1)
        self.reset_button = QPushButton("↻")
        self.reset_button.setObjectName("reset")
        self.reset_button.setAccessibleName("Reiniciar misión")
        self.reset_button.setToolTip("Reiniciar misión")
        self.reset_button.setFixedWidth(56)
        layout.addWidget(self.reset_button)
        self.simulate_button = QPushButton("ϟ  ACTIVAR")
        self.simulate_button.setObjectName("primary")
        layout.addWidget(self.simulate_button)
