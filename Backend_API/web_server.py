from __future__ import annotations

import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ENCLip")

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[assignment]


if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", ROOT)).resolve()
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    ROOT = PROJECT_ROOT / "Core_Data"
    BUNDLE_DIR = ROOT

DATA_DIR = ROOT / "HasilClip"
RAW_VIDEO_DIR = ROOT / "VideoMentah"
WEB_DIR = ROOT / "web"
if not WEB_DIR.exists():
    WEB_DIR = BUNDLE_DIR / "web"
if not WEB_DIR.exists():
    WEB_DIR = ROOT / "_internal" / "web"
if not WEB_DIR.exists():
    WEB_DIR = Path(__file__).parent.parent / "Web_UI" / "frontend"
MODEL_DIR = ROOT / "models"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

if load_dotenv is not None:
    load_dotenv(ROOT / ".env")
    project_env = Path(__file__).resolve().parent.parent / ".env"
    if project_env.is_file():
        load_dotenv(project_env)

MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
QWEN_GGUF_PATH = os.getenv("QWEN_GGUF_PATH", "")
HERMES_GGUF_PATH = os.getenv("HERMES_GGUF_PATH", "")
GGUF_N_CTX = int(os.getenv("GGUF_N_CTX", "8192"))
GGUF_N_GPU_LAYERS = int(os.getenv("GGUF_N_GPU_LAYERS", "-1"))


def get_active_gemini_api_key() -> str:
    """Membaca Gemini API Key dari environment, variabel global, file .env, atau QSettings GUI."""
    global GEMINI_API_KEY
    key = os.getenv("GEMINI_API_KEY", "").strip() or (GEMINI_API_KEY or "").strip()
    if key:
        return key

    for env_candidate in (ROOT / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if env_candidate.is_file():
            try:
                for line in env_candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line_s = line.strip()
                    if line_s.startswith("GEMINI_API_KEY="):
                        val = line_s.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            GEMINI_API_KEY = val
                            os.environ["GEMINI_API_KEY"] = val
                            return val
            except Exception:
                pass

    try:
        from PyQt6.QtCore import QSettings
        saved = (
            QSettings("ENCLip", "ENCLip").value("gemini_api_key", "")
            or QSettings("VanClipper", "VanClipper").value("gemini_api_key", "")
        )
        if saved and str(saved).strip():
            val = str(saved).strip()
            GEMINI_API_KEY = val
            os.environ["GEMINI_API_KEY"] = val
            return val
    except Exception:
        pass

    if sys.platform == "win32":
        try:
            import winreg
            for subkey in (r"Software\ENCLip\ENCLip", r"Software\VanClipper\VanClipper"):
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ) as reg_k:
                        val, _ = winreg.QueryValueEx(reg_k, "gemini_api_key")
                        if val and str(val).strip():
                            val = str(val).strip()
                            GEMINI_API_KEY = val
                            os.environ["GEMINI_API_KEY"] = val
                            return val
                except Exception:
                    pass
        except Exception:
            pass

    return ""


app = FastAPI(title="ENCLip", version="1.0.0")
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
app.mount("/media", StaticFiles(directory=DATA_DIR), name="media")
app.mount("/raw", StaticFiles(directory=RAW_VIDEO_DIR), name="raw")


class CreateJobRequest(BaseModel):
    url: str = Field(min_length=1)
    clip_count: int = Field(default=0, ge=0, le=200)
    language: str = Field(default="id", min_length=2, max_length=10)
    min_duration: int = Field(default=0, ge=0, le=3600)
    max_duration: int = Field(default=0, ge=0, le=3600)
    smart_duration_mode: str = Field(default="auto", pattern="^(auto|fixed)$")
    smart_fixed_duration: int = Field(default=60, ge=5, le=3600)
    max_clips: int = Field(default=10, ge=1, le=200)
    clip_mode: str = Field(default="smart", pattern="^(smart|split_count|split_duration)$")
    clip_profile: str = Field(default="auto", pattern="^(auto|live|standard|manual)$")
    clip_flavor: str = Field(
        default="spicy_drama",
        pattern="^(spicy_drama|viral_all|funny_blunder|deep_meat|hype_rage)$",
    )
    use_audio_energy: bool = Field(default=True)
    snap_sentence_bounds: bool = Field(default=True)
    trim_opening_filler: bool = Field(default=False)
    spicy_headline_hook: bool = Field(default=True)
    split_count: int = Field(default=10, ge=1, le=500)
    segment_duration: int = Field(default=120, ge=5, le=3600)
    use_local_llm: bool = True
    local_model: str = Field(default="qwen", pattern="^(qwen|hermes|gemini)$")
    quality: str = Field(default="1080", pattern="^(360|480|720|1080|2160|best)$")
    custom_prompt: str = Field(default="", max_length=500)
    whisper_model: str = Field(default="small")
    video_encoder: str = Field(default="auto")
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16|4:3|1:1)$")
    framing: str = Field(default="fit", pattern="^(fit|crop)$")
    layout: str = Field(default="standard", pattern="^(auto_smart|standard|facecam_top|podcast_split)$")
    subtitle_style: str = Field(default="bold", pattern="^(classic|bold|highlight|minimal|neon|karaoke|box|none)$")
    subtitle_position: str = Field(default="auto", pattern="^(auto|top|center|bottom|free)$")
    subtitle_color: str = Field(default="auto", pattern="^(auto|white|yellow|cyan|red|green|pink|#[0-9A-Fa-f]{6})$")
    subtitle_active_color: str = Field(default="#FFDD00")
    subtitle_x: float = Field(default=0.15, ge=0, le=1)
    subtitle_y: float = Field(default=0.78, ge=0, le=1)
    subtitle_max_lines: int = Field(default=2, ge=-1, le=5)
    subtitle_font_size: int = Field(default=14, ge=8, le=36)
    subtitle_mode: str = Field(default="active_highlight", pattern="^(phrase|single_word|active_highlight)$")
    bgm_path: str = Field(default="")
    bgm_volume: float = Field(default=0.08, ge=0.0, le=1.0)
    voice_volume: float = Field(default=1.0, ge=0.1, le=2.0)
    bgm_autoduck: bool = Field(default=True)
    audio_loudnorm: bool = Field(default=True)
    censor_profanity: bool = Field(default=False)
    watermark_text: str = Field(default="", max_length=80)
    watermark_image_path: str = Field(default="")
    watermark_position: str = Field(default="top_right", pattern="^(top_right|top_left|bottom_right|bottom_left|center|free)$")
    watermark_opacity: float = Field(default=0.65, ge=0.05, le=1.0)
    hook_banner_enabled: bool = Field(default=True)
    hook_banner_text: str = Field(default="", max_length=120)
    hook_banner_duration: int = Field(default=1, ge=0, le=300)
    facecam_crop: list[float] | None = None
    mirror_video: bool = Field(default=False)
    speed_shift: bool = Field(default=False)
    color_boost: bool = Field(default=False)
    emoji_subtitles: bool = Field(default=True)
    dynamic_micro_zoom: bool = Field(default=True)
    auto_broll: bool = Field(default=False)
    broll_folder: str = Field(default="")
    skip_if_has_subtitles: bool = Field(default=True, description="Otomatis lewati penambahan subtitle jika video sudah memiliki subtitle (embedded/hardsub).")


class RenderRequest(BaseModel):
    subtitle_style: str = Field(default="bold", pattern="^(classic|bold|highlight|minimal|neon|karaoke|box|none)$")
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16|4:3|1:1)$")
    framing: str = Field(default="fit", pattern="^(fit|crop)$")
    layout: str = Field(default="standard", pattern="^(auto_smart|standard|facecam_top|podcast_split)$")
    subtitle_position: str = Field(default="auto", pattern="^(auto|top|center|bottom|free)$")
    subtitle_color: str = Field(default="auto", pattern="^(auto|white|yellow|cyan|red|green|pink|#[0-9A-Fa-f]{6})$")
    subtitle_active_color: str = Field(default="#FFDD00")
    subtitle_x: float = Field(default=0.15, ge=0, le=1)
    subtitle_y: float = Field(default=0.78, ge=0, le=1)
    subtitle_max_lines: int = Field(default=2, ge=-1, le=5)
    subtitle_font_size: int = Field(default=14, ge=8, le=36)
    subtitle_mode: str = Field(default="active_highlight", pattern="^(phrase|single_word|active_highlight)$")
    bgm_path: str = Field(default="")
    bgm_volume: float = Field(default=0.08, ge=0.0, le=1.0)
    voice_volume: float = Field(default=1.0, ge=0.1, le=2.0)
    bgm_autoduck: bool = Field(default=True)
    audio_loudnorm: bool = Field(default=True)
    censor_profanity: bool = Field(default=False)
    watermark_text: str = Field(default="", max_length=80)
    watermark_image_path: str = Field(default="")
    watermark_position: str = Field(default="top_right", pattern="^(top_right|top_left|bottom_right|bottom_left|center|free)$")
    watermark_opacity: float = Field(default=0.65, ge=0.05, le=1.0)
    hook_banner_enabled: bool = Field(default=True)
    hook_banner_text: str = Field(default="", max_length=120)
    hook_banner_duration: int = Field(default=1, ge=0, le=300)
    facecam_crop: list[float] | None = None
    mirror_video: bool = Field(default=False)
    speed_shift: bool = Field(default=False)
    color_boost: bool = Field(default=False)
    emoji_subtitles: bool = Field(default=True)
    dynamic_micro_zoom: bool = Field(default=True)
    auto_broll: bool = Field(default=False)
    broll_folder: str = Field(default="")
    skip_if_has_subtitles: bool = Field(default=True, description="Otomatis lewati penambahan subtitle jika video sudah memiliki subtitle (embedded/hardsub).")


class ManualClipRequest(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    title: str = Field(default="", max_length=120)


@dataclass
class Clip:
    id: str
    start: float
    end: float
    score: float
    title: str
    source: str = "ai"
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    subtitle_url: str = ""
    video_url: str = ""
    core_topic: str = ""
    hook_title: str = ""


@dataclass
class Job:
    id: str
    url: str
    status: str = "queued"
    progress: int = 0
    message: str = "Menunggu proses..."
    sub_progress: int = 0
    sub_message: str = ""
    duration: float = 0.0
    source_url: str = ""
    source_path: str = ""
    source_title: str = ""
    result_dir: str = ""
    transcript: list[dict[str, Any]] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)
    render_profile: dict[str, str] = field(default_factory=dict)
    error: str | None = None


JOBS: dict[str, Job] = {}
JOB_OPTIONS: dict[str, CreateJobRequest] = {}
JOBS_LOCK = threading.Lock()
GGUF_MODELS: dict[str, Any] = {}
GGUF_LOCK = threading.Lock()


def update_job(job_id: str, **changes: Any) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        for key, value in changes.items():
            setattr(job, key, value)

        try:
            from clipper_hud import update_hud_status

            msg_lower = (job.message or "").lower()
            if job.status in ("completed", "done") or job.progress >= 100:
                stage = "done"
            elif "render" in msg_lower or job.progress >= 75:
                stage = "render"
            elif "clip" in msg_lower or job.progress >= 65:
                stage = "clip"
            elif job.progress < 25:
                stage = "download"
            elif job.progress < 60:
                stage = "transcribe"
            else:
                stage = "ai"

            prog = job.progress
            sub_prog = job.sub_progress
            det = job.sub_message or job.message
            update_hud_status(
                stage=stage,
                title=job.source_title,
                progress=prog,
                sub_progress=sub_prog,
                detail=det,
                status=job.status,
            )
        except Exception:
            pass


def job_snapshot(job: Job) -> dict[str, Any]:
    value = asdict(job)
    value["clips"] = [asdict(clip) for clip in job.clips]
    return value


def safe_folder_name(value: str) -> str:
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = text[:120].rstrip(" .") or "Video tanpa judul"
    if text.upper().split(".", 1)[0] in {
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2", "LPT3"
    }:
        text = f"_{text}"
    return text


def create_result_dir(title: str, job_id: str) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    base = DATA_DIR / safe_folder_name(title)
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = DATA_DIR / f"{base.name} ({suffix})"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def job_result_dir(job_id: str) -> Path:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        configured = job.result_dir if job else None
    if configured:
        return Path(configured)
    return DATA_DIR / f"job-{job_id}"


def clip_folder_name(clip_id: str, title: str) -> str:
    return f"{clip_id} - {safe_folder_name(title)}"


def clip_result_dir(job_dir: Path, clip_id: str, title: str) -> Path:
    return job_dir / clip_folder_name(clip_id, title)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def yt_dlp_command() -> list[str]:
    if command_exists("yt-dlp"):
        return ["yt-dlp"]
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("yt-dlp belum terpasang. Jalankan: python -m pip install yt-dlp") from exc
    return [sys.executable, "-m", "yt_dlp"]


def ffmpeg_command() -> list[str]:
    if command_exists("ffmpeg"):
        return ["ffmpeg"]
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return [get_ffmpeg_exe()]
    except ImportError as exc:
        raise RuntimeError("ffmpeg belum terpasang. Jalankan: python -m pip install imageio-ffmpeg") from exc


SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
ACTIVE_PROCESSES: dict[str, Any] = {}
CANCELED_JOBS: set[str] = set()


def cancel_job(job_id: str) -> None:
    CANCELED_JOBS.add(job_id)
    proc = ACTIVE_PROCESSES.pop(job_id, None)
    if proc:
        try:
            proc.kill()
        except Exception:
            pass
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].status = "canceled"
            JOBS[job_id].message = "Proses dibatalkan oleh pengguna."


def run_command(args: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=SUBPROCESS_FLAGS,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail[-2000:] or "Perintah gagal dijalankan")
    return completed.stdout


def format_bytes(value: int | float | None) -> str:
    amount = float(value or 0)
    units = ["B", "KB", "MB", "GB"]
    unit_index = 0
    while amount >= 1024 and unit_index < len(units) - 1:
        amount /= 1024
        unit_index += 1
    return f"{amount:.1f} {units[unit_index]}"


