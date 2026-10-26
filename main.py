"""Punto de entrada del juego. Ejecutar: python main.py."""
import sys


def main() -> int:
    """Configura Qt, inicia la ventana principal y devuelve el código de salida."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    from ui import MainWindow
    from ui.shared.widgets import configureApplication

    app = QApplication(sys.argv)
    configureApplication(app)
    window = MainWindow()
    window.show()
    exit_code = app.exec()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
