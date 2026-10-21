"""Escenario que agrupa el circuito, el robot y las acciones de juego."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

from game_widgets import CircuitView, DeviceIllustration, label
from ui.components.game_footer import GameFooter

CIRCUIT_STYLE = """
QFrame#playfield { background: #f1ecff; border: 2px solid #c7b7e4; border-bottom: 7px solid #c7b7e4; border-radius: 30px; }
QFrame#deviceDock { background: transparent; border: none; }
QLabel#badge { color: #6042a6; background: #eee6ff; border: 2px solid #d7c6f3; border-radius: 14px; padding: 8px 12px; font-size: 11px; font-weight: 700; }
QLabel#hint { color: #6042a6; font-size: 12px; font-weight: 700; }
"""


class CircuitPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(CIRCUIT_STYLE)
        self.setObjectName("playfield")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 24)
        layout.setSpacing(12)

        stage_header = QHBoxLayout()
        stage_header.addWidget(label("EL TALLER", "eyebrow"))
        stage_header.addStretch()
        self.level_path = label("", "hint")
        stage_header.addWidget(self.level_path)
        layout.addLayout(stage_header)

        arena = QHBoxLayout()
        arena.setSpacing(0)
        self.circuit = CircuitView()
        arena.addWidget(self.circuit, 1)
        dock = QFrame()
        dock.setObjectName("deviceDock")
        dock.setFixedWidth(210)
        device_layout = QVBoxLayout(dock)
        device_layout.setContentsMargins(0, 0, 0, 0)
        self.device = DeviceIllustration()
        self.device.setFixedHeight(280)
        self.circuit.animation_timer.timeout.connect(self.device.animate)
        device_layout.addStretch()
        device_layout.addWidget(self.device)
        self.status = label("", "badge", True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        device_layout.addWidget(self.status)
        device_layout.addStretch()
        arena.addWidget(dock)
        layout.addLayout(arena, 1)

        self.footer = GameFooter()
        layout.addWidget(self.footer)
