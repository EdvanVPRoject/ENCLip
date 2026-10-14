from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import logging
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
except ImportError:  # optional when variables are configured directly
    load_dotenv = None  # type: ignore[assignment]


if getattr(sys, "frozen", False):
    # PyInstaller menyimpan executable di dist/VanClipper, sedangkan
    # resource read-only (misalnya web) berada di bundle internal.
    ROOT = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", ROOT)).resolve()
else:
    ROOT = Path(__file__).parent.parent / "Core_Data"
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
DATA_DIR.mkdir(exist_ok=True)
RAW_VIDEO_DIR.mkdir(exist_ok=True)
MODEL_DIR.mkdir(exist_ok=True)

if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
QWEN_GGUF_PATH = os.getenv("QWEN_GGUF_PATH", "")
HERMES_GGUF_PATH = os.getenv("HERMES_GGUF_PATH", "")
GGUF_N_CTX = int(os.getenv("GGUF_N_CTX", "8192"))
GGUF_N_GPU_LAYERS = int(os.getenv("GGUF_N_GPU_LAYERS", "-1"))

app = FastAPI(title="VanClipper", version="0.1.0")
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
    aspect_ratio: str = Field(default="9:16", pattern="^(16:9|9:16|4:3|1:1)$")
    framing: str = Field(default="fit", pattern="^(fit|crop)$")
    layout: str = Field(default="standard", pattern="^(standard|facecam_top|podcast_split)$")
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
    hook_banner_enabled: bool = Field(default=False)
    hook_banner_text: str = Field(default="", max_length=120)
    hook_banner_duration: int = Field(default=4, ge=0, le=300)
    facecam_crop: list[float] | None = None
    mirror_video: bool = Field(default=False)
    speed_shift: bool = Field(default=False)
    color_boost: bool = Field(default=False)


class RenderRequest(BaseModel):
    subtitle_style: str = Field(default="bold", pattern="^(classic|bold|highlight|minimal|neon|karaoke|box|none)$")
    aspect_ratio: str = Field(default="9:16", pattern="^(16:9|9:16|4:3|1:1)$")
    framing: str = Field(default="fit", pattern="^(fit|crop)$")
    layout: str = Field(default="standard", pattern="^(standard|facecam_top|podcast_split)$")
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
    hook_banner_enabled: bool = Field(default=False)
    hook_banner_text: str = Field(default="", max_length=120)
    hook_banner_duration: int = Field(default=4, ge=0, le=300)
    facecam_crop: list[float] | None = None
    mirror_video: bool = Field(default=False)
    speed_shift: bool = Field(default=False)
    color_boost: bool = Field(default=False)


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


def job_snapshot(job: Job) -> dict[str, Any]:
    value = asdict(job)
    value["clips"] = [asdict(clip) for clip in job.clips]
    return value


