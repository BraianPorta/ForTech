"""Selección de personaje antes de entrar en la partida."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.shared.widgets import label


class StartScreen(QWidget):
    """Permite elegir una aventura y consultar su disponibilidad."""

    character_selected = Signal(str)
    statistics_requested = Signal()

    def __init__(self, parent=None):
        """Crea las tarjetas de personajes y el acceso a estadísticas."""
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget#startScreen { background: #fff9ed; }
            QLabel#brand { color: #6042a6; font-size: 18px; font-weight: 700; letter-spacing: 2px; }
            QLabel#title { color: #392d57; font-size: 38px; font-weight: 700; }
            QLabel#subtitle { color: #746985; font-size: 16px; }
            QFrame#characterCard { background: #ffffff; border: 2px solid #e0d7ee; border-bottom: 7px solid #e0d7ee; border-radius: 24px; }
            QFrame#unavailableCard { background: #f4f0f7; border: 2px solid #e2dce8; border-bottom: 7px solid #e2dce8; border-radius: 24px; }
            QLabel#characterName { color: #392d57; font-size: 30px; font-weight: 700; }
            QLabel#characterDetail { color: #746985; font-size: 14px; }
            QPushButton#characterAction { background: #ffd35d; color: #392d57; border: 2px solid #bd852d; border-bottom: 6px solid #bd852d; padding: 14px 22px; font-size: 15px; border-radius: 18px; }
            QPushButton#characterAction:hover { background: #ffe38b; }
            QPushButton#characterAction:disabled { color: #9a90a7; background: #e7e1ec; border-color: #cec5d6; }
        """)
        self.setObjectName("startScreen")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(18)
        layout.addStretch(1)

        brand = label("FORTECH", "brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)
        title = label("¿Ready?", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = label("Elige una aventura para continuar.", "subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        cards = QHBoxLayout()
        cards.setSpacing(24)
        cards.addStretch(1)
        self.leire_card, self.leire_button = self.makeCard(
            "Leire",
            "Retos de circuitos eléctricos",
            "JUGAR",
            lambda: self.character_selected.emit("leire"),
        )
        cards.addWidget(self.leire_card)
        self.unai_card, self.unai_button = self.makeCard(
            "Unai",
            "Su aventura todavía se está preparando.",
            "PRÓXIMAMENTE",
            lambda: self.character_selected.emit("unai"),
            available=False,
        )
        self.unai_detail = self.unai_card.findChild(QLabel, "characterDetail")
        self.unai_portrait = self.unai_card.findChild(QLabel, "characterPortrait")
        cards.addWidget(self.unai_card)
        self.braian_card, self.braian_button = self.makeCard(
            "Braian",
            "Su aventura todavía se está preparando.",
            "PRÓXIMAMENTE",
            None,
            available=False,
        )
        self.completed_modes = set()
        cards.addWidget(self.braian_card)
        cards.addStretch(1)
        layout.addLayout(cards)
        layout.addStretch(1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.statistics_button = QPushButton("VER ESTADÍSTICAS")
        self.statistics_button.setObjectName("characterAction")
        self.statistics_button.clicked.connect(self.statistics_requested.emit)
        footer.addWidget(self.statistics_button)
        layout.addLayout(footer)

    def setAvailableModes(self, modes):
        """Actualiza disponibilidad y estado visual de las aventuras."""
        self.leire_button.setEnabled(0 in modes)
        self.unai_button.setEnabled(1 in modes)
        self.updateActionLabels(modes)
        self.unai_card.setObjectName("characterCard" if 1 in modes else "unavailableCard")
        self.unai_card.style().unpolish(self.unai_card)
        self.unai_card.style().polish(self.unai_card)
        if self.unai_detail is not None:
            self.unai_detail.setText(
                "Retos del modo Unai." if 1 in modes
                else "Su aventura todavía se está preparando."
            )

    def markCompleted(self, mode):
        """Marca una aventura como completada sin impedir volver a jugarla."""
        self.completed_modes.add(mode)
        self.updateActionLabels({
            current_mode
            for current_mode, button in ((0, self.leire_button), (1, self.unai_button))
            if button.isEnabled()
        })

    def updateActionLabels(self, available_modes):
        """Sincroniza las etiquetas de acción con disponibilidad y progreso."""
        for mode, button in ((0, self.leire_button), (1, self.unai_button)):
            if mode not in available_modes:
                button.setText("PRÓXIMAMENTE")
            else:
                button.setText(
                    "✓ COMPLETADO" if mode in self.completed_modes else "JUGAR"
                )

    @staticmethod
    def makeCard(name, detail, action_text, action, available=True):
        """Crea una tarjeta de personaje y devuelve la tarjeta y su botón."""
        card = QFrame()
        card.setObjectName("characterCard" if available else "unavailableCard")
        card.setFixedSize(330, 290)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(14)
        portrait = label(name[0], "characterPortrait")
        portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        portrait.setFixedSize(84, 84)
        portrait.setStyleSheet(
            "background: #c8f1e2; color: #287966; border-radius: 42px; font-weight: 700;"
            if name == "Unai" else
            "background: #eee6ff; color: #6042a6; border-radius: 42px; font-weight: 700;"
            if available else
            "background: #e7e1ec; color: #8d8497; border-radius: 42px; font-weight: 700;"
        )
        layout.addWidget(portrait, alignment=Qt.AlignmentFlag.AlignHCenter)
        name_label = label(name, "characterName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)
        detail_label = label(detail, "characterDetail", True)
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(detail_label, 1)
        button = QPushButton(action_text)
        button.setObjectName("characterAction")
        button.setEnabled(available)
        if action is not None:
            button.clicked.connect(action)
        layout.addWidget(button)
        return card, button
