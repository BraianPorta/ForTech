"""Escena central del circuito, ilustraciones y simulación en segundo plano."""
import math
from PySide6.QtCore import QEasingCurve, QObject, QPointF, QRectF, QRunnable, QPropertyAnimation, QSequentialAnimationGroup, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGraphicsObject, QGraphicsScene, QGraphicsView, QWidget

from data import Challenge
from ui.shared.functions import simulate
from ui.shared.style import BG

class GameBackdrop(QWidget):
    """Papel cálido con confeti geométrico, dibujado sin imágenes externas."""

    resized = Signal()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG))
        painter.setPen(QPen(QColor("#e9decb"), 2))
        for x in range(18, self.width(), 28):
            for y in range(18, self.height(), 28):
                painter.drawPoint(x, y)
        painter.setPen(QPen(QColor("#e7d9fa"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for x, y in ((18, 155), (self.width() - 18, self.height() - 80)):
            painter.drawLine(x - 7, y, x + 7, y)
            painter.drawLine(x, y - 7, x, y + 7)

class ComponentItem(QGraphicsObject):
    """Componente seleccionable con propiedades Qt de opacidad y escala."""

    clicked = Signal(str)

    def __init__(self, identifier: str, value: float, label: str):
        super().__init__()
        self.identifier, self.value, self.label = identifier, value, label
        self.display_value = value
        self.active = False
        self.hovering = False
        self.setAcceptHoverEvents(True)
        self.animations = None
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Seleccionar y editar resistencia")

    def boundingRect(self) -> QRectF:
        return QRectF(-82, -55, 164, 115)

    def paint(self, painter: QPainter, _option, _widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ink = QColor("#66518a")
        accent = QColor("#a6dfcf")
        rect = QRectF(-77, -49, 154, 101)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#b2b6af"))
        painter.drawRoundedRect(rect.translated(0, 7), 19, 19)
        if self.active or self.hovering:
            painter.setPen(QPen(QColor("#9470cf"), 7))
        else:
            painter.setPen(QPen(ink, 2.5))
        painter.setBrush(accent.lighter(110) if self.hovering else accent)
        painter.drawRoundedRect(rect, 19, 19)
        painter.setPen(QPen(QColor("#ffffff"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(-56, -40), QPointF(42, -40))
        painter.setPen(QPen(ink, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path = QPainterPath(QPointF(-51, -4))
        path.lineTo(-38, -4)
        for i in range(8):
            path.lineTo(-30 + i * 8, -14 if i % 2 == 0 else 6)
        path.lineTo(38, -4)
        path.lineTo(51, -4)
        painter.drawPath(path)
        painter.setFont(QFont("DejaVu Sans", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(-68, -35, 136, 17), Qt.AlignmentFlag.AlignCenter, self.label)
        painter.setFont(QFont("DejaVu Sans", 12, QFont.Weight.Bold))
        painter.drawText(
            QRectF(-73, 20, 146, 26),
            Qt.AlignmentFlag.AlignCenter,
            f"{self.display_value:g} Ω",
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self.identifier)
        event.accept()

    def hoverEnterEvent(self, event):
        self.hovering = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.hovering = False
        self.update()
        super().hoverLeaveEvent(event)

    def replace(self, value: float, animated: bool = True):
        """Anima la sustitución y finaliza limpiamente una transición interrumpida."""
        if self.animations:
            self.animations.stop()
        self.setOpacity(1)
        self.setScale(1)
        self.value = value
        if not animated:
            self.display_value = value
            self.update()
            return
        group = QSequentialAnimationGroup(self)
        fade_out = QPropertyAnimation(self, b"opacity")
        fade_out.setDuration(100)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.15)
        def swap():
            self.display_value = value
            self.update()
        fade_out.finished.connect(swap)
        fade_in = QPropertyAnimation(self, b"opacity")
        fade_in.setDuration(180)
        fade_in.setStartValue(0.15)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(fade_out)
        group.addAnimation(fade_in)
        if self.animations:
            self.animations.deleteLater()
        self.animations = group
        group.start()


class CircuitView(QGraphicsView):
    """Circuito dinámico de ramas en paralelo con resistencias en serie."""

    selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.scene_model = QGraphicsScene(self)
        self.setScene(self.scene_model)
        self.setStyleSheet("border: none; background: transparent;")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(330)
        self.component_items: dict[str, ComponentItem] = {}
        self.rows: list[list[str]] = []
        self.phase = 0.0
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(50)
        self.animation_timer.timeout.connect(self.animate_field)
        self.animation_timer.start()

    def configure(self, rows: list[list[tuple[str, str, float]]]) -> None:
        self.scene_model.clear()
        self.component_items.clear()
        self.rows = [[identifier for identifier, _label, _value in row] for row in rows]
        maximum_components = max(len(row) for row in rows)
        right_rail = 390 + (maximum_components - 1) * 165
        height = max(300, 140 + (len(rows) - 1) * 115)
        self.right_rail = right_rail
        self.branch_y = [80 + index * 115 for index in range(len(rows))]
        self.scene_model.setSceneRect(0, 0, right_rail + 80, height)
        for row_index, row in enumerate(rows):
            y = self.branch_y[row_index]
            for component_index, (identifier, label, value) in enumerate(row):
                item = ComponentItem(identifier, value, label)
                item.setPos(220 + component_index * 165, y)
                item.clicked.connect(self.select)
                self.scene_model.addItem(item)
                self.component_items[identifier] = item
        self.viewport().update()
        self.fitInView(self.scene_model.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def current_rows(self) -> list[list[float]]:
        return [
            [self.component_items[identifier].value for identifier in row]
            for row in self.rows
        ]

    def animate_field(self):
        if self.isVisible():
            self.phase = (self.phase + 0.008) % 1
            self.viewport().update()

    def select(self, identifier: str):
        """Resalta el componente y solicita su menú contextual."""
        for component_id, item in self.component_items.items():
            item.active = component_id == identifier
            item.update()
        self.selected.emit(identifier)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.scene_model.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def drawBackground(self, painter, rect):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#abc7b8"))
        painter.drawRoundedRect(self.sceneRect().adjusted(10, 10, -10, -10), 30, 30)
        painter.setPen(QPen(QColor("#7fa791"), 2.5))
        painter.setBrush(QColor("#d9edcf"))
        painter.drawRoundedRect(self.sceneRect().adjusted(10, 4, -10, -16), 30, 30)
        painter.setPen(QPen(QColor("#bed5b4"), 1.5))
        for x in range(34, int(self.sceneRect().right()) - 20, 22):
            for y in range(27, int(self.sceneRect().bottom()) - 20, 22):
                painter.drawPoint(x, y)
        first_y, last_y = self.branch_y[0], self.branch_y[-1]
        left_rail, right_rail = 100, self.right_rail
        tracks = [((left_rail, first_y), (left_rail, last_y)),
                  ((right_rail, first_y), (right_rail, last_y))]
        for row_index, identifiers in enumerate(self.rows):
            y = self.branch_y[row_index]
            centers = [220 + index * 165 for index in range(len(identifiers))]
            tracks.append(((left_rail, y), (centers[0] - 82, y)))
            for start, end in zip(centers, centers[1:]):
                tracks.append(((start + 82, y), (end - 82, y)))
            tracks.append(((centers[-1] + 82, y), (right_rail, y)))
        for color, width in (("#8aac97", 13), ("#f8fff0", 7)):
            painter.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            for start, end in tracks:
                painter.drawLine(QPointF(*start), QPointF(*end))
        painter.setPen(QPen(QColor("#6c997c"), 2))
        painter.setBrush(QColor("#fff9ed"))
        for y in self.branch_y:
            painter.drawEllipse(QPointF(left_rail, y), 7, 7)
            painter.drawEllipse(QPointF(right_rail, y), 7, 7)
        painter.setPen(Qt.PenStyle.NoPen)


class DeviceIllustration(QWidget):
    """Robot de juguete que cobra vida al resolver el circuito."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(230)
        self.value = None
        self.unit = "Ω"
        self.passed = False
        self.phase = 0.0

    def animate(self):
        if self.isVisible():
            self.phase = (self.phase + 0.025) % math.tau
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        scale = min(self.width() / 220, self.height() / 280)
        p.scale(scale, scale)
        ink = QColor("#66518a")
        p.translate(0, math.sin(self.phase) * (3 if self.passed else 1.5))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#d8cbed"))
        p.drawEllipse(QRectF(-91, 100, 182, 22))
        p.setBrush(QColor("#e7dbfa"))
        p.drawEllipse(QPointF(0, -10), 98, 98)
        p.setPen(QPen(ink, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(0, -94), QPointF(0, -112))
        p.setBrush(QColor("#a8dfcc" if self.passed else "#ffb1a3"))
        p.drawEllipse(QPointF(0, -115), 7, 7)
        # Manos, botas y cuerpo de un pequeño robot de juguete.
        p.setBrush(QColor("#b49adf"))
        p.drawRoundedRect(QRectF(-46, 75, 32, 34), 9, 9)
        p.drawRoundedRect(QRectF(14, 75, 32, 34), 9, 9)
        p.drawRoundedRect(QRectF(-88, 3 if not self.passed else -18, 24, 47), 11, 11)
        p.drawRoundedRect(QRectF(64, 3 if not self.passed else -18, 24, 47), 11, 11)
        p.setBrush(QColor("#f7cb59"))
        p.drawRoundedRect(QRectF(-58, -14, 116, 100), 23, 23)
        p.setBrush(QColor("#ffe390"))
        p.drawRoundedRect(QRectF(-73, -96, 146, 107), 27, 27)
        p.setBrush(QColor("#f9fff5"))
        p.drawRoundedRect(QRectF(-59, -79, 118, 64), 20, 20)
        p.setBrush(QColor("#66518a"))
        if self.passed:
            p.setBrush(Qt.BrushStyle.NoBrush)
            for x in (-26, 26):
                p.drawArc(QRectF(x - 9, -60, 18, 18), 0, 180 * 16)
        elif self.value is None:
            for x in (-26, 26):
                p.drawLine(QPointF(x - 8, -49), QPointF(x + 8, -49))
        else:
            for x in (-26, 26):
                p.drawRoundedRect(QRectF(x - 5, -60, 10, 17), 5, 5)
        p.drawArc(QRectF(-13, -48, 26, 20), 180 * 16, 180 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f1b5ad"))
        p.drawEllipse(QPointF(-43, -38), 7, 4)
        p.drawEllipse(QPointF(43, -38), 7, 4)
        p.setPen(QPen(ink, 2))
        p.setBrush(QColor("#fff9ed"))
        p.drawRoundedRect(QRectF(-43, 21, 86, 36), 9, 9)
        p.setPen(ink)
        p.setFont(QFont("DejaVu Sans Mono", 11, QFont.Weight.Bold))
        p.drawText(QRectF(-42, 22, 84, 34), Qt.AlignmentFlag.AlignCenter,
                   f"{self.value:.2f} {self.unit}" if self.value is not None else "· · ·")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#52ab8c" if self.passed else "#d9a848"))
        p.drawEllipse(QPointF(0, 70), 5, 5)
        if self.passed:
            p.setPen(QPen(QColor("#a284cd"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for x, y in ((-90, -90), (88, -85), (80, 65)):
                p.drawLine(QPointF(x - 5, y), QPointF(x + 5, y))
                p.drawLine(QPointF(x, y - 5), QPointF(x, y + 5))


class WorkerSignals(QObject):
    finished = Signal(int, object, str)


class SimulationWorker(QRunnable):
    """Tarea sin acceso a widgets; devuelve una revisión para descartar resultados viejos."""

    def __init__(self, revision: int, challenge: Challenge, rows: list[list[float]]):
        super().__init__()
        self.revision, self.challenge = revision, challenge
        self.rows = rows
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = simulate(self.challenge, self.rows)
            self.signals.finished.emit(self.revision, result, "")
        except Exception as error:
            self.signals.finished.emit(self.revision, None, str(error))
