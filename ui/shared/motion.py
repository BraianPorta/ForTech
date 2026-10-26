"""Animaciones de aparición y cambios de misión sin bloquear la interfaz."""
from PySide6.QtCore import (QObject, QPoint, Property, QEasingCurve,
    QParallelAnimationGroup, QPropertyAnimation, QSequentialAnimationGroup, Qt)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


class WidgetMotion(QObject):
    """Fundido y desplazamiento coordinados, con interrupción segura."""

    def __init__(self, widget):
        """Prepara el efecto de opacidad para animar el widget indicado."""
        super().__init__(widget)
        self.widget, self.group = widget, None
        self.effect = QGraphicsOpacityEffect(widget)
        self.effect.setOpacity(1)
        widget.setGraphicsEffect(self.effect)

    def reset(self):
        """Detiene una animación y restaura el estado visible e interactivo."""
        if self.group is not None:
            self.group.stop()
            self.group.deleteLater()
            self.group = None
        self.effect.setOpacity(1)
        self.widget.setEnabled(True)

    def reveal(self, distance=10, duration=220, moving=None):
        """Muestra el widget con fundido y desplazamiento opcional."""
        self.reset()
        target = self.widget if moving is None else moving
        destination = target.pos()
        self.effect.setOpacity(0)
        self.widget.show()
        self.widget.raise_()
        group = QParallelAnimationGroup(self)
        fade = QPropertyAnimation(self.effect, b"opacity")
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setDuration(duration)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(fade)
        if distance:
            slide = QPropertyAnimation(target, b"pos")
            slide.setStartValue(destination + QPoint(0, distance))
            slide.setEndValue(destination)
            slide.setDuration(duration)
            slide.setEasingCurve(QEasingCurve.Type.OutCubic)
            group.addAnimation(slide)
        self.group = group
        group.start()

    def dismiss(self, on_finished=None):
        """Desvanece y oculta el widget tras finalizar la animación."""
        if not self.widget.isVisible() or not self.widget.isEnabled():
            return
        opacity = self.effect.opacity()
        self.reset()
        self.widget.setEnabled(False)
        group = QParallelAnimationGroup(self)
        fade = QPropertyAnimation(self.effect, b"opacity")
        fade.setStartValue(opacity)
        fade.setEndValue(0.0)
        fade.setDuration(140)
        fade.setEasingCurve(QEasingCurve.Type.InCubic)
        group.addAnimation(fade)
        group.finished.connect(on_finished if on_finished is not None else self.widget.hide)
        self.group = group
        group.start()


class SceneTransition(QWidget):
    """Cubre la escena, cambia de misión y la revela con un fundido suave."""

    def __init__(self, parent):
        """Inicializa la capa translúcida que cubre la escena."""
        super().__init__(parent)
        self._shade, self.group = 0.0, None
        self.hide()

    def getShade(self):
        """Devuelve la opacidad actual de la capa de transición."""
        return self._shade

    def setShade(self, value):
        """Actualiza la opacidad de la capa y solicita un repintado."""
        self._shade = value
        self.update()

    shade = Property(float, getShade, setShade)

    def play(self, change=None):
        """Cubre la escena, ejecuta el cambio y revela el nuevo contenido."""
        if self.group is not None:
            self.group.stop()
            self.group.deleteLater()
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        group = QSequentialAnimationGroup(self)
        if change is not None:
            cover = QPropertyAnimation(self, b"shade")
            cover.setStartValue(0.0)
            cover.setEndValue(1.0)
            cover.setDuration(180)
            cover.setEasingCurve(QEasingCurve.Type.InOutCubic)
            cover.finished.connect(change)
            group.addAnimation(cover)
        reveal = QPropertyAnimation(self, b"shade")
        reveal.setStartValue(1.0)
        reveal.setEndValue(0.0)
        reveal.setDuration(360)
        reveal.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(reveal)
        group.finished.connect(self.hide)
        self.group = group
        group.start()

    def paintEvent(self, _event):
        """Dibuja la capa de transición con la opacidad actual."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(255, 249, 237, int(255 * self._shade)))
