"""Punto de entrada del juego. Ejecutar: python main.py.

Modo de vista previa sin escritorio: python main.py --preview output/preview.png
"""
import argparse
import os
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Circuit Quest · restaura la energía")
    parser.add_argument("--preview", type=Path, help="Guarda una captura con Qt en modo offscreen y termina")
    args = parser.parse_args()
    if args.preview:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "output" / ".mplconfig"))
    from PySide6.QtCore import QCoreApplication, QEvent, QTimer
    from PySide6.QtWidgets import QApplication
    from interface import MainWindow, configure_application

    app = QApplication(sys.argv[:1])
    configure_application(app)
    window = MainWindow()
    window.show()
    if args.preview:
        def capture():
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.preview)):
                print("No se pudo guardar la captura", file=sys.stderr)
                app.exit(1)
                return
            print(args.preview.resolve())
            app.quit()
        QTimer.singleShot(600, capture)
        QTimer.singleShot(30000, lambda: app.exit(2))
    exit_code = app.exec()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
