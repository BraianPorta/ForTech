"""Punto de entrada del juego. Ejecutar: python main.py."""
import sys


def main() -> int:
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    from interface import MainWindow, configure_application

    app = QApplication(sys.argv)
    configure_application(app)
    window = MainWindow()
    window.show()
    exit_code = app.exec()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
