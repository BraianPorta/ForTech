"""Utilidades de widgets y configuración visual compartidas."""
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout

from ui.shared.style import APPLICATION_STYLE, BG, PANEL, TEXT, TEAL

# Raíz del proyecto usada para localizar recursos compartidos.
BASE = Path(__file__).resolve().parents[2]


def configureApplication(app: QApplication) -> None:
    """Carga las fuentes y configura el tema global de la aplicación."""
    for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf"):
        path = BASE / "assets" / "fonts" / name
        if QFontDatabase.addApplicationFont(str(path)) < 0:
            raise RuntimeError(f"No se pudo cargar la fuente {path.name}")
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, BG),
        (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.Base, PANEL),
        (QPalette.ColorRole.Text, TEXT),
        (QPalette.ColorRole.Button, PANEL),
        (QPalette.ColorRole.ButtonText, TEXT),
        (QPalette.ColorRole.Highlight, TEAL),
        (QPalette.ColorRole.HighlightedText, BG),
    ):
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
