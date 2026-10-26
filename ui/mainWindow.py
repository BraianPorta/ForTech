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

from data import ProgressStore, loadChallenges, prepareExercises
from ui.header.header import GameHeader
from ui.initial.startScreen import StartScreen
from ui.pauseMenu.pauseMenu import PauseMenu
from ui.panel.circuitPanel import CircuitPanel
from ui.panel.gameWidgets import GameBackdrop, SimulationWorker
from ui.panel.overlays import ComponentMenu, VictoryOverlay
from ui.shared.motion import SceneTransition
from ui.shared.functions.electronic import Simulation
from ui.shared.functions.flow import FLOW_EXERCISES, simulateFlow
from ui.shared.session import GameSession
from ui.shared.statistics import SessionStatistics
from ui.shared.style import ORANGE
from ui.side.side import MissionPanel

# Raíz del proyecto usada para localizar datos y recursos locales.
BASE = Path(__file__).resolve().parents[1]


class MainWindow(QMainWindow):
    """Juego de misiones: selección cerrada, pruebas y estadísticas del jugador."""

    def __init__(self, progress_path=None):
        """Carga los retos, crea servicios y prepara la ventana del juego."""
        super().__init__()
        self.setWindowTitle("ForTech · Restaura la energía")
        self.resize(1440, 900)
        self.setMinimumSize(1000, 700)
        data_dir = BASE / "data"
        exercises_file = prepareExercises(
            data_dir / "import", data_dir / "exercises" / "exercises.csv"
        )
        self.all_challenges = loadChallenges(exercises_file)
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
        self.buildUi()
        QApplication.instance().installEventFilter(self)
        self.hud_timer = QTimer(self)
        self.hud_timer.setInterval(200)
        self.hud_timer.timeout.connect(self.updateHud)
        self.startScreen.setAvailableModes({challenge.mode for challenge in self.all_challenges})
        if any(challenge.mode == 0 for challenge in self.all_challenges):
            self.challenges = sorted(
                (challenge for challenge in self.all_challenges if challenge.mode == 0),
                key=lambda challenge: (challenge.difficulty, int(challenge.identifier)),
            )
            self.active_mode = 0
            self.setChallenge(0)
            self.session.pause()
        self.hud_timer.start()

    def buildUi(self):
        """Construye la pantalla de juego y conecta las acciones principales."""
        self.content_root = GameBackdrop()
        self.content_root.setMinimumSize(970, 650)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.content_root)
        self.game_page = scroll
        self.stack = QStackedWidget()
        self.startScreen = StartScreen()
        self.startScreen.character_selected.connect(self.startCharacter)
        self.startScreen.statistics_requested.connect(self.showStatistics)
        self.stack.addWidget(self.startScreen)
        self.stack.addWidget(scroll)
        self.stack.setCurrentWidget(self.startScreen)
        self.setCentralWidget(self.stack)
        layout = QVBoxLayout(self.content_root)
        layout.setContentsMargins(30, 24, 30, 26)
        layout.setSpacing(22)
        self.header = GameHeader()
        self.header.menu_button.clicked.connect(self.showPauseMenu)
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
        body.addWidget(self.mission_panel)

        self.circuitPanel = CircuitPanel()
        self.level_path = self.circuitPanel.level_path
        self.flow_panel = self.circuitPanel.flowExercise
        self.flow_panel.parameter_changed.connect(self.applyFlowParameter)
        self.circuit = self.circuitPanel.circuit
        self.device = self.circuitPanel.device
        self.status = self.circuitPanel.status
        self.feedback = self.circuitPanel.footer.feedback
        self.reset_button = self.circuitPanel.footer.reset_button
        self.simulate_button = self.circuitPanel.footer.simulate_button
        self.circuit.selected.connect(self.selectComponent)
        self.reset_button.clicked.connect(lambda: self.changeLevel(self.level_index))
        self.simulate_button.clicked.connect(self.runSimulation)
        body.addWidget(self.circuitPanel, 1)
        layout.addLayout(body, 1)

        self.component_menu = ComponentMenu(self.content_root)
        self.component_menu.chosen.connect(self.applyComponent)
        self.victory = VictoryOverlay(self.content_root)
        self.victory.next_level.connect(self.advanceAfterVictory)
        scroll.verticalScrollBar().valueChanged.connect(self.component_menu.hide)
        self.transition = SceneTransition(self.content_root)
        self.content_root.resized.connect(self.repositionOverlays)

        self.pauseMenu = PauseMenu(self)
        self.pauseMenu.resume_requested.connect(self.resumeGame)
        self.pauseMenu.home_requested.connect(self.returnHome)

    def startCharacter(self, character):
        """Inicia la aventura del personaje elegido y su primera misión."""
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
                self.beginStatisticsSession()
            self.session_records.clear()
            self.completed_challenges.clear()
            self.session_complete = False
            self.setChallenge(0)
        self.pauseMenu.hide()
        self.game_page.setEnabled(True)
        self.stack.setCurrentWidget(self.game_page)
        self.session.resume()
        self.transition.play()

    def beginStatisticsSession(self):
        """Reserva un número nuevo al empezar una sesión tras completar la anterior."""
        self.session_statistics_error = ""
        try:
            self.session_number = self.statistics.begin_session()
        except (OSError, ValueError) as error:
            self.session_number = None
            self.session_statistics_error = str(error)

    def advanceAfterVictory(self):
        """Avanza a la siguiente misión o vuelve al inicio al terminar."""
        if self.session_complete:
            self.returnHome()
        else:
            self.changeLevel((self.level_index + 1) % len(self.challenges))

    def showPauseMenu(self):
        """Pausa la partida y abre el menú modal."""
        self.session.pause()
        self.component_menu.hide()
        self.game_page.setEnabled(False)
        self.pauseMenu.setGeometry(self.rect())
        self.pauseMenu.show()
        self.pauseMenu.raise_()

    def resumeGame(self):
        """Cierra el menú de pausa y reanuda la sesión activa."""
        self.pauseMenu.hide()
        if self.stack.currentWidget() is not self.startScreen:
            self.game_page.setEnabled(True)
            self.session.resume()

    def returnHome(self):
        """Pausa la sesión y muestra la pantalla de selección."""
        self.session.pause()
        self.pauseMenu.hide()
        self.stack.setCurrentWidget(self.startScreen)

    def changeLevel(self, index):
        """Cambia de misión con la transición visual de escena."""
        self.component_menu.dismiss()
        self.transition.play(lambda: self.setChallenge(index))

    def repositionOverlays(self):
        """Recoloca las superposiciones tras cambiar el tamaño del contenido."""
        self.transition.setGeometry(self.content_root.rect())
        self.component_menu.hide()
        if self.victory.isVisible():
            self.victory.showRecord(
                self.history[-1],
                self.session_complete,
                self.session_statistics_error,
            )

    def setChallenge(self, index):
        """Configura paneles, objetivo y componentes para una misión."""
        self.level_index, self.challenge = index, self.challenges[index]
        c = self.challenge
        self.session = GameSession(c.difficulty, c.prompt)
        self.revision += 1
        self.result, self.busy = None, False
        self.current_values = {}
        self.component_kinds = {}
        isFlowExercise = bool(c.exercise_type)
        self.circuitPanel.showFlowExercise(isFlowExercise)
        self.flow_panel.prompt.setVisible(not isFlowExercise)
        if isFlowExercise:
            self.flow_panel.setExercise(c.exercise_type, c.prompt)
        else:
            visual_rows = []
            for row_index, component_specs in enumerate(c.rows, start=1):
                visual_row = []
                for component_index, component in enumerate(component_specs, start=1):
                    is_bulb = component.kind in {"bombilla", "bombilla_ohm"}
                    component_id = (
                        f"fila_{row_index}_{'B' if is_bulb else 'R'}{component_index}"
                    )
                    unit = "W" if component.kind == "bombilla" else "Ω"
                    component_name = "B" if is_bulb else "R"
                    self.current_values[component_id] = None
                    self.component_kinds[component_id] = (
                        "BΩ" if component.kind == "bombilla_ohm" else component_name
                    )
                    visual_row.append(
                        (component_id, f"{component_name}{row_index}.{component_index}", None, unit)
                    )
                visual_rows.append(visual_row)
            self.circuit.configure(visual_rows, c.voltage)
        self.component_menu.hide()
        self.victory.hide()
        self.circuit.setEnabled(not isFlowExercise)
        self.flow_panel.setParametersEnabled(isFlowExercise)
        self.mission_tag.setText(f"NIVEL {index + 1:02d}")
        self.level_path.setText("  ·  ".join("●" if i <= index else "○" for i in range(len(self.challenges))))
        if isFlowExercise:
            exercise = FLOW_EXERCISES[c.exercise_type]
            self.mission_title.setText(exercise.title)
            self.circuitPanel.stage_title.setText("MECÁNICA DE FLUIDOS")
            self.target_label.setText(exercise.objective)
            self.tolerance_label.setText("Criterio para completar")
            self.device_name.setText(c.prompt)
        else:
            has_bulbs = any(
                component.kind in {"bombilla", "bombilla_ohm"}
                for branch in c.rows
                for component in branch
            )
            self.mission_title.setText(
                "Circuito con bombillas" if has_bulbs else "Circuito eléctrico"
            )
            self.circuitPanel.stage_title.setText(
                "CIRCUITO DE BOMBILLAS" if has_bulbs else "RED DE RESISTENCIAS"
            )
            if c.result_min is not None and c.result_max is not None:
                self.target_label.setText(
                    f"{c.result_min:g}–{c.result_max:g} {c.result_unit}"
                )
            else:
                self.target_label.setText(f"{c.result:g} {c.result_unit}")
            self.tolerance_label.setText(
                "Potencia objetivo" if c.result_unit == "W"
                else "Resistencia equivalente objetivo"
            )
            self.device_name.setText(c.prompt)
        self.device.value, self.device.unit, self.device.passed = (
            None, c.result_unit, False
        )
        self.device.update()
        self.status.setText("Zzz…")
        self.status.setStyleSheet("")
        self.flow_panel.status.clear()
        self.flow_panel.status.setStyleSheet("")
        self.feedback.clear()
        if self.progress_error:
            self.feedback.setText("El progreso no se puede guardar: " + self.progress_error)
        self.simulate_button.setEnabled(
            all(value is not None for value in self.flow_panel.values.values())
            if isFlowExercise else
            all(value is not None for value in self.current_values.values())
        )
        self.simulate_button.setText("ϟ  ACTIVAR")
        self.updateHud()

    def updateHud(self):
        """Actualiza el cronómetro y las métricas de la partida."""
        if not hasattr(self, "session"):
            return
        seconds = int(self.session.elapsed)
        self.timer_label.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")
        self.changes_label.setText(f"{self.session.totalChanges:02d}")
        self.attempts_label.setText(f"{self.session.attempts:02d}")

    def selectComponent(self, component_id):
        """Abre el catálogo de valores sobre el componente seleccionado."""
        if self.session.finished is not None or self.busy:
            return
        item = self.circuit.component_items[component_id]
        rect = self.circuit.mapFromScene(item.sceneBoundingRect()).boundingRect()
        rect.moveTopLeft(self.circuit.viewport().mapTo(self.content_root, rect.topLeft()))
        self.component_menu.openAbove(
            component_id, self.current_values[component_id], rect,
            self.component_kinds[component_id],
        )

    @Slot(str, float)
    def applyComponent(self, component_id, value):
        """Registra y aplica un valor nuevo elegido para una pieza."""
        if self.busy or self.session.finished is not None:
            return
        old = self.current_values[component_id]
        if not self.session.change(self.component_kinds[component_id], old, value):
            return
        self.current_values[component_id] = value
        self.circuit.component_items[component_id].replace(value)
        self.simulate_button.setEnabled(
            all(selected is not None for selected in self.current_values.values())
        )
        self.revision += 1
        self.result = None
        self.device.value, self.device.passed = None, False
        self.device.update()
        self.status.setText("Zzz…")
        self.status.setStyleSheet("")
        self.feedback.clear()
        self.updateHud()

    @Slot(str, object, float)
    def applyFlowParameter(self, _key, old, new):
        """Registra un cambio de parámetro y actualiza el estado del reto."""
        if self.busy or self.session.finished is not None:
            return
        if not self.session.change("P", old, new):
            return
        self.simulate_button.setEnabled(
            all(value is not None for value in self.flow_panel.values.values())
        )
        self.revision += 1
        self.result = None
        self.flow_panel.status.clear()
        self.flow_panel.status.setStyleSheet("")
        self.feedback.clear()
        self.updateHud()

    @Slot()
    def runSimulation(self):
        """Valida las selecciones y ejecuta el cálculo del reto activo."""
        if self.busy or self.session.finished is not None:
            return
        isFlowExercise = bool(self.challenge.exercise_type)
        if isFlowExercise and any(
            value is None for value in self.flow_panel.values.values()
        ):
            self.feedback.setText("Selecciona una opción en cada lista antes de activar el cálculo.")
            return
        self.busy = True
        self.component_menu.hide()
        self.circuit.setEnabled(not isFlowExercise)
        self.flow_panel.setParametersEnabled(False)
        self.session.attempts += 1
        self.updateHud()
        self.revision += 1
        revision = self.revision
        self.simulate_button.setEnabled(False)
        self.simulate_button.setText("ACTIVANDO…")
        self.status.setText("…")
        if isFlowExercise:
            try:
                selected_values = {
                    key: value
                    for key, value in self.flow_panel.values.items()
                    if value is not None
                }
                result = simulateFlow(self.challenge.exercise_type, selected_values)
            except (ArithmeticError, ValueError) as error:
                self.acceptResult(revision, None, str(error))
                return
            self.acceptResult(revision, result, "")
            return
        worker = SimulationWorker(revision, self.challenge, self.circuit.currentRows())
        worker.signals.finished.connect(self.acceptResult)
        self.jobs[revision] = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(int, object, str)
    def acceptResult(self, revision, result: Simulation | None, error):
        """Actualiza la interfaz con el resultado vigente de la simulación."""
        self.jobs.pop(revision, None)
        if revision != self.revision:
            return
        self.busy = False
        isFlowExercise = bool(self.challenge.exercise_type)
        self.circuit.setEnabled(not isFlowExercise)
        self.flow_panel.setParametersEnabled(isFlowExercise)
        self.simulate_button.setEnabled(True)
        self.simulate_button.setText("ϟ  ACTIVAR")
        if error:
            status = self.flow_panel.status if isFlowExercise else self.status
            status.setText("Error de cálculo")
            self.feedback.setText(error)
            return
        self.result = result
        if not isFlowExercise:
            self.device.value, self.device.unit = result.measured_value, result.unit
            self.device.passed = result.passed
            self.device.update()
        if not result.passed:
            status = self.flow_panel.status if isFlowExercise else self.status
            status.setText("Revisa el resultado" if isFlowExercise else "¡Casi!")
            status.setStyleSheet(
                f"color: {ORANGE}; background: #fff0db; border-color: #e7c393;"
                if not isFlowExercise else f"color: {ORANGE};"
            )
            if isFlowExercise:
                objective = FLOW_EXERCISES[self.challenge.exercise_type].objective
                self.feedback.setText(
                    f"{result.measured_value:.3f} {result.unit} · Objetivo: {objective}. "
                    "Ajusta los bloques."
                )
            else:
                if self.challenge.result_unit == "W":
                    self.feedback.setText(
                        f"{result.measured_value:.2f} W · Ajusta las bombillas "
                        "para alcanzar el intervalo de potencia."
                    )
                else:
                    direction = (
                        "Reduce" if result.measured_value > self.challenge.result
                        else "Aumenta"
                    )
                    self.feedback.setText(
                        f"{result.measured_value:.3f} Ω · {direction} "
                        "la resistencia equivalente."
                    )
            return
        record = self.session.complete()
        self.updateHud()
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
            self.startScreen.markCompleted(self.active_mode)
            if self.session_number is None:
                if not self.session_statistics_error:
                    self.session_statistics_error = "No se pudo reservar el número de sesión."
            else:
                try:
                    self.statistics.save_session(self.session_number, self.session_records)
                    self.session_statistics_error = ""
                except (OSError, ValueError) as save_error:
                    self.session_statistics_error = str(save_error)
        status = self.flow_panel.status if isFlowExercise else self.status
        status.setText("¡En marcha!")
        status.setStyleSheet("")
        self.circuit.setEnabled(False)
        self.flow_panel.setParametersEnabled(False)
        self.simulate_button.setEnabled(False)
        self.feedback.setText("" if not self.progress_error else "No se pudo guardar: " + self.progress_error)
        self.victory.showRecord(
            record,
            self.session_complete,
            self.session_statistics_error,
        )

    def showStatistics(self):
        """Construye y muestra las estadísticas guardadas de las sesiones."""
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
        """Cierra el catálogo ante clic exterior o la tecla Escape."""
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
        """Ajusta las superposiciones cuando cambia el tamaño de la ventana."""
        super().resizeEvent(event)
        if hasattr(self, "pauseMenu") and self.pauseMenu.isVisible():
            self.pauseMenu.setGeometry(self.rect())
        if hasattr(self, "component_menu"):
            self.component_menu.hide()
        if hasattr(self, "victory") and self.victory.isVisible():
            self.victory.showRecord(
                self.history[-1],
                self.session_complete,
                self.session_statistics_error,
            )

    def closeEvent(self, event):
        """Retira el filtro global y detiene los temporizadores al cerrar."""
        QApplication.instance().removeEventFilter(self)
        self.hud_timer.stop()
        self.circuit.animation_timer.stop()
        QThreadPool.globalInstance().waitForDone()
        event.accept()
