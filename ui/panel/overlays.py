"""Inventario de componentes y pantalla de misión completada."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QGridLayout, QVBoxLayout, QPushButton, QWidget

from ui.shared.motion import WidgetMotion
from ui.shared.session import CATALOG
from ui.shared.widgets import label


class ComponentMenu(QFrame):
    """Inventario cerrado de piezas. No admite valores escritos por el jugador."""

    chosen = Signal(str, float)

    def __init__(self, parent):
        """Prepara el menú flotante con los valores disponibles."""
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame#componentMenu { background: #ffffff; border: 3px solid #7252ba; border-bottom: 7px solid #7252ba; border-radius: 18px; }
            QLabel#section { font-size: 20px; font-weight: 700; }
            QPushButton#preset { padding: 11px 7px; font-size: 12px; }
            QPushButton#preset:checked { background: #d6f2dc; border-color: #21806b; color: #216853; }
        """)
        self.setObjectName("componentMenu")
        self.setFixedWidth(302)
        self.kind = "R"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)
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

    def openAbove(self, component_id, current, anchor, kind="R"):
        """Posiciona el menú sobre la pieza y resalta el valor actual."""
        self.component_id, self.values = component_id, CATALOG[kind]
        unit = "W" if kind == "B" else "Ω"
        for index, button in enumerate(self.buttons):
            if index >= len(self.values):
                button.hide()
                continue
            value = self.values[index]
            button.show()
            button.setText(f"{value:g} {unit}")
            button.setChecked(current == value)
        self.adjustSize()
        x = max(10, min(anchor.center().x() - self.width() // 2,
                        self.parentWidget().width() - self.width() - 10))
        self.move(x, max(10, anchor.top() - self.height() - 12))
        self.motion.reveal()

    def dismiss(self):
        """Cierra el menú con su animación de salida."""
        self.motion.dismiss()

    def hide(self):
        """Oculta el menú y cancela cualquier animación activa."""
        if hasattr(self, "motion"):
            self.motion.reset()
        super().hide()

    def choose(self, value):
        """Notifica la selección realizada y cierra el menú."""
        self.dismiss()
        self.chosen.emit(self.component_id, float(value))


class VictoryOverlay(QWidget):
    """Pantalla de misión cumplida, sin gráficas durante la partida."""

    next_level = Signal()

    def __init__(self, parent):
        """Construye el resumen de victoria y las acciones para continuar."""
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
        self.advance_button = advance
        layout.addWidget(advance)
        self.session_feedback = label("", "muted", True)
        self.session_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_feedback.hide()
        layout.addWidget(self.session_feedback)
        self.motion = WidgetMotion(self)
        self.hide()

    def showRecord(self, record, session_complete=False, session_error=""):
        """Muestra las métricas del nivel y el estado de la sesión."""
        if self.isVisible():
            self.motion.reset()
        changes = "cambio" if record["cambios_total"] == 1 else "cambios"
        attempts = "prueba" if record["pruebas"] == 1 else "pruebas"
        self.summary.setText(
            f"{record['tiempo_s']:.1f} s     /     {record['cambios_total']} "
            f"{changes}     /     {record['pruebas']} {attempts}"
        )
        self.advance_button.setText(
            "VOLVER AL INICIO" if session_complete else "SIGUIENTE MISIÓN  →"
        )
        if session_complete:
            self.session_feedback.setText(
                "Todas las actividades completadas. "
                + (
                    "No se pudieron guardar las estadísticas: " + session_error
                    if session_error else "Las estadísticas de la sesión están guardadas."
                )
            )
            self.session_feedback.show()
        else:
            self.session_feedback.hide()
        self.setGeometry(self.parentWidget().rect())
        self.box.adjustSize()
        self.box.move((self.width() - self.box.width()) // 2,
                      (self.height() - self.box.height()) // 2)
        if not self.isVisible():
            self.motion.reveal(distance=22, duration=340, moving=self.box)

    def hide(self):
        """Oculta la superposición y restaura su efecto visual."""
        if hasattr(self, "motion"):
            self.motion.reset()
        super().hide()

    def paintEvent(self, _event):
        """Dibuja el velo translúcido detrás del resumen de victoria."""
        QPainter(self).fillRect(self.rect(), QColor(244, 235, 255, 225))
