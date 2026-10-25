"""Contexto visual y bloques de entrada para los retos de mecánica de fluidos."""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.shared.flow import FLOW_EXERCISES, FlowExercise


class FlowDiagram(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.diagram = "flow"
        self.setMinimumHeight(112)
        self.setMaximumHeight(128)

    def set_diagram(self, diagram: str):
        self.diagram = diagram
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f7faff"))
        center_y = self.height() / 2
        left, right = 42, self.width() - 42
        painter.setPen(QPen(QColor("#43536b"), 2))
        painter.setBrush(QColor("#dce8f3"))
        painter.drawRoundedRect(QRectF(left, center_y - 22, right - left, 44), 12, 12)
        painter.setPen(QPen(QColor("#168bc5"), 4, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(left + 42, center_y), QPointF(right - 42, center_y))
        arrow = QPainterPath()
        arrow.moveTo(right - 42, center_y)
        arrow.lineTo(right - 58, center_y - 9)
        arrow.lineTo(right - 58, center_y + 9)
        arrow.closeSubpath()
        painter.setBrush(QColor("#168bc5"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(arrow)

        painter.setPen(QPen(QColor("#43536b"), 2))
        painter.setBrush(QColor("#f8fbff"))
        painter.drawEllipse(QRectF(left - 8, center_y - 22, 16, 44))
        painter.drawEllipse(QRectF(right - 8, center_y - 22, 16, 44))
        painter.setPen(QColor("#43536b"))
        painter.setFont(QFont("DejaVu Sans", 9, QFont.Weight.Bold))
        if self.diagram == "heat":
            painter.setPen(QPen(QColor("#ef7564"), 3, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            for x in (self.width() * 0.3, self.width() * 0.5, self.width() * 0.7):
                painter.drawLine(QPointF(x, center_y - 38), QPointF(x + 5, center_y - 53))
            painter.setPen(QColor("#d85d5d"))
            painter.drawText(QRectF(left, center_y - 58, right - left, 16),
                            Qt.AlignmentFlag.AlignCenter, "Calor disipado Q")
            painter.setPen(QColor("#43536b"))
            painter.drawText(QRectF(left, center_y + 25, right - left, 20),
                            Qt.AlignmentFlag.AlignCenter,
                            "Superficie Ts · tubo de 1 m · aire a 20 °C")
        elif self.diagram == "pressure":
            painter.setPen(QPen(QColor("#d85d5d"), 2, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(left + 20, center_y - 38),
                             QPointF(right - 20, center_y - 38))
            painter.setPen(QColor("#d85d5d"))
            painter.drawText(QRectF(left, center_y - 59, right - left, 18),
                            Qt.AlignmentFlag.AlignCenter,
                            "P1  ·  línea de gradiente hidráulico  ·  P2")
            painter.setPen(QColor("#43536b"))
            painter.drawText(QRectF(left, center_y + 25, right - left, 20),
                            Qt.AlignmentFlag.AlignCenter,
                            "Agua · v = 2 m/s · tubería de PVC")
        else:
            painter.drawText(QRectF(right - 40, center_y - 42, 38, 18),
                            Qt.AlignmentFlag.AlignCenter, "D")
            painter.drawText(QRectF(left + 30, center_y - 42, 38, 18),
                            Qt.AlignmentFlag.AlignCenter, "v")
            painter.setPen(QColor("#43536b"))
            painter.drawText(QRectF(left, center_y + 25, right - left, 20),
                            Qt.AlignmentFlag.AlignCenter,
                            "Agua a 20 °C · compara v y D para obtener flujo laminar")


class FlowExercisePanel(QWidget):
    parameter_changed = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.exercise_type = ""
        self.values: dict[str, float] = {}
        self.selectors: dict[str, QComboBox] = {}
        self.setStyleSheet("""
            QFrame#flowCard { background: #ffffff; border: 1px solid #dce5ef; border-radius: 12px; }
            QLabel#flowTitle { color: #392d57; font-size: 19px; font-weight: 700; }
            QLabel#flowPrompt { color: #343d4b; font-size: 13px; }
            QLabel#flowFormula { color: #34465d; background: #eef6fd; border-radius: 10px; padding: 9px; font-size: 12px; }
            QLabel#flowConstants { color: #536174; font-size: 11px; }
            QLabel#flowObjective { color: #176c9b; font-weight: 700; font-size: 12px; }
            QLabel#flowParameter { color: #6042a6; font-size: 11px; font-weight: 700; }
            QLabel#flowStatus { color: #6042a6; font-size: 12px; font-weight: 700; }
            QComboBox#flowSelector { background: #ffffff; border: 2px solid #c7b7e4; border-radius: 9px; padding: 7px 10px; color: #392d57; font-size: 14px; min-width: 105px; }
            QComboBox#flowSelector:focus { border-color: #7252ba; }
            QComboBox#flowSelector:disabled { color: #898391; background: #f0edf4; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 0, 4, 0)
        root.setSpacing(7)

        heading = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("flowTitle")
        heading.addWidget(self.title)
        heading.addStretch()
        self.objective = QLabel()
        self.objective.setObjectName("flowObjective")
        heading.addWidget(self.objective)
        root.addLayout(heading)

        self.prompt = QLabel()
        self.prompt.setObjectName("flowPrompt")
        self.prompt.setWordWrap(True)
        root.addWidget(self.prompt)

        self.diagram = FlowDiagram()
        root.addWidget(self.diagram)

        formula_card = QFrame()
        formula_card.setObjectName("flowCard")
        formula_layout = QVBoxLayout(formula_card)
        formula_layout.setContentsMargins(10, 7, 10, 7)
        formula_layout.setSpacing(4)
        self.formula = QLabel()
        self.formula.setObjectName("flowFormula")
        self.formula.setWordWrap(True)
        formula_layout.addWidget(self.formula)
        self.constants = QLabel()
        self.constants.setObjectName("flowConstants")
        self.constants.setWordWrap(True)
        formula_layout.addWidget(self.constants)
        root.addWidget(formula_card)

        choices = QHBoxLayout()
        self.choice_title = QLabel("AJUSTA LOS BLOQUES")
        self.choice_title.setStyleSheet(
            "color: #6042a6; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        choices.addWidget(self.choice_title)
        choices.addStretch()
        self.status = QLabel()
        self.status.setObjectName("flowStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight)
        choices.addWidget(self.status)
        root.addLayout(choices)
        self.parameters_layout = QHBoxLayout()
        self.parameters_layout.setSpacing(12)
        root.addLayout(self.parameters_layout)
        root.addStretch(1)

    def set_exercise(self, exercise_type: str, prompt: str | None = None):
        if exercise_type not in FLOW_EXERCISES:
            raise ValueError(f"Tipo de ejercicio no admitido: {exercise_type!r}")
        exercise: FlowExercise = FLOW_EXERCISES[exercise_type]
        self.exercise_type = exercise_type
        self.title.setText(exercise.title)
        self.prompt.setText(prompt or exercise.prompt)
        self.objective.setText(exercise.objective)
        self.formula.setText(exercise.formula)
        self.constants.setText(exercise.constants)
        self.diagram.set_diagram(exercise.diagram)
        self.status.clear()
        self.values = {parameter.key: parameter.initial for parameter in exercise.parameters}
        self.selectors.clear()
        while self.parameters_layout.count():
            item = self.parameters_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        for parameter in exercise.parameters:
            card = QFrame()
            card.setObjectName("flowCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 7, 10, 8)
            card_layout.setSpacing(4)
            label = QLabel(parameter.label)
            label.setObjectName("flowParameter")
            selector = QComboBox()
            selector.setObjectName("flowSelector")
            for option in parameter.options:
                selector.addItem(f"{option:g} {parameter.unit}", option)
            selector.setCurrentIndex(parameter.options.index(parameter.initial))
            selector.currentIndexChanged.connect(
                lambda _index, key=parameter.key, control=selector:
                    self._selection_changed(key, control)
            )
            card_layout.addWidget(label)
            card_layout.addWidget(selector)
            self.parameters_layout.addWidget(card, 1)
            self.selectors[parameter.key] = selector
        self.parameters_layout.addStretch(1)

    def _selection_changed(self, key: str, selector: QComboBox):
        previous = self.values[key]
        selected = float(selector.currentData())
        if previous == selected:
            return
        self.values[key] = selected
        self.parameter_changed.emit(key, previous, selected)

    def set_parameters_enabled(self, enabled: bool):
        for selector in self.selectors.values():
            selector.setEnabled(enabled)
