"""Piezas vectoriales, escena y tareas científicas reutilizadas por el juego."""
from pathlib import Path
import math
from PySide6.QtCore import QEasingCurve, QObject, QPointF, QRectF, QRunnable, QPropertyAnimation, QSequentialAnimationGroup, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPalette, QPen, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsObject, QGraphicsScene, QGraphicsView, QLabel, QVBoxLayout, QWidget
from scientific_model import Challenge, simulate
from ui.style import APPLICATION_STYLE, BG, PANEL, TEXT, TEAL
BASE = Path(__file__).resolve().parent

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

def configure_application(app: QApplication):
    """Carga fuentes incluidas para que también funcione el render sin escritorio."""
    for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf"):
        path = BASE / "assets" / "fonts" / name
        if QFontDatabase.addApplicationFont(str(path)) < 0:
            raise RuntimeError(f"No se pudo cargar la fuente {path.name}")
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, BG),
                        (QPalette.ColorRole.WindowText, TEXT),
                        (QPalette.ColorRole.Base, PANEL),
                        (QPalette.ColorRole.Text, TEXT),
                        (QPalette.ColorRole.Button, PANEL),
                        (QPalette.ColorRole.ButtonText, TEXT),
                        (QPalette.ColorRole.Highlight, TEAL),
                        (QPalette.ColorRole.HighlightedText, BG)):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setFont(QFont("DejaVu Sans", 10))
    app.setStyleSheet(APPLICATION_STYLE)


def label(text: str, kind: str = "", wrap: bool = False) -> QLabel:
    """Crea una etiqueta con un estilo semántico compartido."""
    item = QLabel(text)
    item.setObjectName(kind)
    item.setWordWrap(wrap)
    return item


def card() -> tuple[QFrame, QVBoxLayout]:
    """Crea un panel con márgenes y separación comunes."""
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return frame, layout


