from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

import app as core
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSettings, QPoint, QThread, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


ROOT = Path(__file__).parent.resolve()

PREVIEW_SUBTITLE_COLORS = {
    "white": "#ffffff",
    "yellow": "#ffe066",
    "cyan": "#63d9ff",
    "red": "#ff6b6b",
    "green": "#73e6a4",
    "pink": "#ff70d1",
}


def valid_hex_color(value: str) -> str | None:
    text = value.strip().upper()
    if len(text) == 7 and text.startswith("#") and all(char in "0123456789ABCDEF" for char in text[1:]):
        return text
    return None


class DraggableSubtitleLabel(QLabel):
    moved = pyqtSignal(float, float)

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._drag_offset is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        parent = self.parentWidget()
        if parent is None:
            return
        position = self.mapToParent(event.position().toPoint() - self._drag_offset)
        x = max(0, min(parent.width() - self.width(), position.x()))
        y = max(0, min(parent.height() - self.height(), position.y()))
        self.move(x, y)
        width = max(1, parent.width() - self.width())
        height = max(1, parent.height() - self.height())
        self.moved.emit(x / width, y / height)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._drag_offset = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)


class ClickOnlyComboBox(QComboBox):
    """Prevent accidental value changes when the page is scrolled over a dropdown."""

    def wheelEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        event.accept()


class FocusOnlySpinBox(QSpinBox):
    """Only let the mouse wheel change a number after the field is focused."""

    def wheelEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.accept()


class ClipPreviewDialog(QDialog):
    def __init__(self, entries: list[dict[str, Any]], index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entries = entries
        self.index = index
        self.setWindowTitle("Preview clip")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        self.title_label = QLabel()
        self.title_label.setObjectName("title_small")
        layout.addWidget(self.title_label)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        frame = QFrame()
        frame.setObjectName("previewCanvas")
        frame_layout = QGridLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        self.video = QVideoWidget()
        self.video.setMinimumSize(520, 360)
        self.player.setVideoOutput(self.video)
        frame_layout.addWidget(self.video, 0, 0)
        layout.addWidget(frame, 1)

        timeline = QHBoxLayout()
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self.seek_preview)
        self.time_label = QLabel("00:00 / 00:00")
        self.player.positionChanged.connect(self.update_preview_position)
        self.player.durationChanged.connect(self.update_preview_duration)
        timeline.addWidget(self.seek_slider, 1)
        timeline.addWidget(self.time_label)
        layout.addLayout(timeline)

        controls = QHBoxLayout()
        self.previous_button = QPushButton("← Sebelumnya")
        self.previous_button.clicked.connect(self.show_previous)
        self.next_button = QPushButton("Berikutnya →")
        self.next_button.clicked.connect(self.show_next)
        close_button = QPushButton("Tutup")
        close_button.clicked.connect(self.close)
        controls.addWidget(self.previous_button)
        controls.addWidget(self.next_button)
        controls.addStretch()
        controls.addWidget(close_button)
        layout.addLayout(controls)
        self.load_current()

    def load_current(self) -> None:
        if not self.entries:
            return
        entry = self.entries[self.index]
        self.title_label.setText(f"{self.index + 1}/{len(self.entries)} · {entry['title']}")
        self.previous_button.setEnabled(self.index > 0)
        self.next_button.setEnabled(self.index < len(self.entries) - 1)
        path = Path(entry["path"])
        if path.is_file():
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.play()

    def show_previous(self) -> None:
        if self.index <= 0:
            return
        self.index -= 1
        self.load_current()

    def show_next(self) -> None:
        if self.index >= len(self.entries) - 1:
            return
        self.index += 1
        self.load_current()

    def seek_preview(self, position: int) -> None:
        self.player.setPosition(position)

    def update_preview_position(self, position: int) -> None:
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)
        self.time_label.setText(
            f"{format_time(position / 1000)} / {format_time(self.player.duration() / 1000)}"
        )

    def update_preview_duration(self, duration: int) -> None:
        self.seek_slider.setRange(0, max(0, duration))
        self.seek_slider.setEnabled(duration > 0)
        self.time_label.setText(
            f"{format_time(self.player.position() / 1000)} / {format_time(duration / 1000)}"
        )

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.player.stop()
        self.player.setSource(QUrl())
        self.audio.setMuted(True)
        super().closeEvent(event)


