"""Escena central del circuito, ilustraciones y simulación en segundo plano."""
import math
from PySide6.QtCore import QEasingCurve, QObject, QPointF, QRectF, QRunnable, QPropertyAnimation, QSequentialAnimationGroup, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QGraphicsObject, QGraphicsScene, QGraphicsView, QWidget

from data import Challenge
from ui.shared.functions.electronic import simulate
from ui.shared.style import BG

# Dimensiones de piezas y separación mínima usada para distribuir el circuito.
COMPONENT_WIDTH = 124
COMPONENT_SPACING = 24
RAIL_MARGIN = 40


class GameBackdrop(QWidget):
    """Papel cálido con confeti geométrico, dibujado sin imágenes externas."""

    resized = Signal()

    def resizeEvent(self, event):
        """Solicita el repintado de la decoración después de un cambio de tamaño."""
        super().resizeEvent(event)
        self.resized.emit()

    def paintEvent(self, _event):
        """Dibuja el fondo y los detalles decorativos de la pantalla."""
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

    def __init__(
        self, identifier: str, value: float | None, label: str, unit: str = "Ω"
    ):
        """Inicializa una pieza interactiva del circuito."""
        super().__init__()
        self.identifier, self.value, self.label, self.unit = identifier, value, label, unit
        self.display_value = value
        self.active = False
        self.hovering = False
        self.setAcceptHoverEvents(True)
        self.animations = None
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Seleccionar y editar componente")

    def boundingRect(self) -> QRectF:
        """Devuelve el área de escena ocupada por la pieza."""
        return QRectF(-68, -52, 136, 104)

    def paint(self, painter: QPainter, _option, _widget=None):
        """Dibuja la carcasa, el símbolo y el valor actual de la pieza."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ink = QColor("#66518a")
        accent = QColor("#a6dfcf")
        rect = QRectF(-62, -41, COMPONENT_WIDTH, 82)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#b2b6af"))
        painter.drawRoundedRect(rect.translated(0, 6), 15, 15)
        if self.active or self.hovering:
            painter.setPen(QPen(QColor("#9470cf"), 5))
        else:
            painter.setPen(QPen(ink, 2.5))
        painter.setBrush(accent.lighter(110) if self.hovering else accent)
        painter.drawRoundedRect(rect, 15, 15)
        painter.setPen(QPen(QColor("#ffffff"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(-44, -32), QPointF(44, -32))
        painter.setPen(QPen(ink, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if self.unit == "W" or self.label.startswith("B"):
            painter.setBrush(QColor("#fff5c2"))
            painter.drawEllipse(QRectF(-11, -23, 22, 22))
            painter.drawLine(QPointF(-8, 5), QPointF(8, 5))
            painter.drawLine(QPointF(-6, 10), QPointF(6, 10))
            for start, end in (
                (QPointF(0, -31), QPointF(0, -27)),
                (QPointF(-22, -19), QPointF(-19, -17)),
                (QPointF(22, -19), QPointF(19, -17)),
            ):
                painter.drawLine(start, end)
        else:
            path = QPainterPath(QPointF(-43, 0))
            path.lineTo(-31, 0)
            for i in range(7):
                path.lineTo(-25 + i * 7, -7 if i % 2 == 0 else 7)
            path.lineTo(31, 0)
            path.lineTo(43, 0)
            painter.drawPath(path)
        painter.setFont(QFont("DejaVu Sans", 10, QFont.Weight.Bold))
        displayed_value = (
            f"{self.display_value:g} {self.unit}"
            if self.display_value is not None
            else "Selecciona"
        )
        painter.drawText(
            QRectF(-58, 17, 116, 22),
            Qt.AlignmentFlag.AlignCenter,
            displayed_value,
        )

    def mousePressEvent(self, event):
        """Notifica que el jugador ha pulsado la pieza."""
        self.clicked.emit(self.identifier)
        event.accept()

    def hoverEnterEvent(self, event):
        """Resalta la pieza al entrar el puntero."""
        self.hovering = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Retira el resaltado cuando sale el puntero."""
        self.hovering = False
        self.update()
        super().hoverLeaveEvent(event)

    def replace(self, value: float | None, animated: bool = True):
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
            """Actualiza el valor visible en el punto medio de la animación."""
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
    """Circuito dinámico de ramas en paralelo con componentes en serie."""

    selected = Signal(str)

    def __init__(self):
        """Prepara la escena y el temporizador de animación del circuito."""
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
        self.voltage: float | None = None
        self.phase = 0.0
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(50)
        self.animation_timer.timeout.connect(self.animateField)
        self.animation_timer.start()

    def configure(
        self,
        rows: list[list[tuple[str, str, float | None, str]]],
        voltage: float | None = None,
    ) -> None:
        """Construye y centra ramas, piezas y fuente en el área del circuito."""
        self.scene_model.clear()
        self.component_items.clear()
        self.rows = [[identifier for identifier, _label, _value, _unit in row] for row in rows]
        self.voltage = voltage
        maximum_components = max(len(row) for row in rows)
        component_group_width = (
            maximum_components * COMPONENT_WIDTH
            + (maximum_components - 1) * COMPONENT_SPACING
        )
        scene_width = max(420, component_group_width + 4 * RAIL_MARGIN)
        self.left_rail = RAIL_MARGIN
        self.right_rail = scene_width - RAIL_MARGIN
        row_spacing = 115
        content_height = (len(rows) - 1) * row_spacing + (
            167 if voltage is not None else 100
        )
        height = max(300, content_height + 60)
        first_y = (height - content_height) / 2 + 50
        self.branch_y = [first_y + index * row_spacing for index in range(len(rows))]
        self.source_y = self.branch_y[-1] + 80 if voltage is not None else None
        self.scene_model.setSceneRect(0, 0, scene_width, height)
        for row_index, row in enumerate(rows):
            y = self.branch_y[row_index]
            center_x = (self.left_rail + self.right_rail) / 2
            for component_index, (identifier, label, value, unit) in enumerate(row):
                item = ComponentItem(identifier, value, label, unit)
                offset = (
                    component_index - (len(row) - 1) / 2
                ) * (COMPONENT_WIDTH + COMPONENT_SPACING)
                item.setPos(center_x + offset, y)
                item.clicked.connect(self.select)
                self.scene_model.addItem(item)
                self.component_items[identifier] = item
        self.viewport().update()
        self.fitInView(self.scene_model.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def currentRows(self) -> list[list[float]]:
        """Devuelve los valores elegidos en el orden de las ramas."""
        rows = [
            [self.component_items[identifier].value for identifier in row]
            for row in self.rows
        ]
        if any(value is None for row in rows for value in row):
            raise ValueError("Selecciona todos los componentes antes de activar el circuito.")
        return [[value for value in row if value is not None] for row in rows]

    def animateField(self):
        """Actualiza la animación del circuito cuando la vista está visible."""
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
        """Ajusta la escala del circuito al tamaño visible de la vista."""
        super().resizeEvent(event)
        self.fitInView(self.scene_model.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def drawBackground(self, painter, rect):
        """Dibuja el tablero, los raíles y las conexiones entre piezas."""
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
        left_rail, right_rail = self.left_rail, self.right_rail
        tracks = [((left_rail, first_y), (left_rail, last_y)),
                  ((right_rail, first_y), (right_rail, last_y))]
        if self.source_y is not None:
            source_center = (left_rail + right_rail) / 2
            tracks.extend((
                ((left_rail, last_y), (left_rail, self.source_y)),
                ((right_rail, last_y), (right_rail, self.source_y)),
                ((left_rail, self.source_y), (source_center - 18, self.source_y)),
                ((source_center + 18, self.source_y), (right_rail, self.source_y)),
            ))
        for row_index, identifiers in enumerate(self.rows):
            y = self.branch_y[row_index]
            center_x = (left_rail + right_rail) / 2
            centers = [
                center_x + (index - (len(identifiers) - 1) / 2)
                * (COMPONENT_WIDTH + COMPONENT_SPACING)
                for index in range(len(identifiers))
            ]
            tracks.append(((left_rail, y), (centers[0] - COMPONENT_WIDTH / 2, y)))
            for start, end in zip(centers, centers[1:]):
                tracks.append((
                    (start + COMPONENT_WIDTH / 2, y),
                    (end - COMPONENT_WIDTH / 2, y),
                ))
            tracks.append((
                (centers[-1] + COMPONENT_WIDTH / 2, y),
                (right_rail, y),
            ))
        for color, width in (("#8aac97", 13), ("#f8fff0", 7)):
            painter.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            for start, end in tracks:
                painter.drawLine(QPointF(*start), QPointF(*end))
        painter.setPen(QPen(QColor("#6c997c"), 2))
        painter.setBrush(QColor("#fff9ed"))
        for y in self.branch_y:
            painter.drawEllipse(QPointF(left_rail, y), 7, 7)
            painter.drawEllipse(QPointF(right_rail, y), 7, 7)
        if self.source_y is not None and self.voltage is not None:
            source_center = (left_rail + right_rail) / 2
            painter.setPen(QPen(QColor("#6c997c"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(
                QPointF(source_center - 7, self.source_y - 12),
                QPointF(source_center - 7, self.source_y + 12),
            )
            painter.drawLine(
                QPointF(source_center + 7, self.source_y - 7),
                QPointF(source_center + 7, self.source_y + 7),
            )
            painter.setPen(QPen(QColor("#466d56"), 1))
            painter.setFont(QFont("DejaVu Sans", 10, QFont.Weight.Bold))
            painter.drawText(
                QRectF(source_center - 35, self.source_y + 17, 70, 20),
                Qt.AlignmentFlag.AlignCenter,
                f"{self.voltage:g} V",
            )
        painter.setPen(Qt.PenStyle.NoPen)


class DeviceIllustration(QWidget):
    """Robot de juguete que cobra vida al resolver el circuito."""

    def __init__(self):
        """Inicializa el estado visual y de animación del personaje."""
        super().__init__()
        self.setMinimumHeight(230)
        self.value = None
        self.unit = "Ω"
        self.passed = False
        self.phase = 0.0

    def animate(self):
        """Actualiza el movimiento del personaje si está visible."""
        if self.isVisible():
            self.phase = (self.phase + 0.025) % math.tau
            self.update()

    def paintEvent(self, _event):
        """Dibuja el personaje y el resultado actual del circuito."""
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
    """Transporta el resultado del cálculo desde el hilo de trabajo."""

    finished = Signal(int, object, str)


class SimulationWorker(QRunnable):
    """Tarea sin acceso a widgets; devuelve una revisión para descartar resultados viejos."""

    def __init__(self, revision: int, challenge: Challenge, rows: list[list[float]]):
        """Almacena la configuración inmutable que se calculará en segundo plano."""
        super().__init__()
        self.revision, self.challenge = revision, challenge
        self.rows = rows
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """Calcula la simulación y emite el resultado o el error asociado."""
        try:
            result = simulate(self.challenge, self.rows)
            self.signals.finished.emit(self.revision, result, "")
        except Exception as error:
            self.signals.finished.emit(self.revision, None, str(error))