class ComponentItem(QGraphicsObject):
    """Componente seleccionable con propiedades Qt de opacidad y escala."""

    clicked = Signal(str)

    def __init__(self, kind: str, value: float):
        super().__init__()
        self.kind, self.value = kind, value
        self.active = False
        self.hovering = False
        self.setAcceptHoverEvents(True)
        self.animations = None
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Seleccionar y editar " + ("resistencia" if kind == "R" else "condensador"))

    def boundingRect(self) -> QRectF:
        return QRectF(-82, -55, 164, 115)

    def paint(self, painter: QPainter, _option, _widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ink = QColor("#66518a")
        accent = QColor("#a6dfcf" if self.kind == "R" else "#ffc18f")
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
        if self.kind == "R":
            path = QPainterPath(QPointF(-51, -4))
            path.lineTo(-38, -4)
            for i in range(8):
                path.lineTo(-30 + i * 8, -14 if i % 2 == 0 else 6)
            path.lineTo(38, -4)
            path.lineTo(51, -4)
            painter.drawPath(path)
        else:
            painter.drawLine(QPointF(-48, -4), QPointF(-12, -4))
            painter.drawLine(QPointF(-12, -17), QPointF(-12, 9))
            painter.drawLine(QPointF(12, -17), QPointF(12, 9))
            painter.drawLine(QPointF(12, -4), QPointF(48, -4))
        painter.setFont(QFont("DejaVu Sans", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(-68, -35, 136, 17), Qt.AlignmentFlag.AlignCenter, self.kind + "1")
        painter.setFont(QFont("DejaVu Sans", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(-73, 20, 146, 26), Qt.AlignmentFlag.AlignCenter,
                         f"{self.value:g} {'Ω' if self.kind == 'R' else 'µF'}")

    def mousePressEvent(self, event):
        self.clicked.emit(self.kind)
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
        if not animated:
            self.value = value
            self.update()
            return
        group = QSequentialAnimationGroup(self)
        fade_out = QPropertyAnimation(self, b"opacity")
        fade_out.setDuration(100)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.15)
        def swap():
            self.value = value
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
    """Escena RC de topología fija, escalada automáticamente al panel."""

    selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.scene_model = QGraphicsScene(0, 0, 700, 330, self)
        self.setScene(self.scene_model)
        self.setStyleSheet("border: none; background: transparent;")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(330)
        self.resistor = ComponentItem("R", 1000)
        self.capacitor = ComponentItem("C", 470)
        self.resistor.setPos(315, 115)
        self.capacitor.setPos(535, 188)
        for item in (self.resistor, self.capacitor):
            self.scene_model.addItem(item)
            item.clicked.connect(self.select)
        self.voltage = 5.0
        self.measured = None
        self.phase = 0.0
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(50)
        self.animation_timer.timeout.connect(self.animate_field)
        self.animation_timer.start()

    def animate_field(self):
        if self.isVisible():
            self.phase = (self.phase + 0.008) % 1
            self.viewport().update()

    def select(self, kind: str):
        """Resalta el componente y solicita su menú contextual."""
        for item in (self.resistor, self.capacitor):
            item.active = item.kind == kind
            item.update()
        self.selected.emit(kind)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.scene_model.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def drawBackground(self, painter, rect):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#abc7b8"))
        painter.drawRoundedRect(QRectF(10, 44, 680, 285), 30, 30)
        painter.setPen(QPen(QColor("#7fa791"), 2.5))
        painter.setBrush(QColor("#d9edcf"))
        painter.drawRoundedRect(QRectF(10, 34, 680, 285), 30, 30)
        painter.setPen(QPen(QColor("#bed5b4"), 1.5))
        for x in range(34, 685, 22):
            for y in range(57, 310, 22):
                painter.drawPoint(x, y)
        for x, y in ((30, 54), (670, 54), (30, 299), (670, 299)):
            painter.setPen(QPen(QColor("#7fa791"), 2))
            painter.setBrush(QColor("#f5f9e9"))
            painter.drawEllipse(QPointF(x, y), 6, 6)
            painter.drawLine(QPointF(x - 3, y), QPointF(x + 3, y))
        tracks = [((105, 115), (238, 115)), ((392, 115), (535, 115)),
                  ((535, 115), (535, 139)), ((535, 237), (535, 275)),
                  ((535, 275), (105, 275)), ((105, 275), (105, 225)),
                  ((105, 161), (105, 115))]
        for color, width in (("#8aac97", 13), ("#f8fff0", 7)):
            painter.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            for start, end in tracks:
                painter.drawLine(QPointF(*start), QPointF(*end))
        painter.setBrush(QColor("#ffdb75"))
        painter.setPen(QPen(QColor("#a17c3b"), 2.5))
        painter.drawEllipse(QPointF(105, 193), 32, 32)
        painter.drawLine(QPointF(96, 181), QPointF(114, 181))
        painter.drawLine(QPointF(105, 172), QPointF(105, 190))
        painter.drawLine(QPointF(98, 207), QPointF(112, 207))
        painter.setFont(QFont("DejaVu Sans", 10, QFont.Weight.Bold))
        painter.setPen(QColor("#4b715b"))
        painter.drawText(QRectF(43, 73, 125, 25), Qt.AlignmentFlag.AlignCenter, f"{self.voltage:g} V")
        painter.setPen(QPen(QColor("#6c997c"), 2))
        painter.setBrush(QColor("#fff9ed"))
        for point in ((535, 115), (535, 275), (105, 275)):
            painter.drawEllipse(QPointF(*point), 7, 7)
        painter.setPen(Qt.PenStyle.NoPen)
        for offset in (0, 0.33, 0.66):
            x = 105 + ((self.phase + offset) % 1) * 430
            painter.setBrush(QColor("#e9ac39"))
            painter.drawEllipse(QPointF(x, 115), 4, 4)
            painter.drawEllipse(QPointF(640 - x, 275), 4, 4)


class DeviceIllustration(QWidget):
    """Robot de juguete que cobra vida al resolver el circuito."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(230)
        self.voltage = None
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
        elif self.voltage is None:
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
                   f"{self.voltage:.2f} V" if self.voltage is not None else "· · ·")
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

    def __init__(self, revision: int, challenge: Challenge, resistance: float, capacity: float):
        super().__init__()
        self.revision, self.challenge = revision, challenge
        self.resistance, self.capacity = resistance, capacity
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = simulate(self.challenge, self.resistance, self.capacity)
            self.signals.finished.emit(self.revision, result, "")
        except Exception as error:
            self.signals.finished.emit(self.revision, None, str(error))