def download_video(url: str, job_dir: Path, quality: str, job_id: str) -> Path:
    output_template = str(job_dir / "source.%(ext)s")
    max_height = "2160" if quality == "best" else quality
    format_selector = f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b"
    ffmpeg_raw = ffmpeg_command()[0]
    ffmpeg_dir = str(Path(ffmpeg_raw).parent)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    target_ffmpeg = Path(ffmpeg_dir) / "ffmpeg.exe"
    if not target_ffmpeg.exists() and Path(ffmpeg_raw).exists():
        try:
            shutil.copyfile(ffmpeg_raw, target_ffmpeg)
        except Exception:
            pass
    ffmpeg_path = str(target_ffmpeg if target_ffmpeg.exists() else ffmpeg_raw)
    try:
        import yt_dlp

        download_stats: dict[str, dict[str, float]] = {}

        def progress_hook(info: dict[str, Any]) -> None:
            status = info.get("status")
            if status in {"downloading", "finished"}:
                stream_key = str(info.get("filename") or info.get("tmpfilename") or info.get("format_id") or "stream")
                stream = download_stats.setdefault(stream_key, {"downloaded": 0.0, "total": 0.0})
                stream["downloaded"] = float(info.get("downloaded_bytes") or stream["downloaded"])
                exact_total = info.get("total_bytes")
                estimated_total = info.get("total_bytes_estimate")
                stream["estimated"] = 0.0 if exact_total else 1.0
                stream_total = exact_total or estimated_total or stream["total"]
                if stream_total:
                    stream["total"] = float(stream_total)
                if status == "finished" and stream["total"]:
                    stream["downloaded"] = stream["total"]

                downloaded = sum(item["downloaded"] for item in download_stats.values())
                total = sum(item["total"] for item in download_stats.values() if item["total"] > 0)
                display_total = total or fixed_total
                percentage = min(100, (downloaded / display_total * 100)) if display_total else 0
                speed = format_bytes(info.get("speed")) + "/s" if info.get("speed") else "menunggu..."
                has_estimate = any(item.get("estimated", 0) for item in download_stats.values()) or (
                    not total and fixed_total_is_estimate
                )
                total_text = (
                    ("~" if has_estimate else "") + format_bytes(display_total)
                    if display_total
                    else "menghitung total"
                )
                if status == "downloading":
                    update_job(
                        job_id,
                        progress=min(24, 5 + int(percentage * 0.19)),
                        sub_progress=int(percentage),
                        message="Mengunduh video sumber...",
                        sub_message=f"Download: {format_bytes(downloaded)} dari {total_text} ({percentage:.0f}%) · {speed}",
                    )
                else:
                    update_job(
                        job_id,
                        progress=24,
                        sub_progress=100,
                        message="Download selesai!",
                        sub_message="Menggabungkan stream video dan audio...",
                    )

        ydl_options = {
            "noplaylist": True,
            "restrictfilenames": True,
            "ffmpeg_location": ffmpeg_path,
            "format": format_selector,
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "http_chunk_size": 10485760,
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
            "buffersize": 1024 * 1024,
            "socket_timeout": 30,
        }
        fixed_total = 0.0
        fixed_total_is_estimate = False
        try:
            with yt_dlp.YoutubeDL({key: value for key, value in ydl_options.items() if key != "progress_hooks"}) as probe:
                metadata = probe.extract_info(url, download=False)
            source_title = str(metadata.get("title") or metadata.get("fulltitle") or url)
            update_job(job_id, source_title=source_title)
            (job_dir / "video.json").write_text(
                json.dumps({"title": source_title, "url": url}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            selected_formats = metadata.get("requested_formats") or [metadata]
            sizes = []
            for selected_format in selected_formats:
                exact_size = selected_format.get("filesize")
                estimated_size = selected_format.get("filesize_approx")
                if exact_size:
                    sizes.append((float(exact_size), False))
                elif estimated_size:
                    sizes.append((float(estimated_size), True))
            if sizes:
                fixed_total = sum(size for size, _ in sizes)
                fixed_total_is_estimate = any(is_estimate for _, is_estimate in sizes)
                label = ("~" if fixed_total_is_estimate else "") + format_bytes(fixed_total)
                update_job(
                    job_id,
                    progress=5,
                    sub_progress=0,
                    message=f"Menyiapkan download · total {label}...",
                    sub_message=f"Total ukuran diperkirakan: {label}",
                )
        except Exception:
            pass

        try:
            with yt_dlp.YoutubeDL(ydl_options) as downloader:
                downloader.download([url])
        except Exception as dl_err:
            if "403" in str(dl_err) or "Forbidden" in str(dl_err):
                logger.warning(f"Download 403 Forbidden terdeteksi ({dl_err}), mencoba format alternatif...")
                alt_options = dict(ydl_options)
                alt_options["format"] = f"b[height<={max_height}]/best"
                with yt_dlp.YoutubeDL(alt_options) as alt_downloader:
                    alt_downloader.download([url])
            else:
                raise
    except ImportError:
        run_command(
            yt_dlp_command()
            + [
                "--no-playlist",
                "--restrict-filenames",
                "--ffmpeg-location",
                ffmpeg_path,
                "-f",
                format_selector,
                "--merge-output-format",
                "mp4",
                "-o",
                output_template,
                url,
            ]
        )
    merged = job_dir / "source.mp4"
    if merged.exists() and merged.stat().st_size > 0:
        return merged
    candidates = sorted(job_dir.glob("source.*"))
    candidates = [p for p in candidates if p.suffix.lower() not in {".part", ".ytdl"}]
    if not candidates:
        raise RuntimeError("Video tidak ditemukan setelah proses download.")
    return max(candidates, key=lambda p: p.stat().st_size)


def download_raw_job(job_id: str, url: str, quality: str) -> Path:
    raw_dir = RAW_VIDEO_DIR / job_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    video = download_video(url, raw_dir, quality, job_id)
    with JOBS_LOCK:
        title = JOBS[job_id].source_title or video.stem
    (raw_dir / "video.json").write_text(
        json.dumps({"title": title, "url": url}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    update_job(
        job_id,
        source_path=str(video),
        source_url=f"/raw/{job_id}/{video.name}",
        source_title=title,
        status="downloaded",
        progress=100,
        message=f"Video siap digunakan · {video.name}",
    )
    return video


def import_local_video(job_id: str, source: Path) -> Path:
    if not source.is_file():
        raise RuntimeError("File video tidak ditemukan.")
    allowed = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
    if source.suffix.lower() not in allowed:
        raise RuntimeError("Format video belum didukung. Gunakan MP4, MOV, MKV, WEBM, AVI, atau M4V.")
    raw_dir = RAW_VIDEO_DIR / job_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / f"source{source.suffix.lower()}"
    shutil.copy2(source, destination)
    source_title = source.stem
    (raw_dir / "video.json").write_text(
        json.dumps({"title": source_title, "url": str(source)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    update_job(
        job_id,
        source_path=str(destination),
        source_url=f"/raw/{job_id}/{destination.name}",
        source_title=source_title,
        status="downloaded",
        progress=100,
        message=f"File siap digunakan · {source.name}",
    )
    return destination


def extract_audio(video_path: Path, audio_path: Path) -> None:
    if audio_path.is_file() and audio_path.stat().st_size > 100_000:
        return
    existing_audio = video_path.parent / "audio.wav"
    if (
        existing_audio.is_file()
        and existing_audio.stat().st_size > 100_000
        and existing_audio.resolve() != audio_path.resolve()
    ):
        try:
            shutil.copyfile(existing_audio, audio_path)
            return
        except Exception:
            pass
    run_command(
        ffmpeg_command()
        + [
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(audio_path),
        ]
    )


def chunk_segment_text(text: str, max_lines: int = 2) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    words_list = clean.split()
    if max_lines == -1:
        return [clean]

    lines_limit = 2 if max_lines <= 0 else max_lines
    max_words = 5 if lines_limit == 1 else 9
    max_chars = 26 if lines_limit == 1 else 52

    chunks: list[list[str]] = []
    curr: list[str] = []
    curr_len = 0
    for w in words_list:
        if curr and (len(curr) >= max_words or (curr_len + len(w) + 1) > max_chars):
            chunks.append(curr)
            curr = [w]
            curr_len = len(w)
        else:
            curr.append(w)
            curr_len += len(w) + (1 if len(curr) > 1 else 0)
    if curr:
        chunks.append(curr)

    formatted: list[str] = []
    for c in chunks:
        if lines_limit >= 2 and (len(c) >= 5 or len(" ".join(c)) > 26):
            mid = len(c) // 2
            formatted.append(" ".join(c[:mid]) + "\n" + " ".join(c[mid:]))
        else:
            formatted.append(" ".join(c))
    return formatted


# ==============================================================================
# INDONESIAN TRANSCRIPT NORMALIZATION (ANTI-SLANG & PHONETIC ERROR STT)
# ==============================================================================
INDONESIAN_TRANSCRIPT_NORMALIZATION_MAP: dict[str, str] = {
    "galaw": "galau",
    "kalaw": "kalau",
    "walaw": "walau",
    "ataw": "atau",
    "taw": "tau",
    "kacaw": "kacau",
    "pantaw": "pantau",
    "pisaw": "pisau",
    "pisaow": "pisau",
    "galow": "galau",
    "kalo": "kalau",
    "klo": "kalau",
    "klw": "kalau",
    "enggak": "nggak",
    "gga": "nggak",
    "ga": "nggak",
    "gk": "nggak",
    "gak": "nggak",
    "ngga": "nggak",
    "sebenernya": "sebenarnya",
    "gmn": "gimana",
    "knp": "kenapa",
    "bgt": "banget",
    "trs": "terus",
    "udh": "udah",
    "aj": "aja",
    "kyk": "kayak",
    "kek": "kayak",
    "dgn": "dengan",
    "krn": "karena",
    "bkn": "bukan",
    "sdh": "sudah",
    "blm": "belum",
    "tp": "tapi",
}

_SORTED_NORM_KEYS = sorted(INDONESIAN_TRANSCRIPT_NORMALIZATION_MAP.keys(), key=len, reverse=True)
_INDONESIAN_NORM_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _SORTED_NORM_KEYS) + r")\b",
    flags=re.IGNORECASE,
)


def normalize_indonesian_transcript_text(text: str) -> str:
    if not text:
        return ""

    def _replace_match(m: re.Match[str]) -> str:
        word = m.group(0)
        norm = INDONESIAN_TRANSCRIPT_NORMALIZATION_MAP.get(word.lower())
        if not norm:
            return word
        if word.isupper():
            return norm.upper()
        if word.istitle() or (len(word) > 0 and word[0].isupper()):
            return norm.capitalize()
        return norm.lower()

    return _INDONESIAN_NORM_REGEX.sub(_replace_match, text)


def split_segment_into_cues(
    item_start: float, item_end: float, text: str, max_lines: int = 2
) -> list[tuple[float, float, str]]:
    cues = chunk_segment_text(text, max_lines=max_lines)
    if not cues or len(cues) <= 1:
        return [(item_start, item_end, cues[0] if cues else text)]
    total_dur = max(0.2, item_end - item_start)
    total_chars = sum(len(c.replace("\n", " ")) for c in cues) or 1
    result: list[tuple[float, float, str]] = []
    curr_start = item_start
    for i, c in enumerate(cues):
        if i == len(cues) - 1:
            c_end = item_end
        else:
            char_count = len(c.replace("\n", " "))
            dur = max(0.3, total_dur * (char_count / total_chars))
            c_end = min(item_end - 0.1, curr_start + dur)
        result.append((round(curr_start, 2), round(c_end, 2), c))
        curr_start = c_end
    return result


def group_words_into_cues(words_list: list[Any], max_words: int = 5, max_chars: int = 28) -> list[dict[str, Any]]:
    if not words_list:
        return []
    cues: list[dict[str, Any]] = []
    curr_words: list[str] = []
    curr_word_objs: list[dict[str, Any]] = []
    curr_start: float | None = None
    curr_end: float = 0.0

    for w in words_list:
        w_text = getattr(w, "word", "")
        if not w_text and isinstance(w, dict):
            w_text = w.get("word", "")
        if not w_text:
            w_text = str(w)
        w_text = normalize_indonesian_transcript_text(w_text.strip())
        if not w_text:
            continue

        w_start = float(
            getattr(w, "start", 0.0)
            if hasattr(w, "start")
            else (w.get("start", curr_end) if isinstance(w, dict) else curr_end)
        )
        w_end = float(
            getattr(w, "end", w_start + 0.3)
            if hasattr(w, "end")
            else (w.get("end", w_start + 0.3) if isinstance(w, dict) else w_start + 0.3)
        )

        if curr_words and (
            len(curr_words) >= max_words
            or sum(len(x) + 1 for x in curr_words) + len(w_text) > max_chars
            or (w_start - curr_end) > 0.8
        ):
            cues.append({
                "start": round(curr_start if curr_start is not None else 0.0, 2),
                "end": round(curr_end, 2),
                "text": " ".join(curr_words),
                "words": list(curr_word_objs),
            })
            curr_words = [w_text]
            curr_word_objs = [{"word": w_text, "start": round(w_start, 2), "end": round(w_end, 2)}]
            curr_start = w_start
            curr_end = w_end
        else:
            if curr_start is None:
                curr_start = w_start
            curr_words.append(w_text)
            curr_word_objs.append({"word": w_text, "start": round(w_start, 2), "end": round(w_end, 2)})
            curr_end = max(curr_end, w_end)

    if curr_words and curr_start is not None:
        cues.append({
            "start": round(curr_start, 2),
            "end": round(curr_end, 2),
            "text": " ".join(curr_words),
            "words": list(curr_word_objs),
        })
    return cues


def transcribe_with_gemini(
    audio_path: Path, language: str | None = None, job_id: str | None = None
) -> list[dict[str, Any]]:
    api_key = get_active_gemini_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY belum diisi. Masukkan API Key di pengaturan.")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    if job_id:
        update_job(
            job_id,
            progress=30,
            sub_progress=25,
            message="Mengunggah audio ke Gemini Cloud...",
            sub_message="Mengirim file audio ke server Google...",
        )
    logger.info(f"Mengunggah audio ke Gemini Files API: {audio_path.name}")
    audio_file = client.files.upload(file=str(audio_path))

    prompt = (
        "Kamu adalah transkriber audio podcast Bahasa Indonesia profesional berakurasi tinggi.\n"
        "Tugas utama: Dengarkan audio secara seksama dan transkripsikan setiap percakapan menjadi segmen subtitle pendek yang presisi.\n\n"
        "ATURAN WAJIB & KETAT:\n"
        "1. KONTEN & KONSISTENSI KONTEKS (ANTI-HALUSINASI FONETIK):\n"
        "   - Apabila pembicara berbicara sangat cepat, bergumam (mumble), atau terjadi suara tumpang tindih (crosstalk), "
        "simaklah konteks kalimat dan topik pembicaraan secara utuh. Hasilkan kata-kata yang logis dan bermakna sesuai topik, "
        "dilarang keras mengarang kata aneh atau halusinasi fonetik tanpa arti.\n"
        "2. STANDAR EJAAN BAKU & BAHASA PERCAKAPAN RAPI:\n"
        "   - DILARANG KERAS menggunakan ejaan alay atau ejaan fonetik berakhiran 'w' seperti 'galaw', 'kalaw', 'ataw', 'walaw'. "
        "Wajib gunakan ejaan KBBI atau ragam percakapan standar yang rapi (seperti: 'galau', 'kalau', 'atau', 'walau', 'nggak', 'banget', 'sebenarnya', 'gimana', 'kenapa', 'terus', 'udah', 'kayak').\n"
        "   - Tuliskan tanda baca yang sesuai (. , ? !) dan huruf kapital yang benar di awal kalimat.\n"
        "3. FORMAT SUBTITLE & TIMING:\n"
        "   - Bagi audio menjadi frasa pendek yang alami (maksimal 4 hingga 6 kata atau sekitar 1.5 hingga 2.5 detik per segmen).\n"
        "   - Nilai timestamp 'start' dan 'end' (dalam satuan detik float) harus benar-benar presisi mengikuti ucapan pembicara yang sebenarnya "
        "agar subtitle berganti tepat saat pembicara melanjutkan kalimat.\n"
        "4. FORMAT OUTPUT:\n"
        "   - Kembalikan HANYA array JSON murni dari objek: [{\"start\": float, \"end\": float, \"text\": \"string percakapan\"}].\n"
        "   - Nilai timestamp harus berupa angka float positif dan berurutan secara kronologis. Dilarang menyertakan teks pengantar atau markdown backticks."
    )
    if language and language != "auto":
        prompt += f"\nBahasa utama percakapan adalah: {language}."

    if job_id:
        update_job(
            job_id,
            progress=45,
            sub_progress=65,
            message="Mentranskrip audio via Gemini API...",
            sub_message="Gemini menganalisis pembicaraan & timestamp...",
        )
    logger.info("Mengirim audio ke Gemini API...")
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[audio_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    if job_id:
        update_job(
            job_id,
            progress=58,
            sub_progress=95,
            message="Menerima hasil transkripsi dari Cloud...",
            sub_message="Menyusun segmen subtitle...",
        )
    try:
        client.files.delete(name=audio_file.name)
    except Exception:
        pass

    raw_text = (response.text or "").strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
        raw_text = re.sub(r"\s*```$", "", raw_text, flags=re.MULTILINE).strip()
    data = json.loads(raw_text)
    if isinstance(data, dict) and "segments" in data:
        data = data["segments"]
    result = []
    for item in data:
        start = float(item.get("start", 0))
        end = float(item.get("end", 0))
        raw_item_text = str(item.get("text", "")).strip()
        text = normalize_indonesian_transcript_text(raw_item_text)
        if text and end > start:
            w_list = text.split()
            if (end - start) > 3.2 or len(w_list) > 6:
                sub_cues = split_segment_into_cues(start, end, text, max_lines=1)
                for s_start, s_end, s_text in sub_cues:
                    s_clean = normalize_indonesian_transcript_text(s_text.strip())
                    if s_end > s_start and s_clean:
                        result.append({"start": round(s_start, 2), "end": round(s_end, 2), "text": s_clean})
            else:
                result.append({"start": round(start, 2), "end": round(end, 2), "text": text})

    result.sort(key=lambda x: x["start"])
    for i in range(len(result) - 1):
        if result[i]["end"] > result[i + 1]["start"]:
            result[i]["end"] = max(result[i]["start"] + 0.2, result[i + 1]["start"])

    if not result:
        raise ValueError("Gemini tidak mendeteksi teks audio yang valid.")
    return result


def transcribe(
    audio_path: Path, language: str | None, model_size: str = "small", job_id: str | None = None
) -> list[dict[str, Any]]:
    language = None if language == "auto" else language
    if model_size == "gemini":
        try:
            return transcribe_with_gemini(audio_path, language, job_id=job_id)
        except Exception as exc:
            logger.warning(f"Transkripsi Gemini gagal ({exc}), mencoba fallback ke Whisper lokal...")
            if job_id:
                update_job(
                    job_id,
                    message="Peringatan: Gemini Audio gagal, beralih ke Whisper lokal...",
                    sub_message=f"Kendala: {str(exc)[:60]}",
                )
            model_size = "small"
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Paket faster-whisper belum terpasang.") from exc

    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    cpu_threads = int(os.getenv("WHISPER_CPU_THREADS", str(max(2, min(4, (os.cpu_count() or 4) - 1)))))

    def load_whisper(dev: str, comp: str) -> Any:
        return WhisperModel(model_size, device=dev, compute_type=comp, cpu_threads=cpu_threads)

    whisper_kwargs: dict[str, Any] = {
        "language": language,
        "vad_filter": True,
        "word_timestamps": True,
        "condition_on_previous_text": True,
        "initial_prompt": (
            "Percakapan podcast Bahasa Indonesia dengan ejaan rapi dan baku: "
            "kalau, galau, atau, nggak, banget, sebenarnya, gimana, kenapa, terus, jadi, karena."
        ),
    }

    def do_transcribe(m: Any) -> Any:
        try:
            import av

            original_av_open = av.open

            def compatible_av_open(*args: Any, **kwargs: Any) -> Any:
                kwargs.pop("metadata_errors", None)
                return original_av_open(*args, **kwargs)

            av.open = compatible_av_open  # type: ignore[assignment]
            try:
                return m.transcribe(str(audio_path), **whisper_kwargs)
            finally:
                av.open = original_av_open  # type: ignore[assignment]
        except ImportError:
            return m.transcribe(str(audio_path), **whisper_kwargs)

    try:
        model = load_whisper(device, compute_type)
        segments, info = do_transcribe(model)
    except Exception as exc:
        if device != "cpu":
            logger.warning(f"Whisper device '{device}' gagal ({exc}), otomatis beralih ke CPU...")
            model = load_whisper("cpu", "int8")
            segments, info = do_transcribe(model)
        else:
            raise
    result = []
    total_dur = getattr(info, "duration", 0) or 0
    for segment in segments:
        seg_text = re.sub(r"\s+", " ", segment.text).strip()
        seg_text = normalize_indonesian_transcript_text(seg_text)
        if not seg_text:
            continue
        seg_words = getattr(segment, "words", None)
        if seg_words:
            norm_seg_words: list[Any] = []
            for w in seg_words:
                w_str = (
                    getattr(w, "word", "")
                    if hasattr(w, "word")
                    else (w.get("word", "") if isinstance(w, dict) else str(w))
                )
                norm_w_str = normalize_indonesian_transcript_text(w_str)
                if hasattr(w, "_replace"):
                    norm_seg_words.append(w._replace(word=norm_w_str))
                elif isinstance(w, dict):
                    w_dict = dict(w)
                    w_dict["word"] = norm_w_str
                    norm_seg_words.append(w_dict)
                else:
                    norm_seg_words.append({
                        "word": norm_w_str,
                        "start": getattr(w, "start", 0.0),
                        "end": getattr(w, "end", 0.0),
                    })
            cues = group_words_into_cues(norm_seg_words, max_words=5, max_chars=28)
            for c in cues:
                c["text"] = normalize_indonesian_transcript_text(c["text"])
                if c["end"] > c["start"] and c["text"].strip():
                    result.append(c)
        else:
            sub_cues = split_segment_into_cues(float(segment.start), float(segment.end), seg_text, max_lines=1)
            for c_start, c_end, c_text in sub_cues:
                norm_c_text = normalize_indonesian_transcript_text(c_text)
                if c_end > c_start and norm_c_text.strip():
                    result.append({"start": round(c_start, 2), "end": round(c_end, 2), "text": norm_c_text.strip()})

        if job_id:
            cur_sec = float(segment.end)
            est_dur = total_dur or (cur_sec + 30)
            sub_pct = min(98, max(5, int((cur_sec / est_dur) * 100)))
            overall_pct = min(60, 28 + int(sub_pct * 0.32))
            update_job(
                job_id,
                progress=overall_pct,
                sub_progress=sub_pct,
                message=f"Transkripsi audio dengan Whisper ({overall_pct}%)...",
                sub_message=f"Memproses audio: {int(cur_sec // 60)}m {int(cur_sec % 60):02d}s / {int(est_dur // 60)}m {int(est_dur % 60):02d}s ({sub_pct}%)",
            )

    result.sort(key=lambda x: x["start"])
    for i in range(len(result) - 1):
        if result[i]["end"] > result[i + 1]["start"]:
            result[i]["end"] = max(result[i]["start"] + 0.2, result[i + 1]["start"])

    if not result:
        raise RuntimeError("Tidak ada ucapan yang terdeteksi pada video.")
    if job_id:
        update_job(
            job_id,
            progress=60,
            sub_progress=100,
            message="Transkripsi audio selesai!",
            sub_message="Semua percakapan berhasil diubah menjadi teks",
        )
    return result


def words(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ0-9']+", text.lower())


CLIP_PROFILE_GUIDANCE = {
    "auto": "Kenali sendiri apakah transkrip berasal dari live/streamer atau konten terstruktur. Pilih momen paling kuat sesuai konteksnya.",
    "live": "Ini adalah live atau streamer. Prioritaskan blunder, reaksi spontan, kelucuan, emosi, clutch, konflik, atau interaksi penonton. Sertakan buildup dan reaksi setelah kejadian.",
    "standard": "Ini adalah konten biasa yang terstruktur. Prioritaskan hook, insight, tips, opini kuat, cerita, penjelasan jelas, dan payoff yang tuntas.",
    "manual": "Jangan membuat clip otomatis. Video akan direview untuk penambahan clip manual.",
}

CLIP_FLAVOR_PROFILES: dict[str, dict[str, Any]] = {
    "spicy_drama": {
        "label": "Spicy / Drama / Kontroversi",
        "prompt_rule": (
            "FOKUS UTAMA: Cari momen paling SPICY, DRAMA, DEBAT PANAS, SINDIRAN, PENGAKUAN MENGEJUTKAN, "
            "pembongkaran rahasia (spill tea), opini kontroversial, konflik antar orang, nominal uang/gaji, "
            "atau kalimat pedas yang memancing perdebatan di kolom komentar. Mulai klip tepat di kalimat pertanyaan/pemicu topik!"
        ),
        "headline_rule": (
            "Buat judul Headline 4-7 kata yang SPICY, provokatif, menimbulkan curiosity gap tinggi, "
            "dan merangkum inti topik yang dibahas di klip ini."
        ),
        "keywords": {
            "jujur", "bohong", "bongkar", "rahasia", "parah", "gila", "benci", "muak", "marah",
            "kesal", "sindir", "nyindir", "berani", "egois", "munafik", "selingkuh", "putus",
            "pecat", "bangkrut", "hutang", "miliar", "juta", "duit", "uang", "gaji", "bayar",
            "curang", "kasus", "drama", "ribut", "debat", "salah", "ngawur", "hancur", "kapok",
            "nyesel", "ternyata", "padahal", "jangan", "bahaya", "korban", "pelaku", "bukti", "fakta",
        },
        "energy_weight": 1.65,
        "ideal_min": 45,
        "ideal_max": 115,
    },
    "viral_all": {
        "label": "Viral FYP (Hook Kuat & Plot Twist)",
        "prompt_rule": (
            "FOKUS UTAMA: Cari momen dengan potensi VIRAL FYP tertinggi. Harus memiliki Hook/Pertanyaan kuat di "
            "awal klip, alur cerita/jawaban yang padat, dan ditutup dengan Plot Twist atau kesimpulan yang memuaskan."
        ),
        "headline_rule": "Buat judul Headline 4-7 kata yang sangat catchy, bikin penasaran, dan merangkum topik utama.",
        "keywords": {
            "ternyata", "rahasia", "cara", "jangan", "pernah", "alasan", "kenapa", "mengapa",
            "pertama", "terakhir", "paling", "terbaik", "terburuk", "fakta", "bukti", "kaget",
            "mustahil", "ajaib", "solusi", "kesalahan", "fatal", "untung", "rugi",
        },
        "energy_weight": 1.35,
        "ideal_min": 45,
        "ideal_max": 115,
    },
    "funny_blunder": {
        "label": "Komedi / Ngakak / Blunder",
        "prompt_rule": (
            "FOKUS UTAMA: Cari momen paling LUCU, NGAKAK, BLUNDER konyol, salah ngomong, roasting "
            "antar teman, atau reaksi spontan yang mengundang tawa. Sertakan setup cerita sebelum kelucuan "
            "dan tawa pecah setelahnya."
        ),
        "headline_rule": "Buat judul Headline 4-7 kata yang kocak dan merangkum momen lucu di dalam klip.",
        "keywords": {
            "haha", "wkwk", "anjir", "astaga", "waduh", "kocak", "lucu", "ngakak", "blunder",
            "bodoh", "tolol", "konyol", "malu", "jatuh", "gagal", "salah", "ketawa", "asli",
        },
        "energy_weight": 1.85,
        "ideal_min": 35,
        "ideal_max": 95,
    },
    "deep_meat": {
        "label": "Daging / Insight / Mindblowing",
        "prompt_rule": (
            "FOKUS UTAMA: Cari kutipan paling BERBOBOT ('daging'), prinsip hidup, strategi bisnis/uang, "
            "nasihat menohok, atau perspektif cerdas yang membuat penonton menyimpan (save/bookmark) video ini."
        ),
        "headline_rule": "Buat judul Headline 4-7 kata yang tegas, berwibawa, dan merangkum insight emas di dalam klip.",
        "keywords": {
            "prinsip", "kunci", "sukses", "kaya", "mental", "strategi", "ilmu", "pelajaran",
            "hidup", "masa", "depan", "investasi", "bisnis", "kerja", "fokus", "disiplin", "paham",
        },
        "energy_weight": 1.0,
        "ideal_min": 45,
        "ideal_max": 120,
    },
    "hype_rage": {
        "label": "Hype Tinggi / Teriakan / Rage Gaming",
        "prompt_rule": (
            "FOKUS UTAMA: Cari momen dengan energi suara dan tensi paling meledak: teriakan kaget, "
            "rage/marah saat main game, momen clutch menegangkan, atau reaksi heboh maksimal."
        ),
        "headline_rule": "Buat judul Headline 4-7 kata penuh energi yang menggambarkan ketegangan/ledakan emosi momen tersebut.",
        "keywords": {
            "anjing", "anjir", "gila", "mati", "menang", "kalah", "clutch", "hoki", "curang",
            "lari", "tolong", "awas", "kena", "habis", "pecah", "meledak",
        },
        "energy_weight": 2.4,
        "ideal_min": 30,
        "ideal_max": 85,
    },
}

FILLER_STARTERS = {"eh", "ee", "emm", "anu", "jadi", "nah", "oke", "terus", "umm", "uh", "ya"}

BAD_CLIP_START_WORDS = (
    "kalau", "kalo", "karena", "sebab", "jadi", "terus", "lalu", "kemudian",
    "tapi", "tetapi", "namun", "makanya", "misalnya", "contohnya", "soalnya",
    "padahal", "bahkan", "artinya", "apalagi", "sedangkan", "sementara",
    "habis", "setelah", "waktu itu", "pas itu", "ya itu", "itu yang",
    "makanya kalau", "dan", "atau", "yang", "nah kalau", "kan kalau", "ususnya",
)

INTRO_OUTRO_BLACKLIST = (
    "selamat datang",
    "kembali lagi di podcast",
    "kembali lagi bersama",
    "welcome back",
    "gimana kabarnya",
    "apa kabar bro",
    "apa kabar mas",
    "sehat bro",
    "sehat bang",
    "sehat mas",
    "terima kasih sudah datang",
    "makasih udah mampir",
    "makasih udah datang",
    "thanks for coming",
    "thank you for coming",
    "jangan lupa subscribe",
    "jangan lupa like",
    "klik tombol like",
    "klik subscribe",
    "follow akun kita",
    "sponsor kita hari ini",
    "didukung oleh",
    "episode kali ini disponsori",
    "link di deskripsi",
    "cek deskripsi di bawah",
    "sampai jumpa di episode",
    "see you in the next",
    "closing statement",
)


def compute_audio_energy_map(audio_path: Path, window_sec: float = 1.0) -> list[float]:
    import array
    import math
    import wave

    energies: list[float] = []
    try:
        if not audio_path.is_file():
            return []
        with wave.open(str(audio_path), "rb") as wf:
            rate = wf.getframerate()
            chunk_frames = max(1, int(rate * window_sec))
            while True:
                raw = wf.readframes(chunk_frames)
                if not raw:
                    break
                samples = array.array("h", raw)
                if not samples:
                    energies.append(0.0)
                    continue
                rms = math.sqrt(sum(float(s) * float(s) for s in samples) / len(samples))
                energies.append(rms)
    except Exception:
        return []

    if not energies:
        return []
    peak = max(energies) or 1.0
    return [round(val / peak, 3) for val in energies]


def get_window_energy_score(energy_map: list[float], start: float, end: float) -> float:
    if not energy_map:
        return 0.5
    s_idx = max(0, int(start))
    e_idx = min(len(energy_map), max(s_idx + 1, int(end) + 1))
    sub = energy_map[s_idx:e_idx]
    if not sub:
        return 0.5
    return round((max(sub) * 0.7) + ((sum(sub) / len(sub)) * 0.3), 3)


def is_intro_or_outro_text(text: str) -> bool:
    clean = re.sub(r"\s+", " ", text.strip().lower())
    if not clean:
        return False
    return any(phrase in clean for phrase in INTRO_OUTRO_BLACKLIST)


def get_podcast_intro_skip_seconds(total_duration: float) -> float:
    if total_duration >= 600.0:
        return min(150.0, max(75.0, total_duration * 0.04))
    return 0.0


def is_intro_teaser_highlight(seg: dict[str, Any], skip_seconds: float) -> bool:
    start = float(seg.get("start", 0.0))
    end = float(seg.get("end", 0.0))
    if start >= skip_seconds:
        return False
    dur = end - start
    energy = float(seg.get("energy", 0.5))
    txt = str(seg.get("text", ""))
    if is_intro_or_outro_text(txt):
        return False
    return energy >= 0.72 and (12.0 <= dur <= 65.0)


def condense_transcript_for_llm(
    transcript: list[dict[str, Any]],
    energy_map: list[float] | None = None,
    filter_intro: bool = False,
) -> list[dict[str, Any]]:
    """
    Menggabungkan potongan cues pendek menjadi kalimat utuh disertai nomor indeks dan indikator energi.
    Jangan pernah menghapus kalimat di tengah percakapan agar konteks tanya-jawab utuh!
    """
    if not transcript:
        return []
    total_duration = float(transcript[-1]["end"]) if transcript else 0.0
    skip_sec = get_podcast_intro_skip_seconds(total_duration) if filter_intro else 0.0

    merged: list[dict[str, Any]] = []
    curr_start = float(transcript[0]["start"])
    curr_end = float(transcript[0]["end"])
    curr_texts: list[str] = [str(transcript[0].get("text", "")).strip()]

    for item in transcript[1:]:
        s = float(item["start"])
        e = float(item["end"])
        txt = str(item.get("text", "")).strip()
        if not txt:
            continue
        prev_txt = curr_texts[-1] if curr_texts else ""
        is_sentence_end = bool(re.search(r"[.!?]$", prev_txt))
        if (s - curr_end > 0.65) or (is_sentence_end and (curr_end - curr_start >= 3.5)) or (e - curr_start >= 10.0):
            seg_text = normalize_indonesian_transcript_text(" ".join(curr_texts))
            seg_obj: dict[str, Any] = {
                "id": len(merged),
                "start": round(curr_start, 2),
                "end": round(curr_end, 2),
                "text": seg_text,
            }
            if energy_map:
                seg_obj["energy"] = get_window_energy_score(energy_map, curr_start, curr_end)

            if not (filter_intro and curr_start < skip_sec and is_intro_or_outro_text(seg_text)):
                merged.append(seg_obj)
            curr_start = s
            curr_end = e
            curr_texts = [txt]
        else:
            curr_end = e
            curr_texts.append(txt)

    if curr_texts:
        seg_text = normalize_indonesian_transcript_text(" ".join(curr_texts))
        seg_obj = {
            "id": len(merged),
            "start": round(curr_start, 2),
            "end": round(curr_end, 2),
            "text": seg_text,
        }
        if energy_map:
            seg_obj["energy"] = get_window_energy_score(energy_map, curr_start, curr_end)
        if not (filter_intro and curr_start < skip_sec and is_intro_or_outro_text(seg_text)):
            merged.append(seg_obj)

    return merged


def split_transcript(
    transcript: list[dict[str, Any]],
    mode: str,
    split_count: int,
    segment_duration: int,
    total_duration: float | None = None,
) -> list[dict[str, Any]]:
    if not transcript:
        return []
    total = max(float(total_duration or transcript[-1]["end"]), 1.0)
    if mode == "split_count":
        duration = total / split_count
        ranges = [(index * duration, min(total, (index + 1) * duration)) for index in range(split_count)]
    else:
        ranges = [(start, min(total, start + segment_duration)) for start in range(0, int(total), segment_duration)]
    return [
        {"start": start, "end": end, "score": 0.0, "title": f"Part {index:02} ({int(end - start)} detik)"}
        for index, (start, end) in enumerate(ranges, start=1)
        if end - start > 0.5
    ]


def gguf_path_for(model_name: str) -> str:
    configured = QWEN_GGUF_PATH if model_name == "qwen" else HERMES_GGUF_PATH
    if configured and Path(configured).is_file():
        return configured
    patterns = ["*qwen*.gguf", "*Qwen*.gguf"] if model_name == "qwen" else ["*hermes*.gguf", "*Hermes*.gguf"]
    for pattern in patterns:
        matches = sorted(MODEL_DIR.glob(pattern))
        if matches:
            return str(matches[0])
    all_gguf = sorted(MODEL_DIR.glob("*.gguf"))
    if all_gguf:
        return str(all_gguf[0])
    return ""


def load_local_gguf(model_name: str) -> Any | None:
    model_path = gguf_path_for(model_name)
    if not model_path or not Path(model_path).is_file():
        return None
    try:
        from llama_cpp import Llama
    except ImportError:
        logger.warning("llama_cpp belum terpasang; tidak dapat memuat model GGUF.")
        return None
    try:
        with GGUF_LOCK:
            model = GGUF_MODELS.get(model_path)
            if model is None:
                model = Llama(
                    model_path=model_path,
                    n_ctx=min(GGUF_N_CTX, 4096),
                    n_gpu_layers=GGUF_N_GPU_LAYERS,
                    verbose=False,
                )
                GGUF_MODELS[model_path] = model
            return model
    except Exception as exc:
        logger.warning(f"Gagal memuat model GGUF ({model_path}): {exc}")
        return None


def clip_transcript_text(transcript: list[dict[str, Any]], start: float, end: float) -> str:
    return " ".join(item["text"] for item in transcript if item["start"] < end and item["end"] > start).strip()


def is_raw_transcript_fragment(title: str, clip_text: str = "") -> bool:
    """
    Mendeteksi apakah judul merupakan potongan kalimat mentah yang jelek/menggantung
    (seperti 'Kalau tau kan, barang segera gini. Ususnya').
    """
    clean = re.sub(r"\s+", " ", (title or "")).strip().strip('"').strip("'")
    if not clean:
        return True
    toks = words(clean)
    if len(toks) < 3 or len(toks) > 10:
        return True

    low = clean.lower()
    # Mengandung titik di tengah kalimat (2 kalimat terpotong, misal "Barang segera gini. Ususnya")
    if "." in clean[:-1] or "," in clean:
        return True

    # Diawali kata sambung/percakapan mentah
    if any(low.startswith(w + " ") or low == w for w in BAD_CLIP_START_WORDS):
        return True
    if any(
        low.startswith(p)
        for p in ("iya ", "ya ", "oh ", "eh ", "nah ", "kan ", "jadi ", "terus ", "waktu itu ", "ternyata dia ")
    ):
        return True

    # Diakhiri kata gantung
    if toks[-1] in {
        "nya", "ususnya", "kan", "gini", "gitu", "dong", "deh", "sih", "yang",
        "dan", "atau", "di", "ke", "dari", "itu", "ini", "sama", "buat", "kalau",
    }:
        return True

    # Jika judul adalah substring persis dari kalimat tengah transkrip yang diawali huruf kecil
    if clip_text and len(clean) > 15:
        norm_clip = re.sub(r"\s+", " ", clip_text.lower())
        if low in norm_clip and not low.startswith(("kenapa", "mengapa", "bagaimana", "gimana", "apa", "siapa", "rahasia", "alasan", "fakta", "bahaya", "cara")):
            return True

    return False


def fallback_metadata(text: str, current_title: str = "") -> tuple[str, str, list[str]]:
    clean_text = re.sub(r"\s+", " ", text).strip()
    title = current_title.strip()

    if is_raw_transcript_fragment(title, clean_text):
        # Cari kalimat tanya atau kalimat topik utuh tanpa koma/titik gantung
        sentences = [s.strip() for s in re.split(r"[.!?]+", clean_text) if len(words(s.strip())) >= 4]
        chosen = ""
        for s in sentences:
            s_clean = re.sub(r"^[,;\-\s]+", "", s).strip()
            s_low = s_clean.lower()
            if not any(s_low.startswith(w + " ") for w in BAD_CLIP_START_WORDS):
                if any(
                    w in s_low
                    for w in ("kenapa", "gimana", "apa", "rahasia", "alasan", "fakta", "bahaya", "cerita", "hukum", "uang", "kesehatan")
                ):
                    chosen = s_clean
                    break
        if not chosen and sentences:
            for s in sentences:
                s_clean = re.sub(r"^[,;\-\s]+", "", s).strip()
                if not any(s_clean.lower().startswith(w + " ") for w in BAD_CLIP_START_WORDS):
                    chosen = s_clean
                    break
        if chosen:
            # Ambil 5-7 kata utuh tanpa koma
            chosen_no_comma = chosen.split(",")[0].strip()
            w_tokens = chosen_no_comma.split()
            if len(w_tokens) >= 4:
                title = " ".join(w_tokens[:7]).title()
            else:
                title = " ".join(chosen.split()[:6]).title()
        else:
            # Ekstrak kata kunci topik
            stop_w = {
                "yang", "dan", "di", "ke", "dari", "ini", "itu", "kalau", "kalo", "karena",
                "jadi", "terus", "tapi", "sama", "buat", "untuk", "dengan", "ada", "bisa",
                "kita", "kami", "saya", "aku", "kamu", "dia", "mereka", "nggak", "enggak",
                "udah", "sudah", "aja", "saja", "kan", "gini", "gitu", "tau", "tahu",
            }
            important = [w.capitalize() for w in words(clean_text) if len(w) >= 4 and w not in stop_w]
            uniq_imp = list(dict.fromkeys(important))[:4]
            title = f"Fakta Penting Tentang {' '.join(uniq_imp[:3])}" if uniq_imp else "Pembahasan Penting Podcast"

    caption = clean_text[:280] + ("..." if len(clean_text) > 280 else "")
    tokens = [token for token in words(clean_text) if len(token) >= 5]
    hashtags = ["#podcastindonesia", "#fyp"]
    for token in tokens:
        tag = f"#{token}"
        if tag not in hashtags and not is_sensitive_content(token):
            hashtags.append(tag)
        if len(hashtags) >= 5:
            break
    return title, caption, hashtags


def generate_clip_metadata(
    transcript: list[dict[str, Any]],
    clips: list[Clip],
    model_name: str,
    flavor: str = "spicy_drama",
    spicy_hook: bool = True,
) -> None:
    if not clips:
        return
    custom_titles = [clip.source == "manual" and bool(clip.title.strip()) for clip in clips]
    for clip in clips:
        text = clip_transcript_text(transcript, clip.start, clip.end)
        curr_t = "" if is_raw_transcript_fragment(clip.title, text) else clip.title
        fallback_t, fallback_c, fallback_tags = fallback_metadata(text, curr_t)
        clip.title = fallback_t
        if not clip.caption:
            clip.caption = fallback_c
        if not clip.hashtags:
            clip.hashtags = fallback_tags

    items = [
        {
            "index": index,
            "start": clip.start,
            "end": clip.end,
            "core_topic": getattr(clip, "core_topic", ""),
            "text": clip_transcript_text(transcript, clip.start, clip.end),
        }
        for index, clip in enumerate(clips, start=1)
    ]
    prompt = (
        "Kamu adalah Produser Konten & Copywriter Sosial Media Profesional untuk Podcast Video Viral (TikTok, Reels, Shorts).\n"
        "TUGAS WAJIB: Baca dan pahami KESELURUHAN dialog di dalam setiap klip berikut secara utuh dari awal sampai akhir, "
        "lalu rumuskan metadata yang 100% nyambung dan akurat dengan konteks pembicaraan.\n\n"
        "ATURAN FORMULASI METADATA PER KLIP:\n"
        "1. TITLE (Judul Banner/Hook):\n"
        "   - Wajib merangkum INTI TOPIK atau PERNYATAAN PALING MENGEJUTKAN di dalam klip tersebut.\n"
        "   - Panjang 4 sampai 7 kata, padat, utuh, dan jelas subjek/masalahnya.\n"
        "   - Gunakan Title Case (Contoh Benar: 'Hukum & Bahaya Makan Usus Ayam', 'Alasan Sebenarnya Resign dari TV').\n"
        "   - DILARANG KERAS menyalin kalimat ucapan mentah pembicara sebagai title (seperti 'Kalau Tau Kan, Barang Segera Gini. Ususnya' atau 'Jadi Waktu Itu Aku...').\n"
        "   - DILARANG KERAS menggunakan tanda titik (.) atau koma (,) di tengah judul!\n"
        "2. CAPTION (Deskripsi Post):\n"
        "   - Tepat 2 kalimat pendek yang menjelaskan konteks obrolan narasumber diikuti 1 pertanyaan pancingan diskusi.\n"
        "3. HASHTAGS:\n"
        "   - Array 5 hashtag relevan termasuk '#podcastindonesia' dan '#fyp'.\n\n"
        "ATURAN KETAT ANTI-PELANGGARAN TIKTOK:\n"
        "- DILARANG memunculkan kata vulgar, kekerasan, pembunuhan, darah, kematian, sakaratul maut, sekte, setan, pelecehan, atau narkoba.\n\n"
        "FORMAT OUTPUT:\n"
        "Balas HANYA JSON array valid tanpa markdown:\n"
        '[{"index": 1, "title": "Judul Rangkuman Inti Topik", "caption": "Penjelasan konteks obrolan di klip ini. Bagaimana menurut kalian?", "hashtags": ["#topik", "#tokoh", "#opini", "#podcastindonesia", "#fyp"]}]\n\n'
        "CLIPS:\n"
        + json.dumps(items, ensure_ascii=False)
    )

    api_key = get_active_gemini_api_key()
    if model_name == "gemini" or api_key:
        if api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=f"Kamu adalah social media clipper profesional.\n{prompt}",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.25,
                    ),
                )
                parsed = json.loads(response.text)
                if isinstance(parsed, dict):
                    parsed = parsed.get("clips", [])
                for item in parsed:
                    index = int(item["index"]) - 1
                    if not 0 <= index < len(clips):
                        continue
                    raw_new_title = str(item.get("title") or "").strip().rstrip(".")
                    if "." in raw_new_title:
                        raw_new_title = max(raw_new_title.split("."), key=lambda s: len(words(s))).strip()
                    new_title = sanitize_for_tiktok_safety(raw_new_title).strip()
                    new_caption = sanitize_for_tiktok_safety(str(item.get("caption") or "")).strip()
                    tags = item.get("hashtags") or []

                    if not custom_titles[index] and new_title and len(words(new_title)) >= 3:
                        clips[index].title = new_title
                    if new_caption:
                        clips[index].caption = new_caption

                    cleaned_tags = [
                        str(tag) if str(tag).startswith("#") else f"#{tag}"
                        for tag in tags
                        if not is_sensitive_content(str(tag))
                    ]
                    if cleaned_tags:
                        for mandatory in ("#podcastindonesia", "#fyp"):
                            if mandatory not in cleaned_tags:
                                cleaned_tags.append(mandatory)
                        clips[index].hashtags = cleaned_tags[:5]
                return
            except Exception as e:
                logger.warning(f"Gemini Metadata Error: {e}")

    model = load_local_gguf(model_name)
    if model is None:
        return
    try:
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": "Kamu adalah social media editor yang membuat metadata video."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
            max_tokens=max(512, len(clips) * 180),
        )
        content = response["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            parsed = parsed.get("clips", [])
        for item in parsed:
            index = int(item["index"]) - 1
            if not 0 <= index < len(clips):
                continue
            raw_new_title = str(item.get("title") or "").strip().rstrip(".")
            if "." in raw_new_title:
                raw_new_title = max(raw_new_title.split("."), key=lambda s: len(words(s))).strip()
            new_title = sanitize_for_tiktok_safety(raw_new_title).strip()
            new_caption = sanitize_for_tiktok_safety(str(item.get("caption") or "")).strip()
            tags = item.get("hashtags") or []

            if not custom_titles[index] and new_title and len(words(new_title)) >= 3:
                clips[index].title = new_title
            if new_caption:
                clips[index].caption = new_caption

            cleaned_tags = [
                str(tag) if str(tag).startswith("#") else f"#{tag}"
                for tag in tags
                if not is_sensitive_content(str(tag))
            ]
            if cleaned_tags:
                for mandatory in ("#podcastindonesia", "#fyp"):
                    if mandatory not in cleaned_tags:
                        cleaned_tags.append(mandatory)
                clips[index].hashtags = cleaned_tags[:5]
    except Exception:
        return


def ask_local_gguf(
    transcript: list[dict[str, Any]],
    count: int,
    minimum: int,
    maximum: int,
    model_name: str,
    max_clips: int,
    profile: str = "auto",
    custom_prompt: str = "",
    flavor: str = "spicy_drama",
    energy_map: list[float] | None = None,
) -> list[dict[str, Any]] | None:
    model = load_local_gguf(model_name)
    if model is None:
        return None
    condensed = condense_transcript_for_llm(transcript, energy_map, filter_intro=True)
    prompt, eff_min, eff_max = build_clipper_llm_prompt(
        condensed, count, minimum, maximum, max_clips, profile, flavor, custom_prompt
    )
    total_duration = float(transcript[-1]["end"]) if transcript else 0.0
    skip_sec = get_podcast_intro_skip_seconds(total_duration)

    try:
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": "Kamu adalah editor video yang memilih momen paling viral dan utuh konteks tanya-jawabnya."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.20,
            max_tokens=1024,
        )
        content = response["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            parsed = parsed.get("clips", [])
        valid = []
        for item in parsed:
            start = float(item["start"])
            end = float(item["end"])
            duration = end - start
            if end > start and duration >= max(25, eff_min - 15) and duration <= eff_max + 30:
                if start < skip_sec and not is_intro_teaser_highlight(item, skip_sec):
                    continue
                hook_t = str(item.get("hook_title") or item.get("title") or "").strip()
                if is_intro_or_outro_text(hook_t):
                    continue
                valid.append({
                    "start": start,
                    "end": end,
                    "score": float(item.get("score", 90.0)),
                    "title": hook_t,
                    "hook_title": hook_t,
                    "core_topic": str(item.get("core_topic") or ""),
                    "is_ai_selected": True,
                })
        return valid[: (max_clips if count == 0 else count)] or None
    except Exception:
        return None


def ask_gemini(
    transcript: list[dict[str, Any]],
    count: int,
    minimum: int,
    maximum: int,
    max_clips: int,
    profile: str = "auto",
    custom_prompt: str = "",
    flavor: str = "spicy_drama",
    energy_map: list[float] | None = None,
) -> list[dict[str, Any]] | None:
    api_key = get_active_gemini_api_key()
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        condensed = condense_transcript_for_llm(transcript, energy_map, filter_intro=True)
        prompt, eff_min, eff_max = build_clipper_llm_prompt(
            condensed, count, minimum, maximum, max_clips, profile, flavor, custom_prompt
        )
        total_duration = float(transcript[-1]["end"]) if transcript else 0.0
        skip_sec = get_podcast_intro_skip_seconds(total_duration)

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.20,
            ),
        )
        parsed = json.loads(response.text)
        if isinstance(parsed, dict):
            parsed = parsed.get("clips", parsed)
        valid = []
        for item in parsed:
            start = float(item["start"])
            end = float(item["end"])
            duration = end - start
            if end > start and duration >= max(25, eff_min - 15) and duration <= eff_max + 30:
                if start < skip_sec and not is_intro_teaser_highlight(item, skip_sec):
                    continue
                hook_t = str(item.get("hook_title") or item.get("title") or "").strip()
                if is_intro_or_outro_text(hook_t):
                    continue
                valid.append({
                    "start": start,
                    "end": end,
                    "score": float(item.get("score", 92.0)),
                    "title": hook_t,
                    "hook_title": hook_t,
                    "core_topic": str(item.get("core_topic") or ""),
                    "is_ai_selected": True,
                })
        return valid[: (max_clips if count == 0 else count)] or None
    except Exception as e:
        logger.warning(f"Gemini Error: {e}")
        return None


def ask_ollama(
    transcript: list[dict[str, Any]],
    count: int,
    minimum: int,
    maximum: int,
    max_clips: int,
    profile: str = "auto",
    custom_prompt: str = "",
) -> list[dict[str, Any]] | None:
    condensed = condense_transcript_for_llm(transcript, filter_intro=True)
    prompt, eff_min, eff_max = build_clipper_llm_prompt(
        condensed, count, minimum, maximum, max_clips, profile, "spicy_drama", custom_prompt
    )
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}).encode()
    request = urlrequest.Request(
        "[http://127.0.0.1:11434/api/generate](http://127.0.0.1:11434/api/generate)",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
        parsed = json.loads(body.get("response", "[]"))
        if isinstance(parsed, dict):
            parsed = parsed.get("clips", [])
        valid = []
        for item in parsed:
            start = float(item["start"])
            end = float(item["end"])
            duration = end - start
            if end > start and duration >= max(25, eff_min - 15) and duration <= eff_max + 30:
                valid.append({
                    "start": start,
                    "end": end,
                    "score": 90.0,
                    "title": str(item.get("hook_title") or item.get("title") or ""),
                    "is_ai_selected": True,
                })
        return valid[: (max_clips if count == 0 else count)] or None
    except (urlerror.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
        return None


def srt_timestamp(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def format_time_for_error(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"


PROFANITY_WORDS = {
    "anjing", "anjir", "bangsat", "goblog", "goblok", "tolol", "bego",
    "kontol", "memek", "ngentot", "asu", "bajingan", "fuck", "shit", "bitch",
}

TIKTOK_SAFE_WORD_MAP: dict[str, str] = {
    "bunuh diri": "b*nd!r",
    "sakaratul maut": "5akaratul m4ut",
    "gereja setan": "k*munitas keg*lapan",
    "open bo": "0p*n b0",
    "hamil di luar nikah": "h4m!l di lu4r nik4h",
    "penyembelihan": "p*ny*mb*l*h*n",
    "menyembelih": "m*ny*mb*l*h",
    "sembelih": "s*mb*l*h",
    "pembunuhan": "p*mb*n*h*n",
    "membunuh": "m*mb*n*h",
    "dibunuh": "d*b*n*h",
    "terbunuh": "t*rb*n*h",
    "bunuh": "b*n*h",
    "darah": "d4r4h",
    "berdarah": "b*rd4r4h",
    "mutilasi": "m*t!l4s!",
    "siksa": "s!ks4",
    "menyiksa": "m*ny!ks4",
    "disiksa": "d!s!ks4",
    "penyiksaan": "p*ny!ks44n",
    "racun": "r4c*n",
    "senjata": "s*nj4t4",
    "pistol": "p!st*l",
    "tembak": "t*mb4k",
    "menembak": "m*n*mb4k",
    "ditembak": "d!t*mb4k",
    "penembakan": "p*n*mb4k4n",
    "bom": "b*m",
    "teroris": "t*r0r!s",
    "teror": "t*r*r",
    "begal": "b*g4l",
    "rampok": "r4mp*k",
    "sakaratul": "5akaratul",
    "kematian": "k*m4t!an",
    "mati": "m4t!",
    "tewas": "t*w4s",
    "mayat": "m4y4t",
    "jenazah": "j*n4z4h",
    "bangkai": "b4ngk4!",
    "kuburan": "k*b*r4n",
    "makam": "m4k4m",
    "setan": "s3t4n",
    "iblis": "ibl!s",
    "santet": "s4nt*t",
    "pesugihan": "p*sug!h4n",
    "tumbal": "tumb4l",
    "menumbalkan": "m*numb4lk4n",
    "ditumbalkan": "d!tumb4lk4n",
    "ritual": "r!tu4l",
    "sihir": "s!h!r",
    "dukun": "d*k*n",
    "jin": "j!n",
    "hantu": "h4ntu",
    "pocong": "p*c*ng",
    "kuntilanak": "k*nt!l4n4k",
    "perkosa": "p*rk*s4",
    "pemerkosaan": "p*m*rk*s44n",
    "memperkosa": "m*mp*rk*s4",
    "diperkosa": "d!p*rk*s4",
    "pelecehan": "p*l*c*h4n",
    "cabul": "c4b*l",
    "pencabulan": "p*nc4b*l4n",
    "telanjang": "t*l4nj4ng",
    "bugil": "b*g!l",
    "porno": "p*rn*",
    "pornografi": "p*rn*gr4f!",
    "bokep": "b*k*p",
    "seks": "s*ks",
    "seksual": "s*ksu4l",
    "payudara": "p*yud4r4",
    "kelamin": "k*l4m!n",
    "kondom": "k*nd*m",
    "prostitusi": "pr*st!tus!",
    "pelacur": "p*l4c*r",
    "lonte": "l*nt*",
    "zina": "z!n4",
    "narkoba": "n4rk*b4",
    "narkotika": "n4rk*t!k4",
    "sabu": "s4b*",
    "ganja": "g4nj4",
    "ekstasi": "3kst4s!",
    "miras": "m!r4s",
    "kontol": "k*nt*l",
    "memek": "m*m*k",
    "ngentot": "ng*nt*t",
    "bajingan": "b4j!ng4n",
    "bangsat": "b4ngs4t",
    "goblok": "g*bl*k",
    "goblog": "g*bl*k",
    "tolol": "t*l*l",
    "bego": "b*g*",
    "anjing": "4nj!ng",
    "babi": "b4b!",
    "jahanam": "j4h4n4m",
    "kafir": "k4f!r",
}


def is_sensitive_content(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(k in lower for k in TIKTOK_SAFE_WORD_MAP)


def sanitize_for_tiktok_safety(text: str) -> str:
    if not text:
        return ""
    sorted_patterns = sorted(TIKTOK_SAFE_WORD_MAP.keys(), key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted_patterns) + r")\b", re.IGNORECASE)

    def repl(m: re.Match[str]) -> str:
        orig = m.group(0)
        safe = TIKTOK_SAFE_WORD_MAP.get(orig.lower(), orig)
        if orig.isupper():
            return safe.upper()
        if orig.istitle():
            return safe.capitalize()
        return safe

    return pattern.sub(repl, text)


def censor_word_if_enabled(word: str, enabled: bool = False) -> str:
    if not enabled:
        return word
    clean = re.sub(r"[^a-zA-Z]", "", word).lower()
    if clean in TIKTOK_SAFE_WORD_MAP:
        safe = TIKTOK_SAFE_WORD_MAP[clean]
        if word.isupper():
            return safe.upper()
        if word.istitle():
            return safe.capitalize()
        return safe
    if clean in PROFANITY_WORDS and len(word) > 2:
        return word[0] + ("*" * (len(word) - 2)) + word[-1]
    return word


EMOJI_KEYWORD_MAP: dict[str, str] = {
    # Emosi & Marah
    "marah": "😡", "ngamuk": "😡", "emosi": "🤬", "kesal": "😤", "murka": "😡", "benci": "👿",
    # Kaget & Syok
    "kaget": "😱", "syok": "😱", "shock": "😱", "gila": "🤯", "anjir": "😳", "astaga": "😲", "waduh": "😨",
    # Duit & Cuan
    "uang": "💸", "duit": "💸", "cuan": "🤑", "miliaran": "💰", "milyar": "💰", "miliar": "💰", "jutaan": "💵",
    "kaya": "🤑", "rupiah": "💸", "gaji": "💵", "bisnis": "💼", "omset": "📈", "omzet": "📈", "modal": "💳",
    "investasi": "📈", "saham": "📊", "crypto": "🪙", "kripto": "🪙", "untung": "📈", "rugi": "📉",
    # Bohong & Drama
    "bohong": "🤥", "hoax": "🚫", "dusta": "🤥", "tipu": "⚠️", "penipuan": "🚨", "drama": "🎭", "aib": "🫣",
    # Sedih & Menangis
    "nangis": "😭", "menangis": "😭", "sedih": "😢", "hancur": "💔", "drop": "😞", "kecewa": "🥺",
    "trauma": "🥀", "sakit": "🤕", "parah": "💥", "nyesel": "😔", "menyesal": "😔",
    # Lucu & Komedi
    "lucu": "🤣", "ngakak": "🤣", "ketawa": "😂", "kocak": "🤣", "lawak": "😂", "blunder": "🤡",
    # Percintaan & Pasangan
    "cinta": "❤️", "sayang": "🥰", "pacar": "💑", "istri": "💍", "suami": "💍", "nikah": "💒",
    "jodoh": "💖", "selingkuh": "💔", "putus": "💔",
    # Rahasia & Fakta
    "rahasia": "🤫", "fakta": "🔍", "misteri": "🕵️", "sebenarnya": "💡", "sebenernya": "💡",
    "terbongkar": "💥", "bocoran": "🔓", "isu": "👀",
    # Hype & Viral
    "viral": "🔥", "meledak": "💥", "hebat": "👏", "keren": "😎", "juara": "🏆", "top": "⭐",
    "gokil": "🔥", "mantap": "👍", "bahaya": "⚠️", "ancaman": "🚨",
    # Hukum & Kasus
    "polisi": "👮", "jaksa": "⚖️", "pengadilan": "⚖️", "hukum": "⚖️", "penjara": "⛓️",
    "kasus": "📁", "ditangkap": "🚨",
}


def map_word_to_emoji(word: str) -> str:
    """Mengembalikan emoji ekspresif jika kata mengandung kata kunci viral/emosi."""
    clean = re.sub(r"[^a-zA-Z0-9]", "", word).lower()
    return EMOJI_KEYWORD_MAP.get(clean, "")


def decorate_word_with_emoji(word: str, enabled: bool = True) -> str:
    if not enabled:
        return word
    emo = map_word_to_emoji(word)
    return f"{word} {emo}" if emo else word


def hex_to_ass_bgr(hex_color: str, default: str = "&H0000DDFF") -> str:
    clean = (hex_color or "").strip().lstrip("#")
    if len(clean) == 6 and all(c in "0123456789ABCDEFabcdef" for c in clean):
        return f"&H00{clean[4:6].upper()}{clean[2:4].upper()}{clean[0:2].upper()}"
    return default


CONTEXT_COLOR_CATEGORIES: dict[str, dict[str, Any]] = {
    "danger_conflict": {
        "hex": "#FF4D4D",       # Merah Terang: Konflik, Bahaya, Marah, Larangan, Drama
        "ass": "&H004D4DFF",
        "words": {
            "marah", "benci", "bohong", "fitnah", "parah", "bahaya", "jangan", "dilarang",
            "salah", "gagal", "hancur", "bangkrut", "rugi", "curang", "ribut", "debat",
            "musuh", "takut", "ngeri", "ancam", "ancaman", "pecat", "dipecat", "putus",
            "selingkuh", "dosa", "haram", "korban", "pelaku", "kasus", "penjara", "polisi",
            "hukum", "mati", "tewas", "darah", "bunuh", "sakit", "krisis", "hutang",
            "utang", "masalah", "ancur", "rusak", "nyesel", "menyesal", "kapok", "muak",
            "egois", "munafik", "jahat", "kejam", "bodoh", "tolol", "gila", "stres",
            "depresi", "trauma", "konflik", "perang", "serang", "lawan", "tolak", "batal",
        },
    },
    "money_success": {
        "hex": "#00F57A",       # Hijau Neon: Uang, Angka, Cuan, Sukses, Positif, Solusi
        "ass": "&H007AF500",
        "words": {
            "uang", "duit", "cuan", "juta", "miliar", "triliun", "ribu", "rupiah", "dollar",
            "dolar", "gaji", "income", "omset", "omzet", "profit", "untung", "kaya",
            "sukses", "berhasil", "menang", "juara", "gratis", "bonus", "diskon", "murah",
            "mahal", "harga", "bayar", "beli", "jual", "investasi", "saham", "crypto",
            "bisnis", "usaha", "kerja", "karir", "naik", "tumbuh", "solusi", "aman",
            "benar", "setuju", "bagus", "hebat", "terbaik", "sempurna", "berkah", "halal",
            "lulus", "paham", "erti", "mudah", "gampang", "cepat", "efektif", "hasil",
        },
    },
    "question_curiosity": {
        "hex": "#00E5FF",       # Cyan Elektrik: Pertanyaan, Penasaran, Analisis
        "ass": "&H00FFE500",
        "words": {
            "kenapa", "mengapa", "gimana", "bagaimana", "apa", "apakah", "siapa", "kapan",
            "berapa", "dimana", "kemana", "darimana", "kok", "masa", "benarkah", "serius",
            "penasaran", "bingung", "kira", "alasan", "maksud", "maksudnya", "arti",
            "artinya", "caranya", "solusinya", "bedanya", "contoh", "misalnya", "seandainya",
            "kalau", "jika", "andainya", "tanya", "pertanyaan", "menurut", "pendapat",
        },
    },
    "fact_emphasis": {
        "hex": "#FFDD00",       # Kuning Emas: Fakta, Rahasia, Penekanan Penting, Hook
        "ass": "&H0000DDFF",
        "words": {
            "rahasia", "fakta", "bukti", "nyata", "ternyata", "jujur", "asli", "penting",
            "kunci", "inti", "intinya", "syarat", "wajib", "harus", "pasti", "mutlak",
            "pertama", "kedua", "ketiga", "terakhir", "paling", "utama", "khusus", "spesial",
            "ingat", "catat", "perhatikan", "lihat", "dengar", "padahal", "sebenarnya",
            "akhirnya", "kesimpulan", "prinsip", "aturan", "rumus", "strategi", "teknik",
            "cara", "tips", "trik", "ilmu", "pelajaran", "pengalaman", "sejarah",
        },
    },
    "comedy_emotion": {
        "hex": "#FF66CC",       # Pink/Magenta Viral: Komedi, Kejutan, Ekspresi Spontan
        "ass": "&H00CC66FF",
        "words": {
            "haha", "wkwk", "hehe", "lucu", "ngakak", "kocak", "ketawa", "tertawa",
            "komedi", "becanda", "bercanda", "lelucon", "kaget", "kejut", "terkejut",
            "astaga", "waduh", "anjir", "buset", "gokil", "keren", "mantap", "asik",
            "seru", "senang", "bahagia", "bangga", "cinta", "sayang", "rindu", "kangen",
            "nikah", "jodoh", "pacar", "cantik", "ganteng", "indah", "ajaib", "unik",
        },
    },
    "action_power": {
        "hex": "#FF9900",       # Oranye Energi: Aksi Cepat, Perintah, Perubahan
        "ass": "&H000099FF",
        "words": {
            "mulai", "berhenti", "stop", "lari", "jalan", "ambil", "buang", "ganti",
            "ubah", "berubah", "pindah", "bangun", "bikin", "buat", "hajar", "sikat",
            "gas", "lanjut", "berani", "fokus", "disiplin", "latihan", "coba", "praktek",
            "kirim", "buka", "tutup", "cari", "temukan", "capai", "kejar", "dorong",
        },
    },
}


def detect_sentence_mood_color(sentence: str, default_hex: str = "#FFDD00") -> tuple[str, str]:
    clean_s = sentence.strip()
    lower_tokens = set(re.findall(r"[a-zA-Z0-9]+", clean_s.lower()))

    if "?" in clean_s or any(t in CONTEXT_COLOR_CATEGORIES["question_curiosity"]["words"] for t in list(lower_tokens)[:3]):
        cat = CONTEXT_COLOR_CATEGORIES["question_curiosity"]
        return cat["hex"], cat["ass"]
    if any(t in CONTEXT_COLOR_CATEGORIES["danger_conflict"]["words"] for t in lower_tokens):
        cat = CONTEXT_COLOR_CATEGORIES["danger_conflict"]
        return cat["hex"], cat["ass"]
    if any(t in CONTEXT_COLOR_CATEGORIES["money_success"]["words"] for t in lower_tokens):
        cat = CONTEXT_COLOR_CATEGORIES["money_success"]
        return cat["hex"], cat["ass"]
    if any(t in CONTEXT_COLOR_CATEGORIES["comedy_emotion"]["words"] for t in lower_tokens):
        cat = CONTEXT_COLOR_CATEGORIES["comedy_emotion"]
        return cat["hex"], cat["ass"]

    fallback_hex = "#FFDD00" if default_hex == "auto_context" else default_hex
    return fallback_hex, hex_to_ass_bgr(fallback_hex, "&H0000DDFF")


def detect_word_context_color(
    word: str,
    sentence_context: str = "",
    active_color_setting: str = "auto_context",
) -> tuple[str, str, bool]:
    raw = word.strip()
    clean = re.sub(r"[^a-zA-Z0-9%$]", "", raw).lower()

    if any(ch.isdigit() for ch in clean) or "%" in raw or "$" in raw or clean.startswith("rp"):
        cat = CONTEXT_COLOR_CATEGORIES["money_success"]
        return cat["hex"], cat["ass"], True

    if "?" in raw:
        cat = CONTEXT_COLOR_CATEGORIES["question_curiosity"]
        return cat["hex"], cat["ass"], True

    for cat_key in ("danger_conflict", "money_success", "question_curiosity", "comedy_emotion", "fact_emphasis", "action_power"):
        cat = CONTEXT_COLOR_CATEGORIES[cat_key]
        word_set = cat["words"]
        if clean in word_set:
            return cat["hex"], cat["ass"], True
        prefixes = ("me", "mem", "men", "meng", "di", "ter", "ber", "se", "ke", "pe", "per")
        suffixes = ("nya", "kan", "an", "lah", "kah", "in", "i")
        for prefix in prefixes:
            if clean.startswith(prefix) and len(clean) > len(prefix) + 2:
                stem_candidate = clean[len(prefix):]
                if stem_candidate in word_set:
                    return cat["hex"], cat["ass"], True
                for suffix in suffixes:
                    if stem_candidate.endswith(suffix) and len(stem_candidate) > len(suffix) + 2:
                        base = stem_candidate[:-len(suffix)]
                        if base in word_set:
                            return cat["hex"], cat["ass"], True
        for suffix in suffixes:
            if clean.endswith(suffix) and len(clean) > len(suffix) + 2 and clean[:-len(suffix)] in word_set:
                return cat["hex"], cat["ass"], True

    if "!" in raw:
        cat = CONTEXT_COLOR_CATEGORIES["action_power"]
        return cat["hex"], cat["ass"], True

    if active_color_setting == "auto_context" and sentence_context:
        mood_hex, mood_ass = detect_sentence_mood_color(sentence_context, "#FFDD00")
        return mood_hex, mood_ass, False

    base_hex = "#FFDD00" if active_color_setting == "auto_context" else active_color_setting
    return base_hex, hex_to_ass_bgr(base_hex, "&H0000DDFF"), False


def build_thumbnail_hook_headline(raw_title: str, custom_text: str = "") -> str:
    """
    Meracik teks pancingan (Thumbnail Hook) dari judul klip agar padat, memicu penasaran,
    dan siap ditampilkan di 1 detik pertama.
    """
    source = (custom_text or raw_title or "MOMEN PALING KRUSIAL").strip()
    source = sanitize_for_tiktok_safety(source)
    source = re.sub(r"^(part\s*\d+|clip\s*\d+|highlight\s*\d+)\s*[:\-·]?\s*", "", source, flags=re.IGNORECASE).strip()
    words_list = source.split()
    if len(words_list) > 9:
        words_list = words_list[:9]
    headline = " ".join(words_list).upper()
    if headline and not headline.endswith(("!", "?", "...")):
        lower_h = headline.lower()
        if any(q in lower_h for q in ("kenapa", "mengapa", "gimana", "bagaimana", "apa", "siapa", "benarkah", "kok")):
            headline += "?!"
        else:
            headline += "!"
    return headline


def write_srt(
    transcript: list[dict[str, Any]],
    start: float,
    end: float,
    path: Path,
    max_lines: int = 2,
    mode: str = "phrase",
    highlight_color: str = "#FFDD00",
    censor_profanity: bool = False,
    emoji_subtitles: bool = True,
) -> None:
    lines: list[str] = []
    index = 1
    clip_dur = max(0.1, end - start)

    for item in transcript:
        seg_abs_start = float(item.get("start", 0.0))
        seg_abs_end = float(item.get("end", 0.0))
        if seg_abs_end <= start + 0.08 or seg_abs_start >= end:
            continue

        item_start = max(0.0, seg_abs_start - start)
        item_end = min(clip_dur, seg_abs_end - start)
        if item_end <= item_start:
            continue

        item_text = normalize_indonesian_transcript_text(str(item.get("text", "")).strip())
        if not item_text:
            continue

        if censor_profanity:
            item_text = " ".join(censor_word_if_enabled(tok, True) for tok in item_text.split())

        raw_words = item.get("words")
        norm_words: list[dict[str, Any]] = []
        if raw_words:
            for w in raw_words:
                w_txt = str(getattr(w, "word", "") if hasattr(w, "word") else w.get("word", "")).strip()
                if not w_txt:
                    continue
                w_txt = normalize_indonesian_transcript_text(w_txt)
                w_abs_s = float(getattr(w, "start", seg_abs_start) if hasattr(w, "start") else w.get("start", seg_abs_start))
                w_abs_e = float(getattr(w, "end", seg_abs_end) if hasattr(w, "end") else w.get("end", seg_abs_end))
                if w_abs_e <= start + 0.05 or w_abs_s >= end:
                    continue
                w_txt = censor_word_if_enabled(w_txt, censor_profanity)
                rel_s = max(0.0, min(clip_dur, w_abs_s - start))
                rel_e = max(rel_s + 0.08, min(clip_dur, w_abs_e - start))
                if rel_e > rel_s and rel_s < clip_dur:
                    norm_words.append({"word": w_txt, "start": round(rel_s, 3), "end": round(rel_e, 3)})

        if not norm_words:
            w_list = item_text.split()
            if w_list:
                tot_dur = max(0.2, item_end - item_start)
                per_w = tot_dur / len(w_list)
                norm_words = [
                    {
                        "word": w,
                        "start": round(item_start + i * per_w, 3),
                        "end": round(item_start + (i + 1) * per_w, 3),
                    }
                    for i, w in enumerate(w_list)
                ]

        if mode == "single_word":
            for i, nw in enumerate(norm_words):
                ws = nw["start"]
                we = nw["end"]
                if i + 1 < len(norm_words):
                    nxt_s = norm_words[i + 1]["start"]
                    if 0 <= (nxt_s - we) < 0.12:
                        we = nxt_s
                    elif we > nxt_s:
                        we = max(ws + 0.06, nxt_s)
                if we > ws:
                    word_label = nw["word"].upper()
                    if emoji_subtitles:
                        word_label = decorate_word_with_emoji(word_label, enabled=True)
                    w_hex, _, _ = detect_word_context_color(nw["word"], item_text, highlight_color)
                    lines.extend([str(index), f"{srt_timestamp(ws)} --> {srt_timestamp(we)}", f'<font color="{w_hex}">{word_label}</font>', ""])
                    index += 1

        elif mode == "active_highlight":
            chunk_size = 4 if max_lines != 1 else 3
            for chunk_idx in range(0, len(norm_words), chunk_size):
                chunk = norm_words[chunk_idx : chunk_idx + chunk_size]
                chunk_words = [w["word"] for w in chunk if w.get("word")]
                if not chunk_words:
                    continue

                chunk_sentence = " ".join(chunk_words)
                for active_i, nw in enumerate(chunk):
                    ws = nw["start"]
                    if active_i + 1 < len(chunk):
                        nxt_s = chunk[active_i + 1]["start"]
                        we = nxt_s if (nxt_s - nw["end"]) < 0.45 else nw["end"]
                    else:
                        we = nw["end"]
                        if chunk_idx + chunk_size < len(norm_words):
                            next_chunk_s = norm_words[chunk_idx + chunk_size]["start"]
                            if we > next_chunk_s:
                                we = max(ws + 0.06, next_chunk_s)
                    if we <= ws:
                        continue

                    formatted_tokens = []
                    for i, cw in enumerate(chunk_words):
                        disp_w = decorate_word_with_emoji(cw, enabled=True) if emoji_subtitles else cw
                        w_hex, _, is_kw = detect_word_context_color(cw, chunk_sentence, highlight_color)
                        if i == active_i:
                            act_hex = "#FFDD00" if highlight_color in ("#FFDD00", "auto_context") else highlight_color
                            if highlight_color == "auto_context":
                                act_hex = w_hex
                            formatted_tokens.append(f'<b><font color="{act_hex}">{disp_w}</font></b>')
                        else:
                            formatted_tokens.append(disp_w)

                    if max_lines >= 2 and len(formatted_tokens) >= 4:
                        mid = len(formatted_tokens) // 2
                        cue_text = " ".join(formatted_tokens[:mid]) + "\n" + " ".join(formatted_tokens[mid:])
                    else:
                        cue_text = " ".join(formatted_tokens)

                    lines.extend([
                        str(index),
                        f"{srt_timestamp(ws)} --> {srt_timestamp(we)}",
                        cue_text,
                        "",
                    ])
                    index += 1
        else:
            cues = split_segment_into_cues(item_start, item_end, item_text, max_lines=max_lines)
            for c_start, c_end, c_text in cues:
                if c_end <= c_start:
                    continue
                disp_c = " ".join(decorate_word_with_emoji(tok, enabled=True) for tok in c_text.split()) if emoji_subtitles else c_text
                lines.extend([str(index), f"{srt_timestamp(c_start)} --> {srt_timestamp(c_end)}", disp_c, ""])
                index += 1

    path.write_text("\n".join(lines), encoding="utf-8")


SUBTITLE_STYLES = {
    "classic": "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=1.8,Shadow=1,Alignment=2,MarginV=50",
    "bold": "FontName=Arial Black,FontSize=15,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2.2,Shadow=1,Alignment=2,MarginV=55",
    "highlight": "FontName=Arial Black,FontSize=15,PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2.2,Shadow=1,Alignment=2,MarginV=55",
    "minimal": "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=3,Outline=0,Shadow=0,Alignment=2,MarginV=50",
    "neon": "FontName=Arial Black,FontSize=15,PrimaryColour=&H00FFFF00,OutlineColour=&H00302010,BorderStyle=1,Outline=2.0,Shadow=1,Alignment=2,MarginV=55",
    "karaoke": "FontName=Arial Black,FontSize=15,PrimaryColour=&H00FF66FF,OutlineColour=&H00200030,BorderStyle=1,Outline=2.2,Shadow=1,Alignment=2,MarginV=55",
    "box": "FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=3,Outline=0,Shadow=0,Alignment=2,MarginV=50",
}


def output_dimensions(aspect_ratio: str, quality: str = "1080") -> tuple[int, int]:
    q_str = str(quality).lower()
    if q_str in ("720", "720p"):
        if aspect_ratio == "16:9":
            return 1280, 720
        if aspect_ratio == "4:3":
            return 960, 720
        if aspect_ratio == "1:1":
            return 720, 720
        return 720, 1280

    if aspect_ratio == "16:9":
        return 1920, 1080
    if aspect_ratio == "4:3":
        return 1440, 1080
    if aspect_ratio == "1:1":
        return 1080, 1080
    return 1080, 1920


def subtitle_style_with_position(
    style: str,
    position: str,
    color: str = "auto",
    subtitle_x: float = 0.15,
    subtitle_y: float = 0.78,
    aspect_ratio: str = "9:16",
    font_size: int | None = None,
) -> str:
    alignment, margin = {
        "auto": ("2", "50"),
        "bottom": ("2", "50"),
        "center": ("5", "0"),
        "top": ("8", "50"),
    }.get(position, ("2", "50"))
    base = SUBTITLE_STYLES[style]
    if font_size and font_size > 0:
        base = re.sub(r"FontSize=\d+", f"FontSize={font_size}", base)
    default_colors = {
        "classic": "white",
        "bold": "white",
        "highlight": "yellow",
        "minimal": "white",
        "neon": "cyan",
        "karaoke": "pink",
        "box": "white",
    }
    ass_colors = {
        "white": "&H00FFFFFF",
        "yellow": "&H0000FFFF",
        "cyan": "&H00FFFF00",
        "red": "&H000000FF",
        "green": "&H0000FF00",
        "pink": "&H00FF66FF",
    }
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", color or ""):
        rgb = color[1:].upper()
        selected_color = f"&H00{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}"
    else:
        selected_color = ass_colors.get(color, ass_colors[default_colors.get(style, "white")])
    base = re.sub(r"PrimaryColour=&H[0-9A-Fa-f]+", f"PrimaryColour={selected_color}", base)
    if position == "free":
        width, height = output_dimensions(aspect_ratio)
        margin_left = max(0, min(width - 1, int(width * subtitle_x)))
        margin_top = max(0, min(height - 1, int(height * subtitle_y)))
        base = re.sub(r"Alignment=\d+", "Alignment=7", base)
        base = re.sub(r"MarginV=\d+", f"MarginV={margin_top}", base)
        return f"{base},MarginL={margin_left}"
    return re.sub(r"Alignment=\d+", f"Alignment={alignment}", re.sub(r"MarginV=\d+", f"MarginV={margin}", base))


# ==============================================================================
# SAFE OPENCV & YUNET DETECTOR (WITH ANTI-FALSE-POSITIVE RADIO/MIC FILTER)
# ==============================================================================
_CASCADE_CACHE: dict[str, Any] = {}
_CASCADE_URLS = {
    "haarcascade_frontalface_default.xml": "[https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_frontalface_default.xml](https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_frontalface_default.xml)",
    "haarcascade_frontalface_alt2.xml": "[https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_frontalface_alt2.xml](https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_frontalface_alt2.xml)",
    "haarcascade_profileface.xml": "[https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_profileface.xml](https://raw.githubusercontent.com/opencv/opencv/4.x/data/haarcascades/haarcascade_profileface.xml)",
}


def load_safe_cascade(xml_name: str = "haarcascade_frontalface_default.xml") -> Any | None:
    try:
        import cv2
    except ImportError:
        return None

    if xml_name in _CASCADE_CACHE:
        cached = _CASCADE_CACHE[xml_name]
        if cached is not None and not cached.empty():
            return cached

    candidate_paths: list[Path] = []
    for base_d in (MODEL_DIR, ROOT / "models", BUNDLE_DIR / "models", BUNDLE_DIR):
        try:
            candidate_paths.append(base_d / "haarcascades" / xml_name)
        except Exception:
            pass
    try:
        if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            candidate_paths.append(Path(cv2.data.haarcascades) / xml_name)
    except Exception:
        pass

    local_xml = MODEL_DIR / "haarcascades" / xml_name
    for cand in candidate_paths:
        if cand.is_file() and cand.stat().st_size > 10_000:
            if cand != local_xml and not local_xml.is_file():
                try:
                    local_xml.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cand, local_xml)
                except Exception:
                    pass
            clf = cv2.CascadeClassifier(str(local_xml if local_xml.is_file() else cand))
            if clf is not None and not clf.empty():
                _CASCADE_CACHE[xml_name] = clf
                return clf

    url = _CASCADE_URLS.get(xml_name)
    if url:
        try:
            req = urlrequest.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlrequest.urlopen(req, timeout=12) as resp:
                xml_bytes = resp.read()
            if len(xml_bytes) > 10_000:
                local_xml.parent.mkdir(parents=True, exist_ok=True)
                local_xml.write_bytes(xml_bytes)
                clf = cv2.CascadeClassifier(str(local_xml))
                if clf is not None and not clf.empty():
                    _CASCADE_CACHE[xml_name] = clf
                    return clf
        except Exception as exc:
            logger.warning(f"Gagal mengunduh {xml_name}: {exc}")

    return None


_YUNET_DETECTOR: Any = None
_YUNET_FAILED: bool = False


def load_safe_yunet(input_w: int = 640, input_h: int = 360) -> Any | None:
    global _YUNET_DETECTOR, _YUNET_FAILED
    if _YUNET_FAILED:
        return None
    try:
        import cv2
        if not hasattr(cv2, "FaceDetectorYN"):
            return None

        project_root = Path(__file__).resolve().parent.parent
        candidates = [
            MODEL_DIR / "yunet.onnx",
            ROOT / "models" / "yunet.onnx",
            project_root / "Core_Data" / "models" / "yunet.onnx",
            project_root / "models" / "yunet.onnx",
        ]
        local_model = candidates[0]
        for c in candidates:
            if c.is_file() and c.stat().st_size > 100_000:
                local_model = c
                break

        if not local_model.is_file() or local_model.stat().st_size < 100_000:
            url = "[https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx](https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx)"
            try:
                local_model.parent.mkdir(parents=True, exist_ok=True)
                req = urlrequest.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urlrequest.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                if len(data) > 100_000:
                    local_model.write_bytes(data)
            except Exception as e:
                logger.warning(f"Gagal mengunduh model YuNet ONNX: {e}")
                _YUNET_FAILED = True
                return None

        if not local_model.is_file() or local_model.stat().st_size < 100_000:
            return None

        if _YUNET_DETECTOR is None:
            _YUNET_DETECTOR = cv2.FaceDetectorYN.create(
                model=str(local_model),
                config="",
                input_size=(input_w, input_h),
                score_threshold=0.58,
                nms_threshold=0.3,
                top_k=8,
            )
        else:
            _YUNET_DETECTOR.setInputSize((input_w, input_h))
        return _YUNET_DETECTOR
    except Exception as exc:
        logger.warning(f"Inisialisasi YuNet gagal ({exc}).")
        _YUNET_FAILED = True
        return None


def _deduplicate_faces(
    faces: list[tuple[int, int, int, int]], iou_threshold: float = 0.30
) -> list[tuple[int, int, int, int]]:
    if not faces:
        return []
    boxes = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
    kept: list[tuple[int, int, int, int]] = []
    for bx, by, bw, bh in boxes:
        overlap = False
        for kx, ky, kw, kh in kept:
            ix1, iy1 = max(bx, kx), max(by, ky)
            ix2, iy2 = min(bx + bw, kx + kw), min(by + bh, ky + kh)
            iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
            inter = iw * ih
            union = (bw * bh) + (kw * kh) - inter
            if union > 0 and (inter / union) > iou_threshold:
                overlap = True
                break
            cx1, cy1 = bx + bw / 2.0, by + bh / 2.0
            cx2, cy2 = kx + kw / 2.0, ky + kh / 2.0
            if abs(cx1 - cx2) < max(bw, kw) * 0.65 and abs(cy1 - cy2) < max(bh, kh) * 0.65:
                overlap = True
                break
        if not overlap:
            kept.append((bx, by, bw, bh))
    kept.sort(key=lambda b: b[0] + b[2] / 2.0)
    return kept


def detect_faces_robust(
    frame: Any,
    min_size: int = 36,
    score_thresh: float = 0.60,
) -> list[tuple[int, int, int, int]]:
    """
    Deteksi wajah dengan YuNet Deep Learning (score >= 0.60).
    JANGAN pernah menjalankan Haar Cascade jika YuNet sudah aktif karena Haar Cascade
    sering salah mendeteksi speaker radio/mikrofon bulat di meja sebagai wajah ke-2.
    """
    if frame is None:
        return []
    h, w = frame.shape[:2]
    eff_thresh = max(0.58, float(score_thresh))
    detected: list[tuple[int, int, int, int]] = []

    try:
        yn = load_safe_yunet(input_w=w, input_h=h)
        if yn is not None:
            import cv2

            bgr = frame if (len(frame.shape) == 3 and frame.shape[2] == 3) else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            _, raw_faces = yn.detect(bgr)
            if raw_faces is not None and len(raw_faces) > 0:
                for f in raw_faces:
                    fx, fy, fw, fh, conf = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[14])
                    if conf < eff_thresh or fw < min_size or fh < min_size:
                        continue
                    aspect = fw / max(1.0, fh)
                    if not (0.65 <= aspect <= 1.45):
                        continue
                    cy = fy + fh / 2.0
                    # Wajah pembicara podcast selalu di area atas/tengah (bukan meja bawah tempat radio/mic)
                    if cy < h * 0.08 or cy > h * 0.56:
                        continue
                    detected.append((int(fx), int(fy), int(fw), int(fh)))
            return _deduplicate_faces(detected)
    except Exception:
        pass

    # Fallback Haar Cascade HANYA jika YuNet gagal dimuat sama sekali
    try:
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if (len(frame.shape) == 3 and frame.shape[2] == 3) else frame
        gray = cv2.equalizeHist(gray)
        frontal = load_safe_cascade("haarcascade_frontalface_default.xml")
        if frontal is not None and not frontal.empty():
            f1 = frontal.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(min_size, min_size))
            for x, y, bw, bh in f1:
                cy = y + bh / 2.0
                if h * 0.08 <= cy <= h * 0.54:
                    detected.append((int(x), int(y), int(bw), int(bh)))
    except Exception:
        pass

    return _deduplicate_faces(detected)


def safe_detect_faces_in_gray(
    gray_img: Any,
    min_size: int = 36,
    check_profile: bool = True,
) -> list[tuple[int, int, int, int]]:
    return detect_faces_robust(gray_img, min_size=min_size, score_thresh=0.60)


def filter_distinct_podcast_faces(
    faces: list[tuple[int, int, int, int]],
    frame_w: int,
    frame_h: int,
    min_dist_ratio: float = 0.10,
) -> list[tuple[int, int, int, int]]:
    """
    Menyaring deteksi wajah untuk memastikan:
    - Hanya manusia di level kursi/sofa podcast (cy <= 0.56 * frame_h).
    - Konsistensi ukuran wajah & sejajar level mata (menolak objek kecil/radio di meja).
    - Mendukung hingga 4 orang di studio.
    """
    if not faces:
        return []

    candidates: list[tuple[int, int, int, int]] = []
    min_sz = max(32, int(min(frame_w, frame_h) * 0.04))
    for fx, fy, fw, fh in faces:
        if fw < min_sz or fh < min_sz:
            continue
        if fw > frame_w * 0.72 or fh > frame_h * 0.72:
            continue
        cy = fy + fh / 2.0
        if cy < frame_h * 0.08 or cy > frame_h * 0.56:
            continue
        candidates.append((fx, fy, fw, fh))

    if not candidates:
        return []

    candidates.sort(key=lambda b: b[2] * b[3], reverse=True)
    main_face = candidates[0]
    max_area = float(main_face[2] * main_face[3])
    max_fh = float(main_face[3])
    main_cy = main_face[1] + main_face[3] / 2.0

    kept: list[tuple[int, int, int, int]] = []
    min_x_dist = int(frame_w * min_dist_ratio)

    for bx, by, bw, bh in candidates:
        bcx = bx + bw / 2.0
        bcy = by + bh / 2.0

        # Validasi konsistensi ukuran & kesetaraan tinggi mata terhadap wajah utama
        if (bw * bh) < max_area * 0.38 or bh < max_fh * 0.58:
            continue
        if abs(bcy - main_cy) > frame_h * 0.20:
            continue

        duplicate = False
        for kx, ky, kw, kh in kept:
            kcx = kx + kw / 2.0
            ix1, iy1 = max(bx, kx), max(by, ky)
            ix2, iy2 = min(bx + bw, kx + kw), min(by + bh, ky + kh)
            iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
            inter = iw * ih
            union = (bw * bh) + (kw * kh) - inter
            if union > 0 and (inter / union) > 0.25:
                duplicate = True
                break
            if abs(bcx - kcx) < min_x_dist:
                duplicate = True
                break

        if not duplicate:
            kept.append((bx, by, bw, bh))
            if len(kept) >= 4:
                break

    kept.sort(key=lambda b: b[0] + b[2] / 2.0)
    return kept


def detect_face_crop(
    video_path: Path,
    start_sec: float = 0.0,
    end_sec: float = 0.0,
) -> tuple[int, int, int, int] | None:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Mode Facecam di atas membutuhkan paket opencv-python.") from exc

    capture = cv2.VideoCapture(str(video_path))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if width <= 0 or height <= 0:
        capture.release()
        return None

    start_f = max(0, int(start_sec * fps)) if start_sec > 0 else 0
    end_f = min(max(0, frame_count - 1), int(end_sec * fps)) if end_sec > start_sec else max(0, frame_count - 1)
    span = max(1, end_f - start_f)
    sample_points = [start_f + int(span * r) for r in (0.1, 0.3, 0.5, 0.7, 0.9)]

    candidates: list[tuple[float, int, int, int, int]] = []
    for frame_index in sample_points:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        faces = detect_faces_robust(frame, min_size=32, score_thresh=0.58)
        for fx, fy, fw, fh in faces:
            if fh > height * 0.48:
                continue
            cx = fx + fw / 2.0
            edge_dist_x = min(cx / width, (width - cx) / width)
            corner_bonus = 2.0 if edge_dist_x < 0.32 else 0.75
            score = float(fw * fh) * corner_bonus
            candidates.append((score, int(fx), int(fy), int(fw), int(fh)))
    capture.release()

    if not candidates:
        def_w = int(width * 0.30)
        def_h = int(def_w * 9 / 16)
        return (int(width * 0.015), int(height * 0.02), def_w, def_h)

    candidates.sort(key=lambda item: item[0], reverse=True)
    _, face_x, face_y, face_w, face_h = candidates[0]
    crop_w = min(width, max(int(face_w * 3.4), int(width * 0.26)))
    crop_h = min(height, max(int(face_h * 2.8), int(crop_w * 9 / 16)))
    center_x = face_x + face_w // 2
    center_y = face_y + int(face_h * 0.55)
    crop_x = max(0, min(width - crop_w, center_x - crop_w // 2))
    crop_y = max(0, min(height - crop_h, center_y - crop_h // 2))
    return crop_x, crop_y, crop_w, crop_h


def _make_even(val: int, minimum: int = 2) -> int:
    v = max(minimum, int(val))
    return v - (v % 2)


def _crop_around_face(
    cx: float,
    cy: float,
    fw: float,
    fh: float,
    vw: int,
    vh: int,
    panel_w: int,
    panel_h: int,
    min_x: int = 0,
    max_x: int | None = None,
) -> tuple[int, int, int, int]:
    """
    Center-Locked Cropping: Selalu mengunci titik tengah horizontal tepat pada cx
    dan hanya membatasi pada tepi frame video (0 s/d vw - crop_w) agar wajah tidak pernah
    terdorong ke pinggir kanan/kiri layar.
    """
    panel_ar = float(panel_w) / float(max(1, panel_h))

    # 1 Wajah / Format 9:16 Portrait Penuh (panel_ar < 0.75)
    if panel_ar < 0.75:
        crop_h = _make_even(vh, 64)
        crop_w = _make_even(min(vw, int(round(crop_h * panel_ar))), 64)
        x = int(round(cx - crop_w / 2.0))
        x = max(0, min(vw - crop_w, x))
        return x, 0, crop_w, crop_h

    # Split Panel (2 Panel atau 3 Panel)
    if panel_ar >= 1.4:
        desired_h = max(int(fh * 2.6), int(vh * 0.36))
    else:
        desired_h = max(int(fh * 3.0), int(vh * 0.46))

    crop_h = min(vh, desired_h)
    crop_w = int(round(crop_h * panel_ar))
    if crop_w > vw:
        crop_w = vw
        crop_h = min(vh, int(round(crop_w / max(0.1, panel_ar))))

    crop_w = _make_even(min(vw, crop_w), 64)
    crop_h = _make_even(min(vh, crop_h), 64)

    x = int(round(cx - crop_w / 2.0))
    x = max(0, min(vw - crop_w, x))

    headroom_ratio = 0.40 if panel_ar >= 1.4 else 0.38
    y = int(round(cy - crop_h * headroom_ratio))
    y = max(0, min(vh - crop_h, y))
    return x, y, crop_w, crop_h


def _crop_around_group(
    boxes: list[tuple[int, int, int, int]],
    vw: int,
    vh: int,
    panel_w: int,
    panel_h: int,
) -> tuple[int, int, int, int]:
    """Menghitung kotak crop gabungan untuk 2 orang yang duduk berdekatan."""
    if not boxes:
        return 0, 0, _make_even(panel_w, 64), _make_even(panel_h, 64)

    min_x = min(b[0] for b in boxes)
    max_x = max(b[0] + b[2] for b in boxes)
    min_y = min(b[1] for b in boxes)
    max_y = max(b[1] + b[3] for b in boxes)

    group_w = max(32, max_x - min_x)
    group_h = max(32, max_y - min_y)
    group_cx = (min_x + max_x) / 2.0
    group_cy = (min_y + max_y) / 2.0

    panel_ar = float(panel_w) / float(max(1, panel_h))
    desired_w = group_w * 1.65
    desired_h_from_w = desired_w / panel_ar
    desired_h_from_face = max(group_h * 2.9, vh * 0.45)

    crop_h = min(float(vh), max(desired_h_from_w, desired_h_from_face))
    crop_w = crop_h * panel_ar
    if crop_w > vw:
        crop_w = float(vw)
        crop_h = min(float(vh), crop_w / panel_ar)

    int_crop_w = _make_even(min(vw, int(round(crop_w))), 64)
    int_crop_h = _make_even(min(vh, int(round(crop_h))), 64)

    x = max(0, min(vw - int_crop_w, int(round(group_cx - int_crop_w / 2.0))))
    y = max(0, min(vh - int_crop_h, int(round(group_cy - int_crop_h * 0.38))))
    return x, y, int_crop_w, int_crop_h


# ==============================================================================
# 100% PURE GEMINI VISION AI CAMERA-DIRECTOR & SCENE CUT DETECTOR
# ==============================================================================
def extract_camera_shots(
    video_path: Path,
    start_sec: float,
    end_sec: float,
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Mendeteksi perpindahan angle kamera (camera cuts) di sepanjang klip dan mengambil
    1 frame tengah (mid_frame) yang representatif dari setiap shot kamera.
    """
    import cv2
    import numpy as np

    clip_dur = max(0.5, end_sec - start_sec)
    cap = cv2.VideoCapture(str(video_path))
    vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if vw <= 0 or vh <= 0 or total_frames <= 0:
        cap.release()
        return [], 1920, 1080

    step = 0.5
    samples: list[dict[str, Any]] = []
    prev_small: Any = None
    t = 0.0
    while t < clip_dur:
        abs_idx = min(max(0, total_frames - 1), int((start_sec + t) * fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, abs_idx)
        ok, frame = cap.read()
        if ok and frame is not None:
            small = cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA)
            gray_s = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            diff_val = 0.0
            if prev_small is not None:
                diff_val = float(np.mean(cv2.absdiff(gray_s, prev_small)))
            prev_small = gray_s
            samples.append({"t": round(t, 2), "diff": diff_val, "frame": frame})
        t += step
    cap.release()

    if not samples:
        return [], vw, vh

    # Deteksi titik potong perpindahan kamera (diff >= 18.0 dan durasi shot >= 1.5s)
    shots: list[dict[str, Any]] = []
    shot_start_idx = 0
    for i in range(1, len(samples)):
        dur_so_far = samples[i]["t"] - samples[shot_start_idx]["t"]
        if samples[i]["diff"] >= 18.0 and dur_so_far >= 1.5:
            mid_idx = (shot_start_idx + i - 1) // 2
            shots.append({
                "start": 0.0 if not shots else shots[-1]["end"],
                "end": samples[i]["t"],
                "mid_frame": samples[mid_idx]["frame"],
            })
            shot_start_idx = i

    mid_idx = (shot_start_idx + len(samples) - 1) // 2
    shots.append({
        "start": 0.0 if not shots else shots[-1]["end"],
        "end": round(clip_dur, 2),
        "mid_frame": samples[mid_idx]["frame"],
    })

    # Jika ada lebih dari 10 shot, gabungkan shot terpendek ke shot sebelahnya
    while len(shots) > 10:
        shortest_i = min(range(len(shots)), key=lambda k: shots[k]["end"] - shots[k]["start"])
        if shortest_i > 0:
            shots[shortest_i - 1]["end"] = shots[shortest_i]["end"]
            shots.pop(shortest_i)
        elif len(shots) > 1:
            shots[1]["start"] = shots[0]["start"]
            shots.pop(0)
        else:
            break

    return shots, vw, vh


def analyze_shots_with_gemini_ai(
    shots: list[dict[str, Any]],
    vw: int,
    vh: int,
) -> list[dict[str, Any]] | None:
    """
    100% Pure Gemini Vision Camera-Director:
    Mengirim frame setiap camera shot ke gemini-3.8-flash untuk mendeteksi HANYA manusia hidup
    dan mengembalikan layout serta koordinat crop untuk setiap shot kamera.
    """
    api_key = get_active_gemini_api_key()
    if not api_key or not shots:
        return None

    try:
        import cv2
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        parts: list[Any] = []

        for idx, sh in enumerate(shots):
            frame = sh.get("mid_frame")
            if frame is None:
                continue
            scale = 640.0 / max(1, frame.shape[1])
            resized = cv2.resize(frame, (640, int(round(frame.shape[0] * scale))), interpolation=cv2.INTER_AREA)
            cv2.rectangle(resized, (0, 0), (145, 34), (0, 0, 0), -1)
            cv2.putText(
                resized,
                f"SHOT #{idx}",
                (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )
            ok, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                parts.append(types.Part.from_bytes(data=buf.tobytes(), mime_type="image/jpeg"))

        if not parts:
            return None

        prompt = (
            "Kamu adalah AI Camera Director & Video Editor profesional untuk podcast vertikal 9:16.\n"
            f"Terdapat {len(shots)} gambar SHOT kamera podcast berlabel SHOT #0 sampai SHOT #{len(shots) - 1}.\n"
            "Tugasmu adalah menganalisis setiap SHOT dan menentukan framing crop untuk HANYA MANUSIA HIDUP (pembicara/host/tamu podcast).\n\n"
            "ATURAN MUTLAK:\n"
            "1. ABAIKAN BENDA MATI: Jangan pernah menganggap radio kaset, boombox, speaker, mikrofon, patung, lukisan, atau botol di meja sebagai manusia/wajah!\n"
            "2. Pilih `layout_type` dan `crops` (koordinat normalisasi 0.0 sampai 1.0) untuk setiap SHOT berdasarkan jumlah manusia aktif yang terlihat jelas di frame:\n"
            "   - Jika 1 ORANG (`layout_type`: 'single_center'):\n"
            "     Berikan 1 objek di `crops` dengan `center_x` (0.0-1.0) tepat di titik tengah hidung/wajah orang tersebut, serta `xmin, ymin, xmax, ymax` area kepala-dada.\n"
            "   - Jika 2 ORANG (`layout_type`: 'split_2'):\n"
            "     Berikan 2 objek di `crops`:\n"
            "     * Crop pertama (Panel Atas): kepala-dada orang di sebelah Kiri.\n"
            "     * Crop kedua (Panel Bawah): kepala-dada orang di sebelah Kanan.\n"
            "   - Jika 3 ORANG dan 2 orang duduk berdekatan/berdampingan sementara 1 orang terpisah (`layout_type`: 'split_2_grouped_3'):\n"
            "     Berikan 2 objek di `crops`:\n"
            "     * Crop pertama (Panel Atas): kotak gabungan yang mencakup KEDUA orang yang duduk berdekatan secara utuh.\n"
            "     * Crop kedua (Panel Bawah): kotak kepala-dada untuk 1 orang yang duduk terpisah.\n"
            "   - Jika 3 ORANG duduk berjarak seimbang Kiri, Tengah, Kanan (`layout_type`: 'split_3_equal'):\n"
            "     Berikan 3 objek di `crops` berurutan: orang Kiri (Panel Atas), orang Tengah (Panel Tengah), orang Kanan (Panel Bawah).\n"
            "   - Jika 4 ORANG (`layout_type`: 'split_2_grouped_4'):\n"
            "     Berikan 2 objek di `crops`:\n"
            "     * Crop pertama (Panel Atas): kotak gabungan 2 orang di sisi Kiri.\n"
            "     * Crop kedua (Panel Bawah): kotak gabungan 2 orang di sisi Kanan.\n"
            "   - Jika 0 ORANG (`layout_type`: 'none'): `crops` kosong `[]`.\n\n"
            "KEMBALIKAN HANYA JSON ARRAY MURNI TANPA MARKDOWN DENGAN FORMAT:\n"
            '[{"shot_index": 0, "person_count": 1, "layout_type": "single_center", "crops": [{"center_x": 0.52, "center_y": 0.34, "xmin": 0.30, "ymin": 0.08, "xmax": 0.74, "ymax": 0.78}]}]'
        )
        parts.append(prompt)

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        raw_text = (response.text or "").strip()
        raw_text = re.sub(r"^```(?:json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            parsed = parsed.get("shots", parsed.get("results", []))
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed
    except Exception as exc:
        logger.warning(f"Gemini Vision shot analysis terkendala: {exc}")

    return None


def _convert_ai_shot_to_pixel_crops(
    ai_shot: dict[str, Any],
    vw: int,
    vh: int,
    target_w: int,
    target_h: int,
) -> tuple[int, str, list[tuple[int, int, int, int]]]:
    layout_type = str(ai_shot.get("layout_type") or "none").strip()
    person_count = int(ai_shot.get("person_count") or 0)
    raw_crops = ai_shot.get("crops") or []

    if person_count <= 0 or layout_type == "none" or not raw_crops:
        return 0, "none", []

    half_h = _make_even(target_h // 2)
    third_h = _make_even(target_h // 3)
    pixel_crops: list[tuple[int, int, int, int]] = []

    if layout_type == "single_center" or person_count == 1 or len(raw_crops) == 1:
        c0 = raw_crops[0]
        xmin = float(c0.get("xmin", 0.25))
        xmax = float(c0.get("xmax", 0.75))
        ymin = float(c0.get("ymin", 0.10))
        ymax = float(c0.get("ymax", 0.80))
        cx = float(c0.get("center_x", (xmin + xmax) / 2.0)) * vw
        cy = float(c0.get("center_y", (ymin + ymax) / 2.0)) * vh
        fw = max(64.0, (xmax - xmin) * vw * 0.45)
        fh = max(64.0, (ymax - ymin) * vh * 0.45)
        crop_box = _crop_around_face(cx, cy, fw, fh, vw, vh, target_w, target_h)
        return 1, "single_center", [crop_box]

    if layout_type == "split_3_equal" and len(raw_crops) >= 3:
        for idx_c in range(3):
            c = raw_crops[idx_c]
            xmin = float(c.get("xmin", 0.1))
            xmax = float(c.get("xmax", 0.9))
            ymin = float(c.get("ymin", 0.1))
            ymax = float(c.get("ymax", 0.8))
            cx = float(c.get("center_x", (xmin + xmax) / 2.0)) * vw
            cy = float(c.get("center_y", (ymin + ymax) / 2.0)) * vh
            box_h = max(64.0, (ymax - ymin) * vh)
            p_h = third_h if idx_c < 2 else (target_h - 2 * third_h)
            p_ar = float(target_w) / float(max(1, p_h))
            crop_h = _make_even(min(vh, max(int(box_h * 1.25), int(vh * 0.36))), 64)
            crop_w = _make_even(min(vw, int(round(crop_h * p_ar))), 64)
            x = max(0, min(vw - crop_w, int(round(cx - crop_w / 2.0))))
            y = max(0, min(vh - crop_h, int(round(cy - crop_h * 0.42))))
            pixel_crops.append((x, y, crop_w, crop_h))
        return 3, "split_3_equal", pixel_crops

    # Untuk split 2 panel: split_2, split_2_grouped_3, split_2_grouped_4
    if layout_type not in ("split_2", "split_2_grouped_3", "split_2_grouped_4"):
        layout_type = "split_2"

    panel_ar = float(target_w) / float(max(1, half_h))
    for idx_c in range(min(2, len(raw_crops))):
        c = raw_crops[idx_c]
        xmin = float(c.get("xmin", 0.1))
        xmax = float(c.get("xmax", 0.9))
        ymin = float(c.get("ymin", 0.1))
        ymax = float(c.get("ymax", 0.8))
        cx = float(c.get("center_x", (xmin + xmax) / 2.0)) * vw
        cy = float(c.get("center_y", (ymin + ymax) / 2.0)) * vh
        box_w = max(64.0, (xmax - xmin) * vw)
        box_h = max(64.0, (ymax - ymin) * vh)

        desired_h = max(int(box_h * 1.25), int(vh * 0.45))
        desired_w = int(round(desired_h * panel_ar))
        if box_w * 1.20 > desired_w:
            desired_w = min(vw, int(box_w * 1.20))
            desired_h = min(vh, int(round(desired_w / panel_ar)))

        crop_h = _make_even(min(vh, desired_h), 64)
        crop_w = _make_even(min(vw, int(round(crop_h * panel_ar))), 64)
        if crop_w > vw:
            crop_w = _make_even(vw, 64)
            crop_h = _make_even(min(vh, int(round(crop_w / panel_ar))), 64)

        x = max(0, min(vw - crop_w, int(round(cx - crop_w / 2.0))))
        y = max(0, min(vh - crop_h, int(round(cy - crop_h * 0.42))))
        pixel_crops.append((x, y, crop_w, crop_h))

    if len(pixel_crops) == 1:
        return 1, "single_center", pixel_crops
    return max(2, person_count), layout_type, pixel_crops


def analyze_smart_clip_segments(
    video_path: Path,
    start_sec: float,
    end_sec: float,
    target_w: int,
    target_h: int,
) -> list[dict[str, Any]]:
    """
    Menganalisis setiap shot kamera di dalam klip menggunakan 100% Gemini Vision AI Director
    sebagai penentu utama, dengan fallback ke YuNet per-shot bila offline.
    """
    clip_dur = max(0.5, end_sec - start_sec)
    try:
        shots, vw, vh = extract_camera_shots(video_path, start_sec, end_sec)
    except Exception as exc:
        logger.warning(f"Gagal mengekstrak camera shots ({exc}).")
        return [{"start": 0.0, "end": clip_dur, "face_count": 0, "layout_type": "none", "crops": [], "vw": 1920, "vh": 1080}]

    if not shots:
        return [{"start": 0.0, "end": clip_dur, "face_count": 0, "layout_type": "none", "crops": [], "vw": vw, "vh": vh}]

    # 1. UTAMA: 100% Pure Gemini Vision AI Camera-Director
    ai_results = analyze_shots_with_gemini_ai(shots, vw, vh)
    if ai_results:
        ai_map = {int(item.get("shot_index", i)): item for i, item in enumerate(ai_results)}
        final_segments: list[dict[str, Any]] = []
        for idx, sh in enumerate(shots):
            ai_shot = ai_map.get(idx)
            if ai_shot:
                f_count, l_type, p_crops = _convert_ai_shot_to_pixel_crops(ai_shot, vw, vh, target_w, target_h)
            else:
                f_count, l_type, p_crops = 0, "none", []
            final_segments.append({
                "start": sh["start"],
                "end": sh["end"],
                "face_count": f_count,
                "layout_type": l_type,
                "crops": p_crops,
                "vw": vw,
                "vh": vh,
            })
        return final_segments

    # 2. FALLBACK OFFLINE (Jika Tanpa API Key): YuNet Strict Per-Shot
    half_h = _make_even(target_h // 2)
    third_h = _make_even(target_h // 3)
    min_face_sz = max(32, int(min(vw, vh) * 0.04))
    fallback_segments: list[dict[str, Any]] = []

    for sh in shots:
        frame = sh.get("mid_frame")
        raw_faces = detect_faces_robust(frame, min_size=min_face_sz, score_thresh=0.60) if frame is not None else []
        faces = filter_distinct_podcast_faces(raw_faces, vw, vh, min_dist_ratio=0.10)
        f_count = len(faces)
        l_type = "none"
        crops: list[tuple[int, int, int, int]] = []

        if f_count == 1:
            l_type = "single_center"
            f = faces[0]
            crops.append(_crop_around_face(f[0] + f[2] / 2.0, f[1] + f[3] / 2.0, f[2], f[3], vw, vh, target_w, target_h))
        elif f_count == 2:
            l_type = "split_2"
            for f in faces[:2]:
                crops.append(_crop_around_face(f[0] + f[2] / 2.0, f[1] + f[3] / 2.0, f[2], f[3], vw, vh, target_w, half_h))
        elif f_count == 3:
            f0, f1, f2 = faces[0], faces[1], faces[2]
            cx0, cx1, cx2 = f0[0] + f0[2] / 2.0, f1[0] + f1[2] / 2.0, f2[0] + f2[2] / 2.0
            d1, d2 = max(1.0, cx1 - cx0), max(1.0, cx2 - cx1)
            if d1 < d2 * 0.68:
                l_type = "split_2_grouped_3"
                crops.append(_crop_around_group([f0, f1], vw, vh, target_w, half_h))
                crops.append(_crop_around_face(cx2, f2[1] + f2[3] / 2.0, f2[2], f2[3], vw, vh, target_w, half_h))
            elif d2 < d1 * 0.68:
                l_type = "split_2_grouped_3"
                crops.append(_crop_around_group([f1, f2], vw, vh, target_w, half_h))
                crops.append(_crop_around_face(cx0, f0[1] + f0[3] / 2.0, f0[2], f0[3], vw, vh, target_w, half_h))
            else:
                l_type = "split_3_equal"
                crops.append(_crop_around_face(cx0, f0[1] + f0[3] / 2.0, f0[2], f0[3], vw, vh, target_w, third_h))
                crops.append(_crop_around_face(cx1, f1[1] + f1[3] / 2.0, f1[2], f1[3], vw, vh, target_w, third_h))
                crops.append(_crop_around_face(cx2, f2[1] + f2[3] / 2.0, f2[2], f2[3], vw, vh, target_w, target_h - 2 * third_h))
        elif f_count >= 4:
            l_type = "split_2_grouped_4"
            crops.append(_crop_around_group([faces[0], faces[1]], vw, vh, target_w, half_h))
            crops.append(_crop_around_group([faces[2], faces[3]], vw, vh, target_w, half_h))

        fallback_segments.append({
            "start": sh["start"],
            "end": sh["end"],
            "face_count": f_count,
            "layout_type": l_type,
            "crops": crops,
            "vw": vw,
            "vh": vh,
        })

    return fallback_segments


def detect_podcast_speaker_crops(
    video_path: Path,
    start_sec: float,
    end_sec: float,
    target_w: int,
    half_h: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]] | None:
    segs = analyze_smart_clip_segments(video_path, start_sec, end_sec, target_w, half_h * 2)
    for s in segs:
        if len(s.get("crops", [])) >= 2:
            return s["crops"][0], s["crops"][1]
    return None


def build_single_segment_filter(
    seg: dict[str, Any],
    width: int,
    height: int,
    framing: str = "crop",
    input_label: str = "",
    output_label: str = "",
) -> str:
    in_tag = f"[{input_label}]" if input_label else ""
    out_tag = f"[{output_label}]" if output_label else ""
    f_count = int(seg.get("face_count", 0))
    layout_type = str(seg.get("layout_type") or "")
    crops = seg.get("crops") or []
    uid = uuid.uuid4().hex[:6]

    if f_count == 0 or not crops or layout_type == "none":
        if framing == "crop":
            return f"{in_tag}scale=-1:{height},crop={width}:{height}:(in_w-{width})/2:0,setsar=1{out_tag}"
        return (
            f"{in_tag}split=2[fg_{uid}][bg_{uid}];"
            f"[bg_{uid}]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=20:5[bgblur_{uid}];"
            f"[fg_{uid}]scale={width}:{height}:force_original_aspect_ratio=decrease[fgfit_{uid}];"
            f"[bgblur_{uid}][fgfit_{uid}]overlay=(W-w)/2:(H-h)/2,setsar=1{out_tag}"
        )

    if layout_type == "single_center" or len(crops) == 1:
        cx, cy, cw, ch = crops[0]
        return (
            f"{in_tag}crop={cw}:{ch}:{cx}:{cy},"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1{out_tag}"
        )

    if layout_type == "split_3_equal" and len(crops) >= 3:
        (c1_x, c1_y, c1_w, c1_h) = crops[0]
        (c2_x, c2_y, c2_w, c2_h) = crops[1]
        (c3_x, c3_y, c3_w, c3_h) = crops[2]
        h_panel = _make_even(height // 3)
        h_bottom = height - 2 * h_panel
        return (
            f"{in_tag}split=3[s1_{uid}][s2_{uid}][s3_{uid}];"
            f"[s1_{uid}]crop={c1_w}:{c1_h}:{c1_x}:{c1_y},scale={width}:{h_panel}:force_original_aspect_ratio=increase,crop={width}:{h_panel}[p1_{uid}];"
            f"[s2_{uid}]crop={c2_w}:{c2_h}:{c2_x}:{c2_y},scale={width}:{h_panel}:force_original_aspect_ratio=increase,crop={width}:{h_panel}[p2_{uid}];"
            f"[s3_{uid}]crop={c3_w}:{c3_h}:{c3_x}:{c3_y},scale={width}:{h_bottom}:force_original_aspect_ratio=increase,crop={width}:{h_bottom}[p3_{uid}];"
            f"[p1_{uid}][p2_{uid}][p3_{uid}]vstack=inputs=3,"
            f"drawbox=x=0:y={h_panel-2}:w={width}:h=4:color=black@0.88:t=fill,"
            f"drawbox=x=0:y={2*h_panel-2}:w={width}:h=4:color=black@0.88:t=fill,setsar=1{out_tag}"
        )

    (lx, ly, lw, lh), (rx, ry, rw, rh) = crops[0], crops[1]
    h1 = _make_even(height // 2)
    h2 = height - h1
    return (
        f"{in_tag}split=2[s1_{uid}][s2_{uid}];"
        f"[s1_{uid}]crop={lw}:{lh}:{lx}:{ly},scale={width}:{h1}:force_original_aspect_ratio=increase,crop={width}:{h1}[p1_{uid}];"
        f"[s2_{uid}]crop={rw}:{rh}:{rx}:{ry},scale={width}:{h2}:force_original_aspect_ratio=increase,crop={width}:{h2}[p2_{uid}];"
        f"[p1_{uid}][p2_{uid}]vstack=inputs=2,"
        f"drawbox=x=0:y={h1-2}:w={width}:h=4:color=black@0.88:t=fill,setsar=1{out_tag}"
    )


def build_dynamic_segments_filter(
    segments: list[dict[str, Any]],
    width: int,
    height: int,
    framing: str = "fit",
) -> str:
    if not segments or len(segments) == 1:
        seg0 = segments[0] if segments else {"face_count": 0, "crops": []}
        return build_single_segment_filter(seg0, width, height, framing)

    n = len(segments)
    split_tags = "".join(f"[seg_in_{i}]" for i in range(n))
    parts = [f"split={n}{split_tags}"]
    for i, seg in enumerate(segments):
        parts.append(
            build_single_segment_filter(
                seg, width, height, framing, input_label=f"seg_in_{i}", output_label=f"seg_out_{i}"
            )
        )

    curr_base = "seg_out_0"
    for i in range(1, n):
        s_t = max(0.0, float(segments[i]["start"]))
        e_t = float(segments[i]["end"]) + 0.1
        next_base = f"ov_mix_{i}"
        out_str = f"[{next_base}]" if i < n - 1 else ""
        parts.append(f"[{curr_base}][seg_out_{i}]overlay=0:0:enable='between(t,{s_t:.2f},{e_t:.2f})'{out_str}")
        curr_base = next_base

    return ";".join(parts)


def ass_timestamp(seconds: float) -> str:
    cs_total = max(0, int(round(seconds * 100)))
    hours, rem = divmod(cs_total, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def hex_to_ass_bgr(hex_color: str, default: str = "&H0000DDFF") -> str:
    clean = (hex_color or "").strip().lstrip("#")
    if len(clean) == 6 and all(c in "0123456789ABCDEFabcdef" for c in clean):
        return f"&H00{clean[4:6].upper()}{clean[2:4].upper()}{clean[0:2].upper()}"
    return default


QUESTION_TRIGGERS = {
    "kenapa", "mengapa", "gimana", "bagaimana", "apakah", "siapa", "kapan",
    "berapa", "dimana", "kemana", "ceritain", "ceritakan", "jelasin", "jelaskan",
}


_VIDEO_SUBTITLE_CACHE: dict[str, bool] = {}


def check_video_has_subtitles(video_path: Path | str, start_sec: float = 0.0, end_sec: float = 0.0) -> bool:
    """Mendeteksi apakah video sudah memiliki subtitle bawaan (embedded subtitle stream atau hardsub/burned-in teks)."""
    p = Path(video_path)
    if not p.is_file():
        return False

    v_str = str(p.resolve())
    cache_key = f"{v_str}:{round(start_sec, 1)}:{round(end_sec, 1)}"
    if cache_key in _VIDEO_SUBTITLE_CACHE:
        return _VIDEO_SUBTITLE_CACHE[cache_key]

    # 1. Cek embedded stream container
    try:
        ffmpeg_bin = ffmpeg_command()[0]
        res = subprocess.run([ffmpeg_bin, "-i", v_str], capture_output=True, text=True, errors="replace", timeout=6)
        for line in res.stderr.splitlines():
            if "Stream #" in line and "Subtitle:" in line:
                _VIDEO_SUBTITLE_CACHE[cache_key] = True
                return True
    except Exception:
        pass

    # 2. Cek hardcoded burned-in subtitles via OpenCV sampling
    try:
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(v_str)
        if not cap.isOpened():
            return False

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / max(1.0, fps)

        s_sec = max(0.0, start_sec)
        e_sec = min(duration, end_sec) if end_sec > s_sec else duration
        eff_dur = e_sec - s_sec

        sample_start = s_sec + (1.5 if eff_dur > 4.0 else 0.5)
        sample_end = e_sec - (1.0 if eff_dur > 4.0 else 0.2)
        if sample_end <= sample_start:
            sample_start = s_sec
            sample_end = e_sec

        num_samples = 6
        times = [sample_start + (sample_end - sample_start) * (i + 1) / (num_samples + 1) for i in range(num_samples)]

        detected_count = 0
        valid_frames = 0

        for t in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            valid_frames += 1
            h, w = frame.shape[:2]

            is_vertical = h > w
            zones = [
                (int(h * 0.68), int(h * 0.94), int(w * 0.08), int(w * 0.92)),
            ]
            if is_vertical:
                zones.append((int(h * 0.40), int(h * 0.62), int(w * 0.08), int(w * 0.92)))

            frame_has_text = False
            for y1, y2, x1, x2 in zones:
                roi = frame[y1:y2, x1:x2]
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

                sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
                abs_sobelx = np.absolute(sobelx)
                edges = np.uint8(abs_sobelx)

                _, bright_thresh = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)
                _, edge_thresh = cv2.threshold(edges, 45, 255, cv2.THRESH_BINARY)

                text_candidates = cv2.bitwise_and(bright_thresh, edge_thresh)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3))
                connected = cv2.morphologyEx(text_candidates, cv2.MORPH_CLOSE, kernel)

                contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                line_count = 0
                for cnt in contours:
                    cx, cy, cw, ch = cv2.boundingRect(cnt)
                    aspect = cw / max(1, ch)
                    rel_h = ch / float(h)
                    rel_w = cw / float(w)
                    if 0.016 <= rel_h <= 0.11 and rel_w >= 0.035 and aspect >= 1.2:
                        box_roi = text_candidates[cy:cy+ch, cx:cx+cw]
                        fill_ratio = cv2.countNonZero(box_roi) / float(cw * ch)
                        if 0.10 <= fill_ratio <= 0.70:
                            line_count += 1

                if line_count >= 1:
                    frame_has_text = True
                    break

            if frame_has_text:
                detected_count += 1

        cap.release()
        ratio = detected_count / max(1, valid_frames)
        has_sub = ratio >= 0.33
        _VIDEO_SUBTITLE_CACHE[cache_key] = has_sub
        return has_sub
    except Exception:
        return False


def write_ass_pop_subtitle(
    transcript: list[dict[str, Any]],
    start: float,
    end: float,
    ass_path: Path,
    aspect_ratio: str = "16:9",
    layout: str = "standard",
    position: str = "auto",
    font_size: int = 14,
    max_lines: int = 2,
    mode: str = "active_highlight",
    base_color_hex: str = "#FFFFFF",
    active_color_hex: str = "auto_context",
    censor_profanity: bool = False,
    quality: str = "1080",
    subtitle_x: float = 0.15,
    subtitle_y: float = 0.78,
    hook_banner_enabled: bool = True,
    hook_banner_text: str = "",
    hook_banner_duration: float = 1.0,
    layout_segments: list[dict[str, Any]] | None = None,
    emoji_subtitles: bool = True,
    **kwargs: Any,
) -> None:
    width, height = output_dimensions(aspect_ratio, quality)
    is_landscape = width >= height

    if is_landscape:
        scale_factor = (height / 360.0)
        scaled_font_size = max(32, min(72, int(font_size * scale_factor * 0.95)))
        thumb_font_size = max(58, min(96, int(height * 0.072)))
    else:
        scale_factor = (height / 420.0)
        scaled_font_size = max(42, min(92, int(font_size * scale_factor)))
        thumb_font_size = max(68, min(110, int(width * 0.078)))

    primary_ass = hex_to_ass_bgr(base_color_hex, "&H00FFFFFF")
    default_active_ass = hex_to_ass_bgr(
        "#FFDD00" if active_color_hex == "auto_context" else active_color_hex,
        "&H0000DDFF",
    )

    if position == "center" or (layout == "podcast_split" and position in ("auto", "bottom")):
        alignment = 5
        margin_v = 0
    elif position == "top":
        alignment = 8
        margin_v = int(height * (0.08 if is_landscape else 0.14))
    else:
        alignment = 2
        margin_v = int(height * (0.075 if is_landscape else 0.18))

    free_pos_tag = ""
    if position == "free":
        fx = max(60, min(width - 60, int(width * subtitle_x)))
        fy = max(40, min(height - 40, int(height * subtitle_y)))
        alignment = 5
        margin_v = 0
        free_pos_tag = f"{{\\an5\\pos({fx},{fy})}}"

    outline_w = 3.6 if is_landscape else 4.5
    shadow_w = 2.0 if is_landscape else 2.5

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: SmartNotice,Arial Black,{scaled_font_size},{primary_ass},{default_active_ass},&H00000000,&H80000000,-1,0,0,0,100,100,1.0,0,1,{outline_w},{shadow_w},{alignment},40,40,{margin_v},1
Style: ThumbnailHook,Arial Black,{thumb_font_size},&H00FFFFFF,&H0000DDFF,&H00000000,&HB0000000,-1,0,0,0,100,100,1.5,0,1,6.0,3.5,5,50,50,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    clip_dur = max(0.1, end - start)
    hook_dur = max(0.0, min(clip_dur, float(hook_banner_duration))) if hook_banner_enabled else 0.0

    # 1. RENDER THUMBNAIL HOOK DI AWAL VIDEO (DEFAULT 1 DETIK PERTAMA)
    if hook_banner_enabled and hook_dur > 0 and hook_banner_text.strip():
        hb_words = hook_banner_text.strip().split()
        colored_hb_tokens: list[str] = []
        has_special_colored = False
        for idx_w, hw in enumerate(hb_words):
            _, w_ass, is_spec = detect_word_context_color(hw, hook_banner_text, "auto_context")
            if is_spec:
                has_special_colored = True
                colored_hb_tokens.append(f"{{\\c{w_ass}}}{hw}{{\\c&H00FFFFFF}}")
            elif not has_special_colored and idx_w >= len(hb_words) - 2:
                # Jika tidak ada kata di kamus, beri warna Kuning Emas pada 2 kata terakhir sebagai punchline thumbnail
                colored_hb_tokens.append(f"{{\\c&H0000DDFF}}{hw}{{\\c&H00FFFFFF}}")
            else:
                colored_hb_tokens.append(hw)

        max_per_line = 4 if is_landscape else 3
        hb_lines: list[str] = []
        for i in range(0, len(colored_hb_tokens), max_per_line):
            hb_lines.append(" ".join(colored_hb_tokens[i : i + max_per_line]))
        hb_body = "\\N".join(hb_lines[:3])

        cx = width // 2
        cy = int(height * (0.48 if is_landscape else 0.45))
        pop_anim = f"{{\\an5\\pos({cx},{cy})\\fscx115\\fscy115\\t(0,140,\\fscx100\\fscy100)}}"
        events.append(
            f"Dialogue: 2,{ass_timestamp(0.0)},{ass_timestamp(hook_dur)},ThumbnailHook,,0,0,0,,{pop_anim}{hb_body}"
        )

    # 2. RENDER SUBTITLE PERCAKAPAN KONTEKSTUAL
    for item in transcript:
        seg_abs_start = float(item.get("start", 0.0))
        seg_abs_end = float(item.get("end", 0.0))
        if seg_abs_end <= start or seg_abs_start >= end:
            continue
        item_start = max(0.0, seg_abs_start - start)
        item_end = min(clip_dur, seg_abs_end - start)
        if item_end <= item_start:
            continue
        item_text = str(item.get("text", "")).strip()
        if not item_text:
            continue

        raw_words = item.get("words")
        norm_words: list[dict[str, Any]] = []
        if raw_words:
            for w in raw_words:
                w_txt = str(getattr(w, "word", "") if hasattr(w, "word") else w.get("word", "")).strip()
                if not w_txt:
                    continue
                w_txt = censor_word_if_enabled(w_txt, censor_profanity)
                w_abs_s = float(getattr(w, "start", seg_abs_start) if hasattr(w, "start") else w.get("start", seg_abs_start))
                w_abs_e = float(getattr(w, "end", seg_abs_end) if hasattr(w, "end") else w.get("end", seg_abs_end))
                rel_s = w_abs_s - start if w_abs_s >= start - 0.5 else w_abs_s
                rel_e = w_abs_e - start if w_abs_e >= start - 0.5 else w_abs_e
                rel_s = max(0.0, min(clip_dur, rel_s))
                rel_e = max(rel_s + 0.08, min(clip_dur, rel_e))
                if rel_e > rel_s and rel_s < clip_dur:
                    norm_words.append({"word": w_txt, "start": round(rel_s, 3), "end": round(rel_e, 3)})

        if not norm_words:
            w_list = [censor_word_if_enabled(tok, censor_profanity) for tok in item_text.split()]
            if w_list:
                tot_dur = max(0.2, item_end - item_start)
                per_w = tot_dur / len(w_list)
                norm_words = [
                    {"word": w, "start": round(item_start + i * per_w, 3), "end": round(item_start + (i + 1) * per_w, 3)}
                    for i, w in enumerate(w_list)
                ]

        if mode == "single_word":
            for i, nw in enumerate(norm_words):
                ws_t = nw["start"]
                we_t = nw["end"]
                if i + 1 < len(norm_words):
                    nxt_s = norm_words[i + 1]["start"]
                    if 0 <= (nxt_s - we_t) < 0.12:
                        we_t = nxt_s
                    elif we_t > nxt_s:
                        we_t = max(ws_t + 0.06, nxt_s)
                if we_t <= ws_t:
                    continue
                act_ass = "&H0000DDFF" if active_color_hex in ("#FFDD00", "auto_context") else default_active_ass
                if active_color_hex == "auto_context":
                    _, word_ass, _ = detect_word_context_color(nw["word"], item_text, active_color_hex)
                    act_ass = word_ass
                raw_tok = nw["word"].upper()
                if emoji_subtitles:
                    raw_tok = decorate_word_with_emoji(raw_tok, enabled=True)
                cue_text = f"{free_pos_tag}{{\\c{act_ass}\\fscx122\\fscy122\\t(0,110,\\fscx106\\fscy106)}}{raw_tok}"
                events.append(f"Dialogue: 0,{ass_timestamp(ws_t)},{ass_timestamp(we_t)},SmartNotice,,0,0,0,,{cue_text}")
            continue

        chunk_size = 5 if (is_landscape and max_lines != 1) else (3 if max_lines == 1 else 4)
        for chunk_idx in range(0, len(norm_words), chunk_size):
            chunk = norm_words[chunk_idx : chunk_idx + chunk_size]
            if not chunk:
                continue
            chunk_sentence = " ".join(c["word"] for c in chunk)
            for active_i, nw in enumerate(chunk):
                ws_t = nw["start"]
                if active_i + 1 < len(chunk):
                    nxt_s = chunk[active_i + 1]["start"]
                    we_t = nxt_s if (nxt_s - nw["end"]) < 0.45 else nw["end"]
                else:
                    we_t = nw["end"]
                    if chunk_idx + chunk_size < len(norm_words):
                        next_chunk_s = norm_words[chunk_idx + chunk_size]["start"]
                        if we_t > next_chunk_s:
                            we_t = max(ws_t + 0.06, next_chunk_s)
                if we_t <= ws_t:
                    continue

                formatted_tokens: list[str] = []
                for i, cw_obj in enumerate(chunk):
                    raw_tok = cw_obj["word"].upper()
                    if emoji_subtitles:
                        emo = map_word_to_emoji(raw_tok)
                        if emo:
                            raw_tok = f"{raw_tok} {emo}"
                    if i == active_i:
                        act_ass = "&H0000DDFF" if active_color_hex in ("#FFDD00", "auto_context") else default_active_ass
                        if active_color_hex == "auto_context":
                            _, word_ass, _ = detect_word_context_color(raw_tok, chunk_sentence, active_color_hex)
                            act_ass = word_ass
                        formatted_tokens.append(
                            f"{{\\c{act_ass}\\fscx122\\fscy122\\t(0,110,\\fscx106\\fscy106)}}{raw_tok}{{\\c{primary_ass}\\fscx100\\fscy100}}"
                        )
                    else:
                        formatted_tokens.append(raw_tok)

                if max_lines >= 2 and len(formatted_tokens) >= (5 if is_landscape else 4):
                    mid = len(formatted_tokens) // 2
                    cue_text = " ".join(formatted_tokens[:mid]) + "\\N" + " ".join(formatted_tokens[mid:])
                else:
                    cue_text = " ".join(formatted_tokens)

                events.append(f"Dialogue: 0,{ass_timestamp(ws_t)},{ass_timestamp(we_t)},SmartNotice,,0,0,0,,{free_pos_tag}{cue_text}")

    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def video_layout_filter(
    aspect_ratio: str,
    framing: str,
    layout: str,
    face_crop: tuple[int, int, int, int] | None,
    quality: str = "1080",
) -> str:
    width, height = output_dimensions(aspect_ratio, quality)

    if layout != "facecam_top" or not face_crop:
        if framing == "fit":
            return (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
            )
        return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1"

    crop_x, crop_y, crop_w, crop_h = face_crop
    top_height = int(height * 0.35)
    if top_height % 2 != 0:
        top_height += 1
    bottom_height = height - top_height

    if framing == "fit":
        return (
            f"split=2[face][mfg];"
            f"[face]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
            f"scale={width}:{top_height}:force_original_aspect_ratio=increase,crop={width}:{top_height}[faceout];"
            f"[mfg]scale={width}:{bottom_height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{bottom_height}:(ow-iw)/2:(oh-ih)/2:black[mainout];"
            f"[faceout][mainout]vstack=inputs=2,setsar=1"
        )

    return (
        f"split=2[face][main];"
        f"[face]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={width}:{top_height}:force_original_aspect_ratio=increase,crop={width}:{top_height}[faceout];"
        f"[main]scale={width}:{bottom_height}:force_original_aspect_ratio=increase,crop={width}:{bottom_height}[mainout];"
        f"[faceout][mainout]vstack=inputs=2,setsar=1"
    )


_DETECTED_ENCODERS: list[tuple[str, str]] | None = None


def detect_hardware_encoders() -> list[tuple[str, str]]:
    global _DETECTED_ENCODERS
    if _DETECTED_ENCODERS is not None:
        return _DETECTED_ENCODERS

    exe = ffmpeg_command()[0]
    candidates = [
        ("h264_nvenc", "NVIDIA NVENC H.264 (GPU Dedicated)"),
        ("av1_nvenc", "NVIDIA NVENC AV1 (GPU Dedicated)"),
        ("h264_amf", "AMD AMF H.264 (GPU Dedicated)"),
        ("av1_amf", "AMD AMF AV1 (GPU Dedicated)"),
    ]
    detected = [("auto", "Otomatis (Pilih Akselerasi Terbaik)")]
    for enc, label in candidates:
        try:
            cmd = [exe, "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.04", "-c:v", enc, "-f", "null", "-"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=SUBPROCESS_FLAGS)
            if res.returncode == 0:
                detected.append((enc, label))
        except Exception:
            pass
    detected.append(("libx264", "Software CPU (libx264)"))
    _DETECTED_ENCODERS = detected
    return detected


def get_encoder_args(encoder: str) -> tuple[list[str], str]:
    if encoder == "auto":
        hardware = detect_hardware_encoders()
        for enc, _ in hardware:
            if enc not in ("auto", "libx264"):
                return get_encoder_args(enc)
        return get_encoder_args("libx264")

    if encoder == "av1_nvenc":
        return ["-c:v", "av1_nvenc", "-pix_fmt", "yuv420p", "-cq", "24"], "NVIDIA NVENC AV1"
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-pix_fmt", "yuv420p", "-preset", "p4", "-cq", "21"], "NVIDIA NVENC H.264"
    if encoder == "av1_amf":
        return ["-c:v", "av1_amf", "-pix_fmt", "yuv420p", "-quality", "speed"], "AMD AMF AV1"
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-pix_fmt", "yuv420p", "-quality", "speed"], "AMD AMF H.264"
    return ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "21"], "CPU libx264"


def run_ffmpeg_with_progress(
    cmd: list[str],
    cwd: Path,
    job_id: str | None = None,
    clip_duration: float = 30.0,
    clip_index: int = 1,
    total_clips: int = 1,
    progress_start: int = 70,
    progress_end: int = 95,
    clip_title: str = "Highlight",
) -> None:
    if job_id and job_id in CANCELED_JOBS:
        raise RuntimeError("Proses dibatalkan oleh pengguna.")

    full_cmd = list(cmd)
    if "-progress" not in full_cmd:
        full_cmd.insert(-1, "-progress")
        full_cmd.insert(-1, "pipe:1")

    proc = subprocess.Popen(
        full_cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=SUBPROCESS_FLAGS,
    )
    if job_id:
        ACTIVE_PROCESSES[job_id] = proc

    stderr_lines: deque[str] = deque(maxlen=50)

    def _drain_stderr() -> None:
        try:
            if proc.stderr:
                for err_line in proc.stderr:
                    stderr_lines.append(err_line)
        except Exception:
            pass

    t_err = threading.Thread(target=_drain_stderr, daemon=True)
    t_err.start()

    last_update_time = 0.0
    try:
        if proc.stdout:
            for line in proc.stdout:
                if job_id and job_id in CANCELED_JOBS:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    raise RuntimeError("Proses dibatalkan oleh pengguna.")
                line = line.strip()
                if (line.startswith("out_time_ms=") or line.startswith("out_time_us=")) and job_id:
                    try:
                        us = int(line.split("=")[1])
                        cur_sec = us / 1000000.0
                        now = time.time()
                        if now - last_update_time >= 0.5:
                            last_update_time = now
                            clip_dur = max(1.0, clip_duration)
                            clip_pct = min(98, max(1, int((cur_sec / clip_dur) * 100)))
                            clip_ratio = (clip_index - 1 + (clip_pct / 100.0)) / max(1, total_clips)
                            curr_overall = min(
                                progress_end, progress_start + int(clip_ratio * (progress_end - progress_start))
                            )
                            update_job(
                                job_id,
                                progress=curr_overall,
                                sub_progress=clip_pct,
                                message=f"Merender clip {clip_index} dari {total_clips} ({curr_overall}%)...",
                                sub_message=f"Memproses video & subtitle: {clip_pct}% (detik ke-{cur_sec:.0f}/{clip_dur:.0f}s)",
                            )
                    except Exception:
                        pass

        proc.wait()
    finally:
        if job_id:
            ACTIVE_PROCESSES.pop(job_id, None)

    t_err.join(timeout=2.0)
    if proc.returncode != 0:
        if job_id and job_id in CANCELED_JOBS:
            raise RuntimeError("Proses dibatalkan oleh pengguna.")
        stderr_err = "".join(stderr_lines).strip()
        raise RuntimeError(f"FFmpeg render error ({proc.returncode}): {stderr_err[-400:]}")


def media_dimensions(video_path: Path) -> tuple[int, int]:
    try:
        import cv2
        capture = cv2.VideoCapture(str(video_path))
        w = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        capture.release()
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    return 1920, 1080


def wrap_banner_text(text: str, max_chars: int = 26) -> list[str]:
    words_list = text.strip().split()
    if not words_list:
        return []
    lines: list[str] = []
    curr: list[str] = []
    curr_len = 0
    for w in words_list:
        if curr and (curr_len + len(w) + 1 > max_chars):
            lines.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
        else:
            curr.append(w)
            curr_len += len(w) + (1 if len(curr) > 1 else 0)
    if curr:
        lines.append(" ".join(curr))
    return lines[:2]


def escape_drawtext(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("'", "'\\''")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace(",", "\\,")
    )


def resolve_pixel_face_crop(
    video: Path,
    options: CreateJobRequest,
    clip_start: float = 0.0,
    clip_end: float = 0.0,
) -> tuple[int, int, int, int] | None:
    if options.layout != "facecam_top":
        return None
    raw_crop = getattr(options, "facecam_crop", None)
    if raw_crop and len(raw_crop) == 4:
        fx, fy, fw, fh = [float(v) for v in raw_crop]
        vw, vh = media_dimensions(video)
        if all(0.0 <= v <= 1.0 for v in (fx, fy, fw, fh)):
            px = max(0, min(vw - 32, int(fx * vw)))
            py = max(0, min(vh - 32, int(fy * vh)))
            pw = max(32, min(vw - px, int(fw * vw)))
            ph = max(32, min(vh - py, int(fh * vh)))
            return (px, py, pw, ph)
        return (int(fx), int(fy), max(32, int(fw)), max(32, int(fh)))
    return detect_face_crop(video, clip_start, clip_end)


def calculate_dynamic_zoom_intervals(
    transcript: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    energy_map: list[float] | None = None,
) -> list[tuple[float, float]]:
    """
    Menghitung interval waktu (start, end relatif detik) untuk punch-in micro-zoom dinamis (1.08x).
    Memberikan penekanan visual pada momen puncak/punchline/pertanyaan agar klip tidak monoton.
    """
    clip_dur = clip_end - clip_start
    if clip_dur < 10.0:
        return []

    spicy_words = set(CLIP_FLAVOR_PROFILES["spicy_drama"]["keywords"]) | QUESTION_TRIGGERS | _TOPIC_SUBSTANTIVE_TRIGGERS
    candidate_times: list[float] = []

    for item in transcript:
        seg_s = float(item.get("start", 0.0))
        seg_e = float(item.get("end", 0.0))
        if seg_e <= clip_start + 1.0 or seg_s >= clip_end - 1.5:
            continue

        raw_words = item.get("words")
        if raw_words:
            for w in raw_words:
                w_s = float(getattr(w, "start", seg_s) if hasattr(w, "start") else w.get("start", seg_s))
                w_txt = str(getattr(w, "word", "") if hasattr(w, "word") else w.get("word", "")).strip()
                clean = re.sub(r"[^a-zA-Z0-9]", "", w_txt).lower()
                if clean in spicy_words or "?" in w_txt:
                    rel = w_s - clip_start
                    if 1.5 <= rel <= clip_dur - 2.5:
                        candidate_times.append(rel)
        else:
            txt = str(item.get("text", ""))
            for tok in words(txt):
                if tok in spicy_words or "?" in txt:
                    rel = seg_s - clip_start
                    if 1.5 <= rel <= clip_dur - 2.5:
                        candidate_times.append(rel)
                    break

    intervals: list[tuple[float, float]] = []
    last_end = -10.0

    for t in candidate_times:
        if t - last_end >= 5.0 and (t + 1.8) <= clip_dur - 0.8:
            zoom_s = max(0.5, round(t - 0.2, 2))
            zoom_e = min(clip_dur - 0.5, round(zoom_s + 1.8, 2))
            intervals.append((zoom_s, zoom_e))
            last_end = zoom_e
            if len(intervals) >= 5:
                break

    if not intervals and clip_dur >= 18.0:
        t1 = round(clip_dur * 0.28, 2)
        intervals.append((t1, round(t1 + 1.8, 2)))
        if clip_dur >= 42.0:
            t2 = round(clip_dur * 0.65, 2)
            intervals.append((t2, round(t2 + 1.8, 2)))

    return intervals


def build_micro_zoom_filter(
    intervals: list[tuple[float, float]],
    width: int,
    height: int,
    zoom_factor: float = 1.08,
) -> str:
    """
    Membangun FFmpeg split-overlay filter untuk punch-in zoom halus 1.08x tanpa merusak aspect ratio.
    """
    if not intervals:
        return ""
    enable_terms = "+".join([f"between(t,{s:.2f},{e:.2f})" for s, e in intervals])
    return (
        f"split=2[mz_orig][mz_crop];"
        f"[mz_crop]crop=iw/{zoom_factor:.2f}:ih/{zoom_factor:.2f}:(iw-ow)/2:(ih-oh)/2,scale={width}:{height}[mz_zoomed];"
        f"[mz_orig][mz_zoomed]overlay=0:0:enable='{enable_terms}'"
    )


BROLL_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "money": ["uang", "duit", "cuan", "miliar", "milyar", "juta", "kaya", "rupiah", "gaji", "bisnis", "omset", "omzet", "investasi", "saham", "crypto", "kripto", "modal", "untung", "bayaran", "harga"],
    "police_law": ["polisi", "jaksa", "pengadilan", "hukum", "penjara", "kasus", "ditangkap", "sidang", "borgol", "pasal", "tahanan", "korupsi", "kejahatan"],
    "tech": ["ai", "teknologi", "komputer", "internet", "robot", "gadget", "aplikasi", "coding", "software", "hacker", "sistem", "digital", "data"],
    "drama_danger": ["ancaman", "bahaya", "ribut", "bentrok", "hancur", "darurat", "senjata", "rusuh", "teror", "ledakan"],
    "people_city": ["kota", "jakarta", "gedung", "kantor", "masyarakat", "publik", "rakyat", "jalan", "macet"],
    "sad_break": ["sedih", "nangis", "patah", "putus", "depresi", "trauma", "kecewa", "drop", "down", "luka", "hancur"],
}


def detect_broll_moments(
    transcript: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    broll_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Mendeteksi 1-2 momen visual (durasi 2.0-2.5 detik) yang cocok untuk disisipkan B-Roll ilustrasi.
    Mengembalikan daftar dict: [{"path": Path, "start": float, "end": float, "category": str}]
    """
    broll_root = broll_dir if (broll_dir and broll_dir.is_dir()) else (ROOT / "broll")
    if not broll_root.is_dir():
        return []

    video_files: list[Path] = []
    for ext in ("*.mp4", "*.mov", "*.mkv", "*.webm"):
        video_files.extend(broll_root.rglob(ext))

    if not video_files:
        return []

    clip_dur = clip_end - clip_start
    if clip_dur < 16.0:
        return []

    matched_moments: list[dict[str, Any]] = []
    last_end = -10.0

    for item in transcript:
        seg_s = float(item.get("start", 0.0))
        seg_e = float(item.get("end", 0.0))
        if seg_e <= clip_start + 4.0 or seg_s >= clip_end - 4.0:
            continue

        item_text = normalize_indonesian_transcript_text(str(item.get("text", "")).lower())
        toks = words(item_text)

        for cat, kw_list in BROLL_CATEGORY_KEYWORDS.items():
            if any(kw in toks for kw in kw_list):
                rel_s = round(max(3.0, seg_s - clip_start + 0.5), 2)
                rel_e = round(min(clip_dur - 2.0, rel_s + 2.5), 2)
                if (rel_e - rel_s) >= 1.8 and (rel_s - last_end) >= 12.0:
                    cat_files = [f for f in video_files if cat in f.stem.lower() or cat in str(f.parent).lower()]
                    chosen = random.choice(cat_files) if cat_files else random.choice(video_files)
                    matched_moments.append({
                        "path": chosen,
                        "start": rel_s,
                        "end": rel_e,
                        "category": cat,
                    })
                    last_end = rel_e
                    if len(matched_moments) >= 2:
                        return matched_moments
                    break

    return matched_moments


def craft_thumbnail_hook_lines(raw_text: str, is_landscape: bool = True) -> list[tuple[str, str]]:
    """
    Memformat judul klip / pancingan menjadi 2-3 baris thumbnail hook
    dengan kontras warna kontekstual (Merah, Kuning, Hijau, Cyan, Putih).
    Mengembalikan daftar tuple: [(teks_baris, hex_color), ...]
    """
    headline = build_thumbnail_hook_headline(raw_text)
    toks = headline.split()
    if not toks:
        toks = ["HIGHLIGHT", "MENARIK", "HARI", "INI!"]

    # Maksimal 9 kata agar padat dan memicu rasa penasaran
    toks = toks[:9]

    # Bagi menjadi 2 atau 3 baris
    if len(toks) <= 4:
        mid = max(1, len(toks) // 2)
        lines = [" ".join(toks[:mid]), " ".join(toks[mid:])]
    elif len(toks) <= 6:
        mid = len(toks) // 2
        lines = [" ".join(toks[:mid]), " ".join(toks[mid:])]
    else:
        part1 = len(toks) // 3
        part2 = 2 * len(toks) // 3
        lines = [" ".join(toks[:part1]), " ".join(toks[part1:part2]), " ".join(toks[part2:])]

    # Beri warna kontras untuk masing-masing baris
    result: list[tuple[str, str]] = []
    for i, line_str in enumerate(lines):
        line_u = line_str.upper()
        best_col = ""
        for w in line_str.split():
            w_hex, _, is_kw = detect_word_context_color(w, headline, "#FFDD00")
            if is_kw:
                best_col = w_hex
                break
        if not best_col:
            if i == 0:
                best_col = "#00E5FF" if ("?" in headline or len(lines) == 3) else "#FFFFFF"
            elif i == 1:
                best_col = "#FFDD00"
            else:
                best_col = "#FFFFFF"

        result.append((line_u, best_col))
    return result


def render_clip(
    video: Path,
    transcript: list[dict[str, Any]],
    clip: Clip,
    job_dir: Path,
    options: CreateJobRequest,
    face_crop: tuple[int, int, int, int] | None,
    job_id: str | None = None,
    clip_index: int = 1,
    total_clips: int = 1,
    progress_start: int = 70,
    progress_end: int = 95,
) -> None:
    try:
        from clipper_hud import launch_hud_process
        launch_hud_process()
    except Exception:
        pass
    clip_dir = clip_result_dir(job_dir, clip.id, clip.title)
    for old_dir in job_dir.glob(f"{clip.id} - *"):
        if old_dir.is_dir() and old_dir != clip_dir:
            shutil.rmtree(old_dir, ignore_errors=True)
    clip_dir.mkdir(exist_ok=True)
    subtitle_path = clip_dir / "subtitle.srt"
    ass_subtitle_path = clip_dir / "subtitle.ass"
    max_lines = getattr(options, "subtitle_max_lines", 2)
    font_size = getattr(options, "subtitle_font_size", 18)
    sub_mode = getattr(options, "subtitle_mode", "active_highlight")
    active_col = getattr(options, "subtitle_active_color", "#FFDD00")
    if active_col in ("auto", "auto_context", "context"):
        active_col = "auto_context"
    censor_flag = bool(getattr(options, "censor_profanity", False))

    q_opt = getattr(options, "quality", "1080")
    width, height = output_dimensions(options.aspect_ratio, q_opt)

    layout_segments: list[dict[str, Any]] | None = None
    if options.layout == "facecam_top":
        effective_face_crop = (
            resolve_pixel_face_crop(video, options, clip.start, clip.end)
        )
        layout_filter = video_layout_filter(
            options.aspect_ratio, options.framing, options.layout, effective_face_crop, quality=q_opt
        )
    else:
        # Mengabaikan auto framing podcast: gunakan framing standar bersih 9:16 (crop/fit)
        layout_filter = video_layout_filter(
            options.aspect_ratio, options.framing, "standard", None, quality=q_opt
        )

    emoji_flag = bool(getattr(options, "emoji_subtitles", True))

    skip_if_existing = bool(getattr(options, "skip_if_has_subtitles", True))
    has_existing_subs = False
    if skip_if_existing and video.is_file():
        has_existing_subs = check_video_has_subtitles(video, clip.start, clip.end)

    if has_existing_subs:
        logger.info(
            f"ℹ️ [Auto Subtitle Bypass] Video sumber '{video.name}' sudah memiliki subtitle bawaan. "
            f"Subtitle baru otomatis dilewati agar tidak bertumpuk/dobel."
        )

    sub_transcript = [] if has_existing_subs else transcript

    write_srt(
        transcript,
        clip.start,
        clip.end,
        subtitle_path,
        max_lines=max_lines,
        mode=sub_mode,
        highlight_color=active_col,
        censor_profanity=censor_flag,
        emoji_subtitles=emoji_flag,
    )
    hb_enabled = bool(getattr(options, "hook_banner_enabled", True))
    hb_dur = int(getattr(options, "hook_banner_duration", 1))
    hb_headline = build_thumbnail_hook_headline(clip.title, getattr(options, "hook_banner_text", "")) if hb_enabled else ""
    write_ass_pop_subtitle(
        sub_transcript,
        clip.start,
        clip.end,
        ass_subtitle_path,
        aspect_ratio=options.aspect_ratio,
        layout=options.layout,
        position=options.subtitle_position,
        font_size=font_size,
        max_lines=max_lines,
        mode=sub_mode,
        base_color_hex=options.subtitle_color if options.subtitle_color != "auto" else "#FFFFFF",
        active_color_hex=active_col,
        censor_profanity=censor_flag,
        quality=q_opt,
        subtitle_x=options.subtitle_x,
        subtitle_y=options.subtitle_y,
        hook_banner_enabled=hb_enabled,
        hook_banner_text=hb_headline,
        hook_banner_duration=hb_dur,
        layout_segments=layout_segments,
        emoji_subtitles=emoji_flag,
    )

    if getattr(options, "mirror_video", False):
        layout_filter = f"{layout_filter},hflip"
    if getattr(options, "color_boost", False):
        layout_filter = f"{layout_filter},eq=contrast=1.06:saturation=1.12:brightness=0.01"

    if getattr(options, "dynamic_micro_zoom", True):
        zoom_intervals = calculate_dynamic_zoom_intervals(transcript, clip.start, clip.end)
        if zoom_intervals:
            zoom_flt = build_micro_zoom_filter(zoom_intervals, width, height, zoom_factor=1.08)
            if zoom_flt:
                layout_filter = f"{layout_filter}[pre_zoom];[pre_zoom]{zoom_flt}"

    if getattr(options, "auto_broll", False):
        broll_user_dir = Path(getattr(options, "broll_folder", "")).resolve() if getattr(options, "broll_folder", "") else None
        broll_moments = detect_broll_moments(transcript, clip.start, clip.end, broll_dir=broll_user_dir)
        for b_idx, bm in enumerate(broll_moments):
            b_path_str = str(bm["path"].resolve()).replace("\\", "/")
            b_s = bm["start"]
            b_e = bm["end"]
            layout_filter = (
                f"{layout_filter}[pre_broll_{b_idx}];"
                f"movie='{b_path_str}',setpts=PTS-STARTPTS+{b_s}/TB,"
                f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[broll_{b_idx}];"
                f"[pre_broll_{b_idx}][broll_{b_idx}]overlay=0:0:enable='between(t,{b_s:.2f},{b_e:.2f})':eof_action=pass"
            )

    if hb_enabled and hb_dur > 0 and hb_headline:
        box_y = int(height * 0.26)
        box_h = int(height * 0.44)
        layout_filter = (
            f"{layout_filter},"
            f"drawbox=x=0:y={box_y}:w={width}:h={box_h}:color=black@0.58:t=fill:enable='between(t,0,{hb_dur})'"
        )

    if has_existing_subs:
        if hb_enabled and hb_dur > 0 and hb_headline:
            video_filter = f"{layout_filter},ass=subtitle.ass"
        else:
            video_filter = layout_filter
    elif options.subtitle_style == "none" and not (hb_enabled and hb_dur > 0):
        video_filter = layout_filter
    elif hb_enabled or sub_mode in ("active_highlight", "single_word") or active_col == "auto_context" or options.layout == "podcast_split" or options.subtitle_position == "center":
        video_filter = f"{layout_filter},ass=subtitle.ass"
    else:
        subtitle_style = subtitle_style_with_position(
            options.subtitle_style,
            options.subtitle_position,
            options.subtitle_color,
            options.subtitle_x,
            options.subtitle_y,
            options.aspect_ratio,
            font_size=font_size,
        )
        video_filter = f"{layout_filter},subtitles=subtitle.srt:force_style='{subtitle_style}'"

    wm_text = getattr(options, "watermark_text", "").strip()
    wm_pos = getattr(options, "watermark_position", "top_right")
    wm_opacity = float(getattr(options, "watermark_opacity", 0.65))
    if wm_text:
        safe_wm = escape_drawtext(wm_text)
        pos_xy = {
            "top_left": "x=28:y=28",
            "top_right": "x=w-text_w-28:y=28",
            "bottom_right": "x=w-text_w-28:y=h-text_h-36",
            "bottom_left": "x=28:y=h-text_h-36",
            "center": "x=(w-text_w)/2:y=(h-text_h)/2",
        }.get(wm_pos, "x=w-text_w-28:y=28")
        video_filter += (
            f",drawtext=text='{safe_wm}':fontcolor=white@{wm_opacity:.2f}:fontsize=18:font='Arial':"
            f"box=1:boxcolor=black@0.35:boxborderw=5:{pos_xy}"
        )

    wm_img = getattr(options, "watermark_image_path", "").strip()
    if wm_img and Path(wm_img).is_file():
        wm_copy = clip_dir / "wm_logo.png"
        try:
            shutil.copy2(wm_img, wm_copy)
            img_xy = {
                "top_left": "28:28",
                "top_right": "W-w-28:28",
                "bottom_left": "28:H-h-36",
                "bottom_right": "W-w-28:H-h-36",
                "center": "(W-w)/2:(H-h)/2",
            }.get(wm_pos, "W-w-28:28")
            video_filter = (
                f"{video_filter}[basevid];"
                f"movie=wm_logo.png,scale=150:-1,format=rgba,"
                f"colorchannelmixer=aa={wm_opacity:.2f}[wmlogo];"
                f"[basevid][wmlogo]overlay={img_xy}"
            )
        except Exception as e:
            logger.warning(f"Gagal memasang watermark gambar: {e}")

    if getattr(options, "speed_shift", False):
        video_filter = f"{video_filter},setpts=PTS/1.03"

    enc_args, enc_name = get_encoder_args(getattr(options, "video_encoder", "auto"))
    resolved_video = str(Path(video).resolve())
    clip_duration = max(1.0, clip.end - clip.start)

    bgm_file = getattr(options, "bgm_path", "").strip()
    has_bgm = bool(bgm_file and Path(bgm_file).is_file())
    voice_vol = float(getattr(options, "voice_volume", 1.0))
    bgm_vol = float(getattr(options, "bgm_volume", 0.18))
    use_autoduck = bool(getattr(options, "bgm_autoduck", True))
    use_loudnorm = bool(getattr(options, "audio_loudnorm", False))

    voice_chain = f"volume={voice_vol:.2f}"
    if use_loudnorm:
        voice_chain = f"loudnorm=I=-16:TP=-1.5:LRA=11,{voice_chain}"
    if getattr(options, "speed_shift", False):
        voice_chain = f"{voice_chain},atempo=1.03"

    if has_bgm:
        resolved_bgm = str(Path(bgm_file).resolve())
        fade_out_start = max(0.0, clip_duration - 1.5)
        bgm_chain = (
            f"volume={bgm_vol:.2f},"
            f"afade=t=in:st=0:d=1.0,"
            f"afade=t=out:st={fade_out_start:.2f}:d=1.5"
        )
        if use_autoduck:
            audio_filter_complex = (
                f"[0:a]{voice_chain},asplit=2[v_main][v_sc];"
                f"[1:a]{bgm_chain}[bgm_raw];"
                f"[bgm_raw][v_sc]sidechaincompress=threshold=0.03:ratio=6:attack=50:release=400[bgm_ducked];"
                f"[v_main][bgm_ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
        else:
            audio_filter_complex = (
                f"[0:a]{voice_chain}[v_main];"
                f"[1:a]{bgm_chain}[bgm_raw];"
                f"[v_main][bgm_raw]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
        full_filter_complex = f"[0:v]{video_filter}[vout];{audio_filter_complex}"
        base_cmd = (
            ffmpeg_command()
            + [
                "-y",
                "-ss", f"{clip.start:.3f}",
                "-to", f"{clip.end:.3f}",
                "-i", resolved_video,
                "-stream_loop", "-1",
                "-i", resolved_bgm,
                "-filter_complex", full_filter_complex,
                "-map", "[vout]",
                "-map", "[aout]",
            ]
        )
        cmd = base_cmd + enc_args + ["-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "clip.mp4"]
        fallback_cmd = (
            base_cmd
            + ["-c:v", "libx264", "-preset", "fast", "-crf", "21", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "clip.mp4"]
        )
    else:
        base_cmd = (
            ffmpeg_command()
            + [
                "-y",
                "-ss", f"{clip.start:.3f}",
                "-to", f"{clip.end:.3f}",
                "-i", resolved_video,
                "-vf", video_filter,
                "-af", voice_chain,
            ]
        )
        cmd = base_cmd + enc_args + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "clip.mp4"]
        fallback_cmd = (
            base_cmd
            + ["-c:v", "libx264", "-preset", "fast", "-crf", "21", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "clip.mp4"]
        )

    try:
        run_ffmpeg_with_progress(
            cmd,
            cwd=clip_dir,
            job_id=job_id,
            clip_duration=clip_duration,
            clip_index=clip_index,
            total_clips=total_clips,
            progress_start=progress_start,
            progress_end=progress_end,
            clip_title=clip.title,
        )
    except Exception as exc:
        if enc_args[1] != "libx264":
            logger.warning(f"Hardware encoder {enc_name} gagal ({exc}), otomatis beralih ke CPU libx264...")
            run_ffmpeg_with_progress(
                fallback_cmd,
                cwd=clip_dir,
                job_id=job_id,
                clip_duration=clip_duration,
                clip_index=clip_index,
                total_clips=total_clips,
                progress_start=progress_start,
                progress_end=progress_end,
                clip_title=clip.title,
            )
        else:
            raise
    clip.subtitle_url = f"/media/{job_dir.name}/{clip.id}/subtitle.srt"
    clip.video_url = f"/media/{job_dir.name}/{clip.id}/clip.mp4"


def media_duration(video_path: Path, fallback: float) -> float:
    try:
        import cv2
        capture = cv2.VideoCapture(str(video_path))
        frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = capture.get(cv2.CAP_PROP_FPS)
        capture.release()
        if frame_count > 0 and fps > 0:
            return frame_count / fps
    except Exception:
        pass
    return fallback


def render_profile(options: CreateJobRequest) -> dict[str, str]:
    return {
        "subtitle_style": options.subtitle_style,
        "subtitle_mode": getattr(options, "subtitle_mode", "active_highlight"),
        "subtitle_position": options.subtitle_position,
        "subtitle_color": options.subtitle_color,
        "subtitle_active_color": getattr(options, "subtitle_active_color", "#FFDD00"),
        "subtitle_font_size": str(options.subtitle_font_size),
        "subtitle_max_lines": str(options.subtitle_max_lines),
        "subtitle_x": f"{options.subtitle_x:.3f}",
        "subtitle_y": f"{options.subtitle_y:.3f}",
        "aspect_ratio": options.aspect_ratio,
        "framing": options.framing,
        "layout": options.layout,
        "facecam_crop": json.dumps(getattr(options, "facecam_crop", None)),
        "bgm_path": getattr(options, "bgm_path", ""),
        "bgm_volume": f"{getattr(options, 'bgm_volume', 0.18):.2f}",
        "voice_volume": f"{getattr(options, 'voice_volume', 1.0):.2f}",
        "bgm_autoduck": str(getattr(options, "bgm_autoduck", True)),
        "audio_loudnorm": str(getattr(options, "audio_loudnorm", False)),
        "censor_profanity": str(getattr(options, "censor_profanity", False)),
        "watermark_text": getattr(options, "watermark_text", ""),
        "watermark_image_path": getattr(options, "watermark_image_path", ""),
        "watermark_position": getattr(options, "watermark_position", "top_right"),
        "watermark_opacity": f"{getattr(options, 'watermark_opacity', 0.65):.2f}",
        "hook_banner_enabled": str(getattr(options, "hook_banner_enabled", False)),
        "hook_banner_text": getattr(options, "hook_banner_text", ""),
        "hook_banner_duration": str(getattr(options, "hook_banner_duration", 4)),
        "mirror_video": str(getattr(options, "mirror_video", False)),
        "speed_shift": str(getattr(options, "speed_shift", False)),
        "color_boost": str(getattr(options, "color_boost", False)),
    }


def render_selected_clips(
    job_id: str,
    video: Path,
    transcript: list[dict[str, Any]],
    clips: list[Clip],
    job_dir: Path,
    options: CreateJobRequest,
    progress_start: int,
    progress_end: int,
    skip_existing: bool = False,
) -> None:
    def rendered_file(clip: Clip) -> bool:
        clip_dir = clip_result_dir(job_dir, clip.id, clip.title)
        output = clip_dir / "clip.mp4"
        subtitle = clip_dir / "subtitle.srt"
        return output.is_file() and output.stat().st_size > 0 and subtitle.is_file()

    targets = [clip for clip in clips if not skip_existing or not rendered_file(clip)]
    if not targets:
        update_job(job_id, progress=progress_end, message="Semua clip sudah dirender; menyiapkan hasil akhir...")
        return

    face_crop = None
    total_clips = len(targets)
    for index, clip in enumerate(targets, start=1):
        sub_pct = int(((index - 1) / total_clips) * 100)
        curr_progress = progress_start + int(((index - 1) / total_clips) * (progress_end - progress_start))
        update_job(
            job_id,
            progress=curr_progress,
            sub_progress=sub_pct,
            message=f"Merender clip {index} dari {total_clips}...",
            sub_message=f"Menyiapkan render klip: Klip '{clip.title[:32]}'...",
        )
        render_clip(
            video,
            transcript,
            clip,
            job_dir,
            options,
            face_crop,
            job_id=job_id,
            clip_index=index,
            total_clips=total_clips,
            progress_start=progress_start,
            progress_end=progress_end,
        )

        done_sub_pct = int((index / total_clips) * 100)
        done_progress = progress_start + int((index / total_clips) * (progress_end - progress_start))
        update_job(
            job_id,
            progress=done_progress,
            sub_progress=done_sub_pct,
            message=f"Klip {index} dari {total_clips} selesai dirender",
            sub_message=f"Klip {index}/{total_clips} siap ({done_sub_pct}%)",
        )


def process_job(job_id: str, options: CreateJobRequest, source_path: str | None = None) -> None:
    try:
        from clipper_hud import launch_hud_process
        launch_hud_process()
    except Exception:
        pass
    job_dir = DATA_DIR / f".job-{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        if source_path:
            video = Path(source_path)
            if not video.is_file():
                raise RuntimeError("Video sumber tidak ditemukan di folder VideoMentah.")
            update_job(job_id, status="processing", progress=5, message="Menyiapkan video sumber...")
        else:
            update_job(job_id, status="processing", progress=5, message="Mengunduh video...")
            video = download_video(options.url, job_dir, options.quality, job_id)
        with JOBS_LOCK:
            job_title = JOBS[job_id].source_title
        if not job_title:
            job_title = Path(source_path or options.url).stem or "Video tanpa judul"
        final_dir = job_result_dir(job_id)
        if not JOBS[job_id].result_dir:
            if job_dir.exists() and any(job_dir.iterdir()):
                final_dir = create_result_dir(job_title, job_id)
                video_name = video.name
                for item in job_dir.iterdir():
                    shutil.move(str(item), str(final_dir / item.name))
                job_dir.rmdir()
                video = final_dir / video_name
            else:
                final_dir = create_result_dir(job_title, job_id)
            update_job(job_id, result_dir=str(final_dir), source_title=job_title)
            job_dir = final_dir
        else:
            job_dir = final_dir
        if source_path:
            job_dir.mkdir(parents=True, exist_ok=True)
        if job_id in CANCELED_JOBS:
            raise RuntimeError("Proses dibatalkan oleh pengguna.")
        update_job(job_id, progress=25, message="Mengambil audio untuk transkripsi...")
        audio = job_dir / "audio.wav"
        extract_audio(video, audio)
        if job_id in CANCELED_JOBS:
            raise RuntimeError("Proses dibatalkan oleh pengguna.")
        selected_audio_model = getattr(options, "whisper_model", MODEL_NAME)
        if selected_audio_model == "gemini":
            update_job(job_id, progress=38, message="Mentranskrip audio via Gemini API...")
        else:
            update_job(job_id, progress=38, message=f"Transkripsi dengan Whisper {selected_audio_model}...")
        transcript = transcribe(audio, options.language, selected_audio_model, job_id=job_id)
        if job_id in CANCELED_JOBS:
            raise RuntimeError("Proses dibatalkan oleh pengguna.")
        update_job(
            job_id,
            source_url=f"/raw/{video.parent.name}/{video.name}" if source_path else f"/media/{job_dir.name}/{video.name}",
            source_path=str(video),
            transcript=transcript,
            duration=media_duration(video, transcript[-1]["end"]),
            progress=62,
            message="Mencari momen terbaik...",
        )
        energy_map = compute_audio_energy_map(audio) if getattr(options, "use_audio_energy", True) else None
        flavor = getattr(options, "clip_flavor", "spicy_drama")

        if options.clip_mode == "smart" and options.clip_profile == "manual":
            selected = []
        elif options.clip_mode == "smart":
            smart_min = options.smart_fixed_duration if options.smart_duration_mode == "fixed" else options.min_duration
            smart_max = options.smart_fixed_duration if options.smart_duration_mode == "fixed" else options.max_duration
            selected = None
            if options.local_model == "gemini" or get_active_gemini_api_key():
                selected = ask_gemini(
                    transcript,
                    options.clip_count,
                    smart_min,
                    smart_max,
                    options.max_clips,
                    options.clip_profile,
                    options.custom_prompt,
                    flavor=flavor,
                    energy_map=energy_map,
                )
            if not selected and options.use_local_llm:
                selected = ask_local_gguf(
                    transcript,
                    options.clip_count,
                    smart_min,
                    smart_max,
                    options.local_model,
                    options.max_clips,
                    options.clip_profile,
                    options.custom_prompt,
                    flavor=flavor,
                    energy_map=energy_map,
                )
                if not selected:
                    selected = ask_ollama(
                        transcript,
                        options.clip_count,
                        smart_min,
                        smart_max,
                        options.max_clips,
                        options.clip_profile,
                        options.custom_prompt,
                    )
            if not selected:
                selected = heuristic_clips(
                    transcript,
                    options.clip_count,
                    smart_min,
                    smart_max,
                    options.max_clips,
                    options.clip_profile,
                    flavor=flavor,
                    energy_map=energy_map,
                )
        else:
            selected = split_transcript(
                transcript,
                options.clip_mode,
                options.split_count,
                options.segment_duration,
                media_duration(video, transcript[-1]["end"]),
            )
        if not selected and options.clip_profile != "manual":
            raise RuntimeError("Tidak menemukan kandidat clip. Coba durasi yang lebih pendek.")
        if options.clip_mode == "smart" and selected:
            smart_min = options.smart_fixed_duration if options.smart_duration_mode == "fixed" else options.min_duration
            smart_max = options.smart_fixed_duration if options.smart_duration_mode == "fixed" else options.max_duration
            selected = broaden_smart_clips(
                transcript,
                selected,
                smart_min,
                smart_max,
                flavor=flavor,
                snap_bounds=getattr(options, "snap_sentence_bounds", True),
                trim_filler=getattr(options, "trim_opening_filler", False),
            )
        clips = []
        for index, item in enumerate(selected, start=1):
            h_title = str(item.get("hook_title") or item.get("title") or "").strip()
            clip = Clip(
                id=f"clip-{index:02}",
                start=float(item["start"]),
                end=float(item["end"]),
                score=float(item.get("score", 88.0)),
                title=h_title,
                source="ai",
                core_topic=str(item.get("core_topic") or ""),
                hook_title=h_title,
            )
            clips.append(clip)
        update_job(
            job_id,
            progress=62,
            sub_progress=40,
            message="Mencari momen terbaik dengan AI...",
            sub_message=f"Model {options.local_model.upper()} menganalisis transkrip ({flavor})...",
        )
        update_job(
            job_id,
            clips=clips,
            progress=68,
            sub_progress=75,
            message="Membuat metadata (Judul, Caption, Hashtag)...",
            sub_message="AI mengoptimalkan hook dan copywriting klip...",
        )
        generate_clip_metadata(
            transcript,
            clips,
            options.local_model,
            flavor=flavor,
            spicy_hook=getattr(options, "spicy_headline_hook", True),
        )
        update_job(job_id, progress=69, message="Merender clip AI sebelum review...")
        render_selected_clips(
            job_id,
            video,
            transcript,
            clips,
            job_dir,
            options,
            progress_start=69,
            progress_end=70,
        )
        update_job(
            job_id,
            clips=clips,
            render_profile=render_profile(options),
            status="awaiting_render",
            progress=70,
            message="Clip AI siap. Tonton video penuh atau tambahkan clip manual sebelum render final.",
        )
    except Exception as exc:
        update_job(job_id, status="failed", progress=100, message="Proses gagal", error=str(exc))


def render_job(job_id: str, options: CreateJobRequest) -> None:
    try:
        from clipper_hud import launch_hud_process
        launch_hud_process()
    except Exception:
        pass
    try:
        with JOBS_LOCK:
            job = JOBS[job_id]
            clips = job.clips
            transcript = job.transcript
            previous_profile = job.render_profile
        job_dir = job_result_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        video = Path(job.source_path) if job.source_path else job_dir / "source.mp4"
        if not video.exists():
            candidates = [p for p in job_dir.glob("source.*") if p.suffix.lower() not in {".part", ".ytdl"}]
            if not candidates:
                raise RuntimeError("Video sumber tidak ditemukan untuk proses render.")
            video = max(candidates, key=lambda p: p.stat().st_size)
        update_job(job_id, status="processing", progress=70, message="Membuat clip final...")
        same_profile = previous_profile == render_profile(options)
        render_selected_clips(
            job_id,
            video,
            transcript,
            clips,
            job_dir,
            options,
            progress_start=70,
            progress_end=95,
            skip_existing=same_profile,
        )
        update_job(job_id, render_profile=render_profile(options), status="completed", progress=100, message="Selesai")
    except Exception as exc:
        update_job(job_id, status="failed", progress=100, message="Proses gagal", error=str(exc))


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.post("/api/jobs")
def create_job(options: CreateJobRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    job_id = uuid.uuid4().hex[:12]
    job = Job(id=job_id, url=options.url)
    with JOBS_LOCK:
        JOBS[job_id] = job
        JOB_OPTIONS[job_id] = options
    background_tasks.add_task(process_job, job_id, options)
    return {"id": job_id}


@app.post("/api/jobs/{job_id}/render")
def render_job_endpoint(job_id: str, render_options: RenderRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        original_options = JOB_OPTIONS.get(job_id)
        if not job or not original_options:
            raise HTTPException(status_code=404, detail="Job tidak ditemukan")
        if job.status != "awaiting_render":
            raise HTTPException(status_code=409, detail="Job belum siap untuk dirender")
        options = original_options.model_copy(update=render_options.model_dump())
        JOB_OPTIONS[job_id] = options
    background_tasks.add_task(render_job, job_id, options)
    return {"id": job_id}


@app.post("/api/jobs/{job_id}/manual-clips")
def add_manual_clip(job_id: str, manual: ManualClipRequest) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job tidak ditemukan")
        if job.status != "awaiting_render":
            raise HTTPException(status_code=409, detail="Clip manual hanya dapat ditambahkan pada tahap review")
        duration = job.duration or (job.transcript[-1]["end"] if job.transcript else 0)
        if manual.end <= manual.start:
            raise HTTPException(status_code=422, detail="Waktu selesai harus lebih besar dari waktu mulai")
        if duration and manual.end > duration + 0.5:
            raise HTTPException(
                status_code=422, detail=f"Waktu selesai melebihi durasi video ({format_time_for_error(duration)})"
            )
        overlaps = any(manual.start < clip.end and manual.end > clip.start for clip in job.clips)
        if overlaps:
            raise HTTPException(status_code=409, detail="Waktu clip manual bertumpang tindih dengan clip yang sudah ada")
        clip = Clip(
            id=f"manual-{sum(1 for item in job.clips if item.source == 'manual') + 1:02}",
            start=manual.start,
            end=manual.end,
            score=0.0,
            title=manual.title,
            source="manual",
        )
        job.clips.append(clip)
        transcript = list(job.transcript)
        options = JOB_OPTIONS[job_id]
    generate_clip_metadata(transcript, [clip], options.local_model)
    with JOBS_LOCK:
        return job_snapshot(JOBS[job_id])


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job tidak ditemukan")
        return job_snapshot(job)


# ==============================================================================
# NATIVE SMART Q&A TURN SEGMENTATION & FULL CONTEXT AUTO-HEAL ENGINE
# ==============================================================================
EXPLANATION_CONTINUATIONS = {
    "karena", "sebab", "jadi", "terus", "lalu", "kemudian", "nah", "pertama",
    "kedua", "ketiga", "contohnya", "misalnya", "artinya", "makanya", "padahal",
    "tetapi", "tapi", "namun", "sedangkan", "sementara", "bahkan", "apalagi",
    "selain", "untuk", "supaya", "agar", "ketika", "saat", "waktu", "kalau", "jika",
    "sampai", "hingga", "akhirnya", "intinya", "kesimpulannya", "singkatnya",
}

DEFAULT_VIRAL_TOPICS_ID = [
    "uang", "gaji", "investasi", "bisnis", "kaya", "hutang", "miliar", "saham", "crypto",
    "nikah", "selingkuh", "rumah tangga", "mental health", "quarter life crisis", "karir",
    "politik", "pejabat", "korupsi", "pajak", "aturan baru", "viral", "kasus", "fakta",
    "rahasia", "pengalaman", "horor", "mistis", "kesehatan", "dokter", "artis", "komika",
]

_WS_CACHED_TRENDS: list[str] = []
_WS_LAST_TREND_FETCH: float = 0.0


def fetch_current_viral_trends_ws() -> list[str]:
    global _WS_CACHED_TRENDS, _WS_LAST_TREND_FETCH
    now = time.time()
    if _WS_CACHED_TRENDS and (now - _WS_LAST_TREND_FETCH) < 3600:
        return _WS_CACHED_TRENDS

    trends: list[str] = []
    # 1. Google Trends RSS Indonesia
    try:
        import xml.etree.ElementTree as ET
        req = urlrequest.Request(
            "https://trends.google.com/trending/rss?geo=ID",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urlrequest.urlopen(req, timeout=4) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        for item in root.findall(".//item/title"):
            if item.text and item.text.strip():
                trends.append(item.text.strip().lower())
    except Exception:
        pass

    # 2. Twitter / X Trends Indonesia (via Trends24)
    try:
        req_tw = urlrequest.Request(
            "https://trends24.in/indonesia/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urlrequest.urlopen(req_tw, timeout=4) as resp_tw:
            html = resp_tw.read().decode("utf-8", errors="ignore")
        t_trends = re.findall(r'<a[^>]+href="[^"]*twitter\.com/search\?q=[^"]*"[^>]*>([^<]+)</a>', html)
        if not t_trends:
            t_trends = re.findall(r'class="trend-name"[^>]*>.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
        for t in t_trends:
            cleaned = re.sub(r"^[#@]", "", t).strip().lower()
            if len(cleaned) > 2 and cleaned not in trends:
                trends.append(cleaned)
    except Exception:
        pass

    merged = list(dict.fromkeys(trends[:25] + DEFAULT_VIRAL_TOPICS_ID))
    _WS_CACHED_TRENDS = merged
    _WS_LAST_TREND_FETCH = now
    return merged


def get_trend_hijacker_queries(limit: int = 15) -> list[str]:
    """
    Menghasilkan query pencarian YouTube yang memadukan trending topik Google + Twitter Indonesia
    dengan nama-nama kreator/podcast viral untuk mendapatkan first-mover advantage.
    """
    trends = fetch_current_viral_trends_ws()
    top_shows = [
        "curhat bang denny sumargo",
        "close the door deddy corbuzier",
        "pwk podcast",
        "total politik",
        "vindes podcast",
        "kasisolusi",
    ]
    hijacker_queries: list[str] = []
    for t in trends[:12]:
        if len(t) <= 2:
            continue
        hijacker_queries.append(f"podcast {t} terbaru")
        show = random.choice(top_shows)
        hijacker_queries.append(f"{show} {t}")
    return list(dict.fromkeys(hijacker_queries))[:limit]


_TOPIC_SUBSTANTIVE_TRIGGERS = {
    "rahasia", "fakta", "alasan", "sebenarnya", "sebenernya", "penasaran", "kenapa", "mengapa",
    "bagaimana", "gimana", "ternyata", "misteri", "terbongkar", "bocoran", "isu", "jawaban",
    "ribut", "konflik", "masalah", "kecewa", "marah", "nangis", "hancur", "drop", "down",
    "trauma", "kacau", "takut", "ancaman", "gagal", "rugi", "sakit", "drama", "aib",
    "bohong", "dikhianati", "putus", "stres", "parah", "nyesel", "menyesal",
    "uang", "duit", "omset", "omzet", "gaji", "honor", "bisnis", "modal", "untung", "kaya",
    "miskin", "investasi", "saham", "crypto", "kripto", "karier", "kantor", "kerja",
    "bayaran", "rupiah", "juta", "miliar", "proyek", "kontrak", "harga",
    "pengalaman", "kejadian", "ceritanya", "cerita", "perjalanan", "sejarah",
    "momen", "kejadiannya", "pertama", "menurut", "setuju", "salah", "benar", "bener",
    "prinsip", "bodoh", "bahaya", "penting", "aturan", "kesalahan", "keanehan", "kebenaran", "kritik", "hukum",
}

_GREETING_INDICATORS = (
    "halo", "hai", "hello", "hi", "hey", "assalamualaikum", "selamat pagi", "selamat siang",
    "selamat malam", "selamat datang", "apa kabar", "gimana kabar", "kabar baik", "sehat bro",
)


def is_question_or_statement_starter(text: str, gap_from_prev: float = 1.0) -> bool:
    """
    Mendeteksi apakah sebuah kalimat adalah PERTANYAAN PEMBUKA TOPIK BARU yang sah.
    Kalimat yang diawali kata sambung tengah cerita (seperti 'Kalau tau kan...', 'Karena...', 'Jadi...')
    ditolak agar tidak pernah memotong penjelasan narasumber di tengah jalan.
    """
    clean = text.strip().lower()
    toks = words(clean)
    if len(toks) < 6:
        return False

    if is_intro_or_outro_text(clean):
        return False
    if any(clean.startswith(g) or f" {g} " in f" {clean} " for g in _GREETING_INDICATORS if len(words(g)) >= 2):
        return False
    if toks[0] in ("halo", "hai", "hello", "hi", "hey", "assalamualaikum"):
        return False

    # DILARANG menganggap kalimat lanjutan/penjelasan tengah cerita sebagai pertanyaan baru
    if any(clean.startswith(prefix + " ") or clean == prefix for prefix in BAD_CLIP_START_WORDS):
        return False

    STARTER_PHRASES = (
        "menurut lu", "menurut kamu", "menurut anda", "menurut mas", "menurut bang", "menurut pak", "menurut bu",
        "ceritain dong", "ceritain waktu", "ceritain pas", "bener gak sih", "benar nggak sih",
        "emang bener", "gimana ceritanya", "gimana rasanya", "gimana waktu", "gimana awal",
        "awal mulanya", "awal mulanya gimana", "gua mau tanya", "aku mau tanya", "saya mau tanya",
        "mau nanya", "banyak yang tanya", "orang penasaran", "apa yang bikin",
        "kenapa waktu itu", "kok bisa sampe", "kok bisa gitu", "kok bisa sih",
        "waktu pertama kali", "momen paling", "hal paling",
        "pernah gak sih", "pernah nggak sih", "pernah terpikir", "pernah ngerasa",
        "alasan kamu", "alasan lo", "alasannya apa", "ada apa sih", "ada apa sebenarnya",
    )
    if any(p in clean for p in STARTER_PHRASES):
        return True

    has_q_mark = "?" in clean
    has_q_trigger = bool(set(toks[:3]) & QUESTION_TRIGGERS)
    if has_q_mark or has_q_trigger:
        first_tok = toks[0] if toks else ""
        if first_tok in ("iya", "ya", "kan", "oh", "nah", "terus", "oke") and len(toks) < 8:
            return False
        if any(w in _TOPIC_SUBSTANTIVE_TRIGGERS for w in toks):
            return True

    return False


def is_incomplete_explanation(text: str, gap_to_next: float) -> bool:
    clean = text.strip()
    if not clean:
        return False
    toks = words(clean)
    if not toks:
        return False
    if toks[-1] in EXPLANATION_CONTINUATIONS or clean.endswith((",", "-", "...", ":")):
        return True
    if not re.search(r"[.!?]$", clean) and gap_to_next < 0.90:
        return True
    if gap_to_next < 0.60 and len(toks) >= 3:
        return True
    return False


def segment_podcast_into_qa_turns(
    transcript: list[dict[str, Any]],
    energy_map: list[float] | None = None,
    min_dur: float = 45.0,
    max_dur: float = 135.0,
) -> list[dict[str, Any]]:
    total_duration = float(transcript[-1]["end"]) if transcript else 0.0
    skip_seconds = get_podcast_intro_skip_seconds(total_duration)

    sentence_segs = condense_transcript_for_llm(transcript, energy_map)
    if not sentence_segs:
        return []

    turns: list[dict[str, Any]] = []
    n = len(sentence_segs)
    i = 0

    while i < n:
        while i < n:
            seg = sentence_segs[i]
            seg_s = float(seg["start"])
            seg_t = str(seg.get("text", "")).strip()
            if seg_s < skip_seconds and not is_intro_teaser_highlight(seg, skip_seconds):
                i += 1
                continue
            if is_intro_or_outro_text(seg_t):
                i += 1
                continue
            if is_question_or_statement_starter(seg_t):
                break
            i += 1

        if i >= n:
            break

        start_i = i
        if start_i > 0:
            prev_seg = sentence_segs[start_i - 1]
            prev_text = str(prev_seg.get("text", "")).strip().lower()
            prev_gap = float(sentence_segs[start_i]["start"]) - float(prev_seg["end"])
            prev_s = float(prev_seg["start"])
            if (
                prev_gap < 0.60
                and len(words(prev_text)) <= 3
                and (prev_s >= skip_seconds or is_intro_teaser_highlight(prev_seg, skip_seconds))
                and not is_intro_or_outro_text(prev_text)
                and prev_text.startswith(("nah,", "nah ", "kan,", "eh,", "eh ", "bro,", "bang,", "mas,", "pak,", "bu,", "kak,", "mbak,"))
            ):
                start_i -= 1

        start_sec = float(sentence_segs[start_i]["start"])
        end_i = i

        while end_i + 1 < n:
            curr_seg = sentence_segs[end_i]
            next_seg = sentence_segs[end_i + 1]
            curr_end = float(curr_seg["end"])
            next_start = float(next_seg["start"])
            curr_dur = curr_end - start_sec
            gap = next_start - curr_end
            curr_text = str(curr_seg.get("text", "")).strip()
            next_text = str(next_seg.get("text", "")).strip()

            if (float(next_seg["end"]) - start_sec) > max_dur:
                break

            if curr_dur >= min_dur:
                if (
                    is_question_or_statement_starter(next_text, gap_from_prev=gap)
                    and gap >= 0.65
                    and re.search(r"[.!?]$", curr_text)
                    and not is_incomplete_explanation(curr_text, gap)
                ):
                    break
                if (
                    curr_dur >= max(min_dur, 55.0)
                    and not is_incomplete_explanation(curr_text, gap)
                    and gap >= 1.25
                    and re.search(r"[.!?]$", curr_text)
                ):
                    break

            end_i += 1

        end_sec = float(sentence_segs[end_i]["end"])
        dur = end_sec - start_sec

        if dur >= max(40.0, min_dur * 0.85):
            turn_segs = sentence_segs[start_i : end_i + 1]
            full_text = " ".join(str(x.get("text", "")) for x in turn_segs).strip()
            opener_text = str(sentence_segs[i].get("text", "")).strip()
            turns.append({
                "start": round(start_sec, 2),
                "end": round(end_sec, 2),
                "duration": round(dur, 2),
                "has_question": True,
                "opener": opener_text,
                "text": full_text,
                "energy": get_window_energy_score(energy_map, start_sec, end_sec) if energy_map else 0.5,
            })

        i = end_i + 1

    return turns


def build_clipper_llm_prompt(
    condensed_transcript: list[dict[str, Any]],
    count: int,
    minimum: int,
    maximum: int,
    max_clips: int,
    profile: str = "auto",
    flavor: str = "spicy_drama",
    custom_prompt: str = "",
) -> tuple[str, int, int]:
    flavor_cfg = CLIP_FLAVOR_PROFILES.get(flavor, CLIP_FLAVOR_PROFILES["spicy_drama"])
    eff_min = max(45, minimum if minimum > 0 else 45)
    eff_max = maximum if maximum > 0 else 120
    viral_trends = fetch_current_viral_trends_ws()
    trend_str = ", ".join(viral_trends[:16])

    rlsf_injection = ""
    try:
        from rlsf_engine import get_rlsf_prompt_injection
        rlsf_injection = get_rlsf_prompt_injection()
    except Exception:
        pass

    prompt = (
        "Kamu adalah Produser & Head Clipper Podcast Viral Indonesia untuk TikTok, Instagram Reels, dan YouTube Shorts.\n"
        f"{flavor_cfg['prompt_rule']}\n"
        f"REFERENSI TREN VIRAL SEKARANG: [{trend_str}].\n"
        f"{rlsf_injection}\n"
        "ATURAN MUTLAK PEMOTONGAN SIKLUS TANYA-JAWAB UTUH (ANTI-MENGGANTUNG & ANTI-KEPENDEKAN):\n"
        "1. DETIK MULAI (start): WAJIB dimulai tepat dari kalimat PERTANYAAN HOST atau PERNYATAAN PEMBUKA TOPIK sebelum narasumber menjawab!\n"
        "   - DILARANG KERAS memulai klip dari tengah-tengah penjelasan narasumber (seperti kalimat yang diawali 'Kalau...', 'Karena...', 'Jadi...', 'Terus...', 'Tapi...', 'Ususnya...').\n"
        "2. DETIK SELESAI (end): WAJIB menunggu sampai seluruh penjelasan, cerita, dan kesimpulan narasumber TUNTAS 100%.\n"
        f"3. DURASI PENUH: Minimal {eff_min} detik dan idealnya 55 sampai {eff_max} detik per klip. Jangan membuat klip pendek di bawah {eff_min} detik!\n"
        "4. HOOK TITLE (hook_title): Buat Headline Rangkuman Topik 4-7 kata dalam Title Case yang merangkum inti bahasan secara jelas (Contoh benar: 'Hukum & Bahaya Makan Usus Ayam', DILARANG menyalin kalimat mentah pembicara seperti 'Kalau Tau Kan, Barang Segera Gini. Ususnya').\n\n"
        "FORMAT OUTPUT:\n"
        "Balas HANYA JSON array valid tanpa markdown berisi objek:\n"
        '[{"start": float, "end": float, "score": int, "hook_title": "Judul Topik Utuh 4-7 Kata", "core_topic": "Ringkasan 1 kalimat", "title": "Judul Topik Utuh 4-7 Kata"}]\n\n'
        f"Pilih {'sebanyak mungkin, maksimal ' + str(max_clips) if count == 0 else str(count)} segmen non-overlap terbaik.\n"
        + (f"Instruksi tambahan: {custom_prompt}\n" if custom_prompt.strip() else "")
        + "\nTRANSKRIP:\n"
        + json.dumps(condensed_transcript, ensure_ascii=False)
    )
    return prompt, eff_min, eff_max


def heuristic_clips(
    transcript: list[dict[str, Any]],
    count: int,
    minimum: int,
    maximum: int,
    max_clips: int,
    profile: str = "auto",
    flavor: str = "spicy_drama",
    energy_map: list[float] | None = None,
) -> list[dict[str, Any]]:
    if not transcript:
        return []
    total_duration = float(transcript[-1]["end"])
    skip_seconds = get_podcast_intro_skip_seconds(total_duration)

    flavor_cfg = CLIP_FLAVOR_PROFILES.get(flavor, CLIP_FLAVOR_PROFILES["spicy_drama"])
    keywords = set(flavor_cfg["keywords"]) | QUESTION_TRIGGERS
    trend_tokens = set()
    for t_phrase in fetch_current_viral_trends_ws():
        trend_tokens.update(words(t_phrase))

    energy_weight = float(flavor_cfg["energy_weight"])
    eff_min = max(45, minimum if minimum > 0 else 45)
    eff_max = min(150, maximum if maximum > 0 else 125)

    qa_turns = segment_podcast_into_qa_turns(transcript, energy_map, min_dur=eff_min, max_dur=eff_max)
    if not qa_turns:
        return []

    scored_turns: list[dict[str, Any]] = []
    for turn in qa_turns:
        t_start = float(turn["start"])
        if t_start < skip_seconds and not is_intro_teaser_highlight(turn, skip_seconds):
            continue

        opener = turn.get("opener") or ""
        clean_opener = re.sub(r"\s+", " ", opener).strip()
        if is_intro_or_outro_text(clean_opener):
            continue

        text = turn["text"]
        dur = turn["duration"]
        tok_list = words(text)
        if len(tok_list) < 25:
            continue

        wps = len(tok_list) / max(dur, 1.0)
        raw_score = wps * 8.0
        if turn["has_question"]:
            raw_score += 25.0
        raw_score += sum(6.0 for tok in tok_list if tok in keywords)
        raw_score += sum(9.0 for tok in set(tok_list) if tok in trend_tokens)
        raw_score += text.count("?") * 5.0 + text.count("!") * 4.0
        raw_score += (float(turn.get("energy", 0.5)) * 28.0) * energy_weight

        viral_score = min(99.0, max(72.0, round(raw_score, 1)))
        title, _, _ = fallback_metadata(text, "")

        scored_turns.append({
            "start": turn["start"],
            "end": turn["end"],
            "score": viral_score,
            "title": title,
            "hook_title": title,
            "core_topic": title,
            "text": text,
            "is_ai_selected": False,
        })

    scored_turns.sort(key=lambda item: item["score"], reverse=True)
    target = count if count > 0 else max(max_clips, 8)
    return scored_turns[:target]


def broaden_smart_clips(
    transcript: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    minimum: int,
    maximum: int,
    flavor: str = "spicy_drama",
    snap_bounds: bool = True,
    trim_filler: bool = False,
) -> list[dict[str, Any]]:
    """
    Mengunci setiap klip dari awal pertanyaan/topik hingga akhir jawaban tuntas.
    Mencegah awal klip terpotong di tengah kalimat atau dimulai dari kata sambung,
    serta mencegah klip kependekan dengan memperluas hingga akhir kalimat utuh (.!?).
    """
    if not transcript or not selected:
        return selected

    total_duration = float(transcript[-1]["end"])
    eff_min = max(45.0, float(minimum if minimum > 0 else 45.0))
    eff_max = float(maximum if maximum > 0 else 120.0)
    hard_max = max(eff_max + 30.0, 140.0)

    sentence_segs = condense_transcript_for_llm(transcript)
    if not sentence_segs:
        return selected

    by_score = sorted(selected, key=lambda x: float(x.get("score", 85.0)), reverse=True)
    accepted_intervals: list[dict[str, Any]] = []

    for item in by_score:
        raw_start = max(0.0, float(item["start"]))
        raw_end = min(total_duration, float(item["end"]))

        mid_pt = (raw_start + raw_end) / 2.0
        if any(
            (acc["start"] - 3.0) <= mid_pt <= (acc["end"] + 3.0)
            or (min(raw_end, acc["end"]) - max(raw_start, acc["start"])) > 8.0
            for acc in accepted_intervals
        ):
            continue

        # Batas mundur tidak boleh menabrak akhir klip sebelumnya
        lookback_limit = max(0.0, raw_start - 25.0)
        for acc in accepted_intervals:
            if acc["end"] <= raw_start:
                lookback_limit = max(lookback_limit, acc["end"] + 0.5)

        forward_limit = total_duration
        for acc in accepted_intervals:
            if acc["start"] >= raw_start + 10.0:
                forward_limit = min(forward_limit, acc["start"] - 0.5)

        # Temukan segmen terdekat dengan raw_start
        start_idx = 0
        for s_i, seg in enumerate(sentence_segs):
            if float(seg["end"]) >= raw_start:
                start_idx = s_i
                break

        # =====================================================================
        # 1. AUTO-HEAL AWAL KLIP YANG MENGAMBANG
        # =====================================================================
        # Selama segmen di start_idx diawali kata sambung terlarang,
        # ATAU kalimat sebelumnya adalah pertanyaan, ATAU jeda dari kalimat
        # sebelumnya sangat rapat (< 0.75s), tarik mundur start_idx -= 1
        # (maksimal mundur hingga 25 detik).
        while start_idx > 0:
            curr_seg = sentence_segs[start_idx]
            prev_seg = sentence_segs[start_idx - 1]
            prev_s = float(prev_seg["start"])
            if prev_s < lookback_limit:
                break
            if (raw_start - prev_s) > 25.0:
                break

            curr_t = str(curr_seg.get("text", "")).strip().lower()
            prev_t = str(prev_seg.get("text", "")).strip().lower()
            gap_prev = float(curr_seg["start"]) - float(prev_seg["end"])

            # Cek apakah segmen saat ini diawali kata sambung terlarang
            starts_bad = any(
                curr_t == bw or curr_t.startswith(bw + " ") or curr_t.startswith(bw + ",")
                for bw in BAD_CLIP_START_WORDS
            )

            # Cek apakah kalimat sebelumnya adalah pertanyaan
            prev_is_q = (
                "?" in prev_t
                or any(qw in prev_t for qw in ("kenapa", "gimana", "apa", "siapa", "berapa", "kapan", "ceritain", "menurut", "bagaimana"))
            )

            # Cek apakah jeda sangat rapat
            tight_gap = (gap_prev < 0.75)

            if starts_bad or prev_is_q or tight_gap:
                start_idx -= 1
                if prev_is_q and not any(prev_t.startswith(bw + " ") for bw in BAD_CLIP_START_WORDS):
                    break
            else:
                break

        best_start = float(sentence_segs[start_idx]["start"])

        # =====================================================================
        # 2. AUTO-HEAL KLIP KEPENDEKAN / MENGGANTUNG
        # =====================================================================
        end_idx = start_idx
        for s_i in range(start_idx, len(sentence_segs)):
            if float(sentence_segs[s_i]["end"]) >= raw_end:
                end_idx = s_i
                break
        else:
            end_idx = len(sentence_segs) - 1

        while end_idx < len(sentence_segs):
            seg = sentence_segs[end_idx]
            seg_e = float(seg["end"])
            dur = seg_e - best_start
            seg_text = str(seg.get("text", "")).strip()

            if seg_e > forward_limit or dur > hard_max:
                break

            gap_next = 0.0
            if end_idx + 1 < len(sentence_segs):
                gap_next = float(sentence_segs[end_idx + 1]["start"]) - seg_e

            # Jika masih kurang dari durasi minimal, atau penjelasan masih menggantung
            if dur < eff_min or is_incomplete_explanation(seg_text, gap_next):
                if end_idx + 1 < len(sentence_segs):
                    next_seg = sentence_segs[end_idx + 1]
                    next_s = float(next_seg["start"])
                    if next_s > forward_limit or (next_s - best_start) > hard_max:
                        break
                    end_idx += 1
                    continue
                else:
                    break

            # Jika sudah melebihi durasi minimal dan diakhiri tanda baca kalimat selesai (.!?)
            if dur >= eff_min and re.search(r"[.!?]$", seg_text):
                if end_idx + 1 < len(sentence_segs):
                    next_seg = sentence_segs[end_idx + 1]
                    gap_next = float(next_seg["start"]) - seg_e
                    next_text = str(next_seg.get("text", "")).strip()
                    if is_question_or_statement_starter(next_text) and gap_next >= 0.40:
                        break
                    if gap_next >= 0.70:
                        break
                    if dur < min(eff_max, 95.0) and gap_next < 0.60:
                        end_idx += 1
                        continue
                break
            elif end_idx + 1 < len(sentence_segs):
                end_idx += 1
            else:
                break

        best_end = min(forward_limit, float(sentence_segs[end_idx]["end"]))
        final_start = max(0.0, lookback_limit, round(best_start, 3))
        final_end = min(total_duration, forward_limit, round(best_end, 3))

        has_overlap = any(
            final_start < (acc["end"] - 1.0) and final_end > (acc["start"] + 1.0)
            for acc in accepted_intervals
        )
        if not has_overlap and (final_end - final_start) >= 20.0:
            updated = dict(item)
            updated["start"] = final_start
            updated["end"] = final_end
            updated["score"] = float(item.get("score") or 90.0)
            accepted_intervals.append(updated)

    accepted_intervals.sort(key=lambda x: x["start"])
    return accepted_intervals


# --- ANTIGRAVITY PODCAST PRO ENGINE AUTO-HOOK DISABLED ---
pass

