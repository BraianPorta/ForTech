"""Pantalla de juego; las gráficas se reservan a las estadísticas del jugador."""
from pathlib import Path

from PySide6.QtCore import QEvent, QThreadPool, QTimer, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from data import ProgressStore, load_challenges, prepare_exercises
from ui.header.header import GameHeader
from ui.initial.start_screen import StartScreen
from ui.menu.pause_menu import PauseMenu
from ui.panel.circuit_panel import CircuitPanel
from ui.panel.game_widgets import GameBackdrop, SimulationWorker
from ui.panel.overlays import ComponentMenu, VictoryOverlay
from ui.shared.motion import SceneTransition
from ui.shared.flow import FLOW_EXERCISES, simulate_flow
from ui.shared.functions import Simulation, initial_configuration
from ui.shared.session import GameSession
from ui.shared.statistics import SessionStatistics
from ui.shared.style import ORANGE
from ui.side.mission_panel import MissionPanel

BASE = Path(__file__).resolve().parents[1]


class MainWindow(QMainWindow):
    """Juego de misiones: selección cerrada, pruebas y estadísticas del jugador."""
    def __init__(self, progress_path=None):
        super().__init__()
        self.setWindowTitle("ForTech · Restaura la energía")
        self.resize(1440, 900)
        self.setMinimumSize(1000, 700)
        data_dir = BASE / "data"
        exercises_file = prepare_exercises(
            data_dir / "import", data_dir / "exercises" / "exercises.csv"
        )
        self.all_challenges = load_challenges(exercises_file)
        self.challenges = []
        self.active_mode = None
        self.revision, self.jobs, self.result = 0, {}, None
        self.busy, self.history, self.progress_error = False, [], ""
        self.session_records = []
        self.completed_challenges = set()
        self.session_complete = False
        self.session_statistics_error = ""
        self.statistics = SessionStatistics(
            data_dir / "results" / "session",
            data_dir / "results" / "comparison",
        )
        try:
            self.session_number = self.statistics.begin_session()
        except (OSError, ValueError) as error:
            self.session_number = None
            self.session_statistics_error = str(error)
        try:
            self.progress = ProgressStore(
                Path(progress_path)
                if progress_path is not None
                else data_dir / "results" / "progreso.csv"
            )
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
            self.challenges = sorted(
                (challenge for challenge in self.all_challenges if challenge.mode == 0),
                key=lambda challenge: (challenge.difficulty, int(challenge.identifier)),
            )
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
        self.start_screen.statistics_requested.connect(self.show_statistics)
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
        self.flow_panel = self.circuit_panel.flow_exercise
        self.flow_panel.parameter_changed.connect(self.apply_flow_parameter)
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
        self.victory.next_level.connect(self.advance_after_victory)
        scroll.verticalScrollBar().valueChanged.connect(self.component_menu.hide)
        self.transition = SceneTransition(self.content_root)
        self.content_root.resized.connect(self.reposition_overlays)

        self.pause_menu = PauseMenu(self)
        self.pause_menu.resume_requested.connect(self.resume_game)
        self.pause_menu.home_requested.connect(self.return_home)

    def start_character(self, character):
        mode = {"leire": 0, "unai": 1}.get(character)
        if mode is None:
            return
        challenges = sorted(
            (challenge for challenge in self.all_challenges if challenge.mode == mode),
            key=lambda challenge: (challenge.difficulty, int(challenge.identifier)),
        )
        if not challenges:
            return
        if self.active_mode != mode or self.session_complete:
            self.challenges = challenges
            self.active_mode = mode
            if self.session_complete:
                self._begin_statistics_session()
            self.session_records.clear()
            self.completed_challenges.clear()
            self.session_complete = False
            self.set_challenge(0)
        self.pause_menu.hide()
        self.game_page.setEnabled(True)
        self.stack.setCurrentWidget(self.game_page)
        self.session.resume()
        self.transition.play()

    def _begin_statistics_session(self):
        """Reserva un número nuevo al empezar una sesión tras completar la anterior."""
        self.session_statistics_error = ""
        try:
            self.session_number = self.statistics.begin_session()
        except (OSError, ValueError) as error:
            self.session_number = None
            self.session_statistics_error = str(error)

    def advance_after_victory(self):
        if self.session_complete:
            self.return_home()
        else:
            self.change_level((self.level_index + 1) % len(self.challenges))

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
            self.victory.show_record(
                self.history[-1],
                self.session_complete,
                self.session_statistics_error,
            )

    def set_challenge(self, index):
        self.level_index, self.challenge = index, self.challenges[index]
        c = self.challenge
        self.session = GameSession(c.difficulty, c.prompt)
        self.revision += 1
        self.result, self.busy = None, False
        self.current_values = {}
        self.component_kinds = {}
        is_flow_exercise = bool(c.exercise_type)
        self.circuit_panel.show_flow_exercise(is_flow_exercise)
        if is_flow_exercise:
            self.flow_panel.set_exercise(c.exercise_type, c.prompt)
        else:
            initial_values = initial_configuration(c)
            visual_rows = []
            for row_index, (component_specs, values) in enumerate(
                zip(c.rows, initial_values), start=1
            ):
                visual_row = []
                for component_index, (component, value) in enumerate(
                    zip(component_specs, values), start=1
                ):
                    is_bulb = component.kind == "bombilla"
                    component_id = (
                        f"fila_{row_index}_{'B' if is_bulb else 'R'}{component_index}"
                    )
                    unit = "W" if is_bulb else "Ω"
                    component_name = "B" if is_bulb else "R"
                    self.current_values[component_id] = value
                    self.component_kinds[component_id] = component_name
                    visual_row.append(
                        (component_id, f"{component_name}{row_index}.{component_index}", value, unit)
                    )
                visual_rows.append(visual_row)
            self.circuit.configure(visual_rows)
        self.component_menu.hide()
        self.victory.hide()
        self.circuit.setEnabled(not is_flow_exercise)
        self.flow_panel.set_parameters_enabled(is_flow_exercise)
        self.mission_tag.setText(f"NIVEL {index + 1:02d}")
        self.level_path.setText("  ·  ".join("●" if i <= index else "○" for i in range(len(self.challenges))))
        if is_flow_exercise:
            exercise = FLOW_EXERCISES[c.exercise_type]
            self.mission_title.setText(exercise.title)
            self.description.setText("Modifica los bloques y activa el cálculo.")
            self.circuit_panel.stage_title.setText("MECÁNICA DE FLUIDOS")
            self.target_label.setText(exercise.objective)
            self.tolerance_label.setText("Criterio para completar")
            self.device_name.setText("Agua · Ingeniería")
        else:
            has_bulbs = any(
                component.kind == "bombilla" for branch in c.rows for component in branch
            )
            self.mission_title.setText(
                "Circuito con bombillas" if has_bulbs else "Circuito eléctrico"
            )
            self.description.setText(
                "Selecciona cada bombilla para elegir una potencia."
                if has_bulbs else
                "Selecciona cada resistencia para elegir un valor."
            )
            self.circuit_panel.stage_title.setText(
                "CIRCUITO DE BOMBILLAS" if has_bulbs else "RED DE RESISTENCIAS"
            )
            self.target_label.setText(f"{c.result:g} Ω")
            self.tolerance_label.setText("Resistencia equivalente objetivo")
            self.device_name.setText(c.prompt)
        self.device.value, self.device.unit, self.device.passed = None, "Ω", False
        self.device.update()
        self.status.setText("Zzz…")
        self.status.setStyleSheet("")
        self.flow_panel.status.clear()
        self.flow_panel.status.setStyleSheet("")
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
        self.component_menu.open_above(
            component_id, self.current_values[component_id], rect,
            self.component_kinds[component_id],
        )

    @Slot(str, float)
    def apply_component(self, component_id, value):
        if self.busy or self.session.finished is not None:
            return
        old = self.current_values[component_id]
        if not self.session.change(self.component_kinds[component_id], old, value):
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

    @Slot(str, float, float)
    def apply_flow_parameter(self, _key, old, new):
        if self.busy or self.session.finished is not None:
            return
        if not self.session.change("P", old, new):
            return
        self.revision += 1
        self.result = None
        self.flow_panel.status.clear()
        self.flow_panel.status.setStyleSheet("")
        self.feedback.clear()
        self.update_hud()

    @Slot()
    def run_simulation(self):
        if self.busy or self.session.finished is not None:
            return
        self.busy = True
        self.component_menu.hide()
        is_flow_exercise = bool(self.challenge.exercise_type)
        self.circuit.setEnabled(not is_flow_exercise)
        self.flow_panel.set_parameters_enabled(False)
        self.session.attempts += 1
        self.update_hud()
        self.revision += 1
        revision = self.revision
        self.simulate_button.setEnabled(False)
        self.simulate_button.setText("ACTIVANDO…")
        self.status.setText("…")
        if is_flow_exercise:
            try:
                result = simulate_flow(self.challenge.exercise_type, self.flow_panel.values)
            except (ArithmeticError, ValueError) as error:
                self.accept_result(revision, None, str(error))
                return
            self.accept_result(revision, result, "")
            return
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
        is_flow_exercise = bool(self.challenge.exercise_type)
        self.circuit.setEnabled(not is_flow_exercise)
        self.flow_panel.set_parameters_enabled(is_flow_exercise)
        self.simulate_button.setEnabled(True)
        self.simulate_button.setText("ϟ  ACTIVAR")
        if error:
            status = self.flow_panel.status if is_flow_exercise else self.status
            status.setText("Error de cálculo")
            self.feedback.setText(error)
            return
        self.result = result
        if not is_flow_exercise:
            self.device.value, self.device.unit = result.measured_value, result.unit
            self.device.passed = result.passed
            self.device.update()
        if not result.passed:
            status = self.flow_panel.status if is_flow_exercise else self.status
            status.setText("Revisa el resultado" if is_flow_exercise else "¡Casi!")
            status.setStyleSheet(
                f"color: {ORANGE}; background: #fff0db; border-color: #e7c393;"
                if not is_flow_exercise else f"color: {ORANGE};"
            )
            if is_flow_exercise:
                objective = FLOW_EXERCISES[self.challenge.exercise_type].objective
                self.feedback.setText(
                    f"{result.measured_value:.3f} {result.unit} · Objetivo: {objective}. "
                    "Ajusta los bloques."
                )
            else:
                direction = (
                    "Reduce" if result.measured_value > self.challenge.result else "Aumenta"
                )
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
        if self.level_index not in self.completed_challenges:
            self.completed_challenges.add(self.level_index)
            self.session_records.append(record)
        if len(self.completed_challenges) == len(self.challenges):
            self.session_complete = True
            if self.session_number is None:
                if not self.session_statistics_error:
                    self.session_statistics_error = "No se pudo reservar el número de sesión."
            else:
                try:
                    self.statistics.save_session(self.session_number, self.session_records)
                    self.session_statistics_error = ""
                except (OSError, ValueError) as save_error:
                    self.session_statistics_error = str(save_error)
        status = self.flow_panel.status if is_flow_exercise else self.status
        status.setText("¡En marcha!")
        status.setStyleSheet("")
        self.circuit.setEnabled(False)
        self.flow_panel.set_parameters_enabled(False)
        self.simulate_button.setEnabled(False)
        self.feedback.setText("" if not self.progress_error else "No se pudo guardar: " + self.progress_error)
        self.victory.show_record(
            record,
            self.session_complete,
            self.session_statistics_error,
        )

    def show_statistics(self):
        self.component_menu.hide()
        if self.session_statistics_error:
            QMessageBox.warning(
                self,
                "Estadísticas no disponibles",
                "No se pudieron preparar las estadísticas de esta sesión: "
                + self.session_statistics_error,
            )
        try:
            comparison, _, _, _ = self.statistics.build_comparison()
        except FileNotFoundError:
            QMessageBox.information(
                self,
                "Aún no hay estadísticas",
                "Todavía no hay estadísticas guardadas. Completa todas las actividades "
                "de una sesión para que aparezcan aquí.",
            )
            return
        except (OSError, ValueError) as error:
            QMessageBox.warning(
                self,
                "No se pudieron leer las estadísticas",
                str(error),
            )
            return
        current = comparison[comparison["sesion"] == self.session_number]
        if not self.session_complete:
            QMessageBox.information(
                self,
                "Sesión incompleta",
                "La sesión actual aún no está completa. Se muestran las estadísticas "
                "de las sesiones anteriores.",
            )
        elif not current.empty:
            QMessageBox.information(
                self,
                "Estilo de la sesión",
                f"Tu estilo en esta sesión: {current.iloc[0]['estilo']}.",
            )

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
            self.victory.show_record(
                self.history[-1],
                self.session_complete,
                self.session_statistics_error,
            )

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        self.hud_timer.stop()
        self.circuit.animation_timer.stop()
        QThreadPool.globalInstance().waitForDone()
        event.accept()
