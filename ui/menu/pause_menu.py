"""Menú modal que bloquea la partida mientras está abierto."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from ui.shared.widgets import label


class PauseMenu(QWidget):
    resume_requested = Signal()
    home_requested = Signal()
    progress_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame#menuCard { background: #fff9ed; border: 3px solid #7252ba; border-bottom: 8px solid #7252ba; border-radius: 26px; }
            QLabel#menuTitle { color: #392d57; font-size: 30px; font-weight: 700; }
            QLabel#menuHint { color: #746985; font-size: 14px; }
            QPushButton#resume { background: #ffd35d; color: #392d57; border-color: #bd852d; border-bottom-color: #bd852d; }
        """)
        self.card = QFrame(self)
        self.card.setObjectName("menuCard")
        self.card.setFixedWidth(390)
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(14)
        title = label("PAUSA", "menuTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        hint = label("La partida está pausada.", "menuHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self.resume_button = QPushButton("REANUDAR PARTIDA")
        self.resume_button.setObjectName("resume")
        self.resume_button.clicked.connect(self.resume_requested.emit)
        layout.addWidget(self.resume_button)
        progress = QPushButton("VER MI PROGRESO")
        progress.clicked.connect(self.progress_requested.emit)
        layout.addWidget(progress)
        home = QPushButton("VOLVER A LA PANTALLA INICIAL")
        home.clicked.connect(self.home_requested.emit)
        layout.addWidget(home)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.setGeometry(self.parentWidget().rect())
        self.card.adjustSize()
        self.card.move(
            (self.width() - self.card.width()) // 2,
            (self.height() - self.card.height()) // 2,
        )
        self.raise_()
        self.resume_button.setFocus(Qt.FocusReason.PopupFocusReason)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(38, 29, 57))
