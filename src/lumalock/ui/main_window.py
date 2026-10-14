"""Desktop editor orchestration. Image processing lives in background services."""

import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lumalock.ai.analyzer.scene_analyzer import analyze
from lumalock.ai.prompt.parser import apply_plan
from lumalock.ai.segmentation.segmentation_manager import SegmentationManager
from lumalock.core.config import data_dir, load_settings
from lumalock.core.hardware import detect_hardware
from lumalock.core.model_manager import MODEL_SPECS, ModelManager
from lumalock.export.exporter import export_image
from lumalock.imaging.geometry import transform_image
from lumalock.imaging.histogram import histogram
from lumalock.imaging.image_io import load_image
from lumalock.imaging.masks import mask_pixels
from lumalock.pipeline.renderer import render
from lumalock.presets.builtins import PRESETS
from lumalock.project.edit_state import Adjustments, EditState, MaskLayer
from lumalock.project.history import History
from lumalock.project.serialization import load_project, save_project
from lumalock.ui.dialogs.export import ExportDialog
from lumalock.ui.dialogs.settings import SettingsDialog
from lumalock.ui.panels.color_tools import ColorTools
from lumalock.ui.panels.controls import AdjustmentControls
from lumalock.ui.widgets.canvas import ImageCanvas
from lumalock.ui.widgets.histogram import Histogram
from lumalock.ui.workers.task import Task


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LumaLock AI · Edit beautifully. Preserve identity.")
        self.resize(1440, 900)
        self.settings = load_settings()
        self.hardware = detect_hardware()
        self.models = ModelManager(self.hardware)
        self.segmentation = SegmentationManager(self.models, self.settings.face_expansion)
        self.document = None
        self.preview = None
        self.result = None
        self.analysis = None
        self.state = EditState(identity_lock=self.settings.identity_lock)
        self.history = History(self.state)
        self.prompts = []
        self.active_mask = None
        self.task = None
        self.setup_dialog = None
        self.overlay_task = None
        self.overlay_cache = None
        self.generation = 0
        self.pending_plan = None
        self.recipe_base = None
        self.last_recipe = None
        self.look_timer = QTimer(self)
        self.look_timer.setSingleShot(True)
        self.look_timer.setInterval(200)
        self.look_timer.timeout.connect(self.repeat_recipe)
        self.sessions = {}
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(180)
        self.render_timer.timeout.connect(self.render_preview)
        self.commit_timer = QTimer(self)
        self.commit_timer.setSingleShot(True)
        self.commit_timer.setInterval(450)
        self.commit_timer.timeout.connect(lambda: self.commit("Manual adjustment"))
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(60_000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()
        self.build_ui()
        self.build_menu()
        self.sync_controls()

    def button(self, text, callback, layout, primary=False):
        button = QPushButton(text)
        button.clicked.connect(callback)
        if primary:
            button.setObjectName("primary")
        layout.addWidget(button)
        return button

    def build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 10)
        self.setCentralWidget(central)
        header = QHBoxLayout()
        brand = QLabel("LumaLock AI")
        brand.setObjectName("brand")
        header.addWidget(brand)
        subtitle = QLabel("Edit beautifully. Preserve identity.")
        subtitle.setObjectName("muted")
        header.addWidget(subtitle)
        header.addStretch()
        header.addWidget(
            QLabel(f"{self.hardware.gpu} · {self.hardware.vram_gb:g} GB · {self.hardware.profile}")
        )
        root.addLayout(header)
        splitter = QSplitter()
        root.addWidget(splitter, 1)
        left = QFrame()
        self.advanced_sidebar = left
        left.setObjectName("panel")
        left.setMinimumWidth(200)
        left.setMaximumWidth(300)
        sidebar = QVBoxLayout(left)
        self.button("Open photograph", self.open_dialog, sidebar, True)
        self.filename = QLabel("No photograph open")
        self.filename.setWordWrap(True)
        sidebar.addWidget(self.filename)
        tabs = QTabWidget()
        sidebar.addWidget(tabs, 1)
        self.library = QListWidget()
        self.library.itemDoubleClicked.connect(
            lambda item: self.open_image(item.data(Qt.ItemDataRole.UserRole))
        )
        tabs.addTab(self.library, "Library")
        self.history_list = QListWidget()
        self.history_list.currentRowChanged.connect(self.select_history)
        tabs.addTab(self.history_list, "History")
        masks_page = QWidget()
        mask_layout = QVBoxLayout(masks_page)
        self.mask_list = QListWidget()
        self.mask_list.currentRowChanged.connect(self.select_mask)
        mask_layout.addWidget(self.mask_list)
        self.mask_kind = QComboBox()
        self.mask_kind.addItems(
            [
                "subject",
                "background",
                "face",
                "sky",
                "brush",
                "gradient",
                "radial",
                "rectangle",
                "ellipse",
            ]
        )
        mask_layout.addWidget(self.mask_kind)
        self.button("Create mask", self.create_mask, mask_layout)
        self.button("Global controls", self.select_global, mask_layout)
        self.button("Rename mask", self.rename_mask, mask_layout)
        self.button("Invert mask", self.invert_mask, mask_layout)
        self.button("Delete mask", self.delete_mask, mask_layout)
        self.mask_enabled = QCheckBox("Enable mask")
        self.mask_enabled.setChecked(True)
        self.mask_enabled.toggled.connect(self.enable_mask)
        mask_layout.addWidget(self.mask_enabled)
        self.mask_protected = QCheckBox("Protect from generation")
        self.mask_protected.toggled.connect(lambda value: self.mask_property("protected", value))
        mask_layout.addWidget(self.mask_protected)
        self.mask_opacity = QDoubleSpinBox()
        self.mask_opacity.setRange(0, 1)
        self.mask_opacity.setSingleStep(0.1)
        self.mask_opacity.setValue(1)
        self.mask_opacity.valueChanged.connect(lambda value: self.mask_property("opacity", value))
        mask_layout.addWidget(QLabel("Mask opacity"))
        mask_layout.addWidget(self.mask_opacity)
        self.mask_feather = QDoubleSpinBox()
        self.mask_feather.setRange(0, 100)
        self.mask_feather.setValue(0)
        self.mask_feather.valueChanged.connect(lambda value: self.mask_property("feather", value))
        mask_layout.addWidget(QLabel("Edge feather"))
        mask_layout.addWidget(self.mask_feather)
        self.mask_geometry = QWidget()
        geometry_form = QFormLayout(self.mask_geometry)
        self.geometry_spins = []
        for index, label in enumerate(
            ("X / start X", "Y / start Y", "Radius / end X", "Radius / end Y")
        ):
            spin = QDoubleSpinBox()
            spin.setRange(0, 1)
            spin.setSingleStep(0.05)
            spin.setDecimals(3)
            spin.valueChanged.connect(lambda value, i=index: self.geometry_changed(i, value))
            self.geometry_spins.append(spin)
            geometry_form.addRow(label, spin)
        mask_layout.addWidget(self.mask_geometry)
        brush_size = QDoubleSpinBox()
        brush_size.setRange(0.005, 0.3)
        brush_size.setDecimals(3)
        brush_size.setSingleStep(0.01)
        brush_size.setValue(0.04)
        brush_size.valueChanged.connect(lambda value: setattr(self.canvas, "brush_radius", value))
        mask_layout.addWidget(QLabel("Brush radius (relative to image)"))
        mask_layout.addWidget(brush_size)
        mask_scroll = QScrollArea()
        mask_scroll.setWidgetResizable(True)
        mask_scroll.setWidget(masks_page)
        tabs.addTab(mask_scroll, "Masks")
        self.presets = QComboBox()
        self.presets.addItems(PRESETS)
        sidebar.addWidget(self.presets)
        self.button("Apply preset", self.apply_preset, sidebar)
        self.version_list = QComboBox()
        sidebar.addWidget(self.version_list)
        version_actions = QHBoxLayout()
        self.button("Save version", self.save_version, version_actions)
        self.button("Restore", self.restore_version, version_actions)
        sidebar.addLayout(version_actions)
        privacy = QLabel("Local Processing\nYour photographs are processed on this device.")
        privacy.setWordWrap(True)
        privacy.setObjectName("muted")
        sidebar.addWidget(privacy)
        splitter.addWidget(left)
        canvas_panel = QWidget()
        canvas_layout = QVBoxLayout(canvas_panel)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = ImageCanvas()
        canvas_layout.addWidget(self.canvas, 1)
        self.canvas.painted.connect(self.brush_dab)
        self.canvas.stroke_finished.connect(lambda: self.commit("Brush mask"))
        compare = QHBoxLayout()
        self.button("Fit", self.canvas.fit_image, compare)
        self.button("100%", self.canvas.one_to_one, compare)
        self.original_toggle = QCheckBox("Original")
        self.original_toggle.toggled.connect(self.toggle_original)
        compare.addWidget(self.original_toggle)
        self.split_toggle = QCheckBox("Compare")
        self.split_toggle.toggled.connect(self.toggle_split)
        compare.addWidget(self.split_toggle)
        split = QSlider(Qt.Orientation.Horizontal)
        split.setRange(0, 100)
        split.setValue(50)
        split.valueChanged.connect(self.move_split)
        compare.addWidget(split)
        self.overlay_toggle = QCheckBox("Mask overlay")
        self.overlay_toggle.toggled.connect(self.update_overlay)
        compare.addWidget(self.overlay_toggle)
        clip = QCheckBox("Clipping")
        clip.toggled.connect(self.toggle_clipping)
        compare.addWidget(clip)
        canvas_layout.addLayout(compare)
        splitter.addWidget(canvas_panel)
        right = QFrame()
        right.setObjectName("panel")
        right.setMinimumWidth(340)
        right.setMaximumWidth(460)
        tools = QVBoxLayout(right)
        self.mode = QComboBox()
        self.mode.addItem("Natural AI", "Preserve")
        self.mode.addItem("Creative AI", "Creative")
        self.mode.addItem("Manual Pro", "Manual Pro")
        self.mode.currentTextChanged.connect(self.mode_changed)
        tools.addWidget(self.mode)
        self.identity = QCheckBox("Identity Lock · preserve facial structure")
        self.identity.setChecked(True)
        self.identity.toggled.connect(self.identity_changed)
        tools.addWidget(self.identity)
        self.histogram = Histogram()
        self.histogram.setVisible(False)
        tools.addWidget(self.histogram)
        self.workspace = QTabWidget()
        tools.addWidget(self.workspace, 1)
        assistant_page = QWidget()
        assistant_layout = QVBoxLayout(assistant_page)
        self.button("Open photograph", self.open_dialog, assistant_layout, True)
        assistant_scroll = QScrollArea()
        assistant_scroll.setWidgetResizable(True)
        assistant_scroll.setWidget(assistant_page)
        self.workspace.addTab(assistant_scroll, "Smart edit")
        heading = QLabel("A better photo. Still you.")
        heading.setObjectName("sectionTitle")
        assistant_layout.addWidget(heading)
        subtitle = QLabel(
            "Choose a look, adjust the amount, then export. Your original stays untouched."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("muted")
        assistant_layout.addWidget(subtitle)
        self.quality = QComboBox()
        self.quality.addItems(["Maximum", "Quality", "Preview"])
        self.quality.setCurrentText(self.settings.quality_mode)
        self.quality.currentTextChanged.connect(self.quality_changed)
        self.quality.setToolTip(
            "Creative rendering effort: Preview 20 steps / 512 px, Quality 40 steps / 1024 px, Maximum 60 steps / configured resolution. Photographic exports retain original resolution."
        )
        assistant_layout.addWidget(self.quality)
        self.quality.setVisible(False)
        self.analysis_label = QLabel("Open an image for exposure and quality analysis.")
        self.analysis_label.setWordWrap(True)
        self.analysis_label.setObjectName("muted")
        self.analysis_label.setVisible(False)
        assistant_layout.addWidget(self.analysis_label)
        self.button("AI Enhance - preview plan", self.auto_enhance, assistant_layout, True)
        looks = QGridLayout()
        for index, name in enumerate(
            ("Natural", "Portrait", "Warm light", "Low light", "Cinematic")
        ):
            button = QPushButton(name)
            button.setObjectName("look")
            button.setMinimumHeight(40)
            button.clicked.connect(lambda checked=False, key=name: self.quick_enhance(key))
            looks.addWidget(button, index // 2, index % 2)
        assistant_layout.addLayout(looks)
        amount_row = QHBoxLayout()
        amount_row.addWidget(QLabel("Look amount"))
        self.amount_label = QLabel("75%")
        amount_row.addStretch()
        amount_row.addWidget(self.amount_label)
        assistant_layout.addLayout(amount_row)
        self.look_amount = QSlider(Qt.Orientation.Horizontal)
        self.look_amount.setRange(0, 100)
        self.look_amount.setValue(75)
        self.look_amount.valueChanged.connect(self.look_amount_changed)
        assistant_layout.addWidget(self.look_amount)
        self.button("Check face against original", self.check_face, assistant_layout)
        self.button("Paint face protection", self.paint_protection, assistant_layout)
        self.button("Select creative edit area", self.paint_edit_area, assistant_layout)
        self.button("Protect entire person", self.protect_person, assistant_layout)
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Tell LumaLock what you want…")
        self.prompt.setMaximumHeight(85)
        assistant_layout.addWidget(self.prompt)
        self.ai_strength = QSlider(Qt.Orientation.Horizontal)
        self.ai_strength.setRange(0, 100)
        self.ai_strength.setValue(45)
        self.ai_strength_label = QLabel("AI edit strength · 45%")
        self.ai_strength.valueChanged.connect(
            lambda value: self.ai_strength_label.setText(f"AI edit strength · {value}%")
        )
        assistant_layout.addWidget(self.ai_strength_label)
        assistant_layout.addWidget(self.ai_strength)
        prompt_actions = QHBoxLayout()
        self.button("Preview prompt", lambda: self.prompt_edit(False), prompt_actions)
        self.button("Apply / Generate", self.apply_pending_plan, prompt_actions)
        assistant_layout.addLayout(prompt_actions)
        self.assistant = QLabel(
            "Quick looks are immediate. AI generation runs locally after you approve the plan."
        )
        self.assistant.setWordWrap(True)
        assistant_layout.addWidget(self.assistant)
        assistant_layout.addStretch()
        manual_page = QWidget()
        manual_layout = QVBoxLayout(manual_page)
        self.workspace.addTab(manual_page, "Manual controls")
        self.control_target = QLabel("Global adjustments")
        manual_layout.addWidget(self.control_target)
        self.controls = AdjustmentControls()
        self.controls.changed.connect(self.adjustment_changed)
        self.controls.committed.connect(lambda name: self.commit(name.title()))
        self.tool_tabs = QTabWidget()
        self.tool_tabs.addTab(self.controls, "Adjust")
        self.color_tools = ColorTools()
        self.color_tools.hsl_changed.connect(self.hsl_changed)
        self.color_tools.curve_changed.connect(self.curve_changed)
        color_scroll = QScrollArea()
        color_scroll.setWidgetResizable(True)
        color_scroll.setWidget(self.color_tools)
        self.tool_tabs.addTab(color_scroll, "HSL / Curves")
        manual_layout.addWidget(self.tool_tabs, 1)
        self.button("Reset adjustments", self.reset_adjustments, manual_layout)
        self.button("Crop / rotate / straighten", self.geometry_dialog, manual_layout)
        splitter.addWidget(right)
        splitter.setSizes([220, 800, 390])
        left.setVisible(False)
        footer = QHBoxLayout()
        self.status = QLabel("Ready · Hold Space on the canvas to show the original")
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(200)
        self.progress.setRange(0, 100)
        footer.addWidget(self.progress)
        self.advanced_toggle = QCheckBox("Advanced tools")
        self.advanced_toggle.toggled.connect(self.show_advanced)
        footer.addWidget(self.advanced_toggle)
        self.button("Cancel", self.cancel_task, footer)
        self.button("Save project", self.save_project_dialog, footer)
        self.button("Export", self.export_dialog, footer, True)
        root.addLayout(footer)

    def build_menu(self):
        file = self.menuBar().addMenu("File")
        edit = self.menuBar().addMenu("Edit")
        help_menu = self.menuBar().addMenu("Help")
        for menu, label, shortcut, callback in [
            (file, "Open photograph", "Ctrl+O", self.open_dialog),
            (file, "Open project", "Ctrl+Shift+O", self.open_project_dialog),
            (file, "Save project", "Ctrl+S", self.save_project_dialog),
            (file, "Export", "Ctrl+E", self.export_dialog),
            (edit, "Undo", "Ctrl+Z", self.undo),
            (edit, "Redo", "Ctrl+Y", self.redo),
            (edit, "Settings / AI Models", None, self.settings_dialog),
            (help_menu, "System Information", None, self.system_info),
        ]:
            action = QAction(label, self)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)

    def show_advanced(self, enabled):
        self.advanced_sidebar.setVisible(enabled)
        self.histogram.setVisible(enabled)
        self.quality.setVisible(enabled)
        self.analysis_label.setVisible(enabled)

    def paint_protection(self):
        if self.document is None:
            return
        self.add_mask("brush", None)
        self.selected_layer().protected = True
        self.commit("Paint protection")
        self.assistant.setText(
            "Paint over the face or person to preserve its original pixels. Hold Alt to erase. Select an edit area separately for Creative AI."
        )

    def paint_edit_area(self):
        if self.document is None:
            return
        self.add_mask("brush", None)
        self.assistant.setText(
            "Paint where Creative AI may change the scene. Hold Alt to erase, then preview your prompt and Generate."
        )

    def error(self, message):
        QMessageBox.warning(self, "LumaLock AI", str(message))

    def run_task(self, operation, callback):
        if self.task:
            self.task.cancelled.set()
        task = Task(operation)
        self.task = task
        task.signals.progress.connect(self.show_progress)
        task.signals.result.connect(lambda result: callback(result) if self.task is task else None)
        task.signals.error.connect(
            lambda message: self.show_task_error(message) if self.task is task else None
        )
        task.signals.finished.connect(lambda: self.task_finished(task))
        self.pool.start(task)

    def task_finished(self, task):
        if self.task is task:
            self.task = None
            self.progress.setRange(0, 100)
            self.progress.setValue(0)

    def show_task_error(self, message):
        self.status.setText(message)
        if "cancel" not in message.lower():
            self.assistant.setText(message)

    def show_progress(self, value, text):
        self.progress.setRange(0, 0 if value < 0 else 100)
        self.progress.setValue(value)
        self.status.setText(text)

    def cancel_task(self):
        if self.task:
            self.task.cancelled.set()
            self.status.setText("Cancelling at the next safe stage…")

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open photograph", "", "Photographs (*.jpg *.jpeg *.png *.webp *.tif *.tiff)"
        )
        if path:
            self.open_image(path)

    def open_image(self, path, history=None, prompts=None):
        if self.document:
            self.commit("Manual adjustment")
            self.sessions[str(self.document.path)] = (self.history, self.prompts.copy())
        saved = self.sessions.get(str(Path(path).resolve()))
        if history is None and saved:
            history, prompts = saved
        settings = self.settings

        def operation(cancelled, progress):
            progress(10, "Opening image…")
            document = load_image(path)
            preview = document.preview(settings.preview_size)
            return document, preview, analyze(preview, regions=True)

        self.run_task(operation, lambda bundle: self.image_loaded(bundle, history, prompts))

    def image_loaded(self, bundle, history, prompts):
        self.pending_ai_plan = None
        self.recipe_base = None
        self.last_recipe = None
        self.document, self.preview, self.analysis = bundle
        self.overlay_cache = None
        if not any(
            self.library.item(i).data(Qt.ItemDataRole.UserRole) == str(self.document.path)
            for i in range(self.library.count())
        ):
            item = QListWidgetItem(self.document.path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(self.document.path))
            item.setToolTip(str(self.document.path))
            self.library.addItem(item)
        self.history = history or History(EditState(identity_lock=self.settings.identity_lock))
        self.state = self.history.state
        self.prompts = prompts or []
        self.active_mask = None
        self.pending_plan = None
        self.filename.setText(
            f"{self.document.path.name}\n{self.document.size[0]} × {self.document.size[1]}"
        )
        self.analysis_label.setText(self.analysis.describe())
        self.histogram.set_histogram(self.analysis.histogram)
        self.result = self.preview.copy()
        self.canvas.set_images(
            transform_image(self.preview, self.state.geometry), self.result, True
        )
        self.sync_controls()
        self.render_preview()

    def selected_layer(self):
        return next((layer for layer in self.state.masks if layer.id == self.active_mask), None)

    def sync_controls(self):
        layer = self.selected_layer()
        self.version_list.clear()
        self.version_list.addItems(self.history.versions)
        self.mask_geometry.setVisible(
            bool(layer and layer.kind in ("radial", "gradient", "rectangle", "ellipse"))
        )
        if layer and layer.kind in ("radial", "gradient", "rectangle", "ellipse"):
            for spin, value in zip(self.geometry_spins, layer.geometry):
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
        self.controls.sync(layer.adjustments if layer else self.state.adjustments)
        self.control_target.setText(f"Mask · {layer.name}" if layer else "Global adjustments")
        self.color_tools.sync(self.state)
        for widget, value in [
            (self.identity, self.state.identity_lock),
            (self.mask_enabled, layer.enabled if layer else True),
            (self.mask_protected, layer.protected if layer else False),
        ]:
            widget.blockSignals(True)
            widget.setChecked(value)
            widget.blockSignals(False)
        for widget, value in [
            (self.mask_opacity, layer.opacity if layer else 1),
            (self.mask_feather, layer.feather if layer else 0),
        ]:
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(self.mode.findData(self.state.mode))
        self.mode.blockSignals(False)
        self.history_list.blockSignals(True)
        self.history_list.clear()
        self.history_list.addItems([entry.label for entry in self.history.entries])
        self.history_list.setCurrentRow(self.history.index)
        self.history_list.blockSignals(False)
        self.mask_list.blockSignals(True)
        self.mask_list.clear()
        self.mask_list.addItems([layer.name for layer in self.state.masks])
        for index, mask in enumerate(self.state.masks):
            if mask.id == self.active_mask:
                self.mask_list.setCurrentRow(index)
        self.mask_list.blockSignals(False)
        self.canvas.brush = bool(layer and layer.kind == "brush")
        self.canvas.setDragMode(
            self.canvas.DragMode.NoDrag
            if self.canvas.brush
            else self.canvas.DragMode.ScrollHandDrag
        )
        self.update_overlay()

    def adjustment_changed(self, name, value):
        self.recipe_base = None
        layer = self.selected_layer()
        target = layer.adjustments if layer else self.state.adjustments
        setattr(target, name, value)
        self.schedule_render()
        self.commit_timer.start()

    def hsl_changed(self, name, values):
        self.state.hsl[name] = values
        self.schedule_render()
        self.commit_timer.start()

    def curve_changed(self, channel, points):
        self.state.curves[channel] = points
        self.schedule_render()
        self.commit_timer.start()

    def schedule_render(self):
        self.pending_plan = None
        self.generation += 1
        self.render_timer.start()

    def render_preview(self, override=None):
        if self.preview is None:
            return
        snapshot = (override or self.state).model_copy(deep=True)
        source = self.preview
        generation = self.generation
        self.run_task(
            lambda cancelled, progress: (render(source, snapshot, cancelled, progress), generation),
            self.preview_ready,
        )

    def preview_ready(self, bundle):
        result, generation = bundle
        if generation != self.generation:
            return
        self.result = result
        self.canvas.set_images(transform_image(self.preview, self.state.geometry), result)
        self.histogram.set_histogram(histogram(result))
        self.update_overlay()
        self.status.setText("Preview ready · Export renders from the original resolution")

    def commit(self, label):
        self.commit_timer.stop()
        if self.document is None:
            return
        self.history.push(label, self.state)
        self.sync_controls()

    def select_history(self, index):
        if index < 0:
            return
        self.commit_timer.stop()
        self.recipe_base = None
        self.state = self.history.select(index)
        self.active_mask = None
        self.sync_controls()
        self.schedule_render()

    def undo(self):
        self.commit("Manual adjustment")
        self.state = self.history.undo()
        self.active_mask = None
        self.sync_controls()
        self.schedule_render()

    def redo(self):
        self.state = self.history.redo()
        self.active_mask = None
        self.sync_controls()
        self.schedule_render()

    def select_mask(self, index):
        self.active_mask = (
            self.state.masks[index].id if 0 <= index < len(self.state.masks) else None
        )
        self.sync_controls()
        self.workspace.setCurrentIndex(1)

    def select_global(self):
        self.active_mask = None
        self.sync_controls()

    def create_mask(self):
        if self.preview is None:
            return
        kind = self.mask_kind.currentText()
        if kind in ("subject", "background"):
            self.assistant.setText(
                "Classical GrabCut estimates foreground; inspect coverage or paint your own mask. No extra AI model is used."
            )
        if kind in ("brush", "gradient", "radial", "rectangle", "ellipse"):
            self.add_mask(kind, None)
            return
        source = self.preview
        self.run_task(
            lambda cancelled, progress: self.segmentation.create(source, kind, cancelled, progress),
            lambda path: self.add_mask(kind, path),
        )

    def add_mask(self, kind, path):
        layer = MaskLayer(
            id=uuid.uuid4().hex, name=kind.title(), kind=kind, mask_file=str(path) if path else None
        )
        if kind == "gradient":
            layer.geometry = [0.5, 0.15, 0.5, 0.85]
        self.state.masks.append(layer)
        if path and self.analysis:
            from lumalock.pipeline.regional_analysis import update_regional_analysis

            self.analysis = update_regional_analysis(self.analysis, self.preview, layer)
        self.active_mask = layer.id
        self.overlay_toggle.setChecked(True)
        self.commit(f"{kind.title()} mask")
        self.schedule_render()

    def rename_mask(self):
        layer = self.selected_layer()
        if layer:
            name, ok = QInputDialog.getText(self, "Rename mask", "Name", text=layer.name)
            if ok and name.strip():
                layer.name = name.strip()
                self.commit("Rename mask")

    def invert_mask(self):
        layer = self.selected_layer()
        if layer:
            layer.inverted = not layer.inverted
            self.commit("Invert mask")
            self.schedule_render()

    def delete_mask(self):
        if self.active_mask:
            self.state.masks = [m for m in self.state.masks if m.id != self.active_mask]
            self.active_mask = None
            self.commit("Delete mask")
            self.schedule_render()

    def enable_mask(self, enabled):
        layer = self.selected_layer()
        if layer:
            layer.enabled = enabled
            self.commit("Enable mask" if enabled else "Disable mask")
            self.schedule_render()

    def mask_property(self, name, value):
        layer = self.selected_layer()
        if layer:
            setattr(layer, name, value)
            self.commit_timer.start()
            self.schedule_render()
            self.update_overlay()

    def geometry_changed(self, index, value):
        layer = self.selected_layer()
        if layer and layer.kind in ("radial", "gradient", "rectangle", "ellipse"):
            layer.geometry[index] = value
            self.commit_timer.start()
            self.schedule_render()

    def save_version(self):
        if self.document is None:
            return
        name, ok = QInputDialog.getText(self, "Save version", "Version name")
        if ok and name.strip():
            self.history.save_version(name.strip(), self.state)
            self.sync_controls()

    def restore_version(self):
        name = self.version_list.currentText()
        if name in self.history.versions:
            self.state = self.history.restore_version(name)
            self.active_mask = None
            self.sync_controls()
            self.schedule_render()

    def brush_dab(self, x, y, radius, erase):
        layer = self.selected_layer()
        if layer and layer.kind == "brush":
            from lumalock.imaging.geometry import source_coordinate

            x, y = source_coordinate(x, y, self.state.geometry, self.preview.shape[:2])
            if self.state.geometry.crop:
                radius *= min(self.state.geometry.crop[2:])
            layer.strokes.append([x, y, radius, float(erase)])
            self.schedule_render()

    def update_overlay(self):
        layer = self.selected_layer()
        self.canvas.overlay = None
        if self.preview is not None and layer and self.overlay_toggle.isChecked():
            key = layer.model_dump_json(exclude={"adjustments", "name", "enabled"})
            if self.overlay_cache and self.overlay_cache[0] == key:
                self.canvas.overlay = transform_image(self.overlay_cache[1], self.state.geometry)
            else:
                if self.overlay_task:
                    self.overlay_task.cancelled.set()
                snapshot = layer.model_copy(deep=True)
                shape = self.preview.shape[:2]
                task = Task(lambda cancelled, progress: (key, mask_pixels(snapshot, shape)))
                self.overlay_task = task
                task.signals.result.connect(self.overlay_ready)
                self.pool.start(task)
        self.canvas.refresh()

    def overlay_ready(self, bundle):
        key, mask = bundle
        layer = self.selected_layer()
        if layer and key == layer.model_dump_json(exclude={"adjustments", "name", "enabled"}):
            self.overlay_cache = (key, mask)
            self.canvas.overlay = (
                transform_image(mask, self.state.geometry)
                if self.overlay_toggle.isChecked()
                else None
            )
            self.canvas.refresh()

    def toggle_original(self, enabled):
        self.canvas.show_original = enabled
        self.canvas.refresh()

    def toggle_split(self, enabled):
        self.canvas.split = 0.5 if enabled else None
        self.canvas.refresh()

    def move_split(self, value):
        if self.split_toggle.isChecked():
            self.canvas.split = value / 100
            self.canvas.refresh()

    def toggle_clipping(self, enabled):
        self.canvas.clipping = enabled
        self.canvas.refresh()

    def mode_changed(self, mode):
        mode = self.mode.currentData()
        self.state.mode = mode
        self.commit(f"{mode} mode")
        if mode == "Manual Pro":
            self.workspace.setCurrentIndex(1)

    def identity_changed(self, enabled):
        self.state.identity_lock = enabled
        self.commit("Identity Lock on" if enabled else "Identity Lock off")

    def apply_preset(self):
        if self.document is None:
            return
        self.recipe_base = None
        self.look_timer.stop()
        self.pending_ai_plan = None
        self.state.adjustments = Adjustments(**PRESETS[self.presets.currentText()])
        self.active_mask = None
        self.commit(f"Preset: {self.presets.currentText()}")
        self.schedule_render()

    def auto_enhance(self):
        if self.document is None:
            return
        self.prompt.setPlainText(
            "Professionally enhance this photograph with natural lighting, balanced colors and realistic detail. Preserve all people, identity, content and composition."
        )
        self.prompt_edit(False)

    def quick_enhance(self, name):
        if self.preview is None:
            return
        if self.recipe_base is None or self.last_recipe != name:
            self.recipe_base = self.state.model_copy(deep=True)
        self.last_recipe = name
        from lumalock.pipeline.smart_enhance import smart_enhance

        source = self.preview
        analysis = self.analysis
        base = self.recipe_base.model_copy(deep=True)
        amount = self.look_amount.value() / 100
        self.run_task(
            lambda cancelled, progress: smart_enhance(
                source, base, analysis, self.segmentation, name, amount, cancelled, progress
            ),
            lambda result: self.recipe_ready(result, name, amount),
        )

    def recipe_ready(self, result, name, amount):
        self.state = result.state
        self.result = result.pixels
        self.active_mask = None
        self.commit(f"{name} · {round(amount * 100)}%")
        self.canvas.set_images(transform_image(self.preview, self.state.geometry), self.result)
        self.histogram.set_histogram(histogram(self.result))
        self.assistant.setText(result.summary)
        self.status.setText(
            "Ready to compare or export · face pixels are photographed, not generated"
        )

    def look_amount_changed(self, value):
        self.amount_label.setText(f"{value}%")
        if self.last_recipe and self.recipe_base is not None:
            self.look_timer.start()

    def repeat_recipe(self):
        if self.last_recipe and self.recipe_base is not None:
            self.quick_enhance(self.last_recipe)

    def quality_changed(self, value):
        self.settings.quality_mode = value
        self.models.settings = self.settings
        from lumalock.core.config import save_settings

        save_settings(self.settings)

    def check_face(self):
        if self.preview is None or self.result is None:
            return
        from lumalock.ai.identity.check import check_faces
        from lumalock.imaging.geometry import transform_image

        original = transform_image(self.preview, self.state.geometry).copy()
        edited = self.result.copy()
        self.run_task(
            lambda cancelled, progress: check_faces(original, edited),
            lambda report: self.assistant.setText(report.describe()),
        )

    def protect_person(self):
        if self.preview is None:
            return
        source = self.preview
        self.run_task(
            lambda cancelled, progress: self.segmentation.create(
                source, "subject", cancelled, progress
            ),
            self.person_ready,
        )

    def person_ready(self, path):
        layer = MaskLayer(
            id=uuid.uuid4().hex,
            name="Person protection",
            kind="subject",
            mask_file=str(path),
            protected=True,
        )
        self.state.masks.append(layer)
        self.active_mask = layer.id
        self.overlay_toggle.setChecked(True)
        self.commit("Protect entire person")
        self.assistant.setText(
            "The highlighted person region is excluded from creative edits. Inspect the outline and add a protection brush for anything missed."
        )

    def reset_adjustments(self):
        if self.document is None:
            return
        layer = self.selected_layer()
        if layer:
            layer.adjustments = Adjustments()
        else:
            self.state.adjustments = Adjustments()
            self.state.hsl = {}
            self.state.curves = {}
        self.recipe_base = None
        self.commit("Reset adjustments")
        self.schedule_render()

    def prompt_edit(self, apply):
        if self.analysis is None:
            return
        if not self.models.installed("prompt"):
            self.setup_models(["prompt"])
            self.assistant.setText("Install the editing director, then preview your prompt again.")
            return
        text = self.prompt.toPlainText().strip()
        state = self.state.model_copy(deep=True)
        analysis = self.analysis
        from lumalock.pipeline.prompt_edit import prepare_prompt

        self.run_task(
            lambda cancelled, progress: prepare_prompt(
                text,
                self.preview,
                analysis,
                state,
                self.models,
                self.segmentation,
                cancelled,
                progress,
            ),
            lambda prepared: self.plan_ready(prepared.plan, text, apply, prepared.state),
        )

    def plan_ready(self, plan, text, apply=False, prepared_state=None):
        self.assistant.setText(plan.explanation)
        if plan.generative.enabled:
            plan.generative.strength = self.ai_strength.value() / 100
            if plan.intent == "content_change" and self.state.mode != "Creative":
                self.error(
                    "This request requires Creative Mode. Select Creative and choose an editable mask."
                )
                return
            self.pending_ai_plan = plan
            self.pending_ai_request = text
            self.pending_plan = None
            if apply:
                self.apply_pending_plan()
            else:
                self.assistant.setText(plan.explanation + " No generation has started.")
            return
        if plan.confidence < 0.4:
            return
        try:
            state = prepared_state or apply_plan(self.state, plan)
        except ValueError as exc:
            self.error(str(exc))
            return
        self.pending_plan = (state, text)
        if apply:
            self.apply_pending_plan()
            return
        self.generation += 1
        self.render_preview(state)
        self.assistant.setText(
            plan.explanation + " Preview shown. Apply to update the sliders and history."
        )

    def apply_pending_plan(self):
        if getattr(self, "pending_ai_plan", None) is not None:
            plan = self.pending_ai_plan
            if self.prompt.toPlainText().strip() != getattr(self, "pending_ai_request", ""):
                self.pending_ai_plan = None
                self.prompt_edit(False)
                return
            if plan.intent == "content_change" and self.state.mode != "Creative":
                self.error("Select Creative AI before generating this scene change.")
                return
            plan.generative.strength = self.ai_strength.value() / 100
            self.pending_ai_plan = None
            self.creative_edit(plan)
            return
        if self.pending_plan is None:
            self.prompt_edit(True)
            return
        self.state, text = self.pending_plan
        self.recipe_base = None
        self.prompts.append(text)
        self.active_mask = None
        self.pending_plan = None
        self.commit(f"Prompt: {text}")
        self.schedule_render()

    def creative_edit(self, plan):
        if not self.models.installed("flux"):
            if not self.settings.flux_license_accepted:
                self.download_model("flux")
            else:
                self.setup_models(["flux"])
            return
        layer = self.selected_layer()
        if plan.intent != "content_change" and (layer is None or layer.protected):
            layer = None
        if plan.intent == "content_change" and layer and layer.protected:
            self.error("This is a protection mask. Select or paint a separate creative edit area.")
            return
        if not layer:
            if plan.intent == "content_change":
                self.error("Select an editable mask before creative editing.")
                return
            from lumalock.project.edit_state import MaskLayer

            layer = MaskLayer(
                id="natural-ai", name="Natural AI", kind="rectangle", geometry=[0, 0, 1, 1]
            )
        from lumalock.pipeline.creative_edit import creative_edit

        document = self.document
        state = self.state.model_copy(deep=True)
        selected = layer.model_copy(deep=True)
        self.run_task(
            lambda cancelled, progress: creative_edit(
                document.pixels, state, selected, plan, self.models, cancelled, progress
            ),
            lambda path: self.creative_ready(path, plan.generative.prompt),
        )

    def creative_ready(self, path, prompt):
        self.state.generated_file = str(path)
        self.prompts.append(prompt)
        self.commit(f"Creative: {prompt}")
        self.schedule_render()

    def save_project_dialog(self):
        if self.document is None:
            return
        self.commit("Manual adjustment")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project", "Untitled.luma", "LumaLock project (*.luma)"
        )
        if path:
            source = self.document.path
            history = self.history.clone()
            prompts = self.prompts.copy()
            self.run_task(
                lambda cancelled, progress: save_project(Path(path), source, history, prompts),
                lambda _: self.status.setText("Project saved"),
            )

    def open_project_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open project", "", "LumaLock project (*.luma)")
        if path:
            self.run_task(
                lambda cancelled, progress: load_project(Path(path)),
                lambda bundle: self.open_image(bundle[0], bundle[1], bundle[2]),
            )

    def geometry_dialog(self):
        if self.document is None:
            return
        from lumalock.ui.dialogs.geometry import GeometryDialog

        dialog = GeometryDialog(self.state.geometry, self.document.size, self)
        if dialog.exec():
            try:
                self.state.geometry = dialog.geometry()
            except ValueError:
                self.error("Crop dimensions must stay inside the image.")
                return
            self.pending_ai_plan = None
            self.recipe_base = None
            self.commit("Crop / geometry")
            self.schedule_render()

    def export_dialog(self):
        if self.document is None:
            return
        from lumalock.imaging.geometry import geometry_size

        dialog = ExportDialog(
            geometry_size(self.document.size, self.state.geometry), self.settings, self
        )
        if not dialog.exec():
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export photograph",
            f"{self.document.path.stem}-LumaLock.jpg",
            "JPEG (*.jpg);;PNG (*.png);;WebP (*.webp);;TIFF (*.tiff)",
        )
        if not path:
            return
        document = self.document
        state = self.state.model_copy(deep=True)
        options = dialog.options()

        def operation(cancelled, progress):
            pixels = render(document.pixels, state, cancelled, progress)
            if cancelled():
                return
            progress(95, "Writing original-resolution export…")
            export_image(document, pixels, path, options)

        self.run_task(operation, lambda _: self.status.setText(f"Exported {Path(path).name}"))

    def settings_dialog(self):
        SettingsDialog(self.settings, self.models, self).exec()
        self.models.settings = self.settings
        self.segmentation.expansion = self.settings.face_expansion
        if self.document:
            self.preview = self.document.preview(self.settings.preview_size)
            self.schedule_render()

    def autosave(self):
        if (
            not self.settings.autosave
            or self.document is None
            or self.task
            or self.render_timer.isActive()
        ):
            return
        directory = data_dir() / "projects"
        directory.mkdir(exist_ok=True)
        source = self.document.path
        history = self.history.clone()
        history.push("Autosaved adjustment", self.state)
        prompts = self.prompts.copy()
        self.run_task(
            lambda cancelled, progress: save_project(
                directory / "autosave.luma", source, history, prompts
            ),
            lambda _: self.status.setText("Project autosaved locally"),
        )

    def download_model(self, key):
        spec = MODEL_SPECS[key]
        reply = QMessageBox.question(
            self,
            "Download optional model",
            f"Download {spec['name']} (~{spec['size_gb']} GB)?\n{spec['license']}\nModel download only; no photograph is uploaded.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            if key == "flux":
                self.settings.flux_license_accepted = True
                from lumalock.core.config import save_settings

                save_settings(self.settings)
                self.models.settings = self.settings
            self.setup_models([key])

    def setup_models(self, keys, verify_only=False):
        from lumalock.ui.dialogs.model_setup import ModelSetupDialog

        if self.setup_dialog and self.setup_dialog.task:
            self.setup_dialog.show()
            self.setup_dialog.raise_()
            return
        self.setup_dialog = ModelSetupDialog(self.models, keys, self, verify_only)
        self.setup_dialog.show()
        self.setup_dialog.start()

    def verify_model(self, key):
        self.setup_models([key], verify_only=True)

    def remove_model(self, key):
        if (
            QMessageBox.question(
                self, "Remove model", f"Remove local {MODEL_SPECS[key]['name']} files?"
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.run_task(
                lambda cancelled, progress: self.models.remove(key),
                lambda _: self.status.setText("Model removed"),
            )

    def system_info(self):
        from lumalock.core.diagnostics import diagnostics

        self.run_task(
            lambda cancelled, progress: diagnostics(self.hardware),
            lambda report: QMessageBox.information(self, "System Information", report),
        )

    def closeEvent(self, event):
        if self.setup_dialog and self.setup_dialog.task:
            self.setup_dialog.pause_download()
            event.ignore()
            QTimer.singleShot(200, self.close)
            return
        self.cancel_task()
        if self.overlay_task:
            self.overlay_task.cancelled.set()
        if self.pool.activeThreadCount():
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        event.accept()
