"""Pantalla de juego; las gráficas se reservan a las estadísticas del jugador."""
from pathlib import Path
from PySide6.QtCore import QEvent, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QGridLayout,
    QHBoxLayout, QMainWindow, QPushButton, QScrollArea, QVBoxLayout, QWidget)
from game_session import CATALOG, GameSession, ProgressStore
from motion import SceneTransition, WidgetMotion
from game_style import BG, PANEL, EDGE, TEXT, MUTED, TEAL, ORANGE, STYLE
from game_widgets import (GameBackdrop, CircuitView, DeviceIllustration,
                          SimulationWorker, configure_application, label)
from scientific_model import Simulation, load_challenges

BASE = Path(__file__).resolve().parent


class ComponentMenu(QFrame):
    """Inventario cerrado de piezas. No admite valores escritos por el jugador."""
    chosen = Signal(str, float)

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("componentMenu")
        self.setFixedWidth(302)
        self.kind = "R"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)
        top = QHBoxLayout()
        self.title = label("", "section")
        top.addWidget(self.title, 1)
        close = QPushButton("×")
        close.setObjectName("closeMenu")
        close.setAccessibleName("Cerrar inventario")
        close.clicked.connect(self.dismiss)
        top.addWidget(close)
        layout.addLayout(top)
        grid = QGridLayout()
        grid.setSpacing(7)
        self.buttons = []
        for index in range(6):
            button = QPushButton()
            button.setObjectName("preset")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, i=index: self.choose(self.values[i]))
            grid.addWidget(button, index // 3, index % 3)
            self.buttons.append(button)
        layout.addLayout(grid)
        self.motion = WidgetMotion(self)
        self.hide()

    def open_above(self, kind, current, anchor):
        self.kind, self.values = kind, CATALOG[kind]
        unit = "Ω" if kind == "R" else "µF"
        self.title.setText("R1 · Resistencia" if kind == "R" else "C1 · Condensador")
        for button, value in zip(self.buttons, self.values):
            button.setText(f"{value:g} {unit}")
            button.setChecked(current == value)
        self.adjustSize()
        x = max(10, min(anchor.center().x() - self.width() // 2,
                        self.parentWidget().width() - self.width() - 10))
        self.move(x, max(10, anchor.top() - self.height() - 12))
        self.motion.reveal()

    def dismiss(self):
        self.motion.dismiss()

    def hide(self):
        if hasattr(self, "motion"):
            self.motion.reset()
        super().hide()

    def choose(self, value):
        self.dismiss()
        self.chosen.emit(self.kind, float(value))


class StatisticsDialog(QDialog):
    """Gráficas de partidas reales, mostradas únicamente al consultar el progreso."""
    def __init__(self, records, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Circuit Quest · Mi progreso")
        self.resize(1000, 610)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(label("TU RECORRIDO", "eyebrow"))
        layout.addWidget(label("Mi progreso", "hero"))
        self.canvas = None
        if not records:
            layout.addStretch()
            empty = label("Completa tu primer nivel.", "muted", True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
            layout.addStretch()
        else:
            import numpy as np
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            from matplotlib.ticker import MaxNLocator
            missions = "misión resuelta" if len(records) == 1 else "misiones resueltas"
            layout.addWidget(label(f"{len(records)} {missions} · Últimas 10 partidas", "muted"))
            rows = records[-10:]
            figure = Figure(figsize=(9, 3.6), facecolor=BG, layout="constrained")
            self.canvas = FigureCanvasQTAgg(figure)
            axes = figure.subplots(1, 2)
            x = np.arange(len(rows))
            captions = [f"{i + 1 + len(records) - len(rows):02d}\n{r['reto_id']}" for i, r in enumerate(rows)]
            for ax in axes:
                ax.set_facecolor(BG)
                ax.spines[["top", "right"]].set_visible(False)
                for spine in ax.spines.values():
                    spine.set_color(EDGE)
                ax.tick_params(colors=MUTED, labelsize=9)
                ax.set_xticks(x, captions)
                ax.set_xlabel("Partida / misión", color=MUTED)
                ax.grid(axis="y", color=EDGE, alpha=0.5)
                ax.set_axisbelow(True)
            axes[0].bar(x, [r["tiempo_s"] for r in rows], color=TEAL, width=0.55)
            axes[0].set_title("Tiempo para resolver la misión", color=TEXT, pad=15)
            axes[0].set_ylabel("Segundos", color=MUTED)
            axes[1].bar(x - 0.17, [r["cambios_r"] for r in rows], width=0.34, color=TEAL, label="Resistencia")
            axes[1].bar(x + 0.17, [r["cambios_c"] for r in rows], width=0.34, color=ORANGE, label="Condensador")
            axes[1].set_title("Cambios de componentes", color=TEXT, pad=15)
            axes[1].set_ylabel("Número de cambios", color=MUTED)
            axes[1].yaxis.set_major_locator(MaxNLocator(integer=True))
            axes[1].legend(facecolor=PANEL, edgecolor=EDGE, labelcolor=TEXT)
            layout.addWidget(self.canvas, 1)
            latest = rows[-1]
            layout.addWidget(label(f"Última misión: {latest['pruebas']} pruebas · {latest['cambios_total']} cambios · {latest['tiempo_s']:.1f} s", "muted"))
        close = QPushButton("VOLVER AL JUEGO")
        close.clicked.connect(lambda: self.motion.dismiss(self.accept))
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.motion = WidgetMotion(self)

    def showEvent(self, event):
        super().showEvent(event)
        self.motion.reveal(distance=0, duration=280)


class VictoryOverlay(QWidget):
    """Pantalla de misión cumplida sin gráficas durante la partida."""
    next_level = Signal()
    statistics = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.box = QFrame(self)
        self.box.setObjectName("victory")
        self.box.setFixedWidth(550)
        layout = QVBoxLayout(self.box)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(16)
        for text, style in [("✦  ✦  ✦", "gold"), ("¡NIVEL SUPERADO!", "hero")]:
            item = label(text, style)
            item.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(item)
        self.summary = label("", "section", True)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary)
        advance = QPushButton("SIGUIENTE MISIÓN  →")
        advance.setObjectName("primary")
        advance.clicked.connect(self.next_level.emit)
        layout.addWidget(advance)
        progress = QPushButton("VER MI PROGRESO")
        progress.clicked.connect(self.statistics.emit)
        layout.addWidget(progress)
        self.motion = WidgetMotion(self)
        self.hide()

    def show_record(self, record):
        if self.isVisible():
            self.motion.reset()
        changes = "cambio" if record['cambios_total'] == 1 else "cambios"
        attempts = "prueba" if record['pruebas'] == 1 else "pruebas"
        self.summary.setText(f"{record['tiempo_s']:.1f} s     /     {record['cambios_total']} {changes}     /     {record['pruebas']} {attempts}")
        self.setGeometry(self.parentWidget().rect())
        self.box.adjustSize()
        self.box.move((self.width() - self.box.width()) // 2, (self.height() - self.box.height()) // 2)
        if not self.isVisible():
            self.motion.reveal(distance=22, duration=340, moving=self.box)

    def hide(self):
        if hasattr(self, "motion"):
            self.motion.reset()
        super().hide()

    def paintEvent(self, _event):
        QPainter(self).fillRect(self.rect(), QColor(244, 235, 255, 225))


class MainWindow(QMainWindow):
    """Juego de misiones: selección cerrada, pruebas y estadísticas del jugador."""
    def __init__(self, progress_path=None):
        super().__init__()
        self.setWindowTitle("Circuit Quest · Restaura la energía")
        self.resize(1440, 900)
        self.setMinimumSize(1000, 700)
        self.challenges = load_challenges(BASE / "data" / "retos.csv")
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
        self.set_challenge(0)
        self.hud_timer.start()
        QTimer.singleShot(0, self.transition.play)

    def build_ui(self):
        self.content_root = GameBackdrop()
        self.content_root.setMinimumSize(970, 650)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.content_root)
        self.setCentralWidget(scroll)
        layout = QVBoxLayout(self.content_root)
        layout.setContentsMargins(30, 24, 30, 26)
        layout.setSpacing(22)

        top = QHBoxLayout()
        mark = label("ϟ", "levelBadge")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(56, 56)
        top.addWidget(mark)
        top.addSpacing(8)
        top.addWidget(label("Circuit Quest", "title"))
        top.addStretch()
        hud = QFrame()
        hud.setObjectName("hud")
        metrics = QHBoxLayout(hud)
        metrics.setContentsMargins(20, 9, 20, 10)
        metrics.setSpacing(24)
        self.timer_label = label("00:00", "metric")
        self.changes_label = label("00", "metric")
        self.attempts_label = label("00", "metric")
        for title, value in [("TIEMPO", self.timer_label), ("CAMBIOS", self.changes_label), ("INTENTOS", self.attempts_label)]:
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(title, "eyebrow"))
            col.addWidget(value)
            metrics.addLayout(col)
        top.addWidget(hud)
        top.addSpacing(8)
        self.progress_button = QPushButton("Mi progreso")
        self.progress_button.setObjectName("quiet")
        self.progress_button.clicked.connect(self.show_statistics)
        top.addWidget(self.progress_button)
        layout.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(20)
        mission = QFrame()
        mission.setObjectName("mission")
        mission.setFixedWidth(232)
        quest = QVBoxLayout(mission)
        quest.setContentsMargins(22, 24, 22, 24)
        quest.setSpacing(15)
        self.mission_tag = label("", "levelBadge")
        self.mission_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        quest.addWidget(self.mission_tag)
        self.mission_title = label("Despierta al robot", "hero", True)
        quest.addWidget(self.mission_title)
        self.device_name = label("", "muted", True)
        quest.addWidget(self.device_name)
        quest.addStretch(1)
        quest.addWidget(label("OBJETIVO", "eyebrow"))
        self.target_label = label("", "gold", True)
        quest.addWidget(self.target_label)
        self.tolerance_label = label("", "muted", True)
        quest.addWidget(self.tolerance_label)
        quest.addStretch(1)
        self.description = label("Toca R1 o C1\npara cambiar una pieza.", "hint", True)
        quest.addWidget(self.description)
        body.addWidget(mission)

        stage = QFrame()
        stage.setObjectName("playfield")
        field = QVBoxLayout(stage)
        field.setContentsMargins(20, 20, 20, 24)
        field.setSpacing(12)
        stage_top = QHBoxLayout()
        stage_top.addWidget(label("EL TALLER", "eyebrow"))
        stage_top.addStretch()
        self.level_path = label("", "hint")
        stage_top.addWidget(self.level_path)
        field.addLayout(stage_top)
        arena = QHBoxLayout()
        arena.setSpacing(0)
        self.circuit = CircuitView()
        self.circuit.selected.connect(self.select_component)
        arena.addWidget(self.circuit, 1)
        dock = QFrame()
        dock.setObjectName("deviceDock")
        dock.setFixedWidth(210)
        right = QVBoxLayout(dock)
        right.setContentsMargins(0, 0, 0, 0)
        self.device = DeviceIllustration()
        self.device.setFixedHeight(280)
        self.circuit.animation_timer.timeout.connect(self.device.animate)
        right.addStretch()
        right.addWidget(self.device)
        self.status = label("", "badge", True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.status)
        right.addStretch()
        arena.addWidget(dock)
        field.addLayout(arena, 1)
        controls = QFrame()
        controls.setObjectName("controls")
        footer = QHBoxLayout(controls)
        footer.setContentsMargins(16, 14, 16, 14)
        self.feedback = label("", "muted", True)
        footer.addWidget(self.feedback, 1)
        self.reset_button = QPushButton("↻")
        self.reset_button.setObjectName("reset")
        self.reset_button.setAccessibleName("Reiniciar misión")
        self.reset_button.setToolTip("Reiniciar misión")
        self.reset_button.setFixedWidth(56)
        self.reset_button.clicked.connect(lambda: self.change_level(self.level_index))
        footer.addWidget(self.reset_button)
        self.simulate_button = QPushButton("ϟ  ACTIVAR")
        self.simulate_button.setObjectName("primary")
        self.simulate_button.clicked.connect(self.run_simulation)
        footer.addWidget(self.simulate_button)
        field.addWidget(controls)
        body.addWidget(stage, 1)
        layout.addLayout(body, 1)

        self.component_menu = ComponentMenu(self.content_root)
        self.component_menu.chosen.connect(self.apply_component)
        self.victory = VictoryOverlay(self.content_root)
        self.victory.next_level.connect(lambda: self.change_level((self.level_index + 1) % len(self.challenges)))
        self.victory.statistics.connect(self.show_statistics)
        scroll.verticalScrollBar().valueChanged.connect(self.component_menu.hide)
        self.transition = SceneTransition(self.content_root)
        self.content_root.resized.connect(self.reposition_overlays)

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
        self.session = GameSession(c.identifier, c.name)
        self.revision += 1
        self.result, self.busy = None, False
        self.resistance, self.capacity = c.resistance, c.capacitance_uf
        self.component_menu.hide()
        self.victory.hide()
        self.circuit.setEnabled(True)
        self.circuit.voltage, self.circuit.measured = c.voltage, None
        self.circuit.resistor.replace(c.resistance, False)
        self.circuit.capacitor.replace(c.capacitance_uf, False)
        for item in (self.circuit.resistor, self.circuit.capacitor):
            item.active = False
            item.update()
        self.mission_tag.setText(f"NIVEL {index + 1:02d}")
        self.level_path.setText("  ·  ".join("●" if i <= index else "○" for i in range(len(self.challenges))))
        self.description.setText("Toca R1 o C1\npara cambiar una pieza.")
        self.target_label.setText(f"{c.target_voltage:g} V\na los {c.target_time:g} s")
        self.tolerance_label.setText(f"Margen ±{c.tolerance:g} V")
        self.device_name.setText(c.name)
        self.device.voltage, self.device.passed = None, False
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
        seconds = int(self.session.elapsed)
        self.timer_label.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")
        self.changes_label.setText(f"{self.session.total_changes:02d}")
        self.attempts_label.setText(f"{self.session.attempts:02d}")

    def select_component(self, kind):
        if self.session.finished is not None or self.busy:
            return
        item = self.circuit.resistor if kind == "R" else self.circuit.capacitor
        rect = self.circuit.mapFromScene(item.sceneBoundingRect()).boundingRect()
        rect.moveTopLeft(self.circuit.viewport().mapTo(self.content_root, rect.topLeft()))
        self.component_menu.open_above(kind, self.resistance if kind == "R" else self.capacity, rect)

    @Slot(str, float)
    def apply_component(self, kind, value):
        if self.busy or self.session.finished is not None:
            return
        old = self.resistance if kind == "R" else self.capacity
        if not self.session.change(kind, old, value):
            return
        if kind == "R":
            self.resistance = value
            self.circuit.resistor.replace(value)
        else:
            self.capacity = value
            self.circuit.capacitor.replace(value)
        self.revision += 1
        self.result, self.circuit.measured = None, None
        self.device.voltage, self.device.passed = None, False
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
        worker = SimulationWorker(revision, self.challenge, self.resistance, self.capacity)
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
        self.circuit.measured = result.measured_voltage
        self.device.voltage, self.device.passed = result.measured_voltage, result.passed
        self.device.update()
        if not result.passed:
            self.status.setText("¡Casi!")
            self.status.setStyleSheet(f"color: {ORANGE}; background: #fff0db; border-color: #e7c393;")
            direction = "Reduce" if result.measured_voltage > self.challenge.target_voltage else "Aumenta"
            self.feedback.setText(f"{result.measured_voltage:.3f} V · {direction} el voltaje.")
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
