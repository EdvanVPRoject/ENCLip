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
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSettings, QPoint, QPointF, QRect, QRectF, QSize, QThread, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QFont, QIcon, QImage, QPainter, QPen, QPixmap, QPolygon
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink

def get_app_icon() -> QIcon | None:
    for base in [Path(__file__).parent, Path(sys.executable).parent, Path(getattr(sys, "_MEIPASS", ""))]:
        for name in ("icon.ico", "icon.png"):
            candidate = base / name
            if candidate.is_file():
                return QIcon(str(candidate))
    return None
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
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = (Path(__file__).parent.parent / "Core_Data").resolve()

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
    elif icon_type == "zoom":
        painter.drawEllipse(5, 5, 10, 10)
        painter.drawLine(13, 13, 19, 19)

    painter.end()
    return QIcon(pix)


class ToggleSwitch(QCheckBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        checked = self.isChecked()
        track_color = QColor("#2563EB") if checked else QColor("#334155")
        p.setBrush(track_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 12, 12)
        thumb_x = rect.width() - 21 if checked else 3
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(thumb_x, 3, 18, 18)


class DropZoneWidget(QFrame):
    fileDropped = pyqtSignal(str)
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("dropZone")
        self.setMinimumHeight(220)
        self.is_drag_over = False

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        icon_box = QLabel("⬆")
        icon_box.setStyleSheet("font-size: 36px; color: #3B82F6; background: transparent; font-weight: bold;")
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_box)

        self.text_label = QLabel("Drag & drop video Anda di sini atau cari berkas lokal")
        self.text_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #F1F5F9; background: transparent;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)

        self.sub_label = QLabel("Mendukung MP4, MOV, AVI, dll.")
        self.sub_label.setStyleSheet("font-size: 12px; color: #64748B; background: transparent;")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sub_label)

        self.update_style()

    def update_style(self) -> None:
        border_color = "#3B82F6" if self.is_drag_over else "#334155"
        bg_color = "#151F32" if self.is_drag_over else "#0D121C"
        self.setStyleSheet(f"""
            QFrame#dropZone {{
                background-color: {bg_color};
                border: 2px dashed {border_color};
                border-radius: 12px;
            }}
            QFrame#dropZone:hover {{
                border-color: #3B82F6;
                background-color: #111724;
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
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        p.setBrush(QColor("#0F1420"))
        p.setPen(QPen(QColor("#1E293B"), 1))
        p.drawRoundedRect(0, 3, w, h - 6, 4, 4)

        bar_count = max(10, w // 4)
        p.setPen(Qt.PenStyle.NoPen)
        import math
        span = max(1, self.maximum() - self.minimum())
        val_ratio = (self.value() - self.minimum()) / span if self.maximum() > self.minimum() else 0.0
        active_x = int(w * val_ratio)

        for i in range(bar_count):
            bx = i * 4 + 2
            amp = math.sin(i * 0.28) * math.cos(i * 0.14) * 0.7 + 0.3
            bh = max(3, int((h - 14) * abs(amp)))
            by = (h - bh) // 2
            if bx <= active_x:
                p.setBrush(QColor("#38BDF8" if bx % 8 == 0 else "#2563EB"))
            else:
                p.setBrush(QColor("#334155"))
            p.drawRoundedRect(bx, by, 2, bh, 1, 1)

        p.setBrush(QColor("#06B6D4"))
        p.drawRoundedRect(2, 3, 4, h - 6, 2, 2)
        p.drawRoundedRect(w - 6, 3, 4, h - 6, 2, 2)

        if self.maximum() > self.minimum():
            hx = min(w - 6, max(4, active_x))
            p.setBrush(QColor("#3B82F6"))
            p.drawRoundedRect(hx - 2, 2, 4, h - 4, 2, 2)
            poly = QPolygon([
                QPoint(hx - 5, 2),
                QPoint(hx + 5, 2),
                QPoint(hx, 7)
            ])
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

        # Video track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#131926"))
        p.drawRoundedRect(track_left, 26, track_w, 32, 4, 4)
        slice_w = 40
        num_slices = max(1, track_w // slice_w)
        p.setPen(QPen(QColor("#1E293B"), 1))
        for i in range(num_slices):
            p.drawLine(track_left + i * slice_w, 26, track_left + i * slice_w, 58)

        # Audio track
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

        # Subtitle track
        p.setBrush(QColor("#131926"))
        p.drawRoundedRect(track_left, 106, track_w, 28, 4, 4)
        p.setBrush(QColor("#1E293B"))
        chunk_count = 6
        for c in range(chunk_count):
            cx = track_left + int((c / chunk_count) * track_w) + 6
            cw = max(10, int(track_w / (chunk_count + 1)) - 10)
            p.drawRoundedRect(cx, 110, cw, 20, 3, 3)

        # Active clip range
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

        # Playhead
        if self.total_duration_ms > 0:
            pos_ratio = self.current_position_ms / self.total_duration_ms
            hx = track_left + int(pos_ratio * track_w)
            hx = min(track_right, max(track_left, hx))
            p.setPen(QPen(QColor("#3B82F6"), 2))
            p.drawLine(hx, 18, hx, 140)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#3B82F6"))
            poly = QPolygon([
                QPoint(hx - 5, 12),
                QPoint(hx + 5, 12),
                QPoint(hx, 20)
            ])
            p.drawPolygon(poly)


class EditTextDialog(QDialog):
    def __init__(self, title: str, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sunting Teks Klip")
        self.resize(480, 280)
        self.setStyleSheet("background: #0F1420; color: #F1F5F9;")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Judul Klip:"))
        self.title_edit = QLineEdit(title)
        self.title_edit.setMinimumHeight(36)
        layout.addWidget(self.title_edit)
        layout.addWidget(QLabel("Teks / Subtitle:"))
        self.caption_edit = QTextEdit()
        self.caption_edit.setPlainText(caption)
        layout.addWidget(self.caption_edit)
        btns = QHBoxLayout()
        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Simpan")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def get_data(self) -> tuple[str, str]:
        return self.title_edit.text().strip(), self.caption_edit.toPlainText().strip()


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
        end_val = format_time(min(max_dur_sec, current_pos_sec + 30.0))
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
            pix = orig.scaled(240, 135, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
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
        self.thumb_label.setStyleSheet("border-radius: 8px; background: #0F1420;")

        pix = make_decorated_thumbnail(entry_data.get("thumb_path"), float(entry_data.get("duration", 0.0)))
        self.thumb_label.setPixmap(pix)
        layout.addWidget(self.thumb_label)
        self.update_style()

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected
        self.update_style()

    def update_style(self) -> None:
        border = "#3B82F6" if self.is_selected else "#233148"
        bg = "#162030" if self.is_selected else "#111724"
        self.setStyleSheet(f"""
            QFrame#videoCard {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 10px;
            }}
            QFrame#videoCard:hover {{
                border-color: #3B82F6;
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

        # Thumbnail (105x68)
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(105, 68)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setStyleSheet("border-radius: 6px; background: #0B0E14;")

        start_sec = float(clip_data.get("start", 0.0))
        end_sec = float(clip_data.get("end", 0.0))
        dur_sec = max(0.0, end_sec - start_sec)

        thumb_path = get_video_thumbnail_path(source_path, start_sec) if source_path else None
        pix = make_decorated_thumbnail(thumb_path, dur_sec)
        self.thumb_label.setPixmap(pix)
        layout.addWidget(self.thumb_label)

        # Middle Info
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 2, 0, 2)
        info_col.setSpacing(3)

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title_text = f"{index + 1:02d} · {clip_data.get('title', 'Klip Video')}"
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet("font-weight: 700; font-size: 13px; color: #FFFFFF; background: transparent;")
        title_row.addWidget(title_lbl, 1)

        source = clip_data.get("source", "ai")
        source_badge = QLabel("AI" if source == "ai" else "MANUAL")
        if source == "ai":
            source_badge.setStyleSheet("font-size: 10px; font-weight: 700; color: #38BDF8; background: #0C2138; border: 1px solid #1D4ED8; border-radius: 4px; padding: 1px 6px;")
        else:
            source_badge.setStyleSheet("font-size: 10px; font-weight: 700; color: #F59E0B; background: #2E1F0C; border: 1px solid #B45309; border-radius: 4px; padding: 1px 6px;")
        title_row.addWidget(source_badge)
        info_col.addLayout(title_row)

        # Time range badge
        time_text = f"⏱ {format_time(start_sec)} – {format_time(end_sec)} ({int(dur_sec)}s)"
        time_lbl = QLabel(time_text)
        time_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #60A5FA; background: transparent;")
        info_col.addWidget(time_lbl)

        # Subtitle caption snippet
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
                    background: #1C283C;
                    border: 2px solid #3B82F6;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#reviewClipCard {
                    background: #131926;
                    border: 1px solid #233148;
                    border-radius: 8px;
                }
                QFrame#reviewClipCard:hover {
                    border-color: #3B82F6;
                    background: #162030;
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
                background: #131926;
                border: 1px solid #233148;
                border-radius: 10px;
            }
            QFrame#resultCard:hover {
                border-color: #3B82F6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 1. Decorated Thumbnail
        start_sec = float(clip_data.get("start", 0.0))
        end_sec = float(clip_data.get("end", 0.0))
        dur_sec = max(0.0, end_sec - start_sec)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedHeight(125)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setStyleSheet("border-radius: 8px; background: #0B0E14;")

        thumb_file = get_video_thumbnail_path(str(clip_path), 0.5) if clip_path.is_file() else None
        pix = make_decorated_thumbnail(thumb_file, dur_sec)
        self.thumb_label.setPixmap(pix)
        layout.addWidget(self.thumb_label)

        # 2. Clip Title
        title_text = f"{index + 1:02d} · {clip_data.get('title', 'Klip Video')}"
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #FFFFFF; background: transparent;")
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        # 3. Format & Size Info
        size_str = ""
        if clip_path.is_file():
            size_mb = clip_path.stat().st_size / (1024 * 1024)
            size_str = f" · {size_mb:.1f} MB"

        fmt_lbl = QLabel(f"Format: MP4 | 1080p{size_str}")
        fmt_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; background: transparent;")
        layout.addWidget(fmt_lbl)

        # 4. Status Badge row
        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        success_badge = QLabel("✓ Berhasil")
        success_badge.setStyleSheet("font-size: 11px; font-weight: 700; color: #38BDF8; background: #0C2138; border: 1px solid #1D4ED8; border-radius: 4px; padding: 2px 8px;")
        status_row.addWidget(success_badge)
        status_row.addStretch()
        layout.addLayout(status_row)

        # 5. Action Buttons row
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        play_btn = QPushButton("▶ Putar")
        play_btn.setMinimumHeight(32)
        play_btn.setStyleSheet("""
            QPushButton {
                background: #182234;
                border: 1px solid #2C3C56;
                border-radius: 6px;
                color: #60A5FA;
                font-weight: 600;
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

        folder_btn = QPushButton("📁")
        folder_btn.setFixedSize(36, 32)
        folder_btn.setToolTip("Buka folder berkas ini")
        folder_btn.setStyleSheet("""
            QPushButton {
                background: #182234;
                border: 1px solid #2C3C56;
                border-radius: 6px;
                color: #94A3B8;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #202D44;
                color: #FFFFFF;
            }
        """)
        folder_btn.clicked.connect(self.open_folder)
        action_row.addWidget(folder_btn)

        layout.addLayout(action_row)

    def play_clip(self) -> None:
        if self.clip_path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.clip_path)))

    def open_folder(self) -> None:
        folder = self.clip_path.parent if self.clip_path.is_file() else self.clip_path
        if folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


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
    """Never change selection on mouse wheel scroll; always pass wheel events to parent scroll area."""

    def wheelEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        event.ignore()


class FocusOnlySpinBox(QSpinBox):
    """Never change values on mouse wheel scroll; always pass wheel events to parent scroll area."""

    def wheelEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        event.ignore()


class VideoSurfaceWidget(QWidget):
    """Native QWidget video renderer using QVideoSink to prevent DirectX HWND overlay punch-through."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sink = QVideoSink(self)
        self.current_frame: QImage | None = None
        self.sink.videoFrameChanged.connect(self.on_frame_changed)
        self.aspect_ratio_mode = Qt.AspectRatioMode.KeepAspectRatio

    def setAspectRatioMode(self, mode: Qt.AspectRatioMode) -> None:
        self.aspect_ratio_mode = mode
        self.update()

    def on_frame_changed(self, frame: QVideoFrame) -> None:
        if frame.isValid():
            self.current_frame = frame.toImage()
            self.update()

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#05070B"))
        if self.current_frame and not self.current_frame.isNull():
            target_size = self.size()
            scaled = self.current_frame.scaled(
                target_size,
                self.aspect_ratio_mode,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawImage(x, y, scaled)


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


MODELS_CATALOG = [
    {
        "id": "qwen_0.5b",
        "name": "Qwen 2.5 0.5B Instruct",
        "badge": "GGUF Q4_K_M · ~397 MB",
        "type": "gguf",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "specs": "⚡ Rekomendasi: RAM 4 GB+ | CPU Dual-Core / Laptop Standar",
        "desc": "Model analisis super hemat daya, sangat cepat untuk deteksi momen menarik tanpa memberatkan laptop.",
    },
    {
        "id": "qwen_1.5b",
        "name": "Qwen 2.5 1.5B Instruct",
        "badge": "GGUF Q4_K_M · ~1.1 GB",
        "type": "gguf",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "specs": "⚡ Rekomendasi: RAM 8 GB+ | CPU 4-Core atau GPU 2-4 GB VRAM",
        "desc": "Keseimbangan ideal antara kecepatan rendering dan kecerdasan kontekstual memahami isi percakapan video.",
    },
    {
        "id": "qwen_7b",
        "name": "Qwen 2.5 7B Instruct",
        "badge": "GGUF Q4_K_M · ~4.7 GB",
        "type": "gguf",
        "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf",
        "specs": "⚡ Rekomendasi: RAM 16 GB+ | GPU RTX 6-8 GB+ VRAM",
        "desc": "Kualitas setara AI Cloud, penalaran mendalam, deteksi hook & punchline video yang sangat tajam.",
    },
    {
        "id": "whisper_small",
        "name": "Faster-Whisper Small",
        "badge": "CTranslate2 · ~460 MB",
        "type": "whisper",
        "filename": "faster-whisper-small",
        "url": "small",
        "specs": "⚡ Rekomendasi: RAM 4 GB+ | CPU 4-Core atau GPU 2 GB VRAM",
        "desc": "Speech-to-text akurat dan cepat untuk audio percakapan Bahasa Indonesia & Inggris sehari-hari.",
    },
    {
        "id": "whisper_medium",
        "name": "Faster-Whisper Medium",
        "badge": "CTranslate2 · ~1.5 GB",
        "type": "whisper",
        "filename": "faster-whisper-medium",
        "url": "medium",
        "specs": "⚡ Rekomendasi: RAM 8 GB+ | GPU 4 GB+ VRAM",
        "desc": "Presisi tinggi untuk transkripsi audio dengan musik latar belakang atau vokal bising.",
    },
]


class ModelDownloadWorker(QThread):
    progress_signal = pyqtSignal(str, int, str, str)  # model_id, pct, size_str, speed_str
    finished_signal = pyqtSignal(str, bool, str)       # model_id, success, message

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

            import urllib.request
            import time

            tmp_file = self.target_file.with_suffix(".tmp")
            self.target_file.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(
                self.url_or_name,
                headers={"User-Agent": "Mozilla/5.0 ENCLip Downloader"}
            )
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
                        spd_str = f"{speed / (1024*1024):.1f} MB/s" if speed >= 1024*1024 else f"{speed / 1024:.0f} KB/s"
                        sz_str = f"{downloaded / (1024*1024):.1f} MB / {total_len / (1024*1024):.1f} MB" if total_len else f"{downloaded / (1024*1024):.1f} MB"
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
        import subprocess
        python_exe = sys.executable
        self.output_line.emit("=== MEMULAI SETUP ENVIRONMENT & INSTALASI DEPENDENSI ===")
        self.output_line.emit(f"Python: {python_exe}")

        for p in [Path("Core_Data/models"), Path("Core_Data/VideoMentah"), Path("Core_Data/HasilClip")]:
            p.mkdir(parents=True, exist_ok=True)
            self.output_line.emit(f"Direktori kerja siap: {p}")

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
        self.setWindowTitle("ENCLip - Video AI Clipper")
        icon = get_app_icon()
        if icon:
            self.setWindowIcon(icon)
        self.resize(1240, 760)
        self.setMinimumSize(960, 560)
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
        self.setup_tab = self.build_setup_tab()
        self.video_tab = self.build_video_tab()
        self.create_tab = self.build_create_tab()
        self.review_tab = self.build_review_tab()
        self.results_tab = self.build_results_tab()
        self.models_tab = self.build_models_tab()
        self.tutorial_tab = self.build_tutorial_tab()
        self.tabs.addTab(self.setup_tab, "Setup")
        self.tabs.addTab(self.video_tab, "Video")
        self.tabs.addTab(self.create_tab, "Buat clip")
        self.tabs.addTab(self.review_tab, "Review & manual")
        self.tabs.addTab(self.results_tab, "Hasil")
        self.tabs.addTab(self.models_tab, "Model AI Lokal")
        self.tabs.addTab(self.tutorial_tab, "Informasi & Panduan")
        self.tabs.setTabEnabled(3, False)
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

        # Left brand group
        brand_widget = QWidget()
        brand_layout = QHBoxLayout(brand_widget)
        brand_layout.setContentsMargins(4, 0, 8, 0)
        brand_layout.setSpacing(8)

        app_icon = get_app_icon()
        if app_icon:
            brand_icon_lbl = QLabel()
            brand_icon_lbl.setPixmap(app_icon.pixmap(22, 22))
            brand_icon_lbl.setStyleSheet("background: transparent;")
            brand_layout.addWidget(brand_icon_lbl)

        brand = QLabel("<span style='color:#FFFFFF; font-weight:800; font-size:17px; letter-spacing:-0.2px;'>ENC</span><span style='color:#3B82F6; font-weight:800; font-size:17px; letter-spacing:-0.2px;'>Lip</span>")
        brand.setObjectName("brand")
        brand_layout.addWidget(brand)

        meta = QLabel("Local video workspace")
        meta.setObjectName("brandMeta")
        meta.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 500; background: transparent; padding-left: 6px;")
        brand_layout.addWidget(meta)
        toolbar.addWidget(brand_widget)

        # Spacer left to center tabs
        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_left)

        # Center nav tabs
        nav_container = QWidget()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)
        for index, label in ((0, "Setup"), (1, "Video"), (2, "Buat clip"), (3, "Review"), (4, "Hasil"), (5, "Model AI Lokal")):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, target=index: self.switch_tab(target))
            self.nav_buttons[index] = button
            nav_layout.addWidget(button)
        toolbar.addWidget(nav_container)

        # Spacer right
        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_right)

        # Right tools: Cara kerja, Terminal & Theme toggle
        right_tools = QWidget()
        right_layout = QHBoxLayout(right_tools)
        right_layout.setContentsMargins(0, 0, 4, 0)
        right_layout.setSpacing(8)

        self.terminal_toggle_btn = QPushButton("⌨ Terminal")
        self.terminal_toggle_btn.setObjectName("navButton")
        self.terminal_toggle_btn.setCheckable(True)
        self.terminal_toggle_btn.setToolTip("Buka / Tutup Terminal Log Konsol")
        self.terminal_toggle_btn.clicked.connect(self.toggle_terminal_drawer)
        right_layout.addWidget(self.terminal_toggle_btn)

        guide_button = QPushButton("Informasi & Panduan")
        guide_button.setObjectName("navButton")
        guide_button.setToolTip("Buka Pusat Informasi, Panduan Lengkap & Dokumentasi")
        guide_button.setCheckable(True)
        guide_button.clicked.connect(lambda checked=False: self.switch_tab(6))
        self.nav_buttons[6] = guide_button
        right_layout.addWidget(guide_button)

        self.theme_label = QLabel("Tema: Gelap")
        self.theme_label.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500; background: transparent;")
        right_layout.addWidget(self.theme_label)

        self.theme_toggle = ToggleSwitch()
        self.theme_toggle.setChecked(True)
        self.theme_toggle.toggled.connect(self.toggle_theme)
        right_layout.addWidget(self.theme_toggle)

        self.theme_button = QPushButton()
        self.theme_button.setVisible(False)

        toolbar.addWidget(right_tools)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_job)
        saved_theme = QSettings("VanClipper", "VanClipper").value("theme", "dark")
        self.apply_theme(str(saved_theme) == "light")
        self.switch_tab(0)

    def check_system_environment(self) -> list[dict[str, Any]]:
        items = []

        # 1. Python Runtime
        is_frozen = getattr(sys, "frozen", False)
        py_type = "Portable Standalone EXE" if is_frozen else "Virtual Environment (Python)"
        py_ver = platform.python_version()
        items.append({
            "key": "python",
            "name": "Python Runtime & Interpreter",
            "status": "OK",
            "is_ok": True,
            "badge": "✓ TERPASANG & SIAP",
            "color": "#10B981",
            "details": f"{py_type} v{py_ver} — Executable: {sys.executable}",
            "desc": "Inti runtime untuk mengeksekusi logika backend, AI orchestration, dan antarmuka desktop.",
        })

        # 2. FFmpeg & FFprobe
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
            "badge": "✓ TERPASANG & SIAP" if ffmpeg_ok else "⚠ BELUM TERDETEKSI",
            "color": "#10B981" if ffmpeg_ok else "#EF4444",
            "details": f"{ffmpeg_ver_str} — {ffmpeg_bin or 'Tidak ditemukan di PATH'}",
            "desc": "FFmpeg diperlukan untuk decoding video, pemotongan klip 9:16 / 16:9, dan penempelan subtitle.",
        })

        # 3. Faster-Whisper
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
            "badge": "✓ TERPASANG & SIAP" if fw_ok else "⚠ BELUM TERPASANG",
            "color": "#10B981" if fw_ok else "#F59E0B",
            "details": f"Faster-Whisper {fw_ver} (CTranslate2 Engine)",
            "desc": "Modul AI transkripsi suara ke teks dengan timestamp kata-per-kata presisi tinggi.",
        })

        # 4. yt-dlp
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
            "badge": "✓ TERPASANG & SIAP" if yt_ok else "⚠ BELUM TERPASANG",
            "color": "#10B981" if yt_ok else "#F59E0B",
            "details": f"yt-dlp {yt_ver}",
            "desc": "Modul pengunduh video YouTube, Shorts, dan platform online dengan pemilihan resolusi otomatis.",
        })

        # 5. AI Reasoning Engine (Gemini / GGUF)
        gemini_key = QSettings("VanClipper", "VanClipper").value("gemini_api_key", "")
        if not gemini_key:
            gemini_key = os.environ.get("GEMINI_API_KEY", "")
        models_dir = Path("Core_Data/models")
        if not models_dir.exists():
            models_dir = ROOT / "models"
        gguf_files = list(models_dir.glob("*.gguf")) if models_dir.exists() else []

        if gemini_key:
            ai_status_text = "Google Gemini Pro Cloud Terkonfigurasi (Kunci API aktif)"
            ai_badge = "✓ GEMINI CLOUD SIAP"
            ai_color = "#10B981"
        elif gguf_files:
            ai_status_text = f"Model AI Lokal Terdeteksi ({len(gguf_files)} model GGUF di folder models)"
            ai_badge = "✓ MODEL LOKAL SIAP"
            ai_color = "#10B981"
        else:
            ai_status_text = "Tersedia Rule-Based Fallback (Kunci Gemini / Model Lokal dapat diset di tab Buat clip)"
            ai_badge = "ℹ READY (FALLBACK MODE)"
            ai_color = "#3B82F6"

        items.append({
            "key": "ai_engine",
            "name": "AI Intelligence & Clip Reasoning",
            "status": "OK",
            "is_ok": True,
            "badge": ai_badge,
            "color": ai_color,
            "details": ai_status_text,
            "desc": "Menilai relevansi momen video, menyusun judul catchy, caption viral, dan hashtag.",
        })

        # 6. Direktori Kerja
        dir_ok = True
        dirs_created = []
        for d in [Path("Core_Data/VideoMentah"), Path("Core_Data/HasilClip"), Path("Core_Data/models")]:
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
            "badge": "✓ FOLDER KERJA SIAP" if dir_ok else "⚠ GAGAL MEMBUAT",
            "color": "#10B981" if dir_ok else "#EF4444",
            "details": f"Folder kerja aktif: {', '.join(dirs_created)} (di Core_Data/)",
            "desc": "Penyimpanan video mentah yang diunduh, model AI lokal offline, dan hasil render klip.",
        })

        return items

    def create_setup_card(self, item: dict[str, Any]) -> QFrame:
        card = QFrame()
        card.setObjectName("setupCard")
        is_dark = getattr(self, "current_theme", "dark") == "dark"
        bg = "#111827" if is_dark else "#ffffff"
        border = "#1f2937" if is_dark else "#e2e8f0"
        text_color = "#f8fafc" if is_dark else "#0f172a"
        subtext = "#94a3b8" if is_dark else "#64748b"

        card.setStyleSheet(f"""
            QFrame#setupCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 12px 16px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(6)

        # Top row: Title + Badge
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(item["name"])
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {text_color}; background: transparent;")
        top_row.addWidget(title_lbl, 1)

        badge_lbl = QLabel(item["badge"])
        badge_lbl.setStyleSheet(f"""
            background: {item['color']};
            color: #ffffff;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 10px;
        """)
        top_row.addWidget(badge_lbl, 0)
        c_layout.addLayout(top_row)

        # Middle row: Details
        detail_lbl = QLabel(item["details"])
        detail_lbl.setWordWrap(True)
        detail_lbl.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {subtext}; font-family: 'Consolas', 'Segoe UI', monospace; background: transparent;")
        c_layout.addWidget(detail_lbl)

        # Bottom row: Description
        desc_lbl = QLabel(item["desc"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"font-size: 11px; color: {'#64748b' if is_dark else '#94a3b8'}; background: transparent;")
        c_layout.addWidget(desc_lbl)

        card.item_key = item["key"]
        card.title_lbl = title_lbl
        card.badge_lbl = badge_lbl
        card.detail_lbl = detail_lbl
        card.desc_lbl = desc_lbl
        return card

    def refresh_setup_status(self) -> None:
        items = self.check_system_environment()
        item_map = {it["key"]: it for it in items}

        all_ok = True
        for card in getattr(self, "setup_cards", []):
            k = getattr(card, "item_key", None)
            if k and k in item_map:
                it = item_map[k]
                card.badge_lbl.setText(it["badge"])
                card.badge_lbl.setStyleSheet(f"""
                    background: {it['color']};
                    color: #ffffff;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 3px 10px;
                    border-radius: 10px;
                """)
                card.detail_lbl.setText(it["details"])
                if not it.get("is_ok", True):
                    all_ok = False

        if hasattr(self, "setup_summary_lbl"):
            if all_ok:
                self.setup_summary_lbl.setText("🎉 Semua komponen sistem & dependensi telah terverifikasi dan siap digunakan!")
                self.setup_summary_lbl.setStyleSheet("color: #10B981; font-size: 13px; font-weight: 600;")
            else:
                self.setup_summary_lbl.setText("Perhatian: Beberapa dependensi belum lengkap atau belum terdeteksi. Silakan klik tombol 'Pasang / Update Dependensi'.")
                self.setup_summary_lbl.setStyleSheet("color: #F59E0B; font-size: 13px; font-weight: 600;")

    def install_dependencies_in_background(self) -> None:
        if hasattr(self, "dep_worker") and self.dep_worker is not None and self.dep_worker.isRunning():
            QMessageBox.information(self, "Instalasi Berjalan", "Proses instalasi dependensi sedang berjalan di latar belakang.")
            return

        if not self.terminal_drawer.isVisible():
            self.toggle_terminal_drawer()

        self.log_terminal("Memulai instalasi dependensi di background...")
        if hasattr(self, "btn_setup_install"):
            self.btn_setup_install.setEnabled(False)
            self.btn_setup_install.setText("⏳ Sedang Memasang...")

        self.dep_worker = DependencyInstallWorker()
        self.dep_worker.output_line.connect(self.log_terminal)
        self.dep_worker.finished.connect(self.on_dep_install_finished)
        self.dep_worker.start()

    def on_dep_install_finished(self, success: bool, msg: str) -> None:
        if hasattr(self, "btn_setup_install"):
            self.btn_setup_install.setEnabled(True)
            self.btn_setup_install.setText("⚡ Pasang / Update Dependensi Otomatis")

        self.refresh_setup_status()
        if success:
            self.log_terminal(f"SUCCESS: {msg}")
            QMessageBox.information(self, "Setup Selesai", f"Setup environment berhasil:\n{msg}")
        else:
            self.log_terminal(f"FAILED: {msg}")
            QMessageBox.warning(self, "Setup Dependensi", f"Instalasi selesai dengan catatan:\n{msg}")

    def build_setup_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        page = QWidget()
        page.setObjectName("pageContent")
        page.setMinimumWidth(860)
        page.setMaximumWidth(1100)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        # Header section
        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)

        eyebrow = QLabel("TAHAP 01: SETUP ENVIRONMENT & DEPENDENSI")
        eyebrow.setObjectName("eyebrow")
        header_text.addWidget(eyebrow)

        title = QLabel("Pemeriksaan Lingkungan Sistem & AI")
        title.setObjectName("title")
        header_text.addWidget(title)

        subtitle = QLabel("Verifikasi kesiapan Python, FFmpeg, Whisper, yt-dlp, dan folder kerja sebelum memulai klip.")
        subtitle.setStyleSheet("color: #94A3B8; font-size: 13px;")
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, 1)

        # Top action buttons
        top_btn_row = QHBoxLayout()
        top_btn_row.setSpacing(10)

        btn_refresh_top = QPushButton("🔄 Periksa Ulang")
        btn_refresh_top.setFixedHeight(36)
        btn_refresh_top.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                border: 1px solid #334155;
                color: #e2e8f0;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #334155;
                color: #ffffff;
            }
        """)
        btn_refresh_top.clicked.connect(self.refresh_setup_status)
        top_btn_row.addWidget(btn_refresh_top)

        btn_next_top = QPushButton("Lanjut ke Video ➔")
        btn_next_top.setFixedHeight(36)
        btn_next_top.setStyleSheet("""
            QPushButton {
                background: #0084FF;
                border: 1px solid #0084FF;
                color: #ffffff;
                border-radius: 8px;
                padding: 6px 18px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #0073e6;
            }
        """)
        btn_next_top.clicked.connect(lambda: self.switch_tab(1))
        top_btn_row.addWidget(btn_next_top)

        header_row.addLayout(top_btn_row)
        layout.addLayout(header_row)

        # Cards container
        self.setup_cards: list[QFrame] = []
        items = self.check_system_environment()
        for it in items:
            card = self.create_setup_card(it)
            self.setup_cards.append(card)
            layout.addWidget(card)

        # Bottom Summary & Action Frame
        bottom_box = QFrame()
        bottom_box.setStyleSheet("""
            QFrame {
                background: #0d1527;
                border: 1px solid #1e293b;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        bottom_layout = QVBoxLayout(bottom_box)
        bottom_layout.setSpacing(12)

        self.setup_summary_lbl = QLabel("🎉 Semua komponen sistem & dependensi telah terverifikasi dan siap digunakan!")
        self.setup_summary_lbl.setStyleSheet("color: #10B981; font-size: 13px; font-weight: 600;")
        bottom_layout.addWidget(self.setup_summary_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_setup_install = QPushButton("⚡ Pasang / Update Dependensi Otomatis")
        self.btn_setup_install.setFixedHeight(40)
        self.btn_setup_install.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                border: 1px solid #3b82f6;
                color: #60a5fa;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #2563eb;
                color: #ffffff;
            }
        """)
        self.btn_setup_install.clicked.connect(self.install_dependencies_in_background)
        btn_row.addWidget(self.btn_setup_install)

        btn_models = QPushButton("📥 Model AI Offline")
        btn_models.setFixedHeight(40)
        btn_models.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                border: 1px solid #334155;
                color: #e2e8f0;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #334155;
                color: #ffffff;
            }
        """)
        btn_models.clicked.connect(lambda: self.switch_tab(5))
        btn_row.addWidget(btn_models)

        btn_next_bottom = QPushButton("Lanjut ke Pilih Video ➔")
        btn_next_bottom.setFixedHeight(40)
        btn_next_bottom.setStyleSheet("""
            QPushButton {
                background: #0084FF;
                border: 1px solid #0084FF;
                color: #ffffff;
                border-radius: 8px;
                padding: 8px 24px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #0073e6;
            }
        """)
        btn_next_bottom.clicked.connect(lambda: self.switch_tab(1))
        btn_row.addWidget(btn_next_bottom)

        btn_row.addStretch(1)
        bottom_layout.addLayout(btn_row)
        layout.addWidget(bottom_box)

        layout.addStretch(1)
        scroll.setWidget(page)
        return scroll

    def build_create_tab(self) -> QWidget:
        page = QWidget()
        page.setObjectName("pageContent")

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(16, 8, 16, 8)
        page_layout.setSpacing(0)

        self.create_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.create_splitter.setObjectName("mainSplitter")
        self.create_splitter.setChildrenCollapsible(False)
        self.create_splitter.setHandleWidth(8)
        page_layout.addWidget(self.create_splitter)

        # =========================================================================
        # LEFT COLUMN: SCROLLABLE SETTINGS & CONTROLS
        # =========================================================================
        left_column_container = QWidget()
        left_column_container.setStyleSheet("background: transparent;")
        left_outer_layout = QVBoxLayout(left_column_container)
        left_outer_layout.setContentsMargins(0, 0, 0, 0)
        left_outer_layout.setSpacing(8)

        step2_title = QLabel("STEP 2: BUAT CLIP")
        step2_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #FFFFFF; letter-spacing: 0.5px;")
        left_outer_layout.addWidget(step2_title)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: 0;
            }
            QScrollBar:vertical {
                background: #111722;
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #253347;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3B82F6;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        left_container = QWidget()
        left_container.setMinimumWidth(460)
        left_container.setStyleSheet("background: transparent;")
        left_col = QVBoxLayout(left_container)
        left_col.setContentsMargins(0, 0, 6, 0)
        left_col.setSpacing(8)

        # 1. Format Video & Rendering Group
        settings = QGroupBox("Format Video && Rendering")
        video_grid = QGridLayout(settings)
        video_grid.setContentsMargins(10, 8, 10, 8)
        video_grid.setVerticalSpacing(4)
        video_grid.setHorizontalSpacing(10)

        self.aspect_combo = self.combo([
            ("16:9 · Landscape YouTube", "16:9"),
            ("9:16 · Shorts / Reels / TikTok", "9:16"),
            ("1:1 · Square Instagram", "1:1"),
            ("4:3 · Classic", "4:3"),
        ], selected=0)
        self.framing_combo = self.combo([("Full video · Background blur", "fit"), ("Crop memenuhi frame", "crop")])
        self.layout_combo = self.combo([("Standard", "standard"), ("Facecam di atas (Streamer)", "facecam_top")])
        hardware_encoders = core.detect_hardware_encoders()
        self.encoder_combo = self.combo([(label, enc) for enc, label in hardware_encoders])

        for control in (self.aspect_combo, self.framing_combo, self.layout_combo, self.encoder_combo):
            control.setFixedHeight(32)

        video_grid.addWidget(QLabel("Format Output"), 0, 0)
        video_grid.addWidget(self.aspect_combo, 1, 0)
        video_grid.addWidget(QLabel("Framing Video"), 0, 1)
        video_grid.addWidget(self.framing_combo, 1, 1)

        video_grid.addWidget(QLabel("Tata Letak"), 2, 0)
        video_grid.addWidget(self.layout_combo, 3, 0)
        video_grid.addWidget(QLabel("Akselerasi Render"), 2, 1)
        video_grid.addWidget(self.encoder_combo, 3, 1)
        left_col.addWidget(settings)

        # 2. Tampilan Subtitle Group
        subtitle_group = QGroupBox("Tampilan Subtitle")
        sub_layout = QVBoxLayout(subtitle_group)
        sub_layout.setContentsMargins(10, 8, 10, 8)
        sub_layout.setSpacing(6)

        # Hardsub toggle row
        hardsub_row = QHBoxLayout()
        hardsub_row.setContentsMargins(4, 2, 4, 6)
        hardsub_lbl = QLabel("Sematkan Subtitle (Hardsub)")
        hardsub_lbl.setStyleSheet("font-weight: 600; color: #F1F5F9; font-size: 13px; background: transparent;")
        hardsub_row.addWidget(hardsub_lbl)
        hardsub_row.addStretch()

        self.subtitle_toggle_switch = ToggleSwitch()
        self.subtitle_toggle_switch.setChecked(True)
        self.subtitle_enabled = self.subtitle_toggle_switch
        hardsub_row.addWidget(self.subtitle_toggle_switch)
        sub_layout.addLayout(hardsub_row)

        subtitle_grid = QGridLayout()
        subtitle_grid.setVerticalSpacing(4)
        subtitle_grid.setHorizontalSpacing(10)

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
        self.subtitle_position_combo = self.combo([
            ("Otomatis (Aman)", "auto"),
            ("Bawah", "bottom"),
            ("Tengah", "center"),
            ("Atas", "top"),
            ("Bebas (Geser di Preview)", "free"),
        ])
        self.subtitle_color_combo = self.combo([
            ("Otomatis Sesuai Gaya", "auto"),
            ("Putih", "white"),
            ("Kuning", "yellow"),
            ("Cyan", "cyan"),
            ("Merah", "red"),
            ("Hijau", "green"),
            ("Pink", "pink"),
            ("Kustom (Kode HEX)", "custom"),
        ])
        self.subtitle_lines_combo = self.combo([
            ("2 Baris", 2),
            ("1 Baris Saja", 1),
            ("Tanpa Batas", -1),
        ])
        self.subtitle_size_combo = self.combo([
            ("Sedang 14pt", 14),
            ("Kecil 12pt", 12),
            ("Besar 17pt", 17),
            ("Ekstra Besar 20pt", 20),
        ])
        for control in (self.subtitle_combo, self.subtitle_position_combo, self.subtitle_color_combo, self.subtitle_lines_combo, self.subtitle_size_combo):
            control.setFixedHeight(32)

        subtitle_grid.addWidget(QLabel("Gaya Subtitle"), 0, 0)
        subtitle_grid.addWidget(self.subtitle_combo, 1, 0)
        subtitle_grid.addWidget(QLabel("Posisi Teks"), 0, 1)
        subtitle_grid.addWidget(self.subtitle_position_combo, 1, 1)

        subtitle_grid.addWidget(QLabel("Warna Subtitle"), 2, 0)
        subtitle_grid.addWidget(self.subtitle_color_combo, 3, 0)
        subtitle_grid.addWidget(QLabel("Maks. Baris Teks"), 2, 1)
        subtitle_grid.addWidget(self.subtitle_lines_combo, 3, 1)

        subtitle_grid.addWidget(QLabel("Ukuran Font"), 4, 0)
        subtitle_grid.addWidget(self.subtitle_size_combo, 5, 0)

        # Custom Color row
        custom_color_box = QWidget()
        custom_color_row = QHBoxLayout(custom_color_box)
        custom_color_row.setContentsMargins(0, 0, 0, 0)
        custom_color_row.setSpacing(8)

        self.subtitle_color_button = QPushButton()
        self.subtitle_color_button.setObjectName("colorSwatch")
        self.subtitle_color_button.setFixedSize(32, 32)
        self.subtitle_color_button.clicked.connect(self.choose_subtitle_color)

        self.subtitle_color_hex = QLineEdit("#FFFFFF")
        self.subtitle_color_hex.setFixedHeight(32)
        self.subtitle_color_hex.editingFinished.connect(self.apply_custom_subtitle_hex)

        custom_color_row.addWidget(self.subtitle_color_button)
        custom_color_row.addWidget(self.subtitle_color_hex)

        subtitle_grid.addWidget(QLabel("Warna Kustom"), 4, 1)
        subtitle_grid.addWidget(custom_color_box, 5, 1)
        sub_layout.addLayout(subtitle_grid)
        left_col.addWidget(subtitle_group)

        self.subtitle_color_combo.currentIndexChanged.connect(self.update_subtitle_color_chip)
        self.subtitle_toggle_switch.toggled.connect(self.update_subtitle_controls)
        self.update_subtitle_color_chip()
        self.update_subtitle_controls()

        # 3. Pengaturan AI & Model (Compact Card)
        ai_group = QGroupBox("Pengaturan AI && Model")
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.setContentsMargins(10, 8, 10, 8)
        ai_layout.setSpacing(6)

        ai_grid = QGridLayout()
        ai_grid.setVerticalSpacing(4)
        ai_grid.setHorizontalSpacing(10)

        self.mode_combo = self.combo([
            ("Highlight Otomatis (AI)", "smart"),
            ("Bagi Rata Berdasarkan Jumlah", "split_count"),
            ("Bagi Rata Berdasarkan Durasi", "split_duration"),
        ])
        self.profile_combo = self.combo([
            ("Otomatis (Deteksi Jenis Video)", "auto"),
            ("Live / Streamer", "live"),
            ("Konten Terstruktur / Edukasi", "standard"),
            ("Manual Review", "manual"),
        ])
        self.ai_provider_combo = self.combo([
            ("Google Gemini Pro (Cloud)", "gemini"),
            ("Model Lokal GGUF (Offline)", "local"),
        ])
        self.whisper_combo = self.combo([
            ("Gemini Audio (Cloud)", "gemini"),
            ("Whisper Small (Lokal)", "small"),
            ("Whisper Medium (Lokal)", "medium"),
            ("Whisper Large-v3 (Lokal)", "large-v3"),
        ])
        self.language_combo = self.combo([
            ("Deteksi Otomatis", "auto"),
            ("Indonesia", "id"),
            ("Inggris", "en"),
            ("Jepang", "ja"),
            ("Korea", "ko"),
        ])
        for c in (self.mode_combo, self.profile_combo, self.ai_provider_combo, self.whisper_combo, self.language_combo):
            c.setFixedHeight(32)

        ai_grid.addWidget(QLabel("Penyedia Model AI"), 0, 0)
        ai_grid.addWidget(self.ai_provider_combo, 1, 0)
        ai_grid.addWidget(QLabel("Transkripsi Suara"), 0, 1)
        ai_grid.addWidget(self.whisper_combo, 1, 1)

        ai_grid.addWidget(QLabel("Mode Pemotongan"), 2, 0)
        ai_grid.addWidget(self.mode_combo, 3, 0)
        ai_grid.addWidget(QLabel("Bahasa Video"), 2, 1)
        ai_grid.addWidget(self.language_combo, 3, 1)
        ai_layout.addLayout(ai_grid)

        # Gemini panel
        self.gemini_panel = QFrame()
        self.gemini_panel.setStyleSheet("background: #0d121c; border: 1px solid #233148; border-radius: 6px; padding: 6px;")
        gemini_layout = QVBoxLayout(self.gemini_panel)
        gemini_layout.setContentsMargins(6, 6, 6, 6)
        gemini_key_row = QHBoxLayout()
        gemini_key_row.addWidget(QLabel("API Key:"))
        self.gemini_key_edit = QLineEdit()
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_edit.setPlaceholderText("Paste API Key Gemini")
        is_key_saved = QSettings("VanClipper", "VanClipper").value("gemini_api_key_saved", False, type=bool)
        saved_key = QSettings("VanClipper", "VanClipper").value("gemini_api_key", "") if is_key_saved else ""
        self.gemini_key_edit.setText(saved_key)
        self.gemini_key_edit.textChanged.connect(self.on_gemini_key_changed)
        self.gemini_key_edit.setFixedHeight(32)
        gemini_key_row.addWidget(self.gemini_key_edit, 1)
        self.gemini_test_button = QPushButton("Tes")
        self.gemini_test_button.setFixedHeight(32)
        self.gemini_test_button.clicked.connect(self.test_gemini_connection)
        gemini_key_row.addWidget(self.gemini_test_button)
        self.gemini_status_badge = QLabel("")
        gemini_key_row.addWidget(self.gemini_status_badge)
        gemini_layout.addLayout(gemini_key_row)
        ai_layout.addWidget(self.gemini_panel)

        # Local panel
        self.local_panel = QFrame()
        self.local_panel.setStyleSheet("background: #0d121c; border: 1px solid #233148; border-radius: 6px; padding: 6px;")
        local_layout = QVBoxLayout(self.local_panel)
        local_layout.setContentsMargins(6, 6, 6, 6)
        local_row = QHBoxLayout()
        local_row.addWidget(QLabel("File GGUF:"))
        self.model_file_combo = ClickOnlyComboBox()
        self.model_file_combo.setFixedHeight(32)
        self.model_file_combo.currentIndexChanged.connect(self.on_model_file_changed)
        local_row.addWidget(self.model_file_combo, 1)
        self.model_folder_button = QPushButton("Pilih Folder")
        self.model_folder_button.setFixedHeight(32)
        self.model_folder_button.clicked.connect(self.pick_model_folder)
        local_row.addWidget(self.model_folder_button)
        local_layout.addLayout(local_row)
        self.model_path_edits["qwen"] = QLineEdit()
        self.model_path_edits["qwen"].setVisible(False)
        self.model_path_edits["hermes"] = QLineEdit()
        self.model_path_edits["hermes"].setVisible(False)
        ai_layout.addWidget(self.local_panel)

        self.custom_prompt_edit = QLineEdit()
        self.custom_prompt_edit.setPlaceholderText("Instruksi / topik konteks khusus (opsional)...")
        self.custom_prompt_edit.setFixedHeight(32)
        ai_layout.addWidget(self.custom_prompt_edit)

        # Mode stack widgets (kept for state compatibility)
        self.use_llm = QCheckBox("Gunakan AI")
        self.use_llm.setChecked(True)
        self.use_llm.setVisible(False)
        self.clip_count = self.spin(0, 200, 0)
        self.max_clips = self.spin(1, 200, 10)
        self.min_duration = self.spin(0, 3600, 0)
        self.max_duration = self.spin(0, 3600, 0)
        self.split_count = self.spin(1, 500, 10)
        self.segment_duration = self.spin(5, 3600, 120)
        self.smart_duration_mode = self.combo([("auto", "auto"), ("fixed", "fixed")])
        self.smart_fixed_duration = self.spin(5, 3600, 60)
        self.duration_info = QLabel("")
        self.segment_estimate = QLabel("")
        self.mode_stack = QStackedWidget()
        self.mode_stack.setVisible(False)

        self.ai_provider_combo.currentIndexChanged.connect(self.on_ai_provider_changed)
        self.on_ai_provider_changed()
        self.load_model_paths()
        self.refresh_model_file_choices()
        left_col.addWidget(ai_group)

        # Dual Progress Panel Card
        self.progress_panel = QFrame()
        self.progress_panel.setObjectName("progressCard")
        self.progress_panel.setStyleSheet("""
            QFrame#progressCard {
                background: #131926;
                border: 1px solid #233148;
                border-radius: 12px;
                padding: 16px;
                margin-top: 10px;
            }
        """)
        prog_layout = QVBoxLayout(self.progress_panel)
        prog_layout.setSpacing(8)

        total_header = QHBoxLayout()
        self.status_label = QLabel("Menyiapkan proses...")
        self.status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #f1f5f9; border: 0; background: transparent;")
        self.total_percent_label = QLabel("0%")
        self.total_percent_label.setStyleSheet("font-weight: 700; font-size: 14px; color: #3b82f6; border: 0; background: transparent;")
        total_header.addWidget(self.status_label, 1)
        total_header.addWidget(self.total_percent_label)
        prog_layout.addLayout(total_header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet("QProgressBar { background: #1c2230; border-radius: 4px; border: 0; } QProgressBar::chunk { background: #3b82f6; border-radius: 4px; }")
        prog_layout.addWidget(self.progress)

        sub_header = QHBoxLayout()
        self.sub_status_label = QLabel("Detail tahapan...")
        self.sub_status_label.setStyleSheet("font-size: 11px; color: #94a3b8; border: 0; background: transparent;")
        self.sub_percent_label = QLabel("0%")
        self.sub_percent_label.setStyleSheet("font-weight: 600; font-size: 12px; color: #10b981; border: 0; background: transparent;")
        sub_header.addWidget(self.sub_status_label, 1)
        sub_header.addWidget(self.sub_percent_label)
        prog_layout.addLayout(sub_header)

        self.sub_progress = QProgressBar()
        self.sub_progress.setRange(0, 100)
        self.sub_progress.setTextVisible(False)
        self.sub_progress.setFixedHeight(6)
        self.sub_progress.setStyleSheet("QProgressBar { background: #1c2230; border-radius: 3px; border: 0; } QProgressBar::chunk { background: #10b981; border-radius: 3px; }")
        prog_layout.addWidget(self.sub_progress)
        self.progress_panel.setVisible(False)
        left_col.addWidget(self.progress_panel)
        left_col.addStretch()

        left_scroll.setWidget(left_container)
        left_outer_layout.addWidget(left_scroll, 1)

        # Bottom Buttons Row (pinned at bottom of left column, matching mockup)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.setContentsMargins(0, 4, 0, 0)

        btn_back_tab0 = QPushButton("Kembali")
        btn_back_tab0.setFixedHeight(36)
        btn_back_tab0.setMinimumWidth(100)
        btn_back_tab0.setStyleSheet("""
            QPushButton {
                background: #131926;
                border: 1px solid #233148;
                border-radius: 8px;
                color: #CBD5E1;
                font-size: 13px;
                font-weight: 600;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background: #1E293B;
                border-color: #3B82F6;
                color: #FFFFFF;
            }
        """)
        btn_back_tab0.clicked.connect(lambda: self.switch_tab(1))
        action_row.addWidget(btn_back_tab0)

        self.start_button = QPushButton("Mulai Render Video")
        self.start_button.setObjectName("primary")
        self.start_button.setFixedHeight(36)
        self.start_button.setStyleSheet("""
            QPushButton#primary {
                background: #0084FF;
                border: 1px solid #0084FF;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 700;
                padding: 6px 20px;
            }
            QPushButton#primary:hover {
                background: #0070DF;
            }
        """)
        self.start_button.clicked.connect(self.start_process)
        action_row.addWidget(self.start_button, 1)

        self.cancel_button = QPushButton("✕ Batal & Edit Kembali")
        self.cancel_button.setFixedHeight(36)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background: #2d1515;
                border: 1px solid #ef4444;
                border-radius: 8px;
                color: #fca5a5;
                font-size: 13px;
                font-weight: 700;
                padding: 6px 20px;
            }
            QPushButton:hover {
                background: #451a1a;
                color: #ffffff;
            }
        """)
        self.cancel_button.clicked.connect(self.cancel_current_process)
        self.cancel_button.setVisible(False)
        action_row.addWidget(self.cancel_button, 1)
        left_outer_layout.addLayout(action_row)

        self.create_splitter.addWidget(left_column_container)

        # =========================================================================
        # RIGHT COLUMN: PRATINJAU VIDEO & KLIP (FIXED / PINNED COMPACT)
        # =========================================================================
        right_container = QWidget()
        right_container.setStyleSheet("background: transparent;")
        right_col = QVBoxLayout(right_container)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(6)

        preview_title = QLabel("Pratinjau Video & Klip")
        preview_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #FFFFFF; letter-spacing: 0.5px;")
        right_col.addWidget(preview_title)

        self.create_preview_player = QMediaPlayer(self)
        self.create_preview_audio = QAudioOutput(self)
        self.create_preview_player.setAudioOutput(self.create_preview_audio)
        self.create_preview_player.playbackStateChanged.connect(self.on_create_playback_state_changed)

        # Centered container for the video canvas
        preview_box = QWidget()
        preview_box_layout = QVBoxLayout(preview_box)
        preview_box_layout.setContentsMargins(0, 0, 0, 0)
        preview_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        preview_frame = QFrame()
        self.create_preview_frame = preview_frame
        preview_frame.setObjectName("previewCanvas")
        preview_stack = QGridLayout(preview_frame)
        self.create_preview_stack = preview_stack
        preview_stack.setContentsMargins(0, 0, 0, 0)

        self.create_preview_video = VideoSurfaceWidget()
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

        self.preview_subtitle_sample = DraggableSubtitleLabel("Contoh subtitle akan tampil di sini", self.create_preview_video)
        self.preview_subtitle_sample.setObjectName("previewSubtitle")
        self.preview_subtitle_sample.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_subtitle_sample.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.preview_subtitle_sample.moved.connect(self.on_free_subtitle_moved)
        self.preview_placeholder = QLabel("Pilih atau unduh video untuk memuat pratinjau.")
        self.preview_placeholder.setStyleSheet("color: #64748B; font-size: 13px; font-weight: 500;")
        self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_stack.addWidget(self.preview_placeholder, 0, 0, Qt.AlignmentFlag.AlignCenter)

        self.create_preview_player.setVideoOutput(self.create_preview_video.sink)
        preview_box_layout.addWidget(preview_frame)
        right_col.addWidget(preview_box, 1)

        # Scrubber & Timestamps
        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        self.create_preview_time = QLabel("00:00 / 00:00")
        self.create_preview_time.setStyleSheet("font-size: 12px; font-weight: 600; color: #94A3B8; background: transparent;")
        time_row.addWidget(self.create_preview_time)
        time_row.addStretch()

        self.create_preview_pos_time = QLabel("00:00 / 00:00")
        self.create_preview_pos_time.setStyleSheet("font-size: 12px; font-weight: 600; color: #94A3B8; background: transparent;")
        time_row.addWidget(self.create_preview_pos_time)
        right_col.addLayout(time_row)

        self.create_seek_slider = WaveformScrubber()
        self.create_seek_slider.setRange(0, 0)
        self.create_seek_slider.setFixedHeight(24)
        self.create_seek_slider.setEnabled(False)
        self.create_seek_slider.sliderMoved.connect(self.seek_create_preview)
        self.create_preview_player.positionChanged.connect(self.update_create_seek)
        self.create_preview_player.durationChanged.connect(self.update_create_duration)
        right_col.addWidget(self.create_seek_slider)

        # Media Playback Controls Toolbar
        controls_toolbar = QHBoxLayout()
        controls_toolbar.setSpacing(6)

        ctrl_btn_style = """
            QPushButton {
                background: #141B28;
                border: 1px solid #28374F;
                border-radius: 6px;
                color: #FFFFFF;
                font-family: 'Segoe UI Emoji';
                font-size: 13px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background: #1F2C42;
                border-color: #3B82F6;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background: #0F1522;
            }
        """

        btn_aspect = QPushButton("⛶")
        btn_aspect.setToolTip("Ganti Rasio / Framing Output")
        btn_aspect.setFixedSize(32, 32)
        btn_aspect.setStyleSheet(ctrl_btn_style)
        btn_aspect.clicked.connect(lambda: self.aspect_combo.setCurrentIndex((self.aspect_combo.currentIndex() + 1) % self.aspect_combo.count()))
        controls_toolbar.addWidget(btn_aspect)

        controls_toolbar.addStretch()

        btn_prev = QPushButton("⏮")
        btn_prev.setToolTip("Kembali ke Awal (00:00)")
        btn_prev.setFixedSize(32, 32)
        btn_prev.setStyleSheet(ctrl_btn_style)
        btn_prev.clicked.connect(lambda: self.seek_create_preview(0))
        controls_toolbar.addWidget(btn_prev)

        btn_rew = QPushButton("⏪")
        btn_rew.setToolTip("Mundur 5 Detik")
        btn_rew.setFixedSize(32, 32)
        btn_rew.setStyleSheet(ctrl_btn_style)
        btn_rew.clicked.connect(lambda: self.seek_create_preview(max(0, self.create_preview_player.position() - 5000)))
        controls_toolbar.addWidget(btn_rew)

        self.create_preview_play = QPushButton("▶")
        self.create_preview_play.setToolTip("Putar Video (Spasi)")
        self.create_preview_play.setFixedSize(38, 38)
        self.create_preview_play.setStyleSheet("""
            QPushButton {
                background: #0084FF;
                color: #FFFFFF;
                font-family: Arial, 'Segoe UI', sans-serif;
                font-size: 16px;
                font-weight: bold;
                border-radius: 19px;
                border: 0;
                padding: 0px;
            }
            QPushButton:hover {
                background: #0070DF;
            }
            QPushButton:pressed {
                background: #005BBF;
            }
        """)
        self.create_preview_play.clicked.connect(self.toggle_create_preview)
        controls_toolbar.addWidget(self.create_preview_play)

        btn_ff = QPushButton("⏩")
        btn_ff.setToolTip("Maju 5 Detik")
        btn_ff.setFixedSize(32, 32)
        btn_ff.setStyleSheet(ctrl_btn_style)
        btn_ff.clicked.connect(lambda: self.seek_create_preview(min(self.create_preview_player.duration(), self.create_preview_player.position() + 5000)))
        controls_toolbar.addWidget(btn_ff)

        btn_next = QPushButton("⏭")
        btn_next.setToolTip("Lompat ke Akhir Video")
        btn_next.setFixedSize(32, 32)
        btn_next.setStyleSheet(ctrl_btn_style)
        btn_next.clicked.connect(lambda: self.seek_create_preview(self.create_preview_player.duration()))
        controls_toolbar.addWidget(btn_next)

        controls_toolbar.addStretch()

        self.create_preview_mute_btn = QPushButton("🔊")
        self.create_preview_mute_btn.setToolTip("Bisukan Audio")
        self.create_preview_mute_btn.setFixedSize(32, 32)
        self.create_preview_mute_btn.setStyleSheet(ctrl_btn_style)
        self.create_preview_mute_btn.clicked.connect(self.toggle_create_mute)
        controls_toolbar.addWidget(self.create_preview_mute_btn)

        btn_zoom = QPushButton("🔍")
        btn_zoom.setToolTip("Ubah Framing / Zoom")
        btn_zoom.setFixedSize(32, 32)
        btn_zoom.setStyleSheet(ctrl_btn_style)
        btn_zoom.clicked.connect(lambda: self.framing_combo.setCurrentIndex(1 if self.framing_combo.currentIndex() == 0 else 0))
        controls_toolbar.addWidget(btn_zoom)

        emoji_font = QFont("Segoe UI Emoji", 11)
        for b in (btn_aspect, btn_prev, btn_rew, btn_ff, btn_next, self.create_preview_mute_btn, btn_zoom):
            b.setFont(emoji_font)
        self.create_preview_play.setFont(QFont("Segoe UI Emoji", 13))

        right_col.addLayout(controls_toolbar)

        self.preview_layout_badge = QLabel("Preview format output")
        self.preview_layout_badge.setVisible(False)
        self.preview_summary = QLabel("")
        self.preview_summary.setVisible(False)

        for control in (self.aspect_combo, self.framing_combo, self.layout_combo, self.subtitle_combo, self.subtitle_toggle_switch, self.subtitle_position_combo, self.subtitle_color_combo, self.subtitle_lines_combo, self.subtitle_size_combo):
            if isinstance(control, (QCheckBox, ToggleSwitch)):
                control.toggled.connect(self.update_create_preview)
            else:
                control.currentIndexChanged.connect(self.update_create_preview)

        self.create_splitter.addWidget(right_container)
        self.create_splitter.setStretchFactor(0, 0)
        self.create_splitter.setStretchFactor(1, 1)
        self.create_splitter.setSizes([540, 740])
        self.create_splitter.splitterMoved.connect(lambda pos, idx: self.update_create_preview())

        self.settings_group = settings
        self.subtitle_group = subtitle_group
        self.ai_group = ai_group
        self.clip_stage_widgets = [settings, subtitle_group, ai_group, self.start_button, preview_frame]
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

        # =========================================================================
        # LEFT COLUMN: STEP 1: MASUKKAN VIDEO
        # =========================================================================
        left_col = QVBoxLayout()
        left_col.setSpacing(14)

        step_title = QLabel("STEP 1: MASUKKAN VIDEO")
        step_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF; letter-spacing: 0.5px;")
        left_col.addWidget(step_title)

        # Drag and Drop Box
        self.drop_zone = DropZoneWidget()
        self.drop_zone.fileDropped.connect(self.on_file_dropped)
        self.drop_zone.clicked.connect(self.choose_local_video)
        left_col.addWidget(self.drop_zone)

        # Video URL Input
        lbl_url = QLabel("Link video")
        lbl_url.setStyleSheet("font-size: 13px; font-weight: 500; color: #CBD5E1;")
        left_col.addWidget(lbl_url)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_edit.setMinimumHeight(42)
        left_col.addWidget(self.url_edit)

        # Quality selector and Download Button
        url_action_row = QHBoxLayout()
        url_action_row.setSpacing(12)

        self.quality_combo = self.combo([
            ("Kualitas unduhan: 1080p - Full HD", "1080"),
            ("Kualitas unduhan: 720p - HD", "720"),
            ("Kualitas unduhan: 480p", "480"),
            ("Kualitas unduhan: 360p - Hemat", "360"),
            ("Kualitas unduhan: Terbaik (hingga 4K)", "best"),
        ], 0)
        self.quality_combo.setMinimumHeight(42)
        url_action_row.addWidget(self.quality_combo, 1)

        self.download_button = QPushButton("Unduh video")
        self.download_button.setObjectName("primary")
        self.download_button.setMinimumHeight(42)
        self.download_button.setStyleSheet("font-weight: 700; padding: 0 24px;")
        self.download_button.clicked.connect(self.start_download)
        url_action_row.addWidget(self.download_button)

        left_col.addLayout(url_action_row)

        self.local_file_button = QPushButton("Pilih File Lokal...")
        self.local_file_button.setVisible(False)
        self.local_file_button.clicked.connect(self.choose_local_video)

        self.source_status = QLabel("Belum ada video sumber")
        self.source_status.setObjectName("status")
        left_col.addWidget(self.source_status)
        left_col.addStretch()

        main_layout.addLayout(left_col, 55)

        # =========================================================================
        # RIGHT COLUMN: PUSTAKA VIDEO SUMBER
        # =========================================================================
        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        lib_title = QLabel("Pustaka Video Sumber")
        lib_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF; letter-spacing: 0.5px;")
        right_col.addWidget(lib_title)

        # Grid container for video cards
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

        # Actions under library
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

    def build_tutorial_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        eyebrow = QLabel("PUSAT INFORMASI, PANDUAN LENGKAP & DOKUMENTASI")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("Panduan Penggunaan & Pusat Informasi ENCLip")
        title.setObjectName("title")
        layout.addWidget(title)
        content = QTextEdit()
        content.setReadOnly(True)
        content.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #CBD5E1;">
          <h2 style="color: #60A5FA; margin-top: 0;">🚀 1. Panduan Cepat Pemula (3 Langkah Mudah)</h2>
          <p>ENCLip dirancang agar siapapun — termasuk pengguna awam — dapat langsung memotong video panjang menjadi klip viral ber-subtitle tanpa pengaturan teknis yang rumit:</p>
          <ol>
            <li><b>Langkah 1: Setup Lingkungan (Tab Setup):</b> Saat aplikasi dibuka, periksa status sistem. Jika ada yang bertanda kuning/oranye, cukup klik satu tombol <b>"⚡ Pasang / Update Dependensi Otomatis"</b>. Semua modul akan disiapkan secara otomatis di latar belakang.</li>
            <li><b>Langkah 2: Masukkan Video (Tab Video):</b> Masukkan tautan video YouTube / Shorts, atau seret langsung file video (MP4, MKV, dsb.) dari laptop/komputer Anda ke kotak unduh.</li>
            <li><b>Langkah 3: Atur & Render (Tab Buat clip):</b> Pilih rasio (misalnya 9:16 vertikal untuk TikTok/Reels/Shorts), pilih gaya subtitle, lalu klik tombol biru <b>"Mulai Render Video"</b>!</li>
          </ol>

          <h2 style="color: #60A5FA;">🎬 2. Fitur Editor & Review Timeline Interaktif</h2>
          <p>Setelah AI menganalisis video dan mentranskripsi suara, Anda dapat meninjau serta menyunting klip sebelum hasil akhir dirender:</p>
          <ul>
            <li><b>Sunting Subtitle:</b> Klik tombol <i>Sunting</i> pada alat timeline untuk memperbaiki ejaan kata, mengubah teks terjemahan, atau menyesuaikan tanda baca secara instan.</li>
            <li><b>Potong Klip Manual (Trim & Cut):</b> Klik tombol <i>Potong</i> untuk menyesuaikan waktu mulai dan selesai klip secara akurat hingga per milidetik.</li>
            <li><b>Ubah Rasio Layar:</b> Klik tombol <i>Rasio</i> untuk berganti seketika antara 9:16 (Vertikal TikTok/Shorts), 16:9 (Horizontal YouTube), 1:1 (Persegi Feed), atau 4:3.</li>
            <li><b>Framing & Zoom:</b> Gunakan opsi <i>Full video · background blur</i> agar video lanskap tetap utuh dengan latar belakang blur estetis saat diubah menjadi format vertikal HP.</li>
            <li><b>Geser Posisi Subtitle Bebas:</b> Pada layar pratinjau, Anda dapat langsung mengklik dan menyeret (drag) kotak subtitle ke posisi manapun yang Anda inginkan di layar!</li>
          </ul>

          <h2 style="color: #60A5FA;">🎙️ 3. Subtitle Realtime & Anti-Delay (Sinkronisasi Kata Presisi)</h2>
          <p>ENCLip dilengkapi sistem <b>Word-Level Timestamping</b> dari model AI Whisper. Kata-kata dikelompokkan secara cerdas menjadi 3–5 kata (~1.5–2 detik) dan disinkronkan langsung dengan gelombang suara pembicara. Teks tidak akan tertunda (delay) dan berganti tepat saat orang berbicara.</p>

          <h2 style="color: #60A5FA;">🧠 4. Pilihan Otak AI: Google Gemini Cloud vs Model AI Lokal</h2>
          <table border="1" cellpadding="8" style="border-collapse: collapse; border-color: #334155; width: 100%; margin-top: 8px; margin-bottom: 8px;">
            <tr style="background: #1E293B; color: #F8FAFC;">
              <th>Fitur & Karakteristik</th>
              <th>Google Gemini Pro (Cloud)</th>
              <th>Model AI Lokal (Offline)</th>
            </tr>
            <tr>
              <td><b>Kecepatan Analisis</b></td>
              <td>Sangat cepat (Hitungan detik via server Google Cloud)</td>
              <td>Tergantung kecepatan prosesor (CPU/GPU) komputer</td>
            </tr>
            <tr>
              <td><b>Beban Memori (RAM / GPU)</b></td>
              <td>Sangat ringan (Tidak membebani hardware Anda)</td>
              <td>Disarankan memiliki minimal RAM 8GB atau VGA terpisah</td>
            </tr>
            <tr>
              <td><b>Akses Internet</b></td>
              <td>Memerlukan sambungan internet</td>
              <td>100% Offline (Dapat berjalan tanpa internet sama sekali)</td>
            </tr>
            <tr>
              <td><b>Biaya Penggunaan</b></td>
              <td>100% Gratis via kuota developer Google AI Studio</td>
              <td>100% Gratis & Open-Source</td>
            </tr>
          </table>

          <h3 style="color: #38BDF8;">Cara Mendapatkan Google Gemini API Key Gratis (100% Tanpa Kartu Kredit):</h3>
          <ol>
            <li>Buka browser Anda dan kunjungi situs resmi: <b><a href="https://aistudio.google.com/">aistudio.google.com</a></b>.</li>
            <li>Login menggunakan akun Google / Gmail Anda.</li>
            <li>Klik tombol <b>Get API key</b> di menu sebelah kiri atas.</li>
            <li>Klik <b>Create API key</b> &gt; Buat kunci pada project Google Cloud baru (otomatis).</li>
            <li>Salin string kunci API yang muncul (berawalan <code>AIzaSy...</code>).</li>
            <li>Di aplikasi ENCLip, buka tab <b>Buat clip</b> &gt; pilih <b>Google Gemini Pro (Cloud)</b>, tempelkan kunci di kolom API Key, lalu klik <b>Tes</b>. Kunci akan otomatis disimpan untuk selamanya!</li>
          </ol>

          <h2 style="color: #60A5FA;">📁 5. Lokasi Penyimpanan File Kerja</h2>
          <p>Seluruh berkas Anda disimpan secara rapi di dalam direktori <code>Core_Data/</code>:</p>
          <ul>
            <li><code>Core_Data/VideoMentah/</code> : Menyimpan video sumber yang diunduh atau diimpor. Video di sini dapat digunakan kembali kapan saja tanpa perlu download ulang.</li>
            <li><code>Core_Data/HasilClip/Nama Video/</code> : Folder penyimpanan hasil akhir klip video MP4 berkualitas tinggi yang siap Anda unggah ke TikTok, YouTube Shorts, atau Instagram Reels.</li>
            <li><code>Core_Data/models/</code> : Folder penyimpanan model AI offline (GGUF dan model transkripsi Whisper).</li>
          </ul>

          <h2 style="color: #60A5FA;">❓ 6. Pertanyaan Umum & Solusi Kendala (FAQ)</h2>
          <ul>
            <li><b>Bagaimana jika komputer saya spek standar atau tidak memiliki kartu grafis (GPU)?</b><br/>Pilihlah penyedia AI <i>Google Gemini Pro (Cloud)</i> dan gunakan preset render video <i>FAST</i> atau <i>ULTRAFAST</i>. Cara ini sangat hemat RAM dan proses tetap super ngebut.</li>
            <li><b>Apakah video tanpa orang bicara (misal rekaman game tanpa mikrofon atau pemandangan) bisa dipotong?</b><br/>Tentu bisa! Ubah mode klip menjadi <i>"Bagi berdasarkan durasi"</i> (misal tiap 60 detik) atau <i>"Bagi berdasarkan jumlah"</i>, bukan Highlight otomatis.</li>
            <li><b>Bagaimana jika saya ingin membatalkan render yang sedang berjalan?</b><br/>Cukup klik tombol merah <i>"✕ Batal & Edit Kembali"</i>. Render akan langsung dihentikan secara aman dan Anda dapat menyesuaikan kembali pengaturan.</li>
            <li><b>Subtitle menutupi bagian penting video, bagaimana memindahkannya?</b><br/>Di tab <i>Buat clip</i>, Anda dapat langsung mengklik dan menyeret (drag) teks subtitle pada layar pratinjau ke atas, tengah, atau bawah sesuai selera!</li>
          </ul>
        </div>
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
        if hasattr(self, "smart_fixed_label"):
            self.smart_fixed_label.setVisible(fixed)
        if hasattr(self, "smart_fixed_row"):
            self.smart_fixed_row.setVisible(fixed)
        if hasattr(self, "smart_range_label"):
            self.smart_range_label.setVisible(not fixed)
        if hasattr(self, "smart_range_row"):
            self.smart_range_row.setVisible(not fixed)
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
        needed = max(185, hint_h, layout_h) + 16
        self.mode_stack.setFixedHeight(needed)

    def update_subtitle_controls(self) -> None:
        if not hasattr(self, "subtitle_enabled"):
            return
        enabled = self.subtitle_enabled.isChecked()
        for attr in ("subtitle_combo", "subtitle_position_combo", "subtitle_color_combo", "subtitle_color_button", "subtitle_color_hex", "subtitle_lines_combo", "subtitle_size_combo"):
            if hasattr(self, attr):
                getattr(self, attr).setEnabled(enabled)
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
        font_size: int | None = None,
        max_lines: int | None = None,
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
        pad = f"{max(4, int(sz * 0.35))}px {max(8, int(sz * 0.8))}px"
        style_sheets = {
            "bold": (
                f"background: rgba(0, 0, 0, 225); color: {accent}; "
                f"padding: {pad}; border-radius: 4px; "
                f"font-family: Arial Black; font-size: {sz}px; font-weight: 900;"
            ),
            "highlight": (
                f"background: #102742; color: {accent}; "
                f"padding: {pad}; border: 1px solid #5c9dff; border-radius: 4px; "
                f"font-family: Arial Black; font-size: {sz}px; font-weight: 900;"
            ),
            "classic": (
                f"background: rgba(0, 0, 0, 175); color: {accent}; "
                f"padding: {pad}; border-radius: 1px; "
                f"font-family: Arial; font-size: {sz}px; font-weight: 400;"
            ),
            "minimal": (
                f"background: rgba(0, 0, 0, 120); color: {accent}; "
                f"padding: {pad}; border-radius: 2px; "
                f"font-family: Arial; font-size: {sz}px; font-weight: 400;"
            ),
            "neon": (
                f"background: rgba(7, 20, 35, 225); color: {accent}; "
                f"padding: {pad}; border: 1px solid {accent}; border-radius: 12px; "
                f"font-family: Arial Black; font-size: {sz}px; font-weight: 900;"
            ),
            "karaoke": (
                f"background: rgba(51, 14, 67, 225); color: {accent}; "
                f"padding: {pad}; border: 1px solid {accent}; border-radius: 5px; "
                f"font-family: Arial Black; font-size: {sz}px; font-weight: 900;"
            ),
            "box": (
                f"background: rgba(0, 0, 0, 220); color: {accent}; "
                f"padding: {pad}; border-radius: 0px; "
                f"font-family: Arial; font-size: {sz}px; font-weight: 700;"
            ),
        }
        label.setStyleSheet(style_sheets.get(style, style_sheets["bold"]))
        if sample:
            label.setTextFormat(Qt.TextFormat.RichText)
            lines_val = max_lines if max_lines is not None else (self.subtitle_lines_combo.currentData() if hasattr(self, "subtitle_lines_combo") else 2)
            if lines_val == 1:
                sample_text = f"Contoh subtitle sebaris · {language}"
            elif lines_val == 2:
                sample_text = f"Contoh subtitle dua baris<br>rapi & proporsional · {language}"
            else:
                sample_text = f"Contoh subtitle penuh · {language}"

            if style == "highlight":
                label.setText(f"<font color='{accent}'>{sample_text}</font>")
            elif style == "neon":
                label.setText(f"✦ {sample_text} ✦")
            elif style == "karaoke":
                label.setText(f"♪ {sample_text} ♪")
            elif style == "box":
                label.setText(f"[ {sample_text} ]")
            else:
                label.setText(sample_text)
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
        style = self.subtitle_combo.currentData() if hasattr(self, "subtitle_enabled") and self.subtitle_enabled.isChecked() else "none"
        font_sz = self.subtitle_size_combo.currentData() if hasattr(self, "subtitle_size_combo") else 14
        lines_limit = self.subtitle_lines_combo.currentData() if hasattr(self, "subtitle_lines_combo") else 2
        self.apply_subtitle_preview_style(
            self.preview_subtitle_sample,
            style,
            language=lang_text,
            color=self.selected_subtitle_color(),
            sample=True,
            font_size=font_sz,
            max_lines=lines_limit,
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

    def update_create_preview(self) -> None:
        if not hasattr(self, "preview_summary") or not hasattr(self, "create_preview_frame"):
            return
        aspect = self.aspect_combo.currentData()
        framing = self.framing_combo.currentText()
        layout = self.layout_combo.currentText()

        # Dynamic available space calculation:
        # Measure actual height from central tabs to ensure controls never get pushed off-screen
        tabs_h = self.tabs.height() if hasattr(self, "tabs") and self.tabs.height() > 100 else max(400, self.height() - 70)

        # Overhead in right column: title (~30px), time labels (~22px), waveform scrubber (~28px),
        # control toolbar buttons (~46px), margins & spacings (~34px) -> total ~160px
        max_canvas_h = max(140, tabs_h - 170)

        # In full screen or maximized mode, cap vertical height so it never bloats downward
        if self.isMaximized() or self.isFullScreen():
            max_canvas_h = min(max_canvas_h, int(tabs_h * 0.72))

        # Available width from right container or splitter
        if hasattr(self, "create_splitter") and self.create_splitter.sizes() and len(self.create_splitter.sizes()) > 1 and self.create_splitter.sizes()[1] > 100:
            avail_w = max(180, self.create_splitter.sizes()[1] - 32)
        else:
            avail_w = max(180, int((self.width() - 40) * 0.54) - 24)

        aspect_ratios = {
            "9:16": 9 / 16,     # ~0.5625
            "1:1":  1.0,        # 1.0
            "4:3":  4 / 3,      # ~1.3333
            "16:9": 16 / 9,     # ~1.7778
        }
        ar = aspect_ratios.get(aspect, 16 / 9)

        # Calculate bounding box dimensions strictly preserving the chosen aspect ratio
        if (avail_w / max_canvas_h) > ar:
            canvas_height = max_canvas_h
            canvas_width = int(canvas_height * ar)
        else:
            canvas_width = avail_w
            canvas_height = int(canvas_width / ar)

        # Enforce strict maximum bounds: never exceed avail_w or max_canvas_h
        if canvas_height > max_canvas_h:
            canvas_height = max_canvas_h
            canvas_width = int(canvas_height * ar)
        if canvas_width > avail_w:
            canvas_width = avail_w
            canvas_height = int(canvas_width / ar)

        canvas_width = max(160, canvas_width)
        canvas_height = max(120, canvas_height)

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
            language = self.language_combo.currentText() if hasattr(self, "language_combo") else "Indonesia"
            style = self.subtitle_combo.currentText()
            font_sz = self.subtitle_size_combo.currentData() if hasattr(self, "subtitle_size_combo") else 14
            lines_limit = self.subtitle_lines_combo.currentData() if hasattr(self, "subtitle_lines_combo") else 2
            self.apply_subtitle_preview_style(
                self.preview_subtitle_sample,
                self.subtitle_combo.currentData(),
                language=language,
                color=self.selected_subtitle_color(),
                sample=True,
                font_size=font_sz,
                max_lines=lines_limit,
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
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
            label.move(int(available_width * self.subtitle_free_x), int(available_height * self.subtitle_free_y))
        elif position == "top":
            x = (pw - lw) // 2
            y = int(ph * 0.08)
            label.move(max(0, x), max(0, y))
        elif position == "center":
            x = (pw - lw) // 2
            y = (ph - lh) // 2
            label.move(max(0, x), max(0, y))
        else:  # "bottom" or "auto"
            x = (pw - lw) // 2
            if ph > pw:
                y = min(ph - lh - 16, max(16, int(ph * 0.72)))
            else:
                y = max(0, ph - lh - max(16, int(ph * 0.08)))
            label.move(max(0, x), y)

        label.raise_()
        is_sub_on = self.subtitle_enabled.isChecked() if hasattr(self, "subtitle_enabled") else True
        style = self.subtitle_combo.currentData() if hasattr(self, "subtitle_combo") else "bold"
        label.setVisible(is_sub_on and style != "none")

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
        dur = self.create_preview_player.duration()
        time_str = f"{format_time(position / 1000)} / {format_time(dur / 1000)}"
        self.create_preview_time.setText(time_str)
        if hasattr(self, "create_preview_pos_time"):
            self.create_preview_pos_time.setText(time_str)

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
                self.create_preview_play.setText("❚❚")
                self.create_preview_play.setToolTip("Jeda Video (Spasi)")
            else:
                self.create_preview_play.setText("▶")
                self.create_preview_play.setToolTip("Putar Video (Spasi)")

    def toggle_create_preview(self) -> None:
        if self.create_preview_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.create_preview_player.pause()
        else:
            if self.create_preview_player.position() >= self.create_preview_player.duration() and self.create_preview_player.duration() > 0:
                self.create_preview_player.setPosition(0)
            self.create_preview_player.play()

    def toggle_create_mute(self) -> None:
        is_muted = not self.create_preview_audio.isMuted()
        self.create_preview_audio.setMuted(is_muted)
        if hasattr(self, "create_preview_mute_btn"):
            self.create_preview_mute_btn.setText("🔇" if is_muted else "🔊")
            self.create_preview_mute_btn.setToolTip("Aktifkan Audio" if is_muted else "Bisukan Audio")

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
            if path == "gemini": continue
            self.model_file_combo.addItem(Path(path).name, path)
            self.model_file_combo.setItemData(self.model_file_combo.count() - 1, path, Qt.ItemDataRole.ToolTipRole)
        self.model_file_combo.addItem("☁ Gemini Pro API", "gemini")
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
        self.gemini_panel.setVisible(is_gemini)
        self.local_panel.setVisible(not is_gemini)
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

    def on_gemini_key_changed(self, text: str) -> None:
        clean = text.strip()
        import os
        os.environ["GEMINI_API_KEY"] = clean
        core.GEMINI_API_KEY = clean
        if not clean and hasattr(self, "gemini_status_badge"):
            self.gemini_status_badge.setText("")

    def test_gemini_connection(self) -> None:
        key = self.gemini_key_edit.text().strip()
        if not key:
            self.gemini_status_badge.setText("✕ Kunci API kosong")
            self.gemini_status_badge.setStyleSheet("color: #ef4444; background: #2d1515; border: 1px solid #7f1d1d; border-radius: 4px; padding: 4px 8px; font-weight: 600;")
            return
        self.gemini_status_badge.setText("Menguji koneksi...")
        self.gemini_status_badge.setStyleSheet("color: #60a5fa; background: #172554; border: 1px solid #1e40af; border-radius: 4px; padding: 4px 8px; font-weight: 500;")
        QApplication.processEvents()
        try:
            from google import genai
            client = genai.Client(api_key=key)
            client.models.get(model="gemini-3.8-flash")
            self.gemini_status_badge.setText("✓ Terhubung (Gemini Aktif)")
            self.gemini_status_badge.setStyleSheet("color: #10b981; background: #064e3b; border: 1px solid #047857; border-radius: 4px; padding: 4px 8px; font-weight: 600;")
            QSettings("VanClipper", "VanClipper").setValue("gemini_api_key", key)
            QSettings("VanClipper", "VanClipper").setValue("gemini_api_key_saved", True)
            import os
            os.environ["GEMINI_API_KEY"] = key
            core.GEMINI_API_KEY = key
            self.log_terminal("Google Gemini API Key terhubung dan tersimpan.")
        except Exception as exc:
            err_msg = str(exc)
            if "API_KEY_INVALID" in err_msg or "400" in err_msg:
                text = "✕ Kunci API tidak valid"
            elif "429" in err_msg:
                text = "✕ Kuota API habis"
            else:
                text = f"✕ Gagal: {err_msg[:28]}"
            self.gemini_status_badge.setText(text)
            self.gemini_status_badge.setStyleSheet("color: #ef4444; background: #2d1515; border: 1px solid #7f1d1d; border-radius: 4px; padding: 4px 8px; font-weight: 600;")
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
        if candidates and not found["qwen"]:
            found["qwen"] = str(candidates[0])
        for model_name, path in found.items():
            if path:
                self.model_path_edits[model_name].setText(path)
        if candidates:
            self.refresh_model_file_choices([str(candidate) for candidate in candidates], keep_current=False)
        self.save_model_paths()
        found_count = len(candidates)
        if found_count:
            QMessageBox.information(self, "Model ditemukan", f"{found_count} model GGUF berhasil ditemukan di folder models.")
        else:
            QMessageBox.information(self, "Model belum ditemukan", "Tidak ada file .gguf di folder models. Letakkan file .gguf di folder Core_Data/models.")

    def apply_model_paths(self) -> None:
        selected = self.model_file_combo.currentData() if hasattr(self, "model_file_combo") else None
        if selected and selected != "gemini":
            key = self.active_model_key if self.active_model_key in self.model_path_edits else ("hermes" if "hermes" in str(selected).lower() else "qwen")
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
        page.setMinimumWidth(860)
        page.setMaximumWidth(1320)

        main_layout = QHBoxLayout(page)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(28)

        # =========================================================================
        # LEFT COLUMN: STEP 3: REVIEW CLIPS & TIMELINE
        # =========================================================================
        left_col = QVBoxLayout()
        left_col.setSpacing(14)

        step3_title = QLabel("STEP 3: REVIEW CLIPS & TIMELINE")
        step3_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF; letter-spacing: 0.5px;")
        left_col.addWidget(step3_title)

        preview_header = QLabel("Pratinjau Video & Timeline")
        preview_header.setStyleSheet("font-size: 13px; font-weight: 600; color: #94A3B8;")
        left_col.addWidget(preview_header)

        # Player
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.playbackStateChanged.connect(self.on_review_playback_state_changed)

        source_frame = QFrame()
        self.review_source_frame = source_frame
        source_frame.setObjectName("previewCanvas")
        source_frame.setMinimumHeight(380)

        source_stack = QGridLayout(source_frame)
        self.review_source_stack = source_stack
        source_stack.setContentsMargins(0, 0, 0, 0)

        self.video_widget = VideoSurfaceWidget()
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.player.setVideoOutput(self.video_widget.sink)
        source_stack.addWidget(self.video_widget, 0, 0)

        self.source_subtitle_overlay = QLabel("", self.video_widget)
        self.source_subtitle_overlay.setObjectName("previewSubtitle")
        self.source_subtitle_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_subtitle_overlay.setWordWrap(True)
        self.source_subtitle_overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.source_subtitle_overlay.setVisible(False)
        left_col.addWidget(source_frame)

        # Controls under video
        player_controls = QHBoxLayout()
        player_controls.setSpacing(10)

        play_btn_style = (
            "QPushButton { "
            "background: #0084FF; border-radius: 18px; border: none; padding: 0px; margin: 0px; text-align: center; "
            "} "
            "QPushButton:hover { background: #0070D8; } "
            "QPushButton:pressed { background: #005BB5; }"
        )
        self.play_button = QPushButton()
        self.play_button.setIcon(make_vector_icon("play", "#FFFFFF", 24))
        self.play_button.setIconSize(QSize(20, 20))
        self.play_button.setToolTip("Putar Video (Spasi)")
        self.play_button.setFixedSize(36, 36)
        self.play_button.setStyleSheet(play_btn_style)
        self.play_button.clicked.connect(self.toggle_video)
        player_controls.addWidget(self.play_button)

        ctrl_btn_style = (
            "QPushButton { "
            "background: #1E293B; border: 1px solid #334155; border-radius: 6px; padding: 0px; margin: 0px; text-align: center; "
            "} "
            "QPushButton:hover { background: #334155; } "
            "QPushButton:pressed { background: #0F172A; }"
        )
        btn_rew = QPushButton()
        btn_rew.setIcon(make_vector_icon("rewind", "#E2E8F0", 24))
        btn_rew.setIconSize(QSize(18, 18))
        btn_rew.setToolTip("Mundur 5 Detik")
        btn_rew.setFixedSize(32, 32)
        btn_rew.setStyleSheet(ctrl_btn_style)
        btn_rew.clicked.connect(lambda: self.seek_review_video(max(0, self.player.position() - 5000)))
        player_controls.addWidget(btn_rew)

        btn_ff = QPushButton()
        btn_ff.setIcon(make_vector_icon("forward", "#E2E8F0", 24))
        btn_ff.setIconSize(QSize(18, 18))
        btn_ff.setToolTip("Maju 5 Detik")
        btn_ff.setFixedSize(32, 32)
        btn_ff.setStyleSheet(ctrl_btn_style)
        btn_ff.clicked.connect(lambda: self.seek_review_video(min(self.player.duration(), self.player.position() + 5000)))
        player_controls.addWidget(btn_ff)

        self.review_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.review_seek_slider.setRange(0, 0)
        self.review_seek_slider.setEnabled(False)
        self.review_seek_slider.sliderMoved.connect(self.seek_review_video)
        self.player.positionChanged.connect(self.update_player_time)
        self.player.durationChanged.connect(self.update_player_duration)
        player_controls.addWidget(self.review_seek_slider, 1)

        self.current_time = QLabel("00:00:00 / 00:00")
        self.current_time.setStyleSheet("color: #38BDF8; font-weight: 600; font-size: 12px; background: transparent;")
        player_controls.addWidget(self.current_time)
        left_col.addLayout(player_controls)

        # Timeline header & toolbar
        timeline_header_row = QHBoxLayout()
        timeline_title = QLabel("Video Timeline & Audio Waveforms")
        timeline_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #F1F5F9;")
        timeline_header_row.addWidget(timeline_title)
        timeline_header_row.addStretch()

        tools_def = [
            ("edit", "Sunting Teks & Judul Klip Aktif", self.open_edit_text_dialog),
            ("cut", "Potong / Tambah Klip Manual di Detik Ini", self.open_manual_clip_dialog),
            ("ratio", "Ganti Rasio Video (9:16 / 1:1 / 16:9)", self.cycle_review_ratio),
            ("reset", "Kembalikan Putaran ke Awal Klip", self.reset_review_timeline),
            ("zoom", "Zoom / Sesuaikan Skala Tampilan Video (Fit/Crop)", self.toggle_review_zoom),
        ]
        for icon_key, tip, callback in tools_def:
            tool_btn = QPushButton()
            tool_btn.setIcon(make_vector_icon(icon_key, "#CBD5E1", 20))
            tool_btn.setIconSize(QSize(16, 16))
            tool_btn.setToolTip(tip)
            tool_btn.setFixedSize(28, 28)
            tool_btn.setStyleSheet(
                "QPushButton { background: #162030; border: 1px solid #28374F; "
                "border-radius: 4px; padding: 0px; margin: 0px; text-align: center; } "
                "QPushButton:hover { background: #28374F; }"
            )
            tool_btn.clicked.connect(callback)
            timeline_header_row.addWidget(tool_btn)
        left_col.addLayout(timeline_header_row)

        # Multi-track Timeline Widget
        self.timeline_widget = TimelineWidget()
        self.timeline_widget.seekRequested.connect(self.seek_review_video)
        left_col.addWidget(self.timeline_widget)

        main_layout.addLayout(left_col, 58)

        # =========================================================================
        # RIGHT COLUMN: DAFTAR KLIP OTOMATIS
        # =========================================================================
        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        right_title = QLabel("Daftar Klip Otomatis")
        right_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #FFFFFF; letter-spacing: 0.5px;")
        right_col.addWidget(right_title)

        self.review_clip_count_label = QLabel("Daftar Klip Otomatis (0)")
        self.review_clip_count_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #94A3B8;")
        right_col.addWidget(self.review_clip_count_label)

        # Scrollable container for clip cards
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

        # Action buttons below list
        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(10)
        self.edit_text_button = QPushButton("Sunting Teks")
        self.edit_text_button.setMinimumHeight(38)
        self.edit_text_button.clicked.connect(self.open_edit_text_dialog)
        btn_row1.addWidget(self.edit_text_button)

        self.add_manual_button = QPushButton("Tambah Klip Manual")
        self.add_manual_button.setMinimumHeight(38)
        self.add_manual_button.clicked.connect(self.open_manual_clip_dialog)
        btn_row1.addWidget(self.add_manual_button)
        right_col.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        btn_back_review = QPushButton("✕ Batal & Edit Pengaturan")
        btn_back_review.setMinimumHeight(42)
        btn_back_review.setMinimumWidth(180)
        btn_back_review.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                border: 1px solid #334155;
                color: #f1f5f9;
                font-weight: 600;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #334155;
                color: #ffffff;
            }
        """)
        btn_back_review.clicked.connect(self.cancel_to_edit_step2)
        btn_row2.addWidget(btn_back_review)

        self.render_button = QPushButton("Render Final")
        self.render_button.setObjectName("primary")
        self.render_button.setMinimumHeight(42)
        self.render_button.setStyleSheet("font-weight: 700; font-size: 13px; padding: 0 24px;")
        self.render_button.clicked.connect(self.render_final)
        btn_row2.addWidget(self.render_button, 1)
        right_col.addLayout(btn_row2)

        # Compatibility fields
        self.manual_start = QLineEdit("00:00")
        self.manual_end = QLineEdit("01:00")
        self.manual_title = QLineEdit()
        self.auto_clips_layout = QVBoxLayout()
        self.manual_clips_layout = QVBoxLayout()
        self.auto_preview_button = QPushButton()
        self.auto_preview_button.setVisible(False)
        self.preview_player = QMediaPlayer(self)
        self.preview_status = QLabel("")
        self.review_status = QLabel("")

        main_layout.addLayout(right_col, 42)
        scroll.setWidget(page)
        return scroll

    def build_results_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        page = QWidget()
        page.setObjectName("pageContent")
        page.setMinimumWidth(860)
        page.setMaximumWidth(1320)

        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(20)

        # Top Header stats row
        header_row = QHBoxLayout()
        header_row.setSpacing(20)

        left_stat = QVBoxLayout()
        left_stat.setSpacing(4)
        self.results_title = QLabel("10 KLIP SELESAI")
        self.results_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #FFFFFF;")
        left_stat.addWidget(self.results_title)

        self.results_folder_label = QLabel("Folder Hasil: ...")
        self.results_folder_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
        left_stat.addWidget(self.results_folder_label)
        header_row.addLayout(left_stat, 1)

        # Ringkasan Ekspor Box
        summary_card = QFrame()
        summary_card.setStyleSheet("background: #131926; border: 1px solid #233148; border-radius: 8px; padding: 10px 16px;")
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

        sub_header = QLabel("Klip yang Berhasil Diekspor")
        sub_header.setStyleSheet("font-size: 14px; font-weight: 600; color: #F1F5F9;")
        main_layout.addWidget(sub_header)

        # Grid of exported cards
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

        # Bottom prominent button: BUKA FOLDER HASIL
        btn_center_box = QHBoxLayout()
        btn_center_box.addStretch()

        self.open_results_button = QPushButton("📁 BUKA FOLDER HASIL")
        self.open_results_button.setObjectName("primary")
        self.open_results_button.setMinimumHeight(46)
        self.open_results_button.setStyleSheet("font-size: 14px; font-weight: 800; padding: 0 36px; border-radius: 8px;")
        self.open_results_button.clicked.connect(self.open_results_folder)
        btn_center_box.addWidget(self.open_results_button)

        btn_center_box.addStretch()
        main_layout.addLayout(btn_center_box)

        self.results_list = QListWidget()
        self.results_list.setVisible(False)

        scroll.setWidget(page)
        return scroll

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
            whisper_model=self.whisper_combo.currentData(),
            video_encoder=self.encoder_combo.currentData() if hasattr(self, "encoder_combo") else "auto",
            custom_prompt=self.custom_prompt_edit.text().strip(),
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
            subtitle_max_lines=self.subtitle_lines_combo.currentData() if hasattr(self, "subtitle_lines_combo") else 2,
            subtitle_font_size=self.subtitle_size_combo.currentData() if hasattr(self, "subtitle_size_combo") else 14,
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
        self.progress_panel.setVisible(True)
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
            if hasattr(self, "preview_placeholder"):
                self.preview_placeholder.setVisible(False)
            self.update_create_preview()
            self.update_segment_estimate()
        self.progress_panel.setVisible(False)
        for widget in self.clip_stage_widgets:
            widget.setVisible(True)
        self.set_create_inputs_locked(False)
        self.switch_tab(2)

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
        gemini_key = self.gemini_key_edit.text().strip()
        if gemini_key:
            import os
            os.environ["GEMINI_API_KEY"] = gemini_key
            core.GEMINI_API_KEY = gemini_key
            QSettings("VanClipper", "VanClipper").setValue("gemini_api_key", gemini_key)
            QSettings("VanClipper", "VanClipper").setValue("gemini_api_key_saved", True)

        if self.ai_provider_combo.currentData() == "gemini" or self.whisper_combo.currentData() == "gemini":
            if not gemini_key:
                QMessageBox.warning(self, "API Key Kosong", "Masukkan Gemini API Key kamu terlebih dahulu di bagian Otak AI (dapatkan gratis di aistudio.google.com).")
                return
            if self.ai_provider_combo.currentData() == "gemini":
                self.active_model_key = "gemini"
        elif self.use_llm.isChecked():
            current_model = self.model_file_combo.currentData()
            if not current_model:
                QMessageBox.warning(self, "Pilih model GGUF", "Pilih salah satu file .gguf dari dropdown Model aktif terlebih dahulu.")
                return
            if current_model == "gemini" and not self.gemini_key_edit.text().strip():
                QMessageBox.warning(self, "API Key Kosong", "Masukkan Gemini API Key terlebih dahulu.")
                return
        self.apply_model_paths()
        self.save_model_paths()
        self.current_options = options
        with core.JOBS_LOCK:
            core.JOB_OPTIONS[self.current_job_id] = options
        self.set_create_inputs_locked(True)
        self.tabs.setTabEnabled(3, False)
        self.tabs.setTabEnabled(4, False)
        self.progress_panel.setVisible(True)
        self.progress.setValue(0)
        self.total_percent_label.setText("0%")
        self.sub_progress.setValue(0)
        self.sub_percent_label.setText("0%")
        self.status_label.setText("Memulai proses...")
        self.sub_status_label.setText("Menyiapkan tahapan ekstraksi audio...")
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
        
        self.progress.setValue(overall_pct)
        self.total_percent_label.setText(f"{overall_pct}%")
        self.status_label.setText(msg)
        
        self.sub_progress.setValue(sub_pct)
        self.sub_percent_label.setText(f"{sub_pct}%")
        self.sub_status_label.setText(sub_msg or msg)
        if msg != getattr(self, "_last_logged_msg", None):
            self._last_logged_msg = msg
            self.log_terminal(f"[{overall_pct}%] {msg}")
        if snapshot["status"] == "downloaded":
            self.poll_timer.stop()
            self.show_clip_stage(snapshot.get("source_path", ""), snapshot["message"])
        elif snapshot["status"] == "awaiting_render":
            self.poll_timer.stop()
            self.show_review(snapshot)
        elif snapshot["status"] == "completed":
            self.poll_timer.stop()
            self.show_results(snapshot)
        elif snapshot["status"] == "canceled":
            self.poll_timer.stop()
            self.set_create_inputs_locked(False)
            self.status_label.setText("Proses dibatalkan.")
            self.sub_status_label.setText("Pengaturan klip telah dibuka kembali.")
            self.log_terminal("Proses render telah dibatalkan.")
        elif snapshot["status"] == "failed":
            self.poll_timer.stop()
            self.download_button.setEnabled(True)
            self.local_file_button.setEnabled(True)
            self.set_create_inputs_locked(False)
            self.render_button.setEnabled(True)
            self.add_manual_button.setEnabled(True)
            self.log_terminal(f"ERROR: {snapshot.get('error') or snapshot['message']}")
            QMessageBox.critical(self, "Proses gagal", snapshot.get("error") or snapshot["message"])

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
        if not self.current_options:
            try:
                self.current_options = core.JOB_OPTIONS.get(job.get("id")) or self.build_options()
            except Exception:
                self.current_options = None
        ai_count = sum(1 for clip in job["clips"] if clip.get("source") == "ai")
        manual_count = sum(1 for clip in job["clips"] if clip.get("source") == "manual")
        total_clips = len(job["clips"])
        self.review_clip_count_label.setText(f"Daftar Klip Otomatis ({total_clips})")
        self.review_status.setText(
            f"{ai_count} clip AI siap direview · {manual_count} clip manual · tambahkan manual bila perlu"
        )
        self.active_transcript = self.build_timed_cues(job.get("transcript") or [])
        subtitles_available = bool(self.current_options and self.current_options.subtitle_style != "none")
        self.source_subtitle_overlay.setVisible(subtitles_available and bool(self.active_transcript))
        source_path = Path(job.get("source_path", ""))
        source_path_str = str(source_path) if source_path.exists() else ""
        if source_path.exists():
            self.player.setSource(QUrl.fromLocalFile(source_path_str))
            dur_sec = core.media_duration(source_path, 0.0)
            if hasattr(self, "timeline_widget"):
                self.timeline_widget.set_duration(int(dur_sec * 1000))
        self.update_realtime_subtitle(0.0)
        self.auto_preview_running = False
        self.auto_preview_index = 0
        self.auto_preview_items = []
        self.auto_preview_button.setText("Mulai preview clip AI")

        # Clear existing review cards
        while self.review_cards_layout.count():
            item = self.review_cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.review_card_widgets = []
        self.review_entries = []
        for index, clip in enumerate(job["clips"]):
            entry = {
                "title": f"{index+1:02d} · {clip['title']} · {format_time(clip['start'])}–{format_time(clip['end'])}",
                "path": str(core.clip_result_dir(
                    Path(job.get("result_dir") or core.job_result_dir(job["id"])),
                    clip["id"],
                    clip["title"],
                ) / "clip.mp4"),
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
        dialog = EditTextDialog(clip.get("title", ""), clip.get("caption", ""), self)
        if dialog.exec():
            new_title, new_caption = dialog.get_data()
            clip["title"] = new_title
            clip["caption"] = new_caption
            if self.current_job_id:
                with core.JOBS_LOCK:
                    core_job = core.JOBS.get(self.current_job_id)
                    if core_job and idx < len(core_job.clips):
                        core_job.clips[idx].title = new_title
                        core_job.clips[idx].caption = new_caption
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

    def cycle_review_ratio(self) -> None:
        if not self.current_options:
            return
        ratios = ["9:16", "1:1", "16:9"]
        current = getattr(self.current_options, "aspect_ratio", "9:16")
        idx = ratios.index(current) if current in ratios else 0
        new_ratio = ratios[(idx + 1) % len(ratios)]
        self.current_options.aspect_ratio = new_ratio
        if hasattr(self, "aspect_combo"):
            idx_combo = self.aspect_combo.findData(new_ratio)
            if idx_combo >= 0:
                self.aspect_combo.setCurrentIndex(idx_combo)
        self.update_review_subtitle_position()
        if hasattr(self, "review_status"):
            self.review_status.setText(f"Rasio video diubah ke {new_ratio} · Pengaturan tersimpan")

    def reset_review_timeline(self) -> None:
        if hasattr(self, "current_review_job") and self.current_review_job:
            clips = self.current_review_job.get("clips", [])
            idx = getattr(self, "selected_review_clip_index", 0)
            if 0 <= idx < len(clips):
                start_sec = clips[idx].get("start", 0.0)
                self.seek_review_video(int(start_sec * 1000))
                if hasattr(self, "review_status"):
                    self.review_status.setText(f"Putaran dikembalikan ke awal klip {idx + 1:02d} ({format_time(start_sec)})")
                return
        self.seek_review_video(0)
        if hasattr(self, "review_status"):
            self.review_status.setText("Putaran dikembalikan ke detik 00:00")

    def toggle_review_zoom(self) -> None:
        if hasattr(self, "video_widget") and hasattr(self.video_widget, "aspect_ratio_mode"):
            if self.video_widget.aspect_ratio_mode == Qt.AspectRatioMode.KeepAspectRatio:
                self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
                if hasattr(self, "review_status"):
                    self.review_status.setText("Mode Zoom: Penuh Layar (Crop)")
            else:
                self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
                if hasattr(self, "review_status"):
                    self.review_status.setText("Mode Zoom: Rasio Asli (Fit)")

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
            "subtitle_max_lines": self.subtitle_lines_combo.currentData() if hasattr(self, "subtitle_lines_combo") else getattr(self.current_options, "subtitle_max_lines", 2),
            "subtitle_font_size": self.subtitle_size_combo.currentData() if hasattr(self, "subtitle_size_combo") else getattr(self.current_options, "subtitle_font_size", 14),
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
        self.tabs.setTabEnabled(4, True)
        self.switch_tab(4)
        clips = job.get("clips", [])
        total_clips = len(clips)
        self.results_title.setText(f"{total_clips} KLIP SELESAI")

        result_dir = Path(job.get("result_dir") or core.job_result_dir(job["id"]))
        self.results_folder_label.setText(f"Folder Hasil: {result_dir}")

        total_dur_sec = sum(max(0.0, float(clip.get("end", 0.0)) - float(clip.get("start", 0.0))) for clip in clips)
        total_bytes = 0

        # Clear existing cards in results_grid_layout
        while self.results_grid_layout.count():
            item = self.results_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.results_list.clear()

        # Build cards in grid (3 columns)
        columns = 3
        for index, clip in enumerate(clips):
            clip_path = core.clip_result_dir(
                result_dir,
                clip["id"],
                clip["title"],
            ) / "clip.mp4"
            if clip_path.is_file():
                total_bytes += clip_path.stat().st_size

            item = QListWidgetItem(f"{clip['title']} · {format_time(clip['start'])}–{format_time(clip['end'])}")
            item.setData(Qt.ItemDataRole.UserRole, str(clip_path))
            self.results_list.addItem(item)

            card = ResultClipCardWidget(clip, clip_path, index, self.results_grid_widget)
            row = index // columns
            col = index % columns
            self.results_grid_layout.addWidget(card, row, col)

        # Update stats labels
        self.results_dur_label.setText(f"Total Durasi: {format_time(total_dur_sec)}")
        self.results_size_label.setText(f"Ukuran: {total_bytes / (1024 * 1024):.1f} MB")
        self.results_count_label.setText(f"Total Berkas: {total_clips}")

    def open_result(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

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

        self.apply_subtitle_preview_style(
            self.source_subtitle_overlay,
            self.current_options.subtitle_style,
            text=text,
            color=self.current_options.subtitle_color,
            max_lines=getattr(self.current_options, "subtitle_max_lines", 2),
        )
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
            y = int(ph * 0.08)
            label.move(max(0, x), max(0, y))
        elif position == "center":
            x = (pw - lw) // 2
            y = (ph - lh) // 2
            label.move(max(0, x), max(0, y))
        else:
            x = (pw - lw) // 2
            if ph > pw:
                y = min(ph - lh - 16, max(16, int(ph * 0.72)))
            else:
                y = max(0, ph - lh - max(16, int(ph * 0.08)))
            label.move(max(0, x), y)
        label.raise_()

    def switch_tab(self, index: int) -> None:
        if not self.tabs.isTabEnabled(index):
            return
        self.tabs.setCurrentIndex(index)
        for button_index, button in self.nav_buttons.items():
            button.setChecked(button_index == index)
        if index == 2 and hasattr(self, "create_preview_frame"):
            self.update_create_preview()
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
            QWidget { color: #0f172a; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }
            QMainWindow, QDialog, QScrollArea, QWidget#pageContent, QTabWidget::pane { background: #f8fafc; }
            QLabel { background: transparent; color: #334155; padding: 2px 6px; }
            QMainWindow { background: #f8fafc; }
            QToolBar { background: #ffffff; border-bottom: 1px solid #e2e8f0; spacing: 8px; padding: 8px 16px; }
            QLabel#brand { color: #0f172a; font-size: 16px; font-weight: 700; padding-right: 6px; letter-spacing: -0.3px; }
            QLabel#brandMeta { color: #64748b; font-size: 11px; padding-right: 16px; }
            QPushButton#navButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 7px 14px; color: #64748b; font-size: 13px; font-weight: 500; }
            QPushButton#navButton:hover { background: #f1f5f9; color: #0f172a; }
            QPushButton#navButton:checked { background: #eff6ff; border: 1px solid #bfdbfe; color: #2563eb; font-weight: 600; }
            QTabWidget::pane { background: #f8fafc; border: 0; }
            QTabBar { background: #f8fafc; }
            QTabBar::tab { background: #f8fafc; color: #64748b; padding: 10px 18px; border: 0; border-bottom: 2px solid transparent; }
            QTabBar::tab:selected { color: #2563eb; font-weight: 600; border-bottom: 2px solid #2563eb; }
            
            QGroupBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                margin-top: 14px;
                padding: 12px 14px 12px 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                top: 0px;
                padding: 2px 10px;
                color: #1e40af;
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 5px;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.2px;
            }
            
            QLabel#title { color: #0f172a; font-size: 24px; font-weight: 700; letter-spacing: -0.4px; }
            QLabel#eyebrow { color: #2563eb; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; }
            QLabel#muted, QLabel#status { color: #64748b; font-size: 12px; }
            
            QLineEdit, QComboBox, QSpinBox, QTextEdit {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 14px;
                color: #0f172a;
                font-size: 13px;
            }
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover { border-color: #94a3b8; background: #ffffff; }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #2563eb; background: #ffffff; }
            
            QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 24px; border-left: 1px solid #cbd5e1; background: #f1f5f9; border-top-right-radius: 8px; }
            QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 24px; border-left: 1px solid #cbd5e1; background: #f1f5f9; border-bottom-right-radius: 8px; }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #e2e8f0; }
            QSpinBox::up-arrow { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid #334155; }
            QSpinBox::down-arrow { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #334155; }
            
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border: 0; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; width: 0; height: 0; margin-right: 9px; }
            QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; color: #0f172a; selection-background-color: #2563eb; selection-color: #ffffff; padding: 4px; }
            
            QPushButton { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 16px; color: #334155; font-size: 13px; font-weight: 500; }
            QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; color: #0f172a; }
            QPushButton#primary { background: #2563eb; color: #ffffff; font-weight: 600; font-size: 13px; border: 1px solid #2563eb; border-radius: 8px; padding: 10px 24px; }
            QPushButton#primary:hover { background: #1d4ed8; }
            
            QCheckBox { spacing: 12px; padding: 4px 6px; color: #0f172a; font-size: 13px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid #cbd5e1; background: #ffffff; }
            QCheckBox::indicator:hover { border-color: #2563eb; }
            QCheckBox::indicator:checked { background: #2563eb; border-color: #2563eb; }
            
            QSlider::groove:horizontal { height: 6px; background: #e2e8f0; border-radius: 3px; }
            QSlider::handle:horizontal { width: 14px; height: 14px; margin: -4px 0; background: #2563eb; border-radius: 7px; }
            QProgressBar { border: 0; border-radius: 4px; background: #e2e8f0; height: 6px; text-align: center; color: transparent; }
            QProgressBar::chunk { background: #2563eb; border-radius: 4px; }
            QScrollBar:vertical { background: #f8fafc; width: 14px; margin: 0px; }
            QScrollBar::handle:vertical { background: #cbd5e1; min-height: 36px; border-radius: 5px; margin: 2px; }
            QScrollBar::handle:vertical:hover { background: #94a3b8; }
            QScrollBar::handle:vertical:pressed { background: #2563eb; }
            QToolTip { background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; padding: 6px 10px; border-radius: 6px; }
            """
        return """
        /* Canvas & Deep Neutral Dark Background */
        QWidget { color: #f1f5f9; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }
        QMainWindow, QDialog, QScrollArea, QWidget#pageContent, QTabWidget::pane { background: #0b0e14; }
        QLabel { background: transparent; color: #cbd5e1; padding: 2px 6px; }
        QMainWindow { background: #0b0e14; }
        QToolBar { background: #0f1420; border-bottom: 1px solid #1e293b; spacing: 8px; padding: 8px 16px; }
        QLabel#brand { color: #f8fafc; font-size: 16px; font-weight: 700; padding-right: 6px; letter-spacing: -0.3px; }
        QLabel#brandMeta { color: #8292a8; font-size: 11px; padding-right: 16px; font-weight: 500; }
        QPushButton#navButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 7px 16px; color: #94a3b8; font-size: 13px; font-weight: 500; }
        QPushButton#navButton:hover { background: #162030; color: #f1f5f9; }
        QPushButton#navButton:checked { background: #1c283c; border: 1px solid #3b82f6; color: #60a5fa; font-weight: 600; }
        QTabWidget::pane { background: #0b0e14; border: 0; }
        QTabBar { background: #0b0e14; }
        QTabBar::tab { background: #0b0e14; color: #64748b; padding: 10px 18px; border: 0; border-bottom: 2px solid transparent; }
        QTabBar::tab:selected { color: #60a5fa; font-weight: 600; border-bottom: 2px solid #3b82f6; }
        
        /* Elevated Cards with Crisp Boundaries & Badge Headers */
        QGroupBox {
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 12px;
            margin-top: 16px;
            padding: 14px 16px 14px 16px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 16px;
            top: -2px;
            padding: 3px 12px;
            color: #93c5fd;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        
        QLabel#title { color: #f8fafc; font-size: 24px; font-weight: 700; letter-spacing: -0.4px; }
        QLabel#eyebrow { color: #60a5fa; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; }
        QLabel#muted, QLabel#status { color: #94a3b8; font-size: 12px; }
        
        /* High-Contrast Inset Input Controls */
        QLineEdit, QComboBox, QSpinBox, QTextEdit {
            background: #0b0f19;
            border: 1px solid #273549;
            border-radius: 8px;
            padding: 7px 12px;
            color: #f8fafc;
            font-size: 13px;
        }
        QLineEdit:hover, QComboBox:hover, QSpinBox:hover {
            border-color: #3b82f6;
            background: #0e1422;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
            border: 1px solid #60a5fa;
            background: #0f172a;
        }
        
        QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border: 0; }
        QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #94a3b8; width: 0; height: 0; margin-right: 9px; }
        QComboBox QAbstractItemView {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            color: #f1f5f9;
            selection-background-color: #2563eb;
            selection-color: #ffffff;
            padding: 4px;
        }
        
        /* Crisp High-Contrast Stepper Arrows */
        QSpinBox::up-button {
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 24px;
            border-left: 1px solid #28374f;
            background: #141c2c;
            border-top-right-radius: 8px;
        }
        QSpinBox::down-button {
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 24px;
            border-left: 1px solid #28374f;
            background: #141c2c;
            border-bottom-right-radius: 8px;
        }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {
            background: #1f2c44;
        }
        QSpinBox::up-arrow {
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid #cbd5e1;
        }
        QSpinBox::down-arrow {
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #cbd5e1;
        }
        
        /* Distinct Buttons */
        QPushButton {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 8px 16px;
            color: #e2e8f0;
            font-size: 13px;
            font-weight: 500;
        }
        QPushButton:hover {
            background: #28374d;
            border-color: #475569;
            color: #ffffff;
        }
        QPushButton#primary {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #3b82f6);
            color: #ffffff;
            font-weight: 600;
            font-size: 13px;
            border: 1px solid #3b82f6;
            border-radius: 8px;
            padding: 10px 24px;
        }
        QPushButton#primary:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #2563eb);
            border-color: #60a5fa;
        }
        QPushButton#primary:pressed { background: #1e40af; }
        QPushButton:disabled { color: #475569; background: #0e131d; border-color: #1a2332; }
        
        /* Checkboxes */
        QCheckBox { spacing: 12px; padding: 4px 6px; color: #f1f5f9; font-size: 13px; }
        QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3b4c68; background: #0c101a; }
        QCheckBox::indicator:hover { border-color: #60a5fa; }
        QCheckBox::indicator:checked { background: #2563eb; border-color: #2563eb; }
        
        /* Sliders & Timeline */
        QSlider::groove:horizontal { height: 6px; background: #1c2738; border-radius: 3px; }
        QSlider::handle:horizontal { width: 14px; height: 14px; margin: -4px 0; background: #3b82f6; border-radius: 7px; }
        QSlider::handle:horizontal:hover { background: #60a5fa; }
        
        QProgressBar { border: 0; border-radius: 4px; background: #0c101a; height: 6px; text-align: center; color: transparent; }
        QProgressBar::chunk { background: #3b82f6; border-radius: 4px; }
        
        /* Lists & Cards */
        QListWidget { background: #131926; border: 1px solid #233148; border-radius: 10px; padding: 6px; }
        QListWidget::item { padding: 10px; border-bottom: 1px solid #1a2436; border-radius: 6px; }
        QListWidget::item:selected { background: #1e2b40; color: #ffffff; }
        QFrame#clipCard { background: #141c2b; border: 1px solid #25344d; border-radius: 10px; }
        QLabel#clipCardInfo { color: #e2e8f0; }
        QPushButton#clipPlay { background: #1c2738; color: #93c5fd; border: 1px solid #2e4162; padding: 7px 14px; border-radius: 6px; }
        
        /* Preview Canvas */
        QFrame#previewCanvas { background: #0c101a; border: 1px solid #233148; border-radius: 10px; }
        
        /* Splitter Handle */
        QSplitter::handle:horizontal {
            background: #141c2c;
            width: 8px;
            margin: 0px 2px;
            border-radius: 4px;
        }
        QSplitter::handle:horizontal:hover {
            background: #3b82f6;
        }
        QSplitter::handle:horizontal:pressed {
            background: #60a5fa;
        }
        
        /* Scrollbar */
        QScrollBar:vertical { background: #0a0d14; width: 14px; margin: 0px; }
        QScrollBar::handle:vertical { background: #253348; min-height: 36px; border-radius: 5px; margin: 2px; }
        QScrollBar::handle:vertical:hover { background: #384c6c; }
        QScrollBar::handle:vertical:pressed { background: #3b82f6; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        QToolTip { background: #162030; color: #f8fafc; border: 1px solid #2d3e5b; padding: 6px 10px; border-radius: 6px; }
        """

    def set_create_inputs_locked(self, locked: bool) -> None:
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
        self.set_create_inputs_locked(False)
        self.status_label.setText("Proses dibatalkan.")
        self.sub_status_label.setText("Pengaturan klip telah dibuka kembali.")
        self.progress.setValue(0)
        self.total_percent_label.setText("0%")
        self.sub_progress.setValue(0)
        self.sub_percent_label.setText("0%")
        self.log_terminal("Proses render dibatalkan. Pengaturan klip dibuka kembali.")

    def cancel_to_edit_step2(self) -> None:
        self.cancel_current_process()
        self.switch_tab(2)

    def build_terminal_drawer(self) -> QWidget:
        drawer = QFrame()
        drawer.setObjectName("terminalDrawer")
        drawer.setFixedHeight(170)
        drawer.setStyleSheet("""
            QFrame#terminalDrawer {
                background: #090d16;
                border-top: 1px solid #1e293b;
            }
        """)
        layout = QVBoxLayout(drawer)
        layout.setContentsMargins(12, 6, 12, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("⌨ Terminal & Log Sistem")
        lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8; background: transparent;")
        header.addWidget(lbl)
        header.addStretch()

        btn_clear = QPushButton("Bersihkan")
        btn_clear.setFixedHeight(22)
        btn_clear.setStyleSheet("background: #1e293b; color: #cbd5e1; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: 600;")
        btn_clear.clicked.connect(lambda: self.terminal_box.clear() if hasattr(self, "terminal_box") else None)
        header.addWidget(btn_clear)

        btn_close = QPushButton("✕ Tutup")
        btn_close.setFixedHeight(22)
        btn_close.setStyleSheet("background: #1e293b; color: #cbd5e1; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: 600;")
        btn_close.clicked.connect(self.toggle_terminal_drawer)
        header.addWidget(btn_close)
        layout.addLayout(header)

        self.terminal_box = QPlainTextEdit()
        self.terminal_box.setReadOnly(True)
        self.terminal_box.setFont(QFont("Consolas", 10))
        self.terminal_box.setStyleSheet("""
            QPlainTextEdit {
                background: #050811;
                color: #38bdf8;
                border: 1px solid #172554;
                border-radius: 6px;
                padding: 6px;
                font-family: Consolas, 'Cascadia Code', monospace;
            }
        """)
        self.terminal_box.appendPlainText("[SYSTEM] ENCLip Terminal siap. Log proses akan muncul di sini...")
        layout.addWidget(self.terminal_box, 1)
        return drawer

    def toggle_terminal_drawer(self) -> None:
        if hasattr(self, "terminal_drawer"):
            visible = not self.terminal_drawer.isVisible()
            self.terminal_drawer.setVisible(visible)
            if hasattr(self, "terminal_toggle_btn"):
                self.terminal_toggle_btn.setChecked(visible)

    def log_terminal(self, msg: str) -> None:
        if hasattr(self, "terminal_box"):
            import datetime
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.terminal_box.appendPlainText(f"[{ts}] {msg}")
            sb = self.terminal_box.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

    def build_models_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")

        page = QWidget()
        page.setObjectName("pageContent")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 20, 28, 24)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        eyebrow = QLabel("DOWNLOAD & KELOLA AI OFFLINE")
        eyebrow.setObjectName("eyebrow")
        header_text.addWidget(eyebrow)

        title = QLabel("Katalog Model AI Lokal")
        title.setObjectName("title")
        header_text.addWidget(title)

        subtitle = QLabel("Unduh model AI lokal untuk transkripsi audio dan deteksi klip 100% offline tanpa kuota internet.")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 13px;")
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, 1)

        btn_open_folder = QPushButton("📁 Buka Folder Model")
        btn_open_folder.setFixedHeight(36)
        btn_open_folder.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                border: 1px solid #334155;
                color: #e2e8f0;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #334155;
                color: #ffffff;
            }
        """)
        btn_open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT / "models"))))
        header_row.addWidget(btn_open_folder)
        layout.addLayout(header_row)

        self.model_cards: dict[str, dict[str, Any]] = {}
        models_dir = ROOT / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        for m in MODELS_CATALOG:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #0d121c;
                    border: 1px solid #1e293b;
                    border-radius: 10px;
                    padding: 12px;
                }
                QFrame:hover {
                    border-color: #2563eb;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(8)

            top_row = QHBoxLayout()
            m_title = QLabel(m["name"])
            m_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
            top_row.addWidget(m_title)

            m_badge = QLabel(m["badge"])
            m_badge.setStyleSheet("background: #1e293b; color: #38bdf8; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600;")
            top_row.addWidget(m_badge)
            top_row.addStretch()

            status_lbl = QLabel("")
            status_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
            top_row.addWidget(status_lbl)

            btn_dl = QPushButton("⬇ Unduh Model")
            btn_dl.setFixedHeight(32)
            btn_dl.setStyleSheet("""
                QPushButton {
                    background: #2563eb;
                    color: #ffffff;
                    border-radius: 6px;
                    padding: 4px 14px;
                    font-weight: 600;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #1d4ed8;
                }
                QPushButton:disabled {
                    background: #1e293b;
                    color: #64748b;
                }
            """)
            top_row.addWidget(btn_dl)
            card_layout.addLayout(top_row)

            m_desc = QLabel(m["desc"])
            m_desc.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.4;")
            card_layout.addWidget(m_desc)

            m_specs = QLabel(m["specs"])
            m_specs.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 600;")
            card_layout.addWidget(m_specs)

            prog_row = QHBoxLayout()
            prog_bar = QProgressBar()
            prog_bar.setRange(0, 100)
            prog_bar.setValue(0)
            prog_bar.setFixedHeight(6)
            prog_bar.setTextVisible(False)
            prog_bar.setStyleSheet("QProgressBar { background: #1e293b; border-radius: 3px; border: 0; } QProgressBar::chunk { background: #38bdf8; border-radius: 3px; }")
            prog_bar.setVisible(False)
            prog_row.addWidget(prog_bar, 1)

            prog_info = QLabel("")
            prog_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
            prog_info.setVisible(False)
            prog_row.addWidget(prog_info)
            card_layout.addLayout(prog_row)

            is_installed = False
            if m["type"] == "gguf":
                target_p = models_dir / m["filename"]
                is_installed = target_p.exists() and target_p.stat().st_size > 1024 * 1024
            elif m["type"] == "whisper":
                try:
                    import huggingface_hub
                    cached = list(Path(huggingface_hub.constants.HF_HUB_CACHE).glob(f"*{m['url']}*")) if Path(huggingface_hub.constants.HF_HUB_CACHE).exists() else []
                    is_installed = bool(cached)
                except Exception:
                    is_installed = False

            if is_installed:
                status_lbl.setText("✓ Sudah Terpasang")
                status_lbl.setStyleSheet("color: #10b981; font-weight: 700; font-size: 12px;")
                btn_dl.setText("Pasang Ulang")
                btn_dl.setStyleSheet("background: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 6px; padding: 4px 10px; font-size: 11px;")

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

        target_file = (ROOT / "models") / info["filename"]
        worker = ModelDownloadWorker(m_id, info["type"], info["url"], target_file)
        worker.progress_signal.connect(self.on_model_download_progress)
        worker.finished_signal.connect(self.on_model_download_finished)

        self.model_download_workers[m_id] = worker
        card["btn_dl"].setEnabled(False)
        card["btn_dl"].setText("Mengunduh...")
        card["status_lbl"].setText("Mengunduh...")
        card["status_lbl"].setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 12px;")
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
            card["status_lbl"].setText("✓ Sudah Terpasang")
            card["status_lbl"].setStyleSheet("color: #10b981; font-weight: 700; font-size: 12px;")
            card["btn_dl"].setText("Pasang Ulang")
            card["btn_dl"].setStyleSheet("background: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 6px; padding: 4px 10px; font-size: 11px;")
            self.log_terminal(f"Model {card['info']['name']} berhasil diunduh dan siap digunakan.")
            self.scan_project_models()
            QMessageBox.information(self, "Model Terpasang", f"Model {card['info']['name']} berhasil diunduh dan telah ditambahkan ke daftar model aktif!")
        else:
            card["status_lbl"].setText("✕ Gagal")
            card["status_lbl"].setStyleSheet("color: #ef4444; font-weight: 700; font-size: 12px;")
            card["btn_dl"].setText("Coba Lagi")
            card["btn_dl"].setStyleSheet("background: #2563eb; color: #ffffff; border-radius: 6px; padding: 4px 14px; font-weight: 600; font-size: 12px;")
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
    application.setFont(QFont("Segoe UI", 10))
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