def safe_folder_name(value: str) -> str:
    """Make a readable Windows-safe folder name for a video title."""
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = text[:120].rstrip(" .") or "Video tanpa judul"
    if text.upper().split(".", 1)[0] in {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2", "LPT3"}:
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
    # Compatibility fallback for jobs created by older versions.
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
        raise RuntimeError(
            "yt-dlp belum terpasang. Jalankan: python -m pip install yt-dlp"
        ) from exc
    return [sys.executable, "-m", "yt_dlp"]


def ffmpeg_command() -> list[str]:
    if command_exists("ffmpeg"):
        return ["ffmpeg"]
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return [get_ffmpeg_exe()]
    except ImportError as exc:
        raise RuntimeError(
            "ffmpeg belum terpasang. Jalankan: python -m pip install imageio-ffmpeg"
        ) from exc


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
                # For fragmented media, yt-dlp improves total_bytes_estimate as
                # more fragments are discovered. Show that live estimate.
                display_total = total or fixed_total
                percentage = min(100, (downloaded / display_total * 100)) if display_total else 0
                speed = format_bytes(info.get("speed")) + "/s" if info.get("speed") else "menunggu..."
                has_estimate = any(item.get("estimated", 0) for item in download_stats.values()) or (not total and fixed_total_is_estimate)
                total_text = ("~" if has_estimate else "") + format_bytes(display_total) if display_total else "menghitung total"
                if status == "downloading":
                    update_job(
                        job_id,
                        progress=min(24, 5 + int(percentage * 0.19)),
                        sub_progress=int(percentage),
                        message="Mengunduh video sumber...",
                        sub_message=f"Download: {format_bytes(downloaded)} dari {total_text} ({percentage:.0f}%) · {speed}",
                    )
                else:
                    update_job(job_id, progress=24, sub_progress=100, message="Download selesai!", sub_message="Menggabungkan stream video dan audio...")

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
            # Some providers do not expose file size before the download starts.
            # The progress hook will still show a stable first estimate when possible.
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
    """Download only the source video into VideoMentah for the desktop workflow."""
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
    words = clean.split()
    if max_lines == -1:
        return [clean]

    lines_limit = 2 if max_lines <= 0 else max_lines
    max_words = 5 if lines_limit == 1 else 9
    max_chars = 26 if lines_limit == 1 else 52

    chunks: list[list[str]] = []
    curr: list[str] = []
    curr_len = 0
    for w in words:
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


def split_segment_into_cues(item_start: float, item_end: float, text: str, max_lines: int = 2) -> list[tuple[float, float, str]]:
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


def group_words_into_cues(words: list[Any], max_words: int = 5, max_chars: int = 28) -> list[dict[str, Any]]:
    if not words:
        return []
    cues: list[dict[str, Any]] = []
    curr_words: list[str] = []
    curr_word_objs: list[dict[str, Any]] = []
    curr_start: float | None = None
    curr_end: float = 0.0

    for w in words:
        w_text = getattr(w, "word", "")
        if not w_text and isinstance(w, dict):
            w_text = w.get("word", "")
        if not w_text:
            w_text = str(w)
        w_text = w_text.strip()
        if not w_text:
            continue

        w_start = float(getattr(w, "start", 0.0) if hasattr(w, "start") else (w.get("start", curr_end) if isinstance(w, dict) else curr_end))
        w_end = float(getattr(w, "end", w_start + 0.3) if hasattr(w, "end") else (w.get("end", w_start + 0.3) if isinstance(w, dict) else w_start + 0.3))

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


def transcribe_with_gemini(audio_path: Path, language: str | None = None, job_id: str | None = None) -> list[dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip() or GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY belum diisi. Masukkan API Key di pengaturan.")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    
    if job_id:
        update_job(job_id, progress=30, sub_progress=25, message="Mengunggah audio ke Gemini Cloud...", sub_message="Mengirim file audio ke server Google...")
    logger.info(f"Mengunggah audio ke Gemini Files API: {audio_path.name}")
    audio_file = client.files.upload(file=str(audio_path))
    
    prompt = (
        "Transcribe this audio file accurately. Divide it into short, natural spoken subtitle phrases "
        "(maximum 4 to 6 words or about 1.5 to 2.5 seconds per segment). "
        "Each segment's start and end timestamps must strictly follow the speaker's actual voice timing "
        "so the subtitle disappears or advances promptly when the speaker moves to the next phrase. "
        "Return ONLY a valid JSON array of objects, where each object has: "
        "'start': float (start time in seconds), "
        "'end': float (end time in seconds), "
        "'text': string (the spoken dialogue). "
        "Ensure timestamps are strictly numerical, positive, and sequential. Do not wrap in markdown backticks."
    )
    if language and language != "auto":
        prompt += f" The spoken language is {language}."
        
    if job_id:
        update_job(job_id, progress=45, sub_progress=65, message="Mentranskrip audio via Gemini API...", sub_message="Gemini menganalisis pembicaraan & timestamp...")
    logger.info("Mengirim audio ke Gemini API...")
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[audio_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        )
    )
    if job_id:
        update_job(job_id, progress=58, sub_progress=95, message="Menerima hasil transkripsi dari Cloud...", sub_message="Menyusun segmen subtitle...")
    try:
        client.files.delete(name=audio_file.name)
    except Exception:
        pass
        
    raw_text = response.text.strip()
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
        text = str(item.get("text", "")).strip()
        if text and end > start:
            w_list = text.split()
            if (end - start) > 3.2 or len(w_list) > 6:
                sub_cues = split_segment_into_cues(start, end, text, max_lines=1)
                for s_start, s_end, s_text in sub_cues:
                    if s_end > s_start and s_text.strip():
                        result.append({"start": round(s_start, 2), "end": round(s_end, 2), "text": s_text.strip()})
            else:
                result.append({"start": round(start, 2), "end": round(end, 2), "text": text})

    result.sort(key=lambda x: x["start"])
    for i in range(len(result) - 1):
        if result[i]["end"] > result[i + 1]["start"]:
            result[i]["end"] = max(result[i]["start"] + 0.2, result[i + 1]["start"])

    if not result:
        raise ValueError("Gemini tidak mendeteksi teks audio yang valid.")
    return result


def transcribe(audio_path: Path, language: str | None, model_size: str = "small", job_id: str | None = None) -> list[dict[str, Any]]:
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
    cpu_threads = min(8, os.cpu_count() or 4)

    def load_whisper(dev: str, comp: str) -> Any:
        return WhisperModel(model_size, device=dev, compute_type=comp, cpu_threads=cpu_threads)

    def do_transcribe(m: Any) -> Any:
        try:
            import av

            original_av_open = av.open

            def compatible_av_open(*args: Any, **kwargs: Any) -> Any:
                kwargs.pop("metadata_errors", None)
                return original_av_open(*args, **kwargs)

            av.open = compatible_av_open  # type: ignore[assignment]
            try:
                return m.transcribe(str(audio_path), language=language, vad_filter=True, word_timestamps=True)
            finally:
                av.open = original_av_open  # type: ignore[assignment]
        except ImportError:
            return m.transcribe(str(audio_path), language=language, vad_filter=True, word_timestamps=True)

    try:
        model = load_whisper(device, compute_type)
        segments, _ = do_transcribe(model)
    except Exception as exc:
        if device != "cpu":
            logger.warning(f"Whisper device '{device}' gagal ({exc}), otomatis beralih ke CPU...")
            model = load_whisper("cpu", "int8")
            segments, _ = do_transcribe(model)
        else:
            raise
    result = []
    total_dur = getattr(segments, "duration", 0) or 0
    # Process segments with word-accurate cues
    for segment in segments:
        seg_text = re.sub(r"\s+", " ", segment.text).strip()
        if not seg_text:
            continue
        seg_words = getattr(segment, "words", None)
        if seg_words:
            cues = group_words_into_cues(list(seg_words), max_words=5, max_chars=28)
            for c in cues:
                if c["end"] > c["start"] and c["text"].strip():
                    result.append(c)
        else:
            sub_cues = split_segment_into_cues(float(segment.start), float(segment.end), seg_text, max_lines=1)
            for c_start, c_end, c_text in sub_cues:
                if c_end > c_start and c_text.strip():
                    result.append({"start": round(c_start, 2), "end": round(c_end, 2), "text": c_text.strip()})

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
                sub_message=f"Memproses ucapan: detik ke-{cur_sec:.0f} (tahap transkripsi {sub_pct}%)",
            )

    result.sort(key=lambda x: x["start"])
    for i in range(len(result) - 1):
        if result[i]["end"] > result[i + 1]["start"]:
            result[i]["end"] = max(result[i]["start"] + 0.2, result[i + 1]["start"])

    if not result:
        raise RuntimeError("Tidak ada ucapan yang terdeteksi pada video.")
    if job_id:
        update_job(job_id, progress=60, sub_progress=100, message="Transkripsi audio selesai!", sub_message="Semua percakapan berhasil diubah menjadi teks")
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
            "atau kalimat pedas yang memancing perdebatan di kolom komentar. Mulai klip tepat di pernyataan pemicu konflik!"
        ),
        "headline_rule": (
            "Buat judul Headline 3-7 kata yang SPICY, provokatif, menimbulkan curiosity gap tinggi, "
            "atau menyorot pernyataan paling kontroversial/pedas di klip ini."
        ),
        "keywords": {
            "jujur", "bohong", "bongkar", "rahasia", "parah", "gila", "benci", "muak", "marah",
            "kesal", "sindir", "nyindir", "berani", "egois", "munafik", "selingkuh", "putus",
            "pecat", "bangkrut", "hutang", "miliar", "juta", "duit", "uang", "gaji", "bayar",
            "curang", "kasus", "drama", "ribut", "debat", "salah", "ngawur", "hancur", "kapok",
            "nyesel", "ternyata", "padahal", "jangan", "bahaya", "korban", "pelaku", "bukti", "fakta",
        },
        "energy_weight": 1.65,
        "ideal_min": 20,
        "ideal_max": 52,
    },
    "viral_all": {
        "label": "Viral FYP (Hook Kuat & Plot Twist)",
        "prompt_rule": (
            "FOKUS UTAMA: Cari momen dengan potensi VIRAL FYP tertinggi. Harus memiliki Hook kuat di "
            "3 detik pertama (kalimat pembuka yang menghentikan orang scroll), alur cerita yang padat, "
            "dan ditutup dengan Plot Twist atau payoff yang memuaskan."
        ),
        "headline_rule": "Buat judul Headline 3-7 kata yang sangat catchy, bikin penasaran di 3 detik pertama, dan viral-ready.",
        "keywords": {
            "ternyata", "rahasia", "cara", "jangan", "pernah", "alasan", "kenapa", "mengapa",
            "pertama", "terakhir", "paling", "terbaik", "terburuk", "fakta", "bukti", "kaget",
            "mustahil", "ajaib", "solusi", "kesalahan", "fatal", "untung", "rugi",
        },
        "energy_weight": 1.35,
        "ideal_min": 22,
        "ideal_max": 55,
    },
    "funny_blunder": {
        "label": "Komedi / Ngakak / Blunder",
        "prompt_rule": (
            "FOKUS UTAMA: Cari momen paling LUCU, NGAKAK, BLUNDER konyol, salah ngomong, roasting "
            "antar teman, atau reaksi spontan yang mengundang tawa. Sertakan setup singkat sebelum kelucuan "
            "dan tawa pecah setelahnya."
        ),
        "headline_rule": "Buat judul Headline yang kocak, menyorot kebodohan/blunder, atau punchline komedinya.",
        "keywords": {
            "haha", "wkwk", "anjir", "astaga", "waduh", "kocak", "lucu", "ngakak", "blunder",
            "bodoh", "tolol", "konyol", "malu", "jatuh", "gagal", "salah", "ketawa", "asli",
        },
        "energy_weight": 1.85,
        "ideal_min": 15,
        "ideal_max": 42,
    },
    "deep_meat": {
        "label": "Daging / Insight / Mindblowing",
        "prompt_rule": (
            "FOKUS UTAMA: Cari kutipan paling BERBOBOT ('daging'), prinsip hidup, strategi bisnis/uang, "
            "nasihat menohok, atau perspektif cerdas yang membuat penonton menyimpan (save/bookmark) video ini."
        ),
        "headline_rule": "Buat judul Headline yang tegas, berwibawa, dan merangkum insight emas di dalam klip.",
        "keywords": {
            "prinsip", "kunci", "sukses", "kaya", "mental", "strategi", "ilmu", "pelajaran",
            "hidup", "masa", "depan", "investasi", "bisnis", "kerja", "fokus", "disiplin", "paham",
        },
        "energy_weight": 1.0,
        "ideal_min": 28,
        "ideal_max": 58,
    },
    "hype_rage": {
        "label": "Hype Tinggi / Teriakan / Rage Gaming",
        "prompt_rule": (
            "FOKUS UTAMA: Cari momen dengan energi suara dan tensi paling meledak: teriakan kaget, "
            "rage/marah saat main game, momen clutch menegangkan, atau reaksi heboh maksimal."
        ),
        "headline_rule": "Buat judul Headline penuh energi yang menggambarkan ketegangan/ledakan emosi momen tersebut.",
        "keywords": {
            "anjing", "anjir", "gila", "mati", "menang", "kalah", "clutch", "hoki", "curang",
            "lari", "tolong", "awas", "kena", "habis", "pecah", "meledak",
        },
        "energy_weight": 2.4,
        "ideal_min": 14,
        "ideal_max": 38,
    },
}

