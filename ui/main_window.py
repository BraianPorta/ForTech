"""Pantalla de juego; las gráficas se reservan a las estadísticas del jugador."""
from pathlib import Path

from PySide6.QtCore import QEvent, QThreadPool, QTimer, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from data import ProgressStore, load_challenges
from ui.header.header import GameHeader
from ui.initial.start_screen import StartScreen
from ui.menu.pause_menu import PauseMenu
from ui.panel.circuit_panel import CircuitPanel
from ui.panel.game_widgets import GameBackdrop, SimulationWorker
from ui.panel.overlays import ComponentMenu, VictoryOverlay
from ui.shared.motion import SceneTransition
from ui.shared.functions import Simulation, initial_configuration
from ui.shared.session import GameSession
from ui.shared.statistics import StatisticsDialog
from ui.shared.style import ORANGE
from ui.side.mission_panel import MissionPanel

BASE = Path(__file__).resolve().parents[1]


class MainWindow(QMainWindow):
    """Juego de misiones: selección cerrada, pruebas y estadísticas del jugador."""
    def __init__(self, progress_path=None):
        super().__init__()
        self.setWindowTitle("Circuit Quest · Restaura la energía")
        self.resize(1440, 900)
        self.setMinimumSize(1000, 700)
        self.all_challenges = load_challenges(BASE / "data")
        self.challenges = []
        self.active_mode = None
        self.revision, self.jobs, self.result = 0, {}, None
        self.busy, self.history, self.progress_error = False, [], ""
        try:
            self.progress = ProgressStore(Path(progress_path) if progress_path is not None else BASE / "output" / "progreso.csv")
            self.history = list(self.progress.records)
        except (OSError, ValueError) as error:
            self.progress, self.progress_error = None, str(error)
        self.build_ui()
        QApplication.instance().installEventFilter(self)
        self.hud_timer = QTimer(self)
        self.hud_timer.setInterval(200)
        self.hud_timer.timeout.connect(self.update_hud)
        self.start_screen.set_available_modes({challenge.mode for challenge in self.all_challenges})
        if any(challenge.mode == 0 for challenge in self.all_challenges):
            self.challenges = [challenge for challenge in self.all_challenges if challenge.mode == 0]
            self.active_mode = 0
            self.set_challenge(0)
            self.session.pause()
        self.hud_timer.start()

    def build_ui(self):
        self.content_root = GameBackdrop()
        self.content_root.setMinimumSize(970, 650)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.content_root)
        self.game_page = scroll
        self.stack = QStackedWidget()
        self.start_screen = StartScreen()
        self.start_screen.character_selected.connect(self.start_character)
        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(scroll)
        self.stack.setCurrentWidget(self.start_screen)
        self.setCentralWidget(self.stack)
        layout = QVBoxLayout(self.content_root)
        layout.setContentsMargins(30, 24, 30, 26)
        layout.setSpacing(22)
        self.header = GameHeader()
        self.header.menu_button.clicked.connect(self.show_pause_menu)
        self.timer_label = self.header.timer_label
        self.changes_label = self.header.changes_label
        self.attempts_label = self.header.attempts_label
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setSpacing(20)
        self.mission_panel = MissionPanel()
        self.mission_tag = self.mission_panel.mission_tag
        self.mission_title = self.mission_panel.mission_title
        self.device_name = self.mission_panel.device_name
        self.target_label = self.mission_panel.target_label
        self.tolerance_label = self.mission_panel.tolerance_label
        self.description = self.mission_panel.description
        body.addWidget(self.mission_panel)

        self.circuit_panel = CircuitPanel()
        self.level_path = self.circuit_panel.level_path
        self.circuit = self.circuit_panel.circuit
        self.device = self.circuit_panel.device
        self.status = self.circuit_panel.status
        self.feedback = self.circuit_panel.footer.feedback
        self.reset_button = self.circuit_panel.footer.reset_button
        self.simulate_button = self.circuit_panel.footer.simulate_button
        self.circuit.selected.connect(self.select_component)
        self.reset_button.clicked.connect(lambda: self.change_level(self.level_index))
        self.simulate_button.clicked.connect(self.run_simulation)
        body.addWidget(self.circuit_panel, 1)
        layout.addLayout(body, 1)

        self.component_menu = ComponentMenu(self.content_root)
        self.component_menu.chosen.connect(self.apply_component)
        self.victory = VictoryOverlay(self.content_root)
        self.victory.next_level.connect(lambda: self.change_level((self.level_index + 1) % len(self.challenges)))
        self.victory.statistics.connect(self.show_statistics)
        scroll.verticalScrollBar().valueChanged.connect(self.component_menu.hide)
        self.transition = SceneTransition(self.content_root)
        self.content_root.resized.connect(self.reposition_overlays)

        self.pause_menu = PauseMenu(self)
        self.pause_menu.resume_requested.connect(self.resume_game)
        self.pause_menu.home_requested.connect(self.return_home)
        self.pause_menu.progress_requested.connect(self.show_statistics)

    def start_character(self, character):
        mode = {"leire": 0, "unai": 1}.get(character)
        if mode is None:
            return
        challenges = [challenge for challenge in self.all_challenges if challenge.mode == mode]
        if not challenges:
            return
        if self.active_mode != mode:
            self.challenges = challenges
            self.active_mode = mode
            self.set_challenge(0)
        self.pause_menu.hide()
        self.game_page.setEnabled(True)
        self.stack.setCurrentWidget(self.game_page)
        self.session.resume()
        self.transition.play()

    def show_pause_menu(self):
        self.session.pause()
        self.component_menu.hide()
        self.game_page.setEnabled(False)
        self.pause_menu.setGeometry(self.rect())
        self.pause_menu.show()
        self.pause_menu.raise_()

    def resume_game(self):
        self.pause_menu.hide()
        if self.stack.currentWidget() is not self.start_screen:
            self.game_page.setEnabled(True)
            self.session.resume()

    def return_home(self):
        self.session.pause()
        self.pause_menu.hide()
        self.stack.setCurrentWidget(self.start_screen)

    def change_level(self, index):
        self.component_menu.dismiss()
        self.transition.play(lambda: self.set_challenge(index))

    def reposition_overlays(self):
        self.transition.setGeometry(self.content_root.rect())
        self.component_menu.hide()
        if self.victory.isVisible():
            self.victory.show_record(self.history[-1])

    def set_challenge(self, index):
        self.level_index, self.challenge = index, self.challenges[index]
        c = self.challenge
        self.session = GameSession(c.difficulty, c.prompt)
        self.revision += 1
        self.result, self.busy = None, False
        initial_values = initial_configuration(c)
        self.current_values = {}
        visual_rows = []
        for row_index, (component_specs, values) in enumerate(zip(c.rows, initial_values), start=1):
            visual_row = []
            for component_index, (component, value) in enumerate(zip(component_specs, values), start=1):
                component_id = f"fila_{row_index}_R{component_index}"
                self.current_values[component_id] = value
                visual_row.append((component_id, f"R{row_index}.{component_index}", value))
            visual_rows.append(visual_row)
        self.circuit.configure(visual_rows)
        self.component_menu.hide()
        self.victory.hide()
        self.circuit.setEnabled(True)
        self.mission_tag.setText(f"NIVEL {index + 1:02d}")
        self.level_path.setText("  ·  ".join("●" if i <= index else "○" for i in range(len(self.challenges))))
        self.mission_title.setText("Circuito eléctrico")
        self.description.setText("Selecciona cada resistencia para elegir un valor.")
        self.target_label.setText(f"{c.result:g} Ω")
        self.tolerance_label.setText("Resistencia equivalente objetivo")
        self.device_name.setText(c.prompt)
        self.device.value, self.device.unit, self.device.passed = None, "Ω", False
        self.device.update()
        self.status.setText("Zzz…")
        self.status.setStyleSheet("")
        self.feedback.clear()
        if self.progress_error:
            self.feedback.setText("El progreso no se puede guardar: " + self.progress_error)
        self.simulate_button.setEnabled(True)
        self.simulate_button.setText("ϟ  ACTIVAR")
        self.update_hud()

    def update_hud(self):
        if not hasattr(self, "session"):
            return
        seconds = int(self.session.elapsed)
        self.timer_label.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")
        self.changes_label.setText(f"{self.session.total_changes:02d}")
        self.attempts_label.setText(f"{self.session.attempts:02d}")

    def select_component(self, component_id):
        if self.session.finished is not None or self.busy:
            return
        item = self.circuit.component_items[component_id]
        rect = self.circuit.mapFromScene(item.sceneBoundingRect()).boundingRect()
        rect.moveTopLeft(self.circuit.viewport().mapTo(self.content_root, rect.topLeft()))
        self.component_menu.open_above(component_id, self.current_values[component_id], rect)

    @Slot(str, float)
    def apply_component(self, component_id, value):
        if self.busy or self.session.finished is not None:
            return
        old = self.current_values[component_id]
        if not self.session.change("R", old, value):
            return
        self.current_values[component_id] = value
        self.circuit.component_items[component_id].replace(value)
        self.revision += 1
        self.result = None
        self.device.value, self.device.passed = None, False
        self.device.update()
        self.status.setText("Zzz…")
        self.status.setStyleSheet("")
        self.feedback.clear()
        self.update_hud()

    @Slot()
    def run_simulation(self):
        if self.busy or self.session.finished is not None:
            return
        self.busy = True
        self.component_menu.hide()
        self.circuit.setEnabled(False)
        self.session.attempts += 1
        self.update_hud()
        self.revision += 1
        revision = self.revision
        self.simulate_button.setEnabled(False)
        self.simulate_button.setText("ACTIVANDO…")
        self.status.setText("…")
        worker = SimulationWorker(revision, self.challenge, self.circuit.current_rows())
        worker.signals.finished.connect(self.accept_result)
        self.jobs[revision] = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(int, object, str)
    def accept_result(self, revision, result: Simulation | None, error):
        self.jobs.pop(revision, None)
        if revision != self.revision:
            return
        self.busy = False
        self.circuit.setEnabled(True)
        self.simulate_button.setEnabled(True)
        self.simulate_button.setText("ϟ  ACTIVAR")
        if error:
            self.status.setText("Error de activación")
            self.feedback.setText(error)
            return
        self.result = result
        self.device.value, self.device.unit = result.measured_value, result.unit
        self.device.passed = result.passed
        self.device.update()
        if not result.passed:
            self.status.setText("¡Casi!")
            self.status.setStyleSheet(f"color: {ORANGE}; background: #fff0db; border-color: #e7c393;")
            direction = "Reduce" if result.measured_value > self.challenge.result else "Aumenta"
            self.feedback.setText(
                f"{result.measured_value:.3f} Ω · {direction} la resistencia equivalente."
            )
            return
        record = self.session.complete()
        self.update_hud()
        self.history.append(record)
        try:
            if self.progress is not None:
                self.progress.append(record)
        except (OSError, ValueError) as save_error:
            self.progress_error = str(save_error)
        self.status.setText("¡En marcha!")
        self.status.setStyleSheet("")
        self.circuit.setEnabled(False)
        self.simulate_button.setEnabled(False)
        self.feedback.setText("" if not self.progress_error else "No se pudo guardar: " + self.progress_error)
        self.victory.show_record(record)

    def show_statistics(self):
        self.component_menu.hide()
        dialog = StatisticsDialog(self.history, self)
        dialog.exec()
        dialog.deleteLater()

    def eventFilter(self, obj, event):
        menu = getattr(self, "component_menu", None)
        if menu is not None and menu.isVisible():
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                menu.dismiss()
                return True
            if event.type() == QEvent.Type.MouseButtonPress and isinstance(obj, QWidget):
                if obj is not menu and not menu.isAncestorOf(obj):
                    menu.dismiss()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "pause_menu") and self.pause_menu.isVisible():
            self.pause_menu.setGeometry(self.rect())
        if hasattr(self, "component_menu"):
            self.component_menu.hide()
        if hasattr(self, "victory") and self.victory.isVisible():
            self.victory.show_record(self.history[-1])

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        self.hud_timer.stop()
        self.circuit.animation_timer.stop()
        QThreadPool.globalInstance().waitForDone()
        event.accept()
