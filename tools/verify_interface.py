"""Prueba de una partida completa en Qt offscreen, con historial aislado."""
import os
from pathlib import Path
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "output" / ".mplconfig"))
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QDoubleSpinBox, QComboBox, QPushButton
import pandas as pd
from interface import MainWindow, StatisticsDialog, configure_application
from game_session import ProgressStore


def wait_until(app, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("La interfaz no completó la operación dentro del plazo")


def click_piece(window, kind):
    piece = window.circuit.resistor if kind == "R" else window.circuit.capacitor
    point = window.circuit.mapFromScene(piece.scenePos())
    QTest.mouseClick(window.circuit.viewport(), Qt.MouseButton.LeftButton, pos=point)
    menu = window.component_menu
    assert menu.isVisible() and menu.kind == kind
    assert menu.motion.group.duration() >= 200
    wait_until(QApplication.instance(), lambda: menu.motion.effect.opacity() == 1)
    rect = window.circuit.mapFromScene(piece.sceneBoundingRect()).boundingRect()
    top = window.circuit.viewport().mapTo(window.content_root, rect.topLeft()).y()
    assert menu.geometry().bottom() < top
    return menu


def main():
    destination = ROOT / "output"
    destination.mkdir(exist_ok=True)
    app = QApplication([])
    configure_application(app)
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        history_path = Path(temporary) / "progreso.csv"
        window = MainWindow(progress_path=history_path)
        window.show()
        app.processEvents()
        wait_until(app, lambda: not window.transition.isVisible())
        assert window.result is None and window.session.attempts == 0
        assert not window.findChildren(QLineEdit)
        assert not window.findChildren(QDoubleSpinBox)
        assert not window.findChildren(QComboBox)
        assert not hasattr(window, "plot") and not hasattr(window, "load_button")
        assert window.grab().save(str(destination / "preview.png"))

        empty = StatisticsDialog([], window)
        assert empty.canvas is None
        empty.deleteLater()

        # Una prueba de la configuración inicial falla, sin terminar la misión.
        window.simulate_button.click()
        wait_until(app, lambda: not window.busy)
        assert window.result is not None and not window.result.passed
        assert window.session.attempts == 1 and not window.history

        menu = click_piece(window, "C")
        assert not menu.findChildren(QLineEdit)
        QTest.mouseClick(menu.buttons[menu.values.index(470)], Qt.MouseButton.LeftButton)
        wait_until(app, lambda: not menu.isVisible())
        assert window.session.total_changes == 0
        menu = click_piece(window, "C")
        app.processEvents()
        assert window.grab().save(str(destination / "opciones_componente.png"))
        QTest.mouseClick(menu.buttons[menu.values.index(560)], Qt.MouseButton.LeftButton)
        wait_until(app, lambda: window.circuit.capacitor.value == 560 and window.circuit.capacitor.opacity() == 1)
        wait_until(app, lambda: not menu.isVisible())
        assert window.result is None and window.session.attempts == 1
        assert window.session.total_changes == 1 and not menu.isVisible()
        window.simulate_button.click()
        wait_until(app, lambda: window.session.finished is not None)
        assert window.victory.isVisible() and window.result.passed
        wait_until(app, lambda: window.victory.motion.effect.opacity() == 1)
        assert window.session.attempts == 2
        assert window.grab().save(str(destination / "reto_resuelto.png"))
        frozen = window.session.elapsed
        app.processEvents()
        assert window.session.elapsed == frozen
        saved = pd.read_csv(history_path)
        assert len(saved) == 1 and saved["cambios_c"].iloc[0] == 1
        assert saved["pruebas"].iloc[0] == 2
        window.run_simulation()
        assert len(window.history) == 1

        stats = StatisticsDialog(window.history, window)
        stats.show()
        app.processEvents()
        wait_until(app, lambda: stats.motion.effect.opacity() == 1)
        assert stats.canvas is not None
        stats.canvas.draw()
        assert stats.grab().save(str(destination / "estadisticas.png"))
        stats.close()
        stats.deleteLater()
        next_button = next(b for b in window.victory.box.findChildren(QPushButton) if b.text().startswith("SIGUIENTE"))
        QTest.mouseClick(next_button, Qt.MouseButton.LeftButton)
        assert window.transition.isVisible()
        wait_until(app, lambda: not window.transition.isVisible())
        assert window.level_index == 1 and not window.victory.isVisible()
        assert window.session.total_changes == 0 and window.session.attempts == 0
        assert len(ProgressStore(history_path).records) == 1

        menu = click_piece(window, "R")
        QTest.keyClick(window.circuit, Qt.Key.Key_Escape)
        wait_until(app, lambda: not menu.isVisible())
        assert not menu.isVisible()
        menu = click_piece(window, "R")
        QTest.mouseClick(window.mission_title, Qt.MouseButton.LeftButton)
        wait_until(app, lambda: not menu.isVisible())
        assert not menu.isVisible()
        # Reabrir otra pieza durante el fundido de cierre interrumpe la transición anterior.
        menu = click_piece(window, "R")
        menu.dismiss()
        menu = click_piece(window, "C")
        assert menu.isVisible() and menu.isEnabled() and menu.kind == "C"
        QTest.keyClick(window.circuit, Qt.Key.Key_Escape)
        wait_until(app, lambda: not menu.isVisible())
        try:
            window.apply_component("R", 1234)
        except ValueError:
            pass
        else:
            raise AssertionError("Se aceptó un valor fuera del catálogo")
        assert window.session.total_changes == 0

        # Reiniciar invalida una respuesta que todavía está en segundo plano.
        window.run_simulation()
        window.set_challenge(0)
        wait_until(app, lambda: not window.jobs)
        assert window.result is None and window.session.attempts == 0
        window.resize(1160, 800)
        app.processEvents()
        assert window.grab().save(str(destination / "preview_compacta.png"))
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    print("OK: catálogo cerrado, animaciones interrumpibles, prueba fallida, victoria, contadores, CSV y estadísticas separadas")


if __name__ == "__main__":
    main()
