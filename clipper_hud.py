#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clipper_hud.py - ENCLip Studio Pro Minimalist HUD Widget.
=====================================================================
Widget pemantau proses editing modern, minimalis, dan sangat interaktif (UI/UX Pro Max):
- Terintegrasi dalam 1 Widget Tunggal yang dapat di-minimize dan di-maximize.
- Posisi: Pojok KANAN BAWAH desktop (di atas taskbar), membesar (maximize) ke arah ATAS.
- Mode Minimized: Floating Dynamic Island Pill ramping di kanan bawah (440x40px).
- Mode Maximized: Studio Inspector Bento Card elegan (520x520px).
- Fitur Interaktif:
  1. Unbreakable Active Stage Indicator: Tahap yang sedang berjalan di pipeline SELALU
     menyala terang (border tebal cyan elektrik + badge ● [AKTIF]), TIDAK AKAN HILANG
     meskipun pengguna sedang mengklik tahap lain untuk melihat detailnya.
  2. Stage Inspector: Menampilkan status tahap yang dipilih (Sedang Berjalan, Selesai ✓,
     atau Menunggu), lengkap dengan parameter teknis dan tombol re-sinkronisasi.
  3. 3-Tab Segmented View:
     - Tab 1: Metrik Spek (Bento Grid 2x2)
     - Tab 2: Live Console Stream (dengan filter, auto-scroll toggle, dan salin log)
     - Tab 3: Klip Siap & Berkas (Explorer klip MP4 hasil render dengan tombol putar langsung)
  4. Action Bar: Salin ringkasan ke clipboard, buka folder hasil, dan jam digital live.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
CORE_DATA_DIR = CURRENT_DIR / "Core_Data"
CORE_DATA_DIR.mkdir(parents=True, exist_ok=True)

HUD_STATUS_FILE = CORE_DATA_DIR / "hud_status.json"
HUD_PID_FILE = CORE_DATA_DIR / "hud.pid"
AUTOCLIPPER_LOG = CORE_DATA_DIR / "autoclipper_4am.log"
UPLOAD_QUEUE_FILE = CORE_DATA_DIR / "upload_queue.json"
HASIL_CLIP_DIR = CORE_DATA_DIR / "HasilClip"
HASIL_CLIP_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("ClipperHUD")

# Hubungkan ke desktop interaktif Windows
if sys.platform.startswith("win"):
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ENCLip.Studio.HUD.Widget")
        u32 = ctypes.windll.user32
        h_desk = u32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            u32.SetThreadDesktop(h_desk)
    except Exception:
        pass


