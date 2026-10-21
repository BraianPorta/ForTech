"""Inventario de componentes y pantalla de misión completada."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ui.shared.motion import WidgetMotion
from ui.shared.session import CATALOG
from ui.shared.widgets import label


class ComponentMenu(QFrame):
    """Inventario cerrado de piezas. No admite valores escritos por el jugador."""

    chosen = Signal(str, float)

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame#componentMenu { background: #ffffff; border: 3px solid #7252ba; border-bottom: 7px solid #7252ba; border-radius: 18px; }
            QLabel#section { font-size: 20px; font-weight: 700; }
            QPushButton#preset { padding: 11px 7px; font-size: 12px; }
            QPushButton#preset:checked { background: #d6f2dc; border-color: #21806b; color: #216853; }
            QPushButton#closeMenu { padding: 2px 8px; border: none; background: transparent; color: #746985; }
        """)
        self.setObjectName("componentMenu")
        self.setFixedWidth(302)
        self.kind = "R"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)
        top = QHBoxLayout()
        self.title = label("", "section")
        top.addWidget(self.title, 1)
        close = QPushButton("×")
        close.setObjectName("closeMenu")
        close.setAccessibleName("Cerrar inventario")
        close.clicked.connect(self.dismiss)
        top.addWidget(close)
        layout.addLayout(top)
        grid = QGridLayout()
        grid.setSpacing(7)
        self.buttons = []
        for index in range(6):
            button = QPushButton()
            button.setObjectName("preset")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, i=index: self.choose(self.values[i]))
            grid.addWidget(button, index // 3, index % 3)
            self.buttons.append(button)
        layout.addLayout(grid)
        self.motion = WidgetMotion(self)
        self.hide()

    def open_above(self, kind, current, anchor):
        self.kind, self.values = kind, CATALOG[kind]
        unit = "Ω" if kind == "R" else "µF"
        self.title.setText("R1 · Resistencia" if kind == "R" else "C1 · Condensador")
        for button, value in zip(self.buttons, self.values):
            button.setText(f"{value:g} {unit}")
            button.setChecked(current == value)
        self.adjustSize()
        x = max(10, min(anchor.center().x() - self.width() // 2,
                        self.parentWidget().width() - self.width() - 10))
        self.move(x, max(10, anchor.top() - self.height() - 12))
        self.motion.reveal()

    def dismiss(self):
        self.motion.dismiss()

    def hide(self):
        if hasattr(self, "motion"):
            self.motion.reset()
        super().hide()

    def choose(self, value):
        self.dismiss()
        self.chosen.emit(self.kind, float(value))


class VictoryOverlay(QWidget):
    """Pantalla de misión cumplida sin gráficas durante la partida."""

    next_level = Signal()
    statistics = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame#victory { background: #fff9ed; border: 3px solid #7252ba; border-bottom: 9px solid #7252ba; border-radius: 28px; }
            QLabel#gold { color: #392d57; font-size: 29px; font-weight: 700; }
            QLabel#hero { font-size: 30px; font-weight: 700; }
            QLabel#section { font-size: 20px; font-weight: 700; }
        """)
        self.box = QFrame(self)
        self.box.setObjectName("victory")
        self.box.setFixedWidth(550)
        layout = QVBoxLayout(self.box)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(16)
        for text, style in [("✦  ✦  ✦", "gold"), ("¡NIVEL SUPERADO!", "hero")]:
            item = label(text, style)
            item.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(item)
        self.summary = label("", "section", True)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary)
        advance = QPushButton("SIGUIENTE MISIÓN  →")
        advance.setObjectName("primary")
        advance.clicked.connect(self.next_level.emit)
        layout.addWidget(advance)
        progress = QPushButton("VER MI PROGRESO")
        progress.clicked.connect(self.statistics.emit)
        layout.addWidget(progress)
        self.motion = WidgetMotion(self)
        self.hide()

    def show_record(self, record):
        if self.isVisible():
            self.motion.reset()
        changes = "cambio" if record["cambios_total"] == 1 else "cambios"
        attempts = "prueba" if record["pruebas"] == 1 else "pruebas"
        self.summary.setText(
            f"{record['tiempo_s']:.1f} s     /     {record['cambios_total']} "
            f"{changes}     /     {record['pruebas']} {attempts}"
        )
        self.setGeometry(self.parentWidget().rect())
        self.box.adjustSize()
        self.box.move((self.width() - self.box.width()) // 2,
                      (self.height() - self.box.height()) // 2)
        if not self.isVisible():
            self.motion.reveal(distance=22, duration=340, moving=self.box)

    def hide(self):
        if hasattr(self, "motion"):
            self.motion.reset()
        super().hide()

    def paintEvent(self, _event):
        QPainter(self).fillRect(self.rect(), QColor(244, 235, 255, 225))
