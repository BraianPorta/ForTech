"""Colores del tema y estilos globales de la aplicación."""
# Paleta base para fondos, texto, bordes y estados destacados.
BG, PANEL, EDGE = "#fff9ed", "#ffffff", "#dcd4e9"
TEXT, MUTED, TEAL, ORANGE = "#392d57", "#746985", "#21806b", "#a35b16"

# Reglas visuales compartidas por todos los widgets de la aplicación.
APPLICATION_STYLE = f"""
QWidget {{ color: {TEXT}; font-family: 'DejaVu Sans'; font-size: 13px; }}
QMainWindow, QDialog {{ background: {BG}; }}
QLabel {{ background: transparent; border: none; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#eyebrow {{ color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
QPushButton {{ color: {TEXT}; background: {PANEL}; border: 2px solid #c7b7e4; border-bottom: 5px solid #c7b7e4; border-radius: 15px; padding: 12px 18px; font-weight: 700; }}
QPushButton:hover {{ background: #f2ecff; border-color: #9274c6; }}
QPushButton:pressed {{ background: #e2d5f7; border-bottom-width: 2px; padding-top: 15px; }}
QPushButton:disabled {{ color: #9a90a7; background: #f0ecf4; border-color: #ded6e8; }}
QToolTip {{ color: {TEXT}; background: {PANEL}; border: 1px solid #c7b7e4; padding: 6px; }}
QScrollBar:vertical {{ background: {BG}; width: 9px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #c7b7e4; border-radius: 4px; min-height: 28px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
"""