def attach_to_interactive_desktop() -> None:
    """Memastikan thread terpasang ke desktop interaktif 'Default' pengguna di Windows."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            u32 = ctypes.windll.user32
            h_desk = u32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_desk:
                u32.SetThreadDesktop(h_desk)
        except Exception:
            pass


STAGE_SPECS: dict[str, dict[str, str]] = {
    "download": {
        "title": "Tahap 1: Pengunduhan Sumber 1080p",
        "engine": "yt-dlp v2025+ & FFmpeg",
        "quality": "1080p Full HD (1920x1080, ~60fps)",
        "source": "YouTube (HAS Creative)",
        "desc": "Mengunduh video 1080p dengan bitrate tertinggi tanpa downscale. Audio diekstrak sebagai 16-bit PCM WAV uncompressed untuk transkripsi akurat.",
        "badge": "1080p Source",
    },
    "transcribe": {
        "title": "Tahap 2: Transkripsi Audio & Timestamp (Whisper AI)",
        "engine": "faster-whisper (int8 quantized)",
        "quality": "Word-level Timestamp Alignment",
        "source": "WAV 16kHz Mono Stream",
        "desc": "Mendeteksi setiap kata dalam bahasa Indonesia dengan presisi milidetik. Menghasilkan teks, jeda bicara, dan segmentasi dialog.",
        "badge": "Whisper int8",
    },
    "ai": {
        "title": "Tahap 3: Kurasi Klip Viral (Gemini 2.5 Flash)",
        "engine": "Google Gemini 2.5 Flash GenAI",
        "quality": "Viral Hook Scoring & Retention Analysis",
        "source": "Transkrip Terstruktur + Metadata",
        "desc": "Menganalisis teks untuk menemukan momen hook emosional, punchline komedi, atau debat panas berdurasi 30-90 detik yang berpotensi FYP.",
        "badge": "Gemini AI",
    },
    "clip": {
        "title": "Tahap 4: Subtitle Smart Notice & Thumbnail Hook",
        "engine": "Pillow (PIL) + ASS Subtitle Engine",
        "quality": "Smart Notice (Kuning Denyut) + 1.0s Hook Banner",
        "source": "Word Timestamps & Highlight Keywords",
        "desc": "Merender teks subtitle dinamis di tengah-bawah layar dengan animasi denyut kuning kata per kata dan hook banner gelap 1 detik di awal klip.",
        "badge": "Smart Notice",
    },
    "render": {
        "title": "Tahap 5: Final Encoding & Export Video",
        "engine": "FFmpeg H.264 High Profile / AAC 320kbps",
        "quality": "1080p Full HD (16:9 Standard)",
        "source": "Klip Terpilih + Subtitle Burn-in",
        "desc": "Menggabungkan video 1080p, audio yang dinormalisasi, dan subtitle grafis menjadi berkas MP4 siap unggah ke YouTube / TikTok / Reels.",
        "badge": "FFmpeg Export",
    },
}


def update_hud_status(
    stage: str = "",
    title: str = "",
    progress: int = 0,
    detail: str = "",
    sub_progress: int = 0,
    status: str = "processing",
    **kwargs: Any,
) -> None:
    """Menyimpan status proses editing real-time ke Core_Data/hud_status.json secara thread-safe."""
    try:
        stage_labels = {
            "idle": "Standby",
            "init": "Inisialisasi",
            "scan": "Memindai YouTube",
            "download": "1. Unduh Sumber",
            "transcribe": "2. Whisper Audio",
            "ai": "3. Gemini Vision",
            "clip": "4. Subtitle & Hook",
            "render": "5. Render 1080p",
            "done": "Selesai",
            "completed": "Selesai",
            "failed": "Gagal",
        }

        current_data: dict[str, Any] = {}
        if HUD_STATUS_FILE.is_file():
            try:
                with open(HUD_STATUS_FILE, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
            except Exception:
                current_data = {}

        if not stage:
            stage = current_data.get("stage", "idle")
        if not title:
            title = current_data.get("title", "Video Podcast")
        if not detail:
            detail = current_data.get("detail", "")

        eff_stage_label = stage_labels.get(stage.lower(), stage.capitalize())

        data = {
            "status": status,
            "stage": stage.lower(),
            "stage_label": eff_stage_label,
            "title": title,
            "progress": max(0, min(100, int(progress))),
            "sub_progress": max(0, min(100, int(sub_progress))),
            "detail": detail,
            "quality": kwargs.get("quality", current_data.get("quality", "1080p Full HD")),
            "aspect_ratio": kwargs.get("aspect_ratio", current_data.get("aspect_ratio", "16:9 Standard")),
            "subtitle_mode": "Smart Notice (Kuning Denyut Aktif)",
            "subtitles_bypassed": kwargs.get("subtitles_bypassed", current_data.get("subtitles_bypassed", False)),
            "thumbnail_hook": "1.0s Dark Strip Banner",
            "active_clip_index": kwargs.get("active_clip_index", current_data.get("active_clip_index", 0)),
            "total_clips": kwargs.get("total_clips", current_data.get("total_clips", 0)),
            "channel": kwargs.get("channel", current_data.get("channel", "")),
            "updated_at": time.time(),
            "time_str": datetime.now().strftime("%H:%M:%S WIB"),
        }

        tmp_file = HUD_STATUS_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, HUD_STATUS_FILE)
    except Exception as exc:
        logger.warning(f"Gagal update_hud_status: {exc}")


def is_hud_running() -> bool:
    """Mengecek apakah proses window HUD sedang berjalan."""
    if not HUD_PID_FILE.is_file():
        return False
    try:
        with open(HUD_PID_FILE, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        if sys.platform.startswith("win"):
            import ctypes
            import ctypes.wintypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if handle:
                exit_code = ctypes.wintypes.DWORD()
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel32.CloseHandle(handle)
                if exit_code.value == 259:
                    return True
            try:
                HUD_PID_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            return False
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        try:
            HUD_PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def launch_hud_process() -> None:
    """Menjalankan proses HUD di interactive desktop pengguna jika belum aktif (tanpa console window)."""
    if is_hud_running():
        return
    try:
        py_exe = sys.executable
        if py_exe.lower().endswith("python.exe"):
            pyw = Path(py_exe).with_name("pythonw.exe")
            if pyw.is_file():
                py_exe = str(pyw)
        cmd = [py_exe, str(CURRENT_DIR / "clipper_hud.py")]
        if sys.platform.startswith("win"):
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            si.lpDesktop = r"WinSta0\Default"
            subprocess.Popen(
                cmd,
                startupinfo=si,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                cwd=str(CURRENT_DIR),
            )
        else:
            subprocess.Popen(cmd, start_new_session=True, cwd=str(CURRENT_DIR))
    except Exception as exc:
        logger.warning(f"Tidak dapat meluncurkan clipper_hud.py: {exc}")


# =====================================================================
# PYQT6 MODERN MINIMALIST WIDGET IMPLEMENTATION
# =====================================================================

try:
    from PyQt6.QtCore import (
        QEasingCurve,
        QParallelAnimationGroup,
        QPoint,
        QPropertyAnimation,
        QRect,
        QSize,
        Qt,
        QTimer,
    )
    from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
    from PyQt6.QtWidgets import (
        QApplication,
        QFrame,
        QGraphicsDropShadowEffect,
        QGraphicsOpacityEffect,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


def ensure_system_fonts() -> None:
    """Memastikan font sistem Windows terdaftar di Qt."""
    if not PYQT_AVAILABLE:
        return
    for fp in ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/consola.ttf"]:
        if os.path.isfile(fp):
            try:
                QFontDatabase.addApplicationFont(fp)
            except Exception:
                pass


if PYQT_AVAILABLE:

    class ENCLipHUDWidget(QWidget):
        """
        Widget Pemantau Studio Modern, Minimalis, dan Sangat Interaktif (UI/UX Pro Max).
        - Mode 0 (Mini): Dynamic Island Pill di KANAN BAWAH (440 x 40 px).
        - Mode 1 (Expanded): Studio Bento Card (520 x 520 px) membesar KE ATAS.
        """

        MODE_MINI = 0
        MODE_EXPANDED = 1

        def __init__(self) -> None:
            super().__init__()
            ensure_system_fonts()

            try:
                with open(HUD_PID_FILE, "w", encoding="utf-8") as f:
                    f.write(str(os.getpid()))
            except Exception:
                pass

            self.current_mode = self.MODE_MINI
            self.last_status_mtime = 0.0
            self.last_log_pos = 0
            self.auto_scroll_log = True

            # STATE TERPISAH: Tahap yang sedang jalan di pipeline vs tahap yang dipilih untuk diinspeksi
            self.current_pipeline_stage: str = "transcribe"
            self.selected_inspect_stage: str = "transcribe"
            self.user_pinned_inspection: bool = False
            self._anim_group = None

            # Window Properties: Frameless, Always on Top, Floating Tool
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

            self._build_ui()
            self.set_mode(self.MODE_MINI, animate=False)

            # Polling status real-time setiap 700 ms
            self.sync_timer = QTimer(self)
            self.sync_timer.timeout.connect(self.sync_realtime_data)
            self.sync_timer.start(700)

            self.sync_realtime_data()

        # ==========================================
        # BUILD UI: MINI PILL & EXPANDED BENTO CARD
        # ==========================================

        def _build_ui(self) -> None:
            # ------------------------------------------
            # 1. MINI CONTAINER (DYNAMIC ISLAND PILL - 440x40 px)
            # ------------------------------------------
            self.mini_frame = QFrame(self)
            self.mini_frame.setObjectName("miniPill")
            self.mini_frame.setStyleSheet("""
                QFrame#miniPill {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141722, stop:1 #0C0E14);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 20px;
                }
                QFrame#miniPill:hover {
                    border: 1px solid rgba(56, 189, 248, 0.4);
                }
            """)

            shadow_mini = QGraphicsDropShadowEffect(self)
            shadow_mini.setBlurRadius(22)
            shadow_mini.setColor(QColor(0, 0, 0, 200))
            shadow_mini.setOffset(0, 4)
            self.mini_frame.setGraphicsEffect(shadow_mini)

            m_lay = QHBoxLayout(self.mini_frame)
            m_lay.setContentsMargins(14, 0, 10, 0)
            m_lay.setSpacing(8)

            self.mini_dot = QLabel("●")
            self.mini_dot.setStyleSheet("color: #38BDF8; font-size: 11px; background: transparent;")
            m_lay.addWidget(self.mini_dot)

            self.mini_stage = QLabel("WHISPER")
            self.mini_stage.setStyleSheet("""
                background: rgba(56, 189, 248, 0.15);
                color: #38BDF8;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 0.5px;
                padding: 2px 7px;
                border-radius: 6px;
                border: 1px solid rgba(56, 189, 248, 0.3);
            """)
            m_lay.addWidget(self.mini_stage)

            m_sep = QLabel("·")
            m_sep.setStyleSheet("color: #52525B; font-size: 12px; background: transparent;")
            m_lay.addWidget(m_sep)

            self.mini_text = QLabel("Memulai pipeline editing...")
            self.mini_text.setStyleSheet("color: #F4F4F5; font-size: 11px; font-weight: 500; background: transparent;")
            self.mini_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            m_lay.addWidget(self.mini_text, 1)

            self.mini_pct = QLabel("0%")
            self.mini_pct.setStyleSheet("""
                background: rgba(255, 255, 255, 0.06);
                color: #38BDF8;
                font-size: 11px;
                font-weight: 700;
                padding: 2px 7px;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            """)
            m_lay.addWidget(self.mini_pct)

            self.mini_expand_btn = QPushButton("⤢")
            self.mini_expand_btn.setFixedSize(24, 24)
            self.mini_expand_btn.setToolTip("Perbesar Dashboard ke Atas (Maximize)")
            self.mini_expand_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.06);
                    color: #D4D4D8;
                    border: none;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(56, 189, 248, 0.3);
                    color: #FFFFFF;
                }
            """)
            self.mini_expand_btn.clicked.connect(lambda: self.set_mode(self.MODE_EXPANDED))
            m_lay.addWidget(self.mini_expand_btn)

            self.mini_close_btn = QPushButton("✕")
            self.mini_close_btn.setFixedSize(22, 22)
            self.mini_close_btn.setToolTip("Sembunyikan Widget")
            self.mini_close_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #71717A;
                    border: none;
                    border-radius: 11px;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(239, 68, 68, 0.2);
                    color: #EF4444;
                }
            """)
            self.mini_close_btn.clicked.connect(self.close)
            m_lay.addWidget(self.mini_close_btn)

            self.mini_opacity = QGraphicsOpacityEffect(self.mini_frame)
            self.mini_frame.setGraphicsEffect(self.mini_opacity)

            # ------------------------------------------
            # 2. EXPANDED CONTAINER (STUDIO BENTO CARD - 520x520 px)
            # ------------------------------------------
            self.exp_frame = QFrame(self)
            self.exp_frame.setObjectName("expandedCard")
            self.exp_frame.setStyleSheet("""
                QFrame#expandedCard {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151824, stop:0.35 #0E1017, stop:1 #08090D);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-top: 1px solid rgba(255, 255, 255, 0.18);
                    border-radius: 18px;
                }
            """)

            shadow_exp = QGraphicsDropShadowEffect(self)
            shadow_exp.setBlurRadius(28)
            shadow_exp.setColor(QColor(0, 0, 0, 230))
            shadow_exp.setOffset(0, 6)
            self.exp_frame.setGraphicsEffect(shadow_exp)

            e_lay = QVBoxLayout(self.exp_frame)
            e_lay.setContentsMargins(16, 14, 16, 14)
            e_lay.setSpacing(10)

            # --- A. Header Bar ---
            h_row = QHBoxLayout()
            h_row.setSpacing(8)

            logo_lbl = QLabel("⚡ ENCLip Studio")
            logo_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 700; background: transparent;")
            h_row.addWidget(logo_lbl)

            autopilot_badge = QLabel("● 4:00 AM AUTOPILOT")
            autopilot_badge.setStyleSheet("""
                background: rgba(56, 189, 248, 0.12);
                color: #38BDF8;
                font-size: 9px;
                font-weight: 700;
                padding: 2px 7px;
                border-radius: 6px;
                border: 1px solid rgba(56, 189, 248, 0.25);
            """)
            h_row.addWidget(autopilot_badge)

            h_row.addStretch(1)

            e_lay.addLayout(h_row)

            # --- B. Hero Media Bento Box ---
            hero_box = QFrame()
            hero_box.setStyleSheet("""
                QFrame {
                    background: #0B0E14;
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 12px;
                }
            """)
            hero_lay = QVBoxLayout(hero_box)
            hero_lay.setContentsMargins(12, 10, 12, 10)
            hero_lay.setSpacing(6)

            # Meta Tags Row
            meta_row = QHBoxLayout()
            meta_row.setSpacing(6)

            self.channel_badge = QLabel("📺 HAS Creative")
            self.channel_badge.setStyleSheet("""
                background: rgba(255, 255, 255, 0.06);
                color: #E4E4E7;
                font-size: 9px;
                font-weight: 600;
                padding: 2px 7px;
                border-radius: 5px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            """)
            meta_row.addWidget(self.channel_badge)

            quality_badge = QLabel("1080p Full HD")
            quality_badge.setStyleSheet("""
                background: rgba(56, 189, 248, 0.12);
                color: #38BDF8;
                font-size: 9px;
                font-weight: 700;
                padding: 2px 7px;
                border-radius: 5px;
                border: 1px solid rgba(56, 189, 248, 0.3);
            """)
            meta_row.addWidget(quality_badge)

            aspect_badge = QLabel("16:9 Standard")
            aspect_badge.setStyleSheet("""
                background: rgba(255, 255, 255, 0.05);
                color: #A1A1AA;
                font-size: 9px;
                font-weight: 600;
                padding: 2px 6px;
                border-radius: 5px;
            """)
            meta_row.addWidget(aspect_badge)

            sub_style_badge = QLabel("Smart Notice (Kuning Denyut)")
            sub_style_badge.setStyleSheet("""
                background: rgba(234, 179, 8, 0.12);
                color: #FACC15;
                font-size: 9px;
                font-weight: 700;
                padding: 2px 7px;
                border-radius: 5px;
                border: 1px solid rgba(234, 179, 8, 0.25);
            """)
            meta_row.addWidget(sub_style_badge)

            meta_row.addStretch(1)

            # Prominent Live Pipeline Stage Chip
            self.hero_stage_badge = QLabel("● PROSES: 2. WHISPER")
            self.hero_stage_badge.setStyleSheet("""
                background: rgba(56, 189, 248, 0.18);
                color: #38BDF8;
                font-size: 9px;
                font-weight: 800;
                padding: 2px 8px;
                border-radius: 5px;
                border: 1px solid #38BDF8;
            """)
            meta_row.addWidget(self.hero_stage_badge)

            hero_lay.addLayout(meta_row)

            # Video Title
            self.exp_title = QLabel("Memuat judul video...")
            self.exp_title.setStyleSheet("color: #F4F4F5; font-size: 12px; font-weight: 700; background: transparent;")
            self.exp_title.setWordWrap(False)
            hero_lay.addWidget(self.exp_title)

            # Progress Bar
            self.exp_bar = QProgressBar()
            self.exp_bar.setFixedHeight(6)
            self.exp_bar.setTextVisible(False)
            self.exp_bar.setStyleSheet("""
                QProgressBar {
                    background: #11141B;
                    border: none;
                    border-radius: 3px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8);
                    border-radius: 3px;
                }
            """)
            hero_lay.addWidget(self.exp_bar)

            # Sub-row Progress Info
            stat_sub_row = QHBoxLayout()
            self.exp_detail_lbl = QLabel("Menginisialisasi...")
            self.exp_detail_lbl.setStyleSheet("color: #71717A; font-size: 10px; font-weight: 500; background: transparent;")
            stat_sub_row.addWidget(self.exp_detail_lbl, 1)

            self.exp_pct_lbl = QLabel("0%")
            self.exp_pct_lbl.setStyleSheet("color: #38BDF8; font-size: 11px; font-weight: 700; background: transparent;")
            stat_sub_row.addWidget(self.exp_pct_lbl)

            hero_lay.addLayout(stat_sub_row)
            e_lay.addWidget(hero_box)

            # --- C. Interactive Stepper Pipeline (Clickable Chips) ---
            step_header_row = QHBoxLayout()
            step_title_lbl = QLabel("PIPELINE STEPPER · Klik tahap untuk inspeksi teknis:")
            step_title_lbl.setStyleSheet("color: #52525B; font-size: 9px; font-weight: 700; letter-spacing: 0.6px;")
            step_header_row.addWidget(step_title_lbl)

            step_header_row.addStretch(1)

            self.btn_resync_insp = QPushButton("↺ Ikuti Tahap Aktif")
            self.btn_resync_insp.setToolTip("Kembalikan inspeksi otomatis mengikuti proses aktif")
            self.btn_resync_insp.setFixedHeight(18)
            self.btn_resync_insp.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #71717A;
                    font-size: 9px;
                    border: none;
                    padding: 0 4px;
                }
                QPushButton:hover {
                    color: #38BDF8;
                }
            """)
            self.btn_resync_insp.clicked.connect(self._resync_to_active_stage)
            step_header_row.addWidget(self.btn_resync_insp)

            e_lay.addLayout(step_header_row)

            self.step_row = QHBoxLayout()
            self.step_row.setSpacing(5)

            self.step_keys = ["download", "transcribe", "ai", "clip", "render"]
            self.step_buttons: dict[str, QPushButton] = {}
            step_labels = ["1. Unduh", "2. Whisper", "3. AI Viral", "4. Subtitle", "5. Render"]

            for key, label in zip(self.step_keys, step_labels):
                btn = QPushButton(label)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(24)
                btn.clicked.connect(lambda checked, k=key: self.inspect_stage(k))
                self.step_buttons[key] = btn
                self.step_row.addWidget(btn)

            e_lay.addLayout(self.step_row)

            # --- D. Interactive Stage Inspector Card ---
            self.stage_inspector_box = QFrame()
            self.stage_inspector_box.setStyleSheet("""
                QFrame {
                    background: #0B0E15;
                    border: 1px solid rgba(56, 189, 248, 0.22);
                    border-radius: 9px;
                }
            """)
            insp_lay = QVBoxLayout(self.stage_inspector_box)
            insp_lay.setContentsMargins(10, 8, 10, 8)
            insp_lay.setSpacing(4)

            insp_top = QHBoxLayout()
            self.insp_title = QLabel("Tahap 2: Whisper AI Audio Transcription")
            self.insp_title.setStyleSheet("color: #38BDF8; font-size: 11px; font-weight: 700;")
            insp_top.addWidget(self.insp_title)

            insp_top.addStretch(1)

            # Badge Status Hubungan Tahap (Sedang Berjalan / Selesai / Menunggu)
            self.insp_status_tag = QLabel("● SEDANG BERJALAN SEKARANG")
            self.insp_status_tag.setStyleSheet("""
                background: rgba(56, 189, 248, 0.2);
                color: #38BDF8;
                font-size: 9px;
                font-weight: 800;
                padding: 2px 8px;
                border-radius: 5px;
                border: 1px solid #38BDF8;
            """)
            insp_top.addWidget(self.insp_status_tag)

            self.insp_engine_badge = QLabel("faster-whisper int8")
            self.insp_engine_badge.setStyleSheet("""
                background: rgba(255, 255, 255, 0.06);
                color: #A1A1AA;
                font-size: 9px;
                font-weight: 600;
                padding: 2px 6px;
                border-radius: 4px;
            """)
            insp_top.addWidget(self.insp_engine_badge)
            insp_lay.addLayout(insp_top)

            self.insp_desc = QLabel("Memproses transkripsi audio percakapan dengan model Whisper int8...")
            self.insp_desc.setStyleSheet("color: #94A3B8; font-size: 10px; line-height: 1.3;")
            self.insp_desc.setWordWrap(True)
            insp_lay.addWidget(self.insp_desc)

            e_lay.addWidget(self.stage_inspector_box)

            # --- E. 3-Tab Segmented View Switcher ---
            tab_bar = QHBoxLayout()
            tab_bar.setSpacing(6)

            self.tab_btn_metrics = QPushButton("📊 Metrik Spek")
            self.tab_btn_log = QPushButton("📜 Live Console Log")
            self.tab_btn_clips = QPushButton("🎬 Klip Siap Berkas")

            for i, tb in enumerate([self.tab_btn_metrics, self.tab_btn_log, self.tab_btn_clips]):
                tb.setCursor(Qt.CursorShape.PointingHandCursor)
                tb.setFixedHeight(26)
                tb.clicked.connect(lambda checked, idx=i: self.switch_view_tab(idx))
                tab_bar.addWidget(tb)

            e_lay.addLayout(tab_bar)

            # --- F. Stacked Views Area ---
            self.views_stack = QStackedWidget()
            self.views_stack.setFixedHeight(145)

            # VIEW 0: Bento Metrics Grid 2x2
            v_metrics = QWidget()
            v_metrics_lay = QGridLayout(v_metrics)
            v_metrics_lay.setContentsMargins(0, 0, 0, 0)
            v_metrics_lay.setSpacing(8)

            def make_metric_card(title: str, val: str, sub: str) -> tuple[QFrame, QLabel, QLabel]:
                card = QFrame()
                card.setStyleSheet("""
                    QFrame {
                        background: #0B0E14;
                        border: 1px solid rgba(255, 255, 255, 0.05);
                        border-radius: 8px;
                    }
                """)
                c_lay = QVBoxLayout(card)
                c_lay.setContentsMargins(10, 8, 10, 8)
                c_lay.setSpacing(2)

                t_lbl = QLabel(title.upper())
                t_lbl.setStyleSheet("color: #71717A; font-size: 8px; font-weight: 700; letter-spacing: 0.5px;")
                c_lay.addWidget(t_lbl)

                v_lbl = QLabel(val)
                v_lbl.setStyleSheet("color: #F4F4F5; font-size: 11px; font-weight: 700;")
                c_lay.addWidget(v_lbl)

                s_lbl = QLabel(sub)
                s_lbl.setStyleSheet("color: #52525B; font-size: 9px;")
                c_lay.addWidget(s_lbl)
                return card, v_lbl, s_lbl

            card1, self.bento_res_val, self.bento_res_sub = make_metric_card("Resolusi Output", "1080p Full HD", "1920x1080 · 16:9 Standard")
            card2, self.bento_sub_val, self.bento_sub_sub = make_metric_card("Subtitle Engine", "Smart Notice", "Kuning Denyut · 1.0s Hook")
            card3, self.bento_aud_val, self.bento_aud_sub = make_metric_card("Audio Terproses", "0m / 0m", "faster-whisper int8")
            card4, self.bento_out_val, self.bento_out_sub = make_metric_card("Folder Output", "HasilClip", "Klik 'Folder Hasil' di bawah")

            v_metrics_lay.addWidget(card1, 0, 0)
            v_metrics_lay.addWidget(card2, 0, 1)
            v_metrics_lay.addWidget(card3, 1, 0)
            v_metrics_lay.addWidget(card4, 1, 1)

            self.views_stack.addWidget(v_metrics)

            # VIEW 1: Live Console Stream
            v_log = QWidget()
            v_log_lay = QVBoxLayout(v_log)
            v_log_lay.setContentsMargins(0, 0, 0, 0)
            v_log_lay.setSpacing(4)

            log_bar = QHBoxLayout()
            log_sub_lbl = QLabel("Realtime Autoclipper Log Stream:")
            log_sub_lbl.setStyleSheet("color: #71717A; font-size: 9px;")
            log_bar.addWidget(log_sub_lbl)
            log_bar.addStretch(1)

            self.btn_copy_log = QPushButton("📋 Salin Log")
            self.btn_copy_log.setFixedHeight(20)
            self.btn_copy_log.setStyleSheet("""
                QPushButton {
                    background: #151820;
                    color: #A1A1AA;
                    font-size: 9px;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 4px;
                    padding: 0 6px;
                }
                QPushButton:hover {
                    color: #FFFFFF;
                    background: #202533;
                }
            """)
            self.btn_copy_log.clicked.connect(self._copy_log)
            log_bar.addWidget(self.btn_copy_log)

            self.btn_autoscroll = QPushButton("⬇ Auto-scroll: ON")
            self.btn_autoscroll.setFixedHeight(20)
            self.btn_autoscroll.setStyleSheet("""
                QPushButton {
                    background: #151820;
                    color: #38BDF8;
                    font-size: 9px;
                    border: 1px solid rgba(56, 189, 248, 0.2);
                    border-radius: 4px;
                    padding: 0 6px;
                }
            """)
            self.btn_autoscroll.clicked.connect(self._toggle_autoscroll)
            log_bar.addWidget(self.btn_autoscroll)

            v_log_lay.addLayout(log_bar)

            self.exp_log_box = QPlainTextEdit()
            self.exp_log_box.setReadOnly(True)
            self.exp_log_box.setStyleSheet("""
                QPlainTextEdit {
                    background: #080A0E;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                    color: #94A3B8;
                    font-family: Consolas, monospace;
                    font-size: 9.5px;
                    line-height: 1.35;
                    padding: 6px;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 5px;
                }
                QScrollBar::handle:vertical {
                    background: rgba(255, 255, 255, 0.12);
                    border-radius: 2px;
                }
            """)
            v_log_lay.addWidget(self.exp_log_box)

            self.views_stack.addWidget(v_log)

            # VIEW 2: Klip Siap & Berkas
            v_clips = QWidget()
            v_clips_lay = QVBoxLayout(v_clips)
            v_clips_lay.setContentsMargins(0, 0, 0, 0)
            v_clips_lay.setSpacing(4)

            clips_bar = QHBoxLayout()
            self.clips_count_lbl = QLabel("Daftar Klip Tersedia:")
            self.clips_count_lbl.setStyleSheet("color: #71717A; font-size: 9px;")
            clips_bar.addWidget(self.clips_count_lbl)
            clips_bar.addStretch(1)

            btn_refresh_clips = QPushButton("🔄 Segarkan Berkas")
            btn_refresh_clips.setFixedHeight(20)
            btn_refresh_clips.setStyleSheet("""
                QPushButton {
                    background: #151820;
                    color: #A1A1AA;
                    font-size: 9px;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 4px;
                    padding: 0 6px;
                }
                QPushButton:hover {
                    color: #FFFFFF;
                }
            """)
            btn_refresh_clips.clicked.connect(self._refresh_clips_list)
            clips_bar.addWidget(btn_refresh_clips)

            v_clips_lay.addLayout(clips_bar)

            self.clips_scroll = QScrollArea()
            self.clips_scroll.setWidgetResizable(True)
            self.clips_scroll.setStyleSheet("""
                QScrollArea {
                    background: #080A0E;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                }
            """)
            self.clips_container = QWidget()
            self.clips_list_lay = QVBoxLayout(self.clips_container)
            self.clips_list_lay.setContentsMargins(6, 6, 6, 6)
            self.clips_list_lay.setSpacing(5)
            self.clips_scroll.setWidget(self.clips_container)

            v_clips_lay.addWidget(self.clips_scroll)
            self.views_stack.addWidget(v_clips)

            e_lay.addWidget(self.views_stack)

            # Set default view to Tab 0 (Metrik Spek)
            self.switch_view_tab(0)

            # --- G. Footer Actions Bar ---
            foot_row = QHBoxLayout()
            foot_row.setSpacing(8)

            btn_folder = QPushButton("📁 Folder Hasil")
            btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_folder.setStyleSheet("""
                QPushButton {
                    background: #151820;
                    color: #E4E4E7;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 10px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #202534;
                    color: #FFFFFF;
                    border: 1px solid rgba(56, 189, 248, 0.3);
                }
            """)
            btn_folder.clicked.connect(self._open_hasil_dir)
            foot_row.addWidget(btn_folder)

            self.btn_copy_summary = QPushButton("📋 Salin Ringkasan")
            self.btn_copy_summary.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_copy_summary.setStyleSheet("""
                QPushButton {
                    background: #151820;
                    color: #A1A1AA;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 10px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #202534;
                    color: #FFFFFF;
                }
            """)
            self.btn_copy_summary.clicked.connect(self._copy_summary)
            foot_row.addWidget(self.btn_copy_summary)

            btn_refresh = QPushButton("🔄")
            btn_refresh.setFixedSize(24, 24)
            btn_refresh.setToolTip("Segarkan Data")
            btn_refresh.setStyleSheet("""
                QPushButton {
                    background: #151820;
                    color: #A1A1AA;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 6px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #202534;
                    color: #FFFFFF;
                }
            """)
            btn_refresh.clicked.connect(self.sync_realtime_data)
            foot_row.addWidget(btn_refresh)

            foot_row.addStretch(1)

            self.exp_time_lbl = QLabel("● --:--:-- WIB")
            self.exp_time_lbl.setStyleSheet("color: #71717A; font-size: 10px; font-weight: 500;")
            foot_row.addWidget(self.exp_time_lbl)

            self.exp_min_btn = QPushButton("— Minimize")
            self.exp_min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.exp_min_btn.setToolTip("Kecilkan ke Bar Mini di Kanan Bawah")
            self.exp_min_btn.setStyleSheet("""
                QPushButton {
                    background: #18202E;
                    color: #38BDF8;
                    border: 1px solid rgba(56, 189, 248, 0.3);
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 10px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: #233147;
                    color: #FFFFFF;
                }
            """)
            self.exp_min_btn.clicked.connect(lambda: self.set_mode(self.MODE_MINI))
            foot_row.addWidget(self.exp_min_btn)

            self.exp_close_btn = QPushButton("✕")
            self.exp_close_btn.setFixedSize(24, 24)
            self.exp_close_btn.setToolTip("Tutup Widget")
            self.exp_close_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.06);
                    color: #A1A1AA;
                    border: none;
                    border-radius: 6px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: rgba(239, 68, 68, 0.25);
                    color: #EF4444;
                }
            """)
            self.exp_close_btn.clicked.connect(self.close)
            foot_row.addWidget(self.exp_close_btn)

            e_lay.addLayout(foot_row)

            self.exp_opacity = QGraphicsOpacityEffect(self.exp_frame)
            self.exp_frame.setGraphicsEffect(self.exp_opacity)

            # Inisialisasi awal Stepper & Inspector
            self._update_inspector_card()
            self._update_stepper_buttons()
            self._refresh_clips_list()

        # ==========================================
        # INTERAKSI: STAGE INSPECTION & TABS
        # ==========================================

        def inspect_stage(self, stage_key: str) -> None:
            """Pengguna mengklik tombol tahap tertentu untuk melihat detailnya."""
            if stage_key not in STAGE_SPECS:
                return
            self.user_pinned_inspection = True
            self.selected_inspect_stage = stage_key
            self._update_inspector_card()
            self._update_stepper_buttons()

        def _resync_to_active_stage(self) -> None:
            """Mengembalikan inspeksi agar otomatis mengikuti tahap pipeline yang sedang aktif."""
            self.user_pinned_inspection = False
            self.selected_inspect_stage = self.current_pipeline_stage
            self._update_inspector_card()
            self._update_stepper_buttons()

        def _update_inspector_card(self) -> None:
            """Memperbarui kartu inspeksi dengan teks, engine, dan badge status relasional."""
            stage_key = self.selected_inspect_stage
            if stage_key not in STAGE_SPECS:
                return
            spec = STAGE_SPECS[stage_key]
            self.insp_title.setText(spec["title"])
            self.insp_engine_badge.setText(spec["engine"])
            self.insp_desc.setText(f"{spec['desc']} (Kualitas: {spec['quality']})")

            step_order = ["download", "transcribe", "ai", "clip", "render"]
            active_idx = step_order.index(self.current_pipeline_stage) if self.current_pipeline_stage in step_order else -1
            this_idx = step_order.index(stage_key) if stage_key in step_order else -1

            if this_idx == active_idx:
                self.insp_status_tag.setText("● SEDANG BERJALAN (AKTIF)")
                self.insp_status_tag.setStyleSheet("""
                    background: rgba(56, 189, 248, 0.2);
                    color: #38BDF8;
                    font-size: 9px;
                    font-weight: 800;
                    padding: 2px 8px;
                    border-radius: 5px;
                    border: 1px solid #38BDF8;
                """)
            elif this_idx < active_idx:
                self.insp_status_tag.setText("✓ TAHAP TELAH SELESAI")
                self.insp_status_tag.setStyleSheet("""
                    background: rgba(16, 185, 129, 0.15);
                    color: #10B981;
                    font-size: 9px;
                    font-weight: 700;
                    padding: 2px 8px;
                    border-radius: 5px;
                    border: 1px solid rgba(16, 185, 129, 0.35);
                """)
            else:
                self.insp_status_tag.setText("⏳ MENUNGGU PROSES SEBELUMNYA")
                self.insp_status_tag.setStyleSheet("""
                    background: rgba(255, 255, 255, 0.05);
                    color: #94A3B8;
                    font-size: 9px;
                    font-weight: 600;
                    padding: 2px 8px;
                    border-radius: 5px;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                """)

        def _update_stepper_buttons(self) -> None:
            """
            Merender tombol stepper:
            - Tahap yang sedang AKTIF berjalan SELALU menyala terang (border cyan tebal + ● [AKTIF]),
              TIDAK PERNAH padam meskipun user mengklik tahap lain!
            - Tahap yang diklik user mendapat indikator outline inspeksi (dashed) tanpa memadamkan tahap aktif.
            """
            step_order = ["download", "transcribe", "ai", "clip", "render"]
            active_idx = -1
            if self.current_pipeline_stage in step_order:
                active_idx = step_order.index(self.current_pipeline_stage)
            elif self.current_pipeline_stage in ("done", "completed"):
                active_idx = 5

            base_labels = ["1. Unduh", "2. Whisper", "3. AI Viral", "4. Subtitle", "5. Render"]

            for i, k in enumerate(step_order):
                btn = self.step_buttons.get(k)
                if not btn:
                    continue

                lbl = base_labels[i]
                is_currently_running = (i == active_idx)
                is_completed = (active_idx > i)
                is_inspected = (k == self.selected_inspect_stage)

                # 1. TAHAP YANG SEDANG AKTIF BERJALAN
                if is_currently_running:
                    btn.setText(f"● {lbl} [AKTIF]")
                    if is_inspected:
                        # Sedang aktif & sedang diinspeksi
                        btn.setStyleSheet("""
                            QPushButton {
                                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1E3A5F, stop:1 #132438);
                                color: #38BDF8;
                                font-size: 10px;
                                font-weight: 800;
                                border: 2px solid #38BDF8;
                                border-radius: 6px;
                                padding: 2px 6px;
                            }
                        """)
                    else:
                        # Sedang aktif tapi user klik tahap lain -> TETAP MENYALA TERANG!
                        btn.setStyleSheet("""
                            QPushButton {
                                background: #14243B;
                                color: #38BDF8;
                                font-size: 10px;
                                font-weight: 800;
                                border: 2px solid #38BDF8;
                                border-radius: 6px;
                                padding: 2px 6px;
                            }
                            QPushButton:hover {
                                background: #1B3150;
                            }
                        """)

                # 2. TAHAP YANG SUDAH SELESAI
                elif is_completed:
                    btn.setText(f"✓ {lbl}")
                    if is_inspected:
                        # Sudah selesai & sedang diinspeksi
                        btn.setStyleSheet("""
                            QPushButton {
                                background: #142E22;
                                color: #34D399;
                                font-size: 10px;
                                font-weight: 700;
                                border: 1.5px dashed #34D399;
                                border-radius: 6px;
                                padding: 2px 6px;
                            }
                        """)
                    else:
                        btn.setStyleSheet("""
                            QPushButton {
                                background: #0D1C15;
                                color: #10B981;
                                font-size: 10px;
                                font-weight: 600;
                                border: 1px solid rgba(16, 185, 129, 0.3);
                                border-radius: 6px;
                                padding: 2px 6px;
                            }
                            QPushButton:hover {
                                background: #142920;
                                color: #34D399;
                            }
                        """)

                # 3. TAHAP PENDING (BELUM MULAI)
                else:
                    btn.setText(lbl)
                    if is_inspected:
                        # Belum mulai & sedang diinspeksi
                        btn.setStyleSheet("""
                            QPushButton {
                                background: #18202D;
                                color: #E2E8F0;
                                font-size: 10px;
                                font-weight: 600;
                                border: 1.5px dashed #94A3B8;
                                border-radius: 6px;
                                padding: 2px 6px;
                            }
                        """)
                    else:
                        btn.setStyleSheet("""
                            QPushButton {
                                background: #101319;
                                color: #64748B;
                                font-size: 10px;
                                font-weight: 500;
                                border: 1px solid rgba(255, 255, 255, 0.04);
                                border-radius: 6px;
                                padding: 2px 6px;
                            }
                            QPushButton:hover {
                                background: #161B24;
                                color: #94A3B8;
                            }
                        """)

        def switch_view_tab(self, index: int) -> None:
            """Beralih tampilan antara Metrik Spek, Log, dan Klip Siap."""
            self.views_stack.setCurrentIndex(index)
            active_style = """
                QPushButton {
                    background: #1C2333;
                    color: #38BDF8;
                    font-size: 10px;
                    font-weight: 700;
                    border: 1px solid rgba(56, 189, 248, 0.35);
                    border-radius: 6px;
                }
            """
            inactive_style = """
                QPushButton {
                    background: #11141B;
                    color: #71717A;
                    font-size: 10px;
                    font-weight: 600;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background: #181E28;
                    color: #E4E4E7;
                }
            """
            self.tab_btn_metrics.setStyleSheet(active_style if index == 0 else inactive_style)
            self.tab_btn_log.setStyleSheet(active_style if index == 1 else inactive_style)
            self.tab_btn_clips.setStyleSheet(active_style if index == 2 else inactive_style)

            if index == 2:
                self._refresh_clips_list()

        def _refresh_clips_list(self) -> None:
            """Memindai dan menampilkan klip MP4 yang tersedia di HasilClip."""
            while self.clips_list_lay.count() > 0:
                child = self.clips_list_lay.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            clips = []
            seen_paths = set()
            for h_dir in [HASIL_CLIP_DIR, CURRENT_DIR / "HasilClip"]:
                if h_dir.is_dir():
                    for p in sorted(h_dir.rglob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
                        if p.is_file() and p not in seen_paths:
                            seen_paths.add(p)
                            try:
                                sz_mb = p.stat().st_size / (1024 * 1024)
                                title = p.parent.name if p.name.lower() == "clip.mp4" else p.stem
                                clips.append((p, sz_mb, title))
                            except Exception:
                                pass

            self.clips_count_lbl.setText(f"Daftar Klip Tersedia ({len(clips)} berkas MP4):")

            if not clips:
                empty_lbl = QLabel("Belum ada klip yang selesai dirender.\nKlip akan otomatis terdaftar di sini setelah proses render (Tahap 5) selesai.")
                empty_lbl.setStyleSheet("color: #52525B; font-size: 10px; font-style: italic; padding: 12px;")
                empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.clips_list_lay.addWidget(empty_lbl)
                self.clips_list_lay.addStretch(1)
                return

            for clip_path, sz_mb, title in clips[:15]:
                c_row = QFrame()
                c_row.setStyleSheet("""
                    QFrame {
                        background: #0E121A;
                        border: 1px solid rgba(255, 255, 255, 0.05);
                        border-radius: 6px;
                    }
                    QFrame:hover {
                        border: 1px solid rgba(56, 189, 248, 0.3);
                    }
                """)
                r_lay = QHBoxLayout(c_row)
                r_lay.setContentsMargins(8, 4, 8, 4)
                r_lay.setSpacing(6)

                ico = QLabel("🎬")
                ico.setStyleSheet("font-size: 11px; background: transparent;")
                r_lay.addWidget(ico)

                name_lbl = QLabel(title)
                name_lbl.setToolTip(str(clip_path))
                name_lbl.setStyleSheet("color: #E4E4E7; font-size: 10px; font-weight: 500; background: transparent;")
                r_lay.addWidget(name_lbl, 1)

                size_lbl = QLabel(f"{sz_mb:.1f} MB")
                size_lbl.setStyleSheet("color: #71717A; font-size: 9px; background: transparent;")
                r_lay.addWidget(size_lbl)

                play_btn = QPushButton("▶ Putar")
                play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                play_btn.setFixedHeight(18)
                play_btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(56, 189, 248, 0.15);
                        color: #38BDF8;
                        border: 1px solid rgba(56, 189, 248, 0.3);
                        border-radius: 4px;
                        padding: 0 6px;
                        font-size: 9px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background: rgba(56, 189, 248, 0.3);
                        color: #FFFFFF;
                    }
                """)
                play_btn.clicked.connect(lambda checked, p=clip_path: self._play_clip(p))
                r_lay.addWidget(play_btn)

                self.clips_list_lay.addWidget(c_row)

            self.clips_list_lay.addStretch(1)

        def _play_clip(self, clip_path: Path) -> None:
            try:
                os.startfile(str(clip_path))
            except Exception:
                pass

        def _copy_log(self) -> None:
            text = self.exp_log_box.toPlainText()
            if text:
                QApplication.clipboard().setText(text)
                self.btn_copy_log.setText("Tersalin! ✓")
                QTimer.singleShot(1500, lambda: self.btn_copy_log.setText("📋 Salin Log"))

        def _copy_summary(self) -> None:
            summary = (
                f"=== ENCLip Studio Pipeline Summary ===\n"
                f"Judul: {self.exp_title.text()}\n"
                f"Tahap Aktif: {self.current_pipeline_stage.upper()}\n"
                f"Status: {self.exp_detail_lbl.text()}\n"
                f"Progress: {self.exp_pct_lbl.text()}\n"
                f"Format: 1080p Full HD · 16:9 Standard\n"
                f"Subtitle: Smart Notice (Kuning Denyut)\n"
                f"Waktu: {self.exp_time_lbl.text()}\n"
            )
            QApplication.clipboard().setText(summary)
            self.btn_copy_summary.setText("Tersalin! ✓")
            QTimer.singleShot(1500, lambda: self.btn_copy_summary.setText("📋 Salin Ringkasan"))

        def _toggle_autoscroll(self) -> None:
            self.auto_scroll_log = not self.auto_scroll_log
            if self.auto_scroll_log:
                self.btn_autoscroll.setText("⬇ Auto-scroll: ON")
                self.btn_autoscroll.setStyleSheet("""
                    QPushButton {
                        background: #151820;
                        color: #38BDF8;
                        font-size: 9px;
                        border: 1px solid rgba(56, 189, 248, 0.2);
                        border-radius: 4px;
                        padding: 0 6px;
                    }
                """)
            else:
                self.btn_autoscroll.setText("⏸ Auto-scroll: OFF")
                self.btn_autoscroll.setStyleSheet("""
                    QPushButton {
                        background: #151820;
                        color: #71717A;
                        font-size: 9px;
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        border-radius: 4px;
                        padding: 0 6px;
                    }
                """)

        # ==========================================
        # ANIMASI DAN DRAGGABLE WINDOW (KANAN BAWAH KE ATAS)
        # ==========================================

        def resizeEvent(self, event: Any) -> None:
            super().resizeEvent(event)
            w, h = self.width(), self.height()
            if hasattr(self, "mini_frame") and self.mini_frame:
                self.mini_frame.setGeometry(0, 0, w, h)
            if hasattr(self, "exp_frame") and self.exp_frame:
                self.exp_frame.setGeometry(0, 0, w, h)

        def set_mode(self, mode: int, animate: bool = True) -> None:
            """
            Beralih antara mode Mini (Pill 440x40) dan Expanded (Bento 520x520).
            Terpasang di pojok KANAN BAWAH desktop (di atas taskbar) dan membesar (maximize) ke arah ATAS!
            """
            if mode == self.current_mode and hasattr(self, "_anim_group") and self._anim_group and self._anim_group.state() == QParallelAnimationGroup.State.Running:
                return

            prev_mode = self.current_mode
            self.current_mode = mode
            cur_rect = self.geometry()

            screen = QApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else None

            margin_x = 24
            margin_y = 20

            if mode == self.MODE_MINI:
                target_w, target_h = 440, 40
            else:
                target_w, target_h = 520, 520

            # Hitung jangkar KANAN BAWAH (Bottom-Right Anchor)
            if not avail:
                avail_x, avail_y, avail_w, avail_h = 0, 0, 1920, 1080
            else:
                avail_x, avail_y, avail_w, avail_h = avail.x(), avail.y(), avail.width(), avail.height()

            default_right = avail_x + avail_w - margin_x
            default_bottom = avail_y + avail_h - margin_y

            # Jika belum pernah diposisikan atau di luar layar, gunakan default kanan-bawah
            if cur_rect.width() <= 0 or cur_rect.x() <= 0 or cur_rect.y() <= 0:
                cur_right = default_right
                cur_bottom = default_bottom
            else:
                cur_right = cur_rect.x() + cur_rect.width()
                cur_bottom = cur_rect.y() + cur_rect.height()

            # Pastikan tidak melewati batas layar
            cur_right = min(default_right, max(avail_x + target_w, cur_right))
            cur_bottom = min(default_bottom, max(avail_y + target_h, cur_bottom))

            # MAXIMIZE KE ATAS: bottom edge tetap di cur_bottom, y bergeser ke atas (cur_bottom - target_h)
            target_x = cur_right - target_w
            target_y = cur_bottom - target_h

            target_rect = QRect(target_x, target_y, target_w, target_h)

            if not animate or cur_rect.width() <= 0:
                self.setGeometry(target_rect)
                self.mini_frame.setGeometry(0, 0, target_w, target_h)
                self.exp_frame.setGeometry(0, 0, target_w, target_h)
                if mode == self.MODE_MINI:
                    self.mini_frame.setVisible(True)
                    self.mini_opacity.setOpacity(1.0)
                    self.exp_frame.setVisible(False)
                    self.exp_opacity.setOpacity(0.0)
                else:
                    self.exp_frame.setVisible(True)
                    self.exp_opacity.setOpacity(1.0)
                    self.mini_frame.setVisible(False)
                    self.mini_opacity.setOpacity(0.0)
                return

            if hasattr(self, "_anim_group") and self._anim_group:
                try:
                    self._anim_group.stop()
                except Exception:
                    pass

            self._anim_group = QParallelAnimationGroup(self)

            # 1. Animasi Geometri (Resize & Geser Halus ke Atas/Bawah)
            anim_geo = QPropertyAnimation(self, b"geometry")
            anim_geo.setDuration(260)
            anim_geo.setStartValue(cur_rect)
            anim_geo.setEndValue(target_rect)
            anim_geo.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim_group.addAnimation(anim_geo)

            # 2. Animasi Cross-Fade Opacity
            if mode == self.MODE_EXPANDED:
                self.mini_frame.setVisible(True)
                self.exp_frame.setVisible(True)
                self.exp_frame.raise_()

                anim_exp_in = QPropertyAnimation(self.exp_opacity, b"opacity")
                anim_exp_in.setDuration(250)
                anim_exp_in.setStartValue(0.0)
                anim_exp_in.setEndValue(1.0)
                anim_exp_in.setEasingCurve(QEasingCurve.Type.OutQuad)
                self._anim_group.addAnimation(anim_exp_in)

                anim_mini_out = QPropertyAnimation(self.mini_opacity, b"opacity")
                anim_mini_out.setDuration(160)
                anim_mini_out.setStartValue(1.0)
                anim_mini_out.setEndValue(0.0)
                anim_mini_out.setEasingCurve(QEasingCurve.Type.InQuad)
                self._anim_group.addAnimation(anim_mini_out)

                def on_exp_done() -> None:
                    if self.current_mode == self.MODE_EXPANDED:
                        self.mini_frame.setVisible(False)

                self._anim_group.finished.connect(on_exp_done)

            else:
                self.mini_frame.setVisible(True)
                self.exp_frame.setVisible(True)
                self.mini_frame.raise_()

                anim_mini_in = QPropertyAnimation(self.mini_opacity, b"opacity")
                anim_mini_in.setDuration(250)
                anim_mini_in.setStartValue(0.0)
                anim_mini_in.setEndValue(1.0)
                anim_mini_in.setEasingCurve(QEasingCurve.Type.OutQuad)
                self._anim_group.addAnimation(anim_mini_in)

                anim_exp_out = QPropertyAnimation(self.exp_opacity, b"opacity")
                anim_exp_out.setDuration(160)
                anim_exp_out.setStartValue(1.0)
                anim_exp_out.setEndValue(0.0)
                anim_exp_out.setEasingCurve(QEasingCurve.Type.InQuad)
                self._anim_group.addAnimation(anim_exp_out)

                def on_mini_done() -> None:
                    if self.current_mode == self.MODE_MINI:
                        self.exp_frame.setVisible(False)

                self._anim_group.finished.connect(on_mini_done)

            self._anim_group.start()

        def mousePressEvent(self, event: Any) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

        def mouseMoveEvent(self, event: Any) -> None:
            if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
                self.move(event.globalPosition().toPoint() - self._drag_pos)
                event.accept()

        def mouseDoubleClickEvent(self, event: Any) -> None:
            if self.current_mode == self.MODE_MINI:
                self.set_mode(self.MODE_EXPANDED)
            else:
                self.set_mode(self.MODE_MINI)

        def closeEvent(self, event: Any) -> None:
            try:
                if HUD_PID_FILE.is_file():
                    HUD_PID_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            event.accept()

        def _open_hasil_dir(self) -> None:
            HASIL_CLIP_DIR.mkdir(parents=True, exist_ok=True)
            try:
                os.startfile(str(HASIL_CLIP_DIR))
            except Exception:
                pass

        # ==========================================
        # REALTIME SINKRONISASI DATA & LOG
        # ==========================================

        def sync_realtime_data(self) -> None:
            if HUD_STATUS_FILE.is_file():
                try:
                    mtime = HUD_STATUS_FILE.stat().st_mtime
                    if mtime != self.last_status_mtime:
                        self.last_status_mtime = mtime
                        with open(HUD_STATUS_FILE, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        self._apply_status(data)
                except Exception:
                    pass

            if AUTOCLIPPER_LOG.is_file():
                try:
                    size = AUTOCLIPPER_LOG.stat().st_size
                    if size < self.last_log_pos:
                        self.last_log_pos = 0
                    if size > self.last_log_pos:
                        with open(AUTOCLIPPER_LOG, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(self.last_log_pos)
                            new_text = f.read()
                            self.last_log_pos = f.tell()
                        if new_text:
                            self.exp_log_box.appendPlainText(new_text.strip())
                            if self.auto_scroll_log:
                                sb = self.exp_log_box.verticalScrollBar()
                                sb.setValue(sb.maximum())
                except Exception:
                    pass

        def _apply_status(self, data: dict[str, Any]) -> None:
            title = data.get("title", "Video Podcast")
            stage = data.get("stage", "idle").lower()
            progress = data.get("progress", 0)
            sub_progress = data.get("sub_progress", 0)
            detail = data.get("detail", "")
            channel = data.get("channel", "")
            time_str = data.get("time_str", "--:--:-- WIB")

            # Update Active Pipeline Stage
            self.current_pipeline_stage = stage

            # Jika user belum sengaja mem-pin inspeksi tahap lain, ikuti tahap yang sedang aktif!
            if not self.user_pinned_inspection:
                self.selected_inspect_stage = stage

            # Update Mini Pill
            self.mini_text.setText(f"{channel + ' · ' if channel else ''}{detail or title}")
            self.mini_pct.setText(f"{progress}%\")") if False else self.mini_pct.setText(f"{progress}%")

            # Update Expanded Bento Card Hero Box
            self.exp_title.setText(title)
            self.exp_title.setToolTip(title)
            self.exp_bar.setValue(int(progress))
            self.exp_pct_lbl.setText(f"{progress}%")
            self.exp_detail_lbl.setText(detail or f"Proses tahap {stage}...")
            self.exp_time_lbl.setText(f"● {time_str}")

            if channel:
                self.channel_badge.setText(f"📺 {channel}")

            stage_map = {
                "idle": ("STANDBY", "#71717A"),
                "download": ("1. UNDUH", "#38BDF8"),
                "transcribe": ("2. WHISPER", "#38BDF8"),
                "ai": ("3. VISION AI", "#38BDF8"),
                "clip": ("4. SUBTITLE", "#38BDF8"),
                "render": ("5. RENDER", "#38BDF8"),
                "upload": ("6. UPLOAD TIKTOK", "#38BDF8"),
                "done": ("SELESAI", "#10B981"),
                "completed": ("SELESAI", "#10B981"),
            }
            stage_name, dot_color = stage_map.get(stage, ("STANDBY", "#71717A"))
            self.mini_stage.setText(stage_name.replace("1. ", "").replace("2. ", "").replace("3. ", "").replace("4. ", "").replace("5. ", ""))
            self.mini_dot.setStyleSheet(f"color: {dot_color}; font-size: 11px; background: transparent;")
            self.hero_stage_badge.setText(f"● PROSES: {stage_name}")

            # Update Bento KPI Cards
            if "Memproses audio:" in detail:
                aud_part = detail.replace("Memproses audio:", "").strip()
                self.bento_aud_val.setText(aud_part)
                self.bento_aud_sub.setText(f"Sub-progress: {sub_progress}%")
            else:
                self.bento_aud_val.setText(f"{progress}% Selesai")
                self.bento_aud_sub.setText(f"Tahap: {stage_name}")

            # Update Tombol Stepper & Inspector Card
            self._update_stepper_buttons()
            self._update_inspector_card()


def main() -> None:
    """Entry point utama: meluncurkan widget modern minimalis."""
    attach_to_interactive_desktop()

    if not PYQT_AVAILABLE:
        print("ERROR: PyQt6 tidak ditemukan di environment Python ini.")
        sys.exit(1)

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        app.setApplicationName("ENCLip Studio Widget")

    widget = ENCLipHUDWidget()
    widget.show()
    widget.raise_()
    widget.activateWindow()

    if sys.platform.startswith("win"):
        try:
            import ctypes
            hwnd = int(widget.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 5)
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_TOPMOST
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
