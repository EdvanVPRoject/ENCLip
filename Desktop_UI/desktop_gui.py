from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

if not getattr(sys, "frozen", False):
    backend_path = str((Path(__file__).resolve().parent.parent / "Backend_API"))
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
import web_server as core
from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QFont, QIcon, QImage, QLinearGradient, QPainter, QPen, QPixmap, QPolygon
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


def get_app_icon() -> QIcon | None:
    for base in [Path(__file__).parent, Path(sys.executable).parent, Path(getattr(sys, "_MEIPASS", ""))]:
        for name in ("icon.ico", "icon.png"):
            candidate = base / name
            if candidate.is_file():
                return QIcon(str(candidate))
    return None


ROOT = getattr(core, "ROOT", (Path(__file__).parent.parent / "Core_Data").resolve())

PREVIEW_SUBTITLE_COLORS = {
    "white": "#ffffff",
    "yellow": "#ffe066",
    "cyan": "#63d9ff",
    "red": "#ff6b6b",
    "green": "#73e6a4",
    "pink": "#ff70d1",
}


def persist_gemini_key_to_env(api_key: str) -> None:
    """Menyimpan GEMINI_API_KEY ke environment, QSettings, dan file .env agar CLI/Auto-Clipper selalu sinkron."""
    clean = (api_key or "").strip()
    os.environ["GEMINI_API_KEY"] = clean
    core.GEMINI_API_KEY = clean
    if clean:
        QSettings("ENCLip", "ENCLip").setValue("gemini_api_key", clean)
        QSettings("ENCLip", "ENCLip").setValue("gemini_api_key_saved", True)
        for env_path in (ROOT / ".env", Path(__file__).resolve().parent.parent / ".env"):
            try:
                env_path.parent.mkdir(parents=True, exist_ok=True)
                lines: list[str] = []
                if env_path.is_file():
                    lines = [
                        ln for ln in env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                        if not ln.strip().startswith("GEMINI_API_KEY=")
                    ]
                lines.append(f"GEMINI_API_KEY={clean}")
                env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except Exception:
                pass


def valid_hex_color(value: str) -> str | None:
    text = value.strip().upper()
    if len(text) == 7 and text.startswith("#") and all(char in "0123456789ABCDEF" for char in text[1:]):
        return text
    return None


def get_video_thumbnail_path(video_path: str | Path, timestamp: float = 2.0) -> str | None:
    try:
        video_p = Path(video_path)
        if not video_p.is_file():
            return None
        thumb_dir = video_p.parent / ".thumbs"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_file = thumb_dir / f"thumb_{int(timestamp)}.jpg"
        if thumb_file.is_file() and thumb_file.stat().st_size > 0:
            return str(thumb_file)
        ffmpeg = core.ffmpeg_command()
        cmd = ffmpeg + [
            "-ss", str(max(0.0, timestamp)),
            "-i", str(video_p),
            "-vframes", "1",
            "-vf", "scale=360:-1",
            "-y", str(thumb_file),
        ]
        core.run_command(cmd)
        if thumb_file.is_file() and thumb_file.stat().st_size > 0:
            return str(thumb_file)
    except Exception:
        pass
    return None


def make_vector_icon(icon_type: str, color_hex: str = "#CBD5E1", sz: int = 24) -> QIcon:
    pix = QPixmap(sz, sz)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(color_hex)
    painter.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if icon_type == "play":
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        poly = QPolygon([QPoint(7, 5), QPoint(19, 12), QPoint(7, 19)])
        painter.drawPolygon(poly)
    elif icon_type == "pause":
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(6, 5, 4, 14, 1, 1)
        painter.drawRoundedRect(14, 5, 4, 14, 1, 1)
    elif icon_type == "rewind":
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        poly1 = QPolygon([QPoint(11, 6), QPoint(3, 12), QPoint(11, 18)])
        poly2 = QPolygon([QPoint(20, 6), QPoint(12, 12), QPoint(20, 18)])
        painter.drawPolygon(poly1)
        painter.drawPolygon(poly2)
    elif icon_type == "forward":
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        poly1 = QPolygon([QPoint(4, 6), QPoint(12, 12), QPoint(4, 18)])
        poly2 = QPolygon([QPoint(13, 6), QPoint(21, 12), QPoint(13, 18)])
        painter.drawPolygon(poly1)
        painter.drawPolygon(poly2)
    elif icon_type == "edit":
        painter.drawLine(5, 19, 8, 19)
        painter.drawLine(5, 19, 5, 16)
        painter.drawLine(5, 16, 16, 5)
        painter.drawLine(8, 19, 19, 8)
        painter.drawLine(16, 5, 19, 8)
    elif icon_type == "cut":
        painter.drawEllipse(4, 14, 5, 5)
        painter.drawEllipse(4, 5, 5, 5)
        painter.drawLine(8, 7, 19, 17)
        painter.drawLine(8, 17, 19, 7)
    elif icon_type == "ratio":
        painter.drawRoundedRect(5, 5, 14, 14, 2, 2)
        painter.drawLine(5, 12, 19, 12)
    elif icon_type == "reset":
        painter.drawArc(5, 5, 14, 14, 45 * 16, 270 * 16)
        painter.setBrush(QBrush(color))
        poly = QPolygon([QPoint(12, 4), QPoint(17, 7), QPoint(14, 10)])
        painter.drawPolygon(poly)
    elif icon_type == "prev":
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        poly = QPolygon([QPoint(17, 6), QPoint(8, 12), QPoint(17, 18)])
        painter.drawPolygon(poly)
        painter.drawRoundedRect(5, 6, 2, 12, 1, 1)
    elif icon_type == "next":
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        poly = QPolygon([QPoint(7, 6), QPoint(16, 12), QPoint(7, 18)])
        painter.drawPolygon(poly)
        painter.drawRoundedRect(17, 6, 2, 12, 1, 1)
    elif icon_type in ("volume_on", "volume"):
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        poly = QPolygon([QPoint(4, 9), QPoint(8, 9), QPoint(13, 5), QPoint(13, 19), QPoint(8, 15), QPoint(4, 15)])
        painter.drawPolygon(poly)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(11, 8, 8, 8, -45 * 16, 90 * 16)
        painter.drawArc(10, 5, 14, 14, -45 * 16, 90 * 16)
    elif icon_type == "volume_mute":
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        poly = QPolygon([QPoint(4, 9), QPoint(8, 9), QPoint(13, 5), QPoint(13, 19), QPoint(8, 15), QPoint(4, 15)])
        painter.drawPolygon(poly)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(15, 9, 21, 15)
        painter.drawLine(21, 9, 15, 15)
    elif icon_type == "safezone":
        painter.drawRoundedRect(4, 4, 16, 16, 2, 2)
        painter.drawLine(4, 8, 20, 8)
        painter.drawLine(4, 16, 20, 16)
        painter.drawLine(16, 8, 16, 16)
    elif icon_type == "copy":
        painter.drawRoundedRect(8, 4, 12, 13, 2, 2)
        painter.drawRoundedRect(4, 8, 12, 12, 2, 2)
    elif icon_type == "zoom":
        painter.drawEllipse(5, 5, 10, 10)
        painter.drawLine(13, 13, 19, 19)

    painter.end()
    return QIcon(pix)


class ToggleSwitch(QCheckBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._progress: float = 1.0 if self.isChecked() else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_val)

    def _on_anim_val(self, val: Any) -> None:
        self._progress = float(val)
        self.update()

    def nextCheckState(self) -> None:
        new_state = not self.isChecked()
        super().setChecked(new_state)
        self._anim.stop()
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(1.0 if new_state else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # type: ignore[override]
        self._anim.stop()
        super().setChecked(checked)
        self._progress = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        t = max(0.0, min(1.0, self._progress if self._anim.state() == QAbstractAnimation.State.Running else (1.0 if self.isChecked() else 0.0)))
        r = int(24 * (1 - t) + 37 * t)
        g = int(24 * (1 - t) + 99 * t)
        b = int(31 * (1 - t) + 235 * t)
        p.setBrush(QColor(r, g, b))
        border_c = QColor("#3B82F6") if t > 0.5 else QColor("#2E2E3A")
        p.setPen(QPen(border_c, 1))
        p.drawRoundedRect(rect, 11, 11)
        thumb_x = 3.0 + (self.width() - 21.0) * t
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF") if t > 0.3 else QColor("#A1A1AA"))
        p.drawEllipse(QRectF(thumb_x, 3.0, 18.0, 18.0))


class DropZoneWidget(QFrame):
    fileDropped = pyqtSignal(str)
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("dropZone")
        self.setMinimumHeight(210)
        self.is_drag_over = False

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        icon_box = QLabel()
        icon_box.setPixmap(make_vector_icon("folder", "#3B82F6", 42).pixmap(42, 42))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_box)

        self.text_label = QLabel("Tarik & lepas video ke sini, atau klik untuk memilih file")
        self.text_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #FAFAFA; background: transparent; border: none;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)

        self.sub_label = QLabel("Mendukung MP4, MOV, MKV, WEBM, AVI · Tanpa kompresi awal")
        self.sub_label.setStyleSheet("font-size: 12px; color: #71717A; background: transparent; border: none;")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sub_label)

        self.update_style()

    def update_style(self) -> None:
        border_color = "#3B82F6" if self.is_drag_over else "#24242E"
        bg_color = "#0E1628" if self.is_drag_over else "#09090D"
        self.setStyleSheet(f"""
            QFrame#dropZone {{
                background-color: {bg_color};
                border: 1.5px dashed {border_color};
                border-radius: 14px;
            }}
            QFrame#dropZone:hover {{
                border-color: #3B82F6;
                background-color: #0F0F16;
            }}
        """)

    def dragEnterEvent(self, event: Any) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")) for url in urls):
                event.acceptProposedAction()
                self.is_drag_over = True
                self.update_style()
                return
        event.ignore()

    def dragLeaveEvent(self, event: Any) -> None:
        self.is_drag_over = False
        self.update_style()

    def dropEvent(self, event: Any) -> None:
        self.is_drag_over = False
        self.update_style()
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and Path(path).is_file() and Path(path).suffix.lower() in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"):
                self.fileDropped.emit(path)
                event.acceptProposedAction()
                return

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class WaveformScrubber(QSlider):
    def __init__(self, orientation: Qt.Orientation = Qt.Orientation.Horizontal, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.segments: list[dict[str, Any]] = []

    def set_segments(self, segments: list[dict[str, Any]]) -> None:
        self.segments = list(segments or [])
        self.update()

    def wheelEvent(self, event: Any) -> None:
        event.ignore()

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.maximum() > self.minimum():
            ratio = max(0.0, min(1.0, event.position().x() / max(1.0, float(self.width()))))
            val = int(self.minimum() + ratio * (self.maximum() - self.minimum()))
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        p.setBrush(QColor("#09090D"))
        p.setPen(QPen(QColor("#1F1F28"), 1))
        p.drawRoundedRect(0, 3, w, h - 6, 7, 7)

        import math
        span = max(1, self.maximum() - self.minimum())
        val_ratio = (self.value() - self.minimum()) / span if self.maximum() > self.minimum() else 0.0
        active_x = int(w * val_ratio)

        # Draw multi-segment manual clip blocks live on timeline
        if self.segments and self.maximum() > 0:
            dur_sec = max(1.0, self.maximum() / 1000.0)
            palette = [
                (QColor(245, 158, 11, 68), QColor("#F59E0B")),
                (QColor(34, 211, 238, 68), QColor("#22D3EE")),
                (QColor(168, 85, 247, 68), QColor("#A855F7")),
                (QColor(16, 185, 129, 68), QColor("#10B981")),
            ]
            for idx_s, seg in enumerate(self.segments):
                try:
                    s_sec = max(0.0, float(seg.get("start", 0.0)))
                    e_sec = min(dur_sec, float(seg.get("end", 0.0)))
                    if e_sec > s_sec:
                        sx = int((s_sec / dur_sec) * w)
                        ex = max(sx + 6, int((e_sec / dur_sec) * w))
                        fill_c, line_c = palette[idx_s % len(palette)]
                        p.setBrush(fill_c)
                        p.setPen(QPen(line_c, 1.2))
                        p.drawRoundedRect(sx, 4, ex - sx, h - 8, 5, 5)
                        if (ex - sx) >= 24:
                            p.setFont(QFont("Cascadia Mono", 7, QFont.Weight.Bold))
                            p.setPen(line_c)
                            p.drawText(QRect(sx + 4, 4, ex - sx - 6, 12), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, f"#{idx_s + 1:02d}")
                except Exception:
                    pass

        bar_count = max(10, w // 4)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(bar_count):
            bx = i * 4 + 2
            amp = math.sin(i * 0.28) * math.cos(i * 0.14) * 0.68 + 0.28
            bh = max(3, int((h - 16) * abs(amp)))
            by = (h - bh) // 2
            if bx <= active_x:
                p.setBrush(QColor("#38BDF8" if bx % 8 == 0 else "#3B82F6"))
            else:
                p.setBrush(QColor("#272732"))
            p.drawRoundedRect(bx, by, 2, bh, 1, 1)

        if self.maximum() > self.minimum():
            hx = min(w - 5, max(4, active_x))
            p.setBrush(QColor("#FAFAFA"))
            p.drawRoundedRect(hx - 1, 2, 3, h - 4, 1.5, 1.5)
            p.setBrush(QColor("#3B82F6"))
            poly = QPolygon([QPoint(hx - 5, 2), QPoint(hx + 5, 2), QPoint(hx, 8)])
            p.drawPolygon(poly)


class TimelineWidget(QWidget):
    seekRequested = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.total_duration_ms = 0
        self.current_position_ms = 0
        self.clip_start_sec = 0.0
        self.clip_end_sec = 0.0
        self._dragging = False

    def set_duration(self, duration_ms: int) -> None:
        self.total_duration_ms = max(0, duration_ms)
        self.update()

    def set_position(self, position_ms: int) -> None:
        self.current_position_ms = max(0, min(self.total_duration_ms, position_ms))
        self.update()

    def set_active_clip(self, start_sec: float, end_sec: float) -> None:
        self.clip_start_sec = max(0.0, start_sec)
        self.clip_end_sec = max(0.0, end_sec)
        self.update()

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._handle_mouse(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self._dragging:
            self._handle_mouse(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        self._dragging = False
        super().mouseReleaseEvent(event)

    def _handle_mouse(self, x: float) -> None:
        track_left = 90
        track_right = self.width() - 14
        if track_right <= track_left or self.total_duration_ms <= 0:
            return
        ratio = max(0.0, min(1.0, (x - track_left) / (track_right - track_left)))
        target_ms = int(ratio * self.total_duration_ms)
        self.seekRequested.emit(target_ms)

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        track_left = 90
        track_right = w - 14
        track_w = max(1, track_right - track_left)

        p.setBrush(QColor("#0B0E14"))
        p.setPen(QPen(QColor("#1E293B"), 1))
        p.drawRoundedRect(0, 0, w - 1, h - 1, 8, 8)

        font = p.font()
        font.setPointSize(9)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#94A3B8"))
        p.drawText(8, 46, "Video Track")
        p.drawText(8, 86, "Audio Track")
        p.drawText(8, 126, "Subtitle Track")

        ruler_font = p.font()
        ruler_font.setPointSize(8)
        ruler_font.setBold(False)
        p.setFont(ruler_font)
        total_sec = self.total_duration_ms / 1000 if self.total_duration_ms > 0 else 60.0
        step_sec = 60.0 if total_sec > 180 else 15.0
        curr_t = 0.0
        p.setPen(QColor("#475569"))
        while curr_t <= total_sec:
            tx = track_left + int((curr_t / total_sec) * track_w)
            p.drawLine(tx, 14, tx, 20)
            mins = int(curr_t // 60)
            secs = int(curr_t % 60)
            p.drawText(tx - 12, 12, f"{mins}:{secs:02d}")
            curr_t += step_sec

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#131926"))
        p.drawRoundedRect(track_left, 26, track_w, 32, 4, 4)
        slice_w = 40
        num_slices = max(1, track_w // slice_w)
        p.setPen(QPen(QColor("#1E293B"), 1))
        for i in range(num_slices):
            p.drawLine(track_left + i * slice_w, 26, track_left + i * slice_w, 58)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#131926"))
        p.drawRoundedRect(track_left, 66, track_w, 32, 4, 4)
        import math
        audio_bars = max(10, track_w // 4)
        for i in range(audio_bars):
            bx = track_left + i * 4 + 2
            amp = math.sin(i * 0.3) * math.cos(i * 0.15) * 0.65 + 0.35
            bh = max(3, int(22 * abs(amp)))
            by = 66 + (32 - bh) // 2
            p.setBrush(QColor("#38BDF8" if i % 6 == 0 else "#334155"))
            p.drawRoundedRect(bx, by, 2, bh, 1, 1)

        p.setBrush(QColor("#131926"))
        p.drawRoundedRect(track_left, 106, track_w, 28, 4, 4)
        p.setBrush(QColor("#1E293B"))
        chunk_count = 6
        for c in range(chunk_count):
            cx = track_left + int((c / chunk_count) * track_w) + 6
            cw = max(10, int(track_w / (chunk_count + 1)) - 10)
            p.drawRoundedRect(cx, 110, cw, 20, 3, 3)

        if self.clip_end_sec > self.clip_start_sec and total_sec > 0:
            c_start_x = track_left + int((self.clip_start_sec / total_sec) * track_w)
            c_end_x = track_left + int((self.clip_end_sec / total_sec) * track_w)
            c_w = max(4, c_end_x - c_start_x)
            p.setPen(QPen(QColor("#3B82F6"), 2))
            p.setBrush(QColor(59, 130, 246, 35))
            p.drawRoundedRect(c_start_x, 26, c_w, 72, 4, 4)
            p.setBrush(QColor("#06B6D4"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(c_start_x, 26, 4, 72, 2, 2)
            p.drawRoundedRect(c_end_x - 4, 26, 4, 72, 2, 2)

        if self.total_duration_ms > 0:
            pos_ratio = self.current_position_ms / self.total_duration_ms
            hx = track_left + int(pos_ratio * track_w)
            hx = min(track_right, max(track_left, hx))
            p.setPen(QPen(QColor("#3B82F6"), 2))
            p.drawLine(hx, 18, hx, 140)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#3B82F6"))
            poly = QPolygon([QPoint(hx - 5, 12), QPoint(hx + 5, 12), QPoint(hx, 20)])
            p.drawPolygon(poly)


class EditTextDialog(QDialog):
    def __init__(self, title: str, caption: str, subtitle_lines: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sunting Judul, Subtitle Video & Caption Klip")
        self.resize(560, 440)
        self.setStyleSheet("background: #0F1420; color: #F1F5F9;")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Judul Klip (Sekaligus Teks Default Hook Banner):"))
        self.title_edit = QLineEdit(title)
        self.title_edit.setMinimumHeight(34)
        layout.addWidget(self.title_edit)

        layout.addWidget(QLabel("Teks Subtitle Video (Format per baris: mulai - selesai | teks):"))
        self.subtitle_edit = QPlainTextEdit()
        self.subtitle_edit.setPlainText(subtitle_lines)
        self.subtitle_edit.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 12px; background: #0B0E14; "
            "border: 1px solid #233148; border-radius: 6px; padding: 6px;"
        )
        layout.addWidget(self.subtitle_edit, 2)

        layout.addWidget(QLabel("Caption Sosial Media:"))
        self.caption_edit = QTextEdit()
        self.caption_edit.setPlainText(caption)
        self.caption_edit.setMaximumHeight(85)
        layout.addWidget(self.caption_edit, 1)

        btns = QHBoxLayout()
        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Simpan Perubahan")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def get_data(self) -> tuple[str, str, str]:
        return (
            self.title_edit.text().strip(),
            self.caption_edit.toPlainText().strip(),
            self.subtitle_edit.toPlainText().strip(),
        )


class ManualClipDialog(QDialog):
    def __init__(self, current_pos_sec: float = 0.0, max_dur_sec: float = 60.0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tambah Klip Manual")
        self.resize(420, 260)
        self.setStyleSheet("background: #0F1420; color: #F1F5F9;")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        form = QFormLayout()
        start_val = format_time(current_pos_sec)
        end_val = format_time(min(max_dur_sec, current_pos_sec + 45.0))
        self.start_edit = QLineEdit(start_val)
        self.start_edit.setMinimumHeight(34)
        form.addRow("Waktu Mulai:", self.start_edit)
        self.end_edit = QLineEdit(end_val)
        self.end_edit.setMinimumHeight(34)
        form.addRow("Waktu Selesai:", self.end_edit)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Kosongkan untuk judul otomatis")
        self.title_edit.setMinimumHeight(34)
        form.addRow("Judul Klip:", self.title_edit)
        layout.addLayout(form)
        btns = QHBoxLayout()
        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        add_btn = QPushButton("Tambah Klip")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(add_btn)
        layout.addLayout(btns)

    def get_data(self) -> tuple[str, str, str]:
        return self.start_edit.text().strip(), self.end_edit.text().strip(), self.title_edit.text().strip()


def make_decorated_thumbnail(thumb_path: str | None, duration_sec: float) -> QPixmap:
    pix = QPixmap(240, 135)
    if thumb_path and Path(thumb_path).is_file():
        orig = QPixmap(thumb_path)
        if not orig.isNull():
            pix = orig.scaled(
                240, 135, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            pix = pix.copy(max(0, (pix.width() - 240) // 2), max(0, (pix.height() - 135) // 2), 240, 135)
        else:
            pix.fill(QColor("#131926"))
    else:
        pix.fill(QColor("#131926"))

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    p.setBrush(QColor(0, 0, 0, 160))
    p.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
    p.drawEllipse(QPoint(120, 67), 20, 20)
    p.setBrush(QColor("#FFFFFF"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygon([QPoint(114, 57), QPoint(129, 67), QPoint(114, 77)]))

    p.setBrush(QColor(255, 255, 255, 200))
    p.drawPolygon(QPolygon([QPoint(12, 116), QPoint(20, 122), QPoint(12, 128)]))

    dur_text = format_time(duration_sec)
    p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
    metrics = p.fontMetrics()
    bw = metrics.horizontalAdvance(dur_text) + 12
    bh = 18
    bx = 240 - bw - 10
    by = 135 - bh - 8
    p.setBrush(QColor(0, 0, 0, 195))
    p.drawRoundedRect(bx, by, bw, bh, 4, 4)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(bx, by, bw, bh, Qt.AlignmentFlag.AlignCenter, dur_text)
    p.end()
    return pix


class VideoCardWidget(QFrame):
    clicked = pyqtSignal(object)
    doubleClicked = pyqtSignal(object)

    def __init__(self, entry_data: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry_data = entry_data
        self.is_selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("videoCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.thumb_label = QLabel()
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setFixedHeight(120)
        self.thumb_label.setStyleSheet("border-radius: 8px; background: #050508;")

        pix = make_decorated_thumbnail(entry_data.get("thumb_path"), float(entry_data.get("duration", 0.0)))
        self.thumb_label.setPixmap(pix)
        layout.addWidget(self.thumb_label)
        self.update_style()

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected
        self.update_style()

    def update_style(self) -> None:
        border = "#3B82F6" if self.is_selected else "#1C1C26"
        bg = "#0E1626" if self.is_selected else "#09090E"
        self.setStyleSheet(f"""
            QFrame#videoCard {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 11px;
            }}
            QFrame#videoCard:hover {{
                border-color: #3B82F6;
                background: #0D0F18;
            }}
        """)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.entry_data)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self.entry_data)
        super().mouseDoubleClickEvent(event)


class ReviewClipCardWidget(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, clip_data: dict[str, Any], index: int, source_path: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.clip_data = clip_data
        self.index = index
        self.is_selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("reviewClipCard")
        self.setFixedHeight(84)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 12, 6)
        layout.setSpacing(12)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(105, 68)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setStyleSheet("border-radius: 7px; background: #050508;")

        start_sec = float(clip_data.get("start", 0.0))
        end_sec = float(clip_data.get("end", 0.0))
        dur_sec = max(0.0, end_sec - start_sec)

        thumb_path = get_video_thumbnail_path(source_path, start_sec) if source_path else None
        pix = make_decorated_thumbnail(thumb_path, dur_sec)
        self.thumb_label.setPixmap(pix)
        layout.addWidget(self.thumb_label)

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 2, 0, 2)
        info_col.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title_text = f"{index + 1:02d} · {clip_data.get('title', 'Klip Video')}"
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet("font-weight: 700; font-size: 13px; color: #FFFFFF; background: transparent;")
        title_row.addWidget(title_lbl, 1)

        score_val = int(float(clip_data.get("score", 0)))
        if score_val > 0:
            score_badge = QLabel(f"{score_val}%")
            score_col = "#F87171" if score_val >= 88 else "#FBBF24"
            score_bg = "#2D1215" if score_val >= 88 else "#2A1E0D"
            score_badge.setStyleSheet(
                f"font-size: 10px; font-weight: 800; color: {score_col}; "
                f"background: {score_bg}; border: 1px solid {score_col}; "
                f"border-radius: 4px; padding: 1px 6px;"
            )
            title_row.addWidget(score_badge)

        source = clip_data.get("source", "ai")
        source_badge = QLabel("AI" if source == "ai" else "MANUAL")
        if source == "ai":
            source_badge.setStyleSheet(
                "font-size: 10px; font-weight: 700; color: #38BDF8; background: #0C2138; "
                "border: 1px solid #1D4ED8; border-radius: 4px; padding: 1px 6px;"
            )
        else:
            source_badge.setStyleSheet(
                "font-size: 10px; font-weight: 700; color: #F59E0B; background: #2E1F0C; "
                "border: 1px solid #B45309; border-radius: 4px; padding: 1px 6px;"
            )
        title_row.addWidget(source_badge)
        info_col.addLayout(title_row)

        time_text = f"{format_time(start_sec)} – {format_time(end_sec)} ({int(dur_sec)}s)"
        time_lbl = QLabel(time_text)
        time_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #60A5FA; background: transparent;")
        info_col.addWidget(time_lbl)

        caption = str(clip_data.get("caption", "")).strip()
        if caption:
            snippet = caption[:75] + ("..." if len(caption) > 75 else "")
            caption_lbl = QLabel(f'"{snippet}"')
            caption_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; font-style: italic; background: transparent;")
            info_col.addWidget(caption_lbl)

        layout.addLayout(info_col, 1)
        self.update_style()

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected
        self.update_style()

    def update_style(self) -> None:
        if self.is_selected:
            self.setStyleSheet("""
                QFrame#reviewClipCard {
                    background: #0F172A;
                    border: 1.5px solid #3B82F6;
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#reviewClipCard {
                    background: #09090E;
                    border: 1px solid #1C1C26;
                    border-radius: 10px;
                }
                QFrame#reviewClipCard:hover {
                    border-color: #3B82F6;
                    background: #0D0F18;
                }
            """)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)


class ResultClipCardWidget(QFrame):
    def __init__(self, clip_data: dict[str, Any], clip_path: Path, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.clip_data = clip_data
        self.clip_path = clip_path
        self.index = index
        self.setObjectName("resultCard")
        self.setStyleSheet("""
            QFrame#resultCard {
                background: #09090E;
                border: 1px solid #1C1C26;
                border-radius: 12px;
            }
            QFrame#resultCard:hover {
                border-color: #3B82F6;
                background: #0D0F18;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        start_sec = float(clip_data.get("start", 0.0))
        end_sec = float(clip_data.get("end", 0.0))
        dur_sec = max(0.0, end_sec - start_sec)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedHeight(125)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setStyleSheet("border-radius: 8px; background: #050508;")

        thumb_file = get_video_thumbnail_path(str(clip_path), 0.5) if clip_path.is_file() else None
        pix = make_decorated_thumbnail(thumb_file, dur_sec)
        self.thumb_label.setPixmap(pix)
        layout.addWidget(self.thumb_label)

        title_text = f"{index + 1:02d} · {clip_data.get('title', 'Klip Video')}"
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #FFFFFF; background: transparent;")
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        size_str = ""
        if clip_path.is_file():
            size_mb = clip_path.stat().st_size / (1024 * 1024)
            size_str = f" · {size_mb:.1f} MB"

        fmt_lbl = QLabel(f"Format: MP4 | 1080p{size_str}")
        fmt_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; background: transparent;")
        layout.addWidget(fmt_lbl)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        success_badge = QLabel("Berhasil")
        success_badge.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #38BDF8; background: #0C2138; "
            "border: 1px solid #1D4ED8; border-radius: 4px; padding: 2px 8px;"
        )
        status_row.addWidget(success_badge)
        status_row.addStretch()
        layout.addLayout(status_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        play_btn = QPushButton("▶ Putar")
        play_btn.setMinimumHeight(32)
        play_btn.setStyleSheet("""
            QPushButton {
                background: #111118;
                border: 1px solid #242432;
                border-radius: 7px;
                color: #60A5FA;
                font-weight: 700;
                font-size: 12px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: #2563EB;
                color: #FFFFFF;
                border-color: #3B82F6;
            }
        """)
        play_btn.clicked.connect(self.play_clip)
        action_row.addWidget(play_btn, 1)

        folder_btn = QPushButton("Folder")
        folder_btn.setMinimumHeight(32)
        folder_btn.setToolTip("Buka folder berkas ini")
        folder_btn.setStyleSheet("""
            QPushButton {
                background: #111118;
                border: 1px solid #242432;
                border-radius: 7px;
                color: #A1A1AA;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background: #1A1A26;
                color: #FFFFFF;
                border-color: #3B82F6;
            }
        """)
        folder_btn.clicked.connect(self.open_folder)
        action_row.addWidget(folder_btn)

        copy_btn = QPushButton("Salin Caption")
        copy_btn.setMinimumHeight(32)
        copy_btn.setIcon(make_vector_icon("copy", "#A1A1AA", 16))
        copy_btn.setToolTip("Salin judul, caption, dan hashtag AI ke clipboard")
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #111118;
                border: 1px solid #242432;
                border-radius: 7px;
                color: #D4D4D8;
                font-weight: 600;
                font-size: 11px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background: #1A1A26;
                border-color: #38BDF8;
                color: #FFFFFF;
            }
        """)
        copy_btn.clicked.connect(self.copy_metadata)
        self.copy_btn = copy_btn
        action_row.addWidget(copy_btn)

        yt_btn = QPushButton("Shorts")
        yt_btn.setMinimumHeight(32)
        yt_btn.setToolTip("Upload klip ini langsung ke YouTube Shorts")
        yt_btn.setStyleSheet("""
            QPushButton {
                background: #2D1414;
                border: 1px solid #7F1D1D;
                border-radius: 6px;
                color: #FCA5A5;
                font-weight: 700;
                font-size: 11px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background: #DC2626;
                color: #FFFFFF;
                border-color: #EF4444;
            }
        """)
        yt_btn.clicked.connect(self.upload_to_youtube_shorts_action)
        self.yt_btn = yt_btn
        action_row.addWidget(yt_btn)

        tt_btn = QPushButton("TikTok")
        tt_btn.setMinimumHeight(32)
        tt_btn.setToolTip("Upload klip ini ke TikTok (Pilih: Upload Sekarang atau Jadwalkan Jam Ramai FYP)")
        tt_btn.setStyleSheet("""
            QPushButton {
                background: #0F292E;
                border: 1px solid #0E7490;
                border-radius: 6px;
                color: #67E8F9;
                font-weight: 700;
                font-size: 11px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background: #0891B2;
                color: #FFFFFF;
                border-color: #22D3EE;
            }
        """)
        tt_btn.clicked.connect(self.upload_to_tiktok_action)
        self.tt_btn = tt_btn
        action_row.addWidget(tt_btn)

        layout.addLayout(action_row)

    def copy_metadata(self) -> None:
        title = str(self.clip_data.get("title", "")).strip()
        caption = str(self.clip_data.get("caption", "") or self.clip_data.get("summary", "")).strip()
        tags = self.clip_data.get("hashtags", [])
        if isinstance(tags, list):
            tags_str = " ".join(f"#{t.lstrip('#')}" for t in tags if t)
        else:
            tags_str = str(tags).strip()

        parts = [p for p in (title, caption, tags_str) if p]
        full_text = "\n\n".join(parts)
        if full_text:
            QApplication.clipboard().setText(full_text)
            self.copy_btn.setText("Tersalin!")
            QTimer.singleShot(1500, lambda: self.copy_btn.setText("Salin Caption"))

    def play_clip(self) -> None:
        if self.clip_path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.clip_path)))

    def upload_to_youtube_shorts_action(self) -> None:
        try:
            from omnichannel_publisher import SESSION_YOUTUBE
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal memuat modul publisher: {e}")
            return

        if not SESSION_YOUTUBE.is_file():
            ans = QMessageBox.question(
                self,
                "Login YouTube Studio",
                "Sesi akun YouTube belum ditemukan.\n\nBuka jendela browser sekarang untuk login 1x ke YouTube Studio?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans == QMessageBox.StandardButton.Yes:
                self.yt_btn.setEnabled(False)
                self.yt_btn.setText("Login...")
                self._login_worker = YouTubeLoginWorker()
                def on_done(ok: bool, msg: str):
                    self.yt_btn.setEnabled(True)
                    self.yt_btn.setText("Shorts")
                    if ok:
                        QMessageBox.information(self, "Sesi Tersimpan", msg + "\n\nSilakan klik tombol 'Shorts' lagi untuk mengunggah klip.")
                    else:
                        QMessageBox.warning(self, "Login Gagal", msg)
                self._login_worker.finished_login.connect(on_done)
                self._login_worker.start()
            return

        title = str(self.clip_data.get("title", "")).strip() or "Klip Podcast"
        desc = str(self.clip_data.get("caption", "") or self.clip_data.get("summary", "")).strip()
        tags = self.clip_data.get("hashtags", [])
        if tags and isinstance(tags, list):
            tag_str = " ".join(t if t.startswith("#") else f"#{t}" for t in tags[:6])
            desc = f"{desc}\n\n{tag_str}"

        ans = QMessageBox.question(
            self,
            "Konfirmasi Upload YouTube Shorts",
            f"Unggah klip ini ke YouTube Shorts sekarang?\n\nJudul: {title} #Shorts\nFile: {self.clip_path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        self.yt_btn.setEnabled(False)
        self.yt_btn.setText("Uploading...")
        self._upload_worker = YouTubeUploadWorker(self.clip_path, title, desc)
        def on_upload_done(ok: bool, msg: str):
            self.yt_btn.setEnabled(True)
            if ok:
                self.yt_btn.setText("Terunggah!")
                self.yt_btn.setStyleSheet("background: #064E3B; border: 1px solid #059669; color: #6EE7B7; border-radius: 6px; font-weight: 700; font-size: 11px;")
                QMessageBox.information(self, "Sukses", msg)
            else:
                self.yt_btn.setText("Shorts")
                QMessageBox.warning(self, "Upload Gagal", msg)
        self._upload_worker.finished_upload.connect(on_upload_done)
        self._upload_worker.start()

    def open_folder(self) -> None:
        folder = self.clip_path.parent if self.clip_path.is_file() else self.clip_path
        if folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def upload_to_tiktok_action(self) -> None:
        if not self.clip_path.is_file():
            QMessageBox.warning(self, "Berkas Tidak Ditemukan", "File video klip belum tersedia.")
            return
        title = str(self.clip_data.get("title", "")).strip() or "Klip Podcast"
        caption = str(self.clip_data.get("caption", "") or self.clip_data.get("summary", "")).strip()

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Upload TikTok")
        msg_box.setText(f"Pilih metode publikasi TikTok untuk klip:\n\n{title}")
        msg_box.setInformativeText(
            "• Upload Sekarang: Langsung unggah ke TikTok Studio (otomatis pilih sampul detik 1.8s + sound viral + 5 hashtag SEO).\n"
            "• Masuk Antrean Jam Ramai: Disimpan ke antrean pintar untuk diunggah otomatis pada jam aktif FYP (Siang/Sore/Malam)."
        )
        btn_now = msg_box.addButton("Upload Sekarang", QMessageBox.ButtonRole.AcceptRole)
        btn_queue = msg_box.addButton("Antrean Jam Ramai", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton("Batal", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == btn_queue:
            try:
                import auto_clipper_tiktok as act
                q = act.UploadQueue()
                seo_caption = act.format_tiktok_caption(title, caption, self.clip_data.get("hashtags", []), title)
                q.add(
                    video_path=self.clip_path,
                    caption=seo_caption,
                    source_url=str(self.clip_path),
                    clip_title=title,
                    score=float(self.clip_data.get("score", 88)),
                )
                self.tt_btn.setText("Di Antrean")
                QMessageBox.information(
                    self,
                    "Masuk Antrean Jam Ramai",
                    f"Klip '{title}' berhasil ditambahkan ke antrean Smart Peak TikTok!\n\nTotal antrean siap tayang: {q.pending_count()} video.",
                )
            except Exception as exc:
                QMessageBox.warning(self, "Gagal Menambah Antrean", str(exc))
            return

        if clicked == btn_now:
            self.tt_btn.setEnabled(False)
            self.tt_btn.setText("Uploading...")
            self._tt_worker = TikTokUploadWorker(self.clip_path, title, caption, self.clip_data.get("hashtags", []))
            def on_tt_done(ok: bool, msg: str) -> None:
                self.tt_btn.setEnabled(True)
                if ok:
                    self.tt_btn.setText("Terunggah")
                    self.tt_btn.setStyleSheet(
                        "background: #064E3B; border: 1px solid #059669; color: #6EE7B7; border-radius: 6px; font-weight: 700; font-size: 11px;"
                    )
                    QMessageBox.information(self, "TikTok Upload Sukses", msg)
                else:
                    self.tt_btn.setText("TikTok")
                    QMessageBox.warning(self, "TikTok Upload", msg)
            self._tt_worker.finished_upload.connect(on_tt_done)
            self._tt_worker.start()


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
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def wheelEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        event.ignore()

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width() - 18
        cy = self.height() // 2
        pen = QPen(QColor("#A1A1AA" if self.isEnabled() else "#52525B"), 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx - 4.5, cy - 2.0), QPointF(cx, cy + 2.5))
        p.drawLine(QPointF(cx, cy + 2.5), QPointF(cx + 4.5, cy - 2.0))


class FocusOnlySpinBox(QSpinBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self._hover_zone: str | None = None
        self.setMouseTracking(True)

    def wheelEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        event.ignore()

    def _btn_rects(self) -> tuple[QRectF, QRectF]:
        w, h = float(self.width()), float(self.height())
        bw = 24.0
        minus_r = QRectF(w - bw * 2 - 4, 4.0, bw, h - 8.0)
        plus_r = QRectF(w - bw - 3, 4.0, bw, h - 8.0)
        return minus_r, plus_r

    def mouseMoveEvent(self, event: Any) -> None:
        pos = event.position()
        minus_r, plus_r = self._btn_rects()
        new_zone = "minus" if minus_r.contains(pos) else ("plus" if plus_r.contains(pos) else None)
        if new_zone != self._hover_zone:
            self._hover_zone = new_zone
            self.setCursor(Qt.CursorShape.PointingHandCursor if new_zone else Qt.CursorShape.IBeamCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self._hover_zone = None
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            pos = event.position()
            minus_r, plus_r = self._btn_rects()
            if minus_r.contains(pos):
                self.stepDown()
                event.accept()
                return
            if plus_r.contains(pos):
                self.stepUp()
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        minus_r, plus_r = self._btn_rects()
        for zone_name, rect, sym in (("minus", minus_r, "−"), ("plus", plus_r, "+")):
            hovered = self._hover_zone == zone_name and self.isEnabled()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#2563EB") if hovered else QColor("#181822"))
            p.drawRoundedRect(rect, 5.0, 5.0)
            p.setPen(QColor("#FFFFFF") if hovered else QColor("#A1A1AA" if self.isEnabled() else "#52525B"))
            p.setFont(QFont("Segoe UI Variable Display", 10, QFont.Weight.Bold))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, sym)


class NoWheelSlider(QSlider):
    def __init__(self, orientation: Qt.Orientation = Qt.Orientation.Horizontal, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def wheelEvent(self, event: Any) -> None:
        event.ignore()

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.orientation() == Qt.Orientation.Horizontal and self.maximum() > self.minimum():
            ratio = max(0.0, min(1.0, event.position().x() / max(1.0, float(self.width()))))
            val = int(round(self.minimum() + ratio * (self.maximum() - self.minimum())))
            self.setValue(val)
            event.accept()
            return
        super().mousePressEvent(event)


def draw_preset_wireframe(p: QPainter, rect: QRectF, kind: str, color: QColor) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy = rect.center().x(), rect.center().y()
    w, h = rect.width(), rect.height()

    if kind == "ai_spark":
        pts = [
            QPointF(cx, cy - h * 0.42),
            QPointF(cx + w * 0.13, cy - h * 0.13),
            QPointF(cx + w * 0.42, cy),
            QPointF(cx + w * 0.13, cy + h * 0.13),
            QPointF(cx, cy + h * 0.42),
            QPointF(cx - w * 0.13, cy + h * 0.13),
            QPointF(cx - w * 0.42, cy),
            QPointF(cx - w * 0.13, cy - h * 0.13),
        ]
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 45))
        p.drawPolygon([QPoint(int(pt.x()), int(pt.y())) for pt in pts])
    elif kind == "scissors":
        p.drawEllipse(QRectF(cx - 8, cy + 2, 6, 6))
        p.drawEllipse(QRectF(cx + 2, cy + 2, 6, 6))
        p.drawLine(QPointF(cx - 3, cy + 3), QPointF(cx + 6, cy - 8))
        p.drawLine(QPointF(cx + 3, cy + 3), QPointF(cx - 6, cy - 8))
    elif kind in ("frame_none", "ratio_orig"):
        r = QRectF(cx - 10, cy - 7, 20, 14)
        p.drawRoundedRect(r, 3, 3)
        p.drawLine(QPointF(r.left() + 4, r.top() + 4), QPointF(r.left() + 8, r.top() + 4))
        p.drawLine(QPointF(r.left() + 4, r.top() + 4), QPointF(r.left() + 4, r.top() + 8))
        p.drawLine(QPointF(r.right() - 4, r.bottom() - 4), QPointF(r.right() - 8, r.bottom() - 4))
        p.drawLine(QPointF(r.right() - 4, r.bottom() - 4), QPointF(r.right() - 4, r.bottom() - 8))
    elif kind in ("frame_auto", "cam_adapt", "universal"):
        r = QRectF(cx - 7, cy - 10, 14, 20)
        p.drawRoundedRect(r, 3, 3)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 65))
        p.drawEllipse(QRectF(cx - 3, cy - 4, 6, 6))
    elif kind == "frame_manual":
        r = QRectF(cx - 8, cy - 8, 16, 16)
        p.drawRoundedRect(r, 3, 3)
        p.drawLine(QPointF(cx, cy - 5), QPointF(cx, cy + 5))
        p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
    elif kind in ("cam_split", "podcast"):
        r = QRectF(cx - 7, cy - 10, 14, 20)
        p.drawRoundedRect(r, 3, 3)
        p.drawLine(QPointF(r.left(), cy), QPointF(r.right(), cy))
    elif kind == "cam_focus":
        r = QRectF(cx - 7, cy - 10, 14, 20)
        p.drawRoundedRect(r, 3, 3)
        p.drawEllipse(QRectF(cx - 3.5, cy - 5, 7, 7))
    elif kind in ("cam_game", "gaming"):
        r = QRectF(cx - 7, cy - 10, 14, 20)
        p.drawRoundedRect(r, 3, 3)
        p.drawLine(QPointF(r.left(), cy - 3), QPointF(r.right(), cy - 3))
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 55))
        p.drawRect(QRectF(r.left() + 2, r.top() + 2, 10, 4))
    elif kind in ("cam_cinema", "cinema"):
        r = QRectF(cx - 7, cy - 10, 14, 20)
        p.drawRoundedRect(r, 3, 3)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 65))
        p.drawRect(QRectF(r.left() + 1, cy - 4, 12, 8))
    elif kind == "edu":
        p.drawRoundedRect(QRectF(cx - 9, cy - 7, 18, 13), 2.5, 2.5)
        p.drawLine(QPointF(cx - 5, cy - 2), QPointF(cx + 5, cy - 2))
        p.drawLine(QPointF(cx - 5, cy + 2), QPointF(cx + 2, cy + 2))
    elif kind == "music":
        p.drawLine(QPointF(cx - 3, cy + 5), QPointF(cx - 3, cy - 7))
        p.drawLine(QPointF(cx + 5, cy + 3), QPointF(cx + 5, cy - 9))
        p.drawLine(QPointF(cx - 3, cy - 7), QPointF(cx + 5, cy - 9))
        p.setBrush(color)
        p.drawEllipse(QRectF(cx - 7, cy + 3, 4.5, 4))
        p.drawEllipse(QRectF(cx + 1, cy + 1, 4.5, 4))
    elif kind == "ratio_9_16":
        p.drawRoundedRect(QRectF(cx - 6, cy - 10, 12, 20), 2.5, 2.5)
    elif kind == "ratio_16_9":
        p.drawRoundedRect(QRectF(cx - 10, cy - 6, 20, 12), 2.5, 2.5)
    elif kind == "ratio_1_1":
        p.drawRoundedRect(QRectF(cx - 8, cy - 8, 16, 16), 2.5, 2.5)
    elif kind == "ratio_4_5":
        p.drawRoundedRect(QRectF(cx - 7, cy - 9, 14, 18), 2.5, 2.5)
    elif kind == "ratio_custom":
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(cx - 9, cy - 8, 18, 16), 2.5, 2.5)
    elif kind == "sub_bold":
        f = QFont("Arial Black", 9, QFont.Weight.Black)
        p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "AB")
    elif kind == "sub_highlight":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FACC15"))
        p.drawRoundedRect(QRectF(cx - 11, cy - 7, 22, 14), 3.5, 3.5)
        p.setPen(QColor("#09090D"))
        p.setFont(QFont("Segoe UI Variable Display", 8, QFont.Weight.ExtraBold))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Aa")
    elif kind == "sub_karaoke":
        p.setFont(QFont("Impact", 9, QFont.Weight.Bold))
        p.setPen(QColor("#38BDF8"))
        p.drawText(QRectF(cx - 11, cy - 9, 12, 18), Qt.AlignmentFlag.AlignCenter, "A")
        p.setPen(color)
        p.drawText(QRectF(cx + 1, cy - 9, 11, 18), Qt.AlignmentFlag.AlignCenter, "a")
    elif kind == "sub_neon":
        p.setPen(QPen(QColor(34, 211, 238, 110), 3.2))
        p.drawRoundedRect(QRectF(cx - 10, cy - 7, 20, 14), 4, 4)
        p.setPen(QColor("#67E8F9"))
        p.setFont(QFont("Segoe UI Variable Display", 8, QFont.Weight.Bold))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Aa")
    elif kind == "sub_box":
        p.setPen(QPen(QColor("#52525B"), 1.0))
        p.setBrush(QColor("#050508"))
        p.drawRoundedRect(QRectF(cx - 11, cy - 7, 22, 14), 3, 3)
        p.setPen(QColor("#FAFAFA"))
        p.setFont(QFont("Segoe UI Variable Text", 8, QFont.Weight.Bold))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Aa")
    elif kind == "sub_minimal":
        p.setFont(QFont("Segoe UI Variable Text", 9, QFont.Weight.Medium))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "aa")
    elif kind == "sub_classic":
        f = QFont("Georgia", 9, QFont.Weight.Bold)
        f.setItalic(True)
        p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Aa")
    else:
        p.setFont(QFont("Segoe UI Variable Display", 9, QFont.Weight.ExtraBold))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Aa")
    p.restore()


class VisualCardOption(QFrame):
    clicked = pyqtSignal(str)

    def __init__(
        self,
        key: str,
        title: str,
        subtitle: str = "",
        icon_kind: str = "universal",
        accent: str = "#3B82F6",
        compact: bool = False,
        badge: str = "",
        card_height: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self.title_text = title
        self.subtitle_text = subtitle
        self.icon_kind = icon_kind
        self.accent = accent
        self.compact = compact
        self.badge_text = badge
        self._selected = False
        self._hovered = False
        self._pressed = False
        self._spring_scale: float = 1.0
        self._select_progress: float = 0.0
        self._hover_progress: float = 0.0
        self._spring_anim: QVariantAnimation | None = None
        self._select_anim: QVariantAnimation | None = None
        self._hover_anim: QVariantAnimation | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        min_h = card_height if card_height else (48 if compact else (64 if subtitle else 48))
        self.setMinimumHeight(min_h)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _animate_spring(
        self,
        target: float,
        start_val: float | None = None,
        duration: int = 260,
        curve: QEasingCurve.Type = QEasingCurve.Type.OutBack,
    ) -> None:
        if self._spring_anim and self._spring_anim.state() == QAbstractAnimation.State.Running:
            self._spring_anim.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(duration)
        s_val = float(self._spring_scale) if start_val is None else float(start_val)
        anim.setStartValue(s_val)
        anim.setEndValue(float(target))
        anim.setEasingCurve(curve)

        def _on_sval(v: Any) -> None:
            self._spring_scale = float(v)
            self.update()

        anim.valueChanged.connect(_on_sval)
        self._spring_anim = anim
        anim.start()

    def _animate_select(self, target: float) -> None:
        if self._select_anim and self._select_anim.state() == QAbstractAnimation.State.Running:
            self._select_anim.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(190)
        anim.setStartValue(float(self._select_progress))
        anim.setEndValue(float(target))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _on_sel_val(v: Any) -> None:
            self._select_progress = float(v)
            self.update()

        anim.valueChanged.connect(_on_sel_val)
        self._select_anim = anim
        anim.start()

    def _animate_hover(self, target: float) -> None:
        if self._hover_anim and self._hover_anim.state() == QAbstractAnimation.State.Running:
            self._hover_anim.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(150)
        anim.setStartValue(float(self._hover_progress))
        anim.setEndValue(float(target))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _on_hov_val(v: Any) -> None:
            self._hover_progress = float(v)
            self.update()

        anim.valueChanged.connect(_on_hov_val)
        self._hover_anim = anim
        anim.start()

    def set_selected(self, selected: bool, animated: bool = True) -> None:
        if self._selected != selected:
            self._selected = selected
            if animated:
                self._animate_select(1.0 if selected else 0.0)
                if selected:
                    # Bouncy elastic pop (kenyal) on selection
                    self._animate_spring(1.0, start_val=0.94, duration=280, curve=QEasingCurve.Type.OutBack)
                else:
                    self._animate_spring(1.0, duration=160, curve=QEasingCurve.Type.OutCubic)
            else:
                self._select_progress = 1.0 if selected else 0.0
                self._spring_scale = 1.0
                self.update()

    def enterEvent(self, event: Any) -> None:
        self._hovered = True
        self._animate_hover(1.0)
        if not self._selected and not self._pressed:
            self._animate_spring(1.02, duration=160, curve=QEasingCurve.Type.OutCubic)
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self._hovered = False
        self._pressed = False
        self._animate_hover(0.0)
        if not self._selected:
            self._animate_spring(1.0, duration=160, curve=QEasingCurve.Type.OutCubic)
        super().leaveEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._pressed = True
            # Tactile squish / press compression (kenyal)
            self._animate_spring(0.95, duration=80, curve=QEasingCurve.Type.OutQuad)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            is_inside = self.rect().contains(event.pos())
            self._pressed = False
            if is_inside:
                # Bouncy spring rebound
                self._animate_spring(1.0, duration=260, curve=QEasingCurve.Type.OutBack)
                self.clicked.emit(self.key)
            else:
                self._animate_spring(1.0, duration=150, curve=QEasingCurve.Type.OutCubic)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _title_font(self) -> QFont:
        if self.icon_kind == "sub_bold":
            return QFont("Arial Black", 9, QFont.Weight.Black)
        if self.icon_kind == "sub_karaoke":
            return QFont("Impact", 10, QFont.Weight.Bold)
        if self.icon_kind == "sub_classic":
            f = QFont("Georgia", 9, QFont.Weight.Bold)
            f.setItalic(True)
            return f
        if self.icon_kind == "sub_minimal":
            return QFont("Segoe UI Variable Text", 9, QFont.Weight.DemiBold)
        if self.icon_kind == "sub_neon":
            return QFont("Trebuchet MS", 9, QFont.Weight.Bold)
        return QFont("Segoe UI Variable Display", 9, QFont.Weight.Bold)

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        acc = QColor(self.accent)

        # Apply bouncy spring scale centered (kenyal)
        if abs(self._spring_scale - 1.0) > 0.001:
            cx = r.center().x()
            cy = r.center().y()
            p.translate(cx, cy)
            p.scale(self._spring_scale, self._spring_scale)
            p.translate(-cx, -cy)

        sp = self._select_progress
        hp = self._hover_progress

        # Smooth interpolated background
        bg_r = int(11 * (1.0 - sp) + (acc.red() * 0.18 + 11 * 0.82) * sp)
        bg_g = int(11 * (1.0 - sp) + (acc.green() * 0.18 + 11 * 0.82) * sp)
        bg_b = int(16 * (1.0 - sp) + (acc.blue() * 0.18 + 16 * 0.82) * sp)
        if hp > 0.01 and sp < 0.99:
            bg_r = int(bg_r * (1.0 - hp * 0.4) + (acc.red() * 0.1 + 11 * 0.9) * hp * 0.4)
            bg_g = int(bg_g * (1.0 - hp * 0.4) + (acc.green() * 0.1 + 11 * 0.9) * hp * 0.4)
            bg_b = int(bg_b * (1.0 - hp * 0.4) + (acc.blue() * 0.1 + 16 * 0.9) * hp * 0.4)
        bg = QColor(bg_r, bg_g, bg_b)

        # Smooth border interpolation
        bw = 1.0 + sp * 0.7
        b_r = int(31 * (1.0 - sp) + acc.red() * sp)
        b_g = int(31 * (1.0 - sp) + acc.green() * sp)
        b_b = int(43 * (1.0 - sp) + acc.blue() * sp)
        if hp > 0.01 and sp < 0.99:
            b_r = int(b_r * (1.0 - hp) + (acc.red() * 0.55 + 31 * 0.45) * hp)
            b_g = int(b_g * (1.0 - hp) + (acc.green() * 0.55 + 31 * 0.45) * hp)
            b_b = int(b_b * (1.0 - hp) + (acc.blue() * 0.55 + 43 * 0.45) * hp)
        border = QPen(QColor(b_r, b_g, b_b), bw)

        p.setBrush(bg)
        p.setPen(border)
        p.drawRoundedRect(r, 10.0, 10.0)

        # Icon box
        icon_box = QRectF(r.left() + 9, r.center().y() - 13, 26, 26)
        p.setPen(Qt.PenStyle.NoPen)
        box_alpha = int(18 * (1.0 - sp) + 48 * sp + hp * 12 * (1.0 - sp))
        p.setBrush(QColor(acc.red(), acc.green(), acc.blue(), box_alpha))
        p.drawRoundedRect(icon_box, 7.0, 7.0)

        icon_col = acc if (sp > 0.2 or hp > 0.3) else QColor("#A1A1AA")
        draw_preset_wireframe(p, icon_box, self.icon_kind, icon_col)

        # Title & Subtitle text
        text_left = int(icon_box.right() + 9)
        right_pad = 18 if sp > 0.2 else 8
        text_right = int(r.right() - right_pad)
        text_w = max(24, text_right - text_left)

        t_font = self._title_font()
        p.setFont(t_font)
        title_px_w = p.fontMetrics().horizontalAdvance(self.title_text)

        badge_drawn_left = text_right
        if self.badge_text and not self.compact:
            b_font = QFont("Segoe UI Variable Display", 7, QFont.Weight.ExtraBold)
            b_font.setPixelSize(8)
            p.setFont(b_font)
            bw = p.fontMetrics().horizontalAdvance(self.badge_text) + 8
            bh = 13
            bx = int(r.right() - bw - (18 if sp > 0.2 else 7))
            by = int(r.top() + 6)
            if bx > text_left + title_px_w + 6:
                badge_drawn_left = bx - 4
                p.setPen(Qt.PenStyle.NoPen)
                badge_alpha = int(35 * (1.0 - sp) + 65 * sp)
                p.setBrush(QColor(acc.red(), acc.green(), acc.blue(), badge_alpha))
                p.drawRoundedRect(QRectF(bx, by, bw, bh), 4.0, 4.0)
                p.setPen(acc.lighter(135) if sp > 0.2 else acc.lighter(115))
                p.drawText(QRect(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, self.badge_text)

        title_avail_w = max(24, badge_drawn_left - text_left)
        if self.subtitle_text:
            title_r = QRect(text_left, int(r.top() + 6), title_avail_w, 17)
            sub_r = QRect(text_left, int(r.top() + 23), text_w, int(r.height() - 26))
            p.setFont(t_font)
            if self.icon_kind == "sub_neon" and sp > 0.3:
                p.setPen(QColor("#67E8F9"))
            elif self.icon_kind == "sub_highlight" and sp > 0.3:
                p.setPen(QColor("#FDE047"))
            else:
                p.setPen(QColor("#FFFFFF") if sp > 0.3 else QColor("#F4F4F5"))
            p.drawText(title_r, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title_text)

            sub_font = QFont("Segoe UI Variable Text", 8, QFont.Weight.Normal)
            sub_font.setPixelSize(10)
            p.setFont(sub_font)
            p.setPen(QColor("#E2E8F0") if sp > 0.3 else QColor("#94A3B8"))
            p.drawText(sub_r, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self.subtitle_text)
        else:
            title_r = QRect(text_left, int(r.top()), title_avail_w, int(r.height()))
            p.setFont(t_font)
            p.setPen(QColor("#FFFFFF") if sp > 0.3 else QColor("#E4E4E7"))
            p.drawText(title_r, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title_text)

        # Active dot indicator with smooth pop-in
        if sp > 0.05:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(acc)
            dot_rad = 3.0 * min(1.0, sp * 1.2)
            p.drawEllipse(QRectF(r.right() - 13 - dot_rad, r.top() + 8 - dot_rad + 3.0, dot_rad * 2, dot_rad * 2))


class VisualCardSelector(QWidget):
    valueChanged = pyqtSignal(str)

    def __init__(
        self,
        items: list[tuple[Any, ...]],
        columns: int = 2,
        accent: str = "#3B82F6",
        compact: bool = False,
        cols: int | None = None,
        card_height: int | None = None,
        show_preview: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        _ = show_preview
        eff_cols = max(1, int(cols if cols is not None else columns))
        self._cards: dict[str, VisualCardOption] = {}
        self._value: str = str(items[0][0]) if items else ""
        self._bound_combo: QComboBox | None = None
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for idx, entry in enumerate(items):
            key = str(entry[0])
            title = str(entry[1]) if len(entry) > 1 else key
            subtitle = str(entry[2]) if len(entry) > 2 else ""
            icon_kind = str(entry[3]) if len(entry) > 3 else "universal"
            badge = str(entry[4]) if len(entry) > 4 else ""
            item_accent = str(entry[5]) if len(entry) > 5 and entry[5] else accent
            card = VisualCardOption(
                key,
                title,
                subtitle,
                icon_kind=icon_kind,
                accent=item_accent,
                compact=compact,
                badge=badge,
                card_height=card_height,
                parent=self,
            )
            card.clicked.connect(self._on_card_clicked)
            self._cards[key] = card
            grid.addWidget(card, idx // eff_cols, idx % eff_cols)
        for c in range(eff_cols):
            grid.setColumnStretch(c, 1)
        if self._value:
            self.set_value(self._value, emit=False, animated=False)

    def _on_card_clicked(self, key: str) -> None:
        self.set_value(key, emit=True, animated=True)

    def value(self) -> str:
        return self._value

    def set_value(self, key: str, emit: bool = False, animated: bool = True) -> None:
        if key not in self._cards:
            return
        self._value = key
        for k, card in self._cards.items():
            card.set_selected(k == key, animated=animated)
        if self._bound_combo is not None:
            idx = self._bound_combo.findData(key)
            if idx >= 0 and self._bound_combo.currentIndex() != idx:
                self._bound_combo.setCurrentIndex(idx)
        if emit:
            self.valueChanged.emit(key)

    def bind_combo(self, combo: QComboBox) -> None:
        self._bound_combo = combo
        cur = str(combo.currentData() or "")
        if cur in self._cards:
            self.set_value(cur, emit=False, animated=False)
        combo.currentIndexChanged.connect(self._on_combo_changed)

    def _on_combo_changed(self, _idx: int) -> None:
        if self._bound_combo is None:
            return
        cur = str(self._bound_combo.currentData() or "")
        if cur in self._cards and cur != self._value:
            self.set_value(cur, emit=False, animated=True)
        if cur in self._cards and cur != self._value:
            self.set_value(cur, emit=False)


class SegmentedPillBar(QFrame):
    valueChanged = pyqtSignal(object)

    def __init__(
        self,
        items: list[tuple[str, Any]],
        accent: str = "#3B82F6",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._items = items
        self._accent = accent
        self._current_idx = 0
        self._pill_x = 0.0
        self._pill_w = 0.0
        self._buttons: list[QPushButton] = []
        self._bound_combo: QComboBox | None = None
        self.setFixedHeight(36)
        self.setStyleSheet("background: transparent; border: none;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(3)
        for i, (label, _val) in enumerate(items):
            btn = QPushButton(label, self)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            btn.clicked.connect(lambda _checked=False, idx=i: self.set_index(idx, emit=True))
            self._buttons.append(btn)
            lay.addWidget(btn)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self._refresh_button_styles()

    def _on_anim(self, val: Any) -> None:
        self._pill_x = float(val)
        self.update()

    def _refresh_button_styles(self) -> None:
        for i, btn in enumerate(self._buttons):
            active = i == self._current_idx
            col = "#FFFFFF" if active else "#8E95A5"
            wt = "700" if active else "600"
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; color: {col}; font-size: 11.5px; font-weight: {wt}; padding: 0 6px; }}"
                f"QPushButton:hover {{ color: #FAFAFA; background: transparent; }}"
            )

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if 0 <= self._current_idx < len(self._buttons):
            b = self._buttons[self._current_idx]
            self._pill_x = float(b.x())
            self._pill_w = float(b.width())

    def set_index(self, idx: int, emit: bool = False) -> None:
        if not (0 <= idx < len(self._items)):
            return
        self._current_idx = idx
        self._refresh_button_styles()
        target_btn = self._buttons[idx]
        self._pill_w = float(target_btn.width())
        if emit and self.isVisible() and target_btn.width() > 0:
            self._anim.stop()
            self._anim.setStartValue(self._pill_x)
            self._anim.setEndValue(float(target_btn.x()))
            self._anim.start()
        else:
            self._anim.stop()
            self._pill_x = float(target_btn.x())
            self.update()
        val = self._items[idx][1]
        if self._bound_combo is not None:
            c_idx = self._bound_combo.findData(val)
            if c_idx >= 0 and self._bound_combo.currentIndex() != c_idx:
                self._bound_combo.setCurrentIndex(c_idx)
        if emit:
            self.valueChanged.emit(val)

    def bind_combo(self, combo: QComboBox) -> None:
        self._bound_combo = combo
        cur = combo.currentData()
        for i, (_lbl, v) in enumerate(self._items):
            if v == cur:
                self.set_index(i, emit=False)
                break
        combo.currentIndexChanged.connect(self._on_combo_changed)

    def _on_combo_changed(self, _idx: int) -> None:
        if self._bound_combo is None:
            return
        cur = self._bound_combo.currentData()
        for i, (_lbl, v) in enumerate(self._items):
            if v == cur and i != self._current_idx:
                self.set_index(i, emit=False)
                break

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QColor("#0B0B10"))
        p.setPen(QPen(QColor("#20202A"), 1))
        p.drawRoundedRect(r, 9.0, 9.0)
        if 0 <= self._current_idx < len(self._buttons):
            b = self._buttons[self._current_idx]
            pw = float(b.width()) if b.width() > 0 else (self.width() - 6) / max(1, len(self._buttons))
            px = self._pill_x if self._anim.state() == QAbstractAnimation.State.Running else float(b.x())
            acc = QColor(self._accent)
            pill_r = QRectF(px, 3.0, pw, float(self.height() - 6))
            p.setBrush(QColor(acc.red(), acc.green(), acc.blue(), 215))
            p.setPen(QPen(acc.lighter(115), 1))
            p.drawRoundedRect(pill_r, 7.0, 7.0)


class SettingToggleRow(QFrame):
    def __init__(
        self,
        title: str,
        subtitle: str = "",
        checked: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingToggleRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QFrame#settingToggleRow {
                background-color: #0B0B10;
                border: 1px solid #1E1E28;
                border-radius: 10px;
            }
            QFrame#settingToggleRow:hover {
                background-color: #12121A;
                border-color: #2E2E3E;
            }
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(10)

        txt_col = QVBoxLayout()
        txt_col.setContentsMargins(0, 0, 0, 0)
        txt_col.setSpacing(2)
        self.title_lbl = QLabel(title)
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setStyleSheet("color: #F4F4F5; font-size: 12px; font-weight: 600; background: transparent; border: none;")
        txt_col.addWidget(self.title_lbl)
        if subtitle:
            self.sub_lbl = QLabel(subtitle)
            self.sub_lbl.setWordWrap(True)
            self.sub_lbl.setStyleSheet("color: #71717A; font-size: 10.5px; background: transparent; border: none;")
            txt_col.addWidget(self.sub_lbl)
        lay.addLayout(txt_col, 1)

        self.switch = ToggleSwitch(self)
        self.switch.setChecked(checked)
        lay.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.switch.isEnabled():
            if not self.switch.geometry().contains(event.position().toPoint()):
                self.switch.setChecked(not self.switch.isChecked())
                event.accept()
                return
        super().mousePressEvent(event)


class VideoSurfaceWidget(QWidget):
    videoRectChanged = pyqtSignal(QRect)
    facesDetected = pyqtSignal(int, str)
    manualCropChanged = pyqtSignal(float, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sink = QVideoSink(self)
        self.current_frame: QImage | None = None
        self.sink.videoFrameChanged.connect(self.on_frame_changed)
        self.aspect_ratio_mode = Qt.AspectRatioMode.KeepAspectRatio
        self.video_rect = QRect()
        self.preview_mode: str = "auto_universal_9_16"
        self.manual_crop_x: float = 0.5
        self.manual_crop_y: float = 0.5
        self.manual_zoom: float = 1.0
        self.mirror_horizontal: bool = False
        self.color_boost_enabled: bool = False
        self.is_dragging_video: bool = False
        self._drag_start_pos: QPoint | None = None
        self._drag_start_crop_x: float = 0.5
        self._drag_start_crop_y: float = 0.5
        self.show_face_boxes: bool = False
        self.smoothed_faces: list[tuple[float, float, float, float]] = []
        self._last_detect_ts: float = 0.0
        self._last_face_count: int = -1
        self.setMouseTracking(True)

    def is_manual_framing(self) -> bool:
        return self.preview_mode in ("manual_crop", "manual_fit", "manual_ambient") or str(self.preview_mode).startswith("manual_")

    def set_preview_mode(self, mode: str) -> None:
        self.preview_mode = mode
        if self.is_manual_framing() and self.preview_mode != "manual_split":
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def set_manual_crop(self, x: float, y: float, zoom: float = 1.0) -> None:
        self.manual_crop_x = max(0.0, min(1.0, float(x)))
        self.manual_crop_y = max(0.0, min(1.0, float(y)))
        self.manual_zoom = max(0.20, min(3.00, float(zoom)))
        self.update()

    def set_manual_crop_x(self, val: float) -> None:
        self.manual_crop_x = max(0.0, min(1.0, float(val)))
        self.update()

    def set_manual_crop_y(self, val: float) -> None:
        self.manual_crop_y = max(0.0, min(1.0, float(val)))
        self.update()

    def set_manual_zoom(self, val: float) -> None:
        self.manual_zoom = max(0.20, min(3.00, float(val)))
        self.update()

    def mousePressEvent(self, event: Any) -> None:
        if self.is_manual_framing() and self.preview_mode != "manual_split" and event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging_video = True
            self._drag_start_pos = event.position().toPoint()
            self._drag_start_crop_x = self.manual_crop_x
            self._drag_start_crop_y = self.manual_crop_y
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self.is_manual_framing() and self.preview_mode != "manual_split":
            if self.is_dragging_video and self._drag_start_pos:
                delta = event.position().toPoint() - self._drag_start_pos
                w = max(20, self.width())
                h = max(20, self.height())
                span_x = max(20.0, float(w) * 0.8)
                span_y = max(20.0, float(h) * 0.8)
                self.manual_crop_x = max(0.0, min(1.0, self._drag_start_crop_x + (float(delta.x()) / span_x)))
                self.manual_crop_y = max(0.0, min(1.0, self._drag_start_crop_y + (float(delta.y()) / span_y)))
                self.manualCropChanged.emit(self.manual_crop_x, self.manual_crop_y, self.manual_zoom)
                self.update()
                event.accept()
                return
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        if self.is_manual_framing() and event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging_video = False
            self._drag_start_pos = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: Any) -> None:
        if self.is_manual_framing() and self.preview_mode != "manual_split":
            step = 0.05 if event.angleDelta().y() > 0 else -0.05
            self.manual_zoom = max(0.20, min(3.00, round(self.manual_zoom + step, 2)))
            self.manualCropChanged.emit(self.manual_crop_x, self.manual_crop_y, self.manual_zoom)
            self.update()
            event.accept()
            return
        super().wheelEvent(event)

    def set_show_face_boxes(self, show: bool) -> None:
        self.show_face_boxes = bool(show)
        self.update()

    def active_video_rect(self) -> QRect:
        if not self.video_rect.isEmpty():
            return self.video_rect
        return self.rect()

    def setAspectRatioMode(self, mode: Qt.AspectRatioMode) -> None:
        self.aspect_ratio_mode = mode
        self.update()

    def _run_realtime_face_tracker(self, qimg: QImage) -> None:
        import time

        now = time.monotonic()
        if (now - self._last_detect_ts) < 0.38:
            return
        self._last_detect_ts = now
        try:
            import cv2
            import numpy as np

            small = qimg.scaled(320, 180, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            small_rgba = small.convertToFormat(QImage.Format.Format_RGBA8888)
            sw, sh = small_rgba.width(), small_rgba.height()
            bpl = small_rgba.bytesPerLine()
            ptr = small_rgba.bits()
            ptr.setsize(sh * bpl)
            arr = np.frombuffer(ptr, np.uint8).reshape((sh, bpl // 4, 4))[:, :sw, :3]
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

            raw = core.detect_faces_robust(bgr, min_size=16, score_thresh=0.56)
            valid = core.filter_distinct_podcast_faces(raw, sw, sh, min_dist_ratio=0.10)
            norm_faces = [
                (fx / float(sw), fy / float(sh), fw / float(sw), fh / float(sh))
                for (fx, fy, fw, fh) in valid[:2]
            ]

            if not norm_faces:
                if getattr(self, "_empty_streak", 0) < 3 and self.smoothed_faces:
                    self._empty_streak = getattr(self, "_empty_streak", 0) + 1
                else:
                    self._empty_streak = 0
                    self.smoothed_faces = []
            else:
                self._empty_streak = 0
                if len(self.smoothed_faces) == len(norm_faces):
                    alpha = 0.35
                    self.smoothed_faces = [
                        (
                            old[0] * (1 - alpha) + cur[0] * alpha,
                            old[1] * (1 - alpha) + cur[1] * alpha,
                            old[2] * (1 - alpha) + cur[2] * alpha,
                            old[3] * (1 - alpha) + cur[3] * alpha,
                        )
                        for old, cur in zip(self.smoothed_faces, norm_faces)
                    ]
                else:
                    self.smoothed_faces = norm_faces

            f_count = len(self.smoothed_faces)
            if f_count != self._last_face_count:
                self._last_face_count = f_count
                if f_count == 0:
                    msg = "AI Kamera: 0 Wajah · Mode Sinematik Utuh"
                elif f_count == 1:
                    msg = "AI Kamera: 1 Subjek · Fokus Tengah Otomatis"
                else:
                    msg = f"AI Kamera: {f_count} Subjek · Split Atas-Bawah"
                self.facesDetected.emit(f_count, msg)
        except Exception:
            pass

    def on_frame_changed(self, frame: QVideoFrame) -> None:
        if frame.isValid():
            self.current_frame = frame.toImage()
            if self.current_frame and not self.current_frame.isNull():
                if self.preview_mode in ("auto_universal_9_16", "auto_podcast_9_16", "split_2_9_16", "crop_9_16") or self.show_face_boxes:
                    self._run_realtime_face_tracker(self.current_frame)
            self.update()

    def _draw_speaker_crop(
        self,
        p: QPainter,
        img: QImage,
        face_norm: tuple[float, float, float, float],
        dest_rect: QRect,
        label_text: str = "",
        has_real_face: bool = True,
    ) -> None:
        iw, ih = img.width(), img.height()
        fx, fy, fw, fh = face_norm
        cx = (fx + fw * 0.5) * iw
        cy = (fy + fh * 0.5) * ih
        dest_ar = dest_rect.width() / max(1.0, float(dest_rect.height()))

        if dest_ar < 0.8:
            crop_h = ih
            crop_w = min(iw, int(crop_h * dest_ar))
            sx = max(0, min(iw - crop_w, int(cx - crop_w * 0.5)))
            sy = 0
        else:
            crop_h = min(ih, max(int(fh * ih * 4.0), int(ih * 0.68)))
            crop_w = min(iw, int(crop_h * dest_ar))
            if crop_w >= iw:
                crop_w = iw
                crop_h = min(ih, int(crop_w / max(0.1, dest_ar)))
            sx = max(0, min(iw - crop_w, int(cx - crop_w * 0.5)))
            sy = max(0, min(ih - crop_h, int(cy - crop_h * 0.36)))

        sub_img = img.copy(sx, sy, max(16, crop_w), max(16, crop_h))
        scaled = sub_img.scaled(
            dest_rect.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        ox = max(0, (scaled.width() - dest_rect.width()) // 2)
        oy = max(0, (scaled.height() - dest_rect.height()) // 2)
        p.drawImage(dest_rect.topLeft(), scaled, QRect(ox, oy, dest_rect.width(), dest_rect.height()))

        if self.show_face_boxes and has_real_face and label_text:
            rel_fx = ((fx * iw - sx) / max(1.0, float(crop_w))) * dest_rect.width() + dest_rect.x()
            rel_fy = ((fy * ih - sy) / max(1.0, float(crop_h))) * dest_rect.height() + dest_rect.y()
            rel_fw = (fw * iw / max(1.0, float(crop_w))) * dest_rect.width()
            rel_fh = (fh * ih / max(1.0, float(crop_h))) * dest_rect.height()
            box_rect = QRect(int(rel_fx), int(rel_fy), int(rel_fw), int(rel_fh)).intersected(dest_rect.adjusted(4, 4, -4, -4))
            if box_rect.width() > 14 and box_rect.height() > 14:
                p.setPen(QPen(QColor(16, 185, 129, 210), 1.6, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(box_rect, 6, 6)

            badge_w = min(dest_rect.width() - 16, 150)
            badge_rect = QRect(dest_rect.x() + 8, dest_rect.y() + 8, badge_w, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(5, 5, 8, 205))
            p.drawRoundedRect(badge_rect, 5, 5)
            p.setPen(QColor("#34D399"))
            p.setFont(QFont("Segoe UI Variable Text", 8, QFont.Weight.Bold))
            p.drawText(badge_rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label_text)

    def _draw_ambient_cinema(self, p: QPainter, img: QImage, w: int, h: int) -> None:
        tiny = img.scaled(36, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.FastTransformation)
        bg = tiny.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        bx = max(0, (bg.width() - w) // 2)
        by = max(0, (bg.height() - h) // 2)
        p.drawImage(0, 0, bg, bx, by, w, h)
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 135))

        fg_w = int(w * 1.0)
        fg_h = max(40, int(fg_w * (img.height() / max(1.0, float(img.width())))))
        fg = img.scaled(fg_w, fg_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        fx = (w - fg.width()) // 2
        fy = (h - fg.height()) // 2
        new_rect = QRect(fx, fy, fg.width(), fg.height())
        if new_rect != self.video_rect:
            self.video_rect = new_rect
            self.videoRectChanged.emit(new_rect)
        p.drawImage(fx, fy, fg)

        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawLine(0, fy, w, fy)
        p.drawLine(0, fy + fg.height(), w, fy + fg.height())

        if self.show_face_boxes and self.smoothed_faces:
            for (nfx, nfy, nfw, nfh) in self.smoothed_faces:
                rx = fx + int(nfx * fg.width())
                ry = fy + int(nfy * fg.height())
                rw = int(nfw * fg.width())
                rh = int(nfh * fg.height())
                p.setPen(QPen(QColor(56, 189, 248, 210), 1.5, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rx, ry, rw, rh, 5, 5)

    def _apply_color_boost_overlay(self, p: QPainter, rect: QRect) -> None:
        if not self.color_boost_enabled:
            return
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SoftLight)
        p.fillRect(rect, QColor(245, 195, 145, 36))
        p.restore()

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#000000"))
        if not self.current_frame or self.current_frame.isNull() or w < 20 or h < 20:
            return

        img = self.current_frame.mirrored(True, False) if self.mirror_horizontal else self.current_frame
        is_portrait_canvas = h > w

        if self.preview_mode == "original_native":
            scaled = img.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            x = max(0, (w - scaled.width()) // 2)
            y = max(0, (h - scaled.height()) // 2)
            new_rect = QRect(x, y, min(w, scaled.width()), min(h, scaled.height()))
            if new_rect != self.video_rect:
                self.video_rect = new_rect
                self.videoRectChanged.emit(new_rect)
            p.drawImage(x, y, scaled)
            self._apply_color_boost_overlay(p, new_rect)
            return

        if is_portrait_canvas and self.preview_mode in ("ambient_9_16", "manual_ambient"):
            self._draw_ambient_cinema(p, img, w, h)
            self._apply_color_boost_overlay(p, self.rect())
            return

        if is_portrait_canvas and self.preview_mode == "manual_split":
            iw, ih = img.width(), img.height()
            half_h = h // 2
            top_rect = QRect(0, 0, w, half_h)
            bot_rect = QRect(0, half_h, w, h - half_h)
            sub_w = max(16, int(iw * 0.52))
            left_img = img.copy(max(0, int(iw * 0.04)), 0, min(iw - int(iw * 0.04), sub_w), ih)
            right_img = img.copy(max(0, int(iw * 0.44)), 0, min(iw - int(iw * 0.44), sub_w), ih)
            for src_sub, dst_r, lbl_txt in (
                (left_img, top_rect, "Panel Atas (Sisi Kiri)"),
                (right_img, bot_rect, "Panel Bawah (Sisi Kanan)"),
            ):
                sc = src_sub.scaled(dst_r.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                ox = max(0, (sc.width() - dst_r.width()) // 2)
                oy = max(0, (sc.height() - dst_r.height()) // 2)
                p.drawImage(dst_r.topLeft(), sc, QRect(ox, oy, dst_r.width(), dst_r.height()))
                badge_r = QRect(dst_r.x() + 8, dst_r.y() + 8, min(dst_r.width() - 16, 155), 20)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(5, 5, 8, 200))
                p.drawRoundedRect(badge_r, 5, 5)
                p.setPen(QColor("#FBBF24"))
                p.setFont(QFont("Segoe UI Variable Text", 8, QFont.Weight.Bold))
                p.drawText(badge_r.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl_txt)
            p.fillRect(0, half_h - 1, w, 3, QColor(0, 0, 0, 240))
            p.setPen(QPen(QColor(245, 158, 11, 170), 1))
            p.drawLine(0, half_h, w, half_h)
            self._apply_color_boost_overlay(p, self.rect())
            self.video_rect = QRect(0, 0, w, h)
            return

        if self.preview_mode in ("manual_crop", "manual_fit", "manual_ambient") or (
            self.is_manual_framing() and self.preview_mode not in ("auto_universal_9_16", "auto_podcast_9_16", "split_2_9_16", "crop_9_16", "facecam_9_16", "manual_split")
        ):
            if self.preview_mode in ("manual_ambient", "ambient_9_16"):
                tiny = img.scaled(36, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.FastTransformation)
                bg = tiny.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                bx = max(0, (bg.width() - w) // 2)
                by = max(0, (bg.height() - h) // 2)
                p.drawImage(0, 0, bg, bx, by, w, h)
                p.fillRect(0, 0, w, h, QColor(0, 0, 0, 135))
            else:
                p.fillRect(0, 0, w, h, QColor(0, 0, 0))

            if self.preview_mode == "manual_crop":
                base_scale = max(float(w) / max(1, img.width()), float(h) / max(1, img.height()))
            else:
                base_scale = min(float(w) / max(1, img.width()), float(h) / max(1, img.height()))

            z = max(0.20, min(3.00, self.manual_zoom))
            vw = max(10, int(round(img.width() * base_scale * z)))
            vh = max(10, int(round(img.height() * base_scale * z)))
            scaled = img.scaled(vw, vh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

            travel_x = max(abs(w - vw), int(w * 0.8))
            travel_y = max(abs(h - vh), int(h * 0.8))
            fx = int((w - vw) * 0.5 + (self.manual_crop_x - 0.5) * travel_x)
            fy = int((h - vh) * 0.5 + (self.manual_crop_y - 0.5) * travel_y)

            p.drawImage(fx, fy, scaled)
            self._apply_color_boost_overlay(p, QRect(fx, fy, vw, vh))

            p.setPen(QPen(QColor(56, 189, 248, 100), 1, Qt.PenStyle.DashLine))
            p.drawRect(fx, fy, vw, vh)

            badge_r = QRect(8, 8, min(w - 16, 265), 22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(5, 5, 8, 210))
            p.drawRoundedRect(badge_r, 6, 6)
            p.setPen(QColor("#FBBF24"))
            p.setFont(QFont("Cascadia Mono", 8, QFont.Weight.Bold))
            p.drawText(
                badge_r.adjusted(8, 0, -8, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"X {int(self.manual_crop_x * 100)}% · Y {int(self.manual_crop_y * 100)}% · {z:.2f}x",
            )
            self.video_rect = QRect(fx, fy, vw, vh)
            return

        if is_portrait_canvas and self.preview_mode in ("auto_universal_9_16", "auto_podcast_9_16", "split_2_9_16", "crop_9_16"):
            faces = self.smoothed_faces
            if len(faces) >= 2 and self.preview_mode in ("split_2_9_16", "auto_podcast_9_16", "auto_universal_9_16"):
                half_h = h // 2
                top_rect = QRect(0, 0, w, half_h)
                bot_rect = QRect(0, half_h, w, h - half_h)
                self._draw_speaker_crop(p, img, faces[0], top_rect, "Subjek 1", has_real_face=True)
                self._draw_speaker_crop(p, img, faces[1], bot_rect, "Subjek 2", has_real_face=True)
                p.fillRect(0, half_h - 1, w, 3, QColor(0, 0, 0, 240))
                p.setPen(QPen(QColor(59, 130, 246, 160), 1))
                p.drawLine(0, half_h, w, half_h)
                self._apply_color_boost_overlay(p, self.rect())
                self.video_rect = QRect(0, 0, w, h)
                return
            elif len(faces) == 1:
                full_rect = QRect(0, 0, w, h)
                self._draw_speaker_crop(p, img, faces[0], full_rect, "Fokus Subjek", has_real_face=True)
                self._apply_color_boost_overlay(p, full_rect)
                self.video_rect = full_rect
                return
            elif self.preview_mode == "crop_9_16":
                full_rect = QRect(0, 0, w, h)
                self._draw_speaker_crop(p, img, (0.38, 0.18, 0.24, 0.35), full_rect, "", has_real_face=False)
                self._apply_color_boost_overlay(p, full_rect)
                self.video_rect = full_rect
                return
            else:
                self._draw_ambient_cinema(p, img, w, h)
                self._apply_color_boost_overlay(p, self.rect())
                return

        target_size = self.size()
        scaled = img.scaled(
            target_size,
            self.aspect_ratio_mode,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (w - scaled.width()) // 2)
        y = max(0, (h - scaled.height()) // 2)
        new_rect = QRect(x, y, min(w, scaled.width()), min(h, scaled.height()))
        if new_rect != self.video_rect:
            self.video_rect = new_rect
            self.videoRectChanged.emit(new_rect)
        p.drawImage(x, y, scaled)
        self._apply_color_boost_overlay(p, new_rect)


class SafeZoneOverlayWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        if w < 40 or h < 40:
            return

        top_h = int(h * 0.11)
        bot_h = int(h * 0.17)
        right_w = int(w * 0.15)

        painter.fillRect(0, 0, w, top_h, QColor(0, 0, 0, 110))
        painter.fillRect(0, h - bot_h, w, bot_h, QColor(0, 0, 0, 120))
        painter.fillRect(w - right_w, top_h, right_w, h - top_h - bot_h, QColor(0, 0, 0, 95))

        safe_x = int(w * 0.05)
        safe_y = top_h + 2
        safe_w = max(10, (w - right_w) - safe_x - 2)
        safe_h = max(10, (h - bot_h) - safe_y - 2)

        painter.setPen(QPen(QColor(34, 211, 238, 165), 1.2, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(safe_x, safe_y, safe_w, safe_h, 8, 8)

        painter.setFont(QFont("Segoe UI Variable Text", 7, QFont.Weight.DemiBold))
        painter.setPen(QColor(161, 161, 170, 195))
        painter.drawText(QRect(safe_x, 2, safe_w, top_h - 4), Qt.AlignmentFlag.AlignCenter, "Area Header Aplikasi")
        painter.drawText(QRect(safe_x, h - bot_h + 4, safe_w, bot_h - 8), Qt.AlignmentFlag.AlignCenter, "Area Caption & Musik")

        for idx_c, cy_off in enumerate((22, 50, 78)):
            if top_h + cy_off + 16 < h - bot_h:
                painter.setPen(QPen(QColor(161, 161, 170, 130), 1))
                painter.setBrush(QColor(24, 24, 30, 160))
                painter.drawEllipse(w - right_w + (right_w - 18) // 2, top_h + cy_off, 18, 18)

        painter.setPen(QColor(34, 211, 238, 220))
        painter.drawText(QRect(safe_x + 8, safe_y + 4, safe_w - 16, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Area Aman Teks")


class SmartLayoutOverlayWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.face_mode: str = "1"

    def set_face_mode(self, mode: Any) -> None:
        self.face_mode = str(mode).strip()
        self.update()

    def paintEvent(self, event: Any) -> None:
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = self.width()
            h = self.height()
            if w < 40 or h < 40:
                return

            painter.fillRect(0, 0, w, h, QColor("#060609"))
            grid_pen = QPen(QColor(39, 39, 48, 90), 1, Qt.PenStyle.SolidLine)
            painter.setPen(grid_pen)
            painter.drawLine(w // 3, 0, w // 3, h)
            painter.drawLine((2 * w) // 3, 0, (2 * w) // 3, h)

            if self.face_mode == "2":
                half_y = h // 2
                painter.setPen(QPen(QColor(59, 130, 246, 140), 1.2, Qt.PenStyle.DashLine))
                painter.drawLine(8, half_y, w - 8, half_y)

            card_w = min(w - 28, 220)
            card_h = 64
            card_x = (w - card_w) // 2
            card_y = (h - card_h) // 2
            card_rect = QRect(card_x, card_y, card_w, card_h)
            painter.setBrush(QColor(14, 14, 20, 230))
            painter.setPen(QPen(QColor(39, 39, 50, 200), 1))
            painter.drawRoundedRect(card_rect, 12, 12)

            painter.setFont(QFont("Segoe UI Variable Display", 9, QFont.Weight.Bold))
            painter.setPen(QColor("#FAFAFA"))
            painter.drawText(
                QRect(card_x + 8, card_y + 10, card_w - 16, 18),
                Qt.AlignmentFlag.AlignCenter,
                "Pratinjau Studio",
            )
            painter.setFont(QFont("Segoe UI Variable Text", 8, QFont.Weight.Normal))
            painter.setPen(QColor("#71717A"))
            painter.drawText(
                QRect(card_x + 10, card_y + 30, card_w - 20, 26),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                "Pilih video untuk pratinjau langsung",
            )
        except Exception:
            pass


class DraggableFacecamBox(QWidget):
    cropChanged = pyqtSignal(float, float, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._drag_mode: str | None = None
        self._drag_start = QPoint()
        self._initial_geom = QRect()
        self.norm_x = 0.02
        self.norm_y = 0.04
        self.norm_w = 0.30
        self.norm_h = 0.30

    def _bounds_rect(self) -> QRect:
        parent = self.parentWidget()
        if parent is None:
            return QRect(0, 0, 200, 200)
        if hasattr(parent, "active_video_rect"):
            r = parent.active_video_rect()
            if r.width() >= 40 and r.height() >= 40:
                return r
        return parent.rect()

    def reset_to_default(self) -> None:
        self.apply_corner_preset("top_left")

    def apply_corner_preset(self, preset: str) -> None:
        presets = {
            "top_left": (0.02, 0.03, 0.30, 0.30),
            "top_right": (0.68, 0.03, 0.30, 0.30),
            "bottom_left": (0.02, 0.67, 0.30, 0.30),
            "bottom_right": (0.68, 0.67, 0.30, 0.30),
            "center_left": (0.02, 0.35, 0.30, 0.30),
            "center_right": (0.68, 0.35, 0.30, 0.30),
        }
        self.norm_x, self.norm_y, self.norm_w, self.norm_h = presets.get(preset, (0.02, 0.03, 0.30, 0.30))
        self.update_geometry_from_parent()
        self.cropChanged.emit(self.norm_x, self.norm_y, self.norm_w, self.norm_h)

    def update_geometry_from_parent(self) -> None:
        bounds = self._bounds_rect()
        bx, by, bw, bh = bounds.x(), bounds.y(), max(40, bounds.width()), max(30, bounds.height())
        gx = bx + int(self.norm_x * bw)
        gy = by + int(self.norm_y * bh)
        gw = max(40, int(self.norm_w * bw))
        gh = max(30, int(self.norm_h * bh))
        self.setGeometry(gx, gy, gw, gh)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, QColor(6, 182, 212, 45))
        pen = QPen(QColor(6, 182, 212, 235), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(1, 1, w - 2, h - 2)

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255, 240))
        painter.drawText(QRect(2, 2, w - 4, h - 4), Qt.AlignmentFlag.AlignCenter, "FACECAM CROP\n(Geser / Tarik Sudut)")

        painter.fillRect(w - 12, h - 12, 10, 10, QColor(6, 182, 212, 255))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self._drag_mode = "resize" if (pos.x() >= self.width() - 14 and pos.y() >= self.height() - 14) else "move"
            self._drag_start = event.globalPosition().toPoint()
            self._initial_geom = self.geometry()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        if self._drag_mode is None:
            if pos.x() >= self.width() - 14 and pos.y() >= self.height() - 14:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            super().mouseMoveEvent(event)
            return

        bounds = self._bounds_rect()
        bx, by, bw, bh = bounds.x(), bounds.y(), max(40, bounds.width()), max(30, bounds.height())
        diff = event.globalPosition().toPoint() - self._drag_start

        if self._drag_mode == "move":
            nx = max(bx, min(bx + bw - self.width(), self._initial_geom.x() + diff.x()))
            ny = max(by, min(by + bh - self.height(), self._initial_geom.y() + diff.y()))
            self.move(nx, ny)
        elif self._drag_mode == "resize":
            nw = max(45, min(bx + bw - self.x(), self._initial_geom.width() + diff.x()))
            nh = max(32, min(by + bh - self.y(), self._initial_geom.height() + diff.y()))
            self.resize(nw, nh)

        self.norm_x = max(0.0, min(1.0, (self.x() - bx) / float(bw)))
        self.norm_y = max(0.0, min(1.0, (self.y() - by) / float(bh)))
        self.norm_w = max(0.05, min(1.0 - self.norm_x, self.width() / float(bw)))
        self.norm_h = max(0.05, min(1.0 - self.norm_y, self.height() / float(bh)))
        self.cropChanged.emit(self.norm_x, self.norm_y, self.norm_w, self.norm_h)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_mode = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)


class ClipPreviewDialog(QDialog):
    def __init__(self, entries: list[dict[str, Any]], index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entries = entries
        self.index = index
        self.setWindowTitle("Preview clip")
        icon = get_app_icon()
        if icon:
            self.setWindowIcon(icon)
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
        self.time_label.setText(f"{format_time(position / 1000)} / {format_time(self.player.duration() / 1000)}")

    def update_preview_duration(self, duration: int) -> None:
        self.seek_slider.setRange(0, max(0, duration))
        self.seek_slider.setEnabled(duration > 0)
        self.time_label.setText(f"{format_time(self.player.position() / 1000)} / {format_time(duration / 1000)}")

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

    def __init__(
        self, job_id: str, options: core.CreateJobRequest, render: bool = False, source_path: str | None = None
    ) -> None:
        super().__init__()
        self.job_id = job_id
        self.options = options
        self.render = render
        self.source_path = source_path

    def run(self) -> None:
        try:
            from clipper_hud import launch_hud_process
            launch_hud_process()
        except Exception:
            pass
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


class YouTubeUploadWorker(QThread):
    finished_upload = pyqtSignal(bool, str)

    def __init__(self, video_path: Path | str, title: str, description: str = "") -> None:
        super().__init__()
        self.video_path = video_path
        self.title = title
        self.description = description

    def run(self) -> None:
        try:
            from omnichannel_publisher import upload_to_youtube_shorts, SESSION_YOUTUBE
            if not SESSION_YOUTUBE.is_file():
                self.finished_upload.emit(False, "Sesi YouTube belum login. Silakan login terlebih dahulu.")
                return
            success = upload_to_youtube_shorts(
                video_path=self.video_path,
                title=self.title,
                description=self.description,
                session_path=SESSION_YOUTUBE,
                headless=True,
            )
            if success:
                self.finished_upload.emit(True, "Klip berhasil dipublikasikan ke YouTube Shorts!")
            else:
                self.finished_upload.emit(False, "Gagal mengunggah video ke YouTube Shorts. Periksa koneksi atau sesi akun.")
        except Exception as exc:
            self.finished_upload.emit(False, f"Terjadi kesalahan saat upload: {exc}")


class YouTubeLoginWorker(QThread):
    finished_login = pyqtSignal(bool, str)

    def run(self) -> None:
        try:
            from omnichannel_publisher import save_platform_session
            ok = save_platform_session("youtube")
            if ok:
                self.finished_login.emit(True, "Login YouTube Studio berhasil disimpan!")
            else:
                self.finished_login.emit(False, "Login dibatalkan atau gagal.")
        except Exception as exc:
            self.finished_login.emit(False, f"Gagal membuka sesi login: {exc}")


class TikTokUploadWorker(QThread):
    finished_upload = pyqtSignal(bool, str)

    def __init__(self, video_path: Path | str, title: str, caption: str = "", hashtags: list[str] | None = None) -> None:
        super().__init__()
        self.video_path = Path(video_path)
        self.title = title
        self.caption = caption
        self.hashtags = hashtags or []

    def run(self) -> None:
        try:
            import auto_clipper_tiktok as act
            if not act.SESSION_FILE.is_file():
                self.finished_upload.emit(
                    False,
                    "Sesi TikTok belum login. Jalankan login TikTok terlebih dahulu.",
                )
                return
            full_caption = act.format_tiktok_caption(self.title, self.caption, self.hashtags, self.title)
            ok = act.upload_to_tiktok(
                video_path=self.video_path,
                caption=full_caption,
                session_path=act.SESSION_FILE,
                headless=False,
                use_tiktok_sound=True,
                sound_volume=0.08,
            )
            if ok:
                self.finished_upload.emit(
                    True,
                    f"Klip '{self.title}' berhasil dipublikasikan ke TikTok dengan sampul detik 1.8s, sound viral, & SEO 5 hashtag!",
                )
            else:
                self.finished_upload.emit(
                    False,
                    "Upload TikTok belum berhasil. Pastikan koneksi stabil dan sesi TikTok aktif.",
                )
        except Exception as exc:
            self.finished_upload.emit(False, f"Kesalahan saat upload ke TikTok: {exc}")


MODELS_CATALOG = [
    {
        "id": "qwen_0.5b",
        "name": "Qwen 2.5 0.5B Instruct",
        "badge": "GGUF Q4_K_M · ~397 MB",
        "type": "gguf",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "specs": "Rekomendasi: RAM 4 GB+ | CPU Dual-Core / Laptop Standar",
        "desc": "Model analisis super hemat daya, sangat cepat untuk deteksi momen menarik tanpa memberatkan laptop.",
    },
    {
        "id": "qwen_1.5b",
        "name": "Qwen 2.5 1.5B Instruct",
        "badge": "GGUF Q4_K_M · ~1.1 GB",
        "type": "gguf",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "specs": "Rekomendasi: RAM 8 GB+ | CPU 4-Core atau GPU 2-4 GB VRAM",
        "desc": "Keseimbangan ideal antara kecepatan rendering dan kecerdasan kontekstual memahami isi percakapan video.",
    },
    {
        "id": "qwen_7b",
        "name": "Qwen 2.5 7B Instruct",
        "badge": "GGUF Q4_K_M · ~4.7 GB",
        "type": "gguf",
        "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf",
        "specs": "Rekomendasi: RAM 16 GB+ | GPU RTX 6-8 GB+ VRAM",
        "desc": "Kualitas setara AI Cloud, penalaran mendalam, deteksi hook & punchline video yang sangat tajam.",
    },
    {
        "id": "whisper_small",
        "name": "Faster-Whisper Small",
        "badge": "CTranslate2 · ~460 MB",
        "type": "whisper",
        "filename": "faster-whisper-small",
        "url": "small",
        "specs": "Rekomendasi: RAM 4 GB+ | CPU 4-Core atau GPU 2 GB VRAM",
        "desc": "Speech-to-text akurat dan cepat untuk audio percakapan Bahasa Indonesia & Inggris sehari-hari.",
    },
    {
        "id": "whisper_medium",
        "name": "Faster-Whisper Medium",
        "badge": "CTranslate2 · ~1.5 GB",
        "type": "whisper",
        "filename": "faster-whisper-medium",
        "url": "medium",
        "specs": "Rekomendasi: RAM 8 GB+ | GPU 4 GB+ VRAM",
        "desc": "Presisi tinggi untuk transkripsi audio dengan musik latar belakang atau vokal bising.",
    },
]


class ModelDownloadWorker(QThread):
    progress_signal = pyqtSignal(str, int, str, str)
    finished_signal = pyqtSignal(str, bool, str)

    def __init__(self, model_id: str, model_type: str, url_or_name: str, target_file: Path) -> None:
        super().__init__()
        self.model_id = model_id
        self.model_type = model_type
        self.url_or_name = url_or_name
        self.target_file = target_file
        self._canceled = False

    def cancel(self) -> None:
        self._canceled = True

    def run(self) -> None:
        try:
            if self.model_type == "whisper":
                self.progress_signal.emit(self.model_id, 15, "Menyiapkan unduhan Whisper...", "")
                import faster_whisper
                faster_whisper.download_model(self.url_or_name)
                self.finished_signal.emit(self.model_id, True, "Model Whisper siap digunakan!")
                return

            import time
            import urllib.request

            tmp_file = self.target_file.with_suffix(".tmp")
            self.target_file.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(self.url_or_name, headers={"User-Agent": "Mozilla/5.0 ENCLip Downloader"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(tmp_file, "wb") as out_f:
                total_len = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                start_time = time.time()
                last_time = start_time
                chunk = 1024 * 1024

                while True:
                    if self._canceled:
                        out_f.close()
                        if tmp_file.exists():
                            try:
                                tmp_file.unlink()
                            except Exception:
                                pass
                        self.finished_signal.emit(self.model_id, False, "Unduhan dibatalkan.")
                        return

                    data = resp.read(chunk)
                    if not data:
                        break
                    downloaded += len(data)
                    out_f.write(data)

                    now = time.time()
                    if now - last_time >= 0.5:
                        pct = int((downloaded / total_len) * 100) if total_len > 0 else 0
                        speed = downloaded / max(now - start_time, 0.001)
                        spd_str = (
                            f"{speed / (1024 * 1024):.1f} MB/s" if speed >= 1024 * 1024 else f"{speed / 1024:.0f} KB/s"
                        )
                        sz_str = (
                            f"{downloaded / (1024 * 1024):.1f} MB / {total_len / (1024 * 1024):.1f} MB"
                            if total_len
                            else f"{downloaded / (1024 * 1024):.1f} MB"
                        )
                        self.progress_signal.emit(self.model_id, pct, sz_str, spd_str)
                        last_time = now

            if tmp_file.exists():
                if self.target_file.exists():
                    self.target_file.unlink()
                tmp_file.rename(self.target_file)
            self.finished_signal.emit(self.model_id, True, "Model berhasil dipasang!")
        except Exception as exc:
            tmp_file = self.target_file.with_suffix(".tmp")
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass
            self.finished_signal.emit(self.model_id, False, str(exc))


class DependencyInstallWorker(QThread):
    output_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def run(self) -> None:
        python_exe = sys.executable
        self.output_line.emit("=== MEMULAI SETUP ENVIRONMENT & INSTALASI DEPENDENSI ===")
        self.output_line.emit(f"Python: {python_exe}")

        for p in [core.MODEL_DIR, core.RAW_VIDEO_DIR, core.DATA_DIR]:
            try:
                p.mkdir(parents=True, exist_ok=True)
                self.output_line.emit(f"Direktori kerja siap: {p}")
            except Exception as _p_err:
                self.output_line.emit(f"Perhatian direktori {p}: {_p_err}")

        if not getattr(sys, "frozen", False):
            req_file = Path("requirements.txt")
            if not req_file.exists():
                req_file = Path(__file__).resolve().parent.parent / "requirements.txt"

            if req_file.exists():
                self.output_line.emit(f"Memasang paket dari {req_file}...")
                cmd = [python_exe, "-m", "pip", "install", "-r", str(req_file)]
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                    if proc.stdout:
                        for line in proc.stdout:
                            l = line.strip()
                            if l:
                                self.output_line.emit(l)
                    proc.wait()
                    if proc.returncode == 0:
                        self.output_line.emit("=== SEMUA DEPENDENSI BERHASIL DIPASANG ===")
                        self.finished.emit(True, "Semua dependensi Python berhasil dipasang dan diverifikasi!")
                        return
                    else:
                        self.finished.emit(False, f"Instalasi pip selesai dengan kode: {proc.returncode}")
                        return
                except Exception as exc:
                    self.output_line.emit(f"ERROR: {exc}")
                    self.finished.emit(False, str(exc))
                    return
        self.output_line.emit("=== ENVIRONMENT PORTABLE SIAP ===")
        self.finished.emit(True, "Lingkungan portabel dan direktori kerja telah siap digunakan!")


class HermesDesktop(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ENCLip Studio v3.0")
        icon = get_app_icon()
        if icon:
            self.setWindowIcon(icon)
        self.resize(1280, 780)
        self.setMinimumSize(980, 580)
        self.current_job_id: str | None = None
        self.current_options: core.CreateJobRequest | None = None
        self.worker: JobWorker | None = None
        self.metadata_worker: MetadataWorker | None = None
        self.manual_render_worker: ManualRenderWorker | None = None
        self.page_animation: QPropertyAnimation | None = None
        self._tab_anim_state: dict[QTabWidget, tuple[Any, QLabel | None, QWidget | None]] = {}
        self._bar_anims: dict[Any, QPropertyAnimation] = {}
        self._drawer_anim: QPropertyAnimation | None = None
        self._panel_anim: QPropertyAnimation | None = None
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
        self.hook_banner_free_x = 0.5
        self.hook_banner_free_y = 0.11
        self.lyrics_free_x = 0.15
        self.lyrics_free_y = 0.78
        self.watermark_free_x = 0.85
        self.watermark_free_y = 0.08
        self.review_is_unlocked = False

        self.tabs = QTabWidget()
        self.setup_tab = self.build_setup_tab()
        self.video_tab = self.build_video_tab()
        self.create_tab = self.build_create_tab()
        self.review_tab = self.build_review_tab()
        self.results_tab = self.build_results_tab()
        self.models_tab = self.build_models_tab()
        self.tutorial_tab = self.build_tutorial_tab()
        self.tabs.addTab(self.setup_tab, "Sistem")
        self.tabs.addTab(self.video_tab, "Pilih Video")
        self.tabs.addTab(self.create_tab, "Studio Klip")
        self.tabs.addTab(self.review_tab, "Review && Trim")
        self.tabs.addTab(self.results_tab, "Hasil Ekspor")
        self.tabs.addTab(self.models_tab, "Model AI")
        self.tabs.addTab(self.tutorial_tab, "Panduan")
        self.tabs.setTabEnabled(3, True)
        self.tabs.setTabEnabled(4, False)
        self.tabs.tabBar().hide()
        self.nav_buttons: dict[int, QPushButton] = {}
        self.model_download_workers: dict[str, ModelDownloadWorker] = {}
        self.dep_worker: DependencyInstallWorker | None = None

        central_container = QWidget()
        central_layout = QVBoxLayout(central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.tabs, 1)

        self.terminal_drawer = self.build_terminal_drawer()
        self.terminal_drawer.setVisible(False)
        central_layout.addWidget(self.terminal_drawer, 0)
        self.setCentralWidget(central_container)

        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setObjectName("topToolbar")

        brand_widget = QWidget()
        brand_layout = QHBoxLayout(brand_widget)
        brand_layout.setContentsMargins(6, 0, 10, 0)
        brand_layout.setSpacing(8)

        app_icon = get_app_icon()
        if app_icon:
            brand_icon_lbl = QLabel()
            brand_icon_lbl.setPixmap(app_icon.pixmap(22, 22))
            brand_icon_lbl.setStyleSheet("background: transparent;")
            brand_layout.addWidget(brand_icon_lbl)

        brand = QLabel(
            "<span style='color:#FFFFFF; font-weight:800; font-size:17px; letter-spacing:-0.4px;'>ENC</span>"
            "<span style='color:#3B82F6; font-weight:800; font-size:17px; letter-spacing:-0.4px;'>Lip</span>"
        )
        brand.setObjectName("brand")
        brand_layout.addWidget(brand)

        meta = QLabel("STUDIO")
        meta.setObjectName("brandMeta")
        meta.setStyleSheet(
            "color: #A1A1AA; background: #111116; border: 1px solid #24242F; "
            "border-radius: 5px; font-size: 9px; font-weight: 800; padding: 2px 6px; letter-spacing: 0.9px;"
        )
        brand_layout.addWidget(meta)
        toolbar.addWidget(brand_widget)

        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_left)

        nav_container = QFrame()
        nav_container.setObjectName("navPillTrack")
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(4, 3, 4, 3)
        nav_layout.setSpacing(4)
        for index, label in (
            (1, "1 · Pilih Video"),
            (2, "2 · Studio Klip"),
            (3, "3 · Review && Trim"),
            (4, "4 · Hasil Ekspor"),
        ):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, target=index: self.switch_tab(target))
            self.nav_buttons[index] = button
            nav_layout.addWidget(button)
        toolbar.addWidget(nav_container)

        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_right)

        right_tools = QWidget()
        right_layout = QHBoxLayout(right_tools)
        right_layout.setContentsMargins(0, 0, 6, 0)
        right_layout.setSpacing(5)

        sys_btn = QPushButton("● Sistem")
        sys_btn.setObjectName("navUtilButton")
        sys_btn.setCheckable(True)
        sys_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sys_btn.setToolTip("Status Lingkungan Sistem, FFmpeg & Folder Kerja")
        sys_btn.clicked.connect(lambda checked=False: self.switch_tab(0))
        self.nav_buttons[0] = sys_btn
        right_layout.addWidget(sys_btn)

        models_btn = QPushButton("Model AI")
        models_btn.setObjectName("navUtilButton")
        models_btn.setCheckable(True)
        models_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        models_btn.setToolTip("Kelola Model Whisper & LLM Offline")
        models_btn.clicked.connect(lambda checked=False: self.switch_tab(5))
        self.nav_buttons[5] = models_btn
        right_layout.addWidget(models_btn)

        self.hud_btn = QPushButton("HUD")
        self.hud_btn.setObjectName("navUtilButton")
        self.hud_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hud_btn.setToolTip("Buka Jendela Pemantau Render Real-Time")
        self.hud_btn.clicked.connect(self.open_live_hud)
        right_layout.addWidget(self.hud_btn)

        self.terminal_toggle_btn = QPushButton("Log")
        self.terminal_toggle_btn.setObjectName("navUtilButton")
        self.terminal_toggle_btn.setCheckable(True)
        self.terminal_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.terminal_toggle_btn.setToolTip("Tampilkan / Sembunyikan Log Proses")
        self.terminal_toggle_btn.clicked.connect(self.toggle_terminal_drawer)
        right_layout.addWidget(self.terminal_toggle_btn)

        guide_button = QPushButton("Panduan")
        guide_button.setObjectName("navUtilButton")
        guide_button.setCursor(Qt.CursorShape.PointingHandCursor)
        guide_button.setToolTip("Panduan Penggunaan ENCLip Studio")
        guide_button.setCheckable(True)
        guide_button.clicked.connect(lambda checked=False: self.switch_tab(6))
        self.nav_buttons[6] = guide_button
        right_layout.addWidget(guide_button)

        self.theme_label = QLabel("")
        self.theme_label.setVisible(False)
        self.theme_toggle = ToggleSwitch()
        self.theme_toggle.setChecked(True)
        self.theme_toggle.setVisible(False)
        self.theme_toggle.toggled.connect(self.toggle_theme)
        self.theme_button = QPushButton()
        self.theme_button.setVisible(False)

        toolbar.addWidget(right_tools)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_job)
        self.apply_theme(False)
        env_items = getattr(self, "_initial_env_items", None) or self.check_system_environment()
        core_ready = all(it.get("is_ok", True) for it in env_items if it.get("key") in ("python", "ffmpeg", "directories"))
        if 0 in self.nav_buttons:
            self.nav_buttons[0].setText("● Sistem" if core_ready else "▲ Sistem")
        self.switch_tab(1 if core_ready else 0)

    def check_system_environment(self) -> list[dict[str, Any]]:
        items = []

        is_frozen = getattr(sys, "frozen", False)
        py_type = "Portable Standalone EXE" if is_frozen else "Virtual Environment (Python)"
        py_ver = platform.python_version()
        items.append({
            "key": "python",
            "name": "Python Runtime & Interpreter",
            "status": "OK",
            "is_ok": True,
            "badge": "TERPASANG & SIAP",
            "color": "#10B981",
            "details": f"{py_type} v{py_ver} — Executable: {sys.executable}",
            "desc": "Inti runtime untuk mengeksekusi logika backend, AI orchestration, dan antarmuka desktop.",
        })

        ffmpeg_bin = None
        try:
            ffmpeg_cmd = core.ffmpeg_command()
            if ffmpeg_cmd:
                ffmpeg_bin = ffmpeg_cmd[0]
        except Exception:
            ffmpeg_bin = shutil.which("ffmpeg")

        ffmpeg_ok = False
        ffmpeg_ver_str = "Tidak Ditemukan"
        if ffmpeg_bin and Path(ffmpeg_bin).exists():
            ffmpeg_ok = True
            ffmpeg_ver_str = f"FFmpeg Engine ({Path(ffmpeg_bin).name})"
        elif ffmpeg_bin:
            ffmpeg_ok = True
            ffmpeg_ver_str = f"FFmpeg Engine ({ffmpeg_bin})"

        items.append({
            "key": "ffmpeg",
            "name": "FFmpeg Multimedia Engine",
            "status": "OK" if ffmpeg_ok else "MISSING",
            "is_ok": ffmpeg_ok,
            "badge": "TERPASANG & SIAP" if ffmpeg_ok else "BELUM TERDETEKSI",
            "color": "#10B981" if ffmpeg_ok else "#EF4444",
            "details": f"{ffmpeg_ver_str} — {ffmpeg_bin or 'Tidak ditemukan di PATH'}",
            "desc": "FFmpeg diperlukan untuk decoding video, pemotongan klip 9:16 / 16:9, dan penempelan subtitle.",
        })

        fw_ok = False
        fw_ver = "Belum terpasang"
        try:
            import faster_whisper
            fw_ok = True
            fw_ver = f"v{getattr(faster_whisper, '__version__', 'ready')}"
        except Exception as e:
            fw_ver = f"Error: {e}"

        items.append({
            "key": "whisper",
            "name": "Faster-Whisper (Audio Transcription)",
            "status": "OK" if fw_ok else "MISSING",
            "is_ok": fw_ok,
            "badge": "TERPASANG & SIAP" if fw_ok else "BELUM TERPASANG",
            "color": "#10B981" if fw_ok else "#F59E0B",
            "details": f"Faster-Whisper {fw_ver} (CTranslate2 Engine)",
            "desc": "Modul AI transkripsi suara ke teks dengan timestamp kata-per-kata presisi tinggi.",
        })

        yt_ok = False
        yt_ver = "Belum terpasang"
        try:
            import yt_dlp
            yt_ok = True
            v = getattr(getattr(yt_dlp, "version", None), "__version__", "ready")
            yt_ver = f"v{v}"
        except Exception as e:
            yt_ver = f"Error: {e}"

        items.append({
            "key": "ytdlp",
            "name": "yt-dlp Video Downloader",
            "status": "OK" if yt_ok else "MISSING",
            "is_ok": yt_ok,
            "badge": "TERPASANG & SIAP" if yt_ok else "BELUM TERPASANG",
            "color": "#10B981" if yt_ok else "#F59E0B",
            "details": f"yt-dlp {yt_ver}",
            "desc": "Modul pengunduh video YouTube, Shorts, dan platform online dengan pemilihan resolusi otomatis.",
        })

        gemini_key = core.get_active_gemini_api_key()
        models_dir = Path("Core_Data/models")
        if not models_dir.exists():
            models_dir = ROOT / "models"
        gguf_files = list(models_dir.glob("*.gguf")) if models_dir.exists() else []

        if gemini_key:
            ai_status_text = "Google Gemini Pro Cloud Terkonfigurasi (Vision & Q&A Engine Aktif)"
            ai_badge = "GEMINI CLOUD SIAP"
            ai_color = "#10B981"
        elif gguf_files:
            ai_status_text = f"Model AI Lokal Terdeteksi ({len(gguf_files)} model GGUF di folder models)"
            ai_badge = "MODEL LOKAL SIAP"
            ai_color = "#10B981"
        else:
            ai_status_text = "Tersedia Rule-Based Fallback (Kunci Gemini / Model Lokal dapat diset di tab Buat clip)"
            ai_badge = "READY (FALLBACK MODE)"
            ai_color = "#3B82F6"

        items.append({
            "key": "ai_engine",
            "name": "AI Intelligence & Vision Camera-Director",
            "status": "OK",
            "is_ok": True,
            "badge": ai_badge,
            "color": ai_color,
            "details": ai_status_text,
            "desc": "Menilai relevansi momen video, cropping subjek manusia otomatis, serta menyusun judul & caption.",
        })

        dir_ok = True
        dirs_created = []
        for d in [core.RAW_VIDEO_DIR, core.DATA_DIR, core.MODEL_DIR]:
            try:
                d.mkdir(parents=True, exist_ok=True)
                dirs_created.append(d.name)
            except Exception:
                dir_ok = False
        items.append({
            "key": "directories",
            "name": "Direktori Kerja & Penyimpanan Data",
            "status": "OK" if dir_ok else "ERROR",
            "is_ok": dir_ok,
            "badge": "FOLDER KERJA SIAP" if dir_ok else "GAGAL MEMBUAT",
            "color": "#10B981" if dir_ok else "#EF4444",
            "details": f"Folder kerja aktif: {core.DATA_DIR.parent}",
            "desc": "Penyimpanan video mentah yang diunduh, model AI lokal offline, dan hasil render klip.",
        })

        return items

    def create_setup_card(self, item: dict[str, Any]) -> QFrame:
        card = QFrame()
        card.setObjectName("setupCard")
        card.setStyleSheet("""
            QFrame#setupCard {
                background: #0A0A0F;
                border: 1px solid #1E1E28;
                border-radius: 12px;
            }
            QFrame#setupCard:hover {
                border-color: #2E2E3E;
                background: #0F0F16;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(item["name"])
        title_lbl.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #FAFAFA; background: transparent; border: none;")
        top_row.addWidget(title_lbl, 1)

        badge_lbl = QLabel(item["badge"])
        badge_lbl.setStyleSheet(f"""
            background: rgba(16, 185, 129, 0.14);
            border: 1px solid {item['color']};
            color: {item['color']};
            font-size: 10px;
            font-weight: 800;
            padding: 3px 9px;
            border-radius: 9px;
        """)
        top_row.addWidget(badge_lbl, 0)
        c_layout.addLayout(top_row)

        detail_lbl = QLabel(item["details"])
        detail_lbl.setWordWrap(True)
        detail_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 500; color: #A1A1AA; "
            "font-family: 'Cascadia Mono', 'Consolas', monospace; background: transparent; border: none;"
        )
        c_layout.addWidget(detail_lbl)

        desc_lbl = QLabel(item["desc"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 11px; color: #71717A; background: transparent; border: none;")
        c_layout.addWidget(desc_lbl)

        card.item_key = item["key"]
        card.title_lbl = title_lbl
        card.badge_lbl = badge_lbl
        card.detail_lbl = detail_lbl
        card.desc_lbl = desc_lbl
        return card

    def refresh_setup_status(self) -> None:
        items = self.check_system_environment()
        self._initial_env_items = items
        item_map = {it["key"]: it for it in items}

        all_ok = True
        for card in getattr(self, "setup_cards", []):
            k = getattr(card, "item_key", None)
            if k and k in item_map:
                it = item_map[k]
                card.badge_lbl.setText(it["badge"])
                card.badge_lbl.setStyleSheet(f"""
                    background: rgba(16, 185, 129, 0.14);
                    border: 1px solid {it['color']};
                    color: {it['color']};
                    font-size: 10px;
                    font-weight: 800;
                    padding: 3px 9px;
                    border-radius: 9px;
                """)
                card.detail_lbl.setText(it["details"])
                if not it.get("is_ok", True):
                    all_ok = False

        if hasattr(self, "nav_buttons") and 0 in self.nav_buttons:
            self.nav_buttons[0].setText("● Sistem" if all_ok else "▲ Sistem")

        if hasattr(self, "setup_summary_lbl"):
            if all_ok:
                self.setup_summary_lbl.setText("Seluruh komponen sistem, FFmpeg, dan folder penyimpanan siap digunakan.")
                self.setup_summary_lbl.setStyleSheet("color: #10B981; font-size: 12.5px; font-weight: 600; background: transparent; border: none;")
            else:
                self.setup_summary_lbl.setText(
                    "Beberapa komponen belum terdeteksi. Klik 'Perbarui Dependensi' di bawah untuk memasangnya otomatis."
                )
                self.setup_summary_lbl.setStyleSheet("color: #F59E0B; font-size: 12.5px; font-weight: 600; background: transparent; border: none;")

    def install_dependencies_in_background(self) -> None:
        if hasattr(self, "dep_worker") and self.dep_worker is not None and self.dep_worker.isRunning():
            QMessageBox.information(self, "Instalasi Berjalan", "Proses instalasi dependensi sedang berjalan di latar belakang.")
            return

        if not self.terminal_drawer.isVisible():
            self.toggle_terminal_drawer()

        self.log_terminal("Memulai instalasi dependensi di background...")
        if hasattr(self, "btn_setup_install"):
            self.btn_setup_install.setEnabled(False)
            self.btn_setup_install.setText("Memasang...")

        self.dep_worker = DependencyInstallWorker()
        self.dep_worker.output_line.connect(self.log_terminal)
        self.dep_worker.finished.connect(self.on_dep_install_finished)
        self.dep_worker.start()

    def on_dep_install_finished(self, success: bool, msg: str) -> None:
        if hasattr(self, "btn_setup_install"):
            self.btn_setup_install.setEnabled(True)
            self.btn_setup_install.setText("Perbarui Dependensi Otomatis")

        self.refresh_setup_status()
        if success:
            self.log_terminal(f"SUCCESS: {msg}")
            QMessageBox.information(self, "Sistem Siap", msg)
        else:
            self.log_terminal(f"FAILED: {msg}")
            QMessageBox.warning(self, "Pemeriksaan Sistem", msg)

    def build_setup_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        page = QWidget()
        page.setObjectName("pageContent")
        page.setMinimumWidth(860)
        page.setMaximumWidth(1160)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 24)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)

        eyebrow = QLabel("STATUS SISTEM & MODUL")
        eyebrow.setObjectName("eyebrow")
        header_text.addWidget(eyebrow)

        title = QLabel("Kesiapan Sistem & Mesin Render")
        title.setObjectName("title")
        header_text.addWidget(title)

        subtitle = QLabel("Status Python, FFmpeg, modul transkripsi, pengunduh video, dan lokasi folder kerja aktif.")
        subtitle.setStyleSheet("color: #71717A; font-size: 12.5px;")
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, 1)

        top_btn_row = QHBoxLayout()
        top_btn_row.setSpacing(8)

        btn_refresh_top = QPushButton("Periksa Ulang")
        btn_refresh_top.setObjectName("secondary")
        btn_refresh_top.setFixedHeight(36)
        btn_refresh_top.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh_top.clicked.connect(self.refresh_setup_status)
        top_btn_row.addWidget(btn_refresh_top)

        btn_next_top = QPushButton("Buka Pilih Video →")
        btn_next_top.setObjectName("primary")
        btn_next_top.setFixedHeight(36)
        btn_next_top.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next_top.clicked.connect(lambda: self.switch_tab(1))
        top_btn_row.addWidget(btn_next_top)

        header_row.addLayout(top_btn_row)
        layout.addLayout(header_row)

        self.setup_cards: list[QFrame] = []
        items = self.check_system_environment()
        self._initial_env_items = items
        cards_grid = QGridLayout()
        cards_grid.setContentsMargins(0, 0, 0, 0)
        cards_grid.setHorizontalSpacing(12)
        cards_grid.setVerticalSpacing(12)
        for idx_c, it in enumerate(items):
            card = self.create_setup_card(it)
            self.setup_cards.append(card)
            cards_grid.addWidget(card, idx_c // 2, idx_c % 2)
        cards_grid.setColumnStretch(0, 1)
        cards_grid.setColumnStretch(1, 1)
        layout.addLayout(cards_grid)

        bottom_box = QFrame()
        bottom_box.setStyleSheet("""
            QFrame {
                background: #0A0A0F;
                border: 1px solid #1E1E28;
                border-radius: 12px;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_box)
        bottom_layout.setContentsMargins(16, 14, 16, 14)
        bottom_layout.setSpacing(12)

        self.setup_summary_lbl = QLabel("Seluruh komponen sistem, FFmpeg, dan folder penyimpanan siap digunakan.")
        self.setup_summary_lbl.setStyleSheet("color: #10B981; font-size: 12.5px; font-weight: 600; background: transparent; border: none;")
        bottom_layout.addWidget(self.setup_summary_lbl, 1)

        self.btn_setup_install = QPushButton("Perbarui Dependensi Otomatis")
        self.btn_setup_install.setObjectName("secondary")
        self.btn_setup_install.setFixedHeight(36)
        self.btn_setup_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_setup_install.clicked.connect(self.install_dependencies_in_background)
        bottom_layout.addWidget(self.btn_setup_install)

        btn_models = QPushButton("Kelola Model AI")
        btn_models.setObjectName("secondary")
        btn_models.setFixedHeight(36)
        btn_models.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_models.clicked.connect(lambda: self.switch_tab(5))
        bottom_layout.addWidget(btn_models)

        layout.addWidget(bottom_box)
        layout.addStretch(1)
        scroll.setWidget(page)
        return scroll


    def set_framing_mode(self, mode: str) -> None:
        if mode not in ("none", "auto", "manual"):
            mode = "auto"
        self.framing_mode_state = mode
        if hasattr(self, "framing_mode_cards") and self.framing_mode_cards.value() != mode:
            self.framing_mode_cards.set_value(mode, emit=False)
        if hasattr(self, "none_framing_container"):
            self.none_framing_container.setVisible(mode == "none")
        if hasattr(self, "auto_framing_container"):
            self.auto_framing_container.setVisible(mode == "auto")
        if hasattr(self, "manual_framing_container"):
            self.manual_framing_container.setVisible(mode == "manual")
        self.on_unified_format_changed()

    def on_manual_crop_x_changed(self, value: int) -> None:
        ratio = max(0.0, min(1.0, value / 100.0))
        if hasattr(self, "manual_crop_x_val_lbl"):
            pos_txt = f"{value}%"
            if value < 45:
                pos_txt += " · Kiri"
            elif value > 55:
                pos_txt += " · Kanan"
            else:
                pos_txt += " · Tengah"
            self.manual_crop_x_val_lbl.setText(pos_txt)
        if hasattr(self, "create_preview_video"):
            self.create_preview_video.set_manual_crop_x(ratio)
        if hasattr(self, "video_widget"):
            self.video_widget.set_manual_crop_x(ratio)
        self.update_create_preview()

    def on_manual_crop_y_changed(self, value: int) -> None:
        ratio = max(0.0, min(1.0, value / 100.0))
        if hasattr(self, "manual_crop_y_val_lbl"):
            pos_txt = f"{value}%"
            if value < 45:
                pos_txt += " · Atas"
            elif value > 55:
                pos_txt += " · Bawah"
            else:
                pos_txt += " · Tengah"
            self.manual_crop_y_val_lbl.setText(pos_txt)
        if hasattr(self, "create_preview_video"):
            self.create_preview_video.set_manual_crop_y(ratio)
        if hasattr(self, "video_widget"):
            self.video_widget.set_manual_crop_y(ratio)
        self.update_create_preview()

    def on_manual_zoom_changed(self, value: int) -> None:
        zoom = max(0.20, min(3.0, value / 100.0))
        if hasattr(self, "manual_zoom_val_lbl"):
            self.manual_zoom_val_lbl.setText(f"{zoom:.2f}x")
        if hasattr(self, "create_preview_video"):
            self.create_preview_video.set_manual_zoom(zoom)
        if hasattr(self, "video_widget"):
            self.video_widget.set_manual_zoom(zoom)
        self.update_create_preview()

    def reset_manual_pan_zoom(self) -> None:
        if hasattr(self, "manual_crop_x_slider"):
            self.manual_crop_x_slider.setValue(50)
        if hasattr(self, "manual_crop_y_slider"):
            self.manual_crop_y_slider.setValue(50)
        if hasattr(self, "manual_zoom_slider"):
            self.manual_zoom_slider.setValue(100)

    def on_canvas_manual_crop_changed(self, x: float, y: float, zoom: float) -> None:
        vx = int(round(x * 100))
        vy = int(round(y * 100))
        vz = int(round(zoom * 100))
        if hasattr(self, "manual_crop_x_slider"):
            self.manual_crop_x_slider.blockSignals(True)
            self.manual_crop_x_slider.setValue(vx)
            self.manual_crop_x_slider.blockSignals(False)
            if hasattr(self, "manual_crop_x_val_lbl"):
                self.manual_crop_x_val_lbl.setText(f"{vx}% · {'Kiri' if vx < 45 else 'Kanan' if vx > 55 else 'Tengah'}")
        if hasattr(self, "manual_crop_y_slider"):
            self.manual_crop_y_slider.blockSignals(True)
            self.manual_crop_y_slider.setValue(vy)
            self.manual_crop_y_slider.blockSignals(False)
            if hasattr(self, "manual_crop_y_val_lbl"):
                self.manual_crop_y_val_lbl.setText(f"{vy}% · {'Atas' if vy < 45 else 'Bawah' if vy > 55 else 'Tengah'}")
        if hasattr(self, "manual_zoom_slider"):
            self.manual_zoom_slider.blockSignals(True)
            self.manual_zoom_slider.setValue(vz)
            self.manual_zoom_slider.blockSignals(False)
            if hasattr(self, "manual_zoom_val_lbl"):
                self.manual_zoom_val_lbl.setText(f"{zoom:.2f}x")

    def set_custom_ratio_preset(self, w: int, h: int) -> None:
        if hasattr(self, "custom_aspect_w") and hasattr(self, "custom_aspect_h"):
            self.custom_aspect_w.blockSignals(True)
            self.custom_aspect_h.blockSignals(True)
            self.custom_aspect_w.setValue(w)
            self.custom_aspect_h.setValue(h)
            self.custom_aspect_w.blockSignals(False)
            self.custom_aspect_h.blockSignals(False)
            self.on_custom_ratio_changed()

    def on_custom_ratio_changed(self) -> None:
        if hasattr(self, "custom_aspect_w") and hasattr(self, "custom_aspect_h"):
            w = self.custom_aspect_w.value()
            h = self.custom_aspect_h.value()
            if hasattr(self, "custom_ratio_desc_lbl"):
                self.custom_ratio_desc_lbl.setText(f"{w}:{h}")
            self.on_unified_format_changed()

    def choose_broll_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Video Ilustrasi (B-Roll)", str(Path.home()))
        if folder and hasattr(self, "broll_folder_edit"):
            self.broll_folder_edit.setText(folder)

    def clear_watermark_image(self) -> None:
        if hasattr(self, "watermark_image_edit"):
            self.watermark_image_edit.setText("")
        self.update_create_preview()

    def on_pre_manual_item_clicked(self, item: QListWidgetItem) -> None:
        row = self.pre_manual_list.row(item) if hasattr(self, "pre_manual_list") else -1
        segs = getattr(self, "pre_manual_segments", [])
        if 0 <= row < len(segs):
            seg = segs[row]
            s_sec = float(seg.get("start", 0.0))
            e_sec = float(seg.get("end", 0.0))
            if hasattr(self, "pre_manual_start_edit"):
                self.pre_manual_start_edit.setText(format_time(s_sec))
            if hasattr(self, "pre_manual_end_edit"):
                self.pre_manual_end_edit.setText(format_time(e_sec))
            if hasattr(self, "pre_manual_title_edit"):
                self.pre_manual_title_edit.setText(str(seg.get("title") or ""))
            self.seek_create_preview(int(s_sec * 1000))

    def update_selected_pre_manual_segment(self) -> None:
        if not hasattr(self, "pre_manual_list"):
            return
        row = self.pre_manual_list.currentRow()
        if not (0 <= row < len(self.pre_manual_segments)):
            self.add_pre_manual_segment()
            return
        start_val = parse_time(self.pre_manual_start_edit.text().strip())
        end_val = parse_time(self.pre_manual_end_edit.text().strip())
        if start_val is None or end_val is None or end_val <= start_val:
            QMessageBox.warning(self, "Rentang Waktu", "Pastikan waktu selesai lebih besar dari waktu mulai (contoh 00:15 sampai 01:05).")
            return
        title_txt = self.pre_manual_title_edit.text().strip() or f"Segmen Manual #{row + 1:02d}"
        self.pre_manual_segments[row] = {
            "start": round(start_val, 2),
            "end": round(end_val, 2),
            "title": title_txt,
        }
        self.refresh_pre_manual_list_ui()
        self.pre_manual_list.setCurrentRow(row)
        self.update_segment_estimate()

    def on_unified_format_changed(self) -> None:
        if not hasattr(self, "unified_format_combo"):
            return
        mode = getattr(self, "framing_mode_state", "auto")

        if mode == "none":
            if hasattr(self, "custom_ratio_widget"):
                self.custom_ratio_widget.setVisible(False)
            if hasattr(self, "manual_crop_pan_widget"):
                self.manual_crop_pan_widget.setVisible(False)
            if hasattr(self, "facecam_guide_box"):
                self.facecam_guide_box.setVisible(False)
            aspect_val = "original"
            framing_val = "original"
            layout_val = "original"
            sim_val = "0"
            prev_mode = "original_native"
            if hasattr(self, "format_mode_hint"):
                self.format_mode_hint.setText(
                    "<b>Tanpa Framing (Video Asli):</b> Rasio dan resolusi asli video dipertahankan utuh 1:1 tanpa pemotongan, "
                    "tanpa bar hitam tambahan, dan tanpa perpindahan kamera otomatis."
                )
        elif mode == "manual" and hasattr(self, "manual_style_combo") and hasattr(self, "manual_aspect_combo"):
            raw_aspect = str(self.manual_aspect_combo.currentData() or "9:16")
            is_custom = raw_aspect == "custom"
            if hasattr(self, "custom_ratio_widget"):
                self.custom_ratio_widget.setVisible(is_custom)
            if is_custom and hasattr(self, "custom_aspect_w") and hasattr(self, "custom_aspect_h"):
                aspect_val = f"{self.custom_aspect_w.value()}:{self.custom_aspect_h.value()}"
            else:
                aspect_val = raw_aspect

            m_style = str(self.manual_style_combo.currentData() or "manual_fit")
            manual_map = {
                "manual_ambient": ("ambient", "standard", "0", "manual_ambient"),
                "manual_crop": ("crop", "standard", "1", "manual_crop"),
                "manual_split": ("crop", "manual_split", "2", "manual_split"),
                "manual_facecam": ("fit", "facecam_top", "1", "facecam_9_16"),
                "manual_fit": ("fit", "standard", "0", "manual_fit"),
            }
            framing_val, layout_val, sim_val, prev_mode = manual_map.get(
                m_style, ("fit", "standard", "0", "manual_fit")
            )
            if hasattr(self, "manual_crop_pan_widget"):
                self.manual_crop_pan_widget.setVisible(m_style in ("manual_crop", "manual_fit", "manual_ambient"))
            if hasattr(self, "facecam_guide_box"):
                self.facecam_guide_box.setVisible(m_style == "manual_facecam")

            manual_desc_map = {
                "manual_fit": (
                    "<b>Fit Utuh (Latar Hitam):</b> Seluruh frame video tampil utuh di atas kanvas hitam bersih. "
                    "Tarik langsung video di kanvas kanan atau gunakan slider untuk mengatur posisi & skala."
                ),
                "manual_ambient": (
                    "<b>Sinema Blur:</b> Video utuh dipadukan dengan latar belakang blur halus. "
                    "Posisi dan ukuran video dapat digeser bebas secara langsung."
                ),
                "manual_crop": (
                    "<b>Crop Penuh:</b> Video mengisi seluruh bidang rasio yang dipilih. "
                    "Geser posisi X/Y atau scroll mouse di kanvas untuk menentukan area fokus."
                ),
                "manual_split": (
                    "<b>Split 2 Panel Statis:</b> Membagi sisi kiri video ke panel atas dan sisi kanan ke panel bawah secara tetap."
                ),
                "manual_facecam": (
                    "<b>Facecam Atas:</b> Menempatkan kotak kamera wajah di bagian atas dan layar utama di bawah."
                ),
            }
            if hasattr(self, "format_mode_hint"):
                self.format_mode_hint.setText(manual_desc_map.get(m_style, ""))
        else:
            if hasattr(self, "custom_ratio_widget"):
                self.custom_ratio_widget.setVisible(False)
            preset = str(self.unified_format_combo.currentData() or "auto_universal_9_16")
            mapping = {
                "auto_universal_9_16": ("9:16", "ambient", "auto_universal", "1", "auto_universal_9_16"),
                "auto_podcast_9_16": ("9:16", "crop", "auto_smart", "1", "auto_podcast_9_16"),
                "crop_9_16": ("9:16", "crop", "auto_single", "1", "crop_9_16"),
                "split_2_9_16": ("9:16", "crop", "auto_split", "2", "split_2_9_16"),
                "ambient_9_16": ("9:16", "ambient", "auto_cinema", "0", "ambient_9_16"),
                "facecam_9_16": ("9:16", "fit", "facecam_top", "1", "facecam_9_16"),
                "standard_16_9": ("16:9", "fit", "standard", "0", "standard_16_9"),
            }
            aspect_val, framing_val, layout_val, sim_val, prev_mode = mapping.get(
                preset, ("9:16", "ambient", "auto_universal", "1", "auto_universal_9_16")
            )
            if hasattr(self, "manual_crop_pan_widget"):
                self.manual_crop_pan_widget.setVisible(False)
            if hasattr(self, "facecam_guide_box"):
                self.facecam_guide_box.setVisible(preset == "facecam_9_16")

            desc_map = {
                "auto_universal_9_16": (
                    "<b>Adaptif Universal:</b> Cocok untuk semua jenis konten. Subjek manusia dilacak otomatis, "
                    "sedangkan layar tutorial, game, atau lanskap sinematik otomatis dijaga tetap utuh."
                ),
                "auto_podcast_9_16": (
                    "<b>Podcast & Dialog AI:</b> Otomatis beralih antara fokus 1 pembicara di tengah, "
                    "split 2 pembicara atas-bawah, atau tampilan utuh saat tidak ada wajah."
                ),
                "crop_9_16": (
                    "<b>Fokus 1 Subjek:</b> Kamera AI melacak dan mengunci satu subjek utama secara halus di tengah layar vertikal."
                ),
                "split_2_9_16": (
                    "<b>Split 2 Subjek:</b> Menempatkan dua pembicara di panel atas dan bawah secara proporsional."
                ),
                "facecam_9_16": (
                    "<b>Gaming & Stream:</b> Kamera reaksi/wajah di bagian atas dan tangkapan layar utama di bagian bawah."
                ),
                "ambient_9_16": (
                    "<b>Sinematik Utuh:</b> Menampilkan seluruh lebar video tanpa memotong sisi kiri-kanan dengan latar blur lembut."
                ),
            }
            if hasattr(self, "format_mode_hint"):
                self.format_mode_hint.setText(desc_map.get(preset, desc_map["auto_universal_9_16"]))

        if hasattr(self, "aspect_combo"):
            idx_asp = self.aspect_combo.findData(aspect_val)
            if idx_asp < 0:
                self.aspect_combo.addItem(f"{aspect_val}", aspect_val)
                idx_asp = self.aspect_combo.findData(aspect_val)
            self.aspect_combo.blockSignals(True)
            self.aspect_combo.setCurrentIndex(idx_asp)
            self.aspect_combo.blockSignals(False)

        for combo_w, val in (
            (self.framing_combo, framing_val),
            (self.layout_combo, layout_val),
            (self.smart_preview_sim_combo, sim_val),
        ):
            idx = combo_w.findData(val)
            if idx < 0:
                combo_w.addItem(str(val), val)
                idx = combo_w.findData(val)
            combo_w.blockSignals(True)
            if idx >= 0:
                combo_w.setCurrentIndex(idx)
            combo_w.blockSignals(False)

        crop_x_ratio = (self.manual_crop_x_slider.value() / 100.0) if hasattr(self, "manual_crop_x_slider") else 0.5
        crop_y_ratio = (self.manual_crop_y_slider.value() / 100.0) if hasattr(self, "manual_crop_y_slider") else 0.5
        crop_zoom_val = (self.manual_zoom_slider.value() / 100.0) if hasattr(self, "manual_zoom_slider") else 1.0
        if hasattr(self, "create_preview_video"):
            self.create_preview_video.set_manual_crop(crop_x_ratio, crop_y_ratio, crop_zoom_val)
            self.create_preview_video.set_preview_mode(prev_mode)
        if hasattr(self, "video_widget"):
            self.video_widget.set_manual_crop(crop_x_ratio, crop_y_ratio, crop_zoom_val)
            self.video_widget.set_preview_mode(prev_mode)

        self.update_create_preview()

    def on_subtab_bar_clicked(self, target_idx: int) -> None:
        if not hasattr(self, "create_subtabs"):
            return
        from_idx = self.create_subtabs.currentIndex()
        if target_idx == from_idx or target_idx < 0:
            return
        self.animate_tab_transition(self.create_subtabs, from_idx, target_idx, duration_ms=150)

    def on_subtab_changed(self, idx: int) -> None:
        if not hasattr(self, "create_subtabs"):
            return
        w = self.create_subtabs.widget(idx)
        if w is None:
            return
        w.update()

    def on_live_faces_detected(self, count: int, msg: str) -> None:
        if hasattr(self, "smart_detected_badge"):
            self.smart_detected_badge.setText(msg)

    def build_create_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("pageContent")

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(16, 8, 16, 12)
        page_layout.setSpacing(0)

        self.create_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.create_splitter.setObjectName("mainSplitter")
        self.create_splitter.setChildrenCollapsible(False)
        self.create_splitter.setHandleWidth(10)
        page_layout.addWidget(self.create_splitter)

        left_column_container = QWidget()
        left_column_container.setMinimumWidth(360)
        left_column_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_column_container.setStyleSheet("background: transparent;")
        left_outer_layout = QVBoxLayout(left_column_container)
        left_outer_layout.setContentsMargins(0, 0, 8, 0)
        left_outer_layout.setSpacing(8)

        # PROMINENT TOP MENU: MODE OTOMATIS AI vs CLIPPING MANUAL MULTI-SEGMEN
        top_mode_card = QFrame()
        top_mode_card.setObjectName("topModeMenuCard")
        top_mode_card.setStyleSheet(
            "QFrame#topModeMenuCard { background: #09090D; border: 1px solid #1E1E28; border-radius: 12px; }"
        )
        tm_lay = QVBoxLayout(top_mode_card)
        tm_lay.setContentsMargins(12, 10, 12, 10)
        tm_lay.setSpacing(7)

        tm_hdr = QHBoxLayout()
        tm_hdr.setSpacing(8)
        tm_title = QLabel("PILIH METODE PEMBUATAN KLIP")
        tm_title.setStyleSheet("font-size: 10.5px; font-weight: 800; color: #A1A1AA; letter-spacing: 0.9px; background: transparent; border: none;")
        tm_hdr.addWidget(tm_title)
        tm_hdr.addStretch()
        live_pill = QLabel("● PRATINJAU LANGSUNG")
        live_pill.setStyleSheet(
            "color: #34D399; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.32); "
            "border-radius: 6px; padding: 2px 8px; font-size: 9.5px; font-weight: 800;"
        )
        tm_hdr.addWidget(live_pill)
        tm_lay.addLayout(tm_hdr)

        self.top_clip_mode_cards = VisualCardSelector(
            [
                ("auto", "Mode Otomatis", "Pilih Momen AI, Bagi Jumlah, atau Bagi Durasi", "ai_spark", "3 METODE", "#3B82F6"),
                ("manual", "Mode Manual", "Potong bebas multi-segmen langsung dari video", "scissors", "MULTI-SEGMEN", "#F59E0B"),
            ],
            columns=2,
            accent="#3B82F6",
            card_height=58,
        )
        self.top_clip_mode_cards.valueChanged.connect(self.set_clipping_mode_quick)
        tm_lay.addWidget(self.top_clip_mode_cards)

        self.top_clip_mode_desc = QLabel(
            "<b>Mode Otomatis:</b> Tersedia 3 cara otomatis: <b>Otomatis AI (Momen Terbaik)</b>, "
            "<b>Bagi Rata Jumlah Klip</b>, atau <b>Bagi Berdasarkan Durasi Detik</b>."
        )
        self.top_clip_mode_desc.setWordWrap(True)
        self.top_clip_mode_desc.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.top_clip_mode_desc.setMinimumWidth(100)
        self.top_clip_mode_desc.setStyleSheet(
            "color: #D4D4D8; font-size: 11px; background: #07070C; border: 1px solid #1E293B; border-radius: 8px; padding: 6px 10px;"
        )
        tm_lay.addWidget(self.top_clip_mode_desc)
        left_outer_layout.addWidget(top_mode_card)

        # Hidden backing combos for full compatibility with build_options() & backend
        self.aspect_combo = self.combo([
            ("Asli", "original"),
            ("9:16", "9:16"),
            ("16:9", "16:9"),
            ("1:1", "1:1"),
            ("4:5", "4:5"),
            ("4:3", "4:3"),
            ("21:9", "21:9"),
        ], selected=1)
        self.framing_combo = self.combo([
            ("Asli", "original"),
            ("Sinema Blur", "ambient"),
            ("Fit Utuh", "fit"),
            ("Crop Penuh", "crop"),
        ], selected=1)
        self.layout_combo = self.combo([
            ("Asli", "original"),
            ("Adaptif Universal", "auto_universal"),
            ("Podcast AI", "auto_smart"),
            ("Fokus 1 Subjek", "auto_single"),
            ("Split 2 Subjek", "auto_split"),
            ("Sinematik Utuh", "auto_cinema"),
            ("Podcast Split", "podcast_split"),
            ("Manual Split", "manual_split"),
            ("Standar", "standard"),
            ("Facecam Atas", "facecam_top"),
        ], selected=1)
        self.smart_preview_sim_combo = self.combo([
            ("1", "1"),
            ("2", "2"),
            ("0", "0"),
        ], selected=0)
        for hidden_c in (self.aspect_combo, self.framing_combo, self.layout_combo, self.smart_preview_sim_combo):
            hidden_c.setVisible(False)

        def section_lbl(txt: str) -> QLabel:
            lb = QLabel(txt)
            lb.setStyleSheet("color: #A1A1AA; font-size: 11px; font-weight: 700; letter-spacing: 0.2px; background: transparent; border: none;")
            return lb

        def make_toggle_row(title: str, sub: str = "", checked: bool = False) -> tuple[SettingToggleRow, ToggleSwitch]:
            row_w = SettingToggleRow(title, sub, checked=checked)
            return row_w, row_w.switch

        # =========================================================================
        # SUBTAB 2: RASIO & FRAMING (TANPA FRAMING | OTOMATIS AI | MANUAL BEBAS)
        # =========================================================================
        t_frame_widget = QWidget()
        t1_layout = QVBoxLayout(t_frame_widget)
        t1_layout.setContentsMargins(6, 10, 12, 12)
        t1_layout.setSpacing(12)

        settings = QGroupBox("Rasio Kanvas && Gaya Kamera")
        video_v = QVBoxLayout(settings)
        video_v.setContentsMargins(12, 14, 12, 12)
        video_v.setSpacing(10)

        self.framing_mode_state = "auto"
        video_v.addWidget(section_lbl("Mode Framing Video"))
        self.framing_mode_cards = VisualCardSelector(
            [
                ("none", "Tanpa Framing", "Rasio & ukuran asli utuh", "frame_none"),
                ("auto", "Otomatis AI", "Kamera adaptif pintar", "frame_auto"),
                ("manual", "Manual Bebas", "Rasio kustom, geser & skala", "frame_manual"),
            ],
            columns=3,
            accent="#3B82F6",
        )
        self.framing_mode_cards.set_value("auto", emit=False)
        self.framing_mode_cards.valueChanged.connect(self.set_framing_mode)
        video_v.addWidget(self.framing_mode_cards)

        # Panel 0: Tanpa Framing (Asli)
        self.none_framing_container = QWidget()
        none_lay = QVBoxLayout(self.none_framing_container)
        none_lay.setContentsMargins(0, 2, 0, 0)
        none_info = QLabel(
            "Video diekspor sesuai resolusi dan rasio asli sumber tanpa pemotongan, "
            "tanpa latar blur tambahan, dan tanpa perpindahan kamera otomatis."
        )
        none_info.setWordWrap(True)
        none_info.setStyleSheet(
            "color: #E4E4E7; background: #0B0B10; border: 1px solid #22222E; border-radius: 9px; padding: 9px 11px; font-size: 11.5px;"
        )
        none_lay.addWidget(none_info)
        self.none_framing_container.setVisible(False)
        video_v.addWidget(self.none_framing_container)

        # Panel 1: Framing Otomatis AI (Universal + Podcast)
        self.auto_framing_container = QWidget()
        auto_lay = QVBoxLayout(self.auto_framing_container)
        auto_lay.setContentsMargins(0, 2, 0, 0)
        auto_lay.setSpacing(8)

        auto_lay.addWidget(section_lbl("Gaya Kamera AI (Vertikal 9:16)"))
        self.unified_format_combo = self.combo([
            ("Adaptif Universal", "auto_universal_9_16"),
            ("Podcast & Dialog AI", "auto_podcast_9_16"),
            ("Fokus 1 Subjek", "crop_9_16"),
            ("Split 2 Subjek", "split_2_9_16"),
            ("Gaming & Facecam", "facecam_9_16"),
            ("Sinematik Utuh", "ambient_9_16"),
        ], selected=0)
        self.unified_format_combo.setVisible(False)
        self.unified_format_combo.currentIndexChanged.connect(self.on_unified_format_changed)

        self.auto_cam_cards = VisualCardSelector(
            [
                ("auto_universal_9_16", "Adaptif Universal", "Semua konten: subjek fokus, layar utuh", "cam_adapt"),
                ("auto_podcast_9_16", "Podcast & Dialog", "1 orang fokus, 2 orang split otomatis", "cam_split"),
                ("crop_9_16", "Fokus 1 Subjek", "Kunci 1 pembicara utama di tengah", "cam_focus"),
                ("split_2_9_16", "Split 2 Panel", "2 pembicara atas & bawah proporsional", "cam_split"),
                ("facecam_9_16", "Gaming & Stream", "Kamera wajah atas + layar utama bawah", "cam_game"),
                ("ambient_9_16", "Sinematik Utuh", "Tampilan lebar utuh + latar blur halus", "cam_cinema"),
            ],
            columns=2,
            accent="#3B82F6",
        )
        self.auto_cam_cards.bind_combo(self.unified_format_combo)
        auto_lay.addWidget(self.auto_cam_cards)

        fb_row, self.realtime_face_box_check = make_toggle_row(
            "Tampilkan Garis Pelacak Subjek di Pratinjau",
            "Menampilkan indikator posisi subjek saat video diputar (hanya di pratinjau).",
            checked=False,
        )
        self.realtime_face_box_check.toggled.connect(
            lambda checked: self.create_preview_video.set_show_face_boxes(checked) if hasattr(self, "create_preview_video") else None
        )
        auto_lay.addWidget(fb_row)

        tracker_row = QHBoxLayout()
        tracker_row.setSpacing(8)
        self.smart_detected_badge = QLabel("Pelacak Subjek AI siap · Putar video untuk analisis langsung")
        self.smart_detected_badge.setWordWrap(True)
        self.smart_detected_badge.setStyleSheet(
            "color: #34D399; background: #071914; border: 1px solid #065F46; border-radius: 8px; padding: 7px 10px; font-size: 11.5px; font-weight: 600;"
        )
        tracker_row.addWidget(self.smart_detected_badge, 1)

        self.btn_detect_frame_faces = QPushButton("Cek Subjek")
        self.btn_detect_frame_faces.setObjectName("secondary")
        self.btn_detect_frame_faces.setFixedHeight(34)
        self.btn_detect_frame_faces.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_detect_frame_faces.clicked.connect(self.detect_faces_in_current_preview_frame)
        tracker_row.addWidget(self.btn_detect_frame_faces)
        auto_lay.addLayout(tracker_row)
        video_v.addWidget(self.auto_framing_container)

        # Panel 2: Framing Manual Bebas
        self.manual_framing_container = QWidget()
        man_lay = QVBoxLayout(self.manual_framing_container)
        man_lay.setContentsMargins(0, 2, 0, 0)
        man_lay.setSpacing(9)

        self.manual_aspect_combo = self.combo([
            ("9:16 Vertikal", "9:16"),
            ("16:9 Lanskap", "16:9"),
            ("1:1 Persegi", "1:1"),
            ("4:5 Feed", "4:5"),
            ("4:3 Klasik", "4:3"),
            ("21:9 Sinema", "21:9"),
            ("Rasio Kustom", "custom"),
        ], selected=0)
        self.manual_aspect_combo.setVisible(False)
        self.manual_aspect_combo.currentIndexChanged.connect(self.on_unified_format_changed)

        man_lay.addWidget(section_lbl("Rasio Kanvas Output"))
        self.manual_aspect_cards = VisualCardSelector(
            [
                ("9:16", "9:16 Vertikal", "TikTok / Reels / Shorts", "ratio_9_16"),
                ("16:9", "16:9 Lanskap", "YouTube / Layar Lebar", "ratio_16_9"),
                ("1:1", "1:1 Persegi", "Feed Persegi", "ratio_1_1"),
                ("4:5", "4:5 Portrait", "Instagram Feed", "ratio_4_5"),
                ("21:9", "21:9 Sinema", "Ultrawide Sinematik", "ratio_16_9"),
                ("custom", "Rasio Kustom", "Atur Lebar : Tinggi bebas", "ratio_custom"),
            ],
            columns=3,
            accent="#F59E0B",
            compact=True,
        )
        self.manual_aspect_cards.bind_combo(self.manual_aspect_combo)
        man_lay.addWidget(self.manual_aspect_cards)

        self.custom_ratio_widget = QWidget()
        cr_lay = QVBoxLayout(self.custom_ratio_widget)
        cr_lay.setContentsMargins(0, 0, 0, 0)
        cr_box = QFrame()
        cr_box.setStyleSheet("background: #0B0B10; border: 1px solid #272732; border-radius: 9px;")
        cr_box_lay = QHBoxLayout(cr_box)
        cr_box_lay.setContentsMargins(10, 7, 10, 7)
        cr_box_lay.setSpacing(6)
        cr_lbl = QLabel("Lebar : Tinggi")
        cr_lbl.setStyleSheet("color: #E4E4E7; font-size: 11.5px; font-weight: 600; border: none;")
        cr_box_lay.addWidget(cr_lbl)

        self.custom_aspect_w = FocusOnlySpinBox()
        self.custom_aspect_w.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.custom_aspect_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.custom_aspect_w.setRange(1, 9999)
        self.custom_aspect_w.setValue(9)
        self.custom_aspect_w.setFixedWidth(56)
        self.custom_aspect_w.setFixedHeight(30)
        self.custom_aspect_w.valueChanged.connect(self.on_custom_ratio_changed)
        cr_box_lay.addWidget(self.custom_aspect_w)

        colon_lbl = QLabel(":")
        colon_lbl.setStyleSheet("color: #F59E0B; font-size: 14px; font-weight: 800; border: none;")
        cr_box_lay.addWidget(colon_lbl)

        self.custom_aspect_h = FocusOnlySpinBox()
        self.custom_aspect_h.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.custom_aspect_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.custom_aspect_h.setRange(1, 9999)
        self.custom_aspect_h.setValue(16)
        self.custom_aspect_h.setFixedWidth(56)
        self.custom_aspect_h.setFixedHeight(30)
        self.custom_aspect_h.valueChanged.connect(self.on_custom_ratio_changed)
        cr_box_lay.addWidget(self.custom_aspect_h)

        self.custom_ratio_desc_lbl = QLabel("9:16")
        self.custom_ratio_desc_lbl.setStyleSheet("color: #FBBF24; font-family: 'Cascadia Mono', monospace; font-size: 11px; font-weight: 700; border: none;")
        cr_box_lay.addWidget(self.custom_ratio_desc_lbl)
        cr_box_lay.addStretch()

        for p_label, pw, ph in [("4:5", 4, 5), ("3:4", 3, 4), ("2:3", 2, 3), ("16:10", 16, 10)]:
            p_btn = QPushButton(p_label)
            p_btn.setFixedSize(42, 26)
            p_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            p_btn.setStyleSheet(
                "QPushButton { background: #14141C; border: 1px solid #272732; border-radius: 6px; color: #A1A1AA; font-size: 10.5px; font-weight: 600; padding: 0; } "
                "QPushButton:hover { background: #F59E0B; border-color: #FBBF24; color: #000000; }"
            )
            p_btn.clicked.connect(lambda _, w=pw, h=ph: self.set_custom_ratio_preset(w, h))
            cr_box_lay.addWidget(p_btn)

        cr_lay.addWidget(cr_box)
        self.custom_ratio_widget.setVisible(False)
        man_lay.addWidget(self.custom_ratio_widget)

        self.manual_style_combo = self.combo([
            ("Fit Utuh", "manual_fit"),
            ("Sinema Blur", "manual_ambient"),
            ("Crop Penuh", "manual_crop"),
            ("Split 2 Panel", "manual_split"),
            ("Facecam Atas", "manual_facecam"),
        ], selected=0)
        self.manual_style_combo.setVisible(False)
        self.manual_style_combo.currentIndexChanged.connect(self.on_unified_format_changed)

        man_lay.addWidget(section_lbl("Tata Letak Manual"))
        self.manual_style_cards = VisualCardSelector(
            [
                ("manual_fit", "Fit Utuh", "Latar hitam bersih, bebas geser", "frame_manual"),
                ("manual_ambient", "Sinema Blur", "Video utuh + latar blur halus", "cam_cinema"),
                ("manual_crop", "Crop Penuh", "Isi penuh kanvas, bebas zoom", "cam_focus"),
                ("manual_split", "Split 2 Panel", "Kiri di atas & kanan di bawah", "cam_split"),
                ("manual_facecam", "Facecam Atas", "Kamera wajah + layar utama", "cam_game"),
            ],
            columns=2,
            accent="#F59E0B",
        )
        self.manual_style_cards.bind_combo(self.manual_style_combo)
        man_lay.addWidget(self.manual_style_cards)

        self.manual_crop_pan_widget = QFrame()
        self.manual_crop_pan_widget.setStyleSheet("QFrame { background: #0B0B10; border: 1px solid #22222E; border-radius: 10px; }")
        pan_lay = QVBoxLayout(self.manual_crop_pan_widget)
        pan_lay.setContentsMargins(12, 10, 12, 10)
        pan_lay.setSpacing(7)

        pan_top = QHBoxLayout()
        pan_hint = QLabel("Tarik langsung video di kanvas kanan atau scroll mouse untuk ubah skala")
        pan_hint.setWordWrap(True)
        pan_hint.setStyleSheet("color: #D4D4D8; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        pan_top.addWidget(pan_hint, 1)
        self.btn_reset_pan_zoom = QPushButton("Reset 1.00x")
        self.btn_reset_pan_zoom.setObjectName("secondary")
        self.btn_reset_pan_zoom.setFixedHeight(26)
        self.btn_reset_pan_zoom.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_pan_zoom.clicked.connect(self.reset_manual_pan_zoom)
        pan_top.addWidget(self.btn_reset_pan_zoom)
        pan_lay.addLayout(pan_top)

        x_row = QHBoxLayout()
        x_lbl = QLabel("Posisi X")
        x_lbl.setFixedWidth(64)
        x_lbl.setStyleSheet("color: #A1A1AA; font-size: 11px; font-weight: 600; border: none;")
        x_row.addWidget(x_lbl)
        self.manual_crop_x_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.manual_crop_x_slider.setRange(0, 100)
        self.manual_crop_x_slider.setValue(50)
        self.manual_crop_x_slider.valueChanged.connect(self.on_manual_crop_x_changed)
        x_row.addWidget(self.manual_crop_x_slider, 1)
        self.manual_crop_x_val_lbl = QLabel("50% · Tengah")
        self.manual_crop_x_val_lbl.setFixedWidth(92)
        self.manual_crop_x_val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.manual_crop_x_val_lbl.setStyleSheet("color: #FBBF24; font-family: 'Cascadia Mono', monospace; font-weight: 700; font-size: 11px; border: none;")
        x_row.addWidget(self.manual_crop_x_val_lbl)
        pan_lay.addLayout(x_row)

        y_row = QHBoxLayout()
        y_lbl = QLabel("Posisi Y")
        y_lbl.setFixedWidth(64)
        y_lbl.setStyleSheet("color: #A1A1AA; font-size: 11px; font-weight: 600; border: none;")
        y_row.addWidget(y_lbl)
        self.manual_crop_y_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.manual_crop_y_slider.setRange(0, 100)
        self.manual_crop_y_slider.setValue(50)
        self.manual_crop_y_slider.valueChanged.connect(self.on_manual_crop_y_changed)
        y_row.addWidget(self.manual_crop_y_slider, 1)
        self.manual_crop_y_val_lbl = QLabel("50% · Tengah")
        self.manual_crop_y_val_lbl.setFixedWidth(92)
        self.manual_crop_y_val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.manual_crop_y_val_lbl.setStyleSheet("color: #FBBF24; font-family: 'Cascadia Mono', monospace; font-weight: 700; font-size: 11px; border: none;")
        y_row.addWidget(self.manual_crop_y_val_lbl)
        pan_lay.addLayout(y_row)

        z_row = QHBoxLayout()
        z_lbl = QLabel("Skala")
        z_lbl.setFixedWidth(64)
        z_lbl.setStyleSheet("color: #A1A1AA; font-size: 11px; font-weight: 600; border: none;")
        z_row.addWidget(z_lbl)
        self.manual_zoom_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.manual_zoom_slider.setRange(20, 300)
        self.manual_zoom_slider.setValue(100)
        self.manual_zoom_slider.valueChanged.connect(self.on_manual_zoom_changed)
        z_row.addWidget(self.manual_zoom_slider, 1)
        self.manual_zoom_val_lbl = QLabel("1.00x")
        self.manual_zoom_val_lbl.setFixedWidth(92)
        self.manual_zoom_val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.manual_zoom_val_lbl.setStyleSheet("color: #38BDF8; font-family: 'Cascadia Mono', monospace; font-weight: 700; font-size: 11px; border: none;")
        z_row.addWidget(self.manual_zoom_val_lbl)
        pan_lay.addLayout(z_row)

        self.manual_crop_pan_widget.setVisible(False)
        man_lay.addWidget(self.manual_crop_pan_widget)
        self.manual_framing_container.setVisible(False)
        video_v.addWidget(self.manual_framing_container)

        self.format_mode_hint = QLabel("")
        self.format_mode_hint.setWordWrap(True)
        self.format_mode_hint.setStyleSheet(
            "color: #A1A1AA; font-size: 11.5px; background: #07070B; border: 1px solid #1C1C26; border-radius: 9px; padding: 9px 11px;"
        )
        video_v.addWidget(self.format_mode_hint)

        enc_row = QHBoxLayout()
        enc_row.setSpacing(10)
        enc_lbl = QLabel("Mesin Render Video")
        enc_lbl.setStyleSheet("color: #A1A1AA; font-size: 11.5px; font-weight: 600;")
        enc_row.addWidget(enc_lbl)
        hardware_encoders = core.detect_hardware_encoders()
        self.encoder_combo = self.combo([(label, enc) for enc, label in hardware_encoders])
        self.encoder_combo.setMinimumHeight(34)
        enc_row.addWidget(self.encoder_combo, 1)
        video_v.addLayout(enc_row)

        t1_layout.addWidget(settings)

        self.facecam_guide_box = QGroupBox("Pengaturan Area Facecam")
        facecam_group_layout = QVBoxLayout(self.facecam_guide_box)
        facecam_group_layout.setContentsMargins(12, 12, 12, 12)
        facecam_group_layout.setSpacing(8)
        fc_hint = QLabel("Pilih sudut kamera wajah atau geser langsung kotak biru pada kanvas pratinjau kanan.")
        fc_hint.setStyleSheet("color: #71717A; font-size: 11.5px;")
        fc_hint.setWordWrap(True)
        facecam_group_layout.addWidget(fc_hint)

        fc_btn_row = QHBoxLayout()
        self.facecam_preset_combo = self.combo([
            ("Deteksi Wajah AI Otomatis", "auto"),
            ("Pojok Kiri Atas", "top_left"),
            ("Pojok Kanan Atas", "top_right"),
            ("Pojok Kiri Bawah", "bottom_left"),
            ("Pojok Kanan Bawah", "bottom_right"),
            ("Tengah Kiri", "center_left"),
            ("Tengah Kanan", "center_right"),
        ])
        self.facecam_preset_combo.setMinimumHeight(34)
        self.facecam_preset_combo.currentIndexChanged.connect(self.on_facecam_preset_changed)
        fc_btn_row.addWidget(self.facecam_preset_combo, 1)
        self.facecam_box_custom_dragged = False

        self.btn_reset_facecam = QPushButton("Reset")
        self.btn_reset_facecam.setObjectName("secondary")
        self.btn_reset_facecam.setFixedHeight(34)
        self.btn_reset_facecam.clicked.connect(self.reset_facecam_to_auto)
        fc_btn_row.addWidget(self.btn_reset_facecam)
        facecam_group_layout.addLayout(fc_btn_row)
        self.facecam_guide_box.setVisible(False)
        t1_layout.addWidget(self.facecam_guide_box)
        t1_layout.addStretch()

        # =========================================================================
        # SUBTAB 3: SUBTITLE & LIRIK (TIPOGRAFI SEIMBANG + LIRIK LAGU)
        # =========================================================================
        t_sub_widget = QWidget()
        t2_layout = QVBoxLayout(t_sub_widget)
        t2_layout.setContentsMargins(6, 10, 12, 12)
        t2_layout.setSpacing(12)

        subtitle_group = QGroupBox("Tipografi Subtitle Otomatis")
        sub_layout = QVBoxLayout(subtitle_group)
        sub_layout.setContentsMargins(12, 14, 12, 12)
        sub_layout.setSpacing(10)

        sub_master_row, self.subtitle_toggle_switch = make_toggle_row(
            "Tampilkan Subtitle di Video",
            "Menyusun teks proporsional otomatis tanpa kata menggantung sendirian.",
            checked=True,
        )
        self.subtitle_enabled = self.subtitle_toggle_switch
        sub_layout.addWidget(sub_master_row)

        skip_sub_w, self.skip_if_has_subtitles_toggle = make_toggle_row(
            "Lewati Jika Video Sudah Punya Subtitle Bawaan",
            "Mencegah teks bertumpuk pada video yang sudah memiliki hardsub.",
            checked=True,
        )
        self.skip_if_has_subtitles_toggle.toggled.connect(self.update_create_preview)
        sub_layout.addWidget(skip_sub_w)

        self.subtitle_combo = self.combo([
            ("Modern Bersih (Rekomendasi)", "bold"),
            ("CapCut Viral (Tegas & Rapi)", "highlight"),
            ("Minimalis Elegan", "minimal"),
            ("Karaoke Lembut (Sorot Kata)", "karaoke"),
            ("Sinematik Film (Klasik)", "classic"),
            ("Pita Hitam Rapi (Box TV)", "box"),
            ("Neon Halus (Soft Glow)", "neon"),
            ("Tanpa Subtitle", "none"),
        ], selected=0)
        self.subtitle_combo.setMinimumHeight(35)
        self.subtitle_combo.currentIndexChanged.connect(self.update_create_preview)
        self.subtitle_style_cards = None

        self.subtitle_mode_combo = self.combo([
            ("Sorot per Kata (Karaoke Halus)", "active_highlight"),
            ("1 Kata Dinamis (Pop Cepat)", "single_word"),
            ("Kalimat Utuh Tenang", "phrase"),
        ], selected=0)
        self.subtitle_mode_combo.setMinimumHeight(35)
        self.subtitle_mode_combo.currentIndexChanged.connect(self.update_create_preview)
        self.subtitle_mode_pills = None

        self.subtitle_lines_combo = self.combo([
            ("2 Baris Seimbang", 2),
            ("1 Baris Ringkas", 1),
            ("Paragraf Utuh", -1),
        ])
        self.subtitle_lines_combo.setVisible(False)

        self.subtitle_size_combo = self.combo([
            ("Kecil · 12pt", 12),
            ("Sedang · 14pt", 14),
            ("Besar · 17pt", 17),
            ("Ekstra · 20pt", 20),
        ], selected=1)
        self.subtitle_size_combo.setVisible(False)

        # GRID SEBELAHAN: GAYA DESAIN HURUF (DROPDOWN) & ANIMASI KEMUNCULAN TEKS (DROPDOWN)
        typo_grid = QGridLayout()
        typo_grid.setHorizontalSpacing(12)
        typo_grid.setVerticalSpacing(7)
        typo_grid.setColumnStretch(0, 1)
        typo_grid.setColumnStretch(1, 1)

        typo_grid.addWidget(section_lbl("Gaya Desain Huruf (Preset Font)"), 0, 0)
        typo_grid.addWidget(section_lbl("Gaya Animasi Teks"), 0, 1)
        typo_grid.addWidget(self.subtitle_combo, 1, 0)
        typo_grid.addWidget(self.subtitle_mode_combo, 1, 1)

        self.subtitle_lines_pills = SegmentedPillBar([("2 Baris", 2), ("1 Baris", 1), ("Bebas", -1)], accent="#3B82F6")
        self.subtitle_lines_pills.bind_combo(self.subtitle_lines_combo)

        self.subtitle_size_pills = SegmentedPillBar([("12", 12), ("14", 14), ("17", 17), ("20", 20)], accent="#3B82F6")
        self.subtitle_size_pills.bind_combo(self.subtitle_size_combo)

        typo_grid.addWidget(section_lbl("Susunan Baris Teks"), 2, 0)
        typo_grid.addWidget(section_lbl("Ukuran Huruf Teks"), 2, 1)
        typo_grid.addWidget(self.subtitle_lines_pills, 3, 0)
        typo_grid.addWidget(self.subtitle_size_pills, 3, 1)

        self.subtitle_position_combo = self.combo([
            ("Bawah (Area Aman HP)", "auto"),
            ("Bawah Tepi", "bottom"),
            ("Tengah Layar", "center"),
            ("Atas Layar", "top"),
            ("Geser Bebas di Kanvas", "free"),
        ])
        self.subtitle_active_color_combo = self.combo([
            ("Otomatis Konteks Kata", "auto_context"),
            ("Kuning Emas", "#FFDD00"),
            ("Hijau Zamrud", "#00F57A"),
            ("Biru Sian", "#00E5FF"),
            ("Merah Koral", "#FF4D4D"),
            ("Merah Muda", "#FF66CC"),
        ], selected=1)
        self.subtitle_color_combo = self.combo([
            ("Putih Bersih", "white"),
            ("Otomatis", "auto"),
            ("Kuning", "yellow"),
            ("Sian", "cyan"),
            ("Hijau", "green"),
            ("Merah Muda", "pink"),
            ("Kustom HEX", "custom"),
        ])
        for c_sub in (self.subtitle_position_combo, self.subtitle_active_color_combo, self.subtitle_color_combo):
            c_sub.setMinimumHeight(35)

        typo_grid.addWidget(section_lbl("Posisi Subtitle di Layar"), 4, 0)
        typo_grid.addWidget(section_lbl("Warna Sorotan Kata Aktif"), 4, 1)
        typo_grid.addWidget(self.subtitle_position_combo, 5, 0)
        typo_grid.addWidget(self.subtitle_active_color_combo, 5, 1)
        sub_layout.addLayout(typo_grid)

        base_col_row = QHBoxLayout()
        base_col_row.setSpacing(8)
        base_col_row.addWidget(section_lbl("Warna Dasar"))
        base_col_row.addWidget(self.subtitle_color_combo, 1)
        self.subtitle_color_button = QPushButton()
        self.subtitle_color_button.setObjectName("colorSwatch")
        self.subtitle_color_button.setFixedSize(30, 30)
        self.subtitle_color_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.subtitle_color_button.clicked.connect(self.choose_subtitle_color)
        base_col_row.addWidget(self.subtitle_color_button)
        self.subtitle_color_hex = QLineEdit("#FFFFFF")
        self.subtitle_color_hex.setFixedHeight(32)
        self.subtitle_color_hex.setFixedWidth(78)
        self.subtitle_color_hex.editingFinished.connect(self.apply_custom_subtitle_hex)
        base_col_row.addWidget(self.subtitle_color_hex)

        self.btn_safe_zone = QPushButton("Panduan Area HP")
        self.btn_safe_zone.setObjectName("secondary")
        self.btn_safe_zone.setFixedHeight(32)
        self.btn_safe_zone.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_safe_zone.setToolTip("Tampilkan batas area aman dari tombol & caption TikTok/Reels/Shorts")
        self.btn_safe_zone.clicked.connect(self.toggle_safe_zone_overlay)
        base_col_row.addWidget(self.btn_safe_zone)
        sub_layout.addLayout(base_col_row)

        sub_extra_grid = QGridLayout()
        sub_extra_grid.setHorizontalSpacing(8)
        sub_extra_grid.setVerticalSpacing(8)
        sub_extra_grid.setColumnStretch(0, 1)
        sub_extra_grid.setColumnStretch(1, 1)
        emoji_row_w, self.emoji_subtitles_check = make_toggle_row(
            "Emoji Kontekstual",
            "Tambahkan ikon hanya saat relevan",
            checked=False,
        )
        censor_row_w, self.censor_profanity_checkbox = make_toggle_row(
            "Sensor Kata Kasar",
            "Samarkan umpatan di teks",
            checked=False,
        )
        self.emoji_subtitles_check.toggled.connect(self.update_create_preview)
        self.censor_profanity_checkbox.toggled.connect(self.update_create_preview)
        sub_extra_grid.addWidget(emoji_row_w, 0, 0)
        sub_extra_grid.addWidget(censor_row_w, 0, 1)
        sub_layout.addLayout(sub_extra_grid)
        t2_layout.addWidget(subtitle_group)

        # GROUP: TERJEMAHAN LIRIK LAGU & SUBTITLE MUSIK
        lyrics_group = QGroupBox("Terjemahan Lirik Lagu && Ekspor File")
        lyr_layout = QVBoxLayout(lyrics_group)
        lyr_layout.setContentsMargins(12, 14, 12, 12)
        lyr_layout.setSpacing(9)

        lyr_toggle_w, self.translate_lyrics_check = make_toggle_row(
            "Aktifkan Terjemahan Lirik Lagu / Subtitle",
            "Terjemahkan lirik otomatis & simpan file .srt, .lrc, atau .txt ke folder pilihan.",
            checked=False,
        )
        lyr_layout.addWidget(lyr_toggle_w)

        self.lyrics_options_widget = QWidget()
        lyr_opts_layout = QVBoxLayout(self.lyrics_options_widget)
        lyr_opts_layout.setContentsMargins(0, 4, 0, 0)
        lyr_opts_layout.setSpacing(8)

        self.lyrics_target_lang_combo = self.combo([
            ("Bahasa Indonesia (ID)", "id"),
            ("Inggris (EN)", "en"),
            ("Jepang (JA)", "ja"),
            ("Korea (KO)", "ko"),
            ("Mandarin (ZH)", "zh"),
            ("Spanyol (ES)", "es"),
            ("Arab (AR)", "ar"),
            ("Prancis (FR)", "fr"),
            ("Jerman (DE)", "de"),
        ], selected=0)
        self.lyrics_display_mode_combo = self.combo([
            ("Dua Bahasa (Asli + Terjemahan)", "dual"),
            ("Hanya Terjemahan", "translated_only"),
            ("Hanya Asli (Ekspor File Terjemahan)", "original_only"),
        ], selected=0)
        self.lyrics_pos_combo = self.combo([
            ("Ikuti Posisi Subtitle", "auto"),
            ("Bawah Layar", "bottom"),
            ("Tengah Layar", "center"),
            ("Atas Layar", "top"),
            ("Posisi Bebas (X & Y)", "free"),
        ], selected=0)
        for lc in (self.lyrics_target_lang_combo, self.lyrics_display_mode_combo, self.lyrics_pos_combo):
            lc.setMinimumHeight(34)

        lyr_g = QGridLayout()
        lyr_g.setHorizontalSpacing(10)
        lyr_g.setVerticalSpacing(5)
        lyr_g.setColumnStretch(0, 1)
        lyr_g.setColumnStretch(1, 1)
        lyr_g.addWidget(section_lbl("Bahasa Tujuan"), 0, 0)
        lyr_g.addWidget(section_lbl("Tampilan di Video"), 0, 1)
        lyr_g.addWidget(self.lyrics_target_lang_combo, 1, 0)
        lyr_g.addWidget(self.lyrics_display_mode_combo, 1, 1)
        lyr_opts_layout.addLayout(lyr_g)

        lyr_opts_layout.addWidget(section_lbl("Posisi Tampil Lirik"))
        lyr_opts_layout.addWidget(self.lyrics_pos_combo)

        self.lyrics_free_pos_widget = QWidget()
        lyr_free_layout = QVBoxLayout(self.lyrics_free_pos_widget)
        lyr_free_layout.setContentsMargins(0, 0, 0, 0)
        lyr_free_layout.setSpacing(6)

        lyr_x_row = QHBoxLayout()
        lyr_x_lbl = QLabel("Posisi X")
        lyr_x_lbl.setFixedWidth(64)
        lyr_x_lbl.setStyleSheet("color: #A1A1AA; font-size: 11px;")
        self.lyrics_x_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.lyrics_x_slider.setRange(0, 100)
        self.lyrics_x_slider.setValue(15)
        self.lyrics_x_val_lbl = QLabel("15%")
        self.lyrics_x_val_lbl.setStyleSheet("color: #38BDF8; font-family: 'Cascadia Mono', monospace; font-size: 11px; min-width: 36px;")
        lyr_x_row.addWidget(lyr_x_lbl)
        lyr_x_row.addWidget(self.lyrics_x_slider, 1)
        lyr_x_row.addWidget(self.lyrics_x_val_lbl)

        lyr_y_row = QHBoxLayout()
        lyr_y_lbl = QLabel("Posisi Y")
        lyr_y_lbl.setFixedWidth(64)
        lyr_y_lbl.setStyleSheet("color: #A1A1AA; font-size: 11px;")
        self.lyrics_y_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.lyrics_y_slider.setRange(0, 100)
        self.lyrics_y_slider.setValue(78)
        self.lyrics_y_val_lbl = QLabel("78%")
        self.lyrics_y_val_lbl.setStyleSheet("color: #38BDF8; font-family: 'Cascadia Mono', monospace; font-size: 11px; min-width: 36px;")
        lyr_y_row.addWidget(lyr_y_lbl)
        lyr_y_row.addWidget(self.lyrics_y_slider, 1)
        lyr_y_row.addWidget(self.lyrics_y_val_lbl)

        lyr_free_layout.addLayout(lyr_x_row)
        lyr_free_layout.addLayout(lyr_y_row)
        self.lyrics_free_pos_widget.setVisible(False)
        lyr_opts_layout.addWidget(self.lyrics_free_pos_widget)

        lyr_save_row = QHBoxLayout()
        lyr_save_row.setSpacing(8)
        srt_w, self.save_lyrics_srt_check = make_toggle_row("File .SRT", "", checked=True)
        lrc_w, self.save_lyrics_lrc_check = make_toggle_row("File .LRC", "", checked=True)
        txt_w, self.save_lyrics_txt_check = make_toggle_row("File .TXT", "", checked=True)
        lyr_save_row.addWidget(srt_w, 1)
        lyr_save_row.addWidget(lrc_w, 1)
        lyr_save_row.addWidget(txt_w, 1)
        lyr_opts_layout.addWidget(section_lbl("Format Ekspor File Lirik"))
        lyr_opts_layout.addLayout(lyr_save_row)

        lyr_folder_row = QHBoxLayout()
        lyr_folder_row.setSpacing(6)
        self.lyrics_folder_edit = QLineEdit()
        self.lyrics_folder_edit.setPlaceholderText("Default: Otomatis di dalam folder hasil klip...")
        self.lyrics_folder_edit.setMinimumHeight(34)
        btn_lyrics_folder = QPushButton("Pilih Folder")
        btn_lyrics_folder.setObjectName("secondary")
        btn_lyrics_folder.setFixedHeight(34)
        btn_lyrics_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_lyrics_folder.clicked.connect(self.choose_lyrics_folder)
        lyr_folder_row.addWidget(self.lyrics_folder_edit, 1)
        lyr_folder_row.addWidget(btn_lyrics_folder)
        lyr_opts_layout.addWidget(section_lbl("Lokasi Simpan File Lirik"))
        lyr_opts_layout.addLayout(lyr_folder_row)

        lyr_layout.addWidget(self.lyrics_options_widget)
        self.lyrics_options_widget.setVisible(False)

        self.translate_lyrics_check.toggled.connect(self.on_translate_lyrics_toggled)
        self.lyrics_target_lang_combo.currentIndexChanged.connect(self.update_create_preview)
        self.lyrics_display_mode_combo.currentIndexChanged.connect(self.update_create_preview)
        self.lyrics_pos_combo.currentIndexChanged.connect(self.on_lyrics_pos_changed)
        self.lyrics_x_slider.valueChanged.connect(self.on_lyrics_x_slider_changed)
        self.lyrics_y_slider.valueChanged.connect(self.on_lyrics_y_slider_changed)

        t2_layout.addWidget(lyrics_group)
        t2_layout.addStretch()

        self.subtitle_active_color_combo.currentIndexChanged.connect(self.update_create_preview)
        self.subtitle_color_combo.currentIndexChanged.connect(self.update_subtitle_color_chip)
        self.subtitle_toggle_switch.toggled.connect(self.update_subtitle_controls)

        # SUB-TAB 1: MODE PEMOTONGAN (OTOMATIS AI VS MANUAL MULTI-SEGMEN) & MESIN AI
        t_mode_widget = QWidget()
        tm_layout = QVBoxLayout(t_mode_widget)
        tm_layout.setContentsMargins(6, 8, 12, 12)
        tm_layout.setSpacing(10)

        mode_group = QGroupBox("Pengaturan Metode Pemotongan Klip")
        self.mode_group_box = mode_group
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(12, 14, 12, 12)
        mode_layout.setSpacing(10)

        self.mode_combo = self.combo([
            ("Otomatis AI (Momen Terbaik)", "smart"),
            ("Manual Bebas (Multi-Segmen)", "manual"),
            ("Bagi Rata Jumlah Bagian", "split_count"),
            ("Bagi Rata Durasi Detik", "split_duration"),
        ])
        self.mode_combo.setVisible(False)
        self.mode_combo.currentIndexChanged.connect(self.update_mode_settings)

        self.auto_submode_widget = QWidget()
        auto_sub_lay = QVBoxLayout(self.auto_submode_widget)
        auto_sub_lay.setContentsMargins(0, 0, 0, 0)
        auto_sub_lay.setSpacing(5)
        auto_sub_lay.addWidget(section_lbl("Pilih Cara Pemotongan Otomatis (3 Opsi Mode Otomatis)"))
        self.mode_pills = SegmentedPillBar([
            ("Otomatis AI (Momen Terbaik)", "smart"),
            ("Bagi Jumlah Klip", "split_count"),
            ("Bagi Berdasarkan Durasi", "split_duration"),
        ], accent="#3B82F6")
        self.mode_pills.bind_combo(self.mode_combo)
        auto_sub_lay.addWidget(self.mode_pills)
        mode_layout.addWidget(self.auto_submode_widget)

        self.mode_stack = QStackedWidget()

        # PAGE 0: MODE OTOMATIS AI (UNIVERSAL + PODCAST)
        page_smart = QWidget()
        ps_layout = QVBoxLayout(page_smart)
        ps_layout.setContentsMargins(0, 2, 0, 2)
        ps_layout.setSpacing(10)

        self.profile_combo = self.combo([
            ("Universal (Semua Jenis Video)", "auto"),
            ("Podcast & Wawancara", "podcast"),
            ("Gaming & Live Stream", "live"),
            ("Edukasi, Tips & Tutorial", "education"),
            ("Musik, Lagu & Lirik", "music"),
            ("Vlog, Film & Sinematik", "cinematic"),
            ("Pilih Manual di Review", "manual"),
        ])
        self.profile_combo.setVisible(False)
        self.profile_combo.currentIndexChanged.connect(self.update_profile_hint)

        ps_layout.addWidget(section_lbl("Jenis Video Anda"))
        self.profile_cards = VisualCardSelector([
            ("auto", "Universal", "Cocok untuk semua video", "universal", "OTOMATIS", "#3B82F6"),
            ("podcast", "Podcast & Obrolan", "Tanya-jawab & diskusi", "podcast", "POPULER", "#8B5CF6"),
            ("live", "Gaming & Stream", "Reaksi seru & momen live", "gaming", "SERU", "#10B981"),
            ("education", "Edukasi & Tutorial", "Penjelasan & tips praktis", "edu", "ILMU", "#F59E0B"),
            ("music", "Musik & Lagu", "Bagian reff, lagu & lirik", "music", "LIRIK", "#EC4899"),
            ("cinematic", "Vlog & Cerita", "Alur cerita & sinematik", "cinema", "CERITA", "#06B6D4"),
        ], columns=3, accent="#3B82F6", card_height=62)
        self.profile_cards.bind_combo(self.profile_combo)
        ps_layout.addWidget(self.profile_cards)

        self.clip_flavor_combo = self.combo([
            ("Sorotan Utama (Universal)", "universal"),
            ("Debat & Pernyataan Tajam", "spicy_drama"),
            ("Intisari Ilmu & Solusi", "deep_meat"),
            ("Komedi & Momen Lucu", "funny_blunder"),
            ("Reaksi Heboh & Klimaks", "hype_rage"),
            ("Reff, Chorus & Lirik Lagu", "music_lyrics"),
            ("Narasi & Alur Sinematik", "cinematic_story"),
        ], selected=0)
        self.clip_flavor_combo.setVisible(False)

        ps_layout.addWidget(section_lbl("Bagian Apa yang Ingin Diambil AI?"))
        self.clip_flavor_cards = VisualCardSelector([
            ("universal", "Momen Terbaik", "Pembuka kuat & isi jelas", "ai_spark", "UTAMA", "#3B82F6"),
            ("spicy_drama", "Opini & Debat", "Argumen seru & pernyataan kuat", "podcast", "TAJAM", "#EF4444"),
            ("deep_meat", "Inti Pembahasan", "Tips penting & solusi langsung", "edu", "INTI", "#F59E0B"),
            ("funny_blunder", "Momen Lucu", "Tawa & kejadian menghibur", "cam_focus", "FUN", "#10B981"),
            ("music_lyrics", "Reff & Puncak Lagu", "Bagian lagu paling enak", "music", "MUSIK", "#EC4899"),
            ("cinematic_story", "Momen Berkesan", "Suasana & cerita menyentuh", "cinema", "VLOG", "#06B6D4"),
        ], columns=3, accent="#3B82F6", card_height=60)
        self.clip_flavor_cards.bind_combo(self.clip_flavor_combo)
        ps_layout.addWidget(self.clip_flavor_cards)

        self.clip_count = self.spin(0, 200, 0)
        self.clip_count.setVisible(False)
        self.max_clips = self.spin(1, 200, 15)
        self.min_duration = self.spin(0, 3600, 0)
        self.max_duration = self.spin(0, 3600, 0)
        self.min_duration.setSpecialValueText("Otomatis")
        self.max_duration.setSpecialValueText("Otomatis")
        for sp in (self.max_clips, self.min_duration, self.max_duration):
            sp.setFixedHeight(34)

        self.smart_duration_mode = self.combo([("auto", "auto"), ("fixed", "fixed")])
        self.smart_duration_mode.setVisible(False)
        self.smart_fixed_duration = self.spin(5, 3600, 60)
        self.smart_fixed_duration.setVisible(False)
        self.use_llm = QCheckBox("Gunakan AI")
        self.use_llm.setChecked(True)
        self.use_llm.setVisible(False)

        dur_grid = QGridLayout()
        dur_grid.setHorizontalSpacing(8)
        dur_grid.setVerticalSpacing(4)
        dur_grid.setColumnStretch(0, 1)
        dur_grid.setColumnStretch(1, 1)
        dur_grid.setColumnStretch(2, 1)
        dur_grid.addWidget(section_lbl("Maks. Klip"), 0, 0)
        dur_grid.addWidget(section_lbl("Durasi Min (dtk)"), 0, 1)
        dur_grid.addWidget(section_lbl("Durasi Maks (dtk)"), 0, 2)
        dur_grid.addWidget(self.max_clips, 1, 0)
        dur_grid.addWidget(self.min_duration, 1, 1)
        dur_grid.addWidget(self.max_duration, 1, 2)
        ps_layout.addLayout(dur_grid)

        ai_rules_grid = QGridLayout()
        ai_rules_grid.setHorizontalSpacing(8)
        ai_rules_grid.setVerticalSpacing(8)
        ai_rules_grid.setColumnStretch(0, 1)
        ai_rules_grid.setColumnStretch(1, 1)

        ae_w, self.use_audio_energy_check = make_toggle_row(
            "Deteksi Lonjakan Suara",
            " Analisis tawa, reaksi & penekanan vokal",
            checked=True,
        )
        sn_w, self.snap_sentence_check = make_toggle_row(
            "Kunci Kalimat Utuh",
            "Cegah potongan menggantung di tengah kalimat",
            checked=True,
        )
        tf_w, self.trim_filler_check = make_toggle_row(
            "Pangkas Jeda Awal",
            "Mulai langsung dari kalimat pembuka",
            checked=True,
        )
        sh_w, self.spicy_headline_check = make_toggle_row(
            "Judul & Caption AI",
            "Buat ide judul & deskripsi otomatis",
            checked=True,
        )
        ai_rules_grid.addWidget(ae_w, 0, 0)
        ai_rules_grid.addWidget(sn_w, 0, 1)
        ai_rules_grid.addWidget(tf_w, 1, 0)
        ai_rules_grid.addWidget(sh_w, 1, 1)
        ps_layout.addLayout(ai_rules_grid)

        self.profile_hint = QLabel("AI menyesuaikan cara memilih klip dengan kategori video yang Anda pilih.")
        self.profile_hint.setWordWrap(True)
        self.profile_hint.setStyleSheet(
            "color: #A1A1AA; background: #0D0D12; border: 1px solid #1F1F2B; border-radius: 8px; padding: 7px 10px; font-size: 11px;"
        )
        ps_layout.addWidget(self.profile_hint)
        self.mode_stack.addWidget(page_smart)

        # PAGE 1: SPLIT BY COUNT
        page_count = QWidget()
        pc_layout = QVBoxLayout(page_count)
        pc_layout.setContentsMargins(0, 4, 0, 4)
        pc_layout.setSpacing(8)
        pc_info = QLabel(
            "<b>Bagi Rata Jumlah Klip:</b> Video akan dibagi rata menjadi sejumlah bagian klip dengan durasi sama panjang dari awal hingga akhir (tanpa perlu analisis momen AI)."
        )
        pc_info.setWordWrap(True)
        pc_info.setStyleSheet(
            "color: #BFDBFE; background: #0B1222; border: 1px solid #1E3A8A; border-radius: 8px; padding: 8px 10px; font-size: 11px;"
        )
        pc_layout.addWidget(pc_info)
        pc_row = QHBoxLayout()
        pc_row.addWidget(section_lbl("Ingin Dibagi Menjadi Berapa Klip?"))
        self.split_count = self.spin(1, 500, 10)
        self.split_count.setFixedHeight(36)
        self.split_count.valueChanged.connect(self.update_segment_estimate)
        pc_row.addWidget(self.split_count, 1)
        pc_layout.addLayout(pc_row)
        self.mode_stack.addWidget(page_count)

        # PAGE 2: SPLIT BY DURATION
        page_dur = QWidget()
        pd_layout = QVBoxLayout(page_dur)
        pd_layout.setContentsMargins(0, 4, 0, 4)
        pd_layout.setSpacing(8)
        pd_info = QLabel(
            "<b>Bagi Berdasarkan Durasi:</b> Video akan dipotong berurutan setiap sekian detik sesuai durasi yang Anda tentukan (misal: tiap 60 detik menjadi 1 klip)."
        )
        pd_info.setWordWrap(True)
        pd_info.setStyleSheet(
            "color: #BFDBFE; background: #0B1222; border: 1px solid #1E3A8A; border-radius: 8px; padding: 8px 10px; font-size: 11px;"
        )
        pd_layout.addWidget(pd_info)
        pd_row = QHBoxLayout()
        pd_row.addWidget(section_lbl("Durasi Setiap Klip (Detik)"))
        self.segment_duration = self.spin(5, 3600, 60)
        self.segment_duration.setFixedHeight(36)
        self.segment_duration.valueChanged.connect(self.update_segment_estimate)
        pd_row.addWidget(self.segment_duration, 1)
        pd_layout.addLayout(pd_row)
        self.mode_stack.addWidget(page_dur)

        # PAGE 3: MODE CLIPPING MANUAL (MULTI-SEGMEN BEBAS TANPA BATAS)
        page_manual = QWidget()
        pm_layout = QVBoxLayout(page_manual)
        pm_layout.setContentsMargins(0, 2, 0, 2)
        pm_layout.setSpacing(9)
        self.pre_manual_segments: list[dict[str, Any]] = []

        pm_info = QLabel(
            "<b>Mode Clipping Manual · Multi-Segmen Bebas:</b> "
            "Putar video di pratinjau kanan, klik <b>Ambil Waktu</b> untuk menandai titik mulai & selesai, lalu klik "
            "<b>+ Tambah Segmen</b>. Anda bebas menyusun banyak segmen sekaligus (#01, #02, #03...) dalam sekali proses, "
            "dan klik segmen mana saja di daftar untuk melompat & mengeditnya secara langsung."
        )
        pm_info.setWordWrap(True)
        pm_info.setStyleSheet(
            "color: #FDE68A; background: #141007; border: 1px solid #92400E; border-radius: 8px; padding: 8px 10px; font-size: 11px;"
        )
        pm_layout.addWidget(pm_info)

        pm_grid = QGridLayout()
        pm_grid.setHorizontalSpacing(8)
        pm_grid.setVerticalSpacing(5)
        pm_grid.setColumnStretch(0, 1)
        pm_grid.setColumnStretch(1, 1)

        pm_grid.addWidget(section_lbl("Waktu Mulai (MM:SS / dtk)"), 0, 0)
        pm_grid.addWidget(section_lbl("Waktu Selesai (MM:SS / dtk)"), 0, 1)

        start_box = QHBoxLayout()
        start_box.setSpacing(5)
        self.pre_manual_start_edit = QLineEdit("00:00")
        self.pre_manual_start_edit.setPlaceholderText("00:00")
        self.pre_manual_start_edit.setFixedHeight(34)
        self.pre_manual_start_edit.setStyleSheet("font-family: 'Cascadia Mono', 'Consolas', monospace; font-weight: 700;")
        start_box.addWidget(self.pre_manual_start_edit, 1)
        self.btn_grab_manual_start = QPushButton("[ Ambil Waktu")
        self.btn_grab_manual_start.setObjectName("secondary")
        self.btn_grab_manual_start.setFixedHeight(34)
        self.btn_grab_manual_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_grab_manual_start.setToolTip("Ambil waktu mulai langsung dari posisi putar video di sebelah kanan")
        self.btn_grab_manual_start.clicked.connect(lambda: self.grab_preview_time_for_manual(is_start=True))
        start_box.addWidget(self.btn_grab_manual_start)
        pm_grid.addLayout(start_box, 1, 0)

        end_box = QHBoxLayout()
        end_box.setSpacing(5)
        self.pre_manual_end_edit = QLineEdit("01:00")
        self.pre_manual_end_edit.setPlaceholderText("01:00")
        self.pre_manual_end_edit.setFixedHeight(34)
        self.pre_manual_end_edit.setStyleSheet("font-family: 'Cascadia Mono', 'Consolas', monospace; font-weight: 700;")
        end_box.addWidget(self.pre_manual_end_edit, 1)
        self.btn_grab_manual_end = QPushButton("Ambil Waktu ]")
        self.btn_grab_manual_end.setObjectName("secondary")
        self.btn_grab_manual_end.setFixedHeight(34)
        self.btn_grab_manual_end.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_grab_manual_end.setToolTip("Ambil waktu selesai langsung dari posisi putar video di sebelah kanan")
        self.btn_grab_manual_end.clicked.connect(lambda: self.grab_preview_time_for_manual(is_start=False))
        end_box.addWidget(self.btn_grab_manual_end)
        pm_grid.addLayout(end_box, 1, 1)

        pm_grid.addWidget(section_lbl("Judul Segmen (Opsional)"), 2, 0, 1, 2)
        self.pre_manual_title_edit = QLineEdit()
        self.pre_manual_title_edit.setPlaceholderText("Contoh: Bagian Pembuka / Reff Lagu / Momen Inti...")
        self.pre_manual_title_edit.setFixedHeight(34)
        pm_grid.addWidget(self.pre_manual_title_edit, 3, 0, 1, 2)
        pm_layout.addLayout(pm_grid)

        pm_btn_row = QHBoxLayout()
        pm_btn_row.setSpacing(6)
        self.btn_add_pre_manual = QPushButton("+ Tambah Segmen")
        self.btn_add_pre_manual.setFixedHeight(34)
        self.btn_add_pre_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_pre_manual.setStyleSheet(
            "QPushButton { background: #2563EB; border: 1px solid #60A5FA; border-radius: 8px; color: #FFFFFF; font-weight: 700; font-size: 11px; padding: 0 12px; } "
            "QPushButton:hover { background: #1D4ED8; }"
        )
        self.btn_add_pre_manual.clicked.connect(self.add_pre_manual_segment)
        pm_btn_row.addWidget(self.btn_add_pre_manual, 1)

        self.btn_upd_pre_manual = QPushButton("Simpan Edit")
        self.btn_upd_pre_manual.setObjectName("secondary")
        self.btn_upd_pre_manual.setFixedHeight(34)
        self.btn_upd_pre_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_upd_pre_manual.setToolTip("Perbarui waktu atau judul pada segmen yang sedang dipilih di daftar bawah")
        self.btn_upd_pre_manual.clicked.connect(self.update_selected_pre_manual_segment)
        pm_btn_row.addWidget(self.btn_upd_pre_manual)

        self.btn_full_video_manual = QPushButton("1 Video Utuh")
        self.btn_full_video_manual.setFixedHeight(34)
        self.btn_full_video_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_full_video_manual.setToolTip("Masukkan seluruh durasi video dari awal hingga akhir sebagai segmen")
        self.btn_full_video_manual.setStyleSheet(
            "QPushButton { background: #064E3B; border: 1px solid #10B981; border-radius: 8px; color: #ECFDF5; font-weight: 700; font-size: 11px; padding: 0 10px; } "
            "QPushButton:hover { background: #047857; }"
        )
        self.btn_full_video_manual.clicked.connect(self.add_full_video_manual_segment)
        pm_btn_row.addWidget(self.btn_full_video_manual)

        self.btn_del_pre_manual = QPushButton("Hapus")
        self.btn_del_pre_manual.setObjectName("secondary")
        self.btn_del_pre_manual.setFixedHeight(34)
        self.btn_del_pre_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del_pre_manual.clicked.connect(self.remove_selected_pre_manual_segment)
        pm_btn_row.addWidget(self.btn_del_pre_manual)
        pm_layout.addLayout(pm_btn_row)

        pm_layout.addWidget(section_lbl("Daftar Segmen Manual (Klik Segmen untuk Pratinjau & Edit)"))
        self.pre_manual_list = QListWidget()
        self.pre_manual_list.setMinimumHeight(124)
        self.pre_manual_list.setMaximumHeight(168)
        self.pre_manual_list.setStyleSheet(
            "QListWidget { background: #07070B; border: 1px solid #1F1F2B; border-radius: 8px; color: #F4F4F5; "
            "font-family: 'Cascadia Mono', 'Segoe UI Variable Text', monospace; font-size: 11px; padding: 4px; } "
            "QListWidget::item { padding: 6px 8px; border-radius: 6px; margin-bottom: 2px; } "
            "QListWidget::item:selected { background: #261A07; border: 1px solid #F59E0B; color: #FEF3C7; } "
            "QListWidget::item:hover:!selected { background: #12121A; }"
        )
        self.pre_manual_list.itemClicked.connect(self.on_pre_manual_item_clicked)
        pm_layout.addWidget(self.pre_manual_list)
        self.mode_stack.addWidget(page_manual)

        mode_layout.addWidget(self.mode_stack)

        est_strip = QFrame()
        est_strip.setStyleSheet("background: #0D0D14; border: 1px solid #1F1F2B; border-radius: 8px;")
        est_layout = QVBoxLayout(est_strip)
        est_layout.setContentsMargins(10, 7, 10, 7)
        est_layout.setSpacing(2)
        self.duration_info = QLabel("Durasi sumber: belum dimuat")
        self.duration_info.setStyleSheet("color: #A1A1AA; font-size: 11px; font-weight: 600; border: 0; background: transparent;")
        self.segment_estimate = QLabel("Estimasi klip akan tampil setelah video dipilih.")
        self.segment_estimate.setStyleSheet("color: #60A5FA; font-size: 11px; font-weight: 700; border: 0; background: transparent;")
        self.segment_estimate.setWordWrap(True)
        est_layout.addWidget(self.duration_info)
        est_layout.addWidget(self.segment_estimate)
        mode_layout.addWidget(est_strip)

        tm_layout.addWidget(mode_group)

        # GROUP: MESIN AI & BAHASA TRANSKRIPSI (DIPISAH ANTARA ANALISIS AI VS SUARA KE TEKS)
        ai_group = QGroupBox("Mesin Analisis AI && Suara ke Teks (Subtitle)")
        self.ai_engine_group = ai_group
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.setContentsMargins(12, 14, 12, 12)
        ai_layout.setSpacing(8)

        self.ai_engine_mode_note = QLabel(
            "<b>Mode Manual Aktif:</b> Mesin Analisis Momen AI dinonaktifkan karena Anda menentukan titik potong sendiri. "
            "Hanya <b>Mesin Suara ke Teks</b> yang digunakan untuk membuat teks subtitle otomatis."
        )
        self.ai_engine_mode_note.setWordWrap(True)
        self.ai_engine_mode_note.setStyleSheet(
            "color: #A7F3D0; background: #061A14; border: 1px solid #059669; border-radius: 8px; padding: 7px 10px; font-size: 11px;"
        )
        self.ai_engine_mode_note.setVisible(False)
        ai_layout.addWidget(self.ai_engine_mode_note)

        self.ai_provider_combo = self.combo([
            ("Google Gemini Cloud (Cepat & Akurat)", "gemini"),
            ("Model Lokal GGUF (100% Offline)", "local"),
        ])
        self.whisper_combo = self.combo([
            ("Gemini Audio Cloud (Cepat & Akurat)", "gemini"),
            ("Whisper Small (Offline · Cepat)", "small"),
            ("Whisper Medium (Offline · Seimbang)", "medium"),
            ("Whisper Large-v3 (Offline · Presisi)", "large-v3"),
        ])
        self.language_combo = self.combo([
            ("Deteksi Bahasa Otomatis", "auto"),
            ("Bahasa Indonesia", "id"),
            ("Bahasa Inggris", "en"),
            ("Bahasa Jepang", "ja"),
            ("Bahasa Korea", "ko"),
        ])
        self.custom_prompt_edit = QLineEdit()
        self.custom_prompt_edit.setPlaceholderText("Opsional: Ketik topik/bagian yang ingin dicari AI (misal: bahas harga, momen lucu)...")

        for c in (self.ai_provider_combo, self.whisper_combo, self.language_combo, self.custom_prompt_edit):
            c.setMinimumHeight(34)

        # Baris 1: Mesin Suara ke Teks & Bahasa Video (Selalu digunakan untuk Subtitle baik di Otomatis maupun Manual)
        stt_grid = QGridLayout()
        stt_grid.setHorizontalSpacing(10)
        stt_grid.setVerticalSpacing(5)
        stt_grid.setColumnStretch(0, 3)
        stt_grid.setColumnStretch(1, 2)
        stt_grid.addWidget(section_lbl("Mesin Suara ke Teks (Pembuat Subtitle)"), 0, 0)
        stt_grid.addWidget(section_lbl("Bahasa di Dalam Video"), 0, 1)
        stt_grid.addWidget(self.whisper_combo, 1, 0)
        stt_grid.addWidget(self.language_combo, 1, 1)
        ai_layout.addLayout(stt_grid)

        # Kontainer Khusus Analisis Momen AI (HANYA tampil saat Mode Otomatis AI dipilih)
        self.ai_analysis_container = QWidget()
        ai_an_layout = QVBoxLayout(self.ai_analysis_container)
        ai_an_layout.setContentsMargins(0, 2, 0, 0)
        ai_an_layout.setSpacing(8)

        an_grid = QGridLayout()
        an_grid.setHorizontalSpacing(10)
        an_grid.setVerticalSpacing(5)
        an_grid.setColumnStretch(0, 2)
        an_grid.setColumnStretch(1, 3)
        an_grid.addWidget(section_lbl("Mesin Analisis Momen AI (Khusus Mode Otomatis AI)"), 0, 0)
        an_grid.addWidget(section_lbl("Cari Topik / Bagian Tertentu (Opsional)"), 0, 1)
        an_grid.addWidget(self.ai_provider_combo, 1, 0)
        an_grid.addWidget(self.custom_prompt_edit, 1, 1)
        ai_an_layout.addLayout(an_grid)

        self.local_panel = QFrame()
        self.local_panel.setStyleSheet("background: #07070B; border: 1px solid #1F1F2B; border-radius: 8px;")
        local_layout = QVBoxLayout(self.local_panel)
        local_layout.setContentsMargins(10, 8, 10, 8)
        local_row = QHBoxLayout()
        local_row.setSpacing(8)
        local_row.addWidget(section_lbl("Model AI Offline (.GGUF)"))
        self.model_file_combo = ClickOnlyComboBox()
        self.model_file_combo.setMinimumHeight(32)
        self.model_file_combo.currentIndexChanged.connect(self.on_model_file_changed)
        local_row.addWidget(self.model_file_combo, 1)
        self.model_folder_button = QPushButton("Pilih Folder")
        self.model_folder_button.setObjectName("secondary")
        self.model_folder_button.setFixedHeight(32)
        self.model_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.model_folder_button.clicked.connect(self.pick_model_folder)
        local_row.addWidget(self.model_folder_button)
        local_layout.addLayout(local_row)
        self.model_path_edits["qwen"] = QLineEdit()
        self.model_path_edits["qwen"].setVisible(False)
        self.model_path_edits["hermes"] = QLineEdit()
        self.model_path_edits["hermes"].setVisible(False)
        ai_an_layout.addWidget(self.local_panel)
        ai_layout.addWidget(self.ai_analysis_container)

        self.gemini_panel = QFrame()
        self.gemini_panel.setStyleSheet("background: #07070B; border: 1px solid #1F1F2B; border-radius: 8px;")
        gemini_layout = QVBoxLayout(self.gemini_panel)
        gemini_layout.setContentsMargins(10, 8, 10, 8)
        gemini_key_row = QHBoxLayout()
        gemini_key_row.setSpacing(8)
        gemini_key_row.addWidget(section_lbl("API Key Gemini"))
        self.gemini_key_edit = QLineEdit()
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_edit.setPlaceholderText("Tempel API Key Google Gemini...")
        saved_key = core.get_active_gemini_api_key()
        self.gemini_key_edit.setText(saved_key)
        self.gemini_key_edit.textChanged.connect(self.on_gemini_key_changed)
        self.gemini_key_edit.setFixedHeight(32)
        gemini_key_row.addWidget(self.gemini_key_edit, 1)
        self.gemini_test_button = QPushButton("Uji Koneksi")
        self.gemini_test_button.setObjectName("secondary")
        self.gemini_test_button.setFixedHeight(32)
        self.gemini_test_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gemini_test_button.clicked.connect(self.test_gemini_connection)
        gemini_key_row.addWidget(self.gemini_test_button)
        self.gemini_status_badge = QLabel("")
        gemini_key_row.addWidget(self.gemini_status_badge)
        gemini_layout.addLayout(gemini_key_row)
        ai_layout.addWidget(self.gemini_panel)

        tm_layout.addWidget(ai_group)
        tm_layout.addStretch()

        self.ai_provider_combo.currentIndexChanged.connect(self.on_ai_provider_changed)
        self.whisper_combo.currentIndexChanged.connect(self.update_ai_engine_visibility)
        self.on_ai_provider_changed()
        self.load_model_paths()
        self.refresh_model_file_choices()

        # SUB-TAB 4: AUDIO, EFEK VISUAL REAL-TIME & OVERLAY OPSIONAL
        t_audio_widget = QWidget()
        t3_layout = QVBoxLayout(t_audio_widget)
        t3_layout.setContentsMargins(6, 8, 12, 12)
        t3_layout.setSpacing(10)

        bgm_group = QGroupBox("Audio Utama && Musik Latar")
        bgm_box_layout = QVBoxLayout(bgm_group)
        bgm_box_layout.setContentsMargins(12, 14, 12, 12)
        bgm_box_layout.setSpacing(9)

        bgm_file_row = QHBoxLayout()
        bgm_file_row.setSpacing(6)
        self.bgm_path_label = QLabel("Belum ada musik latar dipilih (opsional)")
        self.bgm_path_label.setWordWrap(True)
        self.bgm_path_label.setStyleSheet(
            "color: #A1A1AA; font-size: 11px; background: #07070B; "
            "border: 1px solid #1F1F2B; border-radius: 8px; padding: 7px 10px;"
        )
        bgm_file_row.addWidget(self.bgm_path_label, 1)

        self.btn_pick_bgm = QPushButton("Pilih Musik")
        self.btn_pick_bgm.setObjectName("secondary")
        self.btn_pick_bgm.setFixedHeight(34)
        self.btn_pick_bgm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_bgm.clicked.connect(self.choose_bgm_file)
        bgm_file_row.addWidget(self.btn_pick_bgm)

        self.btn_clear_bgm = QPushButton("Hapus")
        self.btn_clear_bgm.setObjectName("secondary")
        self.btn_clear_bgm.setFixedHeight(34)
        self.btn_clear_bgm.setEnabled(False)
        self.btn_clear_bgm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_bgm.clicked.connect(self.clear_bgm_file)
        bgm_file_row.addWidget(self.btn_clear_bgm)
        bgm_box_layout.addLayout(bgm_file_row)

        vol_grid = QGridLayout()
        vol_grid.setHorizontalSpacing(12)
        vol_grid.setVerticalSpacing(4)
        vol_grid.setColumnStretch(0, 1)
        vol_grid.setColumnStretch(1, 1)

        vol_grid.addWidget(section_lbl("Volume Suara Video"), 0, 0)
        vol_grid.addWidget(section_lbl("Volume Musik Latar"), 0, 1)

        voice_vol_row = QHBoxLayout()
        self.voice_vol_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.voice_vol_slider.setRange(50, 150)
        self.voice_vol_slider.setValue(100)
        self.voice_vol_label = QLabel("100%")
        self.voice_vol_label.setStyleSheet("color: #34D399; font-family: 'Cascadia Mono', monospace; font-weight: 700; font-size: 11px; min-width: 38px;")
        self.voice_vol_slider.valueChanged.connect(self.on_voice_vol_changed)
        voice_vol_row.addWidget(self.voice_vol_slider, 1)
        voice_vol_row.addWidget(self.voice_vol_label)
        vol_grid.addLayout(voice_vol_row, 1, 0)

        bgm_vol_row = QHBoxLayout()
        self.bgm_vol_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.bgm_vol_slider.setRange(0, 100)
        self.bgm_vol_slider.setValue(8)
        self.bgm_vol_label = QLabel("8%")
        self.bgm_vol_label.setStyleSheet("color: #60A5FA; font-family: 'Cascadia Mono', monospace; font-weight: 700; font-size: 11px; min-width: 34px;")
        self.bgm_vol_slider.valueChanged.connect(self.on_bgm_vol_changed)
        bgm_vol_row.addWidget(self.bgm_vol_slider, 1)
        bgm_vol_row.addWidget(self.bgm_vol_label)
        vol_grid.addLayout(bgm_vol_row, 1, 1)
        bgm_box_layout.addLayout(vol_grid)

        audio_fx_grid = QGridLayout()
        audio_fx_grid.setHorizontalSpacing(8)
        audio_fx_grid.setVerticalSpacing(8)
        audio_fx_grid.setColumnStretch(0, 1)
        audio_fx_grid.setColumnStretch(1, 1)
        duck_w, self.bgm_duck_checkbox = make_toggle_row(
            "Auto-Ducking Musik",
            "Kecilkan musik saat ada suara bicara",
            checked=True,
        )
        loud_w, self.loudnorm_checkbox = make_toggle_row(
            "Normalisasi Suara",
            "Stabilkan volume standar -14 LUFS",
            checked=True,
        )
        audio_fx_grid.addWidget(duck_w, 0, 0)
        audio_fx_grid.addWidget(loud_w, 0, 1)
        bgm_box_layout.addLayout(audio_fx_grid)
        t3_layout.addWidget(bgm_group)

        # GROUP: EFEK VISUAL REAL-TIME (DEFAULT MATI — TANPA AI SLOP)
        fx_group = QGroupBox("Efek Visual && Penyesuaian Gambar")
        fx_layout = QVBoxLayout(fx_group)
        fx_layout.setContentsMargins(12, 14, 12, 12)
        fx_layout.setSpacing(8)

        fx_grid = QGridLayout()
        fx_grid.setHorizontalSpacing(8)
        fx_grid.setVerticalSpacing(8)
        fx_grid.setColumnStretch(0, 1)
        fx_grid.setColumnStretch(1, 1)

        cb_w, self.color_boost_check = make_toggle_row(
            "Pertajam Warna & Kontras",
            "Tampil langsung di pratinjau kanan",
            checked=False,
        )
        mr_w, self.mirror_video_check = make_toggle_row(
            "Balik Kiri-Kanan (Mirror)",
            "Cerminkan gambar secara real-time",
            checked=False,
        )
        sp_w, self.speed_shift_check = make_toggle_row(
            "Tempo Halus 1.03x",
            "Percepat sedikit laju putar & audio",
            checked=False,
        )
        mz_w, self.micro_zoom_check = make_toggle_row(
            "Zoom Halus Momen Penting",
            "Zoom 1.06x saat penekanan kalimat",
            checked=False,
        )
        self.color_boost_check.toggled.connect(self.update_create_preview)
        self.mirror_video_check.toggled.connect(self.update_create_preview)
        self.speed_shift_check.toggled.connect(self.update_create_preview)

        fx_grid.addWidget(cb_w, 0, 0)
        fx_grid.addWidget(mr_w, 0, 1)
        fx_grid.addWidget(sp_w, 1, 0)
        fx_grid.addWidget(mz_w, 1, 1)
        fx_layout.addLayout(fx_grid)

        br_w, self.auto_broll_check = make_toggle_row(
            "Sisipkan Video B-Roll Otomatis",
            "Tampilkan klip ilustrasi pendek dari folder lokal Anda",
            checked=False,
        )
        fx_layout.addWidget(br_w)

        self.broll_folder_widget = QWidget()
        br_row = QHBoxLayout(self.broll_folder_widget)
        br_row.setContentsMargins(0, 0, 0, 0)
        br_row.setSpacing(6)
        self.broll_folder_edit = QLineEdit()
        self.broll_folder_edit.setPlaceholderText("Pilih folder berisi kumpulan video B-Roll (.mp4)...")
        self.broll_folder_edit.setFixedHeight(32)
        btn_broll_dir = QPushButton("Pilih Folder")
        btn_broll_dir.setObjectName("secondary")
        btn_broll_dir.setFixedHeight(32)
        btn_broll_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_broll_dir.clicked.connect(self.choose_broll_folder)
        br_row.addWidget(self.broll_folder_edit, 1)
        br_row.addWidget(btn_broll_dir)
        self.broll_folder_widget.setVisible(False)
        self.auto_broll_check.toggled.connect(self.broll_folder_widget.setVisible)
        fx_layout.addWidget(self.broll_folder_widget)
        t3_layout.addWidget(fx_group)

        # GROUP: WATERMARK & BANNER JUDUL OPSIONAL (OFF BY DEFAULT — ZERO SLOP)
        wm_group = QGroupBox("Watermark && Overlay Judul (Opsional)")
        wm_layout = QVBoxLayout(wm_group)
        wm_layout.setContentsMargins(12, 14, 12, 12)
        wm_layout.setSpacing(8)

        wm_inputs_grid = QGridLayout()
        wm_inputs_grid.setHorizontalSpacing(8)
        wm_inputs_grid.setVerticalSpacing(5)
        wm_inputs_grid.setColumnStretch(0, 1)
        wm_inputs_grid.setColumnStretch(1, 1)
        wm_inputs_grid.addWidget(section_lbl("Teks Watermark"), 0, 0)
        wm_inputs_grid.addWidget(section_lbl("Logo PNG Transparan"), 0, 1)

        self.watermark_edit = QLineEdit()
        self.watermark_edit.setPlaceholderText("Contoh: @ChannelAnda")
        self.watermark_edit.setFixedHeight(34)
        self.watermark_edit.textChanged.connect(self.update_create_preview)
        wm_inputs_grid.addWidget(self.watermark_edit, 1, 0)

        wm_png_row = QHBoxLayout()
        wm_png_row.setSpacing(5)
        self.watermark_image_edit = QLineEdit()
        self.watermark_image_edit.setPlaceholderText("Opsional: File .png")
        self.watermark_image_edit.setFixedHeight(34)
        self.watermark_image_edit.textChanged.connect(self.update_create_preview)
        btn_pick_wm = QPushButton("Pilih PNG")
        btn_pick_wm.setObjectName("secondary")
        btn_pick_wm.setFixedHeight(34)
        btn_pick_wm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pick_wm.clicked.connect(self.choose_watermark_image)
        btn_clear_wm = QPushButton("Hapus")
        btn_clear_wm.setObjectName("secondary")
        btn_clear_wm.setFixedHeight(34)
        btn_clear_wm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_wm.clicked.connect(self.clear_watermark_image)
        wm_png_row.addWidget(self.watermark_image_edit, 1)
        wm_png_row.addWidget(btn_pick_wm)
        wm_png_row.addWidget(btn_clear_wm)
        wm_inputs_grid.addLayout(wm_png_row, 1, 1)
        wm_layout.addLayout(wm_inputs_grid)

        wm_pos_op_grid = QGridLayout()
        wm_pos_op_grid.setHorizontalSpacing(10)
        wm_pos_op_grid.setVerticalSpacing(4)
        wm_pos_op_grid.setColumnStretch(0, 1)
        wm_pos_op_grid.setColumnStretch(1, 1)
        wm_pos_op_grid.addWidget(section_lbl("Posisi Watermark"), 0, 0)
        wm_pos_op_grid.addWidget(section_lbl("Transparansi Watermark"), 0, 1)

        self.watermark_pos_combo = self.combo([
            ("Kanan Atas", "top_right"),
            ("Kiri Atas", "top_left"),
            ("Kanan Bawah", "bottom_right"),
            ("Kiri Bawah", "bottom_left"),
            ("Tengah Layar", "center"),
            ("Posisi Bebas (Geser di Video)", "free"),
        ], selected=0)
        self.watermark_pos_combo.setMinimumHeight(34)
        self.watermark_pos_combo.currentIndexChanged.connect(self.on_watermark_pos_changed)
        wm_pos_op_grid.addWidget(self.watermark_pos_combo, 1, 0)

        wm_op_row = QHBoxLayout()
        self.watermark_opacity_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.watermark_opacity_slider.setRange(15, 100)
        self.watermark_opacity_slider.setValue(75)
        self.watermark_opacity_lbl = QLabel("75%")
        self.watermark_opacity_lbl.setStyleSheet("color: #A1A1AA; font-family: 'Cascadia Mono', monospace; font-size: 11px; min-width: 34px;")
        self.watermark_opacity_slider.valueChanged.connect(
            lambda v: (self.watermark_opacity_lbl.setText(f"{v}%"), self.update_create_preview())
        )
        wm_op_row.addWidget(self.watermark_opacity_slider, 1)
        wm_op_row.addWidget(self.watermark_opacity_lbl)
        wm_pos_op_grid.addLayout(wm_op_row, 1, 1)
        wm_layout.addLayout(wm_pos_op_grid)

        self.watermark_free_pos_widget = QWidget()
        wm_free_l = QHBoxLayout(self.watermark_free_pos_widget)
        wm_free_l.setContentsMargins(0, 0, 0, 0)
        wm_free_l.setSpacing(8)
        wm_free_l.addWidget(section_lbl("X"))
        self.watermark_x_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.watermark_x_slider.setRange(0, 100)
        self.watermark_x_slider.setValue(85)
        self.watermark_x_val_lbl = QLabel("85%")
        self.watermark_x_val_lbl.setStyleSheet("color: #60A5FA; font-family: 'Cascadia Mono', monospace; font-size: 11px;")
        self.watermark_x_slider.valueChanged.connect(self.on_watermark_x_slider_changed)
        wm_free_l.addWidget(self.watermark_x_slider, 1)
        wm_free_l.addWidget(self.watermark_x_val_lbl)

        wm_free_l.addWidget(section_lbl("Y"))
        self.watermark_y_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.watermark_y_slider.setRange(0, 100)
        self.watermark_y_slider.setValue(8)
        self.watermark_y_val_lbl = QLabel("8%")
        self.watermark_y_val_lbl.setStyleSheet("color: #60A5FA; font-family: 'Cascadia Mono', monospace; font-size: 11px;")
        self.watermark_y_slider.valueChanged.connect(self.on_watermark_y_slider_changed)
        wm_free_l.addWidget(self.watermark_y_slider, 1)
        wm_free_l.addWidget(self.watermark_y_val_lbl)
        self.watermark_free_pos_widget.setVisible(False)
        wm_layout.addWidget(self.watermark_free_pos_widget)

        hb_row_w, self.hook_banner_toggle = make_toggle_row(
            "Tampilkan Banner Judul Pembuka (Hook)",
            "Kotak judul di awal video (mati secara bawaan agar video tetap bersih)",
            checked=False,
        )
        wm_layout.addWidget(hb_row_w)

        self.hook_banner_options_widget = QWidget()
        hb_opts_l = QVBoxLayout(self.hook_banner_options_widget)
        hb_opts_l.setContentsMargins(0, 2, 0, 0)
        hb_opts_l.setSpacing(6)
        self.hook_banner_edit = QLineEdit()
        self.hook_banner_edit.setPlaceholderText("Kosongkan agar otomatis mengikuti judul klip, atau ketik teks sendiri...")
        self.hook_banner_edit.setFixedHeight(34)
        self.hook_banner_edit.textChanged.connect(self.update_create_preview)
        hb_opts_l.addWidget(self.hook_banner_edit)

        hb_sub_row = QHBoxLayout()
        hb_sub_row.setSpacing(8)
        self.hook_banner_dur_combo = self.combo([
            ("3 Detik Awal", 3),
            ("5 Detik Awal", 5),
            ("8 Detik Awal", 8),
            ("Sepanjang Klip", 0),
        ], selected=1)
        self.hook_banner_dur_combo.setMinimumHeight(34)
        self.hook_banner_dur_combo.currentIndexChanged.connect(self.update_create_preview)
        self.hook_banner_dur_spin = self.spin(0, 120, 5)
        self.hook_banner_dur_spin.setVisible(False)

        self.hook_banner_pos_combo = self.combo([
            ("Atas Tengah", "top"),
            ("Tengah Layar", "center"),
            ("Geser Bebas di Video", "free"),
        ], selected=0)
        self.hook_banner_pos_combo.setMinimumHeight(34)
        self.hook_banner_pos_combo.currentIndexChanged.connect(self.update_create_preview)
        hb_sub_row.addWidget(self.hook_banner_dur_combo, 1)
        hb_sub_row.addWidget(self.hook_banner_pos_combo, 1)
        hb_opts_l.addLayout(hb_sub_row)
        self.hook_banner_options_widget.setVisible(False)
        self.hook_banner_toggle.toggled.connect(self.hook_banner_options_widget.setVisible)
        self.hook_banner_toggle.toggled.connect(self.update_create_preview)
        wm_layout.addWidget(self.hook_banner_options_widget)

        cta_row_w, self.outro_cta_check = make_toggle_row(
            "Tampilkan Teks Ajakan Penutup (Outro CTA)",
            "Tambahkan teks ajakan simpan/bagikan pada 2.5 detik terakhir klip",
            checked=False,
        )
        wm_layout.addWidget(cta_row_w)

        t3_layout.addWidget(wm_group)
        t3_layout.addStretch()

        # PURE BLACK SEGMENTED SUB-TABS
        self.create_subtabs = QTabWidget()
        self.create_subtabs.setDocumentMode(True)
        self.create_subtabs.tabBar().setUsesScrollButtons(False)
        self.create_subtabs.tabBar().setExpanding(True)
        self.create_subtabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #1C1C26; background: #050508; border-radius: 12px; margin-top: 6px; } "
            "QTabBar { background: transparent; } "
            "QTabBar::tab { background: #0C0C12; border: 1px solid #1E1E2A; color: #A1A1AA; "
            "padding: 7px 8px; font-size: 11px; font-weight: 700; border-radius: 8px; margin-right: 4px; } "
            "QTabBar::tab:selected { background: #172554; border: 1px solid #3B82F6; color: #FFFFFF; } "
            "QTabBar::tab:hover:!selected { color: #F4F4F5; background: #14141D; border-color: #2E2E3E; }"
        )

        def wrap_tab(w: QWidget) -> QScrollArea:
            for child in w.findChildren(QWidget):
                if isinstance(child, QLabel):
                    if len(child.text().strip()) > 14 and child.minimumWidth() == 0:
                        child.setWordWrap(True)
                elif isinstance(child, QComboBox):
                    child.setMinimumWidth(0)
                    child.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                    child.setMinimumContentsLength(6)
                    sp = child.sizePolicy()
                    sp.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
                    child.setSizePolicy(sp)
                elif isinstance(child, QLineEdit):
                    if child.maximumWidth() > 500:
                        child.setMinimumWidth(0)
            w.setMinimumWidth(0)
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.Shape.NoFrame)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sa.setStyleSheet("QScrollArea { background: transparent; border: 0; }")
            sa.setWidget(w)
            return sa

        self.create_subtabs.addTab(wrap_tab(t_mode_widget), "1 · Mode && Potongan")
        self.create_subtabs.addTab(wrap_tab(t_frame_widget), "2 · Rasio && Framing")
        self.create_subtabs.addTab(wrap_tab(t_sub_widget), "3 · Subtitle && Lirik")
        self.create_subtabs.addTab(wrap_tab(t_audio_widget), "4 · Audio && Overlay")
        self.create_subtabs.tabBarClicked.connect(self.on_subtab_bar_clicked)
        self.create_subtabs.currentChanged.connect(self.on_subtab_changed)

        left_outer_layout.addWidget(self.create_subtabs, 1)

        self.progress_panel = QFrame()
        self.progress_panel.setObjectName("progressCard")
        self.progress_panel.setStyleSheet(
            "QFrame#progressCard { background: #09090E; border: 1px solid #2563EB; border-radius: 12px; padding: 12px; margin-top: 4px; }"
        )
        prog_layout = QVBoxLayout(self.progress_panel)
        prog_layout.setSpacing(6)

        total_header = QHBoxLayout()
        self.status_label = QLabel("Menyiapkan proses...")
        self.status_label.setStyleSheet("font-weight: 700; font-size: 12px; color: #F4F4F5; border: 0; background: transparent;")
        self.total_percent_label = QLabel("0%")
        self.total_percent_label.setStyleSheet("font-family: 'Cascadia Mono', monospace; font-weight: 800; font-size: 13px; color: #60A5FA; border: 0; background: transparent;")
        total_header.addWidget(self.status_label, 1)
        total_header.addWidget(self.total_percent_label)
        prog_layout.addLayout(total_header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(7)
        self.progress.setStyleSheet(
            "QProgressBar { background: #181822; border-radius: 3px; border: 0; } "
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #38BDF8); border-radius: 3px; }"
        )
        prog_layout.addWidget(self.progress)

        sub_header = QHBoxLayout()
        self.sub_status_label = QLabel("Detail tahapan...")
        self.sub_status_label.setStyleSheet("font-size: 11px; color: #A1A1AA; border: 0; background: transparent;")
        self.sub_percent_label = QLabel("0%")
        self.sub_percent_label.setStyleSheet("font-family: 'Cascadia Mono', monospace; font-weight: 700; font-size: 11px; color: #34D399; border: 0; background: transparent;")
        sub_header.addWidget(self.sub_status_label, 1)
        sub_header.addWidget(self.sub_percent_label)
        prog_layout.addLayout(sub_header)

        self.sub_progress = QProgressBar()
        self.sub_progress.setRange(0, 100)
        self.sub_progress.setTextVisible(False)
        self.sub_progress.setFixedHeight(5)
        self.sub_progress.setStyleSheet(
            "QProgressBar { background: #181822; border-radius: 2px; border: 0; } "
            "QProgressBar::chunk { background: #10B981; border-radius: 2px; }"
        )
        prog_layout.addWidget(self.sub_progress)
        self.progress_panel.setVisible(False)
        left_outer_layout.addWidget(self.progress_panel)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.setContentsMargins(0, 2, 0, 0)

        btn_back_tab0 = QPushButton("← Pilih Video")
        btn_back_tab0.setFixedHeight(42)
        btn_back_tab0.setMinimumWidth(124)
        btn_back_tab0.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back_tab0.setStyleSheet(
            "QPushButton { background: #0C0C12; border: 1px solid #242432; border-radius: 10px; "
            "color: #E4E4E7; font-size: 12px; font-weight: 700; padding: 0 14px; } "
            "QPushButton:hover { background: #161622; border-color: #3B82F6; color: #FFFFFF; }"
        )
        btn_back_tab0.clicked.connect(lambda: self.switch_tab(1))
        action_row.addWidget(btn_back_tab0)

        self.start_button = QPushButton("Mulai Analisis && Buat Klip AI")
        self.start_button.setObjectName("primary")
        self.start_button.setFixedHeight(42)
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setStyleSheet(
            "QPushButton#primary { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #1D4ED8); "
            "border: 1px solid #60A5FA; border-radius: 10px; color: #FFFFFF; font-size: 13px; font-weight: 800; padding: 0 22px; } "
            "QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #2563EB); }"
        )
        self.start_button.clicked.connect(self.start_process)
        action_row.addWidget(self.start_button, 1)

        self.cancel_button = QPushButton("Batalkan Proses")
        self.cancel_button.setFixedHeight(42)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setStyleSheet(
            "QPushButton { background: #2A0A10; border: 1px solid #EF4444; border-radius: 10px; "
            "color: #FCA5A5; font-size: 12px; font-weight: 700; padding: 0 18px; } "
            "QPushButton:hover { background: #450A0A; color: #FFFFFF; }"
        )
        self.cancel_button.clicked.connect(self.cancel_current_process)
        self.cancel_button.setVisible(False)
        action_row.addWidget(self.cancel_button, 1)
        left_outer_layout.addLayout(action_row)

        self.create_splitter.addWidget(left_column_container)

        # RIGHT COLUMN: PRATINJAU VIDEO REAL-TIME (PURE BLACK MONITOR)
        right_container = QFrame()
        self.studio_right_container = right_container
        right_container.setObjectName("studioPreviewCard")
        right_container.setMinimumWidth(360)
        right_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_container.setStyleSheet(
            "QFrame#studioPreviewCard { background: #060609; border: 1px solid #1C1C26; border-radius: 14px; }"
        )
        right_col = QVBoxLayout(right_container)
        right_col.setContentsMargins(14, 12, 14, 12)
        right_col.setSpacing(8)

        preview_header_row = QHBoxLayout()
        live_dot = QLabel("●")
        live_dot.setStyleSheet("color: #10B981; font-size: 11px; border: 0; background: transparent;")
        preview_header_row.addWidget(live_dot)
        preview_title = QLabel("Pratinjau Real-Time (POV Hasil)")
        preview_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #FAFAFA; border: 0; background: transparent;")
        preview_header_row.addWidget(preview_title)
        preview_header_row.addStretch()

        self.preview_layout_badge = QLabel("9:16 · Adaptif AI")
        self.preview_layout_badge.setStyleSheet(
            "background: #111827; color: #93C5FD; border: 1px solid #2563EB; border-radius: 6px; padding: 3px 9px; font-size: 10px; font-weight: 700;"
        )
        preview_header_row.addWidget(self.preview_layout_badge)
        right_col.addLayout(preview_header_row)

        self.create_preview_player = QMediaPlayer(self)
        self.create_preview_audio = QAudioOutput(self)
        self.create_preview_player.setAudioOutput(self.create_preview_audio)
        self.create_preview_player.playbackStateChanged.connect(self.on_create_playback_state_changed)

        self.bgm_preview_player = QMediaPlayer(self)
        self.bgm_preview_audio = QAudioOutput(self)
        self.bgm_preview_player.setAudioOutput(self.bgm_preview_audio)
        self.bgm_preview_audio.setVolume(0.08)

        preview_box = QWidget()
        preview_box.setStyleSheet("background: transparent; border: 0;")
        preview_box_layout = QVBoxLayout(preview_box)
        preview_box_layout.setContentsMargins(0, 0, 0, 0)
        preview_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        preview_frame = QFrame()
        self.create_preview_frame = preview_frame
        preview_frame.setObjectName("previewCanvas")
        preview_frame.setStyleSheet(
            "QFrame#previewCanvas { background: #000000; border: 1px solid #272733; border-radius: 10px; }"
        )
        preview_stack = QGridLayout(preview_frame)
        self.create_preview_stack = preview_stack
        preview_stack.setContentsMargins(0, 0, 0, 0)

        self.create_preview_video = VideoSurfaceWidget()
        self.create_preview_video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.create_preview_video.facesDetected.connect(self.on_live_faces_detected)
        self.create_preview_video.manualCropChanged.connect(self.on_canvas_manual_crop_changed)
        preview_stack.addWidget(self.create_preview_video, 0, 0)

        self.safe_zone_overlay = SafeZoneOverlayWidget(self.create_preview_video)
        self.safe_zone_overlay.setVisible(False)
        self.smart_layout_overlay = SmartLayoutOverlayWidget(self.create_preview_video)
        self.smart_layout_overlay.setVisible(False)

        self.facecam_box = DraggableFacecamBox(self.create_preview_video)
        self.facecam_box.setVisible(False)

        self.preview_layout_overlay = QLabel("")
        self.preview_layout_overlay.setObjectName("previewBadge")
        self.preview_layout_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_layout_overlay.setVisible(False)
        preview_stack.addWidget(self.preview_layout_overlay, 0, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self.preview_facecam_top = QLabel("FACECAM")
        self.preview_facecam_top.setVisible(False)
        self.preview_facecam_main = QLabel("VIDEO UTAMA")
        self.preview_facecam_main.setVisible(False)

        self.preview_subtitle_sample = DraggableSubtitleLabel("Contoh subtitle tampil di sini", self.create_preview_video)
        self.preview_subtitle_sample.setObjectName("previewSubtitle")
        self.preview_subtitle_sample.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_subtitle_sample.moved.connect(self.on_free_subtitle_moved)

        self.preview_hook_banner = DraggableSubtitleLabel("", self.create_preview_video)
        self.preview_hook_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_hook_banner.setWordWrap(True)
        self.preview_hook_banner.setCursor(Qt.CursorShape.OpenHandCursor)
        self.preview_hook_banner.setToolTip("Geser kotak judul ke posisi mana saja di kanvas")
        self.preview_hook_banner.moved.connect(self.on_free_hook_banner_moved)
        self.preview_hook_banner.setVisible(False)

        self.preview_watermark_label = DraggableSubtitleLabel("", self.create_preview_video)
        self.preview_watermark_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_watermark_label.setCursor(Qt.CursorShape.OpenHandCursor)
        self.preview_watermark_label.setToolTip("Geser watermark ke posisi mana saja di kanvas")
        self.preview_watermark_label.moved.connect(self.on_free_watermark_moved)
        self.preview_watermark_label.setVisible(False)

        self.create_preview_video.videoRectChanged.connect(lambda _: self.facecam_box.update_geometry_from_parent())
        self.facecam_box.cropChanged.connect(lambda *_: setattr(self, "facecam_box_custom_dragged", True))

        self.preview_placeholder = QLabel("Pilih video pada langkah 1 untuk melihat pratinjau langsung")
        self.preview_placeholder.setWordWrap(True)
        self.preview_placeholder.setStyleSheet("color: #71717A; font-size: 12px; font-weight: 600; padding: 16px; background: transparent; border: 0;")
        self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_stack.addWidget(self.preview_placeholder, 0, 0, Qt.AlignmentFlag.AlignCenter)

        self.create_preview_player.setVideoOutput(self.create_preview_video.sink)
        preview_box_layout.addWidget(preview_frame)
        right_col.addWidget(preview_box, 1)

        self.preview_summary = QLabel("")
        self.preview_summary.setWordWrap(True)
        self.preview_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_summary.setStyleSheet("color: #A1A1AA; font-size: 11px; font-weight: 500; border: 0; background: transparent;")
        right_col.addWidget(self.preview_summary)

        self.create_seek_slider = WaveformScrubber()
        self.create_seek_slider.setRange(0, 0)
        self.create_seek_slider.setFixedHeight(28)
        self.create_seek_slider.setEnabled(False)
        self.create_seek_slider.sliderMoved.connect(self.seek_create_preview)
        self.create_preview_player.positionChanged.connect(self.update_create_seek)
        self.create_preview_player.durationChanged.connect(self.update_create_duration)
        right_col.addWidget(self.create_seek_slider)

        controls_toolbar = QHBoxLayout()
        controls_toolbar.setSpacing(6)
        ctrl_btn_style = (
            "QPushButton { background: #0E0E15; border: 1px solid #222230; border-radius: 8px; color: #D4D4D8; padding: 0px; } "
            "QPushButton:hover { background: #181824; border-color: #3B82F6; color: #FFFFFF; } "
            "QPushButton:pressed { background: #09090E; }"
        )

        self.create_preview_time = QLabel("00:00 / 00:00")
        self.create_preview_time.setStyleSheet(
            "font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 11px; font-weight: 700; color: #60A5FA; background: transparent; border: 0;"
        )
        controls_toolbar.addWidget(self.create_preview_time)
        self.create_preview_pos_time = QLabel("")
        self.create_preview_pos_time.setVisible(False)

        controls_toolbar.addStretch()

        btn_prev = QPushButton()
        btn_prev.setIcon(make_vector_icon("prev", "#D4D4D8", 16))
        btn_prev.setToolTip("Kembali ke Awal (00:00)")
        btn_prev.setFixedSize(32, 32)
        btn_prev.setStyleSheet(ctrl_btn_style)
        btn_prev.clicked.connect(lambda: self.seek_create_preview(0))
        controls_toolbar.addWidget(btn_prev)

        btn_rew = QPushButton()
        btn_rew.setIcon(make_vector_icon("rewind", "#D4D4D8", 16))
        btn_rew.setToolTip("Mundur 5 Detik")
        btn_rew.setFixedSize(32, 32)
        btn_rew.setStyleSheet(ctrl_btn_style)
        btn_rew.clicked.connect(lambda: self.seek_create_preview(max(0, self.create_preview_player.position() - 5000)))
        controls_toolbar.addWidget(btn_rew)

        self.create_preview_play = QPushButton()
        self.create_preview_play.setIcon(make_vector_icon("play", "#FFFFFF", 18))
        self.create_preview_play.setToolTip("Putar / Jeda Pratinjau")
        self.create_preview_play.setFixedSize(40, 40)
        self.create_preview_play.setStyleSheet(
            "QPushButton { background: #2563EB; border-radius: 20px; border: 1px solid #60A5FA; padding: 0px; } "
            "QPushButton:hover { background: #3B82F6; } QPushButton:pressed { background: #1D4ED8; }"
        )
        self.create_preview_play.clicked.connect(self.toggle_create_preview)
        controls_toolbar.addWidget(self.create_preview_play)

        btn_ff = QPushButton()
        btn_ff.setIcon(make_vector_icon("forward", "#D4D4D8", 16))
        btn_ff.setToolTip("Maju 5 Detik")
        btn_ff.setFixedSize(32, 32)
        btn_ff.setStyleSheet(ctrl_btn_style)
        btn_ff.clicked.connect(
            lambda: self.seek_create_preview(
                min(self.create_preview_player.duration(), self.create_preview_player.position() + 5000)
            )
        )
        controls_toolbar.addWidget(btn_ff)

        btn_next = QPushButton()
        btn_next.setIcon(make_vector_icon("next", "#D4D4D8", 16))
        btn_next.setToolTip("Lompat ke Akhir Video")
        btn_next.setFixedSize(32, 32)
        btn_next.setStyleSheet(ctrl_btn_style)
        btn_next.clicked.connect(lambda: self.seek_create_preview(self.create_preview_player.duration()))
        controls_toolbar.addWidget(btn_next)
        controls_toolbar.addStretch()

        self.create_preview_mute_btn = QPushButton()
        self.create_preview_mute_btn.setIcon(make_vector_icon("volume_on", "#D4D4D8", 16))
        self.create_preview_mute_btn.setToolTip("Bisukan / Aktifkan Suara")
        self.create_preview_mute_btn.setFixedSize(32, 32)
        self.create_preview_mute_btn.setStyleSheet(ctrl_btn_style)
        self.create_preview_mute_btn.clicked.connect(self.toggle_create_mute)
        controls_toolbar.addWidget(self.create_preview_mute_btn)

        right_col.addLayout(controls_toolbar)

        for control in (
            self.aspect_combo,
            self.framing_combo,
            self.layout_combo,
            self.subtitle_combo,
            self.subtitle_mode_combo,
            self.subtitle_toggle_switch,
            self.subtitle_position_combo,
            self.subtitle_color_combo,
            self.subtitle_lines_combo,
            self.subtitle_size_combo,
        ):
            if isinstance(control, (QCheckBox, ToggleSwitch)):
                control.toggled.connect(self.update_create_preview)
            else:
                control.currentIndexChanged.connect(self.update_create_preview)

        self.create_splitter.addWidget(right_container)
        self.create_splitter.setCollapsible(0, False)
        self.create_splitter.setCollapsible(1, False)
        self.create_splitter.setStretchFactor(0, 1)
        self.create_splitter.setStretchFactor(1, 1)
        self.create_splitter.setSizes([640, 540])
        self.create_splitter.splitterMoved.connect(lambda pos, idx: self.update_create_preview())

        self.settings_group = settings
        self.subtitle_group = subtitle_group
        self.ai_group = ai_group
        self.clip_stage_widgets = [self.create_subtabs, self.start_button, preview_frame]
        self.load_studio_hook_settings()
        self.update_subtitle_color_chip()
        self.update_subtitle_controls()
        self.set_framing_mode("auto")
        self.set_clipping_mode_quick("auto")
        self.update_profile_hint()
        return page

    def build_video_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        page = QWidget()
        page.setObjectName("pageContent")
        page.setMinimumWidth(860)
        page.setMaximumWidth(1320)

        main_layout = QHBoxLayout(page)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(28)

        left_col = QVBoxLayout()
        left_col.setSpacing(14)

        step_title = QLabel("Pilih Video Sumber")
        step_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #FAFAFA; letter-spacing: 0.2px;")
        left_col.addWidget(step_title)

        step_sub = QLabel("Tarik berkas video lokal (MP4/MKV/MOV) atau tempel tautan YouTube / TikTok / Reels.")
        step_sub.setStyleSheet("font-size: 12px; color: #71717A; margin-top: -6px; margin-bottom: 4px;")
        left_col.addWidget(step_sub)

        self.drop_zone = DropZoneWidget()
        self.drop_zone.fileDropped.connect(self.on_file_dropped)
        self.drop_zone.clicked.connect(self.choose_local_video)
        left_col.addWidget(self.drop_zone)

        lbl_url = QLabel("Tautan Video Online")
        lbl_url.setStyleSheet("font-size: 12px; font-weight: 700; color: #D4D4D8;")
        left_col.addWidget(lbl_url)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Tempel tautan YouTube, Shorts, TikTok, atau Instagram...")
        self.url_edit.setMinimumHeight(40)
        left_col.addWidget(self.url_edit)

        url_action_row = QHBoxLayout()
        url_action_row.setSpacing(12)

        self.quality_combo = self.combo([
            ("Kualitas 1080p · Full HD (Disarankan)", "1080"),
            ("Kualitas 720p · HD Cepat", "720"),
            ("Kualitas 480p · Ringan", "480"),
            ("Kualitas 360p · Hemat Kuota", "360"),
            ("Kualitas Asli Terbaik (Hingga 4K)", "best"),
        ], 0)
        self.quality_combo.setMinimumHeight(40)
        url_action_row.addWidget(self.quality_combo, 1)

        self.download_button = QPushButton("Unduh Video")
        self.download_button.setObjectName("primary")
        self.download_button.setMinimumHeight(40)
        self.download_button.setStyleSheet("font-weight: 700; padding: 0 24px;")
        self.download_button.clicked.connect(self.start_download)
        url_action_row.addWidget(self.download_button)
        left_col.addLayout(url_action_row)

        self.local_file_button = QPushButton("Pilih Berkas Lokal...")
        self.local_file_button.setVisible(False)
        self.local_file_button.clicked.connect(self.choose_local_video)

        self.dl_progress_card = QFrame()
        self.dl_progress_card.setObjectName("dlProgressCard")
        self.dl_progress_card.setStyleSheet(
            "QFrame#dlProgressCard { background: #09090E; border: 1px solid #1C1C26; border-radius: 11px; padding: 12px; margin-top: 10px; }"
        )
        dl_card_layout = QVBoxLayout(self.dl_progress_card)
        dl_card_layout.setContentsMargins(14, 12, 14, 12)
        dl_card_layout.setSpacing(6)

        dl_header = QHBoxLayout()
        self.dl_status_label = QLabel("Mengunduh video sumber...")
        self.dl_status_label.setStyleSheet("font-weight: 700; font-size: 13px; color: #FAFAFA; background: transparent; border: 0;")
        self.dl_percent_label = QLabel("0%")
        self.dl_percent_label.setStyleSheet("font-weight: 800; font-size: 13px; color: #38BDF8; background: transparent; border: 0;")
        dl_header.addWidget(self.dl_status_label, 1)
        dl_header.addWidget(self.dl_percent_label)
        dl_card_layout.addLayout(dl_header)

        self.dl_progress_bar = QProgressBar()
        self.dl_progress_bar.setRange(0, 100)
        self.dl_progress_bar.setValue(0)
        self.dl_progress_bar.setTextVisible(False)
        self.dl_progress_bar.setFixedHeight(8)
        self.dl_progress_bar.setStyleSheet(
            "QProgressBar { background: #14141E; border-radius: 4px; border: 0; } "
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #38BDF8); border-radius: 4px; }"
        )
        dl_card_layout.addWidget(self.dl_progress_bar)

        self.dl_detail_label = QLabel("Menyiapkan unduhan...")
        self.dl_detail_label.setStyleSheet("font-size: 11px; font-weight: 500; color: #71717A; background: transparent; border: 0;")
        dl_card_layout.addWidget(self.dl_detail_label)

        self.dl_progress_card.setVisible(False)
        left_col.addWidget(self.dl_progress_card)

        self.source_status = QLabel("Belum ada video sumber")
        self.source_status.setObjectName("status")
        left_col.addWidget(self.source_status)
        left_col.addStretch()

        main_layout.addLayout(left_col, 55)

        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        lib_title = QLabel("Pustaka Video Sumber")
        lib_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF; letter-spacing: 0.5px;")
        right_col.addWidget(lib_title)

        self.raw_video_scroll = QScrollArea()
        self.raw_video_scroll.setWidgetResizable(True)
        self.raw_video_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.raw_video_scroll.setStyleSheet("background: transparent;")

        self.raw_video_grid_widget = QWidget()
        self.raw_video_grid_widget.setStyleSheet("background: transparent;")
        self.raw_video_grid_layout = QGridLayout(self.raw_video_grid_widget)
        self.raw_video_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.raw_video_grid_layout.setSpacing(12)
        self.raw_video_scroll.setWidget(self.raw_video_grid_widget)
        right_col.addWidget(self.raw_video_scroll, 1)

        lib_action_row = QHBoxLayout()
        lib_action_row.setSpacing(8)

        self.use_raw_video_button = QPushButton("Gunakan Video Terpilih")
        self.use_raw_video_button.setObjectName("primary")
        self.use_raw_video_button.setEnabled(False)
        self.use_raw_video_button.clicked.connect(self.use_selected_raw_video)
        lib_action_row.addWidget(self.use_raw_video_button)

        refresh_button = QPushButton("Muat ulang")
        refresh_button.clicked.connect(self.refresh_raw_video_list)
        lib_action_row.addWidget(refresh_button)

        open_folder_button = QPushButton("Buka Folder")
        open_folder_button.clicked.connect(self.open_raw_video_folder)
        lib_action_row.addWidget(open_folder_button)
        right_col.addLayout(lib_action_row)

        self.raw_video_status = QLabel("Belum ada video tersimpan.")
        self.raw_video_status.setObjectName("muted")
        right_col.addWidget(self.raw_video_status)

        main_layout.addLayout(right_col, 45)

        self.selected_raw_entry = None
        self.refresh_raw_video_list()
        scroll.setWidget(page)
        return scroll

    def refresh_raw_video_list(self) -> None:
        if not hasattr(self, "raw_video_grid_layout"):
            return
        while self.raw_video_grid_layout.count():
            item = self.raw_video_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        root = core.RAW_VIDEO_DIR
        entries: list[dict[str, Any]] = []
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
                dur = core.media_duration(video, 15.0)
                thumb = get_video_thumbnail_path(video, min(2.0, dur / 2 if dur > 2 else 0.5))
                entries.append({
                    "mtime": video.stat().st_mtime,
                    "title": title,
                    "path": str(video),
                    "thumb_path": thumb,
                    "duration": dur,
                    "size": video.stat().st_size,
                })

        entries.sort(key=lambda x: x["mtime"], reverse=True)
        self.video_card_widgets: list[VideoCardWidget] = []
        for i, entry in enumerate(entries):
            row = i // 2
            col = i % 2
            card = VideoCardWidget(entry)
            card.clicked.connect(self.on_video_card_clicked)
            card.doubleClicked.connect(lambda e: self.use_selected_raw_video(e))
            self.video_card_widgets.append(card)
            self.raw_video_grid_layout.addWidget(card, row, col)

        count = len(entries)
        if count > 0:
            if not getattr(self, "selected_raw_entry", None):
                self.selected_raw_entry = entries[0]
                self.video_card_widgets[0].set_selected(True)
            if hasattr(self, "use_raw_video_button"):
                self.use_raw_video_button.setEnabled(True)
        else:
            self.selected_raw_entry = None
            if hasattr(self, "use_raw_video_button"):
                self.use_raw_video_button.setEnabled(False)
        self.raw_video_status.setText(
            f"{count} video tersimpan di pustaka." if count else "Belum ada video tersimpan di pustaka."
        )

    def on_video_card_clicked(self, entry: dict[str, Any]) -> None:
        self.selected_raw_entry = entry
        for card in getattr(self, "video_card_widgets", []):
            card.set_selected(card.entry_data == entry)
        if hasattr(self, "use_raw_video_button"):
            self.use_raw_video_button.setEnabled(True)

    def on_file_dropped(self, path: str) -> None:
        if not path or not Path(path).is_file():
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

    def open_raw_video_folder(self) -> None:
        core.RAW_VIDEO_DIR.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(core.RAW_VIDEO_DIR)))

    def use_selected_raw_video(self, entry: dict[str, Any] | None = None) -> None:
        if not isinstance(entry, dict):
            entry = getattr(self, "selected_raw_entry", None)
        if not entry and getattr(self, "video_card_widgets", []):
            entry = self.video_card_widgets[0].entry_data
            self.on_video_card_clicked(entry)
        if not entry:
            QMessageBox.information(self, "Pilih Video", "Silakan klik salah satu video dari pustaka terlebih dahulu.")
            return
        path = Path(str(entry.get("path", "")))
        title = str(entry.get("title", "") or path.stem)
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
                message=f"Video siap digunakan · {title}",
                source_path=str(path),
                source_url=f"/raw/{path.parent.name}/{path.name}",
                source_title=title,
            )
        self.url_edit.setText(str(path))
        self.show_clip_stage(str(path), f"Video siap digunakan · {title}")

    def ensure_splitter_balanced(self) -> None:
        if not hasattr(self, "create_splitter"):
            return
        total_w = self.create_splitter.width()
        if total_w < 500:
            total_w = max(500, self.width() - 40)
        left_w = int(total_w * 0.52)
        right_w = max(360, total_w - left_w)
        self.create_splitter.setSizes([left_w, right_w])

    def build_tutorial_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(10)
        eyebrow = QLabel("PANDUAN LENGKAP PENGGUNAAN")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("Panduan Penggunaan ENCLip Studio")
        title.setObjectName("title")
        layout.addWidget(title)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setStyleSheet(
            "QTextEdit { background: #07070C; border: 1px solid #1E1E2A; border-radius: 12px; padding: 16px; color: #E4E4E7; }"
        )
        content.setHtml(
            "<div style='font-family: \"Segoe UI Variable Text\", \"Segoe UI\", Arial, sans-serif; line-height: 1.6; color: #D4D4D8; font-size: 13px;'>"
            "<div style='background: #0B132B; border: 1px solid #1D4ED8; border-radius: 10px; padding: 14px 16px; margin-bottom: 16px;'>"
            "<b style='color: #60A5FA; font-size: 14px;'>Cara Mendapatkan Google Gemini API Key (100% Gratis &amp; Resmi)</b><br>"
            "<span style='color: #94A3B8; font-size: 12px;'>Gemini API digunakan untuk analisis momen viral otomatis dan penyusunan judul serta deskripsi. Google menyediakan kuota gratis yang sangat melimpah tanpa perlu kartu kredit.</span>"
            "<ol style='margin-top: 8px; margin-bottom: 4px; padding-left: 20px; line-height: 1.7;'>"
            "<li>Buka browser Anda dan kunjungi situs resmi: <b style='color: #38BDF8;'>https://aistudio.google.com</b></li>"
            "<li>Login menggunakan akun Google / Gmail Anda.</li>"
            "<li>Klik tombol biru <b>'Get API key'</b> (di panel menu sebelah kiri) atau <b>'Create API key'</b>.</li>"
            "<li>Pilih opsi <b>'Create API key in new project'</b>.</li>"
            "<li>Google akan membuat kode API Key unik. Klik tombol <b>Copy</b> untuk menyalin kode tersebut.</li>"
            "<li>Buka ENCLip Studio → masuk ke tab <b>Studio Klip</b> (pada kolom <i>Gemini API Key</i>) atau buka menu <b>● Sistem</b> di pojok kanan atas.</li>"
            "<li>Tempelkan (Paste) kode API Key Anda ke kolom yang tersedia, lalu klik <b>Uji Koneksi</b>. Status akan berubah hijau: <b style='color: #34D399;'>Terhubung (Gemini Aktif)</b>. Kunci otomatis tersimpan secara aman di komputer Anda.</li>"
            "</ol>"
            "</div>"
            "<h3 style='color: #38BDF8; margin-top: 10px; margin-bottom: 6px;'>Alur 4 Tahap Pembuatan Klip</h3>"
            "<ol style='margin-top: 4px; padding-left: 20px; line-height: 1.65;'>"
            "<li><b>1 · Pilih Video:</b> Masukkan video dari komputer Anda (drag &amp; drop file MP4/MKV/MOV) atau unduh langsung dari tautan YouTube/TikTok.</li>"
            "<li><b>2 · Studio Klip:</b> Atur metode pemotongan, rasio layar (9:16 vertikal), gaya font subtitle, dan musik latar. Pratinjau video di sebelah kanan langsung mencerminkan setiap perubahan secara real-time.</li>"
            "<li><b>3 · Review &amp; Trim:</b> Tinjau klip yang berhasil dibuat, sesuaikan batas detik awal/akhir pada garis waktu jika diperlukan, dan edit kata pada subtitle sebelum disimpan.</li>"
            "<li><b>4 · Hasil Ekspor:</b> Tonton hasil video akhir beresolusi tinggi, salin caption otomatis, atau buka foldernya untuk diunggah ke TikTok, Instagram Reels, atau YouTube Shorts.</li>"
            "</ol>"
            "<hr style='border: 0; border-top: 1px solid #1F1F2B; margin: 14px 0;'>"
            "<h3 style='color: #60A5FA; margin-bottom: 6px;'>Pilihan Metode Pemotongan Video</h3>"
            "<ul style='padding-left: 20px; line-height: 1.65;'>"
            "<li><b style='color: #93C5FD;'>Mode Otomatis (3 Opsi Pemotongan):</b>"
            "<ul>"
            "<li><b>Otomatis AI (Momen Terbaik):</b> AI menganalisis transkrip pembicaraan dan lonjakan suara untuk menemukan potongan terbaik secara utuh tanpa kalimat terpotong.</li>"
            "<li><b>Bagi Jumlah Klip:</b> Membagi durasi video secara rata menjadi sejumlah bagian (misal 5 atau 10 klip) tanpa memanggil AI.</li>"
            "<li><b>Bagi Berdasarkan Durasi:</b> Memotong video secara berurutan setiap sekian detik yang Anda tentukan (misal setiap 60 detik).</li>"
            "</ul></li>"
            "<li><b style='color: #FBBF24;'>Clipping Manual Bebas (Multi-Segmen):</b>"
            "<ul>"
            "<li>Gunakan tombol <b>[ Ambil Waktu</b> dan <b>Ambil Waktu ]</b> saat memutar video di pratinjau kanan untuk menentukan awal dan akhir, lalu klik <b>+ Tambah Segmen</b>.</li>"
            "<li>Anda bisa membuat banyak segmen sekaligus (#01, #02, #03...) atau klik <b>1 Video Utuh</b> untuk memproses seluruh video tanpa memotong.</li>"
            "<li>Pada Mode Manual, mesin analisis momen AI otomatis dinonaktifkan sehingga hanya modul suara ke teks (transkripsi) yang bekerja membuat subtitle.</li>"
            "</ul></li>"
            "</ul>"
            "<hr style='border: 0; border-top: 1px solid #1F1F2B; margin: 14px 0;'>"
            "<h3 style='color: #34D399; margin-bottom: 6px;'>Rasio Kanvas &amp; Framing Kamera</h3>"
            "<ul style='padding-left: 20px; line-height: 1.65;'>"
            "<li><b>Tanpa Framing:</b> Mempertahankan rasio dan resolusi asli video tanpa pemotongan maupun blur.</li>"
            "<li><b>Framing Otomatis AI (9:16):</b> Kamera pintar adaptif yang otomatis mengikuti pembicara, membuat split screen 2 panel atas-bawah saat ada 2 pembicara, atau menambahkan blur sinematik halus pada video lanskap.</li>"
            "<li><b>Framing Manual Bebas:</b> Pilih rasio (9:16, 16:9, 1:1, 4:5, 21:9, atau Rasio Kustom) serta geser posisi X, Y, dan perbesar skala zoom langsung di layar pratinjau.</li>"
            "</ul>"
            "<hr style='border: 0; border-top: 1px solid #1F1F2B; margin: 14px 0;'>"
            "<h3 style='color: #F59E0B; margin-bottom: 6px;'>Subtitle, Audio &amp; Proteksi Konten</h3>"
            "<ul style='padding-left: 20px; line-height: 1.65;'>"
            "<li><b>Gaya Desain Huruf (Dropdown):</b> Pilihan font modern yang nyaman di mata (Modern Bersih, CapCut Viral, Minimalis, dsb) yang dapat diatur bersamaan dengan posisi, ukuran, dan warna sorotan.</li>"
            "<li><b>Terjemahan Lirik Lagu:</b> Fitur khusus untuk video musik/lagu yang dapat menerjemahkan lirik otomatis dan mengekspor file <code>.srt</code> atau <code>.lrc</code>.</li>"
            "<li><b>Proteksi Anti-Klaim:</b> Opsi percepatan tempo halus 1.03x dan balik horizontal (mirror) untuk membantu video lolos deteksi otomatis hak cipta.</li>"
            "<li><b>Area Aman HP (Safe Zone):</b> Menampilkan batas aman agar subtitle tidak tertutup oleh tombol navigasi TikTok, Reels, atau Shorts.</li>"
            "</ul>"
            "<hr style='border: 0; border-top: 1px solid #1F1F2B; margin: 14px 0;'>"
            "<h3 style='color: #60A5FA; margin-bottom: 6px;'>Lisensi &amp; Ketentuan Pengembangan</h3>"
            "<p style='color: #94A3B8; margin-top: 2px; margin-bottom: 4px; line-height: 1.6;'>"
            "ENCLip Studio dikembangkan dan dimiliki secara eksklusif oleh <b>Edvan</b>. "
            "Pihak mana pun yang ingin menggunakan, mengadaptasi, memodifikasi, atau mengembangkan lebih lanjut "
            "(fork / karya turunan) <b>wajib mencantumkan nama Edvan secara jelas sebagai pencipta orisinal</b> "
            "di dalam kode sumber, dokumentasi, dan antarmuka aplikasi."
            "</p>"
            "</div>"
        )
        layout.addWidget(content, 1)
        return page

    def set_clipping_mode_quick(self, kind: str) -> None:
        if not hasattr(self, "mode_combo"):
            return
        if kind == "manual":
            idx = self.mode_combo.findData("manual")
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
        else:
            if self.mode_combo.currentData() == "manual":
                idx = self.mode_combo.findData("smart")
                if idx >= 0:
                    self.mode_combo.setCurrentIndex(idx)
        if hasattr(self, "create_subtabs") and self.create_subtabs.currentIndex() != 0:
            self.create_subtabs.setCurrentIndex(0)
        self.update_mode_settings()

    def grab_preview_time_for_manual(self, is_start: bool = True) -> None:
        pos_sec = 0.0
        if hasattr(self, "create_preview_player"):
            pos_sec = max(0.0, self.create_preview_player.position() / 1000.0)
        formatted = format_time(pos_sec)
        if is_start and hasattr(self, "pre_manual_start_edit"):
            self.pre_manual_start_edit.setText(formatted)
        elif not is_start and hasattr(self, "pre_manual_end_edit"):
            self.pre_manual_end_edit.setText(formatted)

    def refresh_pre_manual_list_ui(self) -> None:
        if not hasattr(self, "pre_manual_list"):
            return
        self.pre_manual_list.clear()
        segs = getattr(self, "pre_manual_segments", [])
        if not segs:
            self.pre_manual_list.addItem(
                "Belum ada segmen manual · Klik [ Ambil Waktu ] lalu + Tambah Segmen, atau lanjut ke Timeline Review"
            )
        else:
            for idx, item in enumerate(segs, start=1):
                s_t = format_time(float(item.get("start", 0.0)))
                e_t = format_time(float(item.get("end", 0.0)))
                dur_t = max(0.0, float(item.get("end", 0.0)) - float(item.get("start", 0.0)))
                ttl = str(item.get("title") or f"Segmen Manual #{idx:02d}")
                self.pre_manual_list.addItem(f"#{idx:02d}   {s_t} → {e_t}  ({dur_t:.0f} dtk)   ·   {ttl}")
        if hasattr(self, "create_seek_slider") and hasattr(self.create_seek_slider, "set_segments"):
            is_man = hasattr(self, "mode_combo") and self.mode_combo.currentData() == "manual"
            self.create_seek_slider.set_segments(segs if is_man else [])
        self.update_segment_estimate()

    def add_pre_manual_segment(self) -> None:
        s_val = parse_time(self.pre_manual_start_edit.text().strip()) if hasattr(self, "pre_manual_start_edit") else None
        e_val = parse_time(self.pre_manual_end_edit.text().strip()) if hasattr(self, "pre_manual_end_edit") else None
        if s_val is None or e_val is None or e_val <= s_val:
            QMessageBox.warning(
                self,
                "Rentang Waktu Tidak Valid",
                "Masukkan waktu Mulai dan Selesai yang benar (contoh: 00:15 sampai 01:10).",
            )
            return
        if self.source_duration > 0 and e_val > self.source_duration + 0.5:
            e_val = self.source_duration
        if e_val <= s_val:
            QMessageBox.warning(self, "Rentang Waktu", "Waktu selesai melebihi durasi video sumber.")
            return
        ttl = self.pre_manual_title_edit.text().strip() if hasattr(self, "pre_manual_title_edit") else ""
        if not hasattr(self, "pre_manual_segments"):
            self.pre_manual_segments = []
        idx = len(self.pre_manual_segments) + 1
        self.pre_manual_segments.append({
            "start": round(float(s_val), 2),
            "end": round(float(e_val), 2),
            "title": ttl or f"Segmen Manual #{idx:02d}",
        })
        if hasattr(self, "pre_manual_title_edit"):
            self.pre_manual_title_edit.clear()
        if hasattr(self, "pre_manual_start_edit") and hasattr(self, "pre_manual_end_edit"):
            next_end = min(self.source_duration, float(e_val) + 30.0) if self.source_duration > float(e_val) + 2.0 else float(e_val) + 30.0
            self.pre_manual_start_edit.setText(format_time(float(e_val)))
            self.pre_manual_end_edit.setText(format_time(next_end))
        self.refresh_pre_manual_list_ui()
        if hasattr(self, "pre_manual_list") and self.pre_manual_segments:
            self.pre_manual_list.setCurrentRow(len(self.pre_manual_segments) - 1)

    def add_full_video_manual_segment(self) -> None:
        end_sec = self.source_duration if self.source_duration > 0 else 600.0
        if hasattr(self, "create_preview_player") and self.create_preview_player.duration() > 0:
            end_sec = self.create_preview_player.duration() / 1000.0
        self.pre_manual_segments = [{
            "start": 0.0,
            "end": round(max(1.0, float(end_sec)), 2),
            "title": "Video Utuh (Awal sampai Akhir)",
        }]
        if hasattr(self, "pre_manual_start_edit"):
            self.pre_manual_start_edit.setText("00:00")
        if hasattr(self, "pre_manual_end_edit"):
            self.pre_manual_end_edit.setText(format_time(end_sec))
        self.refresh_pre_manual_list_ui()

    def remove_selected_pre_manual_segment(self) -> None:
        if not hasattr(self, "pre_manual_list") or not getattr(self, "pre_manual_segments", []):
            return
        row = self.pre_manual_list.currentRow()
        if 0 <= row < len(self.pre_manual_segments):
            self.pre_manual_segments.pop(row)
        else:
            self.pre_manual_segments.pop()
        self.refresh_pre_manual_list_ui()

    def update_mode_settings(self) -> None:
        if not hasattr(self, "mode_stack"):
            return
        mode = self.mode_combo.currentData()
        is_manual = mode == "manual"
        is_smart_ai = mode == "smart"
        if hasattr(self, "top_clip_mode_cards"):
            self.top_clip_mode_cards.set_value("manual" if is_manual else "auto", emit=False)
        if hasattr(self, "auto_submode_widget"):
            self.auto_submode_widget.setVisible(not is_manual)
        if hasattr(self, "mode_group_box"):
            self.mode_group_box.setTitle(
                "Pemotongan Manual Multi-Segmen" if is_manual else "Pengaturan Pemotongan Mode Otomatis"
            )
        if hasattr(self, "top_clip_mode_desc"):
            if is_manual:
                self.top_clip_mode_desc.setText(
                    "<b>Mode Manual (Multi-Segmen):</b> Tandai waktu mulai & selesai bebas dari video. "
                    "Mesin Analisis AI dimatikan — hanya <b>Suara ke Teks</b> yang aktif untuk membuat subtitle."
                )
                self.top_clip_mode_desc.setStyleSheet(
                    "color: #FDE68A; background: #120E06; border: 1px solid #92400E; border-radius: 7px; padding: 6px 10px; font-size: 11px;"
                )
            elif mode == "split_count":
                self.top_clip_mode_desc.setText(
                    "<b>Mode Otomatis · Bagi Jumlah Klip:</b> Video dibagi rata menjadi beberapa klip berdurasi sama panjang dari awal sampai akhir."
                )
                self.top_clip_mode_desc.setStyleSheet(
                    "color: #BFDBFE; background: #0B1222; border: 1px solid #1E3A8A; border-radius: 7px; padding: 6px 10px; font-size: 11px;"
                )
            elif mode == "split_duration":
                self.top_clip_mode_desc.setText(
                    "<b>Mode Otomatis · Bagi Berdasarkan Durasi:</b> Video dipotong otomatis berurutan setiap sekian detik sesuai durasi pilihan Anda."
                )
                self.top_clip_mode_desc.setStyleSheet(
                    "color: #BFDBFE; background: #0B1222; border: 1px solid #1E3A8A; border-radius: 7px; padding: 6px 10px; font-size: 11px;"
                )
            else:
                self.top_clip_mode_desc.setText(
                    "<b>Mode Otomatis · Otomatis AI:</b> Menganalisis isi pembicaraan & lonjakan suara untuk memilihkan momen terbaik "
                    "secara otomatis dengan kalimat utuh."
                )
                self.top_clip_mode_desc.setStyleSheet(
                    "color: #D4D4D8; background: #0D0D14; border: 1px solid #2563EB; border-radius: 7px; padding: 6px 10px; font-size: 11px;"
                )
        self.mode_stack.setCurrentIndex({"smart": 0, "split_count": 1, "split_duration": 2, "manual": 3}.get(mode, 0))
        self.update_ai_engine_visibility()
        if hasattr(self, "pre_manual_list") and is_manual and self.pre_manual_list.count() == 0:
            self.refresh_pre_manual_list_ui()
        if hasattr(self, "create_seek_slider") and hasattr(self.create_seek_slider, "set_segments"):
            self.create_seek_slider.set_segments(getattr(self, "pre_manual_segments", []) if is_manual else [])
        self.resize_mode_stack()
        self.update_segment_estimate()

    def update_ai_engine_visibility(self) -> None:
        mode = self.mode_combo.currentData() if hasattr(self, "mode_combo") else "smart"
        is_smart_ai = mode == "smart"
        is_gemini_llm = hasattr(self, "ai_provider_combo") and self.ai_provider_combo.currentData() == "gemini"
        is_gemini_stt = hasattr(self, "whisper_combo") and self.whisper_combo.currentData() == "gemini"
        if hasattr(self, "ai_analysis_container"):
            self.ai_analysis_container.setVisible(is_smart_ai)
        if hasattr(self, "ai_engine_mode_note"):
            self.ai_engine_mode_note.setVisible(not is_smart_ai)
            if mode == "manual":
                self.ai_engine_mode_note.setText(
                    "<b>Mode Manual Aktif:</b> Mesin Analisis Momen AI tidak digunakan karena Anda menentukan titik potong sendiri. "
                    "Hanya <b>Mesin Suara ke Teks</b> di bawah ini yang digunakan untuk membuat subtitle."
                )
            elif not is_smart_ai:
                self.ai_engine_mode_note.setText(
                    "<b>Pemotongan Bagi Rata Aktif:</b> Mesin Analisis Momen AI tidak digunakan karena durasi dibagi rata secara otomatis. "
                    "Hanya <b>Mesin Suara ke Teks</b> yang digunakan untuk membuat subtitle."
                )
        if hasattr(self, "ai_engine_group"):
            self.ai_engine_group.setTitle(
                "Mesin Analisis AI && Suara ke Teks" if is_smart_ai else "Mesin Suara ke Teks (Pembuat Subtitle Otomatis)"
            )
        if hasattr(self, "local_panel"):
            self.local_panel.setVisible(is_smart_ai and not is_gemini_llm)
        if hasattr(self, "gemini_panel"):
            needs_gemini_key = (is_smart_ai and is_gemini_llm) or is_gemini_stt
            self.gemini_panel.setVisible(needs_gemini_key)

    def update_profile_hint(self) -> None:
        if not hasattr(self, "profile_hint"):
            return
        hints = {
            "auto": "Universal AI: Menyesuaikan pemilihan klip secara cerdas untuk segala jenis video (vlog, ulasan, obrolan, maupun hiburan).",
            "podcast": "Podcast & Dialog: Mengutamakan siklus tanya-jawab utuh, argumen kuat, dan kesimpulan pembicara tanpa terpotong.",
            "standard": "Podcast & Dialog: Mengutamakan siklus tanya-jawab utuh, argumen kuat, dan kesimpulan pembicara tanpa terpotong.",
            "live": "Gaming & Stream: Menangkap momen aksi puncak, reaksi spontan, tawa, dan highlight gameplay paling seru.",
            "education": "Edukasi & Tutorial: Mengambil penjelasan konsep inti, langkah praktis, dan tips utuh dari awal hingga solusi.",
            "music": "Musik & Lirik: Fokus pada bagian reff/chorus dan bait terbaik, sekaligus mengaktifkan opsi terjemahan lirik.",
            "cinematic": "Vlog & Sinematik: Menjaga kesinambungan cerita, suasana visual, dan narasi emosional tanpa potongan kasar.",
            "manual": "Transkrip tetap dibuat penuh untuk memudahkan Anda memilih segmen sendiri di tab Review.",
        }
        p_val = self.profile_combo.currentData() if hasattr(self, "profile_combo") else "auto"
        self.profile_hint.setText(hints.get(str(p_val), hints["auto"]))
        flavor_map = {
            "auto": "universal",
            "podcast": "spicy_drama",
            "live": "funny_blunder",
            "education": "deep_meat",
            "music": "music_lyrics",
            "cinematic": "cinematic_story",
        }
        if p_val == "music" and hasattr(self, "translate_lyrics_check") and not self.translate_lyrics_check.isChecked():
            self.translate_lyrics_check.setChecked(True)
        target_flavor = flavor_map.get(str(p_val))
        if target_flavor and hasattr(self, "clip_flavor_combo"):
            m_idx = self.clip_flavor_combo.findData(target_flavor)
            if m_idx >= 0:
                self.clip_flavor_combo.setCurrentIndex(m_idx)

    def update_smart_duration_fields(self) -> None:
        if not hasattr(self, "smart_duration_mode"):
            return
        self.resize_mode_stack()

    def resize_mode_stack(self) -> None:
        if not hasattr(self, "mode_stack"):
            return
        current = self.mode_stack.currentWidget()
        if current is None:
            return
        current.adjustSize()
        hint_h = current.sizeHint().height()
        layout_h = current.layout().sizeHint().height() if current.layout() else 0
        needed = max(140, hint_h, layout_h) + 12
        self.mode_stack.setFixedHeight(needed)

    def update_subtitle_controls(self) -> None:
        if not hasattr(self, "subtitle_enabled"):
            return
        enabled = self.subtitle_enabled.isChecked()
        for attr in (
            "subtitle_combo",
            "subtitle_mode_combo",
            "subtitle_position_combo",
            "subtitle_color_combo",
            "subtitle_active_color_combo",
            "subtitle_color_button",
            "subtitle_color_hex",
            "subtitle_lines_combo",
            "subtitle_lines_pills",
            "subtitle_size_combo",
            "subtitle_size_pills",
        ):
            w_obj = getattr(self, attr, None)
            if w_obj is not None:
                w_obj.setEnabled(enabled)
        if hasattr(self, "preview_subtitle_sample") and hasattr(self, "language_combo"):
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
            f"QPushButton#colorSwatch {{ background: {color}; border: 2px solid #3B82F6; border-radius: 15px; }}"
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
        font_size: int | None = None,
        max_lines: int | None = None,
        active_word_idx: int = 2,
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
        sz = font_size or 14
        pad = f"{max(3, int(sz * 0.28))}px {max(8, int(sz * 0.65))}px"
        style_meta = {
            "bold": {
                "font": "'Segoe UI Variable Display', 'Segoe UI', -apple-system, sans-serif",
                "weight": "800",
                "italic": False,
                "uppercase": False,
                "css": f"background: rgba(0, 0, 0, 165); color: {accent}; padding: {pad}; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.15); font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; font-size: {sz}px; font-weight: 800; letter-spacing: 0.3px;",
            },
            "highlight": {
                "font": "'Montserrat', 'Segoe UI Variable Display', 'Segoe UI', sans-serif",
                "weight": "800",
                "italic": False,
                "uppercase": False,
                "css": f"background: rgba(0, 0, 0, 150); color: {accent}; padding: {pad}; border-radius: 8px; border: 1px solid rgba(250, 204, 21, 0.25); font-family: 'Montserrat', 'Segoe UI', sans-serif; font-size: {sz}px; font-weight: 800; letter-spacing: 0.2px;",
            },
            "karaoke": {
                "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
                "weight": "800",
                "italic": False,
                "uppercase": False,
                "css": f"background: rgba(10, 10, 15, 160); color: {accent}; padding: {pad}; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.12); font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; font-size: {sz}px; font-weight: 800;",
            },
            "neon": {
                "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
                "weight": "800",
                "italic": False,
                "uppercase": False,
                "css": f"background: rgba(4, 20, 32, 180); color: #38BDF8; padding: {pad}; border: 1.5px solid rgba(56, 189, 248, 0.6); border-radius: 8px; font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; font-size: {sz}px; font-weight: 800; letter-spacing: 0.3px;",
            },
            "box": {
                "font": "'Segoe UI Semibold', 'Segoe UI', sans-serif",
                "weight": "700",
                "italic": False,
                "uppercase": False,
                "css": f"background: rgba(0, 0, 0, 220); color: {accent}; padding: {pad}; border-radius: 5px; border: 1px solid #3F3F46; font-family: 'Segoe UI Semibold', 'Segoe UI', sans-serif; font-size: {sz}px; font-weight: 700;",
            },
            "minimal": {
                "font": "'Segoe UI Variable Text', 'Segoe UI', sans-serif",
                "weight": "600",
                "italic": False,
                "uppercase": False,
                "css": f"background: rgba(0, 0, 0, 110); color: {accent}; padding: {pad}; border-radius: 6px; border: none; font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif; font-size: {max(11, sz - 1)}px; font-weight: 600; letter-spacing: 0.2px;",
            },
            "classic": {
                "font": "'Segoe UI Semibold', 'Segoe UI', sans-serif",
                "weight": "700",
                "italic": False,
                "uppercase": False,
                "css": f"background: rgba(0, 0, 0, 170); color: #FFFFFF; padding: {pad}; border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.15); font-family: 'Segoe UI Semibold', 'Segoe UI', sans-serif; font-size: {sz}px; font-weight: 700;",
            },
        }
        meta = style_meta.get(style, style_meta["bold"])
        label.setStyleSheet(meta["css"])
        f_fam = meta["font"]
        is_up = bool(meta["uppercase"])
        is_it = bool(meta["italic"])

        def _wrap_style_text(s: str, col: str, is_active_word: bool = False) -> str:
            t_out = s.upper() if is_up else s
            fs_use = (sz + 1) if is_active_word else sz
            wt_use = "900" if is_active_word else meta["weight"]
            bg_span = ""
            if is_active_word and style == "highlight":
                bg_span = "background-color: #FACC15; color: #09090D; padding: 1px 5px; border-radius: 4px;"
                col = "#09090D"
            elif is_active_word and style == "neon":
                col = "#38BDF8"
                bg_span = "border-bottom: 2px solid #38BDF8;"
            elif is_active_word and style == "karaoke":
                col = "#FDE047"
                bg_span = "font-weight: 900;"
            elif is_active_word and style == "box":
                bg_span = "background-color: #2563EB; color: #FFFFFF; padding: 1px 4px; border-radius: 3px;"
                col = "#FFFFFF"
            span = (
                f"<span style=\"font-family:{f_fam}; font-size:{fs_use}px; font-weight:{wt_use}; "
                f"{'font-style:italic;' if is_it else ''} color:{col}; {bg_span}\">{t_out}</span>"
            )
            return span

        if sample:
            label.setTextFormat(Qt.TextFormat.RichText)
            sub_mode = self.subtitle_mode_combo.currentData() if hasattr(self, "subtitle_mode_combo") else "active_highlight"
            lines_val = (
                max_lines
                if max_lines is not None
                else (self.subtitle_lines_combo.currentData() if hasattr(self, "subtitle_lines_combo") else 2)
            )
            active_col = (
                self.subtitle_active_color_combo.currentData()
                if hasattr(self, "subtitle_active_color_combo")
                else "#FFDD00"
            )
            use_emoji = hasattr(self, "emoji_subtitles_check") and self.emoji_subtitles_check.isChecked()
            censor_on = hasattr(self, "censor_profanity_checkbox") and self.censor_profanity_checkbox.isChecked()
            emoji_prefix = "✨ " if use_emoji else ""

            last_w = "g*la!" if censor_on else "nyata!"
            demo_words = ["Strategi", "tepat", "ini", "mengubah", "hasil", last_w]
            demo_colors_ctx = ["#FFDD00", "#38BDF8", "#FFFFFF", "#00F57A", "#FFDD00", "#FF4D4D"]
            w_idx = active_word_idx % len(demo_words)
            preview_active_col = demo_colors_ctx[w_idx] if active_col in ("auto_context", "auto") else active_col

            base_col = "#67E8F9" if style == "neon" else ("#FEF3C7" if style == "classic" else accent)

            if sub_mode == "single_word":
                sample_text = emoji_prefix + _wrap_style_text(demo_words[w_idx], preview_active_col, is_active_word=True)
            elif sub_mode == "active_highlight":
                rendered_words = []
                limit_w = 4 if lines_val == 1 else len(demo_words)
                w_idx_clamped = active_word_idx % limit_w
                for idx_w, w_str in enumerate(demo_words[:limit_w]):
                    if idx_w == w_idx_clamped:
                        c_hex = demo_colors_ctx[idx_w] if active_col in ("auto_context", "auto") else active_col
                        rendered_words.append(_wrap_style_text(w_str, c_hex, is_active_word=True))
                    else:
                        rendered_words.append(_wrap_style_text(w_str, base_col, is_active_word=False))
                if lines_val >= 2 and len(rendered_words) >= 6:
                    mid = len(rendered_words) // 2
                    sample_text = emoji_prefix + " ".join(rendered_words[:mid]) + "<br>" + " ".join(rendered_words[mid:])
                else:
                    sample_text = emoji_prefix + " ".join(rendered_words)
            elif lines_val == 1:
                sample_text = emoji_prefix + _wrap_style_text(f"Strategi tepat ini mengubah {last_w}", base_col, False)
            else:
                sample_text = (
                    emoji_prefix
                    + _wrap_style_text("Strategi tepat ini", base_col, False)
                    + "<br>"
                    + _wrap_style_text(f"mengubah hasil {last_w}", base_col, False)
                )

            if hasattr(self, "translate_lyrics_check") and self.translate_lyrics_check.isChecked():
                lyr_mode = self.lyrics_display_mode_combo.currentData() if hasattr(self, "lyrics_display_mode_combo") else "dual"
                lang_code = str(self.lyrics_target_lang_combo.currentData() or "id") if hasattr(self, "lyrics_target_lang_combo") else "id"
                trans_samples = {
                    "id": "Kupikir kaulah satu-satunya tujuanku",
                    "en": "I thought you were my only destination",
                    "ja": "君だけが僕の目的地だと思っていた",
                    "ko": "너만이 나의 유일한 목적지라고 생각했어",
                }
                tr_line = trans_samples.get(lang_code, trans_samples["id"])
                if lyr_mode == "dual":
                    sub_fs = max(10, int(sz * 0.80))
                    sample_text = f"{sample_text}<br><font color='#93C5FD' style='font-size:{sub_fs}px;'><i>{tr_line}</i></font>"
                elif lyr_mode == "translated_only":
                    sample_text = f"♪ {tr_line}"

            label.setText(sample_text)
        else:
            if "<font" in text or "</font>" in text or "<b>" in text or "<br>" in text:
                label.setTextFormat(Qt.TextFormat.RichText)
            else:
                label.setTextFormat(Qt.TextFormat.PlainText)
            label.setText(text)
        label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        label.adjustSize()
        label.setVisible(bool(text) or sample)
        label.raise_()

    def refresh_subtitle_preview_style(self) -> None:
        if not hasattr(self, "preview_subtitle_sample"):
            return
        lang_text = self.language_combo.currentText() if hasattr(self, "language_combo") else "Indonesia"
        style = (
            self.subtitle_combo.currentData()
            if hasattr(self, "subtitle_enabled") and self.subtitle_enabled.isChecked()
            else "none"
        )
        font_sz = self.subtitle_size_combo.currentData() if hasattr(self, "subtitle_size_combo") else 14
        lines_limit = self.subtitle_lines_combo.currentData() if hasattr(self, "subtitle_lines_combo") else 2
        word_tick = getattr(self, "_preview_word_tick", 2)
        self.apply_subtitle_preview_style(
            self.preview_subtitle_sample,
            style,
            language=lang_text,
            color=self.selected_subtitle_color(),
            sample=True,
            font_size=font_sz,
            max_lines=lines_limit,
            active_word_idx=word_tick,
        )
        if hasattr(self, "source_subtitle_overlay") and self.source_subtitle_overlay.isVisible():
            self.apply_subtitle_preview_style(
                self.source_subtitle_overlay,
                self.current_options.subtitle_style if self.current_options else "none",
                self.source_subtitle_overlay.text(),
                color=self.current_options.subtitle_color if self.current_options else "auto",
                font_size=getattr(self.current_options, "subtitle_font_size", 14) if self.current_options else font_sz,
                max_lines=getattr(self.current_options, "subtitle_max_lines", 2) if self.current_options else lines_limit,
            )

    def detect_faces_in_current_preview_frame(self) -> None:
        frame_img = getattr(self.create_preview_video, "current_frame", None)
        if frame_img is None or frame_img.isNull():
            self.smart_detected_badge.setText("Putar atau geser video terlebih dahulu untuk memindai subjek secara langsung.")
            return
        try:
            self.create_preview_video._last_face_detect_ts = 0.0
            self.create_preview_video._run_realtime_face_tracker(frame_img)
            self.create_preview_video.update()
            boxes = getattr(self.create_preview_video, "live_face_boxes", [])
            num_faces = len(boxes)
            if num_faces == 0:
                mode_code = "0"
                status_text = "Deteksi Live: 0 Wajah → Tampilan Sinematik Utuh (Tanpa Kotak Palsu)"
            elif num_faces == 1:
                mode_code = "1"
                status_text = "Deteksi Live: 1 Subjek → Fokus Potret 9:16 Presisi"
            else:
                mode_code = "2"
                status_text = f"Deteksi Live: {num_faces} Subjek → Split 2 Panel Atas-Bawah"
            idx = self.smart_preview_sim_combo.findData(mode_code)
            if idx >= 0:
                self.smart_preview_sim_combo.setCurrentIndex(idx)
            self.smart_detected_badge.setText(status_text)
            self.update_create_preview()
        except Exception as exc:
            self.smart_detected_badge.setText(f"Gagal memindai frame: {exc}")

    def update_create_preview(self) -> None:
        if not hasattr(self, "preview_summary") or not hasattr(self, "create_preview_frame"):
            return
        aspect = str(self.aspect_combo.currentData() or "9:16")
        mode_state = getattr(self, "framing_mode_state", "auto")
        if mode_state == "none" or aspect == "original":
            unified_mode = "original_native"
        elif mode_state == "manual" and hasattr(self, "manual_style_combo"):
            m_style = str(self.manual_style_combo.currentData() or "manual_fit")
            if m_style == "manual_ambient":
                unified_mode = "manual_ambient"
            elif m_style == "manual_crop":
                unified_mode = "manual_crop"
            elif m_style == "manual_split":
                unified_mode = "manual_split"
            elif m_style == "manual_facecam":
                unified_mode = "facecam_9_16"
            else:
                unified_mode = "manual_fit"
        else:
            unified_mode = (
                str(self.unified_format_combo.currentData() or "auto_universal_9_16")
                if hasattr(self, "unified_format_combo")
                else "auto_universal_9_16"
            )

        if hasattr(self, "create_preview_video"):
            self.create_preview_video.set_preview_mode(str(unified_mode))
            if hasattr(self, "manual_crop_x_slider"):
                self.create_preview_video.set_manual_crop_x(self.manual_crop_x_slider.value() / 100.0)
            if hasattr(self, "manual_crop_y_slider"):
                self.create_preview_video.set_manual_crop_y(self.manual_crop_y_slider.value() / 100.0)
            if hasattr(self, "manual_zoom_slider"):
                self.create_preview_video.set_manual_zoom(self.manual_zoom_slider.value() / 100.0)
            if hasattr(self, "realtime_face_box_check"):
                self.create_preview_video.set_show_face_boxes(
                    mode_state == "auto" and self.realtime_face_box_check.isChecked()
                )
            if hasattr(self, "mirror_video_check"):
                self.create_preview_video.mirror_horizontal = self.mirror_video_check.isChecked()
            if hasattr(self, "color_boost_check"):
                self.create_preview_video.color_boost_enabled = self.color_boost_check.isChecked()
            self.create_preview_video.update()

        if hasattr(self, "create_preview_player") and hasattr(self, "speed_shift_check"):
            target_rate = 1.03 if self.speed_shift_check.isChecked() else 1.0
            if abs(self.create_preview_player.playbackRate() - target_rate) > 0.005:
                self.create_preview_player.setPlaybackRate(target_rate)

        tabs_h = self.tabs.height() if hasattr(self, "tabs") and self.tabs.height() > 100 else max(400, self.height() - 70)
        max_canvas_h = max(170, tabs_h - 160)
        if self.isMaximized() or self.isFullScreen():
            max_canvas_h = min(max_canvas_h, int(tabs_h * 0.75))

        if (
            hasattr(self, "create_splitter")
            and self.create_splitter.sizes()
            and len(self.create_splitter.sizes()) > 1
            and self.create_splitter.sizes()[1] > 100
        ):
            avail_w = max(210, self.create_splitter.sizes()[1] - 32)
        else:
            avail_w = max(210, int((self.width() - 40) * 0.45) - 24)

        def _parse_ar(ar_str: str) -> float:
            if ar_str == "original":
                f_img = getattr(self.create_preview_video, "current_frame", None)
                if f_img is not None and not f_img.isNull() and f_img.height() > 0:
                    return f_img.width() / f_img.height()
                return 16 / 9
            try:
                if ":" in ar_str:
                    parts = ar_str.split(":")
                    w_ar, h_ar = float(parts[0]), float(parts[1])
                    if w_ar > 0 and h_ar > 0:
                        return w_ar / h_ar
            except Exception:
                pass
            return 9 / 16

        ar = _parse_ar(aspect)

        if (avail_w / max_canvas_h) > ar:
            canvas_height = max_canvas_h
            canvas_width = int(canvas_height * ar)
        else:
            canvas_width = avail_w
            canvas_height = int(canvas_width / ar)

        canvas_width = max(170, min(avail_w, canvas_width))
        canvas_height = max(130, min(max_canvas_h, canvas_height))

        badge_short_map = {
            "original_native": "Asli · Tanpa Framing",
            "auto_universal_9_16": "9:16 · Adaptif Universal",
            "auto_podcast_9_16": "9:16 · Podcast AI",
            "ambient_9_16": f"{aspect} · Sinematik Blur",
            "split_2_9_16": "9:16 · Split 2 Panel",
            "crop_9_16": "9:16 · Fokus Subjek",
            "manual_crop": f"{aspect} · Bebas Zoom & Geser",
            "manual_fit": f"{aspect} · Fit Utuh",
            "manual_ambient": f"{aspect} · Blur Sinematik",
            "manual_split": f"{aspect} · Split 2 Panel",
            "facecam_9_16": "9:16 · Gaming Facecam",
            "standard_16_9": f"{aspect} · Fit Utuh",
        }
        short_badge = badge_short_map.get(
            str(unified_mode or ""),
            f"{aspect} · Manual" if mode_state == "manual" else f"{aspect} · Otomatis AI",
        )

        self.create_preview_frame.setFixedSize(canvas_width, canvas_height)
        self.create_preview_video.setAspectRatioMode(
            Qt.AspectRatioMode.KeepAspectRatioByExpanding
            if self.framing_combo.currentData() == "crop"
            else Qt.AspectRatioMode.KeepAspectRatio
        )
        self.preview_layout_badge.setText(short_badge)
        if hasattr(self, "safe_zone_overlay"):
            self.safe_zone_overlay.setGeometry(self.create_preview_video.rect())

        has_live_frame = (
            getattr(self.create_preview_video, "current_frame", None) is not None
            and not self.create_preview_video.current_frame.isNull()
        )
        is_smart_mode = (
            mode_state == "auto"
            and self.layout_combo.currentData() in ("auto_universal", "auto_smart", "podcast_split", "auto_split", "auto_single")
            and aspect == "9:16"
        )
        show_smart_canvas = is_smart_mode and not has_live_frame
        if hasattr(self, "smart_layout_overlay"):
            self.smart_layout_overlay.setGeometry(self.create_preview_video.rect())
            sim_mode = str(self.smart_preview_sim_combo.currentData() or "1") if hasattr(self, "smart_preview_sim_combo") else "1"
            self.smart_layout_overlay.set_face_mode(sim_mode)
            self.smart_layout_overlay.setVisible(show_smart_canvas)

        if hasattr(self, "preview_placeholder"):
            self.preview_placeholder.setVisible(not has_live_frame and not show_smart_canvas)

        is_facecam = self.layout_combo.currentData() in ("facecam_top", "auto_gaming")
        if hasattr(self, "facecam_box"):
            self.facecam_box.setVisible(is_facecam and mode_state == "manual")
            if is_facecam and mode_state == "manual":
                self.facecam_box.update_geometry_from_parent()

        if is_facecam and mode_state == "manual":
            self.preview_layout_overlay.setText("Mode Facecam · Geser kotak biru ke posisi kamera wajah")
            self.preview_layout_overlay.setVisible(True)
        else:
            self.preview_layout_overlay.setVisible(False)
        self.preview_facecam_top.setVisible(False)
        self.preview_facecam_main.setVisible(False)

        if self.subtitle_enabled.isChecked():
            language = self.language_combo.currentText() if hasattr(self, "language_combo") else "Indonesia"
            style = self.subtitle_combo.currentText().strip()
            font_sz = self.subtitle_size_combo.currentData() if hasattr(self, "subtitle_size_combo") else 14
            lines_limit = self.subtitle_lines_combo.currentData() if hasattr(self, "subtitle_lines_combo") else 2
            word_tick = getattr(self, "_preview_word_tick", 2)
            self.apply_subtitle_preview_style(
                self.preview_subtitle_sample,
                self.subtitle_combo.currentData(),
                language=language,
                color=self.selected_subtitle_color(),
                sample=True,
                font_size=font_sz,
                max_lines=lines_limit,
                active_word_idx=word_tick,
            )
            subtitle_summary = f"Subtitle {style}"
        else:
            self.apply_subtitle_preview_style(self.preview_subtitle_sample, "none")
            subtitle_summary = "Tanpa Subtitle"
        self.update_create_subtitle_position()

        fx_tags: list[str] = []
        if hasattr(self, "mirror_video_check") and self.mirror_video_check.isChecked():
            fx_tags.append("Mirror")
        if hasattr(self, "color_boost_check") and self.color_boost_check.isChecked():
            fx_tags.append("Warna+")
        if hasattr(self, "speed_shift_check") and self.speed_shift_check.isChecked():
            fx_tags.append("1.03x")
        fx_suffix = f"  ·  Efek: {', '.join(fx_tags)}" if fx_tags else ""
        self.preview_summary.setText(f"{short_badge}  ·  {subtitle_summary}{fx_suffix}")

        pw = max(1, self.create_preview_video.width())
        ph = max(1, self.create_preview_video.height())
        if hasattr(self, "preview_hook_banner"):
            hb_on = hasattr(self, "hook_banner_toggle") and self.hook_banner_toggle.isChecked()
            if hb_on:
                raw_custom = self.hook_banner_edit.text().strip() if hasattr(self, "hook_banner_edit") else ""
                hb_html = (
                    f"<span style='color:#FFFFFF;'>{raw_custom.upper()}</span>"
                    if raw_custom
                    else "<span style='color:#FFFFFF;'>JUDUL SOROTAN UTAMA</span>"
                )
                hb_font_sz = max(9, min(12, int(pw * 0.038)))
                self.preview_hook_banner.setTextFormat(Qt.TextFormat.RichText)
                self.preview_hook_banner.setText(hb_html)
                self.preview_hook_banner.setStyleSheet(
                    f"background: rgba(10, 10, 16, 230); color: #FFFFFF; "
                    f"font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; "
                    f"font-size: {hb_font_sz}px; font-weight: 800; padding: 6px 12px; border-radius: 8px; "
                    f"border: 1px solid rgba(59, 130, 246, 180);"
                )
                self.preview_hook_banner.setMaximumWidth(int(pw * 0.88))
                self.preview_hook_banner.adjustSize()
                lw_hb = self.preview_hook_banner.width()
                lh_hb = self.preview_hook_banner.height()
                hb_pos_mode = (
                    str(self.hook_banner_pos_combo.currentData() or "top")
                    if hasattr(self, "hook_banner_pos_combo")
                    else "top"
                )
                if hb_pos_mode == "free":
                    hx = int(pw * getattr(self, "hook_banner_free_x", 0.5) - lw_hb / 2.0)
                    hy = int(ph * getattr(self, "hook_banner_free_y", 0.11) - lh_hb / 2.0)
                elif hb_pos_mode == "center":
                    hx = (pw - lw_hb) // 2
                    hy = int(ph * 0.45 - lh_hb / 2.0)
                else:
                    hx = (pw - lw_hb) // 2
                    hy = max(22, int(ph * (0.11 if ph > pw else 0.14) - lh_hb / 2.0))
                hx = max(4, min(max(4, pw - lw_hb - 4), hx))
                hy = max(4, min(max(4, ph - lh_hb - 4), hy))
                self.preview_hook_banner.move(hx, hy)
                self.preview_hook_banner.setVisible(True)
                self.preview_hook_banner.raise_()
            else:
                self.preview_hook_banner.setVisible(False)
        self.save_studio_hook_settings()

        if hasattr(self, "preview_watermark_label"):
            wm_txt = self.watermark_edit.text().strip() if hasattr(self, "watermark_edit") else ""
            wm_img = self.watermark_image_edit.text().strip() if hasattr(self, "watermark_image_edit") else ""
            op_ratio = (
                (self.watermark_opacity_slider.value() / 100.0)
                if hasattr(self, "watermark_opacity_slider")
                else 0.75
            )
            op_alpha = int(op_ratio * 255)
            has_wm = False
            if wm_img and Path(wm_img).is_file():
                pix = QPixmap(wm_img)
                if not pix.isNull():
                    target_w = max(36, min(110, int(pw * 0.22)))
                    scaled_pix = pix.scaledToWidth(target_w, Qt.TransformationMode.SmoothTransformation)
                    out_pix = QPixmap(scaled_pix.size())
                    out_pix.fill(Qt.GlobalColor.transparent)
                    p_wm = QPainter(out_pix)
                    p_wm.setOpacity(op_ratio)
                    p_wm.drawPixmap(0, 0, scaled_pix)
                    p_wm.end()
                    self.preview_watermark_label.setText("")
                    self.preview_watermark_label.setPixmap(out_pix)
                    self.preview_watermark_label.setStyleSheet("background: transparent; border: 0; padding: 0;")
                    self.preview_watermark_label.resize(out_pix.size())
                    has_wm = True
            if not has_wm and (wm_txt or wm_img):
                display_wm = wm_txt or Path(wm_img).name
                self.preview_watermark_label.setPixmap(QPixmap())
                self.preview_watermark_label.setText(display_wm)
                self.preview_watermark_label.setStyleSheet(
                    f"background: rgba(0, 0, 0, 110); color: rgba(255, 255, 255, {op_alpha}); "
                    f"font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px;"
                )
                self.preview_watermark_label.adjustSize()
                has_wm = True

            if has_wm:
                lw, lh = self.preview_watermark_label.width(), self.preview_watermark_label.height()
                wm_pos = self.watermark_pos_combo.currentData() if hasattr(self, "watermark_pos_combo") else "top_right"
                if wm_pos == "free":
                    avail_w_wm = max(0, pw - lw)
                    avail_h_wm = max(0, ph - lh)
                    wx = int(avail_w_wm * self.watermark_free_x)
                    wy = int(avail_h_wm * self.watermark_free_y)
                else:
                    pos_coords = {
                        "top_left": (10, 10),
                        "top_right": (max(4, pw - lw - 10), 10),
                        "bottom_left": (10, max(4, ph - lh - 14)),
                        "bottom_right": (max(4, pw - lw - 10), max(4, ph - lh - 14)),
                        "center": (max(0, (pw - lw) // 2), max(0, (ph - lh) // 2)),
                    }
                    wx, wy = pos_coords.get(str(wm_pos), (max(4, pw - lw - 10), 10))
                self.preview_watermark_label.move(wx, wy)
                self.preview_watermark_label.setVisible(True)
                self.preview_watermark_label.raise_()
            else:
                self.preview_watermark_label.setPixmap(QPixmap())
                self.preview_watermark_label.setVisible(False)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self.ensure_splitter_balanced()
        if hasattr(self, "review_lock_overlay") and hasattr(self, "review_outer_wrapper"):
            self.review_lock_overlay.setGeometry(self.review_outer_wrapper.rect())
        if hasattr(self, "create_preview_frame"):
            self.update_create_preview()

    @staticmethod
    def subtitle_alignment(position: str) -> Qt.AlignmentFlag:
        if position == "top":
            return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        if position == "center":
            return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom

    def update_create_subtitle_position(self) -> None:
        if not hasattr(self, "create_preview_video") or not hasattr(self, "preview_subtitle_sample"):
            return
        label = self.preview_subtitle_sample
        if label.parent() != self.create_preview_video:
            label.setParent(self.create_preview_video)

        position = self.subtitle_position_combo.currentData() if hasattr(self, "subtitle_position_combo") else "auto"
        if hasattr(self, "translate_lyrics_check") and self.translate_lyrics_check.isChecked():
            lyr_pos = self.lyrics_pos_combo.currentData() if hasattr(self, "lyrics_pos_combo") else "auto"
            if lyr_pos != "auto":
                position = lyr_pos
        pw = max(1, self.create_preview_video.width())
        ph = max(1, self.create_preview_video.height())
        label.setMaximumWidth(max(120, int(pw * 0.88)))
        label.setWordWrap(True)
        label.adjustSize()
        lw = label.width()
        lh = label.height()

        if position == "free":
            available_width = max(0, pw - lw)
            available_height = max(0, ph - lh)
            fx = self.lyrics_free_x if (hasattr(self, "translate_lyrics_check") and self.translate_lyrics_check.isChecked() and hasattr(self, "lyrics_pos_combo") and self.lyrics_pos_combo.currentData() == "free") else self.subtitle_free_x
            fy = self.lyrics_free_y if (hasattr(self, "translate_lyrics_check") and self.translate_lyrics_check.isChecked() and hasattr(self, "lyrics_pos_combo") and self.lyrics_pos_combo.currentData() == "free") else self.subtitle_free_y
            label.move(int(available_width * fx), int(available_height * fy))
        elif position == "top":
            x = (pw - lw) // 2
            y = int(ph * 0.14)
            label.move(max(0, x), max(0, y))
        elif position == "center":
            x = (pw - lw) // 2
            y = (ph - lh) // 2
            label.move(max(0, x), max(0, y))
        else:
            x = (pw - lw) // 2
            live_faces = len(getattr(self.create_preview_video, "live_face_boxes", []))
            unified_mode = (
                self.unified_format_combo.currentData()
                if hasattr(self, "unified_format_combo")
                else "auto_universal_9_16"
            )
            mode_state = getattr(self, "framing_mode_state", "auto")
            is_split_active = (
                mode_state == "auto"
                and (
                    (unified_mode == "split_2_9_16" and live_faces >= 1)
                    or (unified_mode in ("auto_podcast_9_16", "auto_universal_9_16") and live_faces >= 2)
                )
            )
            if is_split_active and ph > pw:
                y = (ph - lh) // 2
            elif ph > pw:
                y = min(ph - lh - 18, max(24, int(ph * 0.74)))
            else:
                y = max(12, ph - lh - max(16, int(ph * 0.09)))
            label.move(max(0, x), y)

        label.raise_()
        is_sub_on = self.subtitle_enabled.isChecked() if hasattr(self, "subtitle_enabled") else True
        style = self.subtitle_combo.currentData() if hasattr(self, "subtitle_combo") else "bold"
        label.setVisible(is_sub_on and style != "none")

    def on_free_subtitle_moved(self, x: float, y: float) -> None:
        self.subtitle_free_x = max(0.0, min(1.0, x))
        self.subtitle_free_y = max(0.0, min(1.0, y))
        if hasattr(self, "translate_lyrics_check") and self.translate_lyrics_check.isChecked():
            if hasattr(self, "lyrics_pos_combo") and self.lyrics_pos_combo.currentData() != "free":
                idx_free = self.lyrics_pos_combo.findData("free")
                if idx_free >= 0:
                    self.lyrics_pos_combo.blockSignals(True)
                    self.lyrics_pos_combo.setCurrentIndex(idx_free)
                    self.lyrics_pos_combo.blockSignals(False)
            if hasattr(self, "lyrics_free_pos_widget"):
                self.lyrics_free_pos_widget.setVisible(True)
            self.lyrics_free_x = self.subtitle_free_x
            self.lyrics_free_y = self.subtitle_free_y
            if hasattr(self, "lyrics_x_slider"):
                self.lyrics_x_slider.blockSignals(True)
                self.lyrics_x_slider.setValue(int(self.lyrics_free_x * 100))
                self.lyrics_x_slider.blockSignals(False)
            if hasattr(self, "lyrics_x_val_lbl"):
                self.lyrics_x_val_lbl.setText(f"{int(self.lyrics_free_x * 100)}%")
            if hasattr(self, "lyrics_y_slider"):
                self.lyrics_y_slider.blockSignals(True)
                self.lyrics_y_slider.setValue(int(self.lyrics_free_y * 100))
                self.lyrics_y_slider.blockSignals(False)
            if hasattr(self, "lyrics_y_val_lbl"):
                self.lyrics_y_val_lbl.setText(f"{int(self.lyrics_free_y * 100)}%")
        else:
            if hasattr(self, "subtitle_position_combo") and self.subtitle_position_combo.currentData() != "free":
                idx_free = self.subtitle_position_combo.findData("free")
                if idx_free >= 0:
                    self.subtitle_position_combo.blockSignals(True)
                    self.subtitle_position_combo.setCurrentIndex(idx_free)
                    self.subtitle_position_combo.blockSignals(False)
        if hasattr(self, "preview_summary"):
            if hasattr(self, "translate_lyrics_check") and self.translate_lyrics_check.isChecked() and hasattr(self, "lyrics_pos_combo") and self.lyrics_pos_combo.currentData() == "free":
                self.preview_summary.setText(
                    f"Lirik bebas · X {self.lyrics_free_x:.0%}, Y {self.lyrics_free_y:.0%}"
                )
            elif self.subtitle_position_combo.currentData() == "free":
                self.preview_summary.setText(
                    f"Subtitle bebas · X {self.subtitle_free_x:.0%}, Y {self.subtitle_free_y:.0%}"
                )

    def on_hook_banner_dur_combo_changed(self) -> None:
        if hasattr(self, "hook_banner_dur_combo") and hasattr(self, "hook_banner_dur_spin"):
            dur_val = int(self.hook_banner_dur_combo.currentData() or 0)
            self.hook_banner_dur_spin.blockSignals(True)
            self.hook_banner_dur_spin.setValue(dur_val)
            self.hook_banner_dur_spin.blockSignals(False)
        self.update_create_preview()

    def on_free_hook_banner_moved(self, _x: float, _y: float) -> None:
        if not hasattr(self, "create_preview_video") or not hasattr(self, "preview_hook_banner"):
            return
        pw = max(1, self.create_preview_video.width())
        ph = max(1, self.create_preview_video.height())
        lw = self.preview_hook_banner.width()
        lh = self.preview_hook_banner.height()
        cx = (self.preview_hook_banner.x() + lw / 2.0) / pw
        cy = (self.preview_hook_banner.y() + lh / 2.0) / ph
        self.hook_banner_free_x = round(max(0.08, min(0.92, cx)), 4)
        self.hook_banner_free_y = round(max(0.05, min(0.92, cy)), 4)
        if hasattr(self, "hook_banner_pos_combo") and self.hook_banner_pos_combo.currentData() != "free":
            idx_free = self.hook_banner_pos_combo.findData("free")
            if idx_free >= 0:
                self.hook_banner_pos_combo.blockSignals(True)
                self.hook_banner_pos_combo.setCurrentIndex(idx_free)
                self.hook_banner_pos_combo.blockSignals(False)
        if hasattr(self, "preview_summary"):
            self.preview_summary.setText(
                f"Banner judul bebas · X {self.hook_banner_free_x:.0%}, Y {self.hook_banner_free_y:.0%}"
            )
        self.save_studio_hook_settings()

    def on_free_watermark_moved(self, _x: float, _y: float) -> None:
        if not hasattr(self, "create_preview_video") or not hasattr(self, "preview_watermark_label"):
            return
        pw = max(1, self.create_preview_video.width())
        ph = max(1, self.create_preview_video.height())
        lw = self.preview_watermark_label.width()
        lh = self.preview_watermark_label.height()
        avail_w = max(1, pw - lw)
        avail_h = max(1, ph - lh)
        rx = self.preview_watermark_label.x() / avail_w
        ry = self.preview_watermark_label.y() / avail_h
        self.watermark_free_x = round(max(0.0, min(1.0, rx)), 4)
        self.watermark_free_y = round(max(0.0, min(1.0, ry)), 4)
        if hasattr(self, "watermark_pos_combo") and self.watermark_pos_combo.currentData() != "free":
            idx_free = self.watermark_pos_combo.findData("free")
            if idx_free >= 0:
                self.watermark_pos_combo.blockSignals(True)
                self.watermark_pos_combo.setCurrentIndex(idx_free)
                self.watermark_pos_combo.blockSignals(False)
        if hasattr(self, "watermark_free_pos_widget"):
            self.watermark_free_pos_widget.setVisible(True)
        if hasattr(self, "watermark_x_slider"):
            self.watermark_x_slider.blockSignals(True)
            self.watermark_x_slider.setValue(int(self.watermark_free_x * 100))
            self.watermark_x_slider.blockSignals(False)
        if hasattr(self, "watermark_x_val_lbl"):
            self.watermark_x_val_lbl.setText(f"{int(self.watermark_free_x * 100)}%")
        if hasattr(self, "watermark_y_slider"):
            self.watermark_y_slider.blockSignals(True)
            self.watermark_y_slider.setValue(int(self.watermark_free_y * 100))
            self.watermark_y_slider.blockSignals(False)
        if hasattr(self, "watermark_y_val_lbl"):
            self.watermark_y_val_lbl.setText(f"{int(self.watermark_free_y * 100)}%")
        if hasattr(self, "preview_summary"):
            self.preview_summary.setText(
                f"Watermark bebas · X {self.watermark_free_x:.0%}, Y {self.watermark_free_y:.0%}"
            )

    def on_watermark_pos_changed(self) -> None:
        pos = self.watermark_pos_combo.currentData() if hasattr(self, "watermark_pos_combo") else "top_right"
        if hasattr(self, "watermark_free_pos_widget"):
            self.watermark_free_pos_widget.setVisible(pos == "free")
        self.update_create_preview()

    def on_watermark_x_slider_changed(self, val: int) -> None:
        self.watermark_free_x = val / 100.0
        if hasattr(self, "watermark_x_val_lbl"):
            self.watermark_x_val_lbl.setText(f"{val}%")
        self.update_create_preview()

    def on_watermark_y_slider_changed(self, val: int) -> None:
        self.watermark_free_y = val / 100.0
        if hasattr(self, "watermark_y_val_lbl"):
            self.watermark_y_val_lbl.setText(f"{val}%")
        self.update_create_preview()

    def save_studio_hook_settings(self) -> None:
        if getattr(self, "_loading_hook_settings", False):
            return
        try:
            hook_cfg_path = core.DATA_DIR / "studio_hook_settings.json"
            hook_cfg_path.parent.mkdir(parents=True, exist_ok=True)
            dur_val = (
                int(self.hook_banner_dur_combo.currentData() or 0)
                if hasattr(self, "hook_banner_dur_combo")
                else (self.hook_banner_dur_spin.value() if hasattr(self, "hook_banner_dur_spin") else 0)
            )
            pos_val = (
                str(self.hook_banner_pos_combo.currentData() or "top")
                if hasattr(self, "hook_banner_pos_combo")
                else "top"
            )
            payload = {
                "schema_v": 2,
                "hook_banner_enabled": bool(self.hook_banner_toggle.isChecked()) if hasattr(self, "hook_banner_toggle") else False,
                "hook_banner_text": self.hook_banner_edit.text().strip() if hasattr(self, "hook_banner_edit") else "",
                "hook_banner_duration": dur_val,
                "hook_banner_position": pos_val,
                "hook_banner_x": round(float(getattr(self, "hook_banner_free_x", 0.5)), 4),
                "hook_banner_y": round(float(getattr(self, "hook_banner_free_y", 0.11)), 4),
            }
            hook_cfg_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def load_studio_hook_settings(self) -> None:
        hook_cfg_path = core.DATA_DIR / "studio_hook_settings.json"
        if not hook_cfg_path.exists():
            self.save_studio_hook_settings()
            return
        self._loading_hook_settings = True
        try:
            data = json.loads(hook_cfg_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and int(data.get("schema_v", 1)) >= 2:
                if hasattr(self, "hook_banner_toggle") and "hook_banner_enabled" in data:
                    self.hook_banner_toggle.setChecked(bool(data["hook_banner_enabled"]))
                if hasattr(self, "hook_banner_edit") and "hook_banner_text" in data:
                    self.hook_banner_edit.setText(str(data.get("hook_banner_text") or ""))
                dur_v = int(data.get("hook_banner_duration", 5))
                if hasattr(self, "hook_banner_dur_combo"):
                    idx_d = self.hook_banner_dur_combo.findData(dur_v)
                    if idx_d >= 0:
                        self.hook_banner_dur_combo.setCurrentIndex(idx_d)
                if hasattr(self, "hook_banner_dur_spin"):
                    self.hook_banner_dur_spin.setValue(dur_v)
                pos_v = str(data.get("hook_banner_position") or "top")
                if hasattr(self, "hook_banner_pos_combo"):
                    idx_p = self.hook_banner_pos_combo.findData(pos_v)
                    if idx_p >= 0:
                        self.hook_banner_pos_combo.setCurrentIndex(idx_p)
                if "hook_banner_x" in data:
                    self.hook_banner_free_x = float(data["hook_banner_x"])
                if "hook_banner_y" in data:
                    self.hook_banner_free_y = float(data["hook_banner_y"])
        except Exception:
            pass
        finally:
            self._loading_hook_settings = False

    def update_segment_estimate(self) -> None:
        if not hasattr(self, "segment_estimate"):
            return
        mode = self.mode_combo.currentData() if hasattr(self, "mode_combo") else "smart"
        if hasattr(self, "start_button"):
            if mode == "manual":
                m_cnt = len(getattr(self, "pre_manual_segments", []))
                if m_cnt > 0:
                    self.start_button.setText(f"Proses && Render {m_cnt} Segmen Manual")
                else:
                    self.start_button.setText("Lanjut ke Timeline Review Manual")
            else:
                self.start_button.setText("Mulai Analisis && Buat Klip AI")

        if mode == "manual":
            m_cnt = len(getattr(self, "pre_manual_segments", []))
            if self.source_duration > 0:
                self.duration_info.setText(f"Durasi video sumber: {format_time(self.source_duration)}")
            if m_cnt > 0:
                total_sel = sum(max(0.0, float(s.get("end", 0)) - float(s.get("start", 0))) for s in getattr(self, "pre_manual_segments", []))
                self.segment_estimate.setText(
                    f"Mode Manual Multi-Segmen: {m_cnt} segmen siap diproses (total durasi terpilih {format_time(total_sel)})."
                )
            else:
                self.segment_estimate.setText(
                    "Mode Manual Aktif: Tambahkan satu atau banyak segmen di atas, atau langsung potong bebas di Timeline Review."
                )
            return

        if self.source_duration <= 0:
            self.duration_info.setText("Durasi sumber: belum dimuat")
            self.segment_estimate.setText("Estimasi jumlah klip akan tampil setelah video dipilih.")
            return
        total = self.source_duration
        self.duration_info.setText(f"Durasi video sumber: {format_time(total)}")
        if mode == "split_count":
            count = max(1, self.split_count.value())
            per_clip = total / count
            self.segment_estimate.setText(
                f"Bagi Rata: {count} klip · sekitar {format_time(per_clip)} per klip."
            )
        elif mode == "split_duration":
            duration = max(1, self.segment_duration.value())
            count = max(1, int((total + duration - 1) // duration))
            self.segment_estimate.setText(
                f"Bagi Durasi: sekitar {count} klip · masing-masing {format_time(duration)}."
            )
        elif self.smart_duration_mode.currentData() == "fixed":
            duration = max(1, self.smart_fixed_duration.value())
            count = min(self.max_clips.value(), max(1, int((total + duration - 1) // duration)))
            self.segment_estimate.setText(
                f"Otomatis AI: maksimal {count} klip · target {format_time(duration)} per klip."
            )
        else:
            requested = self.clip_count.value()
            limit = self.max_clips.value() if requested == 0 else min(requested, self.max_clips.value())
            self.segment_estimate.setText(
                f"Otomatis AI: memilih hingga {limit} momen terbaik · "
                + (
                    "durasi adaptif mengikuti alur kalimat utuh."
                    if self.min_duration.value() == 0 and self.max_duration.value() == 0
                    else f"rentang {self.min_duration.value() or 'otomatis'}–{self.max_duration.value() or 'otomatis'} detik."
                )
            )

    def seek_create_preview(self, position: int) -> None:
        self.create_preview_player.setPosition(position)
        if hasattr(self, "bgm_preview_player") and getattr(self, "bgm_file_path", ""):
            bgm_dur = self.bgm_preview_player.duration()
            if bgm_dur > 0:
                self.bgm_preview_player.setPosition(position % bgm_dur)

    def update_create_seek(self, position: int) -> None:
        if not self.create_seek_slider.isSliderDown():
            self.create_seek_slider.setValue(position)
        dur = self.create_preview_player.duration()
        time_str = f"{format_time(position / 1000)} / {format_time(dur / 1000)}"
        self.create_preview_time.setText(time_str)
        if hasattr(self, "create_preview_pos_time"):
            self.create_preview_pos_time.setText(time_str)

        new_tick = int(position / 420)
        if new_tick != getattr(self, "_preview_word_tick", -1):
            self._preview_word_tick = new_tick
            if hasattr(self, "subtitle_enabled") and self.subtitle_enabled.isChecked():
                self.refresh_subtitle_preview_style()
                self.update_create_subtitle_position()

        if hasattr(self, "create_preview_video") and hasattr(self, "smart_detected_badge"):
            boxes = getattr(self.create_preview_video, "live_face_boxes", [])
            n_faces = len(boxes)
            if getattr(self, "_last_live_face_count", -1) != n_faces:
                self._last_live_face_count = n_faces
                if n_faces == 0:
                    self.smart_detected_badge.setText("Live AI: 0 Wajah → Tampilan Sinematik Utuh")
                elif n_faces == 1:
                    self.smart_detected_badge.setText("Live AI: 1 Subjek → Fokus Potret 9:16")
                else:
                    self.smart_detected_badge.setText(f"Live AI: {n_faces} Subjek → Split 2 Panel")
                if hasattr(self, "smart_layout_overlay") and self.smart_layout_overlay.isVisible():
                    self.smart_layout_overlay.setVisible(False)
                self.update_create_subtitle_position()

    def update_create_duration(self, duration: int) -> None:
        self.create_seek_slider.setRange(0, max(0, duration))
        self.create_seek_slider.setEnabled(duration > 0)
        if duration > 0:
            self.source_duration = duration / 1000
            self.update_segment_estimate()
        self.update_create_seek(self.create_preview_player.position())

    def on_create_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if hasattr(self, "create_preview_play"):
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.create_preview_play.setIcon(make_vector_icon("pause", "#FFFFFF", 18))
                self.create_preview_play.setToolTip("Jeda Pratinjau")
                if hasattr(self, "bgm_preview_player") and getattr(self, "bgm_file_path", ""):
                    self.bgm_preview_player.play()
            else:
                self.create_preview_play.setIcon(make_vector_icon("play", "#FFFFFF", 18))
                self.create_preview_play.setToolTip("Putar Pratinjau")
                if hasattr(self, "bgm_preview_player"):
                    self.bgm_preview_player.pause()

    def toggle_create_preview(self) -> None:
        if self.create_preview_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.create_preview_player.pause()
        else:
            if (
                self.create_preview_player.position() >= self.create_preview_player.duration()
                and self.create_preview_player.duration() > 0
            ):
                self.create_preview_player.setPosition(0)
            self.create_preview_player.play()

    def toggle_create_mute(self) -> None:
        is_muted = not self.create_preview_audio.isMuted()
        self.create_preview_audio.setMuted(is_muted)
        if hasattr(self, "bgm_preview_audio"):
            self.bgm_preview_audio.setMuted(is_muted)
        if hasattr(self, "create_preview_mute_btn"):
            self.create_preview_mute_btn.setIcon(
                make_vector_icon("volume_mute" if is_muted else "volume_on", "#D4D4D8", 16)
            )
            self.create_preview_mute_btn.setToolTip("Aktifkan Suara" if is_muted else "Bisukan Suara")

    def choose_bgm_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Musik Latar", str(Path.home()), "Audio (*.mp3 *.wav *.m4a *.aac *.flac *.ogg)"
        )
        if not path:
            return
        self.bgm_file_path = str(path)
        self.bgm_path_label.setText(Path(path).name)
        self.btn_clear_bgm.setEnabled(True)
        if hasattr(self, "bgm_preview_player"):
            self.bgm_preview_player.setSource(QUrl.fromLocalFile(path))

    def clear_bgm_file(self) -> None:
        self.bgm_file_path = ""
        self.bgm_path_label.setText("Belum ada musik latar dipilih (opsional)")
        self.btn_clear_bgm.setEnabled(False)
        if hasattr(self, "bgm_preview_player"):
            self.bgm_preview_player.stop()
            self.bgm_preview_player.setSource(QUrl())

    def on_bgm_vol_changed(self, val: int) -> None:
        self.bgm_vol_label.setText(f"{val}%")
        if hasattr(self, "bgm_preview_audio"):
            self.bgm_preview_audio.setVolume(val / 100.0)

    def on_voice_vol_changed(self, val: int) -> None:
        self.voice_vol_label.setText(f"{val}%")
        if hasattr(self, "create_preview_audio"):
            self.create_preview_audio.setVolume(min(1.0, val / 100.0))

    def toggle_safe_zone_overlay(self) -> None:
        if hasattr(self, "safe_zone_overlay"):
            is_vis = not self.safe_zone_overlay.isVisible()
            self.safe_zone_overlay.setVisible(is_vis)
            if hasattr(self, "btn_safe_zone"):
                self.btn_safe_zone.setText(
                    "Sembunyikan Area HP" if is_vis else "Panduan Area HP"
                )
                self.btn_safe_zone.setStyleSheet(
                    "background: #172554; border: 1px solid #3B82F6; color: #FFFFFF; font-weight: 700; border-radius: 7px; padding: 0 10px;"
                    if is_vis
                    else ""
                )

    def reset_facecam_to_auto(self) -> None:
        if hasattr(self, "facecam_box"):
            self.facecam_box.reset_to_default()
        self.facecam_box_custom_dragged = False
        if hasattr(self, "facecam_preset_combo"):
            self.facecam_preset_combo.blockSignals(True)
            self.facecam_preset_combo.setCurrentIndex(0)
            self.facecam_preset_combo.blockSignals(False)
        self.update_create_preview()

    def on_facecam_preset_changed(self) -> None:
        if not hasattr(self, "facecam_preset_combo") or not hasattr(self, "facecam_box"):
            return
        preset = self.facecam_preset_combo.currentData()
        if preset == "auto":
            self.facecam_box_custom_dragged = False
        elif preset:
            self.facecam_box.apply_corner_preset(str(preset))
            self.facecam_box_custom_dragged = True
        self.update_create_preview()

    def choose_watermark_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pilih Logo Watermark PNG", str(Path.home()), "Gambar PNG (*.png)")
        if path and hasattr(self, "watermark_image_edit"):
            self.watermark_image_edit.setText(path)
            self.update_create_preview()

    def choose_lyrics_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Pilih Folder Penyimpanan File Lirik",
            self.lyrics_folder_edit.text().strip() or str(core.DATA_DIR),
        )
        if folder and hasattr(self, "lyrics_folder_edit"):
            self.lyrics_folder_edit.setText(folder)

    def on_translate_lyrics_toggled(self, checked: bool) -> None:
        if hasattr(self, "lyrics_options_widget"):
            self.lyrics_options_widget.setVisible(checked)
        self.update_create_preview()

    def on_lyrics_pos_changed(self) -> None:
        pos = self.lyrics_pos_combo.currentData() if hasattr(self, "lyrics_pos_combo") else "auto"
        if hasattr(self, "lyrics_free_pos_widget"):
            self.lyrics_free_pos_widget.setVisible(pos == "free")
        self.update_create_preview()

    def on_lyrics_x_slider_changed(self, val: int) -> None:
        self.lyrics_free_x = val / 100.0
        if hasattr(self, "lyrics_x_val_lbl"):
            self.lyrics_x_val_lbl.setText(f"{val}%")
        self.update_create_preview()

    def on_lyrics_y_slider_changed(self, val: int) -> None:
        self.lyrics_free_y = val / 100.0
        if hasattr(self, "lyrics_y_val_lbl"):
            self.lyrics_y_val_lbl.setText(f"{val}%")
        self.update_create_preview()

    def get_active_facecam_crop(self) -> list[float] | None:
        if hasattr(self, "layout_combo") and self.layout_combo.currentData() == "facecam_top":
            preset = self.facecam_preset_combo.currentData() if hasattr(self, "facecam_preset_combo") else "auto"
            if preset == "auto" and not getattr(self, "facecam_box_custom_dragged", False):
                return None
            if hasattr(self, "facecam_box"):
                return [
                    round(self.facecam_box.norm_x, 4),
                    round(self.facecam_box.norm_y, 4),
                    round(self.facecam_box.norm_w, 4),
                    round(self.facecam_box.norm_h, 4),
                ]
        return None

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
            model_dir = ROOT / "models"
            if model_dir.is_dir():
                try:
                    paths.extend([str(c) for c in sorted(model_dir.glob("*.gguf"))])
                except OSError:
                    pass
        unique_paths = list(dict.fromkeys(paths))
        current = self.model_file_combo.currentData() if keep_current else None
        if not current and keep_current:
            current = next((edit.text().strip() for edit in self.model_path_edits.values() if edit.text().strip()), None)
            if not current and unique_paths:
                current = unique_paths[0]
        self.model_file_combo.blockSignals(True)
        self.model_file_combo.clear()
        for path in unique_paths:
            if path == "gemini":
                continue
            self.model_file_combo.addItem(Path(path).name, path)
            self.model_file_combo.setItemData(self.model_file_combo.count() - 1, path, Qt.ItemDataRole.ToolTipRole)
        self.model_file_combo.addItem("Gemini Pro API", "gemini")
        self.model_file_combo.setItemData(self.model_file_combo.count() - 1, "Gunakan API Google Gemini", Qt.ItemDataRole.ToolTipRole)
        selected_index = self.model_file_combo.findData(current) if current else -1
        if selected_index < 0 and self.model_file_combo.count() > 0:
            selected_index = 0
        self.model_file_combo.setCurrentIndex(selected_index)
        self.model_file_combo.blockSignals(False)
        if selected_index >= 0:
            self.on_model_file_changed(selected_index)

    def on_ai_provider_changed(self) -> None:
        is_gemini = self.ai_provider_combo.currentData() == "gemini"
        if is_gemini:
            self.active_model_key = "gemini"
            self.use_llm.setChecked(True)
            idx = self.whisper_combo.findData("gemini")
            if idx >= 0:
                self.whisper_combo.setCurrentIndex(idx)
        else:
            self.on_model_file_changed(self.model_file_combo.currentIndex())
            if self.whisper_combo.currentData() == "gemini":
                idx = self.whisper_combo.findData("small")
                if idx >= 0:
                    self.whisper_combo.setCurrentIndex(idx)
        self.update_ai_engine_visibility()

    def on_gemini_key_changed(self, text: str) -> None:
        clean = text.strip()
        persist_gemini_key_to_env(clean)
        if not clean and hasattr(self, "gemini_status_badge"):
            self.gemini_status_badge.setText("")

    def test_gemini_connection(self) -> None:
        key = self.gemini_key_edit.text().strip()
        if not key:
            self.gemini_status_badge.setText("Kunci API kosong")
            self.gemini_status_badge.setStyleSheet(
                "color: #ef4444; background: #2d1515; border: 1px solid #7f1d1d; border-radius: 4px; padding: 4px 8px; font-weight: 600;"
            )
            return
        self.gemini_status_badge.setText("Menguji koneksi...")
        self.gemini_status_badge.setStyleSheet(
            "color: #60a5fa; background: #172554; border: 1px solid #1e40af; border-radius: 4px; padding: 4px 8px; font-weight: 500;"
        )
        QApplication.processEvents()
        try:
            from google import genai
            client = genai.Client(api_key=key)
            client.models.get(model="gemini-3.8-flash")
            self.gemini_status_badge.setText("Terhubung (Gemini Aktif)")
            self.gemini_status_badge.setStyleSheet(
                "color: #10b981; background: #064e3b; border: 1px solid #047857; border-radius: 4px; padding: 4px 8px; font-weight: 600;"
            )
            persist_gemini_key_to_env(key)
            self.refresh_setup_status()
            self.log_terminal("Google Gemini API Key terhubung dan disinkronkan ke .env.")
        except Exception as exc:
            err_msg = str(exc)
            if "API_KEY_INVALID" in err_msg or "400" in err_msg:
                text = "Kunci API tidak valid"
            elif "429" in err_msg:
                text = "Kuota API habis"
            else:
                text = f"Gagal: {err_msg[:28]}"
            self.gemini_status_badge.setText(text)
            self.gemini_status_badge.setStyleSheet(
                "color: #ef4444; background: #2d1515; border: 1px solid #7f1d1d; border-radius: 4px; padding: 4px 8px; font-weight: 600;"
            )
            self.log_terminal(f"Uji coba Google Gemini API Key gagal: {err_msg}")

    def on_model_file_changed(self, index: int) -> None:
        if index < 0:
            return
        path = self.model_file_combo.itemData(index)
        if not path:
            return
        if str(path) == "gemini":
            self.active_model_key = "gemini"
        else:
            lowered = Path(str(path)).name.lower()
            self.active_model_key = "hermes" if "hermes" in lowered else "qwen"
            self.model_path_edits[self.active_model_key].setText(str(path))
            self.save_model_paths()

    def pick_model_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Pilih folder yang berisi model GGUF", str(Path.home()))
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
        QMessageBox.information(self, "Model ditemukan", f"{len(candidates)} file GGUF ditemukan.")

    def pick_model(self, model_name: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, f"Pilih model {'Qwen' if model_name == 'qwen' else 'Hermes'} GGUF", str(Path.home()), "Model GGUF (*.gguf)"
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
        if candidates and not found["qwen"]:
            found["qwen"] = str(candidates[0])
        for model_name, path in found.items():
            if path:
                self.model_path_edits[model_name].setText(path)
        if candidates:
            self.refresh_model_file_choices([str(candidate) for candidate in candidates], keep_current=False)
        self.save_model_paths()

    def apply_model_paths(self) -> None:
        selected = self.model_file_combo.currentData() if hasattr(self, "model_file_combo") else None
        if selected and selected != "gemini":
            key = (
                self.active_model_key
                if self.active_model_key in self.model_path_edits
                else ("hermes" if "hermes" in str(selected).lower() else "qwen")
            )
            if key in self.model_path_edits:
                self.model_path_edits[key].setText(str(selected))
        if "qwen" in self.model_path_edits:
            core.QWEN_GGUF_PATH = self.model_path_edits["qwen"].text().strip()
        if "hermes" in self.model_path_edits:
            core.HERMES_GGUF_PATH = self.model_path_edits["hermes"].text().strip()


    def build_review_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        page = QWidget()
        page.setObjectName("pageContent")
        page.setMinimumWidth(880)
        page.setMaximumWidth(1360)

        main_layout = QHBoxLayout(page)
        main_layout.setContentsMargins(28, 22, 28, 22)
        main_layout.setSpacing(28)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        top_review_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        step3_title = QLabel("Review & Rapikan Klip")
        step3_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #FAFAFA; letter-spacing: 0.2px;")
        title_box.addWidget(step3_title)

        preview_header = QLabel("Klik segmen klip di kanan untuk meninjau hasil potongan, teks subtitle, dan tata letak kamera.")
        preview_header.setStyleSheet("font-size: 12px; font-weight: 500; color: #71717A;")
        title_box.addWidget(preview_header)
        top_review_bar.addLayout(title_box, 1)

        format_box = QVBoxLayout()
        format_box.setSpacing(2)
        fmt_lbl = QLabel("Format & Framing Klip:")
        fmt_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #38BDF8;")
        format_box.addWidget(fmt_lbl)

        self.review_format_combo = self.combo(
            [
                ("[Tanpa Framing] Rasio Asli Utuh 1:1", "original_native"),
                ("[Otomatis AI] 9:16 Adaptif Universal", "auto_universal_9_16"),
                ("[Otomatis AI] 9:16 Podcast & Dialog", "auto_podcast_9_16"),
                ("[Otomatis AI] 9:16 Fokus 1 Subjek", "crop_9_16"),
                ("[Otomatis AI] 9:16 Split 2 Panel", "split_2_9_16"),
                ("[Otomatis AI] 9:16 Gaming & Stream", "auto_gaming_9_16"),
                ("[Otomatis AI] 9:16 Sinematik Utuh", "auto_cinema_9_16"),
                ("[Manual] 9:16 Fit Utuh Standar", "fit_9_16"),
                ("[Manual] 9:16 Latar Blur Sinematik", "ambient_9_16"),
                ("[Manual] 9:16 Crop & Zoom Bebas", "manual_crop"),
                ("[Manual] 9:16 Split 2 Panel Statis", "manual_split"),
                ("[Manual] 9:16 Facecam Atas + Konten", "facecam_9_16"),
                ("[Manual] 1:1 Kotak Persegi", "square_1_1"),
                ("[Manual] 16:9 Landscape Lebar", "fit_16_9"),
            ],
            selected=1,
        )
        self.review_format_combo.setMinimumWidth(285)
        self.review_format_combo.currentIndexChanged.connect(self.on_review_format_changed)
        format_box.addWidget(self.review_format_combo)
        top_review_bar.addLayout(format_box)
        left_col.addLayout(top_review_bar)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.playbackStateChanged.connect(self.on_review_playback_state_changed)

        source_frame = QFrame()
        self.review_source_frame = source_frame
        source_frame.setObjectName("previewCanvas")
        source_frame.setMinimumHeight(390)

        source_stack = QGridLayout(source_frame)
        self.review_source_stack = source_stack
        source_stack.setContentsMargins(0, 0, 0, 0)

        self.video_widget = VideoSurfaceWidget()
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video_widget.manualCropChanged.connect(self.on_canvas_manual_crop_changed)
        self.player.setVideoOutput(self.video_widget.sink)
        source_stack.addWidget(self.video_widget, 0, 0)

        self.source_subtitle_overlay = QLabel("", self.video_widget)
        self.source_subtitle_overlay.setObjectName("previewSubtitle")
        self.source_subtitle_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_subtitle_overlay.setWordWrap(True)
        self.source_subtitle_overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.source_subtitle_overlay.setVisible(False)

        self.review_hook_banner_overlay = QLabel("", self.video_widget)
        self.review_hook_banner_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.review_hook_banner_overlay.setWordWrap(True)
        self.review_hook_banner_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.review_hook_banner_overlay.setVisible(False)
        left_col.addWidget(source_frame)

        player_controls = QHBoxLayout()
        player_controls.setSpacing(10)

        self.play_button = QPushButton()
        self.play_button.setIcon(make_vector_icon("play", "#FFFFFF", 24))
        self.play_button.setIconSize(QSize(20, 20))
        self.play_button.setToolTip("Putar / Jeda Video (Spasi)")
        self.play_button.setFixedSize(38, 38)
        self.play_button.setStyleSheet(
            "QPushButton { background: #2563EB; border-radius: 19px; border: none; padding: 0px; } "
            "QPushButton:hover { background: #1D4ED8; } QPushButton:pressed { background: #1E40AF; }"
        )
        self.play_button.clicked.connect(self.toggle_video)
        player_controls.addWidget(self.play_button)

        ctrl_btn_style = (
            "QPushButton { background: #101018; border: 1px solid #242432; border-radius: 8px; padding: 0px 10px; color: #E4E4E7; font-size: 12px; font-weight: 600; } "
            "QPushButton:hover { background: #1A1A28; color: #FFFFFF; border-color: #3B82F6; } QPushButton:pressed { background: #09090E; }"
        )
        btn_rew = QPushButton("-5d")
        btn_rew.setToolTip("Mundur 5 Detik")
        btn_rew.setFixedHeight(34)
        btn_rew.setStyleSheet(ctrl_btn_style)
        btn_rew.clicked.connect(lambda: self.seek_review_video(max(0, self.player.position() - 5000)))
        player_controls.addWidget(btn_rew)

        btn_ff = QPushButton("+5d")
        btn_ff.setToolTip("Maju 5 Detik")
        btn_ff.setFixedHeight(34)
        btn_ff.setStyleSheet(ctrl_btn_style)
        btn_ff.clicked.connect(lambda: self.seek_review_video(min(self.player.duration(), self.player.position() + 5000)))
        player_controls.addWidget(btn_ff)

        btn_reset_clip = QPushButton("Awal Klip")
        btn_reset_clip.setToolTip("Kembalikan putaran ke detik awal klip yang sedang dipilih")
        btn_reset_clip.setFixedHeight(34)
        btn_reset_clip.setStyleSheet(ctrl_btn_style)
        btn_reset_clip.clicked.connect(self.reset_review_timeline)
        player_controls.addWidget(btn_reset_clip)

        self.review_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.review_seek_slider.setRange(0, 0)
        self.review_seek_slider.setEnabled(False)
        self.review_seek_slider.sliderMoved.connect(self.seek_review_video)
        self.player.positionChanged.connect(self.update_player_time)
        self.player.durationChanged.connect(self.update_player_duration)
        player_controls.addWidget(self.review_seek_slider, 1)

        self.current_time = QLabel("00:00 / 00:00")
        self.current_time.setStyleSheet("color: #38BDF8; font-weight: 700; font-size: 12px; background: transparent;")
        player_controls.addWidget(self.current_time)
        left_col.addLayout(player_controls)

        timeline_header_row = QHBoxLayout()
        timeline_title = QLabel("Garis Waktu Klip (Area Biru = Durasi Klip yang Dipilih)")
        timeline_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #E2E8F0;")
        timeline_header_row.addWidget(timeline_title)
        timeline_header_row.addStretch()

        self.review_status = QLabel("")
        self.review_status.setStyleSheet("font-size: 12px; font-weight: 600; color: #38BDF8;")
        timeline_header_row.addWidget(self.review_status)
        left_col.addLayout(timeline_header_row)

        self.timeline_widget = TimelineWidget()
        self.timeline_widget.seekRequested.connect(self.seek_review_video)
        left_col.addWidget(self.timeline_widget)

        main_layout.addLayout(left_col, 58)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        right_title = QLabel("Daftar Klip Siap Render")
        right_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #F8FAFC; letter-spacing: 0.4px;")
        right_col.addWidget(right_title)

        self.review_clip_count_label = QLabel("0 Klip Ditemukan")
        self.review_clip_count_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #94A3B8;")
        right_col.addWidget(self.review_clip_count_label)

        self.review_cards_scroll = QScrollArea()
        self.review_cards_scroll.setWidgetResizable(True)
        self.review_cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.review_cards_scroll.setStyleSheet("background: transparent;")

        self.review_cards_container = QWidget()
        self.review_cards_container.setStyleSheet("background: transparent;")
        self.review_cards_layout = QVBoxLayout(self.review_cards_container)
        self.review_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.review_cards_layout.setSpacing(10)
        self.review_cards_layout.addStretch()
        self.review_cards_scroll.setWidget(self.review_cards_container)
        right_col.addWidget(self.review_cards_scroll, 1)

        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(10)
        self.edit_text_button = QPushButton("Edit Judul, Caption && Subtitle")
        self.edit_text_button.setMinimumHeight(40)
        self.edit_text_button.setToolTip("Ubah judul klip, caption, atau perbaiki teks subtitle klip yang sedang dipilih")
        self.edit_text_button.clicked.connect(self.open_edit_text_dialog)
        btn_row1.addWidget(self.edit_text_button)

        self.add_manual_button = QPushButton("Tambah Klip Manual")
        self.add_manual_button.setMinimumHeight(40)
        self.add_manual_button.setToolTip("Buat potongan klip tambahan sendiri berdasarkan menit/detik yang kamu inginkan")
        self.add_manual_button.clicked.connect(self.open_manual_clip_dialog)
        btn_row1.addWidget(self.add_manual_button)
        right_col.addLayout(btn_row1)

        self.review_export_progress_card = QFrame()
        self.review_export_progress_card.setObjectName("reviewExportCard")
        self.review_export_progress_card.setStyleSheet(
            "QFrame#reviewExportCard { background: #090D18; border: 1.5px solid #2563EB; border-radius: 12px; padding: 10px 12px; }"
        )
        rep_lay = QVBoxLayout(self.review_export_progress_card)
        rep_lay.setContentsMargins(10, 8, 10, 8)
        rep_lay.setSpacing(6)
        rep_top = QHBoxLayout()
        self.review_export_status_lbl = QLabel("Mengekspor klip video final...")
        self.review_export_status_lbl.setStyleSheet("font-weight: 800; font-size: 12px; color: #FAFAFA; border: 0; background: transparent;")
        self.review_export_pct_lbl = QLabel("0%")
        self.review_export_pct_lbl.setStyleSheet("font-family: 'Cascadia Mono', monospace; font-weight: 800; font-size: 13px; color: #38BDF8; border: 0; background: transparent;")
        rep_top.addWidget(self.review_export_status_lbl, 1)
        rep_top.addWidget(self.review_export_pct_lbl)
        rep_lay.addLayout(rep_top)

        self.review_export_bar = QProgressBar()
        self.review_export_bar.setRange(0, 100)
        self.review_export_bar.setValue(0)
        self.review_export_bar.setTextVisible(False)
        self.review_export_bar.setFixedHeight(7)
        self.review_export_bar.setStyleSheet(
            "QProgressBar { background: #141824; border-radius: 3px; border: 0; } "
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #10B981); border-radius: 3px; }"
        )
        rep_lay.addWidget(self.review_export_bar)

        rep_sub_row = QHBoxLayout()
        self.review_export_detail_lbl = QLabel("Menyiapkan render video & subtitle...")
        self.review_export_detail_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; border: 0; background: transparent;")
        self.btn_cancel_review_export = QPushButton("Batalkan Ekspor")
        self.btn_cancel_review_export.setFixedHeight(28)
        self.btn_cancel_review_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel_review_export.setStyleSheet(
            "QPushButton { background: #2A0A10; border: 1px solid #EF4444; border-radius: 6px; color: #FCA5A5; font-size: 11px; font-weight: 700; padding: 0 12px; } "
            "QPushButton:hover { background: #450A0A; color: #FFFFFF; }"
        )
        self.btn_cancel_review_export.clicked.connect(self.cancel_current_process)
        rep_sub_row.addWidget(self.review_export_detail_lbl, 1)
        rep_sub_row.addWidget(self.btn_cancel_review_export)
        rep_lay.addLayout(rep_sub_row)
        self.review_export_progress_card.setVisible(False)
        right_col.addWidget(self.review_export_progress_card)

        btn_row2 = QHBoxLayout()
        self.btn_back_review = QPushButton("← Kembali ke Studio Klip")
        self.btn_back_review.setMinimumHeight(44)
        self.btn_back_review.setMinimumWidth(175)
        self.btn_back_review.setStyleSheet(
            "QPushButton { background: #101018; border: 1px solid #242432; color: #E4E4E7; font-weight: 700; border-radius: 10px; } "
            "QPushButton:hover { background: #1A1A28; color: #FFFFFF; border-color: #3B82F6; }"
        )
        self.btn_back_review.clicked.connect(self.cancel_to_edit_step2)
        btn_row2.addWidget(self.btn_back_review)

        self.render_button = QPushButton("Ekspor Semua Klip Sekarang")
        self.render_button.setObjectName("primary")
        self.render_button.setMinimumHeight(44)
        self.render_button.setStyleSheet("font-weight: 800; font-size: 13px; padding: 0 24px; border-radius: 10px;")
        self.render_button.clicked.connect(self.render_final)
        btn_row2.addWidget(self.render_button, 1)
        right_col.addLayout(btn_row2)

        self.manual_start = QLineEdit("00:00")
        self.manual_end = QLineEdit("01:00")
        self.manual_title = QLineEdit()
        self.auto_clips_layout = QVBoxLayout()
        self.manual_clips_layout = QVBoxLayout()
        self.auto_preview_button = QPushButton()
        self.auto_preview_button.setVisible(False)
        self.preview_player = QMediaPlayer(self)
        self.preview_status = QLabel("")

        main_layout.addLayout(right_col, 42)
        scroll.setWidget(page)

        class _ReviewWrapper(QWidget):
            def __init__(self, inner_scroll: QScrollArea, owner: Any) -> None:
                super().__init__()
                self._owner = owner
                lay = QVBoxLayout(self)
                lay.setContentsMargins(0, 0, 0, 0)
                lay.setSpacing(0)
                lay.addWidget(inner_scroll)

            def resizeEvent(self, ev: Any) -> None:
                super().resizeEvent(ev)
                if hasattr(self._owner, "review_lock_overlay"):
                    self._owner.review_lock_overlay.setGeometry(self.rect())

        wrapper = _ReviewWrapper(scroll, self)
        wrapper.setObjectName("pageContent")
        wrapper.setStyleSheet("QWidget#pageContent { background: #000000; }")
        self.review_outer_wrapper = wrapper
        self.review_inner_scroll = scroll

        self.review_lock_overlay = QFrame(wrapper)
        self.review_lock_overlay.setObjectName("reviewLockOverlay")
        self.review_lock_overlay.setStyleSheet(
            "QFrame#reviewLockOverlay { background: rgba(3, 3, 7, 195); border: none; }"
        )
        lock_lay = QVBoxLayout(self.review_lock_overlay)
        lock_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lock_card = QFrame()
        lock_card.setObjectName("reviewLockCard")
        lock_card.setFixedWidth(480)
        lock_card.setStyleSheet(
            "QFrame#reviewLockCard { background: #0B0D16; border: 1.5px solid #2563EB; border-radius: 16px; padding: 22px; }"
        )
        lc_lay = QVBoxLayout(lock_card)
        lc_lay.setSpacing(10)

        lock_badge = QLabel("MENU REVIEW & TRIM (TERKUNCI SEMENTARA)")
        lock_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lock_badge.setStyleSheet(
            "color: #60A5FA; background: rgba(37, 99, 235, 0.16); border: 1px solid rgba(59, 130, 246, 0.45); "
            "border-radius: 8px; padding: 4px 10px; font-size: 10.5px; font-weight: 800; letter-spacing: 0.6px;"
        )
        lc_lay.addWidget(lock_badge)

        lock_title = QLabel("Selesaikan Pengaturan di Studio Klip Terlebih Dahulu")
        lock_title.setWordWrap(True)
        lock_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lock_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #FFFFFF; background: transparent; border: 0;")
        lc_lay.addWidget(lock_title)

        self.review_lock_desc = QLabel(
            "Di halaman ini nantinya Anda dapat memutar ulang setiap potongan klip, menggeser batas awal/akhir di Garis Waktu (Timeline), "
            "dan mengedit teks subtitle sebelum diekspor.\n\n"
            "Saat ini halaman digelapkan karena Anda masih berada di tahap pengaturan Studio Klip."
        )
        self.review_lock_desc.setWordWrap(True)
        self.review_lock_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.review_lock_desc.setStyleSheet("font-size: 12px; color: #A1A1AA; line-height: 1.5; background: transparent; border: 0;")
        lc_lay.addWidget(self.review_lock_desc)

        btn_go_studio = QPushButton("← Kembali ke 2 · Studio Klip")
        btn_go_studio.setObjectName("primary")
        btn_go_studio.setFixedHeight(40)
        btn_go_studio.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_go_studio.setStyleSheet("font-size: 12.5px; font-weight: 800; border-radius: 10px; padding: 0 20px;")
        btn_go_studio.clicked.connect(lambda: self.switch_tab(2))
        lc_lay.addWidget(btn_go_studio)

        lock_lay.addWidget(lock_card)
        self.set_review_unlocked(False)
        return wrapper

    def set_review_unlocked(self, unlocked: bool) -> None:
        self.review_is_unlocked = unlocked
        if hasattr(self, "review_lock_overlay") and hasattr(self, "review_outer_wrapper"):
            self.review_lock_overlay.setGeometry(self.review_outer_wrapper.rect())
            self.review_lock_overlay.setVisible(not unlocked)
            if not unlocked:
                self.review_lock_overlay.raise_()
        if hasattr(self, "review_inner_scroll"):
            eff = self.review_inner_scroll.graphicsEffect()
            if not unlocked:
                if not isinstance(eff, QGraphicsOpacityEffect):
                    eff = QGraphicsOpacityEffect(self.review_inner_scroll)
                    self.review_inner_scroll.setGraphicsEffect(eff)
                eff.setOpacity(0.38)
            else:
                self.review_inner_scroll.setGraphicsEffect(None)

    def build_results_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        page = QWidget()
        page.setObjectName("pageContent")
        page.setMinimumWidth(880)
        page.setMaximumWidth(1360)

        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(20)

        header_row = QHBoxLayout()
        header_row.setSpacing(20)

        left_stat = QVBoxLayout()
        left_stat.setSpacing(4)
        self.results_title = QLabel("0 KLIP SELESAI")
        self.results_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #FFFFFF;")
        left_stat.addWidget(self.results_title)

        self.results_folder_label = QLabel("Folder Hasil: ...")
        self.results_folder_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
        left_stat.addWidget(self.results_folder_label)
        header_row.addLayout(left_stat, 1)

        summary_card = QFrame()
        summary_card.setStyleSheet("background: #09090E; border: 1px solid #1C1C26; border-radius: 12px; padding: 10px 16px;")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(4)

        sum_title = QLabel("Ringkasan Ekspor")
        sum_title.setStyleSheet("font-weight: 700; color: #F1F5F9; font-size: 13px; border: 0; background: transparent;")
        summary_layout.addWidget(sum_title)

        self.results_dur_label = QLabel("Total Durasi: 00:00")
        self.results_dur_label.setStyleSheet("color: #94A3B8; font-size: 12px; border: 0; background: transparent;")
        summary_layout.addWidget(self.results_dur_label)

        self.results_size_label = QLabel("Ukuran: 0 MB")
        self.results_size_label.setStyleSheet("color: #94A3B8; font-size: 12px; border: 0; background: transparent;")
        summary_layout.addWidget(self.results_size_label)

        self.results_count_label = QLabel("Total Berkas: 0")
        self.results_count_label.setStyleSheet("color: #94A3B8; font-size: 12px; border: 0; background: transparent;")
        summary_layout.addWidget(self.results_count_label)

        header_row.addWidget(summary_card)
        main_layout.addLayout(header_row)

        sub_header = QLabel("Klip yang Berhasil Diekspor (Gunakan tombol TikTok pada kartu untuk Upload Langsung / Masuk Antrean)")
        sub_header.setStyleSheet("font-size: 13px; font-weight: 600; color: #E2E8F0;")
        main_layout.addWidget(sub_header)

        self.results_grid_scroll = QScrollArea()
        self.results_grid_scroll.setWidgetResizable(True)
        self.results_grid_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.results_grid_scroll.setStyleSheet("background: transparent;")

        self.results_grid_widget = QWidget()
        self.results_grid_widget.setStyleSheet("background: transparent;")
        self.results_grid_layout = QGridLayout(self.results_grid_widget)
        self.results_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.results_grid_layout.setSpacing(14)
        self.results_grid_scroll.setWidget(self.results_grid_widget)
        main_layout.addWidget(self.results_grid_scroll, 1)

        btn_center_box = QHBoxLayout()
        btn_center_box.setSpacing(12)
        btn_center_box.addStretch()

        self.open_results_button = QPushButton("Buka Folder Hasil")
        self.open_results_button.setObjectName("primary")
        self.open_results_button.setMinimumHeight(46)
        self.open_results_button.setStyleSheet("font-size: 13px; font-weight: 800; padding: 0 28px; border-radius: 10px;")
        self.open_results_button.clicked.connect(self.open_results_folder)
        btn_center_box.addWidget(self.open_results_button)

        self.btn_batch_tiktok_queue = QPushButton("Masukkan Semua ke Antrean TikTok (Jam Ramai)")
        self.btn_batch_tiktok_queue.setMinimumHeight(46)
        self.btn_batch_tiktok_queue.setStyleSheet("""
            QPushButton {
                background: #0F2922;
                border: 1px solid #10B981;
                border-radius: 10px;
                color: #34D399;
                font-size: 13px;
                font-weight: 700;
                padding: 0 22px;
            }
            QPushButton:hover {
                background: #059669;
                color: #FFFFFF;
            }
        """)
        self.btn_batch_tiktok_queue.clicked.connect(self.batch_queue_all_clips_to_tiktok)
        btn_center_box.addWidget(self.btn_batch_tiktok_queue)

        self.btn_login_yt = QPushButton("Login YouTube Studio")
        self.btn_login_yt.setMinimumHeight(46)
        self.btn_login_yt.setStyleSheet("""
            QPushButton {
                background: #101018;
                border: 1px solid #242432;
                border-radius: 10px;
                color: #F87171;
                font-size: 13px;
                font-weight: 700;
                padding: 0 20px;
            }
            QPushButton:hover {
                background: #2D1414;
                border-color: #DC2626;
                color: #FFFFFF;
            }
        """)
        self.btn_login_yt.clicked.connect(self.trigger_youtube_login)
        btn_center_box.addWidget(self.btn_login_yt)
        btn_center_box.addStretch()
        main_layout.addLayout(btn_center_box)

        self.results_list = QListWidget()
        self.results_list.setVisible(False)

        scroll.setWidget(page)
        return scroll

    @staticmethod
    def combo(items: list[tuple[str, Any]], selected: int = 0) -> QComboBox:
        box = ClickOnlyComboBox()
        for label, value in items:
            box.addItem(label, value)
        box.setCurrentIndex(selected)
        box.setMinimumHeight(38)
        box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        box.setMinimumContentsLength(10)
        return box

    @staticmethod
    def spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        box = FocusOnlySpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        box.setMinimumHeight(38)
        return box

    def build_options(self) -> core.CreateJobRequest:
        minimum = self.min_duration.value()
        maximum = self.max_duration.value()
        if minimum > 0 and maximum > 0 and minimum > maximum:
            raise ValueError("Minimum durasi tidak boleh lebih besar dari maksimum durasi.")
        self.save_studio_hook_settings()
        hb_dur_val = (
            int(self.hook_banner_dur_combo.currentData() or 0)
            if hasattr(self, "hook_banner_dur_combo")
            else (self.hook_banner_dur_spin.value() if hasattr(self, "hook_banner_dur_spin") else 0)
        )
        hb_pos_val = (
            str(self.hook_banner_pos_combo.currentData() or "top")
            if hasattr(self, "hook_banner_pos_combo")
            else "top"
        )
        effective_url = self.url_edit.text().strip() or getattr(self, "selected_source_video_path", "") or "local_video"
        return core.CreateJobRequest(
            url=effective_url,
            clip_count=self.clip_count.value(),
            language=self.language_combo.currentData(),
            whisper_model=self.whisper_combo.currentData(),
            video_encoder=self.encoder_combo.currentData() if hasattr(self, "encoder_combo") else "auto",
            custom_prompt=self.custom_prompt_edit.text().strip(),
            min_duration=minimum,
            max_duration=maximum,
            max_clips=self.max_clips.value(),
            clip_mode=self.mode_combo.currentData(),
            clip_profile="manual" if self.mode_combo.currentData() == "manual" else self.profile_combo.currentData(),
            manual_segments=list(getattr(self, "pre_manual_segments", [])) if self.mode_combo.currentData() == "manual" else [],
            clip_flavor=self.clip_flavor_combo.currentData() if hasattr(self, "clip_flavor_combo") else "universal",
            use_audio_energy=self.use_audio_energy_check.isChecked() if hasattr(self, "use_audio_energy_check") else True,
            snap_sentence_bounds=self.snap_sentence_check.isChecked() if hasattr(self, "snap_sentence_check") else True,
            trim_opening_filler=self.trim_filler_check.isChecked() if hasattr(self, "trim_filler_check") else False,
            spicy_headline_hook=self.spicy_headline_check.isChecked() if hasattr(self, "spicy_headline_check") else True,
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
            framing_mode=getattr(self, "framing_mode_state", "auto"),
            manual_crop_x=(self.manual_crop_x_slider.value() / 100.0) if hasattr(self, "manual_crop_x_slider") else 0.5,
            manual_crop_y=(self.manual_crop_y_slider.value() / 100.0) if hasattr(self, "manual_crop_y_slider") else 0.5,
            manual_zoom=(self.manual_zoom_slider.value() / 100.0) if hasattr(self, "manual_zoom_slider") else 1.0,
            subtitle_style=self.subtitle_combo.currentData() if self.subtitle_enabled.isChecked() else "none",
            subtitle_position=self.subtitle_position_combo.currentData() if self.subtitle_enabled.isChecked() else "auto",
            subtitle_color=self.selected_subtitle_color() if self.subtitle_enabled.isChecked() else "auto",
            subtitle_active_color=self.subtitle_active_color_combo.currentData() if hasattr(self, "subtitle_active_color_combo") else "#FFDD00",
            subtitle_x=self.subtitle_free_x,
            subtitle_y=self.subtitle_free_y,
            subtitle_max_lines=self.subtitle_lines_combo.currentData() if hasattr(self, "subtitle_lines_combo") else 2,
            subtitle_font_size=self.subtitle_size_combo.currentData() if hasattr(self, "subtitle_size_combo") else 14,
            subtitle_mode=self.subtitle_mode_combo.currentData() if hasattr(self, "subtitle_mode_combo") else "active_highlight",
            skip_if_has_subtitles=self.skip_if_has_subtitles_toggle.isChecked() if hasattr(self, "skip_if_has_subtitles_toggle") else True,
            bgm_path=getattr(self, "bgm_file_path", "").strip(),
            bgm_volume=self.bgm_vol_slider.value() / 100.0 if hasattr(self, "bgm_vol_slider") else 0.08,
            voice_volume=self.voice_vol_slider.value() / 100.0 if hasattr(self, "voice_vol_slider") else 1.0,
            bgm_autoduck=self.bgm_duck_checkbox.isChecked() if hasattr(self, "bgm_duck_checkbox") else True,
            audio_loudnorm=self.loudnorm_checkbox.isChecked() if hasattr(self, "loudnorm_checkbox") else False,
            censor_profanity=self.censor_profanity_checkbox.isChecked() if hasattr(self, "censor_profanity_checkbox") else False,
            watermark_text=self.watermark_edit.text().strip() if hasattr(self, "watermark_edit") else "",
            watermark_image_path=self.watermark_image_edit.text().strip() if hasattr(self, "watermark_image_edit") else "",
            watermark_position=self.watermark_pos_combo.currentData() if hasattr(self, "watermark_pos_combo") else "top_right",
            watermark_opacity=self.watermark_opacity_slider.value() / 100.0 if hasattr(self, "watermark_opacity_slider") else 0.75,
            watermark_x=self.watermark_free_x if hasattr(self, "watermark_free_x") else 0.85,
            watermark_y=self.watermark_free_y if hasattr(self, "watermark_free_y") else 0.08,
            hook_banner_enabled=self.hook_banner_toggle.isChecked() if hasattr(self, "hook_banner_toggle") else False,
            hook_banner_text=self.hook_banner_edit.text().strip() if hasattr(self, "hook_banner_edit") else "",
            hook_banner_duration=hb_dur_val,
            hook_banner_position=hb_pos_val,
            hook_banner_x=self.hook_banner_free_x,
            hook_banner_y=self.hook_banner_free_y,
            outro_cta_enabled=self.outro_cta_check.isChecked() if hasattr(self, "outro_cta_check") else False,
            facecam_crop=self.get_active_facecam_crop(),
            mirror_video=self.mirror_video_check.isChecked() if hasattr(self, "mirror_video_check") else False,
            speed_shift=self.speed_shift_check.isChecked() if hasattr(self, "speed_shift_check") else False,
            color_boost=self.color_boost_check.isChecked() if hasattr(self, "color_boost_check") else False,
            emoji_subtitles=self.emoji_subtitles_check.isChecked() if hasattr(self, "emoji_subtitles_check") else False,
            dynamic_micro_zoom=self.micro_zoom_check.isChecked() if hasattr(self, "micro_zoom_check") else False,
            auto_broll=self.auto_broll_check.isChecked() if hasattr(self, "auto_broll_check") else False,
            broll_folder=self.broll_folder_edit.text().strip() if hasattr(self, "broll_folder_edit") else "",
            translate_lyrics=self.translate_lyrics_check.isChecked() if hasattr(self, "translate_lyrics_check") else False,
            lyrics_target_lang=self.lyrics_target_lang_combo.currentData() if hasattr(self, "lyrics_target_lang_combo") else "id",
            lyrics_display_mode=self.lyrics_display_mode_combo.currentData() if hasattr(self, "lyrics_display_mode_combo") else "dual",
            lyrics_position=self.lyrics_pos_combo.currentData() if hasattr(self, "lyrics_pos_combo") else "auto",
            lyrics_pos_x=self.lyrics_free_x if hasattr(self, "lyrics_free_x") else 0.15,
            lyrics_pos_y=self.lyrics_free_y if hasattr(self, "lyrics_free_y") else 0.78,
            save_translated_srt=self.save_lyrics_srt_check.isChecked() if hasattr(self, "save_lyrics_srt_check") else True,
            save_translated_lrc=self.save_lyrics_lrc_check.isChecked() if hasattr(self, "save_lyrics_lrc_check") else True,
            save_translated_txt=self.save_lyrics_txt_check.isChecked() if hasattr(self, "save_lyrics_txt_check") else True,
            lyrics_save_folder=self.lyrics_folder_edit.text().strip() if hasattr(self, "lyrics_folder_edit") else "",
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
        if hasattr(self, "dl_progress_card"):
            self.dl_progress_card.setVisible(True)
            self.dl_progress_bar.setValue(0)
            self.dl_percent_label.setText("0%")
            self.dl_status_label.setText("Mengunduh video sumber...")
            self.dl_detail_label.setText("Menghubungkan ke server sumber...")
        self.set_progress_panel_visible(True)
        self.progress.setValue(0)
        self.total_percent_label.setText("0%")
        self.sub_progress.setValue(0)
        self.sub_percent_label.setText("0%")
        self.source_status.setText("Mengunduh video sumber...")
        self.status_label.setText("Menyiapkan download video...")
        self.sub_status_label.setText("Menghubungkan ke server sumber...")
        self.download_worker = DownloadWorker(self.current_job_id, url, self.quality_combo.currentData())
        self.download_worker.finished_download.connect(self.refresh_job)
        self.download_worker.start()
        self.poll_timer.start(700)

    def choose_local_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih file video", str(Path.home()), "Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v)"
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
        if hasattr(self, "dl_progress_card"):
            self.dl_progress_card.setVisible(False)
        self.download_button.setEnabled(True)
        self.local_file_button.setEnabled(True)
        self.source_status.setText(message)
        self.active_transcript = []
        self.source_subtitle_overlay.setVisible(False)
        if source_path and Path(source_path).is_file():
            self.source_duration = core.media_duration(Path(source_path), 0.0)
            self.create_preview_player.setSource(QUrl.fromLocalFile(source_path))
            self.create_preview_player.pause()
            if hasattr(self, "preview_placeholder"):
                self.preview_placeholder.setVisible(False)
            self.update_create_preview()
            self.update_segment_estimate()
        self.set_progress_panel_visible(False)
        for widget in self.clip_stage_widgets:
            widget.setVisible(True)
        self.set_create_inputs_locked(False)
        if hasattr(self, "set_review_unlocked"):
            self.set_review_unlocked(False)
        self.switch_tab(2)
        QTimer.singleShot(40, self.ensure_splitter_balanced)

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
        gemini_key = self.gemini_key_edit.text().strip() or core.get_active_gemini_api_key()
        if gemini_key:
            persist_gemini_key_to_env(gemini_key)

        needs_ai_analysis = (options.clip_mode == "smart")
        ai_prov = self.ai_provider_combo.currentData() if needs_ai_analysis else "none"
        stt_prov = self.whisper_combo.currentData()

        if ai_prov == "gemini" or stt_prov == "gemini":
            if not gemini_key:
                QMessageBox.warning(
                    self,
                    "API Key Kosong",
                    "Masukkan Gemini API Key kamu terlebih dahulu di bagian Mesin Suara ke Teks / AI (dapatkan gratis di aistudio.google.com).",
                )
                return
            if ai_prov == "gemini":
                self.active_model_key = "gemini"
                options.local_model = "gemini"
        elif needs_ai_analysis and self.use_llm.isChecked():
            current_model = self.model_file_combo.currentData()
            if not current_model:
                QMessageBox.warning(self, "Pilih model GGUF", "Pilih salah satu file .gguf dari dropdown Model aktif terlebih dahulu.")
                return
            if current_model == "gemini" and not gemini_key:
                QMessageBox.warning(self, "API Key Kosong", "Masukkan Gemini API Key terlebih dahulu.")
                return
        self.apply_model_paths()
        self.save_model_paths()
        self.current_options = options
        if hasattr(core, "reset_canceled_job"):
            core.reset_canceled_job(self.current_job_id)
        with core.JOBS_LOCK:
            core.JOB_OPTIONS[self.current_job_id] = options
        self.set_create_inputs_locked(True)
        self.tabs.setTabEnabled(3, True)
        if hasattr(self, "set_review_unlocked"):
            self.set_review_unlocked(False)
        if hasattr(self, "review_lock_desc"):
            self.review_lock_desc.setText(
                "<b>Sedang Memproses Pembuatan Klip di Studio Klip...</b><br>"
                "Tunggu sebentar hingga proses pemotongan & pembuatan subtitle selesai, lalu halaman Review & Trim ini akan otomatis terbuka penuh."
            )
        self.tabs.setTabEnabled(4, False)
        self.set_progress_panel_visible(True)
        self.progress.setValue(0)
        self.total_percent_label.setText("0%")
        self.sub_progress.setValue(0)
        self.sub_percent_label.setText("0%")
        self.status_label.setText("Memulai proses pembuatan klip...")
        self.sub_status_label.setText("Menyiapkan tahapan ekstraksi audio & pemotongan...")
        self.log_terminal(f"Memulai proses clip video (Job ID: {self.current_job_id})...")
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
        overall_pct = snapshot.get("progress", 0)
        sub_pct = snapshot.get("sub_progress", 0)
        msg = snapshot.get("message", "Memproses...")
        sub_msg = snapshot.get("sub_message", "")

        self.animate_progress_bar(self.progress, overall_pct)
        self.total_percent_label.setText(f"{overall_pct}%")
        self.status_label.setText(msg)

        self.animate_progress_bar(self.sub_progress, sub_pct)
        self.sub_percent_label.setText(f"{sub_pct}%")
        self.sub_status_label.setText(sub_msg or msg)

        if hasattr(self, "review_export_progress_card") and self.review_export_progress_card.isVisible():
            eff_export_pct = overall_pct if overall_pct > 0 else sub_pct
            self.animate_progress_bar(self.review_export_bar, eff_export_pct)
            self.review_export_pct_lbl.setText(f"{eff_export_pct}%")
            self.review_export_status_lbl.setText(msg)
            self.review_export_detail_lbl.setText(sub_msg or f"Progress render video: {eff_export_pct}% — Mohon tunggu hingga selesai...")

        if hasattr(self, "dl_progress_card") and self.dl_progress_card.isVisible():
            effective_pct = sub_pct if sub_pct > 0 else overall_pct
            self.animate_progress_bar(self.dl_progress_bar, effective_pct)
            self.dl_percent_label.setText(f"{effective_pct}%")
            if msg:
                self.dl_status_label.setText(msg)
            if sub_msg:
                self.dl_detail_label.setText(sub_msg)
            elif effective_pct > 0:
                self.dl_detail_label.setText(f"Progress: {effective_pct}%")

        if msg != getattr(self, "_last_logged_msg", None):
            self._last_logged_msg = msg
            self.log_terminal(f"[{overall_pct}%] {msg}")
        if snapshot["status"] == "downloaded":
            if hasattr(self, "dl_progress_card"):
                self.dl_progress_card.setVisible(False)
            self.poll_timer.stop()
            self.show_clip_stage(snapshot.get("source_path", ""), snapshot["message"])
        elif snapshot["status"] == "awaiting_render":
            self.poll_timer.stop()
            self.show_review(snapshot)
        elif snapshot["status"] == "completed":
            self.poll_timer.stop()
            if hasattr(self, "review_export_progress_card"):
                self.review_export_progress_card.setVisible(False)
            self.set_progress_panel_visible(False)
            self.set_create_inputs_locked(False)
            self.render_button.setEnabled(True)
            if hasattr(self, "edit_text_button"):
                self.edit_text_button.setEnabled(True)
            if hasattr(self, "btn_back_review"):
                self.btn_back_review.setEnabled(True)
            self.add_manual_button.setEnabled(True)
            self.show_results(snapshot)
        elif snapshot["status"] == "canceled":
            if hasattr(self, "dl_progress_card"):
                self.dl_progress_card.setVisible(False)
            if hasattr(self, "review_export_progress_card"):
                self.review_export_progress_card.setVisible(False)
            self.set_progress_panel_visible(False)
            self.poll_timer.stop()
            self.set_create_inputs_locked(False)
            self.render_button.setEnabled(True)
            if hasattr(self, "edit_text_button"):
                self.edit_text_button.setEnabled(True)
            if hasattr(self, "btn_back_review"):
                self.btn_back_review.setEnabled(True)
            self.add_manual_button.setEnabled(True)
            self.status_label.setText("Proses dibatalkan.")
            self.sub_status_label.setText("Pengaturan klip telah dibuka kembali.")
            self.log_terminal("Proses render telah dibatalkan.")
        elif snapshot["status"] == "failed":
            if hasattr(self, "dl_progress_card"):
                self.dl_progress_card.setVisible(False)
            if hasattr(self, "review_export_progress_card"):
                self.review_export_progress_card.setVisible(False)
            self.poll_timer.stop()
            self.download_button.setEnabled(True)
            self.local_file_button.setEnabled(True)
            self.set_create_inputs_locked(False)
            self.render_button.setEnabled(True)
            if hasattr(self, "edit_text_button"):
                self.edit_text_button.setEnabled(True)
            if hasattr(self, "btn_back_review"):
                self.btn_back_review.setEnabled(True)
            self.add_manual_button.setEnabled(True)
            err_msg = str(snapshot.get("error") or snapshot.get("message") or "")
            if "dibatalkan" in err_msg.lower():
                self.set_progress_panel_visible(False)
                self.status_label.setText("Proses dibatalkan.")
                self.sub_status_label.setText("Pengaturan klip telah dibuka kembali.")
                self.log_terminal("Proses telah dibatalkan.")
            else:
                self.log_terminal(f"ERROR: {err_msg}")
                QMessageBox.critical(self, "Proses gagal", err_msg)

    def open_live_hud(self) -> None:
        try:
            from clipper_hud import launch_hud_process
            launch_hud_process()
        except Exception as exc:
            QMessageBox.warning(self, "Gagal Membuka HUD", f"Tidak dapat membuka Live HUD: {exc}")

    def build_timed_cues(self, transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cues: list[dict[str, Any]] = []
        lines_val = getattr(self.current_options, "subtitle_max_lines", 2) if self.current_options else 2
        for item in transcript:
            s_start = float(item.get("start", 0.0))
            s_end = float(item.get("end", 0.0))
            text = str(item.get("text", "")).strip()
            if not text or s_end <= s_start:
                continue
            sub_cues = core.split_segment_into_cues(s_start, s_end, text, max_lines=lines_val)
            for c_start, c_end, c_text in sub_cues:
                if c_end > c_start and c_text.strip():
                    cues.append({"start": c_start, "end": c_end, "text": c_text.strip()})
        cues.sort(key=lambda x: x["start"])
        for i in range(len(cues) - 1):
            if cues[i]["end"] > cues[i + 1]["start"]:
                cues[i]["end"] = max(cues[i]["start"] + 0.2, cues[i + 1]["start"])
        return cues

    def show_review(self, job: dict[str, Any]) -> None:
        self.current_review_job = job
        self.selected_review_clip_index = 0
        self.set_progress_panel_visible(False)
        self.set_create_inputs_locked(False)
        if hasattr(self, "set_review_unlocked"):
            self.set_review_unlocked(True)
        if hasattr(self, "review_export_progress_card"):
            self.review_export_progress_card.setVisible(False)
        self.render_button.setEnabled(True)
        if hasattr(self, "edit_text_button"):
            self.edit_text_button.setEnabled(True)
        if hasattr(self, "btn_back_review"):
            self.btn_back_review.setEnabled(True)
        self.add_manual_button.setEnabled(True)
        if not self.current_options:
            try:
                self.current_options = core.JOB_OPTIONS.get(job.get("id")) or self.build_options()
            except Exception:
                self.current_options = None
        studio_prev_mode = (
            getattr(self.create_preview_video, "preview_mode", "auto_universal_9_16")
            if hasattr(self, "create_preview_video")
            else "auto_universal_9_16"
        )
        if hasattr(self, "review_format_combo"):
            self.review_format_combo.blockSignals(True)
            idx_rf = self.review_format_combo.findData(studio_prev_mode)
            if idx_rf >= 0:
                self.review_format_combo.setCurrentIndex(idx_rf)
            self.review_format_combo.blockSignals(False)
        if hasattr(self, "video_widget"):
            self.video_widget.set_preview_mode(studio_prev_mode)
            if hasattr(self, "create_preview_video"):
                self.video_widget.set_manual_crop(
                    self.create_preview_video.manual_crop_x,
                    self.create_preview_video.manual_crop_y,
                    self.create_preview_video.manual_zoom,
                )
            if hasattr(self, "mirror_video_check"):
                self.video_widget.mirror_horizontal = self.mirror_video_check.isChecked()
            if hasattr(self, "color_boost_check"):
                self.video_widget.color_boost_enabled = self.color_boost_check.isChecked()
            if hasattr(self, "realtime_face_box_check"):
                self.video_widget.set_show_face_boxes(self.realtime_face_box_check.isChecked())
            self.video_widget.update()
        if hasattr(self, "player") and hasattr(self, "speed_shift_check"):
            try:
                self.player.setPlaybackRate(1.03 if self.speed_shift_check.isChecked() else 1.0)
            except Exception:
                pass

        ai_count = sum(1 for clip in job["clips"] if clip.get("source") == "ai")
        manual_count = sum(1 for clip in job["clips"] if clip.get("source") == "manual")
        total_clips = len(job["clips"])
        self.review_clip_count_label.setText(f"{total_clips} Klip Siap Direview ({ai_count} Otomatis AI · {manual_count} Manual)")
        self.review_status.setText(f"{ai_count} klip AI & {manual_count} klip manual siap dirender")
        self.active_transcript = self.build_timed_cues(job.get("transcript") or [])
        subtitles_available = bool(self.current_options and self.current_options.subtitle_style != "none")
        self.source_subtitle_overlay.setVisible(subtitles_available and bool(self.active_transcript))
        source_path = Path(job.get("source_path", ""))
        source_path_str = str(source_path) if source_path.exists() else ""
        if source_path.exists():
            self.source_has_subtitles = core.check_video_has_subtitles(source_path)
            self.player.setSource(QUrl.fromLocalFile(source_path_str))
            dur_sec = core.media_duration(source_path, 0.0)
            if hasattr(self, "timeline_widget"):
                self.timeline_widget.set_duration(int(dur_sec * 1000))
        self.update_realtime_subtitle(0.0)
        self.auto_preview_running = False
        self.auto_preview_index = 0
        self.auto_preview_items = []
        self.auto_preview_button.setText("Mulai preview clip AI")

        while self.review_cards_layout.count():
            item = self.review_cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.review_card_widgets = []
        self.review_entries = []
        for index, clip in enumerate(job["clips"]):
            entry = {
                "title": f"{index + 1:02d} · {clip['title']} · {format_time(clip['start'])}–{format_time(clip['end'])}",
                "path": str(
                    core.clip_result_dir(
                        Path(job.get("result_dir") or core.job_result_dir(job["id"])),
                        clip["id"],
                        clip["title"],
                    )
                    / "clip.mp4"
                ),
                "source": clip.get("source", "ai"),
            }
            self.review_entries.append(entry)
            if clip.get("source") == "ai":
                self.auto_preview_items.append(entry)

            card = ReviewClipCardWidget(clip, index, source_path_str, self.review_cards_container)
            card.clicked.connect(self.select_review_clip)
            self.review_cards_layout.addWidget(card)
            self.review_card_widgets.append(card)

        self.review_cards_layout.addStretch()

        if total_clips > 0:
            self.select_review_clip(0)

        self.auto_preview_button.setEnabled(bool(self.auto_preview_items))
        self.tabs.setTabEnabled(3, True)
        self.switch_tab(3)

    def select_review_clip(self, index: int) -> None:
        if not hasattr(self, "current_review_job") or not self.current_review_job:
            return
        clips = self.current_review_job.get("clips", [])
        if not (0 <= index < len(clips)):
            return
        self.selected_review_clip_index = index
        clip = clips[index]

        for i, card in enumerate(getattr(self, "review_card_widgets", [])):
            card.set_selected(i == index)

        start_ms = int(float(clip.get("start", 0.0)) * 1000)
        self.player.setPosition(start_ms)

        if hasattr(self, "timeline_widget"):
            self.timeline_widget.set_active_clip(float(clip.get("start", 0.0)), float(clip.get("end", 0.0)))
            self.timeline_widget.set_position(start_ms)

    def open_edit_text_dialog(self) -> None:
        if not hasattr(self, "current_review_job") or not self.current_review_job:
            return
        clips = self.current_review_job.get("clips", [])
        if not clips:
            return
        idx = getattr(self, "selected_review_clip_index", 0)
        if not (0 <= idx < len(clips)):
            idx = 0
        clip = clips[idx]
        c_start = float(clip.get("start", 0.0))
        c_end = float(clip.get("end", 0.0))

        transcript = self.current_review_job.get("transcript", [])
        sub_lines = []
        for seg in transcript:
            if float(seg.get("end", 0)) > c_start and float(seg.get("start", 0)) < c_end:
                sub_lines.append(f"{float(seg['start']):.2f} - {float(seg['end']):.2f} | {seg.get('text', '')}")

        dialog = EditTextDialog(clip.get("title", ""), clip.get("caption", ""), "\n".join(sub_lines), self)
        if dialog.exec():
            new_title, new_caption, new_subs_raw = dialog.get_data()
            clip["title"] = new_title
            clip["caption"] = new_caption

            updated_segments = []
            for line in new_subs_raw.splitlines():
                if "|" not in line or "-" not in line.split("|")[0]:
                    continue
                times_part, text_part = line.split("|", 1)
                s_str, e_str = times_part.split("-", 1)
                try:
                    s_val, e_val = float(s_str.strip()), float(e_str.strip())
                    if e_val > s_val and text_part.strip():
                        updated_segments.append({"start": round(s_val, 2), "end": round(e_val, 2), "text": text_part.strip()})
                except ValueError:
                    pass

            if updated_segments:
                outside = [
                    seg for seg in transcript
                    if not (float(seg.get("end", 0)) > c_start and float(seg.get("start", 0)) < c_end)
                ]
                new_transcript = sorted(outside + updated_segments, key=lambda x: x["start"])
                self.current_review_job["transcript"] = new_transcript
                if self.current_job_id:
                    with core.JOBS_LOCK:
                        core_job = core.JOBS.get(self.current_job_id)
                        if core_job:
                            core_job.transcript = new_transcript
                            core_job.render_profile = {}

            if self.current_job_id:
                with core.JOBS_LOCK:
                    core_job = core.JOBS.get(self.current_job_id)
                    if core_job and idx < len(core_job.clips):
                        core_job.clips[idx].title = new_title
                        core_job.clips[idx].caption = new_caption
                        core_job.render_profile = {}
            self.show_review(self.current_review_job)
            self.select_review_clip(idx)

    def open_manual_clip_dialog(self) -> None:
        current_sec = self.player.position() / 1000.0 if hasattr(self, "player") else 0.0
        max_dur = self.player.duration() / 1000.0 if hasattr(self, "player") and self.player.duration() > 0 else 300.0
        dialog = ManualClipDialog(current_pos_sec=current_sec, max_dur_sec=max_dur, parent=self)
        if dialog.exec():
            start_str, end_str, title_str = dialog.get_data()
            self.manual_start.setText(start_str)
            self.manual_end.setText(end_str)
            self.manual_title.setText(title_str)
            self.add_manual_clip()

    def on_review_format_changed(self) -> None:
        if not hasattr(self, "review_format_combo"):
            return
        mode = str(self.review_format_combo.currentData() or "auto_universal_9_16")
        if mode == "original_native":
            self.set_framing_mode("none")
        elif mode in (
            "auto_universal_9_16",
            "auto_podcast_9_16",
            "crop_9_16",
            "split_2_9_16",
            "auto_gaming_9_16",
            "auto_cinema_9_16",
        ):
            self.set_framing_mode("auto")
            if hasattr(self, "unified_format_combo"):
                idx = self.unified_format_combo.findData(mode)
                if idx >= 0:
                    self.unified_format_combo.setCurrentIndex(idx)
        else:
            self.set_framing_mode("manual")
            review_to_manual = {
                "fit_9_16": ("9:16", "manual_fit"),
                "ambient_9_16": ("9:16", "manual_ambient"),
                "manual_crop": ("9:16", "manual_crop"),
                "manual_split": ("9:16", "manual_split"),
                "facecam_9_16": ("9:16", "manual_facecam"),
                "square_1_1": ("1:1", "manual_crop"),
                "fit_16_9": ("16:9", "manual_fit"),
            }
            asp_v, sty_v = review_to_manual.get(mode, ("9:16", "manual_fit"))
            if hasattr(self, "manual_aspect_combo"):
                idx_a = self.manual_aspect_combo.findData(asp_v)
                if idx_a >= 0:
                    self.manual_aspect_combo.setCurrentIndex(idx_a)
            if hasattr(self, "manual_style_combo"):
                idx_s = self.manual_style_combo.findData(sty_v)
                if idx_s >= 0:
                    self.manual_style_combo.setCurrentIndex(idx_s)
        if hasattr(self, "video_widget"):
            self.video_widget.set_preview_mode(mode)
        if self.current_options:
            self.current_options.aspect_ratio = self.aspect_combo.currentData()
            self.current_options.framing = self.framing_combo.currentData()
            self.current_options.layout = self.layout_combo.currentData()
            self.current_options.framing_mode = getattr(self, "framing_mode_state", "auto")
            self.current_options.manual_crop_x = (
                (self.manual_crop_x_slider.value() / 100.0) if hasattr(self, "manual_crop_x_slider") else 0.5
            )
            self.current_options.manual_crop_y = (
                (self.manual_crop_y_slider.value() / 100.0) if hasattr(self, "manual_crop_y_slider") else 0.5
            )
            self.current_options.manual_zoom = (
                (self.manual_zoom_slider.value() / 100.0) if hasattr(self, "manual_zoom_slider") else 1.0
            )
        self.update_review_subtitle_position()
        if hasattr(self, "review_status"):
            self.review_status.setText(f"Format klip diubah ke: {self.review_format_combo.currentText()}")

    def cycle_review_ratio(self) -> None:
        if hasattr(self, "review_format_combo"):
            nxt = (self.review_format_combo.currentIndex() + 1) % self.review_format_combo.count()
            self.review_format_combo.setCurrentIndex(nxt)

    def reset_review_timeline(self) -> None:
        if hasattr(self, "current_review_job") and self.current_review_job:
            clips = self.current_review_job.get("clips", [])
            idx = getattr(self, "selected_review_clip_index", 0)
            if 0 <= idx < len(clips):
                start_sec = clips[idx].get("start", 0.0)
                self.seek_review_video(int(start_sec * 1000))
                if hasattr(self, "review_status"):
                    self.review_status.setText(f"Putaran dikembalikan ke awal klip #{idx + 1:02d} ({format_time(start_sec)})")
                return
        self.seek_review_video(0)
        if hasattr(self, "review_status"):
            self.review_status.setText("Putaran dikembalikan ke detik 00:00")

    def toggle_review_zoom(self) -> None:
        self.cycle_review_ratio()

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
        self.preview_status.setText("Clip manual sudah dirender dan tersedia di daftar klip.")
        self.show_review(snapshot)

    def render_final(self) -> None:
        if not self.current_job_id:
            return
        try:
            self.current_options = self.build_options()
        except Exception:
            if not self.current_options:
                return
        with core.JOBS_LOCK:
            core.JOB_OPTIONS[self.current_job_id] = self.current_options
        self.render_button.setEnabled(False)
        if hasattr(self, "edit_text_button"):
            self.edit_text_button.setEnabled(False)
        if hasattr(self, "btn_back_review"):
            self.btn_back_review.setEnabled(False)
        self.add_manual_button.setEnabled(False)
        if hasattr(self, "review_export_progress_card"):
            self.review_export_bar.setValue(0)
            self.review_export_pct_lbl.setText("0%")
            self.review_export_status_lbl.setText("Menyiapkan Ekspor & Render Video Final...")
            self.review_export_detail_lbl.setText("Menggabungkan pemotongan klip, framing kamera, dan subtitle ke file MP4...")
            self.review_export_progress_card.setVisible(True)
        self.set_create_inputs_locked(True)
        self.set_progress_panel_visible(True)
        self.status_label.setText("Mengekspor & merender klip final...")
        self.sub_status_label.setText("Sedang memproses video final dari menu Review & Trim...")
        self.preview_status.setText("Menyiapkan render final semua klip terpilih...")
        self.worker = JobWorker(self.current_job_id, self.current_options, render=True)
        self.worker.finished_job.connect(self.refresh_job)
        self.worker.start()
        self.poll_timer.start(700)

    def show_results(self, job: dict[str, Any]) -> None:
        self.current_results_job = job
        self.tabs.setTabEnabled(4, True)
        self.switch_tab(4)
        clips = job.get("clips", [])
        total_clips = len(clips)
        self.results_title.setText(f"{total_clips} KLIP SELESAI")

        result_dir = Path(job.get("result_dir") or core.job_result_dir(job["id"]))
        self.results_folder_label.setText(f"Folder Hasil: {result_dir}")

        total_dur_sec = sum(max(0.0, float(clip.get("end", 0.0)) - float(clip.get("start", 0.0))) for clip in clips)
        total_bytes = 0

        while self.results_grid_layout.count():
            item = self.results_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.results_list.clear()

        columns = 3
        for index, clip in enumerate(clips):
            clip_path = core.clip_result_dir(result_dir, clip["id"], clip["title"]) / "clip.mp4"
            if clip_path.is_file():
                total_bytes += clip_path.stat().st_size

            item = QListWidgetItem(f"{clip['title']} · {format_time(clip['start'])}–{format_time(clip['end'])}")
            item.setData(Qt.ItemDataRole.UserRole, str(clip_path))
            self.results_list.addItem(item)

            card = ResultClipCardWidget(clip, clip_path, index, self.results_grid_widget)
            row = index // columns
            col = index % columns
            self.results_grid_layout.addWidget(card, row, col)

        self.results_dur_label.setText(f"Total Durasi: {format_time(total_dur_sec)}")
        self.results_size_label.setText(f"Ukuran: {total_bytes / (1024 * 1024):.1f} MB")
        self.results_count_label.setText(f"Total Berkas: {total_clips}")

    def batch_queue_all_clips_to_tiktok(self) -> None:
        job = getattr(self, "current_results_job", None)
        if not job:
            QMessageBox.information(self, "Antrean TikTok", "Belum ada klip hasil render untuk dimasukkan ke antrean.")
            return
        clips = job.get("clips", [])
        result_dir = Path(job.get("result_dir") or core.job_result_dir(job["id"]))
        added_count = 0
        try:
            import auto_clipper_tiktok as act
            for clip in clips:
                clip_path = core.clip_result_dir(result_dir, clip["id"], clip["title"]) / "clip.mp4"
                if not clip_path.is_file():
                    continue
                title_raw = str(clip.get("title", "Klip Viral")).strip()
                cap_raw = str(clip.get("caption", "")).strip()
                act.enqueue_clips_for_scheduled_upload(
                    [
                        {
                            "clip_path": str(clip_path),
                            "title": title_raw,
                            "caption": cap_raw,
                            "hashtags": ["#PodcastIndonesia", "#CurhatBang", "#PotonganPodcast", "#KontenViral", "#fyp"],
                        }
                    ],
                    video_title=title_raw,
                )
                added_count += 1
            if added_count > 0:
                QMessageBox.information(
                    self,
                    "Antrean Jam Ramai TikTok",
                    f"{added_count} klip berhasil dimasukkan ke Antrean Jam Ramai FYP!\n\n"
                    "Fitur otomatis yang diterapkan:\n"
                    "• Jadwal fleksibel mengikuti jam trafik tertinggi (Siang 11:30–13:30, Sore 16:30–18:15, Prime Time 19:15–22:30)\n"
                    "• Frame Sampul (Cover) otomatis di detik 1.8s\n"
                    "• Sound Viral TikTok otomatis (Volume -25 dB)\n"
                    "• 5 Hashtag SEO terfokus + CTA Save/Share",
                )
            else:
                QMessageBox.warning(self, "Antrean TikTok", "Tidak ditemukan file video klip yang valid.")
        except Exception as exc:
            QMessageBox.critical(self, "Gagal Menjadwalkan", f"Terjadi kesalahan: {exc}")

    def open_result(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def trigger_youtube_login(self) -> None:
        if hasattr(self, "btn_login_yt"):
            self.btn_login_yt.setEnabled(False)
            self.btn_login_yt.setText("Membuka Login...")
        self._yt_login_worker = YouTubeLoginWorker()
        def on_done(ok: bool, msg: str):
            if hasattr(self, "btn_login_yt"):
                self.btn_login_yt.setEnabled(True)
                self.btn_login_yt.setText("Login YouTube Studio")
            if ok:
                QMessageBox.information(self, "Login YouTube", msg)
            else:
                QMessageBox.warning(self, "Login YouTube", msg)
        self._yt_login_worker.finished_login.connect(on_done)
        self._yt_login_worker.start()

    def open_results_folder(self) -> None:
        if self.current_job_id:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(core.job_result_dir(self.current_job_id))))

    def on_review_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if hasattr(self, "play_button"):
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.play_button.setIcon(make_vector_icon("pause", "#FFFFFF", 24))
                self.play_button.setToolTip("Jeda Video (Spasi)")
            else:
                self.play_button.setIcon(make_vector_icon("play", "#FFFFFF", 24))
                self.play_button.setToolTip("Putar Video (Spasi)")

    def toggle_video(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if self.player.position() >= self.player.duration() and self.player.duration() > 0:
                self.player.setPosition(0)
            self.player.play()

    def seek_review_video(self, position: int) -> None:
        self.player.setPosition(position)

    def update_player_time(self, position: int) -> None:
        if not self.review_seek_slider.isSliderDown():
            self.review_seek_slider.setValue(position)
        if hasattr(self, "timeline_widget"):
            self.timeline_widget.set_position(position)
        self.current_time.setText(f"{format_time(position / 1000)} / {format_time(self.player.duration() / 1000)}")
        self.update_realtime_subtitle(position / 1000)

    def update_player_duration(self, duration: int) -> None:
        self.review_seek_slider.setRange(0, max(0, duration))
        self.review_seek_slider.setEnabled(duration > 0)
        if hasattr(self, "timeline_widget"):
            self.timeline_widget.set_duration(duration)
        self.current_time.setText(f"{format_time(self.player.position() / 1000)} / {format_time(duration / 1000)}")

    def update_realtime_subtitle(self, seconds: float) -> None:
        if hasattr(self, "review_hook_banner_overlay") and hasattr(self, "video_widget"):
            hb_on = getattr(self.current_options, "hook_banner_enabled", False) if self.current_options else (self.hook_banner_toggle.isChecked() if hasattr(self, "hook_banner_toggle") else False)
            hb_dur = float(getattr(self.current_options, "hook_banner_duration", 0.0)) if self.current_options else (
                float(self.hook_banner_dur_combo.currentData() or 0)
                if hasattr(self, "hook_banner_dur_combo")
                else 0.0
            )
            hb_pos_mode = str(getattr(self.current_options, "hook_banner_position", "top") or "top") if self.current_options else (
                str(self.hook_banner_pos_combo.currentData() or "top")
                if hasattr(self, "hook_banner_pos_combo")
                else "top"
            )
            hb_fx = float(getattr(self.current_options, "hook_banner_x", getattr(self, "hook_banner_free_x", 0.5)))
            hb_fy = float(getattr(self.current_options, "hook_banner_y", getattr(self, "hook_banner_free_y", 0.11)))
            clip_start = 0.0
            clip_title = ""
            if hasattr(self, "current_review_job") and self.current_review_job:
                clips = self.current_review_job.get("clips", [])
                c_idx = getattr(self, "selected_review_clip_index", 0)
                if 0 <= c_idx < len(clips):
                    clip_start = float(clips[c_idx].get("start", 0.0))
                    clip_title = str(clips[c_idx].get("title", "")).strip()

            custom_hb = getattr(self.current_options, "hook_banner_text", "").strip() if self.current_options else ""
            if not custom_hb and hasattr(self, "hook_banner_edit"):
                custom_hb = self.hook_banner_edit.text().strip()
            hb_text = custom_hb or clip_title
            in_hb_window = (seconds >= clip_start) if hb_dur <= 0 else (0.0 <= (seconds - clip_start) <= hb_dur)

            if hb_on and hb_text and in_hb_window:
                vw_w = max(1, self.video_widget.width())
                vw_h = max(1, self.video_widget.height())
                is_landscape = vw_w >= vw_h
                headline = core.build_thumbnail_hook_headline(hb_text) if hasattr(core, "build_thumbnail_hook_headline") else hb_text.upper()
                hb_words = headline.split()
                colored_tokens = [f"<font color='#FFFFFF'>{hw}</font>" for hw in hb_words]
                max_per_line = 5 if is_landscape else 4
                hb_lines = [" ".join(colored_tokens[i:i+max_per_line]) for i in range(0, len(colored_tokens), max_per_line)]
                rich_hb = "<br>".join(hb_lines[:2])

                self.review_hook_banner_overlay.setTextFormat(Qt.TextFormat.RichText)
                self.review_hook_banner_overlay.setText(rich_hb)
                self.review_hook_banner_overlay.setStyleSheet(
                    "background: rgba(10, 10, 16, 230); color: #FFFFFF; font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; "
                    "font-size: 12px; font-weight: 800; padding: 6px 14px; border-radius: 8px; "
                    "border: 1px solid rgba(59, 130, 246, 190);"
                )
                self.review_hook_banner_overlay.setMaximumWidth(int(vw_w * 0.88))
                self.review_hook_banner_overlay.adjustSize()
                lw_r = self.review_hook_banner_overlay.width()
                lh_r = self.review_hook_banner_overlay.height()
                if hb_pos_mode == "free":
                    rx = int(vw_w * hb_fx - lw_r / 2.0)
                    ry = int(vw_h * hb_fy - lh_r / 2.0)
                elif hb_pos_mode == "upper_mid":
                    rx = (vw_w - lw_r) // 2
                    ry = int(vw_h * 0.28 - lh_r / 2.0)
                elif hb_pos_mode == "center":
                    rx = (vw_w - lw_r) // 2
                    ry = int(vw_h * 0.45 - lh_r / 2.0)
                elif hb_pos_mode == "bottom_above_sub":
                    rx = (vw_w - lw_r) // 2
                    ry = int(vw_h * 0.65 - lh_r / 2.0)
                else:
                    rx = (vw_w - lw_r) // 2
                    ry = max(10, int(vw_h * 0.085 - lh_r / 2.0))
                self.review_hook_banner_overlay.move(
                    max(4, min(max(4, vw_w - lw_r - 4), rx)),
                    max(4, min(max(4, vw_h - lh_r - 4), ry)),
                )
                self.review_hook_banner_overlay.setVisible(True)
                self.review_hook_banner_overlay.raise_()
            else:
                self.review_hook_banner_overlay.setVisible(False)

        skip_existing = getattr(self.current_options, "skip_if_has_subtitles", True) if self.current_options else True
        if getattr(self, "source_has_subtitles", False) and skip_existing:
            self.source_subtitle_overlay.setVisible(False)
            return

        if not self.current_options or self.current_options.subtitle_style == "none" or not getattr(self, "active_transcript", None):
            self.source_subtitle_overlay.setVisible(False)
            return
        matching = [
            item for item in self.active_transcript
            if float(item.get("start", 0)) <= seconds <= float(item.get("end", 0))
        ]
        current = matching[-1] if matching else None
        text = str(current.get("text", "")).strip() if current else ""
        if not text:
            self.source_subtitle_overlay.setVisible(False)
            return

        active_col_opt = getattr(self.current_options, "subtitle_active_color", "#FFDD00")
        sub_mode = getattr(self.current_options, "subtitle_mode", "active_highlight")
        c_start = float(current.get("start", 0.0))
        c_end = max(c_start + 0.1, float(current.get("end", c_start + 1.0)))
        rel_ratio = max(0.0, min(0.999, (seconds - c_start) / (c_end - c_start)))

        tokens = text.replace("\n", " ").split()
        if tokens and sub_mode in ("active_highlight", "single_word"):
            active_idx = min(len(tokens) - 1, int(rel_ratio * len(tokens)))
            if sub_mode == "single_word":
                tok = tokens[active_idx]
                act_hex = "#FFDD00" if active_col_opt in ("#FFDD00", "auto_context") else active_col_opt
                if active_col_opt == "auto_context":
                    w_hex, _, _ = core.detect_word_context_color(tok, text, active_col_opt)
                    act_hex = w_hex
                rich_text = f"<font color='{act_hex}'><b><span style='font-size:15px;'>{tok.upper()}</span></b></font>"
            else:
                rich_tokens = []
                for idx_t, tok in enumerate(tokens):
                    if idx_t == active_idx:
                        act_hex = "#FFDD00" if active_col_opt in ("#FFDD00", "auto_context") else active_col_opt
                        if active_col_opt == "auto_context":
                            w_hex, _, _ = core.detect_word_context_color(tok, text, active_col_opt)
                            act_hex = w_hex
                        rich_tokens.append(f"<font color='{act_hex}'><b><span style='font-size:15px;'>{tok.upper()}</span></b></font>")
                    else:
                        rich_tokens.append(tok)
                if len(rich_tokens) >= 5:
                    mid = len(rich_tokens) // 2
                    rich_text = " ".join(rich_tokens[:mid]) + "<br>" + " ".join(rich_tokens[mid:])
                else:
                    rich_text = " ".join(rich_tokens)
        else:
            rich_text = text

        self.apply_subtitle_preview_style(
            self.source_subtitle_overlay,
            self.current_options.subtitle_style,
            text=rich_text,
            color=self.current_options.subtitle_color,
            font_size=getattr(self.current_options, "subtitle_font_size", 14),
            max_lines=getattr(self.current_options, "subtitle_max_lines", 2),
        )
        self.source_subtitle_overlay.setTextFormat(Qt.TextFormat.RichText)
        self.source_subtitle_overlay.setText(rich_text)
        self.source_subtitle_overlay.adjustSize()
        self.update_review_subtitle_position()

    def update_review_subtitle_position(self) -> None:
        if not hasattr(self, "video_widget") or not hasattr(self, "source_subtitle_overlay") or not self.current_options:
            return
        label = self.source_subtitle_overlay
        if label.parent() != self.video_widget:
            label.setParent(self.video_widget)
        position = self.current_options.subtitle_position
        pw = max(1, self.video_widget.width())
        ph = max(1, self.video_widget.height())
        label.setMaximumWidth(max(120, int(pw * 0.88)))
        label.setWordWrap(True)
        label.adjustSize()
        lw = label.width()
        lh = label.height()

        if position == "free":
            available_width = max(0, pw - lw)
            available_height = max(0, ph - lh)
            label.move(
                int(available_width * self.current_options.subtitle_x),
                int(available_height * self.current_options.subtitle_y),
            )
        elif position == "top":
            x = (pw - lw) // 2
            y = int(ph * 0.14)
            label.move(max(0, x), max(0, y))
        elif position == "center":
            x = (pw - lw) // 2
            y = (ph - lh) // 2
            label.move(max(0, x), max(0, y))
        else:
            x = (pw - lw) // 2
            live_faces = len(getattr(self.video_widget, "live_face_boxes", []))
            mode = getattr(self.video_widget, "preview_mode", "auto_universal_9_16")
            if (mode == "split_2_9_16" and live_faces >= 1) or (mode in ("auto_podcast_9_16", "auto_universal_9_16") and live_faces >= 2):
                y = (ph - lh) // 2
            elif ph > pw:
                y = min(ph - lh - 18, max(24, int(ph * 0.74)))
            else:
                y = max(12, ph - lh - max(16, int(ph * 0.09)))
            label.move(max(0, x), y)
        label.raise_()

    def switch_tab(self, index: int) -> None:
        if not hasattr(self, "tabs") or not self.tabs.isTabEnabled(index):
            return
        current_idx = self.tabs.currentIndex()
        for button_index, button in self.nav_buttons.items():
            button.setChecked(button_index == index)
        if hasattr(self, "nav_setup_btn"):
            self.nav_setup_btn.setChecked(index == 0)
        if hasattr(self, "nav_models_btn"):
            self.nav_models_btn.setChecked(index == 5)

        if current_idx == index:
            return

        self.animate_tab_transition(self.tabs, current_idx, index, duration_ms=160)

        if index == 2 and hasattr(self, "create_preview_frame"):
            self.update_create_preview()
            QTimer.singleShot(25, self.ensure_splitter_balanced)
        elif index == 3 and hasattr(self, "review_lock_overlay") and hasattr(self, "review_outer_wrapper"):
            QTimer.singleShot(
                10,
                lambda: self.review_lock_overlay.setGeometry(self.review_outer_wrapper.rect())
                if not getattr(self, "review_is_unlocked", False)
                else None,
            )

    def animate_tab_transition(self, tab_widget: QTabWidget, from_idx: int, to_idx: int, duration_ms: int = 160) -> None:
        if from_idx == to_idx or from_idx < 0 or to_idx < 0:
            tab_widget.setCurrentIndex(to_idx)
            return

        old_w = tab_widget.widget(from_idx)
        new_w = tab_widget.widget(to_idx)
        if old_w is None or new_w is None:
            tab_widget.setCurrentIndex(to_idx)
            return

        if not hasattr(self, "_tab_anim_state"):
            self._tab_anim_state = {}
        if tab_widget in self._tab_anim_state:
            prev_group, prev_overlay, prev_w = self._tab_anim_state.pop(tab_widget, (None, None, None))
            if prev_group is not None:
                try:
                    prev_group.stop()
                except Exception:
                    pass
            if prev_overlay is not None:
                try:
                    prev_overlay.deleteLater()
                except Exception:
                    pass
            if prev_w is not None:
                try:
                    prev_w.setGraphicsEffect(None)
                except Exception:
                    pass

        if not old_w.isVisible() or old_w.width() <= 0 or old_w.height() <= 0:
            tab_widget.setCurrentIndex(to_idx)
            return

        parent_w = old_w.parentWidget() or tab_widget
        try:
            geom = old_w.geometry()
            pm = old_w.grab()
        except Exception:
            tab_widget.setCurrentIndex(to_idx)
            return

        overlay = QLabel(parent_w)
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        overlay.setPixmap(pm)
        overlay.setGeometry(geom)
        overlay.show()
        overlay.raise_()

        # Switch to target tab immediately at natural layout position (zero layout fighting / zero gempa)
        tab_widget.setCurrentIndex(to_idx)

        eff_old = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(eff_old)

        eff_new = QGraphicsOpacityEffect(new_w)
        eff_new.setOpacity(0.08)
        new_w.setGraphicsEffect(eff_new)

        anim_group = QParallelAnimationGroup(parent_w)

        anim_fade_old = QPropertyAnimation(eff_old, b"opacity", anim_group)
        anim_fade_old.setDuration(duration_ms)
        anim_fade_old.setStartValue(1.0)
        anim_fade_old.setEndValue(0.0)
        anim_fade_old.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim_group.addAnimation(anim_fade_old)

        anim_fade_new = QPropertyAnimation(eff_new, b"opacity", anim_group)
        anim_fade_new.setDuration(duration_ms)
        anim_fade_new.setStartValue(0.08)
        anim_fade_new.setEndValue(1.0)
        anim_fade_new.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim_group.addAnimation(anim_fade_new)

        def on_transition_finished() -> None:
            try:
                overlay.deleteLater()
            except Exception:
                pass
            try:
                new_w.setGraphicsEffect(None)
            except Exception:
                pass
            if tab_widget in self._tab_anim_state:
                del self._tab_anim_state[tab_widget]

        anim_group.finished.connect(on_transition_finished)
        self._tab_anim_state[tab_widget] = (anim_group, overlay, new_w)
        anim_group.start()

    def animate_progress_bar(self, bar: Any, target_value: int | float, duration_ms: int = 250) -> None:
        target = max(0, min(100, int(target_value)))
        if not hasattr(self, "_bar_anims"):
            self._bar_anims = {}
        current_anim = self._bar_anims.get(bar)
        if current_anim is not None and current_anim.state() == QAbstractAnimation.State.Running:
            current_anim.stop()
        curr = bar.value()
        if curr == target:
            return
        if target < curr:
            bar.setValue(target)
            return
        anim = QPropertyAnimation(bar, b"value", self)
        anim.setDuration(duration_ms)
        anim.setStartValue(curr)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._bar_anims[bar] = anim
        anim.start()

    def set_progress_panel_visible(self, visible: bool, animated: bool = True) -> None:
        if not hasattr(self, "progress_panel"):
            return
        if not animated:
            self.progress_panel.setVisible(visible)
            return

        if self._panel_anim is not None and self._panel_anim.state() == QAbstractAnimation.State.Running:
            self._panel_anim.stop()

        if visible:
            self.progress_panel.setVisible(True)
            eff = self.progress_panel.graphicsEffect()
            if not isinstance(eff, QGraphicsOpacityEffect):
                eff = QGraphicsOpacityEffect(self.progress_panel)
                self.progress_panel.setGraphicsEffect(eff)
            eff.setOpacity(0.0)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(220)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.finished.connect(lambda: self.progress_panel.setGraphicsEffect(None))
            self._panel_anim = anim
            anim.start()
        else:
            if not self.progress_panel.isVisible():
                return
            eff = self.progress_panel.graphicsEffect()
            if not isinstance(eff, QGraphicsOpacityEffect):
                eff = QGraphicsOpacityEffect(self.progress_panel)
                self.progress_panel.setGraphicsEffect(eff)
            start_op = eff.opacity() if eff.opacity() > 0.05 else 1.0
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(180)
            anim.setStartValue(start_op)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            def on_hidden() -> None:
                self.progress_panel.setVisible(False)
                self.progress_panel.setGraphicsEffect(None)
            anim.finished.connect(on_hidden)
            self._panel_anim = anim
            anim.start()

    def toggle_theme(self) -> None:
        self.apply_theme(self.current_theme != "light")

    def apply_theme(self, light: bool) -> None:
        self.current_theme = "light" if light else "dark"
        if hasattr(self, "theme_button"):
            self.theme_button.setText("Tema: Gelap" if light else "Tema: Terang")
        self.setStyleSheet(self.stylesheet(self.current_theme))
        self.refresh_subtitle_preview_style()
        QSettings("ENCLip", "ENCLip").setValue("theme", self.current_theme)

    @staticmethod
    def stylesheet(theme: str = "dark") -> str:
        if theme == "light":
            return (
                "QWidget { color: #09090B; font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif; font-size: 13px; } "
                "QMainWindow, QDialog, QScrollArea, QWidget#pageContent, QTabWidget::pane { background: #F8FAFC; } "
                "QLabel { background: transparent; color: #27272A; padding: 1px 2px; } "
                "QToolBar { background: #FFFFFF; border-bottom: 1px solid #E4E4E7; spacing: 8px; padding: 6px 14px; } "
                "QFrame#navPillTrack { background: #F4F4F5; border: 1px solid #E4E4E7; border-radius: 10px; } "
                "QPushButton#navButton { background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 6px 13px; color: #52525B; font-weight: 600; font-size: 12px; } "
                "QPushButton#navButton:hover { background: #E4E4E7; color: #09090B; } "
                "QPushButton#navButton:checked { background: #2563EB; border: 1px solid #1D4ED8; color: #FFFFFF; font-weight: 700; } "
                "QPushButton#navUtilButton { background: #F4F4F5; border: 1px solid #E4E4E7; border-radius: 8px; padding: 5px 10px; color: #3F3F46; font-weight: 600; font-size: 11px; } "
                "QGroupBox { background: #FFFFFF; border: 1px solid #E4E4E7; border-radius: 12px; margin-top: 0px; padding: 36px 14px 12px 14px; } "
                "QGroupBox::title { subcontrol-origin: padding; subcontrol-position: top left; left: 12px; top: 9px; padding: 3px 10px; color: #1E40AF; background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 6px; font-weight: 800; font-size: 11px; } "
                "QLineEdit, QComboBox, QSpinBox, QTextEdit { background: #FFFFFF; border: 1px solid #D4D4D8; border-radius: 8px; padding: 5px 10px; min-height: 22px; color: #09090B; } "
                "QPushButton { background: #FFFFFF; border: 1px solid #D4D4D8; border-radius: 8px; padding: 6px 12px; color: #18181B; font-weight: 600; } "
                "QPushButton#primary { background: #2563EB; color: #FFFFFF; font-weight: 700; border: 1px solid #2563EB; border-radius: 10px; padding: 8px 20px; } "
                "QScrollBar:vertical { background: transparent; width: 6px; margin: 2px 1px; } "
                "QScrollBar::handle:vertical { background: #A1A1AA; min-height: 28px; border-radius: 3px; } "
                "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
            )
        return (
            "QWidget { color: #F4F4F5; font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif; font-size: 12px; } "
            "QMainWindow, QDialog, QScrollArea, QWidget#pageContent, QTabWidget::pane { background: #000000; } "
            "QLabel { background: transparent; color: #D4D4D8; padding: 1px 2px; } "
            "QToolBar { background: #030305; border-bottom: 1px solid #181820; spacing: 6px; padding: 6px 14px; } "
            "QLabel#brand { color: #FFFFFF; font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; font-size: 16px; font-weight: 900; padding-right: 4px; letter-spacing: 0.4px; } "
            "QFrame#navPillTrack { background: #09090E; border: 1px solid #1C1C26; border-radius: 10px; } "
            "QPushButton#navButton { background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 6px 13px; color: #A1A1AA; font-weight: 600; font-size: 12px; } "
            "QPushButton#navButton:hover { background: #14141E; border-color: #272736; color: #FAFAFA; } "
            "QPushButton#navButton:pressed { background: #1D4ED8; color: #FFFFFF; } "
            "QPushButton#navButton:checked { background: #2563EB; border: 1px solid #60A5FA; color: #FFFFFF; font-weight: 700; } "
            "QPushButton#navButton:disabled { color: #3F3F46; background: transparent; border-color: transparent; } "
            "QPushButton#navUtilButton { background: #09090E; border: 1px solid #1E1E2A; border-radius: 8px; padding: 5px 10px; color: #A1A1AA; font-weight: 600; font-size: 11px; } "
            "QPushButton#navUtilButton:hover { background: #14141F; border-color: #3B82F6; color: #FFFFFF; } "
            "QPushButton#navUtilButton:checked { background: #172554; border: 1px solid #3B82F6; color: #FFFFFF; font-weight: 700; } "
            "QGroupBox { background: #08080C; border: 1px solid #1A1A24; border-radius: 12px; margin-top: 0px; padding: 36px 12px 12px 12px; } "
            "QGroupBox::title { subcontrol-origin: padding; subcontrol-position: top left; left: 12px; top: 8px; padding: 3px 10px; color: #F4F4F5; background: #12121B; border: 1px solid #272736; border-radius: 6px; font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; font-size: 11px; font-weight: 800; } "
            "QLabel#title { color: #FAFAFA; font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; font-size: 22px; font-weight: 800; } "
            "QLabel#eyebrow { color: #60A5FA; font-size: 10px; font-weight: 800; letter-spacing: 0.8px; } "
            "QLabel#muted, QLabel#status { color: #A1A1AA; font-size: 12px; } "
            "QLineEdit, QComboBox, QSpinBox, QTextEdit { background: #0D0D14; border: 1px solid #222230; border-radius: 8px; padding: 4px 10px; min-height: 22px; color: #FAFAFA; font-weight: 500; } "
            "QComboBox { padding-right: 26px; } "
            "QSpinBox { padding-right: 56px; font-weight: 700; } "
            "QLineEdit:hover, QComboBox:hover, QSpinBox:hover { border-color: #3B82F6; background: #12121C; } "
            "QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1.5px solid #3B82F6; background: #12121C; } "
            "QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 24px; border: 0; background: transparent; } "
            "QComboBox::down-arrow { image: none; width: 0px; height: 0px; border: 0; } "
            "QComboBox QAbstractItemView { background: #0C0C14; border: 1px solid #272736; border-radius: 8px; color: #FAFAFA; selection-background-color: #2563EB; selection-color: #FFFFFF; padding: 4px; outline: 0; } "
            "QPushButton { background: #101018; border: 1px solid #242432; border-radius: 8px; padding: 6px 12px; color: #E4E4E7; font-weight: 600; } "
            "QPushButton:hover { background: #181824; border-color: #3B82F6; color: #FFFFFF; } "
            "QPushButton:pressed { background: #0A0A10; } "
            "QPushButton#secondary { background: #0E0E16; border: 1px solid #252534; border-radius: 8px; padding: 5px 11px; color: #E4E4E7; font-weight: 600; font-size: 11px; } "
            "QPushButton#secondary:hover { background: #181826; border-color: #3B82F6; color: #FFFFFF; } "
            "QPushButton#primary { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #1D4ED8); color: #FFFFFF; font-weight: 800; border: 1px solid #60A5FA; border-radius: 10px; padding: 8px 20px; } "
            "QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #2563EB); border-color: #93C5FD; } "
            "QPushButton#primary:pressed { background: #1E40AF; border-color: #60A5FA; } "
            "QPushButton:disabled { color: #52525B; background: #07070B; border-color: #16161F; } "
            "QCheckBox { spacing: 8px; padding: 2px 4px; color: #F4F4F5; font-weight: 500; } "
            "QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px; border: 1.5px solid #3F3F4E; background: #09090E; } "
            "QCheckBox::indicator:hover { border-color: #3B82F6; } "
            "QCheckBox::indicator:checked { background: #2563EB; border: 1.5px solid #60A5FA; } "
            "QSlider::groove:horizontal { height: 5px; background: #1E1E2A; border-radius: 2px; } "
            "QSlider::sub-page:horizontal { background: #3B82F6; border-radius: 2px; } "
            "QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; background: #FFFFFF; border: 2px solid #2563EB; border-radius: 7px; } "
            "QSlider::handle:horizontal:hover { background: #DBEAFE; border-color: #60A5FA; } "
            "QFrame#previewCanvas { background: #000000; border: 1px solid #242432; border-radius: 10px; } "
            "QSplitter::handle:horizontal { background: #14141E; width: 3px; margin: 6px 3px; border-radius: 1px; } "
            "QSplitter::handle:horizontal:hover { background: #3B82F6; } "
            "QMessageBox { background: #09090E; } "
            "QScrollBar:vertical { background: transparent; width: 6px; margin: 4px 1px; border-radius: 3px; } "
            "QScrollBar::handle:vertical { background: #272736; min-height: 28px; border-radius: 3px; } "
            "QScrollBar::handle:vertical:hover { background: #3B82F6; } "
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; } "
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; } "
            "QScrollBar:horizontal { background: transparent; height: 6px; margin: 1px 4px; border-radius: 3px; } "
            "QScrollBar::handle:horizontal { background: #272736; min-width: 28px; border-radius: 3px; } "
            "QScrollBar::handle:horizontal:hover { background: #3B82F6; } "
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; background: none; } "
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
        )

    def set_create_inputs_locked(self, locked: bool) -> None:
        if hasattr(self, "top_clip_mode_cards"):
            self.top_clip_mode_cards.setEnabled(not locked)
        if hasattr(self, "create_subtabs"):
            self.create_subtabs.setEnabled(not locked)
        if hasattr(self, "settings_group"):
            self.settings_group.setEnabled(not locked)
        if hasattr(self, "subtitle_group"):
            self.subtitle_group.setEnabled(not locked)
        if hasattr(self, "ai_group"):
            self.ai_group.setEnabled(not locked)
        if hasattr(self, "start_button"):
            self.start_button.setVisible(not locked)
            self.start_button.setEnabled(not locked)
        if hasattr(self, "cancel_button"):
            self.cancel_button.setVisible(locked)

    def cancel_current_process(self) -> None:
        if self.current_job_id:
            core.cancel_job(self.current_job_id)
        self.poll_timer.stop()
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            try:
                self.worker.terminate()
                self.worker.wait(500)
            except Exception:
                pass
        if self.current_job_id and hasattr(core, "reset_canceled_job"):
            core.reset_canceled_job(self.current_job_id)
        self.set_create_inputs_locked(False)
        self.set_progress_panel_visible(False)
        if hasattr(self, "review_export_progress_card"):
            self.review_export_progress_card.setVisible(False)
        self.render_button.setEnabled(True)
        if hasattr(self, "edit_text_button"):
            self.edit_text_button.setEnabled(True)
        if hasattr(self, "btn_back_review"):
            self.btn_back_review.setEnabled(True)
        self.add_manual_button.setEnabled(True)
        self.status_label.setText("Proses dibatalkan.")
        self.sub_status_label.setText("Pengaturan siap digunakan kembali.")
        self.progress.setValue(0)
        self.total_percent_label.setText("0%")
        self.sub_progress.setValue(0)
        self.sub_percent_label.setText("0%")
        self.log_terminal("Proses dibatalkan oleh pengguna. Studio siap digunakan kembali.")

    def cancel_to_edit_step2(self) -> None:
        self.cancel_current_process()
        self.switch_tab(2)

    def build_terminal_drawer(self) -> QWidget:
        drawer = QFrame()
        drawer.setObjectName("terminalDrawer")
        drawer.setMaximumHeight(170)
        drawer.setMinimumHeight(0)
        drawer.setStyleSheet("QFrame#terminalDrawer { background: #050508; border-top: 1px solid #1C1C26; }")
        layout = QVBoxLayout(drawer)
        layout.setContentsMargins(12, 6, 12, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Log & Aktivitas Sistem")
        lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #A1A1AA; background: transparent;")
        header.addWidget(lbl)
        header.addStretch()

        btn_clear = QPushButton("Bersihkan")
        btn_clear.setFixedHeight(22)
        btn_clear.setStyleSheet(
            "background: #12121A; border: 1px solid #242432; color: #D4D4D8; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: 600;"
        )
        btn_clear.clicked.connect(lambda: self.terminal_box.clear() if hasattr(self, "terminal_box") else None)
        header.addWidget(btn_clear)

        btn_close = QPushButton("Tutup")
        btn_close.setFixedHeight(22)
        btn_close.setStyleSheet(
            "background: #12121A; border: 1px solid #242432; color: #D4D4D8; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: 600;"
        )
        btn_close.clicked.connect(self.toggle_terminal_drawer)
        header.addWidget(btn_close)
        layout.addLayout(header)

        self.terminal_box = QPlainTextEdit()
        self.terminal_box.setReadOnly(True)
        self.terminal_box.setFont(QFont("Cascadia Mono", 10))
        self.terminal_box.setStyleSheet(
            "QPlainTextEdit { background: #000000; color: #60A5FA; border: 1px solid #1C1C26; "
            "border-radius: 6px; padding: 6px; font-family: 'Cascadia Mono', Consolas, monospace; }"
        )
        self.terminal_box.appendPlainText("[SISTEM] ENCLip Studio siap. Log aktivitas akan tampil di sini.")
        layout.addWidget(self.terminal_box, 1)
        return drawer

    def toggle_terminal_drawer(self) -> None:
        if not hasattr(self, "terminal_drawer"):
            return
        is_opening = not self.terminal_drawer.isVisible()
        if hasattr(self, "terminal_toggle_btn"):
            self.terminal_toggle_btn.setChecked(is_opening)

        if self._drawer_anim is not None and self._drawer_anim.state() == QAbstractAnimation.State.Running:
            self._drawer_anim.stop()

        target_height = 170
        if is_opening:
            self.terminal_drawer.setMaximumHeight(0)
            self.terminal_drawer.setVisible(True)
            anim = QPropertyAnimation(self.terminal_drawer, b"maximumHeight", self)
            anim.setDuration(200)
            anim.setStartValue(0)
            anim.setEndValue(target_height)
            anim.setEasingCurve(QEasingCurve.Type.OutQuart)
            self._drawer_anim = anim
            anim.start()
        else:
            current_h = self.terminal_drawer.height()
            anim = QPropertyAnimation(self.terminal_drawer, b"maximumHeight", self)
            anim.setDuration(170)
            anim.setStartValue(current_h)
            anim.setEndValue(0)
            anim.setEasingCurve(QEasingCurve.Type.OutQuart)
            def on_drawer_closed() -> None:
                self.terminal_drawer.setVisible(False)
                self.terminal_drawer.setMaximumHeight(target_height)
            anim.finished.connect(on_drawer_closed)
            self._drawer_anim = anim
            anim.start()

    def log_terminal(self, msg: str) -> None:
        if hasattr(self, "terminal_box"):
            import datetime
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.terminal_box.appendPlainText(f"[{ts}] {msg}")
            sb = self.terminal_box.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

    def _writable_models_dir(self) -> Path:
        cand = ROOT / "models"
        if core.is_path_writable(cand):
            return cand
        fallback = core.DATA_DIR / "models"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def build_models_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")

        page = QWidget()
        page.setObjectName("pageContent")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 24)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        eyebrow = QLabel("MANAJEMEN MODEL AI LOKAL")
        eyebrow.setObjectName("eyebrow")
        header_text.addWidget(eyebrow)

        title = QLabel("Katalog Model Offline")
        title.setObjectName("title")
        header_text.addWidget(title)

        subtitle = QLabel("Unduh model Whisper & GGUF agar proses transkripsi serta analisis berjalan penuh secara offline.")
        subtitle.setStyleSheet("color: #A1A1AA; font-size: 12px;")
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, 1)

        models_dir = self._writable_models_dir()

        btn_open_folder = QPushButton("Buka Folder Model")
        btn_open_folder.setObjectName("secondary")
        btn_open_folder.setFixedHeight(36)
        btn_open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(models_dir))))
        header_row.addWidget(btn_open_folder)
        layout.addLayout(header_row)

        self.model_cards: dict[str, dict[str, Any]] = {}

        for m in MODELS_CATALOG:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background: #09090E; border: 1px solid #1C1C26; border-radius: 12px; padding: 10px; } "
                "QFrame:hover { border-color: #3B82F6; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(6)

            top_row = QHBoxLayout()
            m_title = QLabel(m["name"])
            m_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #FAFAFA; border: 0;")
            top_row.addWidget(m_title)

            m_badge = QLabel(m["badge"])
            m_badge.setStyleSheet(
                "background: #14141F; color: #60A5FA; border: 1px solid #272736; border-radius: 5px; padding: 2px 8px; font-size: 10px; font-weight: 700;"
            )
            top_row.addWidget(m_badge)
            top_row.addStretch()

            status_lbl = QLabel("")
            status_lbl.setStyleSheet("font-size: 11px; font-weight: 700; border: 0;")
            top_row.addWidget(status_lbl)

            btn_dl = QPushButton("Unduh Model")
            btn_dl.setFixedHeight(32)
            btn_dl.setStyleSheet(
                "QPushButton { background: #2563EB; border: 1px solid #60A5FA; color: #FFFFFF; border-radius: 7px; padding: 0 14px; font-weight: 700; font-size: 11px; } "
                "QPushButton:hover { background: #1D4ED8; } QPushButton:disabled { background: #14141D; color: #52525B; border-color: #222230; }"
            )
            top_row.addWidget(btn_dl)
            card_layout.addLayout(top_row)

            m_desc = QLabel(m["desc"])
            m_desc.setStyleSheet("color: #A1A1AA; font-size: 12px; border: 0;")
            card_layout.addWidget(m_desc)

            m_specs = QLabel(m["specs"])
            m_specs.setStyleSheet("color: #FBBF24; font-size: 11px; font-weight: 600; border: 0;")
            card_layout.addWidget(m_specs)

            prog_row = QHBoxLayout()
            prog_bar = QProgressBar()
            prog_bar.setRange(0, 100)
            prog_bar.setValue(0)
            prog_bar.setFixedHeight(6)
            prog_bar.setTextVisible(False)
            prog_bar.setStyleSheet(
                "QProgressBar { background: #181822; border-radius: 3px; border: 0; } "
                "QProgressBar::chunk { background: #3B82F6; border-radius: 3px; }"
            )
            prog_bar.setVisible(False)
            prog_row.addWidget(prog_bar, 1)

            prog_info = QLabel("")
            prog_info.setStyleSheet("color: #A1A1AA; font-size: 11px; border: 0;")
            prog_info.setVisible(False)
            prog_row.addWidget(prog_info)
            card_layout.addLayout(prog_row)

            is_installed = False
            if m["type"] == "gguf":
                for check_dir in (models_dir, ROOT / "models"):
                    target_p = check_dir / m["filename"]
                    if target_p.exists() and target_p.stat().st_size > 1024 * 1024:
                        is_installed = True
                        break
            elif m["type"] == "whisper":
                try:
                    import huggingface_hub
                    cached = (
                        list(Path(huggingface_hub.constants.HF_HUB_CACHE).glob(f"*{m['url']}*"))
                        if Path(huggingface_hub.constants.HF_HUB_CACHE).exists()
                        else []
                    )
                    is_installed = bool(cached)
                except Exception:
                    is_installed = False

            if is_installed:
                status_lbl.setText("Terpasang")
                status_lbl.setStyleSheet("color: #10B981; font-weight: 700; font-size: 11px; border: 0;")
                btn_dl.setText("Pasang Ulang")
                btn_dl.setStyleSheet(
                    "background: #12121A; color: #A1A1AA; border: 1px solid #272736; border-radius: 7px; padding: 0 12px; font-size: 11px;"
                )

            btn_dl.clicked.connect(lambda checked=False, info=m: self.start_model_download(info))

            self.model_cards[m["id"]] = {
                "info": m,
                "status_lbl": status_lbl,
                "btn_dl": btn_dl,
                "prog_bar": prog_bar,
                "prog_info": prog_info,
            }
            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def start_model_download(self, info: dict) -> None:
        m_id = info["id"]
        card = self.model_cards.get(m_id)
        if not card:
            return

        target_file = self._writable_models_dir() / info["filename"]
        worker = ModelDownloadWorker(m_id, info["type"], info["url"], target_file)
        worker.progress_signal.connect(self.on_model_download_progress)
        worker.finished_signal.connect(self.on_model_download_finished)

        self.model_download_workers[m_id] = worker
        card["btn_dl"].setEnabled(False)
        card["btn_dl"].setText("Mengunduh...")
        card["status_lbl"].setText("Mengunduh...")
        card["status_lbl"].setStyleSheet("color: #60A5FA; font-weight: 600; font-size: 11px; border: 0;")
        card["prog_bar"].setVisible(True)
        card["prog_bar"].setValue(0)
        card["prog_info"].setVisible(True)
        card["prog_info"].setText("Menghubungkan...")

        self.log_terminal(f"Memulai unduhan model: {info['name']}...")
        worker.start()

    def on_model_download_progress(self, model_id: str, pct: int, size_str: str, speed_str: str) -> None:
        card = self.model_cards.get(model_id)
        if not card:
            return
        card["prog_bar"].setValue(pct)
        card["prog_info"].setText(f"{pct}% · {size_str} ({speed_str})")

    def on_model_download_finished(self, model_id: str, success: bool, msg: str) -> None:
        card = self.model_cards.get(model_id)
        if not card:
            return
        card["prog_bar"].setVisible(False)
        card["prog_info"].setVisible(False)
        card["btn_dl"].setEnabled(True)

        if success:
            card["status_lbl"].setText("Terpasang")
            card["status_lbl"].setStyleSheet("color: #10B981; font-weight: 700; font-size: 11px; border: 0;")
            card["btn_dl"].setText("Pasang Ulang")
            card["btn_dl"].setStyleSheet(
                "background: #12121A; color: #A1A1AA; border: 1px solid #272736; border-radius: 7px; padding: 0 12px; font-size: 11px;"
            )
            self.log_terminal(f"Model {card['info']['name']} berhasil diunduh dan siap digunakan.")
            self.scan_project_models()
            QMessageBox.information(
                self, "Model Terpasang", f"Model {card['info']['name']} berhasil diunduh dan siap digunakan."
            )
        else:
            card["status_lbl"].setText("Gagal")
            card["status_lbl"].setStyleSheet("color: #EF4444; font-weight: 700; font-size: 11px; border: 0;")
            card["btn_dl"].setText("Coba Lagi")
            card["btn_dl"].setStyleSheet(
                "background: #2563EB; color: #FFFFFF; border-radius: 7px; padding: 0 14px; font-weight: 700; font-size: 11px;"
            )
            self.log_terminal(f"Unduhan model {card['info']['name']} gagal: {msg}")
            QMessageBox.warning(self, "Unduhan Gagal", f"Gagal mengunduh model: {msg}")

        self.model_download_workers.pop(model_id, None)


def main() -> int:
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("enclip.video.clipper.app")
    except Exception:
        pass
    application = QApplication(sys.argv)
    application.setApplicationName("ENCLip")
    app_font = QFont("Segoe UI Variable Text", 10)
    app_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    application.setFont(app_font)
    icon = get_app_icon()
    if icon:
        application.setWindowIcon(icon)
    window = HermesDesktop()
    if icon:
        window.setWindowIcon(icon)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
