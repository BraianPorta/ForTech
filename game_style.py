"""Tema arcade claro: papel crema, tinta violeta y piezas de juguete."""
BG, PANEL, EDGE = "#fff9ed", "#ffffff", "#dcd4e9"
TEXT, MUTED, TEAL, ORANGE = "#392d57", "#746985", "#21806b", "#a35b16"
STYLE = f"""
QWidget {{ color: {TEXT}; font-family: 'DejaVu Sans'; font-size: 13px; }}
QMainWindow, QDialog {{ background: {BG}; }}
QLabel {{ background: transparent; border: none; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#eyebrow {{ color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
QLabel#title {{ color: #6042a6; font-size: 28px; font-weight: 700; letter-spacing: -1px; }}
QLabel#hero {{ font-size: 30px; font-weight: 700; }}
QLabel#section {{ font-size: 20px; font-weight: 700; }}
QLabel#metric {{ font-family: 'DejaVu Sans Mono'; font-size: 21px; font-weight: 700; }}
QLabel#gold {{ color: {TEXT}; font-size: 29px; font-weight: 700; }}
QLabel#badge {{ color: #6042a6; background: #eee6ff; border: 2px solid #d7c6f3; border-radius: 14px; padding: 8px 12px; font-size: 11px; font-weight: 700; }}
QLabel#levelBadge {{ background: #7252ba; color: white; border-radius: 18px; padding: 14px; font-size: 20px; font-weight: 700; }}
QLabel#hint {{ color: #6042a6; font-size: 12px; font-weight: 700; }}
QFrame#mission {{ background: #ffffff; border: 2px solid #e0d7ee; border-bottom: 6px solid #e0d7ee; border-radius: 24px; }}
QFrame#hud {{ background: #ffffff; border: 2px solid #e0d7ee; border-bottom: 5px solid #e0d7ee; border-radius: 20px; }}
QFrame#playfield {{ background: #f1ecff; border: 2px solid #c7b7e4; border-bottom: 7px solid #c7b7e4; border-radius: 30px; }}
QFrame#deviceDock {{ background: transparent; border: none; }}
QFrame#controls {{ background: transparent; border: none; }}
QFrame#componentMenu {{ background: #ffffff; border: 3px solid #7252ba; border-bottom: 7px solid #7252ba; border-radius: 18px; }}
QFrame#victory {{ background: #fff9ed; border: 3px solid #7252ba; border-bottom: 9px solid #7252ba; border-radius: 28px; }}
QPushButton {{ color: {TEXT}; background: #ffffff; border: 2px solid #c7b7e4; border-bottom: 5px solid #c7b7e4; border-radius: 15px; padding: 12px 18px; font-weight: 700; }}
QPushButton:hover {{ background: #f2ecff; border-color: #9274c6; }}
QPushButton:pressed {{ background: #e2d5f7; border-bottom-width: 2px; padding-top: 15px; }}
QPushButton:disabled {{ color: #9a90a7; background: #f0ecf4; border-color: #ded6e8; }}
QPushButton#primary {{ background: #ffd35d; color: {TEXT}; border: 2px solid #bd852d; border-bottom: 6px solid #bd852d; padding: 17px 32px; font-size: 16px; border-radius: 18px; }}
QPushButton#primary:hover {{ background: #ffe38b; }}
QPushButton#primary:pressed {{ background: #f4c34c; border-bottom-width: 2px; padding-top: 21px; }}
QPushButton#primary:disabled {{ background: #ece3c8; border-color: #cfc3a7; color: #908773; }}
QPushButton#reset {{ font-size: 24px; padding: 7px; }}
QPushButton#quiet {{ background: #fff9ed; }}
QPushButton#preset {{ padding: 11px 7px; font-size: 12px; }}
QPushButton#preset:checked {{ background: #d6f2dc; border-color: #21806b; color: #216853; }}
QPushButton#closeMenu {{ padding: 2px 8px; border: none; background: transparent; color: {MUTED}; }}
QToolTip {{ color: {TEXT}; background: #ffffff; border: 1px solid #c7b7e4; padding: 6px; }}
QScrollBar:vertical {{ background: {BG}; width: 9px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #c7b7e4; border-radius: 4px; min-height: 28px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
"""
