"""Panel lateral con el objetivo, el enunciado y los datos de la misión."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout

from ui.shared.widgets import label

# Estilos del panel lateral de misión y sus objetivos.
MISSION_STYLE = """
QFrame#mission { background: #ffffff; border: 2px solid #e0d7ee; border-bottom: 6px solid #e0d7ee; border-radius: 24px; }
QLabel#hero { font-size: 30px; font-weight: 700; }
QLabel#gold { color: #392d57; font-size: 29px; font-weight: 700; }
QLabel#levelBadge { background: #7252ba; color: white; border-radius: 18px; padding: 14px; font-size: 20px; font-weight: 700; }
"""


class MissionPanel(QFrame):
    """Presenta el título de la misión, el enunciado y su objetivo."""

    def __init__(self, parent=None):
        """Construye el panel lateral con etiquetas de misión y objetivo."""
        super().__init__(parent)
        self.setStyleSheet(MISSION_STYLE)
        self.setObjectName("mission")
        self.setFixedWidth(232)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 24, 22, 24)
        layout.setSpacing(15)

        self.mission_tag = label("", "levelBadge")
        self.mission_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.mission_tag)
        self.mission_title = label("Despierta al robot", "hero", True)
        layout.addWidget(self.mission_title)
        self.device_name = label("", "muted", True)
        layout.addWidget(self.device_name)
        layout.addStretch(1)
        layout.addWidget(label("OBJETIVO", "eyebrow"))
        self.target_label = label("", "gold", True)
        layout.addWidget(self.target_label)
        self.tolerance_label = label("", "muted", True)
        layout.addWidget(self.tolerance_label)