FILLER_STARTERS = {"eh", "ee", "emm", "anu", "jadi", "nah", "oke", "terus", "umm", "uh", "ya"}


def compute_audio_energy_map(audio_path: Path, window_sec: float = 1.0) -> list[float]:
    """Menghitung peta lonjakan energi suara (RMS) tiap 1 detik dari file audio.wav."""
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


def condense_transcript_for_llm(
    transcript: list[dict[str, Any]],
    energy_map: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Menggabungkan potongan cues pendek menjadi kalimat utuh disertai indikator energi suara untuk LLM."""
    if not transcript:
        return []
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
            seg_obj: dict[str, Any] = {
                "start": round(curr_start, 2),
                "end": round(curr_end, 2),
                "text": " ".join(curr_texts),
            }
            if energy_map:
                seg_obj["energy"] = get_window_energy_score(energy_map, curr_start, curr_end)
            merged.append(seg_obj)
            curr_start = s
            curr_end = e
            curr_texts = [txt]
        else:
            curr_end = e
            curr_texts.append(txt)

    if curr_texts:
        seg_obj = {
            "start": round(curr_start, 2),
            "end": round(curr_end, 2),
            "text": " ".join(curr_texts),
        }
        if energy_map:
            seg_obj["energy"] = get_window_energy_score(energy_map, curr_start, curr_end)
        merged.append(seg_obj)
    return merged


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
    flavor_cfg = CLIP_FLAVOR_PROFILES.get(flavor, CLIP_FLAVOR_PROFILES["spicy_drama"])
    keywords = set(flavor_cfg["keywords"])
    if profile == "live":
        keywords |= {"anjir", "gila", "waduh", "astaga", "haha", "wkwk", "blunder", "clutch", "chat", "stream"}
    elif profile == "standard":
        keywords |= {"langkah", "contoh", "solusi", "hasil", "alasan", "pelajaran", "trik"}

    energy_weight = float(flavor_cfg["energy_weight"])
    total = float(transcript[-1]["end"])
    eff_min = max(8, minimum if minimum > 0 else int(flavor_cfg["ideal_min"]))
    eff_max = maximum if maximum > 0 else int(flavor_cfg["ideal_max"])
    preferred = max(eff_min, int(round(eff_max * 0.78)))

    candidates = []
    for anchor_index, anchor in enumerate(transcript):
        start = max(0.0, float(anchor["start"]))
        end_index = anchor_index
        while end_index + 1 < len(transcript):
            candidate_end = float(transcript[end_index + 1]["end"])
            candidate_duration = candidate_end - start
            current_text = str(transcript[end_index].get("text", ""))
            natural_break = (
                bool(re.search(r"[.!?]$", current_text))
                or (float(transcript[end_index + 1]["start"]) - float(transcript[end_index]["end"]) > 0.65)
            )
            if eff_max > 0 and candidate_duration > eff_max:
                break
            end_index += 1
            if candidate_duration >= preferred and natural_break:
                break

        end = min(total, float(transcript[end_index]["end"]))
        dur = end - start
        if dur < eff_min:
            continue

        segs_in_window = [x for x in transcript if float(x["start"]) < end and float(x["end"]) > start]
        text = " ".join(str(x.get("text", "")) for x in segs_in_window).strip()
        token_list = words(text)
        if len(token_list) < 12:
            continue

        wps = len(token_list) / max(dur, 1.0)
        raw_score = wps * 11.0
        raw_score += sum(7.5 for token in token_list if token in keywords)
        raw_score += text.count("!") * 4.5 + text.count("?") * 3.5
        raw_score += len(re.findall(r"\b\d+\b", text)) * 3.0

        if energy_map:
            e_val = get_window_energy_score(energy_map, start, end)
            raw_score += (e_val * 32.0) * energy_weight

        for i in range(len(segs_in_window) - 1):
            gap = float(segs_in_window[i + 1]["start"]) - float(segs_in_window[i]["end"])
            if gap > 2.5:
                raw_score -= gap * 5.0

        viral_score = min(99.0, max(55.0, round(raw_score, 1)))
        candidates.append({"start": start, "end": end, "score": viral_score, "text": text})

    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected: list[dict[str, Any]] = []
    target = count if count > 0 else max_clips
    for candidate in candidates:
        overlaps = any(
            candidate["start"] < item["end"] and candidate["end"] > item["start"]
            for item in selected
        )
        if not overlaps:
            selected.append(candidate)
        if len(selected) >= target:
            break
    return selected


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
    Mengunci titik potong start & end tepat pada batas kata/kalimat alami,
    membuang basa-basi (filler) di 3 detik pertama, dan memberi micro-padding.
    """
    if not transcript or not selected:
        return selected

    flavor_cfg = CLIP_FLAVOR_PROFILES.get(flavor, CLIP_FLAVOR_PROFILES["spicy_drama"])
    total_duration = float(transcript[-1]["end"])
    eff_min = float(minimum if minimum > 0 else flavor_cfg["ideal_min"])
    eff_max = float(maximum if maximum > 0 else flavor_cfg["ideal_max"])

    all_words: list[dict[str, Any]] = []
    for seg in transcript:
        seg_words = seg.get("words") or []
        if seg_words:
            all_words.extend(seg_words)
        else:
            all_words.append({"word": seg.get("text", ""), "start": seg["start"], "end": seg["end"]})

    ordered = sorted(selected, key=lambda item: float(item.get("start", 0)))
    polished: list[dict[str, Any]] = []
    cursor = 0.0

    for idx, item in enumerate(ordered):
        raw_start = max(cursor, float(item["start"]))
        raw_end = min(total_duration, float(item["end"]))
        next_clip_start = float(ordered[idx + 1]["start"]) if idx + 1 < len(ordered) else total_duration

        best_start = raw_start
        if snap_bounds and all_words:
            for w_i, w in enumerate(all_words):
                ws = float(w["start"])
                if abs(ws - raw_start) <= 1.8 and ws >= cursor:
                    prev_end = float(all_words[w_i - 1]["end"]) if w_i > 0 else 0.0
                    prev_word = str(all_words[w_i - 1].get("word", "")) if w_i > 0 else "."
                    is_clean_start = (ws - prev_end >= 0.32) or bool(re.search(r"[.?!]$", prev_word))
                    if is_clean_start:
                        clean_tok = re.sub(r"[^a-zA-Z]", "", str(w.get("word", ""))).lower()
                        if trim_filler and clean_tok in FILLER_STARTERS and w_i + 1 < len(all_words):
                            best_start = float(all_words[w_i + 1]["start"])
                        else:
                            best_start = ws
                        break

        target_end = max(raw_end, best_start + eff_min)
        target_end = min(target_end, best_start + eff_max, next_clip_start - 0.2)

        best_end = target_end
        if snap_bounds and all_words:
            for w_i, w in enumerate(all_words):
                we = float(w["end"])
                if we < best_start + eff_min:
                    continue
                if we > best_start + eff_max or we > next_clip_start - 0.15:
                    break
                next_start = float(all_words[w_i + 1]["start"]) if w_i + 1 < len(all_words) else total_duration
                word_str = str(w.get("word", "")).strip()
                is_sentence_end = bool(re.search(r"[.?!]$", word_str)) or (next_start - we >= 0.42)
                if we >= target_end - 2.2 and is_sentence_end:
                    best_end = we
                    break
                best_end = we

        final_start = max(cursor, round(best_start - 0.18, 3))
        final_end = min(total_duration, next_clip_start - 0.1, round(best_end + 0.40, 3))

        if final_end - final_start >= 5.0:
            updated = dict(item)
            updated["start"] = final_start
            updated["end"] = final_end
            updated["score"] = float(item.get("score") or 88.0)
            polished.append(updated)
            cursor = final_end

    return polished


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
        ranges = [
            (start, min(total, start + segment_duration))
            for start in range(0, int(total), segment_duration)
        ]
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
    return " ".join(
        item["text"] for item in transcript if item["start"] < end and item["end"] > start
    ).strip()


def fallback_metadata(text: str, current_title: str = "") -> tuple[str, str, list[str]]:
    clean_text = re.sub(r"\s+", " ", text).strip()
    first_sentence = re.split(r"[.!?]", clean_text)[0].strip()
    title = current_title.strip() or (first_sentence[:70].rstrip() if first_sentence else "Highlight clip")
    caption = clean_text[:280] + ("..." if len(clean_text) > 280 else "")
    tokens = [token for token in words(clean_text) if len(token) >= 5]
    hashtags = ["#shorts", "#clip"]
    for token in tokens:
        tag = f"#{token}"
        if tag not in hashtags:
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
        clip.title, clip.caption, clip.hashtags = fallback_metadata(text, clip.title if clip.source == "manual" else "")

    flavor_cfg = CLIP_FLAVOR_PROFILES.get(flavor, CLIP_FLAVOR_PROFILES["spicy_drama"])
    headline_instruction = flavor_cfg["headline_rule"] if spicy_hook else "Buat title 3-8 kata yang spesifik dan menarik."

    items = [
        {
            "index": index,
            "start": clip.start,
            "end": clip.end,
            "text": clip_transcript_text(transcript, clip.start, clip.end),
        }
        for index, clip in enumerate(clips, start=1)
    ]
    prompt = (
        "Buat metadata sosial media untuk setiap clip video berikut. TULIS DALAM BAHASA INDONESIA, meskipun transkrip asli berbahasa asing. "
        "Balas HANYA JSON array valid dengan field index, title, caption, hashtags. "
        f"ATURAN HEADLINE HOOK (title): {headline_instruction} "
        "Caption maksimal 2 kalimat, mulai dengan kalimat pancingan (hook) yang memicu penonton berkomentar/berdebat, "
        "hindari kalimat kaku seperti 'di video ini'. Hashtags berupa array 3-6 hashtag relevan. "
        "Jangan mengarang klaim di luar transkrip.\n\nCLIPS:\n"
        + json.dumps(items, ensure_ascii=False)
    )

    if model_name == "gemini":
        if not GEMINI_API_KEY:
            return
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=f"Kamu adalah social media clipper profesional.\n{prompt}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.35,
                ),
            )
            parsed = json.loads(response.text)
            if isinstance(parsed, dict):
                parsed = parsed.get("clips", [])
            for item in parsed:
                index = int(item["index"]) - 1
                if not 0 <= index < len(clips):
                    continue
                if not custom_titles[index]:
                    clips[index].title = str(item.get("title") or clips[index].title)
                clips[index].caption = str(item.get("caption") or clips[index].caption)
                tags = item.get("hashtags") or clips[index].hashtags
                clips[index].hashtags = [str(tag) if str(tag).startswith("#") else f"#{tag}" for tag in tags][:8]
            return
        except Exception as e:
            logger.warning(f"Gemini Metadata Error: {e}")
            return

    model = load_local_gguf(model_name)
    if model is None:
        return
    try:
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": "Kamu adalah social media editor yang membuat metadata video."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
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
            if not custom_titles[index]:
                clips[index].title = str(item.get("title") or clips[index].title)
            clips[index].caption = str(item.get("caption") or clips[index].caption)
            tags = item.get("hashtags") or clips[index].hashtags
            clips[index].hashtags = [str(tag) if str(tag).startswith("#") else f"#{tag}" for tag in tags][:8]
    except Exception:
        return


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
    eff_min = minimum if minimum > 0 else int(flavor_cfg["ideal_min"])
    eff_max = maximum if maximum > 0 else int(flavor_cfg["ideal_max"])
    prompt = (
        "Kamu adalah Clipper Profesional TikTok, Reels, dan YouTube Shorts.\n"
        f"{flavor_cfg['prompt_rule']}\n"
        f"Profil Konten: {CLIP_PROFILE_GUIDANCE.get(profile, CLIP_PROFILE_GUIDANCE['auto'])}\n"
        "ATURAN PEMOTONGAN PRESISI:\n"
        "1. DETIK MULAI (start): Harus langsung masuk ke kalimat HOOK / pernyataan paling panas di 3 detik pertama. "
        "Jangan masukkan basa-basi atau jeda lambat sebelum topik dimulai.\n"
        "2. DETIK SELESAI (end): Harus berhenti tepat setelah punchline, sindiran, reaksi, atau kesimpulan tuntas.\n"
        f"3. DURASI: Antara {eff_min} sampai {eff_max} detik per klip.\n"
        "4. Perhatikan field 'energy' (0.0-1.0) bila tersedia: angka tinggi menandakan intonasi suara meninggi/debat/tertawa/teriak.\n"
        "5. Balas HANYA JSON array valid tanpa markdown dengan field: start (float), end (float), score (int 65-99), title (string judul singkat & pedas).\n"
        f"Pilih {'sebanyak mungkin, maksimal ' + str(max_clips) if count == 0 else str(count)} segmen non-overlap terbaik.\n"
        + (f"Instruksi khusus dari user: {custom_prompt}\n" if custom_prompt.strip() else "")
        + "\nTRANSKRIP:\n"
        + json.dumps(condensed_transcript, ensure_ascii=False)
    )
    return prompt, eff_min, eff_max


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
    condensed = condense_transcript_for_llm(transcript, energy_map)
    prompt, eff_min, eff_max = build_clipper_llm_prompt(
        condensed, count, minimum, maximum, max_clips, profile, flavor, custom_prompt
    )
    try:
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": "Kamu adalah editor video yang memilih momen paling viral dan spicy."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
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
            if end > start and duration >= max(5, eff_min - 5) and duration <= eff_max + 15:
                valid.append({
                    "start": start,
                    "end": end,
                    "score": float(item.get("score", 90.0)),
                    "title": str(item.get("title", "Highlight")),
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
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        condensed = condense_transcript_for_llm(transcript, energy_map)
        prompt, eff_min, eff_max = build_clipper_llm_prompt(
            condensed, count, minimum, maximum, max_clips, profile, flavor, custom_prompt
        )
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.25,
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
            if end > start and duration >= max(5, eff_min - 5) and duration <= eff_max + 15:
                valid.append({
                    "start": start,
                    "end": end,
                    "score": float(item.get("score", 92.0)),
                    "title": str(item.get("title", "Highlight")),
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
    prompt = (
        "Pilih segmen video paling menarik untuk short clip. Sertakan buildup sebelum momen utama dan reaksi/payoff setelahnya, "
        "jangan hanya mengambil satu kalimat. Kembalikan JSON array saja "
        "dengan field start, end, title. start/end dalam detik. Jangan overlap. "
        f"Pilih {'sebanyak mungkin, maksimal ' + str(max_clips) if count == 0 else str(count)} segmen, durasi "
        f"{'alami tanpa batas minimum/maksimum' if minimum == 0 and maximum == 0 else f'{minimum}-{maximum} detik'}. "
        f"Profil momen: {CLIP_PROFILE_GUIDANCE.get(profile, CLIP_PROFILE_GUIDANCE['auto'])}\n"
        + (f"Instruksi tambahan dari user: {custom_prompt}\n" if custom_prompt.strip() else "")
        + "\nTRANSKRIP:\n"
        + json.dumps(transcript, ensure_ascii=False)
    )
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}).encode()
    request = urlrequest.Request(
        "http://127.0.0.1:11434/api/generate",
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
            if end > start and (minimum == 0 or duration >= minimum) and (maximum == 0 or duration <= maximum):
                valid.append({"start": start, "end": end, "score": 100.0, "title": str(item.get("title", "Highlight"))})
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


def censor_word_if_enabled(word: str, enabled: bool = False) -> str:
    if not enabled:
        return word
    clean = re.sub(r"[^a-zA-Z]", "", word).lower()
    if clean in PROFANITY_WORDS and len(word) > 2:
        return word[0] + ("*" * (len(word) - 2)) + word[-1]
    return word


def write_srt(
    transcript: list[dict[str, Any]],
    start: float,
    end: float,
    path: Path,
    max_lines: int = 2,
    mode: str = "phrase",
    highlight_color: str = "#FFDD00",
    censor_profanity: bool = False,
) -> None:
    lines: list[str] = []
    index = 1
    clip_dur = max(0.1, end - start)

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

        if censor_profanity:
            item_text = " ".join(censor_word_if_enabled(tok, True) for tok in item_text.split())

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
                    lines.extend([str(index), f"{srt_timestamp(ws)} --> {srt_timestamp(we)}", nw["word"].upper(), ""])
                    index += 1

        elif mode == "active_highlight":
            chunk_size = 4 if max_lines != 1 else 3
            for chunk_idx in range(0, len(norm_words), chunk_size):
                chunk = norm_words[chunk_idx:chunk_idx + chunk_size]
                chunk_words = [w["word"] for w in chunk if w["word"]]
                if not chunk_words:
                    continue

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
                        if i == active_i:
                            formatted_tokens.append(f"<font color=\"{highlight_color}\">{cw}</font>")
                        else:
                            formatted_tokens.append(cw)

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
                lines.extend([str(index), f"{srt_timestamp(c_start)} --> {srt_timestamp(c_end)}", c_text, ""])
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


def subtitle_style_with_position(
    style: str,
    position: str,
    color: str = "auto",
    subtitle_x: float = 0.15,
    subtitle_y: float = 0.78,
    aspect_ratio: str = "9:16",
    font_size: int | None = None,
) -> str:
    """Apply a stable subtitle position without changing the selected visual style."""
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


def detect_face_crop(
    video_path: Path,
    start_sec: float = 0.0,
    end_sec: float = 0.0,
) -> tuple[int, int, int, int] | None:
    """Deteksi koordinat kotak facecam streamer di area pinggir/pojok pada rentang waktu klip."""
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

    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    start_f = max(0, int(start_sec * fps)) if start_sec > 0 else 0
    end_f = min(max(0, frame_count - 1), int(end_sec * fps)) if end_sec > start_sec else max(0, frame_count - 1)
    span = max(1, end_f - start_f)
    sample_points = [start_f + int(span * r) for r in (0.1, 0.3, 0.5, 0.7, 0.9)]

    candidates: list[tuple[float, int, int, int, int]] = []
    for frame_index in sample_points:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(32, 32))
        for (fx, fy, fw, fh) in faces:
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


QUESTION_TRIGGERS = {
    "kenapa", "mengapa", "gimana", "bagaimana", "apa", "apakah", "siapa", "kapan",
    "berapa", "dimana", "ceritain", "ceritakan", "jelasin", "jelaskan", "menurut",
    "bener", "benar", "setuju", "awal", "mulanya", "kisah", "kronologi", "alasan",
    "maksudnya", "pertanyaan", "tanya", "penasaran", "kok", "boleh", "bisa", "sebenarnya",
    "pernah", "rasanya", "pendapat", "pandangan", "solusi", "rahasia", "fakta",
}


def detect_podcast_speaker_crops(
    video_path: Path,
    start_sec: float,
    end_sec: float,
    target_w: int,
    half_h: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]] | None:
    try:
        import cv2
    except ImportError:
        return None

    cap = cv2.VideoCapture(str(video_path))
    vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if vw <= 0 or vh <= 0:
        cap.release()
        return None

    frontal = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

    start_f = max(0, int(start_sec * fps))
    end_f = min(max(1, total_frames - 1), int(end_sec * fps)) if end_sec > start_sec else max(1, total_frames - 1)
    span = max(1, end_f - start_f)

    left_x, left_y, right_x, right_y = [], [], [], []
    for r in (0.10, 0.22, 0.35, 0.48, 0.60, 0.74, 0.88):
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f + int(span * r))
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = list(frontal.detectMultiScale(gray, 1.1, 5, minSize=(40, 40)))
        if len(faces) < 2:
            faces.extend(list(profile.detectMultiScale(gray, 1.1, 4, minSize=(40, 40))))
        for (fx, fy, fw, fh) in faces:
            cx = fx + fw / 2.0
            cy = fy + fh * 0.82
            if cx < vw * 0.47:
                left_x.append(cx)
                left_y.append(cy)
            elif cx > vw * 0.53:
                right_x.append(cx)
                right_y.append(cy)
    cap.release()

    panel_ar = float(target_w) / float(max(1, half_h))
    crop_h = min(vh, int(vh * 0.82))
    crop_w = min(vw // 2, int(crop_h * panel_ar))
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2

    lcx = sum(left_x) / len(left_x) if left_x else (vw * 0.24)
    lcy = sum(left_y) / len(left_y) if left_y else (vh * 0.44)
    rcx = sum(right_x) / len(right_x) if right_x else (vw * 0.76)
    rcy = sum(right_y) / len(right_y) if right_y else (vh * 0.44)

    lx = max(0, min((vw // 2) - crop_w, int(lcx - crop_w / 2)))
    ly = max(0, min(vh - crop_h, int(lcy - crop_h * 0.42)))
    rx = max(vw // 2, min(vw - crop_w, int(rcx - crop_w / 2)))
    ry = max(0, min(vh - crop_h, int(rcy - crop_h * 0.42)))
    return (lx, ly, crop_w, crop_h), (rx, ry, crop_w, crop_h)


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


def write_ass_pop_subtitle(
    transcript: list[dict[str, Any]],
    start: float,
    end: float,
    ass_path: Path,
    aspect_ratio: str = "9:16",
    layout: str = "podcast_split",
    position: str = "auto",
    font_size: int = 18,
    max_lines: int = 2,
    mode: str = "active_highlight",
    base_color_hex: str = "#FFFFFF",
    active_color_hex: str = "#FFDD00",
    censor_profanity: bool = False,
) -> None:
    width, height = output_dimensions(aspect_ratio)
    scaled_font_size = max(44, min(72, int(font_size * 3.1)))
    primary_ass = hex_to_ass_bgr(base_color_hex, "&H00FFFFFF")
    active_ass = hex_to_ass_bgr(active_color_hex, "&H0000DDFF")
    question_ass = "&H00FFEE00"
    power_ass = "&H0077FF00"

    if position == "center" or (layout == "podcast_split" and position in ("auto", "bottom")):
        alignment = 5
        margin_v = 0
    elif position == "top":
        alignment = 8
        margin_v = int(height * 0.14)
    else:
        alignment = 2
        margin_v = int(height * 0.19)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PodcastPro,Arial Black,{scaled_font_size},{primary_ass},{active_ass},&H00000000,&H80000000,-1,0,0,0,100,100,1.2,0,1,4.5,2.5,{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    clip_dur = max(0.1, end - start)
    spicy_words = CLIP_FLAVOR_PROFILES["spicy_drama"]["keywords"]

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

        chunk_size = 3 if max_lines == 1 else 4
        for chunk_idx in range(0, len(norm_words), chunk_size):
            chunk = norm_words[chunk_idx : chunk_idx + chunk_size]
            if not chunk:
                continue
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
                    clean_tok = re.sub(r"[^a-zA-Z0-9]", "", raw_tok).lower()
                    if i == active_i:
                        if "?" in raw_tok or clean_tok in QUESTION_TRIGGERS:
                            col = question_ass
                        elif clean_tok in spicy_words or clean_tok.isdigit():
                            col = power_ass
                        else:
                            col = active_ass
                        formatted_tokens.append(
                            f"{{\\c{col}\\fscx118\\fscy118\\t(0,105,\\fscx105\\fscy105)}}{raw_tok}{{\\c{primary_ass}\\fscx100\\fscy100}}"
                        )
                    else:
                        formatted_tokens.append(raw_tok)

                if max_lines >= 2 and len(formatted_tokens) >= 4:
                    mid = len(formatted_tokens) // 2
                    cue_text = " ".join(formatted_tokens[:mid]) + "\\N" + " ".join(formatted_tokens[mid:])
                else:
                    cue_text = " ".join(formatted_tokens)

                events.append(f"Dialogue: 0,{ass_timestamp(ws_t)},{ass_timestamp(we_t)},PodcastPro,,0,0,0,,{cue_text}")

    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def output_dimensions(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "16:9":
        return 1280, 720
    if aspect_ratio == "4:3":
        return 1440, 1080
    if aspect_ratio == "1:1":
        return 1080, 1080
    return 720, 1280


def video_layout_filter(
    aspect_ratio: str,
    framing: str,
    layout: str,
    face_crop: tuple[int, int, int, int] | None,
) -> str:
    width, height = output_dimensions(aspect_ratio)

    if layout == "podcast_split":
        half_h = (height // 2)
        if half_h % 2 != 0:
            half_h += 1
        rem_h = height - half_h
        return (
            f"split=2[left_spk][right_spk];"
            f"[left_spk]crop=iw/2:ih:0:0,scale={width}:{half_h}:force_original_aspect_ratio=increase,crop={width}:{half_h}[top_out];"
            f"[right_spk]crop=iw/2:ih:iw/2:0,scale={width}:{rem_h}:force_original_aspect_ratio=increase,crop={width}:{rem_h}[bot_out];"
            f"[top_out][bot_out]vstack=inputs=2"
        )

    if layout != "facecam_top" or not face_crop:
        if framing == "fit":
            return (
                f"split=2[bg][fg];"
                f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=20:10[blurred];"
                f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fg_fit];"
                f"[blurred][fg_fit]overlay=(W-w)/2:(H-h)/2"
            )
        return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"

    crop_x, crop_y, crop_w, crop_h = face_crop
    top_height = int(height * 0.35)
    if top_height % 2 != 0:
        top_height += 1
    bottom_height = height - top_height

    if framing == "fit":
        return (
            f"split=3[face][mbg][mfg];"
            f"[face]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
            f"scale={width}:{top_height}:force_original_aspect_ratio=increase,crop={width}:{top_height}[faceout];"
            f"[mbg]scale={width}:{bottom_height}:force_original_aspect_ratio=increase,crop={width}:{bottom_height},boxblur=18:8[mblur];"
            f"[mfg]scale={width}:{bottom_height}:force_original_aspect_ratio=decrease[mfit];"
            f"[mblur][mfit]overlay=(W-w)/2:(H-h)/2[mainout];"
            f"[faceout][mainout]vstack=inputs=2"
        )

    return (
        f"split=2[face][main];"
        f"[face]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={width}:{top_height}:force_original_aspect_ratio=increase,crop={width}:{top_height}[faceout];"
        f"[main]scale={width}:{bottom_height}:force_original_aspect_ratio=increase,crop={width}:{bottom_height}[mainout];"
        f"[faceout][mainout]vstack=inputs=2"
    )


_DETECTED_ENCODERS: list[tuple[str, str]] | None = None

def detect_hardware_encoders() -> list[tuple[str, str]]:
    """Mendeteksi hardware encoder GPU/eGPU yang aktif pada sistem."""
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
            # NVENC requires minimum 128x128 frame dimensions to initialize
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
    """Mengembalikan argumen FFmpeg dan label encoder untuk rendering."""
    if encoder == "auto":
        hardware = detect_hardware_encoders()
        for enc, label in hardware:
            if enc not in ("auto", "libx264"):
                return get_encoder_args(enc)
        return get_encoder_args("libx264")

    if encoder == "av1_nvenc":
        return ["-c:v", "av1_nvenc", "-pix_fmt", "yuv420p", "-cq", "24"], "NVIDIA NVENC AV1"
    elif encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-pix_fmt", "yuv420p", "-preset", "p4", "-cq", "21"], "NVIDIA NVENC H.264"
    elif encoder == "av1_amf":
        return ["-c:v", "av1_amf", "-pix_fmt", "yuv420p", "-quality", "speed"], "AMD AMF AV1"
    elif encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-pix_fmt", "yuv420p", "-quality", "speed"], "AMD AMF H.264"
    else:
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
                            curr_overall = min(progress_end, progress_start + int(clip_ratio * (progress_end - progress_start)))
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
    clip_dir = clip_result_dir(job_dir, clip.id, clip.title)
    # Bersihkan folder lama dengan ID klip yang sama jika pengguna baru saja mengganti judul klip di tab Review
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
    censor_flag = bool(getattr(options, "censor_profanity", False))

    write_srt(
        transcript,
        clip.start,
        clip.end,
        subtitle_path,
        max_lines=max_lines,
        mode=sub_mode,
        highlight_color=active_col,
        censor_profanity=censor_flag,
    )
    write_ass_pop_subtitle(
        transcript,
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
    )

    width, height = output_dimensions(options.aspect_ratio)
    if options.layout == "podcast_split":
        half_h = (height // 2) + ((height // 2) % 2)
        rem_h = height - half_h
        p_crops = detect_podcast_speaker_crops(video, clip.start, clip.end, width, half_h)
        if p_crops:
            (lx, ly, lw, lh), (rx, ry, rw, rh) = p_crops
            layout_filter = (
                f"split=2[left_spk][right_spk];"
                f"[left_spk]crop={lw}:{lh}:{lx}:{ly},scale={width}:{half_h}:force_original_aspect_ratio=increase,crop={width}:{half_h}[top_out];"
                f"[right_spk]crop={rw}:{rh}:{rx}:{ry},scale={width}:{rem_h}:force_original_aspect_ratio=increase,crop={width}:{rem_h}[bot_out];"
                f"[top_out][bot_out]vstack=inputs=2,"
                f"drawbox=x=0:y={half_h-2}:w={width}:h=4:color=black@0.85:t=fill"
            )
        else:
            layout_filter = (
                f"split=2[left_spk][right_spk];"
                f"[left_spk]crop=iw*0.44:ih*0.84:iw*0.02:ih*0.06,scale={width}:{half_h}:force_original_aspect_ratio=increase,crop={width}:{half_h}[top_out];"
                f"[right_spk]crop=iw*0.44:ih*0.84:iw*0.54:ih*0.06,scale={width}:{rem_h}:force_original_aspect_ratio=increase,crop={width}:{rem_h}[bot_out];"
                f"[top_out][bot_out]vstack=inputs=2,"
                f"drawbox=x=0:y={half_h-2}:w={width}:h=4:color=black@0.85:t=fill"
            )
    else:
        effective_face_crop = resolve_pixel_face_crop(video, options, clip.start, clip.end) if options.layout == "facecam_top" else None
        layout_filter = video_layout_filter(options.aspect_ratio, options.framing, options.layout, effective_face_crop)

    if getattr(options, "mirror_video", False):
        layout_filter = f"{layout_filter},hflip"
    if getattr(options, "color_boost", False):
        layout_filter = f"{layout_filter},eq=contrast=1.06:saturation=1.12:brightness=0.01"

    if options.subtitle_style == "none":
        video_filter = layout_filter
    elif options.layout == "podcast_split" or options.subtitle_position == "center":
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

    if getattr(options, "hook_banner_enabled", False):
        hb_text = (getattr(options, "hook_banner_text", "") or clip.title or "").strip()
        hb_dur = int(getattr(options, "hook_banner_duration", 4))
        enable_expr = f":enable='between(t,0,{hb_dur})'" if hb_dur > 0 else ""
        wrapped_lines = wrap_banner_text(hb_text.upper(), max_chars=26)
        for line_idx, line_str in enumerate(wrapped_lines):
            safe_hb = escape_drawtext(line_str)
            y_pos = f"h*0.10+{line_idx * 34}"
            video_filter += (
                f",drawtext=text='{safe_hb}':fontcolor=#FFDD00:fontsize=22:font='Arial Black':"
                f"box=1:boxcolor=black@0.82:boxborderw=8:x=(w-text_w)/2:y={y_pos}{enable_expr}"
            )

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
        fallback_cmd = base_cmd + ["-c:v", "libx264", "-preset", "fast", "-crf", "21", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "clip.mp4"]
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
        fallback_cmd = base_cmd + ["-c:v", "libx264", "-preset", "fast", "-crf", "21", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "clip.mp4"]

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
    # Use a temporary workspace until a downloaded video's title is known.
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
            if options.local_model == "gemini":
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
            elif options.use_local_llm:
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
                trim_filler=getattr(options, "trim_opening_filler", True),
            )
        clips = []
        for index, item in enumerate(selected, start=1):
            clip = Clip(
                id=f"clip-{index:02}",
                start=float(item["start"]),
                end=float(item["end"]),
                score=float(item.get("score", 88.0)),
                title=str(item.get("title") or f"Highlight {index}"),
                source="ai",
            )
            clips.append(clip)
        update_job(job_id, progress=62, sub_progress=40, message="Mencari momen terbaik dengan AI...", sub_message=f"Model {options.local_model.upper()} menganalisis transkrip ({flavor})...")
        update_job(job_id, clips=clips, progress=68, sub_progress=75, message="Membuat metadata (Judul, Caption, Hashtag)...", sub_message="AI mengoptimalkan hook dan copywriting klip...")
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
    except Exception as exc:  # surfaced in the UI for a friendlier local setup experience
        update_job(job_id, status="failed", progress=100, message="Proses gagal", error=str(exc))


def render_job(job_id: str, options: CreateJobRequest) -> None:
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
    except Exception as exc:  # surfaced in the UI for a friendlier local setup experience
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
            raise HTTPException(status_code=422, detail=f"Waktu selesai melebihi durasi video ({format_time_for_error(duration)})")
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


# --- ANTIGRAVITY PODCAST PRO ENGINE AUTO-HOOK ---
try:
    import auto_clipper_tiktok as _act
    _act.inject_podcast_pro_engine()
except Exception:
    pass