def parse_time(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        if ":" not in text:
            return float(text)
        parts = [float(part) for part in text.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except ValueError:
        return None
    return None


def format_time(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"


class DownloadWorker(QThread):
    finished_download = pyqtSignal()

    def __init__(self, job_id: str, url: str, quality: str) -> None:
        super().__init__()
        self.job_id = job_id
        self.url = url
        self.quality = quality

    def run(self) -> None:
        try:
            core.download_raw_job(self.job_id, self.url, self.quality)
        except Exception as exc:
            core.update_job(self.job_id, status="failed", progress=100, message="Download gagal", error=str(exc))
        self.finished_download.emit()


class JobWorker(QThread):
    finished_job = pyqtSignal()

    def __init__(self, job_id: str, options: core.CreateJobRequest, render: bool = False, source_path: str | None = None) -> None:
        super().__init__()
        self.job_id = job_id
        self.options = options
        self.render = render
        self.source_path = source_path

    def run(self) -> None:
        if self.render:
            core.render_job(self.job_id, self.options)
        else:
            core.process_job(self.job_id, self.options, self.source_path)
        self.finished_job.emit()


class MetadataWorker(QThread):
    finished_metadata = pyqtSignal()

    def __init__(self, transcript: list[dict[str, Any]], clip: core.Clip, model_name: str) -> None:
        super().__init__()
        self.transcript = transcript
        self.clip = clip
        self.model_name = model_name

    def run(self) -> None:
        core.generate_clip_metadata(self.transcript, [self.clip], self.model_name)
        self.finished_metadata.emit()


class ManualRenderWorker(QThread):
    finished_render = pyqtSignal()

    def __init__(self, job_id: str, clip: core.Clip, options: core.CreateJobRequest) -> None:
        super().__init__()
        self.job_id = job_id
        self.clip = clip
        self.options = options

    def run(self) -> None:
        try:
            with core.JOBS_LOCK:
                job = core.JOBS[self.job_id]
                video = Path(job.source_path)
                transcript = list(job.transcript)
            core.render_selected_clips(
                self.job_id,
                video,
                transcript,
                [self.clip],
                core.job_result_dir(self.job_id),
                self.options,
                progress_start=70,
                progress_end=70,
            )
        except Exception as exc:
            core.update_job(self.job_id, error=str(exc), message="Render clip manual gagal")
        self.finished_render.emit()


class HermesDesktop(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VanClipper")
        self.resize(1240, 820)
        self.current_job_id: str | None = None
        self.current_options: core.CreateJobRequest | None = None
        self.worker: JobWorker | None = None
        self.metadata_worker: MetadataWorker | None = None
        self.manual_render_worker: ManualRenderWorker | None = None
        self.page_animation: QPropertyAnimation | None = None
        self.auto_preview_items: list[dict[str, Any]] = []
        self.review_entries: list[dict[str, Any]] = []
        self.clip_preview_dialog: ClipPreviewDialog | None = None
        self.auto_preview_index = 0
        self.auto_preview_running = False
        self.model_path_edits: dict[str, QLineEdit] = {}
        self.active_model_key = "qwen"
        self.source_duration = 0.0
        self.active_transcript: list[dict[str, Any]] = []
        self.subtitle_free_x = 0.15
        self.subtitle_free_y = 0.78

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.create_tab = self.build_create_tab()
        self.video_tab = self.build_video_tab()
        self.review_tab = self.build_review_tab()
        self.results_tab = self.build_results_tab()
        self.tutorial_tab = self.build_tutorial_tab()
        self.tabs.addTab(self.video_tab, "Video")
        self.tabs.addTab(self.create_tab, "Buat clip")
        self.tabs.addTab(self.review_tab, "Review & manual")
        self.tabs.addTab(self.results_tab, "Hasil")
        self.tabs.addTab(self.tutorial_tab, "Cara kerja")
        self.tabs.setTabEnabled(2, False)
        self.tabs.setTabEnabled(3, False)
        self.tabs.tabBar().hide()
        self.nav_buttons: dict[int, QPushButton] = {}

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.clicked.connect(self.toggle_theme)
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setObjectName("topToolbar")
        brand = QLabel("VanClipper")
        brand.setObjectName("brand")
        toolbar.addWidget(brand)
        meta = QLabel("Local video workspace")
        meta.setObjectName("brandMeta")
        toolbar.addWidget(meta)
        for index, label in ((0, "Video"), (1, "Buat clip"), (2, "Review"), (3, "Hasil")):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, target=index: self.switch_tab(target))
            self.nav_buttons[index] = button
            toolbar.addWidget(button)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        guide_button = QPushButton("Cara kerja")
        guide_button.setObjectName("navButton")
        guide_button.setCheckable(True)
        guide_button.clicked.connect(lambda checked=False: self.switch_tab(4))
        self.nav_buttons[4] = guide_button
        toolbar.addWidget(guide_button)
        toolbar.addWidget(self.theme_button)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_job)
        saved_theme = QSettings("VanClipper", "VanClipper").value("theme", "dark")
        self.apply_theme(str(saved_theme) == "light")
        self.switch_tab(0)

    def build_create_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        page = QWidget()
        page.setObjectName("pageContent")
        page.setMinimumWidth(860)
        page.setMaximumWidth(1320)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        hero = QHBoxLayout()
        hero.setSpacing(24)
        hero_copy = QVBoxLayout()
        eyebrow = QLabel("VANCLIPPER  /  WORKSPACE")
        eyebrow.setObjectName("eyebrow")
        hero_copy.addWidget(eyebrow)
        header = QLabel("Buat clip dari satu video")
        header.setObjectName("title")
        hero_copy.addWidget(header)
        intro = QLabel("Pilih sumber, tentukan cara potong, lalu review hasilnya sebelum render final.")
        intro.setObjectName("muted")
        hero_copy.addWidget(intro)
        hero.addLayout(hero_copy)
        hero.addStretch()
        workflow_note = QLabel("LOCAL WORKFLOW\nDOWNLOAD  ·  EDIT  ·  EXPORT")
        workflow_note.setObjectName("workflowNote")
        workflow_note.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hero.addWidget(workflow_note)
        layout.addLayout(hero)

        source_group = QGroupBox("Sumber")
        source_form = QFormLayout(source_group)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        source_form.addRow("Link video", self.url_edit)
        self.quality_combo = self.combo([
            ("360p · hemat ukuran", "360"),
            ("480p", "480"),
            ("720p · HD", "720"),
            ("1080p · Full HD", "1080"),
            ("Terbaik hingga 2160p", "best"),
        ], 3)
        source_form.addRow("Kualitas unduhan", self.quality_combo)
        source_buttons = QHBoxLayout()
        self.download_button = QPushButton("Unduh video")
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(self.start_download)
        self.local_file_button = QPushButton("Pilih file video")
        self.local_file_button.clicked.connect(self.choose_local_video)
        source_buttons.addWidget(self.download_button)
        source_buttons.addWidget(self.local_file_button)
        source_buttons.addStretch()
        source_form.addRow("Sumber", source_buttons)
        support = QLabel("Link yang didukung mengikuti yt-dlp, termasuk YouTube, Vimeo, TikTok, Instagram, Facebook, X, dan banyak situs lain. File lokal: MP4, MOV, MKV, WEBM, AVI, M4V.")
        support.setObjectName("muted")
        support.setWordWrap(True)
        source_form.addRow("Info", support)
        self.source_status = QLabel("Belum ada video sumber")
        self.source_status.setObjectName("status")
        source_form.addRow("Status", self.source_status)
        layout.addWidget(source_group)
        self.source_group = source_group
        self.create_content_layout = layout

        settings = QGroupBox("Output")
        grid = QGridLayout(settings)
        self.mode_combo = self.combo([("Highlight otomatis", "smart"), ("Bagi berdasarkan jumlah", "split_count"), ("Bagi berdasarkan durasi", "split_duration")])
        self.profile_combo = self.combo([
            ("Otomatis · deteksi jenis video", "auto"),
            ("Live / Streamer", "live"),
            ("Konten biasa", "standard"),
            ("Manual + Review", "manual"),
        ])
        self.language_combo = self.combo([
            ("Indonesia", "id"), ("English", "en"), ("Melayu", "ms"), ("日本語", "ja"),
            ("中文", "zh"), ("한국어", "ko"), ("Español", "es"), ("Deutsch", "de"),
            ("Français", "fr"), ("Português", "pt"), ("العربية", "ar"),
        ])
        self.aspect_combo = self.combo([
            ("9:16 · Shorts / Reels", "9:16"),
            ("16:9 · Landscape", "16:9"),
            ("4:3 · Classic", "4:3"),
            ("1:1 · Square", "1:1"),
        ])
        self.framing_combo = self.combo([("Full video · background blur", "fit"), ("Crop memenuhi frame", "crop")])
        self.layout_combo = self.combo([("Standard", "standard"), ("Facecam di atas", "facecam_top")])
        self.subtitle_combo = self.combo([
            ("Bold", "bold"),
            ("Highlight", "highlight"),
            ("Classic", "classic"),
            ("Minimal", "minimal"),
            ("Neon", "neon"),
            ("Karaoke", "karaoke"),
            ("Box", "box"),
            ("Tanpa subtitle", "none"),
        ])
        self.subtitle_enabled = QCheckBox("Gunakan subtitle")
        self.subtitle_enabled.setChecked(True)
        self.use_llm = QCheckBox("Gunakan model lokal")
        self.use_llm.setChecked(True)

        fields = [
            ("Mode clip", self.mode_combo), ("Profil momen", self.profile_combo), ("Format output", self.aspect_combo),
            ("Framing", self.framing_combo), ("Layout", self.layout_combo),
        ]
        for index, (label, widget) in enumerate(fields):
            grid.addWidget(QLabel(label), index // 3 * 2, index % 3)
            grid.addWidget(widget, index // 3 * 2 + 1, index % 3)
        self.mode_combo.currentIndexChanged.connect(self.update_mode_settings)
        self.profile_combo.currentIndexChanged.connect(self.update_profile_hint)
        self.subtitle_enabled.toggled.connect(self.update_subtitle_controls)
        self.profile_hint = QLabel()
        self.profile_hint.setObjectName("muted")
        self.profile_hint.setWordWrap(True)
        grid.addWidget(self.profile_hint, 4, 0, 1, 3)
        self.update_profile_hint()

        subtitle_group = QGroupBox("Subtitle")
        subtitle_grid = QGridLayout(subtitle_group)
        subtitle_grid.addWidget(self.subtitle_enabled, 0, 0, 1, 3)
        subtitle_grid.addWidget(QLabel("Bahasa"), 1, 0)
        subtitle_grid.addWidget(self.language_combo, 1, 1, 1, 2)
        subtitle_grid.addWidget(QLabel("Gaya"), 2, 0)
        subtitle_grid.addWidget(self.subtitle_combo, 2, 1, 1, 2)
        self.subtitle_position_combo = self.combo([
            ("Otomatis · aman", "auto"),
            ("Bawah", "bottom"),
            ("Tengah", "center"),
            ("Atas", "top"),
            ("Bebas · geser di preview", "free"),
        ])
        subtitle_grid.addWidget(QLabel("Posisi"), 3, 0)
        subtitle_grid.addWidget(self.subtitle_position_combo, 3, 1, 1, 2)
        self.subtitle_color_combo = self.combo([
            ("Otomatis sesuai gaya", "auto"),
            ("Putih", "white"),
            ("Kuning", "yellow"),
            ("Cyan", "cyan"),
            ("Merah", "red"),
            ("Hijau", "green"),
            ("Pink", "pink"),
            ("Kustom · kode HEX", "custom"),
        ])
        subtitle_grid.addWidget(QLabel("Warna"), 4, 0)
        subtitle_grid.addWidget(self.subtitle_color_combo, 4, 1, 1, 2)
        custom_color_row = QHBoxLayout()
        self.subtitle_color_button = QPushButton()
        self.subtitle_color_button.setObjectName("colorSwatch")
        self.subtitle_color_button.setFixedSize(30, 30)
        self.subtitle_color_button.setToolTip("Klik untuk memilih warna subtitle")
        self.subtitle_color_button.clicked.connect(self.choose_subtitle_color)
        self.subtitle_color_hex = QLineEdit("#FFFFFF")
        self.subtitle_color_hex.setPlaceholderText("#RRGGBB")
        self.subtitle_color_hex.setMaximumWidth(150)
        self.subtitle_color_hex.editingFinished.connect(self.apply_custom_subtitle_hex)
        custom_color_row.addWidget(self.subtitle_color_button)
        custom_color_row.addWidget(self.subtitle_color_hex)
        custom_color_row.addWidget(QLabel("Klik bulatan atau masukkan kode HEX"))
        custom_color_row.addStretch()
        subtitle_grid.addWidget(QLabel("Kustom"), 5, 0)
        subtitle_grid.addLayout(custom_color_row, 5, 1, 1, 2)
        self.subtitle_color_combo.currentIndexChanged.connect(self.update_subtitle_color_chip)
        self.update_subtitle_color_chip()
        self.update_subtitle_controls()
        output_subtitle_row = QHBoxLayout()
        output_subtitle_row.setSpacing(12)
        output_subtitle_row.addWidget(settings, 1)
        output_subtitle_row.addWidget(subtitle_group, 1)
        layout.addLayout(output_subtitle_row)

        preview_group = QGroupBox("Preview sebelum proses")
        preview_layout = QVBoxLayout(preview_group)
        self.create_preview_player = QMediaPlayer(self)
        self.create_preview_audio = QAudioOutput(self)
        self.create_preview_player.setAudioOutput(self.create_preview_audio)
        preview_frame = QFrame()
        self.create_preview_frame = preview_frame
        preview_frame.setObjectName("previewCanvas")
        preview_stack = QGridLayout(preview_frame)
        self.create_preview_stack = preview_stack
        preview_stack.setContentsMargins(0, 0, 0, 0)
        self.create_preview_video = QVideoWidget()
        self.create_preview_video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        preview_stack.addWidget(self.create_preview_video, 0, 0)
        self.preview_layout_overlay = QLabel("")
        self.preview_layout_overlay.setObjectName("previewBadge")
        self.preview_layout_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_stack.addWidget(self.preview_layout_overlay, 0, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.preview_facecam_top = QLabel("FACECAM")
        self.preview_facecam_top.setObjectName("previewGuide")
        self.preview_facecam_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_facecam_top.setVisible(False)
        preview_stack.addWidget(self.preview_facecam_top, 0, 0, Qt.AlignmentFlag.AlignTop)
        self.preview_facecam_main = QLabel("VIDEO UTAMA")
        self.preview_facecam_main.setObjectName("previewGuide")
        self.preview_facecam_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_facecam_main.setVisible(False)
        preview_stack.addWidget(self.preview_facecam_main, 0, 0, Qt.AlignmentFlag.AlignBottom)
        self.preview_subtitle_sample = DraggableSubtitleLabel("Contoh subtitle akan tampil di sini")
        self.preview_subtitle_sample.setObjectName("previewSubtitle")
        self.preview_subtitle_sample.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_subtitle_sample.moved.connect(self.on_free_subtitle_moved)
        preview_stack.addWidget(self.preview_subtitle_sample, 0, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.create_preview_player.setVideoOutput(self.create_preview_video)
        preview_row = QHBoxLayout()
        preview_row.addStretch()
        preview_row.addWidget(preview_frame)
        preview_row.addStretch()
        preview_layout.addLayout(preview_row)
        self.create_preview_play = QPushButton("Play / Pause video sumber")
        self.create_preview_play.clicked.connect(self.toggle_create_preview)
        preview_layout.addWidget(self.create_preview_play, alignment=Qt.AlignmentFlag.AlignLeft)
        preview_timeline = QHBoxLayout()
        self.create_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.create_seek_slider.setRange(0, 0)
        self.create_seek_slider.setEnabled(False)
        self.create_seek_slider.sliderMoved.connect(self.seek_create_preview)
        self.create_preview_time = QLabel("00:00 / 00:00")
        self.create_preview_player.positionChanged.connect(self.update_create_seek)
        self.create_preview_player.durationChanged.connect(self.update_create_duration)
        preview_timeline.addWidget(self.create_seek_slider, 1)
        preview_timeline.addWidget(self.create_preview_time)
        preview_layout.addLayout(preview_timeline)
        self.preview_layout_badge = QLabel("Preview format output")
        self.preview_layout_badge.setObjectName("previewBadge")
        preview_layout.addWidget(self.preview_layout_badge)
        self.preview_summary = QLabel("Pilih format output dan gaya subtitle untuk melihat ringkasannya.")
        self.preview_summary.setObjectName("muted")
        preview_layout.addWidget(self.preview_summary)
        for control in (self.aspect_combo, self.framing_combo, self.layout_combo, self.subtitle_combo, self.language_combo, self.subtitle_enabled, self.subtitle_position_combo, self.subtitle_color_combo):
            if isinstance(control, QCheckBox):
                control.toggled.connect(self.update_create_preview)
            else:
                control.currentIndexChanged.connect(self.update_create_preview)
        self.update_create_preview()
        layout.addWidget(preview_group)

        mode_settings = QGroupBox("Pengaturan segmen")
        mode_layout = QVBoxLayout(mode_settings)
        self.mode_stack = QStackedWidget()
        self.mode_stack.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        smart_page = QWidget()
        smart_grid = QGridLayout(smart_page)
        smart_grid.setColumnStretch(5, 1)
        self.clip_count = self.spin(0, 200, 0)
        self.max_clips = self.spin(1, 200, 10)
        self.smart_duration_mode = self.combo([("Otomatis mengikuti momen", "auto"), ("Durasi tetap", "fixed")])
        self.smart_fixed_duration = self.spin(5, 3600, 60)
        self.min_duration = self.spin(0, 3600, 0)
        self.max_duration = self.spin(0, 3600, 0)
        for control in (self.clip_count, self.max_clips, self.smart_duration_mode, self.smart_fixed_duration, self.min_duration, self.max_duration):
            control.setMaximumWidth(260)
        smart_grid.addWidget(QLabel("Jumlah clip (0 = otomatis)"), 0, 0)
        smart_grid.addWidget(self.clip_count, 0, 1)
        smart_grid.addWidget(QLabel("Maksimal clip otomatis"), 0, 2)
        smart_grid.addWidget(self.max_clips, 0, 3)
        smart_grid.addWidget(QLabel("Durasi clip"), 1, 0)
        smart_grid.addWidget(self.smart_duration_mode, 1, 1)
        self.smart_fixed_row = QWidget()
        fixed_row = QHBoxLayout(self.smart_fixed_row)
        fixed_row.setContentsMargins(0, 0, 0, 0)
        fixed_row.addWidget(self.smart_fixed_duration)
        fixed_row.addWidget(QLabel("detik per clip"))
        smart_grid.addWidget(QLabel("Durasi tetap"), 1, 2)
        smart_grid.addWidget(self.smart_fixed_row, 1, 3)
        self.smart_range_row = QWidget()
        range_row = QHBoxLayout(self.smart_range_row)
        range_row.setContentsMargins(0, 0, 0, 0)
        range_row.addWidget(self.min_duration)
        range_row.addWidget(QLabel("sampai"))
        range_row.addWidget(self.max_duration)
        range_row.addWidget(QLabel("detik"))
        smart_grid.addWidget(QLabel("Rentang durasi (0 = otomatis)"), 2, 0)
        smart_grid.addWidget(self.smart_range_row, 2, 1, 1, 3)
        smart_hint = QLabel("Default otomatis mengikuti durasi alami adegan. Isi minimum/maksimum jika ingin membatasi durasi.")
        smart_hint.setObjectName("muted")
        smart_grid.addWidget(smart_hint, 3, 0, 1, 6)
        self.mode_stack.addWidget(smart_page)

        count_page = QWidget()
        count_form = QFormLayout(count_page)
        count_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.split_count = self.spin(1, 500, 10)
        self.split_count.setMaximumWidth(280)
        count_form.addRow("Jumlah bagian", self.split_count)
        count_hint = QLabel("Video akan dibagi rata menjadi jumlah bagian yang dipilih.")
        count_hint.setObjectName("muted")
        count_form.addRow("", count_hint)
        self.mode_stack.addWidget(count_page)

        duration_page = QWidget()
        duration_form = QFormLayout(duration_page)
        duration_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.segment_duration = self.spin(5, 3600, 120)
        self.segment_duration.setMaximumWidth(280)
        duration_form.addRow("Durasi setiap clip", self.segment_duration)
        duration_hint = QLabel("Video akan dipotong berurutan sampai selesai, misalnya 120 detik per clip.")
        duration_hint.setObjectName("muted")
        duration_form.addRow("", duration_hint)
        self.mode_stack.addWidget(duration_page)
        mode_layout.addWidget(self.mode_stack)
        self.duration_info = QLabel("Durasi sumber: belum diketahui")
        self.duration_info.setObjectName("status")
        self.segment_estimate = QLabel("Estimasi pembagian akan tampil setelah video siap.")
        self.segment_estimate.setObjectName("muted")
        self.segment_estimate.setWordWrap(True)
        mode_layout.addWidget(self.duration_info)
        mode_layout.addWidget(self.segment_estimate)
        layout.addWidget(mode_settings)
        self.smart_duration_mode.currentIndexChanged.connect(self.update_smart_duration_fields)
        self.mode_combo.currentIndexChanged.connect(self.update_segment_estimate)
        self.clip_count.valueChanged.connect(self.update_segment_estimate)
        self.max_clips.valueChanged.connect(self.update_segment_estimate)
        self.smart_duration_mode.currentIndexChanged.connect(self.update_segment_estimate)
        self.smart_fixed_duration.valueChanged.connect(self.update_segment_estimate)
        self.min_duration.valueChanged.connect(self.update_segment_estimate)
        self.max_duration.valueChanged.connect(self.update_segment_estimate)
        self.split_count.valueChanged.connect(self.update_segment_estimate)
        self.segment_duration.valueChanged.connect(self.update_segment_estimate)
        self.update_mode_settings()
        self.update_smart_duration_fields()
        self.update_segment_estimate()

        model_group = QGroupBox("Model lokal (.gguf)")
        model_grid = QGridLayout(model_group)
        model_grid.addWidget(QLabel("Model aktif"), 0, 0)
        self.model_file_combo = ClickOnlyComboBox()
        self.model_file_combo.setMinimumHeight(34)
        self.model_file_combo.setPlaceholderText("Belum ada model — pilih folder .gguf")
        self.model_file_combo.setToolTip("Pilih file GGUF yang ingin digunakan")
        self.model_file_combo.currentIndexChanged.connect(self.on_model_file_changed)
        model_grid.addWidget(self.model_file_combo, 0, 1)
        self.model_folder_button = QPushButton("Pilih folder model")
        self.model_folder_button.clicked.connect(self.pick_model_folder)
        model_grid.addWidget(self.model_folder_button, 0, 2)

        self.model_path_edits["qwen"] = QLineEdit()
        self.model_path_edits["qwen"].setReadOnly(True)
        self.model_path_edits["qwen"].setVisible(False)
        self.model_path_edits["qwen"].setPlaceholderText("Belum dipilih — pilih file .gguf")

        self.model_path_edits["hermes"] = QLineEdit()
        self.model_path_edits["hermes"].setReadOnly(True)
        self.model_path_edits["hermes"].setVisible(False)
        self.model_path_edits["hermes"].setPlaceholderText("Belum dipilih — pilih file .gguf")

        model_hint = QLabel("Pilih satu folder yang berisi beberapa file .gguf. VanClipper akan mencari Qwen/Hermes secara otomatis.")
        model_hint.setObjectName("muted")
        model_grid.addWidget(model_hint, 1, 0, 1, 3)
        model_grid.addWidget(self.use_llm, 2, 0, 1, 3)
        layout.addWidget(model_group)
        self.load_model_paths()
        self.refresh_model_file_choices()

        self.start_button = QPushButton("Mulai analisis")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start_process)
        layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.status_label = QLabel("Menunggu link video")
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)
        layout.addStretch()
        self.clip_stage_widgets = [settings, subtitle_group, preview_group, mode_settings, model_group, self.start_button]
        for widget in self.clip_stage_widgets:
            widget.setVisible(False)
        self.progress.setVisible(False)
        self.status_label.setVisible(False)
        scroll.setWidget(page)
        return scroll

    def build_video_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        page = QWidget()
        page.setMinimumWidth(860)
        page.setMaximumWidth(1320)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        eyebrow = QLabel("VANCLIPPER  /  VIDEO")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("Masukkan video")
        title.setObjectName("title")
        layout.addWidget(title)
        intro = QLabel("Unduh video atau pilih file dari komputer. Setelah siap, lanjut ke Buat clip.")
        intro.setObjectName("muted")
        layout.addWidget(intro)
        self.create_content_layout.removeWidget(self.source_group)
        self.source_group.setParent(page)
        layout.addWidget(self.source_group)
        library_group = QGroupBox("VideoMentah · pilih video lama")
        library_layout = QVBoxLayout(library_group)
        library_header = QHBoxLayout()
        library_hint = QLabel("Pilih video yang sudah tersimpan untuk membuat clip ulang tanpa download lagi.")
        library_hint.setObjectName("muted")
        library_hint.setWordWrap(True)
        library_header.addWidget(library_hint, 1)
        refresh_button = QPushButton("Muat ulang daftar")
        refresh_button.clicked.connect(self.refresh_raw_video_list)
        open_folder_button = QPushButton("Buka folder VideoMentah")
        open_folder_button.clicked.connect(self.open_raw_video_folder)
        library_header.addWidget(refresh_button)
        library_header.addWidget(open_folder_button)
        library_layout.addLayout(library_header)
        self.raw_video_list = QListWidget()
        self.raw_video_list.setMinimumHeight(150)
        self.raw_video_list.setMaximumHeight(280)
        self.raw_video_list.itemDoubleClicked.connect(lambda item: self.use_selected_raw_video())
        library_layout.addWidget(self.raw_video_list)
        self.use_raw_video_button = QPushButton("Gunakan video terpilih untuk clip ulang")
        self.use_raw_video_button.setObjectName("primary")
        self.use_raw_video_button.setEnabled(False)
        self.use_raw_video_button.clicked.connect(self.use_selected_raw_video)
        library_layout.addWidget(self.use_raw_video_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.raw_video_status = QLabel("Belum ada video tersimpan.")
        self.raw_video_status.setObjectName("muted")
        library_layout.addWidget(self.raw_video_status)
        self.raw_video_list.itemSelectionChanged.connect(
            lambda: self.use_raw_video_button.setEnabled(bool(self.raw_video_list.selectedItems()))
        )
        layout.addWidget(library_group)
        self.refresh_raw_video_list()
        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def refresh_raw_video_list(self) -> None:
        if not hasattr(self, "raw_video_list"):
            return
        self.raw_video_list.clear()
        root = core.RAW_VIDEO_DIR
        entries: list[tuple[float, str, Path]] = []
        if root.exists():
            for folder in root.iterdir():
                if not folder.is_dir():
                    continue
                candidates = [
                    item for item in folder.glob("source.*")
                    if item.suffix.lower() not in {".part", ".ytdl"} and item.is_file()
                ]
                if not candidates:
                    continue
                video = max(candidates, key=lambda item: item.stat().st_mtime)
                title = folder.name
                manifest = folder / "video.json"
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    title = str(data.get("title") or title)
                except (OSError, ValueError, TypeError):
                    pass
                entries.append((video.stat().st_mtime, title, video))
        for _, title, video in sorted(entries, reverse=True):
            item = QListWidgetItem(f"{title}\n{video.name} · {core.format_bytes(video.stat().st_size)}")
            item.setToolTip(str(video))
            item.setData(Qt.ItemDataRole.UserRole, str(video))
            item.setData(Qt.ItemDataRole.UserRole + 1, title)
            self.raw_video_list.addItem(item)
        count = len(entries)
        self.raw_video_status.setText(
            f"{count} video tersimpan di VideoMentah." if count else "Belum ada video tersimpan di VideoMentah."
        )

    def open_raw_video_folder(self) -> None:
        core.RAW_VIDEO_DIR.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(core.RAW_VIDEO_DIR)))

    def use_selected_raw_video(self) -> None:
        item = self.raw_video_list.currentItem()
        if item is None:
            return
        path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        title = str(item.data(Qt.ItemDataRole.UserRole + 1) or path.stem)
        if not path.is_file():
            QMessageBox.warning(self, "Video tidak ditemukan", "File video tersebut sudah dipindahkan atau dihapus.")
            self.refresh_raw_video_list()
            return
        self.current_job_id = uuid.uuid4().hex[:12]
        with core.JOBS_LOCK:
            core.JOBS[self.current_job_id] = core.Job(
                id=self.current_job_id,
                url=str(path),
                status="downloaded",
                progress=100,
                message=f"Video lama siap digunakan · {title}",
                source_path=str(path),
                source_url=f"/raw/{path.parent.name}/{path.name}",
                source_title=title,
            )
        self.url_edit.setText(str(path))
        self.show_clip_stage(str(path), f"Video lama siap digunakan · {title}")

    def build_tutorial_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        eyebrow = QLabel("CARA KERJA  /  WORKFLOW")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("Cara kerja VanClipper")
        title.setObjectName("title")
        layout.addWidget(title)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setHtml("""
        <h2>Alur kerja</h2>
        <ol>
          <li>Buka tab <b>Video</b>, tempel link atau pilih file lokal, lalu unduh/muat video. Video yang sudah pernah disimpan juga muncul di daftar <b>VideoMentah</b> untuk clip ulang.</li>
          <li>VanClipper otomatis berpindah ke tab <b>Buat clip</b> setelah video siap.</li>
          <li>Pilih cara pembagian, profil momen, subtitle, format output, dan model lokal.</li>
          <li>Periksa estimasi durasi serta preview sebelum menekan <b>Mulai analisis</b>. Batas rasio 16:9, 4:3, 1:1, dan 9:16 ditampilkan di semua preview.</li>
          <li>Setelah transkripsi dan clip AI selesai, aplikasi berpindah ke <b>Review</b>.</li>
          <li>Tekan <b>Mulai preview clip AI</b> untuk memutar semua clip otomatis satu per satu.</li>
          <li>Tonton video penuh, tambah clip manual bila perlu, lalu tekan <b>Render final</b>.</li>
        </ol>

        <h2>Profil momen AI</h2>
        <p><b>Otomatis:</b> AI mengenali apakah isi video lebih mirip live streamer atau konten terstruktur.</p>
        <p><b>Live / Streamer:</b> mencari blunder, reaksi spontan, kelucuan, emosi, clutch, konflik, dan interaksi penonton.</p>
        <p><b>Konten biasa:</b> mencari hook, tips, insight, opini, cerita, penjelasan, dan kesimpulan yang kuat.</p>
        <p><b>Manual + Review:</b> transkripsi tetap dibuat, tetapi tidak membuat clip AI. Pilih sendiri bagian video dari tab Review.</p>

        <h2>Parameter penilaian otomatis</h2>
        <ul>
          <li><b>Hook:</b> kekuatan beberapa detik pertama.</li>
          <li><b>Emosi:</b> tawa, kejutan, kemarahan, ketegangan, atau reaksi kuat.</li>
          <li><b>Rasa penasaran:</b> membuat penonton ingin mengetahui kelanjutannya.</li>
          <li><b>Payoff:</b> momen memiliki jawaban, hasil, atau punchline yang jelas.</li>
          <li><b>Kejelasan:</b> clip tetap bisa dipahami tanpa seluruh video.</li>
          <li><b>Pacing:</b> minim jeda kosong dan tidak terlalu lambat.</li>
          <li><b>Penalti:</b> konteks menggantung, pengulangan, jeda panjang, atau akhir yang terpotong.</li>
        </ul>
        <p>Skor AI adalah perkiraan kualitas momen, bukan jaminan viral. Topik, audiens, judul, thumbnail, dan platform tetap berpengaruh.</p>

        <h2>Cara pembagian clip</h2>
        <p><b>Highlight otomatis:</b> memilih momen berdasarkan transkrip, jeda, kata penting, emosi, dan profil momen.</p>
        <p><b>Bagi berdasarkan jumlah:</b> video dibagi rata sesuai jumlah bagian, tanpa penilaian viral.</p>
        <p><b>Bagi berdasarkan durasi:</b> video dipotong berurutan sesuai durasi per clip; bagian terakhir bisa lebih pendek.</p>

        <h2>Subtitle dan tampilan</h2>
        <ul>
          <li>Gaya: Bold, Highlight, Classic, Minimal, Neon, Karaoke, dan Box.</li>
          <li>Warna: preset atau kode HEX kustom seperti <code>#FF8800</code>.</li>
          <li>Posisi: otomatis, atas, tengah, bawah, atau bebas dengan cara menyeret subtitle di preview.</li>
          <li>Subtitle realtime tersedia di tab Review setelah transkripsi selesai.</li>
          <li>Framing <b>Full video · background blur</b> lebih aman untuk mengubah video vertikal menjadi 16:9.</li>
        </ul>

        <h2>Model dan proses lokal</h2>
        <p>Whisper membuat transkrip dan timestamp. Qwen/Hermes membantu memilih momen serta membuat judul, caption, dan hashtag. Jika model tidak menghasilkan jawaban valid, aplikasi memakai fallback berbasis aturan teks.</p>
        <p>File video mentah tersimpan di <code>VideoMentah</code>. Hasil proses tersimpan rapi di <code>HasilClip/Nama Video/clip-01 - Judul Clip</code>, dan model GGUF tidak perlu dimasukkan ke GitHub.</p>

        <h2>Jika proses gagal</h2>
        <ul>
          <li>Pastikan FFmpeg tersedia dan video memiliki audio.</li>
          <li>Pastikan file model GGUF sudah dipilih di dropdown.</li>
          <li>Jika tidak menemukan clip, turunkan durasi minimum atau gunakan profil yang sesuai.</li>
          <li>Untuk video tanpa ucapan, mode pembagian berdasarkan jumlah/durasi lebih cocok daripada Highlight otomatis.</li>
        </ul>
        """)
        layout.addWidget(content)
        return page

    def update_mode_settings(self) -> None:
        if not hasattr(self, "mode_stack"):
            return
        mode = self.mode_combo.currentData()
        self.mode_stack.setCurrentIndex({"smart": 0, "split_count": 1, "split_duration": 2}.get(mode, 0))
        self.resize_mode_stack()
        self.update_segment_estimate()

    def update_profile_hint(self) -> None:
        if not hasattr(self, "profile_hint"):
            return
        hints = {
            "auto": "AI mendeteksi apakah video lebih cocok dinilai sebagai live atau konten terstruktur.",
            "live": "Fokus pada blunder, reaksi spontan, emosi, kelucuan, clutch, konflik, dan interaksi penonton.",
            "standard": "Fokus pada hook, tips, insight, opini, cerita, penjelasan, dan kesimpulan yang kuat.",
            "manual": "Transkripsi tetap dibuat, tetapi clip dipilih sendiri melalui tab Review & manual.",
        }
        self.profile_hint.setText(hints.get(self.profile_combo.currentData(), hints["auto"]))

    def update_smart_duration_fields(self) -> None:
        if not hasattr(self, "smart_duration_mode"):
            return
        fixed = self.smart_duration_mode.currentData() == "fixed"
        self.smart_fixed_row.setVisible(fixed)
        self.smart_range_row.setVisible(not fixed)
        self.resize_mode_stack()

    def resize_mode_stack(self) -> None:
        if not hasattr(self, "mode_stack"):
            return
        current = self.mode_stack.currentWidget()
        if current is None:
            return
        current.adjustSize()
        self.mode_stack.setFixedHeight(max(70, current.sizeHint().height()))

    def update_subtitle_controls(self) -> None:
        enabled = self.subtitle_enabled.isChecked()
        self.language_combo.setEnabled(enabled)
        self.subtitle_combo.setEnabled(enabled)
        self.subtitle_position_combo.setEnabled(enabled)
        self.subtitle_color_combo.setEnabled(enabled)
        self.subtitle_color_button.setEnabled(enabled)
        self.subtitle_color_hex.setEnabled(enabled)
        self.update_create_preview()

    def selected_subtitle_color(self) -> str:
        selected = self.subtitle_color_combo.currentData()
        if selected == "custom":
            return valid_hex_color(self.subtitle_color_hex.text()) or "#FFFFFF"
        return str(selected or "auto")

    def update_subtitle_color_chip(self) -> None:
        if not hasattr(self, "subtitle_color_button"):
            return
        selected = self.subtitle_color_combo.currentData()
        if selected == "custom":
            color = valid_hex_color(self.subtitle_color_hex.text()) or "#FFFFFF"
        else:
            color = PREVIEW_SUBTITLE_COLORS.get(str(selected), "#FFFFFF")
        self.subtitle_color_button.setStyleSheet(
            f"QPushButton#colorSwatch {{ background: {color}; border: 2px solid #5c9dff; border-radius: 15px; }}"
        )

    def choose_subtitle_color(self) -> None:
        current = valid_hex_color(self.subtitle_color_hex.text()) or "#FFFFFF"
        color = QColorDialog.getColor(QColor(current), self, "Pilih warna subtitle")
        if not color.isValid():
            return
        self.subtitle_color_hex.setText(color.name().upper())
        custom_index = self.subtitle_color_combo.findData("custom")
        self.subtitle_color_combo.setCurrentIndex(custom_index)
        self.update_subtitle_color_chip()
        self.update_create_preview()

    def apply_custom_subtitle_hex(self) -> None:
        color = valid_hex_color(self.subtitle_color_hex.text())
        if color is None:
            QMessageBox.warning(self, "Kode warna", "Masukkan kode HEX seperti #FF8800.")
            self.subtitle_color_hex.setText("#FFFFFF")
            return
        self.subtitle_color_hex.setText(color)
        custom_index = self.subtitle_color_combo.findData("custom")
        self.subtitle_color_combo.setCurrentIndex(custom_index)
        self.update_subtitle_color_chip()
        self.update_create_preview()

    def apply_subtitle_preview_style(
        self,
        label: QLabel,
        style: str,
        text: str = "",
        language: str = "",
        color: str = "auto",
        sample: bool = False,
    ) -> None:
        if style == "none":
            label.setVisible(False)
            return
        default_colors = {
            "bold": "white",
            "highlight": "yellow",
            "classic": "white",
            "minimal": "white",
            "neon": "cyan",
            "karaoke": "pink",
            "box": "white",
        }
        accent = valid_hex_color(color) or PREVIEW_SUBTITLE_COLORS.get(
            color,
            PREVIEW_SUBTITLE_COLORS[default_colors.get(style, "white")],
        )
        style_sheets = {
            "bold": (
                f"background: rgba(0, 0, 0, 225); color: {accent}; "
                "padding: 10px 18px; border-radius: 4px; "
                "font-family: Arial Black; font-size: 20px; font-weight: 900;"
            ),
            "highlight": (
                f"background: #102742; color: {accent}; "
                "padding: 10px 18px; border: 1px solid #5c9dff; border-radius: 4px; "
                "font-family: Arial Black; font-size: 20px; font-weight: 900;"
            ),
            "classic": (
                f"background: rgba(0, 0, 0, 175); color: {accent}; "
                "padding: 7px 14px; border-radius: 1px; "
                "font-family: Arial; font-size: 18px; font-weight: 400;"
            ),
            "minimal": (
                f"background: rgba(0, 0, 0, 120); color: {accent}; "
                "padding: 5px 10px; border-radius: 2px; "
                "font-family: Arial; font-size: 17px; font-weight: 400;"
            ),
            "neon": (
                f"background: rgba(7, 20, 35, 225); color: {accent}; "
                f"padding: 9px 16px; border: 1px solid {accent}; border-radius: 12px; "
                "font-family: Arial Black; font-size: 19px; font-weight: 900;"
            ),
            "karaoke": (
                f"background: rgba(51, 14, 67, 225); color: {accent}; "
                f"padding: 10px 18px; border: 1px solid {accent}; border-radius: 5px; "
                "font-family: Arial Black; font-size: 20px; font-weight: 900;"
            ),
            "box": (
                f"background: rgba(0, 0, 0, 220); color: {accent}; "
                "padding: 10px 18px; border-radius: 0px; "
                "font-family: Arial; font-size: 19px; font-weight: 700;"
            ),
        }
        label.setStyleSheet(style_sheets.get(style, style_sheets["bold"]))
        if sample:
            label.setTextFormat(Qt.TextFormat.RichText)
            if style == "highlight":
                label.setText(f"Contoh <font color='{accent}'>subtitle</font> · {language}")
            elif style == "neon":
                label.setText(f"✦ Contoh subtitle · {language} ✦")
            elif style == "karaoke":
                label.setText(f"♪ Contoh subtitle · {language} ♪")
            elif style == "box":
                label.setText(f"[ Contoh subtitle · {language} ]")
            elif style == "minimal":
                label.setText(f"subtitle contoh · {language}")
            else:
                label.setText(f"Contoh subtitle · {language}")
        else:
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setText(text)
        label.setVisible(bool(text) or sample)

    def refresh_subtitle_preview_style(self) -> None:
        if not hasattr(self, "preview_subtitle_sample"):
            return
        style = self.subtitle_combo.currentData() if self.subtitle_enabled.isChecked() else "none"
        self.apply_subtitle_preview_style(
            self.preview_subtitle_sample,
            style,
            language=self.language_combo.currentText(),
            color=self.selected_subtitle_color(),
            sample=True,
        )
        if hasattr(self, "source_subtitle_overlay") and self.source_subtitle_overlay.isVisible():
            self.apply_subtitle_preview_style(
                self.source_subtitle_overlay,
                self.current_options.subtitle_style if self.current_options else "none",
                self.source_subtitle_overlay.text(),
                color=self.current_options.subtitle_color if self.current_options else "auto",
            )

    def update_create_preview(self) -> None:
        if not hasattr(self, "preview_summary"):
            return
        aspect = self.aspect_combo.currentData()
        framing = self.framing_combo.currentText()
        layout = self.layout_combo.currentText()
        canvas_sizes = {"9:16": (360, 640), "16:9": (800, 450), "4:3": (720, 540), "1:1": (520, 520)}
        canvas_width, canvas_height = canvas_sizes.get(aspect, (800, 450))
        self.create_preview_frame.setFixedSize(canvas_width, canvas_height)
        self.create_preview_video.setAspectRatioMode(
            Qt.AspectRatioMode.KeepAspectRatioByExpanding
            if self.framing_combo.currentData() == "crop"
            else Qt.AspectRatioMode.KeepAspectRatio
        )
        self.preview_layout_badge.setText(f"{aspect}  ·  {framing}  ·  {layout}")
        if self.layout_combo.currentData() == "facecam_top":
            self.preview_layout_overlay.setText("Area facecam di atas · preview layout")
            self.preview_layout_overlay.setVisible(True)
            self.preview_facecam_top.setVisible(True)
            self.preview_facecam_main.setVisible(True)
        else:
            self.preview_layout_overlay.setVisible(False)
            self.preview_facecam_top.setVisible(False)
            self.preview_facecam_main.setVisible(False)
        if self.subtitle_enabled.isChecked():
            language = self.language_combo.currentText()
            style = self.subtitle_combo.currentText()
            self.apply_subtitle_preview_style(
                self.preview_subtitle_sample,
                self.subtitle_combo.currentData(),
                language=language,
                color=self.selected_subtitle_color(),
                sample=True,
            )
            subtitle_summary = f"Subtitle: {language} · {style}"
        else:
            self.apply_subtitle_preview_style(self.preview_subtitle_sample, "none")
            subtitle_summary = "Subtitle: tidak digunakan"
        self.update_create_subtitle_position()
        position_summary = self.subtitle_position_combo.currentText()
        if self.subtitle_position_combo.currentData() == "free":
            position_summary += " · seret teks di preview"
        self.preview_summary.setText(f"Output {aspect} · {framing} · {layout}  |  {subtitle_summary}  |  Posisi: {position_summary}")

    @staticmethod
    def subtitle_alignment(position: str) -> Qt.AlignmentFlag:
        if position == "top":
            return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        if position == "center":
            return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom

    def update_create_subtitle_position(self) -> None:
        if not hasattr(self, "create_preview_stack"):
            return
        label = self.preview_subtitle_sample
        position = self.subtitle_position_combo.currentData()
        self.create_preview_stack.removeWidget(label)
        if position == "free":
            label.setParent(self.create_preview_frame)
            label.adjustSize()
            available_width = max(0, self.create_preview_frame.width() - label.width())
            available_height = max(0, self.create_preview_frame.height() - label.height())
            label.move(int(available_width * self.subtitle_free_x), int(available_height * self.subtitle_free_y))
            label.raise_()
        else:
            self.create_preview_stack.addWidget(label, 0, 0, self.subtitle_alignment(position))

    def on_free_subtitle_moved(self, x: float, y: float) -> None:
        self.subtitle_free_x = max(0.0, min(1.0, x))
        self.subtitle_free_y = max(0.0, min(1.0, y))
        if hasattr(self, "preview_summary") and self.subtitle_position_combo.currentData() == "free":
            self.preview_summary.setText(
                f"Subtitle bebas · posisi {self.subtitle_free_x:.0%} dari kiri, {self.subtitle_free_y:.0%} dari atas · seret teks untuk mengubah"
            )

    def update_segment_estimate(self) -> None:
        if not hasattr(self, "segment_estimate"):
            return
        if self.source_duration <= 0:
            self.duration_info.setText("Durasi sumber: belum diketahui")
            self.segment_estimate.setText("Estimasi pembagian akan tampil setelah video siap.")
            return
        total = self.source_duration
        self.duration_info.setText(f"Durasi sumber: {format_time(total)}")
        mode = self.mode_combo.currentData()
        if mode == "split_count":
            count = max(1, self.split_count.value())
            per_clip = total / count
            self.segment_estimate.setText(
                f"Hasil: {count} clip · sekitar {format_time(per_clip)} per clip · total {format_time(total)}."
            )
        elif mode == "split_duration":
            duration = max(1, self.segment_duration.value())
            count = max(1, int((total + duration - 1) // duration))
            self.segment_estimate.setText(
                f"Hasil: sekitar {count} clip · {format_time(duration)} per clip · clip terakhir dapat lebih pendek."
            )
        elif self.smart_duration_mode.currentData() == "fixed":
            duration = max(1, self.smart_fixed_duration.value())
            count = min(self.max_clips.value(), max(1, int((total + duration - 1) // duration)))
            self.segment_estimate.setText(
                f"Otomatis: maksimal {count} clip · target {format_time(duration)} per clip · AI tetap memilih momen terbaik."
            )
        else:
            requested = self.clip_count.value()
            limit = self.max_clips.value() if requested == 0 else min(requested, self.max_clips.value())
            self.segment_estimate.setText(
                f"Otomatis memilih sampai {limit} clip · "
                + (
                    "durasi alami tanpa batas default."
                    if self.min_duration.value() == 0 and self.max_duration.value() == 0
                    else f"rentang {self.min_duration.value() or 'otomatis'}–{self.max_duration.value() or 'otomatis'} detik per clip."
                )
            )

    def seek_create_preview(self, position: int) -> None:
        self.create_preview_player.setPosition(position)

    def update_create_seek(self, position: int) -> None:
        if not self.create_seek_slider.isSliderDown():
            self.create_seek_slider.setValue(position)
        self.create_preview_time.setText(
            f"{format_time(position / 1000)} / {format_time(self.create_preview_player.duration() / 1000)}"
        )

    def update_create_duration(self, duration: int) -> None:
        self.create_seek_slider.setRange(0, max(0, duration))
        self.create_seek_slider.setEnabled(duration > 0)
        if duration > 0:
            self.source_duration = duration / 1000
            self.update_segment_estimate()
        self.update_create_seek(self.create_preview_player.position())

    def toggle_create_preview(self) -> None:
        if self.create_preview_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.create_preview_player.pause()
        else:
            self.create_preview_player.play()

    @staticmethod
    def model_config_path() -> Path:
        return ROOT / "model_paths.json"

    def load_model_paths(self) -> None:
        values: dict[str, str] = {}
        config_path = self.model_config_path()
        try:
            if config_path.is_file():
                loaded = json.loads(config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    values = {str(key): str(value) for key, value in loaded.items()}
        except (OSError, ValueError):
            values = {}
        for model_name, edit in self.model_path_edits.items():
            saved = values.get(model_name, "")
            if saved and Path(saved).is_file():
                edit.setText(saved)
            else:
                detected = core.gguf_path_for(model_name)
                if detected:
                    edit.setText(detected)

    def save_model_paths(self) -> None:
        values = {name: edit.text().strip() for name, edit in self.model_path_edits.items() if edit.text().strip()}
        try:
            self.model_config_path().write_text(json.dumps(values, indent=2), encoding="utf-8")
        except OSError:
            pass

    def set_model_path(self, model_name: str, path: str) -> None:
        if not path.lower().endswith(".gguf"):
            QMessageBox.warning(self, "Model tidak valid", "Pilih file dengan ekstensi .gguf.")
            return
        self.model_path_edits[model_name].setText(path)
        self.save_model_paths()
        self.refresh_model_file_choices([path], keep_current=True)

    def refresh_model_file_choices(self, paths: list[str] | None = None, keep_current: bool = True) -> None:
        if not hasattr(self, "model_file_combo"):
            return
        if paths is None:
            paths = [edit.text().strip() for edit in self.model_path_edits.values() if edit.text().strip()]
        unique_paths = list(dict.fromkeys(paths))
        current = self.model_file_combo.currentData() if keep_current else None
        if not current and keep_current:
            current = next((edit.text().strip() for edit in self.model_path_edits.values() if edit.text().strip()), None)
        self.model_file_combo.blockSignals(True)
        self.model_file_combo.clear()
        for path in unique_paths:
            self.model_file_combo.addItem(Path(path).name, path)
            self.model_file_combo.setItemData(self.model_file_combo.count() - 1, path, Qt.ItemDataRole.ToolTipRole)
        selected_index = self.model_file_combo.findData(current) if current else -1
        self.model_file_combo.setCurrentIndex(selected_index)
        self.model_file_combo.blockSignals(False)
        if selected_index >= 0:
            self.on_model_file_changed(selected_index)

    def on_model_file_changed(self, index: int) -> None:
        if index < 0:
            return
        path = self.model_file_combo.itemData(index)
        if not path:
            return
        lowered = Path(str(path)).name.lower()
        self.active_model_key = "hermes" if "hermes" in lowered else "qwen"
        self.model_path_edits[self.active_model_key].setText(str(path))
        self.save_model_paths()

    def pick_model_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Pilih folder yang berisi model GGUF",
            str(Path.home()),
        )
        if not folder:
            return
        try:
            candidates = sorted(Path(folder).rglob("*.gguf"))
        except OSError as exc:
            QMessageBox.warning(self, "Folder model", f"Folder tidak dapat dibaca: {exc}")
            return
        if not candidates:
            QMessageBox.information(self, "Model belum ditemukan", "Folder tersebut tidak berisi file .gguf.")
            return

        found = {"qwen": "", "hermes": ""}
        for candidate in candidates:
            lowered = candidate.name.lower()
            if "qwen" in lowered and not found["qwen"]:
                found["qwen"] = str(candidate)
            if "hermes" in lowered and not found["hermes"]:
                found["hermes"] = str(candidate)

        for model_name, path in found.items():
            if path:
                self.model_path_edits[model_name].setText(path)
        self.refresh_model_file_choices([str(candidate) for candidate in candidates], keep_current=False)
        self.save_model_paths()
        QMessageBox.information(self, "Model ditemukan", f"{len(candidates)} file GGUF ditemukan. Pilih model dari dropdown Model aktif.")

    def pick_model(self, model_name: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Pilih model {'Qwen' if model_name == 'qwen' else 'Hermes'} GGUF",
            str(Path.home()),
            "Model GGUF (*.gguf)",
        )
        if path:
            self.set_model_path(model_name, path)

    def scan_project_models(self) -> None:
        found = {"qwen": "", "hermes": ""}
        model_dir = ROOT / "models"
        try:
            candidates = sorted(model_dir.glob("*.gguf"))
        except OSError:
            candidates = []
        for candidate in candidates:
            lowered = candidate.name.lower()
            if "qwen" in lowered and not found["qwen"]:
                found["qwen"] = str(candidate)
            if "hermes" in lowered and not found["hermes"]:
                found["hermes"] = str(candidate)
        for model_name, path in found.items():
            if path:
                self.model_path_edits[model_name].setText(path)
        self.save_model_paths()
        found_count = sum(bool(path) for path in found.values())
        if found_count:
            QMessageBox.information(self, "Model ditemukan", f"{found_count} model GGUF berhasil ditemukan di folder models.")
        else:
            QMessageBox.information(self, "Model belum ditemukan", "Tidak ada file .gguf di folder models. Gunakan tombol Cari Qwen atau Cari Hermes.")

    def apply_model_paths(self) -> None:
        selected = self.model_file_combo.currentData() if hasattr(self, "model_file_combo") else None
        if selected:
            self.model_path_edits[self.active_model_key].setText(str(selected))
        core.QWEN_GGUF_PATH = self.model_path_edits["qwen"].text().strip()
        core.HERMES_GGUF_PATH = self.model_path_edits["hermes"].text().strip()

    def build_review_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        eyebrow = QLabel("REVIEW  /  TIMELINE")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        self.review_status = QLabel("Clip AI siap direview")
        self.review_status.setObjectName("title_small")
        layout.addWidget(self.review_status)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        source_frame = QFrame()
        self.review_source_frame = source_frame
        source_frame.setObjectName("previewCanvas")
        source_stack = QGridLayout(source_frame)
        self.review_source_stack = source_stack
        source_stack.setContentsMargins(0, 0, 0, 0)
        self.video_widget = QVideoWidget()
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.player.setVideoOutput(self.video_widget)
        self.video_widget.setMinimumHeight(360)
        source_stack.addWidget(self.video_widget, 0, 0)
        self.source_subtitle_overlay = QLabel("")
        self.source_subtitle_overlay.setObjectName("previewSubtitle")
        self.source_subtitle_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_subtitle_overlay.setWordWrap(True)
        self.source_subtitle_overlay.setVisible(False)
        source_stack.addWidget(self.source_subtitle_overlay, 0, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(source_frame)
        player_controls = QHBoxLayout()
        self.play_button = QPushButton("Play / Pause")
        self.play_button.clicked.connect(self.toggle_video)
        self.current_time = QLabel("00:00 / 00:00")
        self.review_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.review_seek_slider.setRange(0, 0)
        self.review_seek_slider.setEnabled(False)
        self.review_seek_slider.sliderMoved.connect(self.seek_review_video)
        self.player.positionChanged.connect(self.update_player_time)
        self.player.durationChanged.connect(self.update_player_duration)
        player_controls.addWidget(self.play_button)
        player_controls.addWidget(self.review_seek_slider, 1)
        player_controls.addWidget(self.current_time)
        player_controls.addStretch()
        layout.addLayout(player_controls)

        preview_group = QGroupBox("Preview clip render")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_player = QMediaPlayer(self)
        self.preview_audio = QAudioOutput(self)
        self.preview_player.setAudioOutput(self.preview_audio)
        self.preview_player.mediaStatusChanged.connect(self.handle_auto_preview_status)
        preview_frame = QFrame()
        preview_frame.setObjectName("previewCanvas")
        preview_stack = QGridLayout(preview_frame)
        preview_stack.setContentsMargins(0, 0, 0, 0)
        self.preview_video = QVideoWidget()
        self.preview_player.setVideoOutput(self.preview_video)
        self.preview_video.setMinimumHeight(240)
        preview_stack.addWidget(self.preview_video, 0, 0)
        preview_layout.addWidget(preview_frame)
        self.preview_status = QLabel("Pilih clip dari daftar untuk melihat hasil subtitle dan framing.")
        self.preview_status.setObjectName("muted")
        preview_layout.addWidget(self.preview_status)
        self.auto_preview_button = QPushButton("Mulai preview clip AI")
        self.auto_preview_button.setEnabled(False)
        self.auto_preview_button.clicked.connect(self.toggle_auto_preview)
        preview_layout.addWidget(self.auto_preview_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(preview_group)

        manual_group = QGroupBox("Tambahkan clip manual sebelum render final")
        form = QGridLayout(manual_group)
        self.manual_start = QLineEdit("00:00")
        self.manual_end = QLineEdit("01:00")
        self.manual_title = QLineEdit()
        self.manual_title.setPlaceholderText("Kosongkan untuk judul otomatis")
        start_button = QPushButton("Gunakan posisi sebagai mulai")
        end_button = QPushButton("Gunakan posisi sebagai selesai")
        start_button.clicked.connect(lambda: self.manual_start.setText(format_time(self.player.position() / 1000)))
        end_button.clicked.connect(lambda: self.manual_end.setText(format_time(self.player.position() / 1000)))
        form.addWidget(QLabel("Mulai"), 0, 0)
        form.addWidget(self.manual_start, 1, 0)
        form.addWidget(start_button, 2, 0)
        form.addWidget(QLabel("Selesai"), 0, 1)
        form.addWidget(self.manual_end, 1, 1)
        form.addWidget(end_button, 2, 1)
        form.addWidget(QLabel("Judul opsional"), 0, 2)
        form.addWidget(self.manual_title, 1, 2)
        self.add_manual_button = QPushButton("Tambah clip manual")
        self.add_manual_button.clicked.connect(self.add_manual_clip)
        form.addWidget(self.add_manual_button, 2, 2)
        layout.addWidget(manual_group)

        self.review_flow_hint = QLabel("Urutan: clip AI sudah dirender → tambahkan clip manual (render terpisah) → Render final")
        self.review_flow_hint.setObjectName("muted")
        layout.addWidget(self.review_flow_hint)

        layout.addWidget(QLabel("Clip otomatis"))
        self.auto_clips_container = QWidget()
        self.auto_clips_layout = QVBoxLayout(self.auto_clips_container)
        self.auto_clips_layout.setContentsMargins(0, 0, 0, 0)
        self.auto_clips_layout.setSpacing(8)
        layout.addWidget(self.auto_clips_container)

        layout.addWidget(QLabel("Clip manual"))
        self.manual_clips_container = QWidget()
        self.manual_clips_layout = QVBoxLayout(self.manual_clips_container)
        self.manual_clips_layout.setContentsMargins(0, 0, 0, 0)
        self.manual_clips_layout.setSpacing(8)
        layout.addWidget(self.manual_clips_container)
        self.render_button = QPushButton("Render final")
        self.render_button.setObjectName("primary")
        self.render_button.clicked.connect(self.render_final)
        layout.addWidget(self.render_button, alignment=Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(page)
        return scroll

    def build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        eyebrow = QLabel("EXPORT  /  FILES")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        self.results_title = QLabel("Hasil clip")
        self.results_title.setObjectName("title_small")
        layout.addWidget(self.results_title)
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.open_result)
        layout.addWidget(self.results_list)
        open_button = QPushButton("Buka folder hasil")
        open_button.clicked.connect(self.open_results_folder)
        layout.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignLeft)
        return page

    @staticmethod
    def combo(items: list[tuple[str, str]], selected: int = 0) -> QComboBox:
        box = ClickOnlyComboBox()
        for label, value in items:
            box.addItem(label, value)
        box.setCurrentIndex(selected)
        box.setMinimumHeight(34)
        return box

    @staticmethod
    def spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        box = FocusOnlySpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        box.setMinimumHeight(34)
        return box

    def build_options(self) -> core.CreateJobRequest:
        minimum = self.min_duration.value()
        maximum = self.max_duration.value()
        if minimum > 0 and maximum > 0 and minimum > maximum:
            raise ValueError("Minimum durasi tidak boleh lebih besar dari maksimum durasi.")
        return core.CreateJobRequest(
            url=self.url_edit.text().strip(),
            clip_count=self.clip_count.value(),
            language=self.language_combo.currentData(),
            min_duration=minimum,
            max_duration=maximum,
            max_clips=self.max_clips.value(),
            clip_mode=self.mode_combo.currentData(),
            clip_profile=self.profile_combo.currentData(),
            split_count=self.split_count.value(),
            segment_duration=self.segment_duration.value(),
            smart_duration_mode=self.smart_duration_mode.currentData(),
            smart_fixed_duration=self.smart_fixed_duration.value(),
            use_local_llm=self.use_llm.isChecked(),
            local_model=self.active_model_key,
            quality=self.quality_combo.currentData(),
            aspect_ratio=self.aspect_combo.currentData(),
            framing=self.framing_combo.currentData(),
            layout=self.layout_combo.currentData(),
            subtitle_style=self.subtitle_combo.currentData() if self.subtitle_enabled.isChecked() else "none",
            subtitle_position=self.subtitle_position_combo.currentData() if self.subtitle_enabled.isChecked() else "auto",
            subtitle_color=self.selected_subtitle_color() if self.subtitle_enabled.isChecked() else "auto",
            subtitle_x=self.subtitle_free_x,
            subtitle_y=self.subtitle_free_y,
        )

    def start_download(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Sumber video", "Masukkan link video terlebih dahulu.")
            return
        self.current_job_id = uuid.uuid4().hex[:12]
        with core.JOBS_LOCK:
            core.JOBS[self.current_job_id] = core.Job(id=self.current_job_id, url=url)
        self.download_button.setEnabled(False)
        self.local_file_button.setEnabled(False)
        self.progress.setVisible(True)
        self.status_label.setVisible(True)
        self.progress.setValue(0)
        self.source_status.setText("Mengunduh video ke folder VideoMentah...")
        self.status_label.setText("Menyiapkan download...")
        self.download_worker = DownloadWorker(self.current_job_id, url, self.quality_combo.currentData())
        self.download_worker.finished_download.connect(self.refresh_job)
        self.download_worker.start()
        self.poll_timer.start(700)

    def choose_local_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih file video",
            str(Path.home()),
            "Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v)",
        )
        if not path:
            return
        self.current_job_id = uuid.uuid4().hex[:12]
        with core.JOBS_LOCK:
            core.JOBS[self.current_job_id] = core.Job(id=self.current_job_id, url=str(path))
        try:
            source = core.import_local_video(self.current_job_id, Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "File video", str(exc))
            return
        self.url_edit.setText(str(path))
        self.show_clip_stage(str(source), f"File siap digunakan · {Path(path).name}")

    def show_clip_stage(self, source_path: str, message: str) -> None:
        self.download_button.setEnabled(True)
        self.local_file_button.setEnabled(True)
        self.source_status.setText(message)
        self.active_transcript = []
        self.source_subtitle_overlay.setVisible(False)
        if source_path and Path(source_path).is_file():
            self.source_duration = core.media_duration(Path(source_path), 0.0)
            self.create_preview_player.setSource(QUrl.fromLocalFile(source_path))
            self.create_preview_player.pause()
            self.update_create_preview()
            self.update_segment_estimate()
        self.progress.setVisible(False)
        self.status_label.setVisible(False)
        for widget in self.clip_stage_widgets:
            widget.setVisible(True)
        self.start_button.setEnabled(True)
        self.switch_tab(1)

    def start_process(self) -> None:
        if not self.current_job_id:
            QMessageBox.warning(self, "Video sumber", "Unduh atau pilih file video terlebih dahulu.")
            return
        with core.JOBS_LOCK:
            existing_job = core.JOBS.get(self.current_job_id)
            source_path = existing_job.source_path if existing_job else ""
        if not source_path:
            QMessageBox.warning(self, "Video sumber", "Video belum siap digunakan. Unduh atau pilih file video terlebih dahulu.")
            return
        try:
            options = self.build_options()
        except Exception as exc:
            QMessageBox.critical(self, "Pengaturan tidak valid", str(exc))
            return
        if self.use_llm.isChecked() and not self.model_file_combo.currentData():
            QMessageBox.warning(self, "Pilih model", "Pilih salah satu file .gguf dari dropdown Model aktif terlebih dahulu.")
            return
        self.apply_model_paths()
        self.save_model_paths()
        self.current_options = options
        with core.JOBS_LOCK:
            core.JOB_OPTIONS[self.current_job_id] = options
        self.start_button.setEnabled(False)
        self.tabs.setTabEnabled(2, False)
        self.tabs.setTabEnabled(3, False)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Memulai...")
        self.worker = JobWorker(self.current_job_id, options, source_path=source_path)
        self.worker.finished_job.connect(self.refresh_job)
        self.worker.start()
        self.poll_timer.start(700)

    def refresh_job(self) -> None:
        if not self.current_job_id:
            return
        with core.JOBS_LOCK:
            job = core.JOBS.get(self.current_job_id)
            snapshot = core.job_snapshot(job) if job else None
        if not snapshot:
            return
        self.progress.setValue(snapshot["progress"])
        self.status_label.setText(snapshot["message"])
        if snapshot["status"] == "downloaded":
            self.poll_timer.stop()
            self.show_clip_stage(snapshot.get("source_path", ""), snapshot["message"])
        elif snapshot["status"] == "awaiting_render":
            self.poll_timer.stop()
            self.start_button.setEnabled(True)
            self.show_review(snapshot)
        elif snapshot["status"] == "completed":
            self.poll_timer.stop()
            self.start_button.setEnabled(True)
            self.show_results(snapshot)
        elif snapshot["status"] == "failed":
            self.poll_timer.stop()
            self.download_button.setEnabled(True)
            self.local_file_button.setEnabled(True)
            self.start_button.setEnabled(True)
            self.render_button.setEnabled(True)
            self.add_manual_button.setEnabled(True)
            QMessageBox.critical(self, "Proses gagal", snapshot.get("error") or snapshot["message"])

    def show_review(self, job: dict[str, Any]) -> None:
        ai_count = sum(1 for clip in job["clips"] if clip.get("source") == "ai")
        manual_count = sum(1 for clip in job["clips"] if clip.get("source") == "manual")
        self.review_status.setText(
            f"{ai_count} clip AI siap direview · {manual_count} clip manual · tambahkan manual bila perlu"
        )
        self.active_transcript = list(job.get("transcript") or [])
        subtitles_available = bool(self.current_options and self.current_options.subtitle_style != "none")
        self.source_subtitle_overlay.setVisible(subtitles_available and bool(self.active_transcript))
        source_path = Path(job.get("source_path", ""))
        if source_path.exists():
            self.player.setSource(QUrl.fromLocalFile(str(source_path)))
        self.update_realtime_subtitle(0.0)
        self.auto_preview_running = False
        self.auto_preview_index = 0
        self.auto_preview_items = []
        self.auto_preview_button.setText("Mulai preview clip AI")
        self.clear_clip_layout(self.auto_clips_layout)
        self.clear_clip_layout(self.manual_clips_layout)
        self.review_entries = []
        automatic_count = 0
        manual_count = 0
        for index, clip in enumerate(job["clips"], start=1):
            source = "AI" if clip.get("source") == "ai" else "MANUAL"
            caption = clip.get("caption", "")[:100]
            text = f"{index:02} · {clip['title']} · {format_time(clip['start'])}–{format_time(clip['end'])} · {source}"
            if caption:
                text += f"\n   {caption}"
            entry = {
                "title": text,
                "path": str(core.clip_result_dir(
                    Path(job.get("result_dir") or core.job_result_dir(job["id"])),
                    clip["id"],
                    clip["title"],
                ) / "clip.mp4"),
                "source": clip.get("source", "ai"),
            }
            self.review_entries.append(entry)
            target_layout = self.auto_clips_layout if clip.get("source") == "ai" else self.manual_clips_layout
            target_layout.addWidget(self.create_clip_card(entry, len(self.review_entries) - 1))
            if clip.get("source") == "ai":
                self.auto_preview_items.append(entry)
                automatic_count += 1
            else:
                manual_count += 1
        if automatic_count == 0:
            self.add_empty_clip_label(self.auto_clips_layout, "Belum ada clip AI otomatis.")
        if manual_count == 0:
            self.add_empty_clip_label(self.manual_clips_layout, "Belum ada clip manual. Gunakan kontrol di atas untuk menambahkannya.")
        self.auto_preview_button.setEnabled(bool(self.auto_preview_items))
        self.tabs.setTabEnabled(2, True)
        self.switch_tab(2)

    @staticmethod
    def clear_clip_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def add_empty_clip_label(layout: QVBoxLayout, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("muted")
        label.setWordWrap(True)
        layout.addWidget(label)

    def create_clip_card(self, entry: dict[str, Any], index: int) -> QFrame:
        card = QFrame()
        card.setObjectName("clipCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)
        info = QLabel(entry["title"])
        info.setWordWrap(True)
        info.setObjectName("clipCardInfo")
        row.addWidget(info, 1)
        play_button = QPushButton("▶ Play")
        play_button.setObjectName("clipPlay")
        play_button.clicked.connect(lambda checked=False, clip_index=index: self.open_clip_popup(clip_index))
        row.addWidget(play_button, 0, Qt.AlignmentFlag.AlignVCenter)
        return card

    def open_clip_popup(self, index: int) -> None:
        if not hasattr(self, "review_entries") or not (0 <= index < len(self.review_entries)):
            return
        if hasattr(self, "clip_preview_dialog") and self.clip_preview_dialog is not None:
            self.clip_preview_dialog.close()
        self.clip_preview_dialog = ClipPreviewDialog(self.review_entries, index, self)
        self.clip_preview_dialog.show()
        self.clip_preview_dialog.raise_()
        self.clip_preview_dialog.activateWindow()

    def toggle_auto_preview(self) -> None:
        if self.auto_preview_running:
            self.auto_preview_running = False
            self.preview_player.stop()
            self.auto_preview_button.setText("Mulai preview clip AI")
            self.preview_status.setText("Preview otomatis dihentikan.")
            return
        if not self.auto_preview_items:
            self.preview_status.setText("Belum ada clip AI yang bisa dipreview.")
            return
        self.auto_preview_running = True
        self.auto_preview_index = 0
        self.auto_preview_button.setText("Hentikan preview otomatis")
        self.play_auto_preview_item()

    def play_auto_preview_item(self) -> None:
        if not self.auto_preview_running or not self.auto_preview_items:
            return
        if self.auto_preview_index >= len(self.auto_preview_items):
            self.auto_preview_running = False
            self.auto_preview_button.setText("Mulai preview clip AI")
            self.preview_status.setText("Semua clip AI sudah selesai dipreview.")
            return
        item = self.auto_preview_items[self.auto_preview_index]
        path = item["path"]
        if path and Path(path).is_file():
            self.preview_player.setSource(QUrl.fromLocalFile(path))
            self.preview_player.play()
            self.preview_status.setText(
                f"Preview otomatis · clip AI {self.auto_preview_index + 1}/{len(self.auto_preview_items)}"
            )
        else:
            self.auto_preview_index += 1
            self.play_auto_preview_item()

    def handle_auto_preview_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status != QMediaPlayer.MediaStatus.EndOfMedia or not self.auto_preview_running:
            return
        self.auto_preview_index += 1
        QTimer.singleShot(350, self.play_auto_preview_item)

    def add_manual_clip(self) -> None:
        if not self.current_job_id:
            return
        start = parse_time(self.manual_start.text())
        end = parse_time(self.manual_end.text())
        if start is None or end is None or end <= start:
            QMessageBox.warning(self, "Waktu clip", "Waktu mulai dan selesai tidak valid.")
            return
        with core.JOBS_LOCK:
            job = core.JOBS[self.current_job_id]
            if any(start < item.end and end > item.start for item in job.clips):
                QMessageBox.warning(self, "Clip tumpang tindih", "Waktu tersebut bertumpang tindih dengan clip yang sudah ada.")
                return
            clip = core.Clip(
                id=f"manual-{sum(1 for item in job.clips if item.source == 'manual') + 1:02}",
                start=start,
                end=end,
                score=0,
                title=self.manual_title.text().strip(),
                source="manual",
            )
            job.clips.append(clip)
            transcript = list(job.transcript)
            options = core.JOB_OPTIONS[self.current_job_id]
        self.add_manual_button.setEnabled(False)
        self.preview_status.setText("Membuat metadata dan merender clip manual...")
        self.metadata_worker = MetadataWorker(transcript, clip, options.local_model)
        self.metadata_worker.finished_metadata.connect(self.manual_metadata_ready)
        self.metadata_worker.start()

    def manual_metadata_ready(self) -> None:
        with core.JOBS_LOCK:
            job = core.JOBS[self.current_job_id]
            clip = next((item for item in job.clips if item.source == "manual" and not item.video_url), None)
            options = core.JOB_OPTIONS[self.current_job_id]
        if clip is None:
            self.add_manual_button.setEnabled(True)
            return
        self.manual_render_worker = ManualRenderWorker(self.current_job_id, clip, options)
        self.manual_render_worker.finished_render.connect(self.manual_render_ready)
        self.manual_render_worker.start()

    def manual_render_ready(self) -> None:
        self.add_manual_button.setEnabled(True)
        self.manual_title.clear()
        with core.JOBS_LOCK:
            job = core.JOBS[self.current_job_id]
            render_error = job.error if job.message == "Render clip manual gagal" else None
            snapshot = core.job_snapshot(job)
        if render_error:
            QMessageBox.critical(self, "Render clip manual", render_error)
            return
        self.preview_status.setText("Clip manual sudah dirender dan tersedia di bagian Clip manual.")
        self.show_review(snapshot)

    def render_final(self) -> None:
        if not self.current_job_id or not self.current_options:
            return
        options = self.current_options.model_copy(update={
            "subtitle_style": self.current_options.subtitle_style,
            "aspect_ratio": self.current_options.aspect_ratio,
            "framing": self.current_options.framing,
            "layout": self.current_options.layout,
        })
        with core.JOBS_LOCK:
            core.JOB_OPTIONS[self.current_job_id] = options
        self.render_button.setEnabled(False)
        self.add_manual_button.setEnabled(False)
        self.preview_status.setText("Menyiapkan render final semua clip...")
        self.worker = JobWorker(self.current_job_id, options, render=True)
        self.worker.finished_job.connect(self.refresh_job)
        self.worker.start()
        self.poll_timer.start(700)

    def show_results(self, job: dict[str, Any]) -> None:
        self.tabs.setTabEnabled(3, True)
        self.switch_tab(3)
        self.results_title.setText(f"{len(job['clips'])} clip selesai")
        self.results_list.clear()
        for clip in job["clips"]:
            path = core.clip_result_dir(
                Path(job.get("result_dir") or core.job_result_dir(job["id"])),
                clip["id"],
                clip["title"],
            ) / "clip.mp4"
            item = QListWidgetItem(f"{clip['title']} · {format_time(clip['start'])}–{format_time(clip['end'])}")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.results_list.addItem(item)

    def open_result(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_results_folder(self) -> None:
        if self.current_job_id:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(core.job_result_dir(self.current_job_id))))

    def toggle_video(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def seek_review_video(self, position: int) -> None:
        self.player.setPosition(position)

    def update_player_time(self, position: int) -> None:
        if not self.review_seek_slider.isSliderDown():
            self.review_seek_slider.setValue(position)
        self.current_time.setText(f"{format_time(position / 1000)} / {format_time(self.player.duration() / 1000)}")
        self.update_realtime_subtitle(position / 1000)

    def update_player_duration(self, duration: int) -> None:
        self.review_seek_slider.setRange(0, max(0, duration))
        self.review_seek_slider.setEnabled(duration > 0)
        self.current_time.setText(f"{format_time(self.player.position() / 1000)} / {format_time(duration / 1000)}")

    def update_realtime_subtitle(self, seconds: float) -> None:
        if not self.current_options or self.current_options.subtitle_style == "none":
            self.source_subtitle_overlay.setVisible(False)
            return
        self.update_review_subtitle_position()
        current = next(
            (
                item for item in self.active_transcript
                if float(item.get("start", 0)) <= seconds <= float(item.get("end", 0))
            ),
            None,
        )
        text = str(current.get("text", "")).strip() if current else ""
        self.apply_subtitle_preview_style(
            self.source_subtitle_overlay,
            self.current_options.subtitle_style,
            text=text,
            color=self.current_options.subtitle_color,
        )
        self.update_review_subtitle_position()

    def update_review_subtitle_position(self) -> None:
        if not hasattr(self, "review_source_stack") or not self.current_options:
            return
        label = self.source_subtitle_overlay
        position = self.current_options.subtitle_position
        self.review_source_stack.removeWidget(label)
        if position == "free":
            label.setParent(self.review_source_frame)
            label.adjustSize()
            available_width = max(0, self.review_source_frame.width() - label.width())
            available_height = max(0, self.review_source_frame.height() - label.height())
            label.move(
                int(available_width * self.current_options.subtitle_x),
                int(available_height * self.current_options.subtitle_y),
            )
            label.raise_()
        else:
            self.review_source_stack.addWidget(label, 0, 0, self.subtitle_alignment(position))

    def switch_tab(self, index: int) -> None:
        if not self.tabs.isTabEnabled(index):
            return
        self.tabs.setCurrentIndex(index)
        for button_index, button in self.nav_buttons.items():
            button.setChecked(button_index == index)
        page = self.tabs.widget(index)
        if page is None:
            return
        if self.page_animation is not None:
            self.page_animation.stop()
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(0.55)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.page_animation = animation
        animation.start()

    def toggle_theme(self) -> None:
        self.apply_theme(self.current_theme != "light")

    def apply_theme(self, light: bool) -> None:
        self.current_theme = "light" if light else "dark"
        self.theme_button.setText("Tema: Gelap" if light else "Tema: Terang")
        self.theme_button.setToolTip("Ganti ke tema gelap" if light else "Ganti ke tema terang")
        self.setStyleSheet(self.stylesheet(self.current_theme))
        self.refresh_subtitle_preview_style()
        QSettings("VanClipper", "VanClipper").setValue("theme", self.current_theme)

    @staticmethod
    def stylesheet(theme: str = "dark") -> str:
        if theme == "light":
            return """
            QWidget { background: #f4f6f2; color: #202820; font-family: Segoe UI; font-size: 13px; }
            QMainWindow, QToolBar { background: #f4f6f2; }
            QToolBar { border: 0; spacing: 6px; padding: 7px 12px; }
            QLabel#brand { color: #1b2a42; font-size: 16px; font-weight: 700; padding-right: 6px; }
            QLabel#brandMeta { color: #7b8798; font-size: 11px; padding-right: 16px; }
            QPushButton#navButton { background: transparent; border: 0; border-radius: 4px; padding: 8px 11px; color: #64748a; }
            QPushButton#navButton:hover { background: #e4ebf6; color: #243a5a; }
            QPushButton#navButton:checked { background: #dce8fa; color: #234b86; font-weight: 600; }
            QTabWidget::pane { background: #ffffff; border: 1px solid #d8ded6; border-top: 0; }
            QTabBar { background: #f4f6f2; }
            QTabBar::tab { background: #f4f6f2; color: #6c776c; padding: 12px 18px; border: 0; border-bottom: 2px solid transparent; }
            QTabBar::tab:hover { color: #263126; background: #e9eee7; }
            QTabBar::tab:selected { color: #1c2a42; background: #ffffff; border-bottom: 2px solid #467dd1; }
            QGroupBox { background: #ffffff; border: 1px solid #d8dee8; border-radius: 7px; margin-top: 14px; padding: 14px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #596a82; font-size: 11px; font-weight: 600; }
            QLabel#eyebrow { color: #4f78b6; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
            QLabel#workflowNote { color: #6d83a4; font-size: 10px; font-weight: 600; line-height: 1.5; }
            QLabel#title { color: #182018; font-size: 27px; font-weight: 650; margin: 2px 0; }
            QLabel#title_small { color: #182018; font-size: 21px; font-weight: 650; }
            QLabel#muted, QLabel#status { color: #687386; }
            QLabel#previewSubtitle { background: rgba(20, 29, 45, 210); color: #ffffff; padding: 9px 18px; border-radius: 3px; font-weight: 700; margin-bottom: 14px; }
            QFrame#previewCanvas { background: #11151c; border: 1px solid #b9c8dd; border-radius: 5px; }
            QLabel#previewBadge { color: #4f78b6; font-size: 11px; font-weight: 600; padding: 4px 0; }
            QLabel#previewGuide { background: rgba(38, 83, 145, 175); color: #ffffff; padding: 10px 34px; border: 1px solid #4d8cf5; font-size: 10px; font-weight: 700; }
            QSlider::groove:horizontal { height: 5px; background: #dbe4f1; border-radius: 2px; }
            QSlider::handle:horizontal { width: 13px; margin: -5px 0; background: #4d8cf5; border-radius: 7px; }
            QLineEdit, QComboBox, QSpinBox, QTextEdit { background: #fbfcff; border: 1px solid #c8d1df; border-radius: 4px; padding: 8px; color: #202820; selection-background-color: #c8d9f2; }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus { border: 1px solid #4d8cf5; }
            QComboBox::drop-down { width: 26px; border: 0; }
            QPushButton { background: #edf2fb; border: 1px solid #c7d2e4; border-radius: 4px; padding: 8px 13px; color: #2b3a52; }
            QPushButton:hover { background: #e5edf9; border-color: #4d8cf5; }
            QPushButton#primary { background: #4f83d7; color: #ffffff; font-weight: 700; border: 0; padding: 10px 17px; }
            QPushButton#primary:hover { background: #3f70bf; }
            QPushButton:disabled { color: #9aa4b3; background: #e9edf4; border-color: #d7dde7; }
            QProgressBar { border: 0; border-radius: 2px; background: #dbe4f1; text-align: center; height: 8px; color: transparent; }
            QProgressBar::chunk { background: #4d8cf5; border-radius: 2px; }
            QListWidget { background: #fbfcff; border: 1px solid #d8dee8; border-radius: 4px; padding: 4px; }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #e5eaf2; }
            QListWidget::item:selected { background: #dce8fa; color: #20304a; }
            QFrame#clipCard { background: #fbfcff; border: 1px solid #d8dee8; border-radius: 6px; }
            QLabel#clipCardInfo { color: #2b3a52; }
            QPushButton#clipPlay { background: #dce8fa; color: #234b86; border: 1px solid #aabbd4; padding: 7px 14px; }
            QScrollBar:vertical { background: #f4f6f2; width: 10px; margin: 2px; }
            QScrollBar::handle:vertical { background: #bec9d9; min-height: 24px; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QToolTip { background: #ffffff; color: #202820; border: 1px solid #aabbd4; padding: 5px; }
            """
        return """
        QWidget { background: #090b0f; color: #e7edf5; font-family: Segoe UI; font-size: 13px; }
        QMainWindow { background: #090b0f; }
        QToolBar { background: #0d1016; border: 0; spacing: 6px; padding: 7px 12px; }
        QLabel#brand { color: #e8f0fb; font-size: 16px; font-weight: 700; padding-right: 6px; }
        QLabel#brandMeta { color: #8190a5; font-size: 11px; padding-right: 16px; }
        QPushButton#navButton { background: transparent; border: 0; border-radius: 4px; padding: 8px 11px; color: #8794a8; }
        QPushButton#navButton:hover { background: #172334; color: #dce7f8; }
        QPushButton#navButton:checked { background: #1b3557; color: #e8f1ff; font-weight: 600; }
        QTabWidget::pane { background: #0d1016; border: 1px solid #252e3b; border-top: 0; }
        QTabBar { background: #090b0f; }
        QTabBar::tab { background: #090b0f; color: #8490a2; padding: 12px 18px; border: 0; border-bottom: 2px solid transparent; }
        QTabBar::tab:hover { color: #dce7f8; background: #111721; }
        QTabBar::tab:selected { color: #e9f1ff; background: #111721; border-bottom: 2px solid #5c9dff; }
        QGroupBox { background: #11151c; border: 1px solid #252e3b; border-radius: 7px; margin-top: 14px; padding: 14px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #9ba9bd; font-size: 11px; font-weight: 600; }
        QLabel#eyebrow { color: #78aef5; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
        QLabel#workflowNote { color: #7187a7; font-size: 10px; font-weight: 600; line-height: 1.5; }
        QLabel#title { color: #eef2ec; font-size: 27px; font-weight: 650; margin: 2px 0; }
        QLabel#title_small { color: #eef2ec; font-size: 21px; font-weight: 650; }
        QLabel#muted, QLabel#status { color: #8d98aa; }
        QLabel#previewSubtitle { background: rgba(0, 0, 0, 210); color: #ffffff; padding: 9px 18px; border-radius: 3px; font-weight: 700; margin-bottom: 14px; }
        QFrame#previewCanvas { background: #05070a; border: 1px solid #35537b; border-radius: 5px; }
        QLabel#previewBadge { color: #78aef5; font-size: 11px; font-weight: 600; padding: 4px 0; }
        QLabel#previewGuide { background: rgba(35, 77, 132, 180); color: #dcecff; padding: 10px 34px; border: 1px solid #5c9dff; font-size: 10px; font-weight: 700; }
        QSlider::groove:horizontal { height: 5px; background: #283343; border-radius: 2px; }
        QSlider::handle:horizontal { width: 13px; margin: -5px 0; background: #5c9dff; border-radius: 7px; }
        QLineEdit, QComboBox, QSpinBox, QTextEdit { background: #090c11; border: 1px solid #303b4c; border-radius: 4px; padding: 8px; color: #e7edf5; selection-background-color: #355f9c; }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus { border: 1px solid #5f9fff; }
        QComboBox::drop-down { width: 26px; border: 0; }
        QPushButton { background: #171e29; border: 1px solid #394a63; border-radius: 4px; padding: 8px 13px; color: #c8d5e9; }
        QPushButton:hover { background: #24334b; border-color: #6396dd; }
        QPushButton#primary { background: #4f8fe8; color: #08111e; font-weight: 700; border: 0; padding: 10px 17px; }
        QPushButton#primary:hover { background: #6aa5f5; }
        QPushButton:disabled { color: #687487; background: #171c25; border-color: #293548; }
        QProgressBar { border: 0; border-radius: 2px; background: #283343; text-align: center; height: 8px; color: transparent; }
        QProgressBar::chunk { background: #5c9dff; border-radius: 2px; }
        QListWidget { background: #090c11; border: 1px solid #252e3b; border-radius: 4px; padding: 4px; }
        QListWidget::item { padding: 10px; border-bottom: 1px solid #202936; }
        QListWidget::item:selected { background: #1d2d45; color: #e9f1ff; }
        QFrame#clipCard { background: #111a26; border: 1px solid #2b415f; border-radius: 6px; }
        QLabel#clipCardInfo { color: #d7e5f7; }
        QPushButton#clipPlay { background: #1b3557; color: #dcecff; border: 1px solid #4d79ad; padding: 7px 14px; }
        QScrollBar:vertical { background: #090b0f; width: 10px; margin: 2px; }
        QScrollBar::handle:vertical { background: #3b4b63; min-height: 24px; border-radius: 4px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QToolTip { background: #171e29; color: #edf3fb; border: 1px solid #52709b; padding: 5px; }
        """


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("VanClipper")
    window = HermesDesktop()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
