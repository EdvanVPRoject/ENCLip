from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
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
    url: str = Field(min_length=8)
    clip_count: int = Field(default=0, ge=0, le=200)
    language: str = Field(default="id", min_length=2, max_length=10)
    min_duration: int = Field(default=0, ge=0, le=3600)
    max_duration: int = Field(default=0, ge=0, le=3600)
    smart_duration_mode: str = Field(default="auto", pattern="^(auto|fixed)$")
    smart_fixed_duration: int = Field(default=60, ge=5, le=3600)
    max_clips: int = Field(default=10, ge=1, le=200)
    clip_mode: str = Field(default="smart", pattern="^(smart|split_count|split_duration)$")
    clip_profile: str = Field(default="auto", pattern="^(auto|live|standard|manual)$")
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
    layout: str = Field(default="standard", pattern="^(standard|facecam_top)$")
    subtitle_style: str = Field(default="bold", pattern="^(classic|bold|highlight|minimal|neon|karaoke|box|none)$")
    subtitle_position: str = Field(default="auto", pattern="^(auto|top|center|bottom|free)$")
    subtitle_color: str = Field(default="auto", pattern="^(auto|white|yellow|cyan|red|green|pink|#[0-9A-Fa-f]{6})$")
    subtitle_x: float = Field(default=0.15, ge=0, le=1)
    subtitle_y: float = Field(default=0.78, ge=0, le=1)
    subtitle_max_lines: int = Field(default=2, ge=-1, le=5)
    subtitle_font_size: int = Field(default=14, ge=8, le=36)


class RenderRequest(BaseModel):
    subtitle_style: str = Field(default="bold", pattern="^(classic|bold|highlight|minimal|neon|karaoke|box|none)$")
    aspect_ratio: str = Field(default="9:16", pattern="^(16:9|9:16|4:3|1:1)$")
    framing: str = Field(default="fit", pattern="^(fit|crop)$")
    layout: str = Field(default="standard", pattern="^(standard|facecam_top)$")
    subtitle_position: str = Field(default="auto", pattern="^(auto|top|center|bottom|free)$")
    subtitle_color: str = Field(default="auto", pattern="^(auto|white|yellow|cyan|red|green|pink|#[0-9A-Fa-f]{6})$")
    subtitle_x: float = Field(default=0.15, ge=0, le=1)
    subtitle_y: float = Field(default=0.78, ge=0, le=1)
    subtitle_max_lines: int = Field(default=2, ge=-1, le=5)
    subtitle_font_size: int = Field(default=14, ge=8, le=36)


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
    ffmpeg_path = ffmpeg_command()[0]
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
                update_job(job_id, progress=5, message=f"Menyiapkan download · total {label}...")
        except Exception:
            # Some providers do not expose file size before the download starts.
            # The progress hook will still show a stable first estimate when possible.
            pass

        with yt_dlp.YoutubeDL(ydl_options) as downloader:
            downloader.download([url])
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
            })
            curr_words = [w_text]
            curr_start = w_start
            curr_end = w_end
        else:
            if curr_start is None:
                curr_start = w_start
            curr_words.append(w_text)
            curr_end = max(curr_end, w_end)

    if curr_words and curr_start is not None:
        cues.append({
            "start": round(curr_start, 2),
            "end": round(curr_end, 2),
            "text": " ".join(curr_words),
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
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    # Some faster-whisper/PyAV combinations pass metadata_errors to av.open,
    # while older PyAV builds do not accept that keyword. The generated WAV is
    # local and already validated by FFmpeg, so dropping the optional keyword
    # is safe and keeps both versions compatible.
    try:
        import av

        original_av_open = av.open

        def compatible_av_open(*args: Any, **kwargs: Any) -> Any:
            kwargs.pop("metadata_errors", None)
            return original_av_open(*args, **kwargs)

        av.open = compatible_av_open  # type: ignore[assignment]
        try:
            segments, _ = model.transcribe(str(audio_path), language=language, vad_filter=True, word_timestamps=True)
        finally:
            av.open = original_av_open  # type: ignore[assignment]
    except ImportError:
        segments, _ = model.transcribe(str(audio_path), language=language, vad_filter=True, word_timestamps=True)
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


def heuristic_clips(
    transcript: list[dict[str, Any]],
    count: int,
    minimum: int,
    maximum: int,
    max_clips: int,
    profile: str = "auto",
) -> list[dict[str, Any]]:
    if not transcript:
        return []
    candidates = []
    keywords = {
        "cara", "tips", "rahasia", "penting", "terbaik", "ternyata", "mengapa", "kenapa",
        "how", "why", "secret", "mistake", "never", "best", "jangan", "bisa", "ingat",
    }
    if profile == "live":
        keywords |= {
            "anjir", "gila", "waduh", "astaga", "haha", "wkwk", "blunder", "salah",
            "menang", "kalah", "clutch", "chat", "stream", "serius", "tidak mungkin",
        }
    elif profile == "standard":
        keywords |= {"langkah", "contoh", "solusi", "hasil", "alasan", "pelajaran", "trik"}
    total = transcript[-1]["end"]
    effective_minimum = max(5, minimum)
    preferred = max(effective_minimum, int(round(maximum * 0.8))) if maximum > 0 else max(effective_minimum, 45)
    for anchor_index, anchor in enumerate(transcript):
        start = max(0.0, anchor["start"] - 3.0)
        end_index = anchor_index
        while end_index + 1 < len(transcript):
            candidate_end = transcript[end_index + 1]["end"]
            candidate_duration = candidate_end - start
            current_text = transcript[end_index]["text"]
            natural_break = bool(re.search(r"[.!?]$", current_text)) or transcript[end_index + 1]["start"] - transcript[end_index]["end"] > 0.9
            if maximum > 0 and candidate_duration > maximum:
                break
            end_index += 1
            # Jangan berhenti di kalimat pertama setelah minimum; sertakan
            # buildup dan payoff agar adegan tidak terasa terpotong.
            if candidate_duration >= preferred and natural_break:
                break
        end = min(total, transcript[end_index]["end"])
        if end - start < effective_minimum:
            end = min(total, start + effective_minimum)
        if end - start < effective_minimum:
            continue
        text_parts = [x["text"] for x in transcript if x["start"] < end and x["end"] > start]
        text = " ".join(text_parts).strip()
        token_list = words(text)
        if len(token_list) < 10:
            continue
        score = float(len(token_list)) / max(end - start, 1)
        score += sum(1.5 for token in token_list if token in keywords)
        score += text.count("!") * 1.5 + text.count("?")
        candidates.append({"start": start, "end": end, "score": score, "text": text})
    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected: list[dict[str, Any]] = []
    for candidate in candidates:
        overlaps = any(
            candidate["start"] < item["end"] and candidate["end"] > item["start"]
            for item in selected
        )
        if not overlaps:
            selected.append(candidate)
        target = count if count > 0 else max_clips
        if len(selected) >= target:
            break
    return selected


def broaden_smart_clips(
    transcript: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    minimum: int,
    maximum: int,
) -> list[dict[str, Any]]:
    """Add context around model-selected moments without exceeding the duration range."""
    if not transcript or not selected:
        return selected
    total = float(transcript[-1]["end"])
    effective_minimum = max(5, minimum)
    preferred = max(effective_minimum, int(round(maximum * 0.8))) if maximum > 0 else max(effective_minimum, 45)
    ordered = sorted(selected, key=lambda item: float(item.get("start", 0)))
    expanded: list[dict[str, Any]] = []
    cursor = 0.0
    for index, item in enumerate(ordered):
        original_start = max(0.0, float(item["start"]))
        original_end = min(total, float(item["end"]))
        next_start = float(ordered[index + 1]["start"]) if index + 1 < len(ordered) else total
        left_bound = cursor
        right_bound = max(original_end, min(total, next_start - 0.25))
        start = max(left_bound, original_start - 5.0)
        end = min(right_bound, original_end + 8.0)
        while end - start < preferred:
            next_items = [part for part in transcript if float(part["end"]) > end]
            if not next_items:
                break
            candidate_end = float(next_items[0]["end"])
            if candidate_end > right_bound:
                break
            end = candidate_end
        while end - start < minimum and start > left_bound:
            previous_items = [part for part in transcript if float(part["start"]) < start]
            if not previous_items:
                break
            start = max(left_bound, float(previous_items[-1]["start"]))
        if end - start < effective_minimum:
            start = max(left_bound, original_start)
            end = min(total, max(original_end, start + effective_minimum))
        updated = dict(item)
        updated["start"] = round(start, 3)
        max_cap = float(maximum) if maximum > 0 else 90.0
        updated["end"] = round(min(end, start + max_cap), 3)
        expanded.append(updated)
        cursor = updated["end"]
    return expanded


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
) -> None:
    if not clips:
        return
    custom_titles = [clip.source == "manual" and bool(clip.title.strip()) for clip in clips]
    for clip in clips:
        text = clip_transcript_text(transcript, clip.start, clip.end)
        clip.title, clip.caption, clip.hashtags = fallback_metadata(text, clip.title if clip.source == "manual" else "")

    
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
        "Bertindak sebagai editor short-form yang membuat hook kuat: title 3-8 kata harus spesifik, "
        "memancing rasa penasaran, atau menonjolkan konflik/manfaat. Caption maksimal 2 kalimat, "
        "mulai dengan hook, hindari kalimat datar seperti 'di video ini', dan boleh ditutup dengan "
        "pertanyaan yang mengundang komentar. Hashtags berupa array 3-6 hashtag yang relevan. "
        "Jangan membuat fakta atau klaim yang tidak ada di transkrip. Gunakan bahasa yang sama dengan transkrip.\n\nCLIPS:\n"
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
                model='gemini-3.8-flash',
                contents=f"Kamu adalah social media editor.\n{prompt}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.35,
                )
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


def ask_local_gguf(
    transcript: list[dict[str, Any]],
    count: int,
    minimum: int,
    maximum: int,
    model_name: str,
    max_clips: int,
    profile: str = "auto",
    custom_prompt: str = "",
) -> list[dict[str, Any]] | None:
    model = load_local_gguf(model_name)
    if model is None:
        return None

    prompt = (
        "Pilih segmen video paling menarik untuk short clip. Sertakan konteks adegan secara utuh: "
        "ambil buildup sebelum momen utama dan reaksi/payoff setelahnya, jangan hanya satu kalimat punchline. "
        "Balas HANYA JSON array valid, tanpa markdown, dengan field start, end, title. "
        f"Pilih {'sebanyak mungkin, maksimal ' + str(max_clips) if count == 0 else str(count)} segmen non-overlap dengan durasi "
        f"{'alami durasi 30-60 detik untuk shorts/reels' if minimum == 0 and maximum == 0 else f'{minimum}-{maximum} detik'}. "
        "Gunakan sebagian besar rentang durasi jika adegannya masih berlanjut, tanpa memotong setup atau reaksi penting. "
        "Judul harus singkat dan sesuai bahasa transkrip. "
        f"Profil momen: {CLIP_PROFILE_GUIDANCE.get(profile, CLIP_PROFILE_GUIDANCE['auto'])}\n"
        + (f"Instruksi tambahan dari user: {custom_prompt}\n" if custom_prompt.strip() else "")
        + "\nTRANSKRIP:\n"
        + json.dumps(transcript, ensure_ascii=False)
    )
    try:
        response = model.create_chat_completion(
            messages=[
                {"role": "system", "content": "Kamu adalah editor video yang memilih momen paling engaging."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        content = response["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            parsed = parsed.get("clips", [])
        valid = []
        effective_max = float(maximum) if maximum > 0 else 90.0
        for item in parsed:
            start = float(item["start"])
            end = float(item["end"])
            duration = end - start
            if end > start and (minimum == 0 or duration >= minimum) and duration <= effective_max:
                valid.append({"start": start, "end": end, "score": 100.0, "title": str(item.get("title", "Highlight"))})
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
) -> list[dict[str, Any]] | None:
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = (
            "Pilih segmen video paling menarik untuk short clip. Sertakan konteks adegan secara utuh: "
            "ambil buildup sebelum momen utama dan reaksi/payoff setelahnya, jangan hanya satu kalimat punchline. "
            "Balas HANYA JSON array valid, tanpa markdown, dengan field start, end, title. "
            f"Pilih {'sebanyak mungkin, maksimal ' + str(max_clips) if count == 0 else str(count)} segmen non-overlap dengan durasi "
            f"{'alami durasi 30-60 detik untuk shorts/reels' if minimum == 0 and maximum == 0 else f'{minimum}-{maximum} detik'}. "
            "Judul harus singkat dan sesuai bahasa transkrip. "
            f"Profil momen: {CLIP_PROFILE_GUIDANCE.get(profile, CLIP_PROFILE_GUIDANCE['auto'])}\n"
            + (f"Instruksi tambahan dari user: {custom_prompt}\n" if custom_prompt.strip() else "")
            + "\nTRANSKRIP:\n"
            + json.dumps(transcript, ensure_ascii=False)
        )
        
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            )
        )
        parsed = json.loads(response.text)
        if isinstance(parsed, dict):
            parsed = parsed.get("clips", parsed) # some models wrap it in 'clips' key
        
        valid = []
        effective_max = float(maximum) if maximum > 0 else 90.0
        for item in parsed:
            start = float(item["start"])
            end = float(item["end"])
            duration = end - start
            if end > start and (minimum == 0 or duration >= minimum) and duration <= effective_max:
                valid.append({"start": start, "end": end, "score": 100.0, "title": str(item.get("title", "Highlight"))})
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





def write_srt(transcript: list[dict[str, Any]], start: float, end: float, path: Path, max_lines: int = 2) -> None:
    lines: list[str] = []
    index = 1
    for item in transcript:
        item_start = max(0.0, item["start"] - start)
        item_end = min(end - start, item["end"] - start)
        if item_end <= 0 or item_start >= end - start:
            continue
        cues = split_segment_into_cues(item_start, item_end, item.get("text", ""), max_lines=max_lines)
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


def detect_face_crop(video_path: Path) -> tuple[int, int, int, int] | None:
    """Return x, y, width, height for a facecam crop, or None when no face is found."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Mode Facecam di atas membutuhkan paket opencv-python.") from exc

    capture = cv2.VideoCapture(str(video_path))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if width <= 0 or height <= 0:
        capture.release()
        return None
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    best_face = None
    sample_points = [0, max(0, frame_count // 3), max(0, frame_count // 2), max(0, frame_count * 2 // 3)]
    for frame_index in sample_points:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(32, 32))
        for face in faces:
            if best_face is None or face[2] * face[3] > best_face[2] * best_face[3]:
                best_face = face
    capture.release()
    if best_face is None:
        return None

    face_x, face_y, face_w, face_h = [int(value) for value in best_face]
    crop_w = min(width, max(face_w * 4, int(width * 0.28)))
    crop_h = min(height, max(face_h * 4, int(crop_w * 9 / 16)))
    center_x = face_x + face_w // 2
    center_y = face_y + face_h // 2
    crop_x = max(0, min(width - crop_w, center_x - crop_w // 2))
    crop_y = max(0, min(height - crop_h, center_y - crop_h // 2))
    return crop_x, crop_y, crop_w, crop_h


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
    top_height = int(height * 0.34)
    bottom_height = height - top_height
    return (
        f"split=2[face][main];"
        f"[face]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={width}:{top_height}:force_original_aspect_ratio=increase,crop={width}:{top_height}[faceout];"
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
    clip_dir.mkdir(exist_ok=True)
    subtitle_path = clip_dir / "subtitle.srt"
    output_path = clip_dir / "clip.mp4"
    max_lines = getattr(options, "subtitle_max_lines", 2)
    font_size = getattr(options, "subtitle_font_size", 14)
    write_srt(transcript, clip.start, clip.end, subtitle_path, max_lines=max_lines)
    layout_filter = video_layout_filter(options.aspect_ratio, options.framing, options.layout, face_crop)
    if options.subtitle_style == "none":
        video_filter = layout_filter
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
    enc_args, enc_name = get_encoder_args(getattr(options, "video_encoder", "auto"))
    resolved_video = str(Path(video).resolve())
    cmd = (
        ffmpeg_command()
        + [
            "-y",
            "-ss", f"{clip.start:.3f}",
            "-to", f"{clip.end:.3f}",
            "-i", resolved_video,
            "-vf", video_filter,
        ]
        + enc_args
        + [
            "-c:a", "aac",
            "-movflags", "+faststart",
            "clip.mp4",
        ]
    )
    clip_duration = max(1.0, clip.end - clip.start)
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
            fallback_cmd = (
                ffmpeg_command()
                + [
                    "-y",
                    "-ss", f"{clip.start:.3f}",
                    "-to", f"{clip.end:.3f}",
                    "-i", resolved_video,
                    "-vf", video_filter,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "21",
                    "-c:a", "aac",
                    "-movflags", "+faststart",
                    "clip.mp4",
                ]
            )
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
        "subtitle_position": options.subtitle_position,
        "subtitle_x": str(options.subtitle_x),
        "subtitle_y": str(options.subtitle_y),
        "aspect_ratio": options.aspect_ratio,
        "framing": options.framing,
        "layout": options.layout,
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

    # URL metadata can survive a failed/interrupted render, so verify the actual
    # files before deciding that a clip is already available.
    targets = [clip for clip in clips if not skip_existing or not rendered_file(clip)]
    if not targets:
        update_job(job_id, progress=progress_end, message="Semua clip sudah dirender; menyiapkan hasil akhir...")
        return
    face_crop = detect_face_crop(video) if options.layout == "facecam_top" else None
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
            selected = broaden_smart_clips(transcript, selected, smart_min, smart_max)
        clips = []
        for index, item in enumerate(selected, start=1):
            clip = Clip(
                id=f"clip-{index:02}",
                start=float(item["start"]),
                end=float(item["end"]),
                score=float(item.get("score", 0)),
                title=str(item.get("title") or f"Highlight {index}"),
                source="ai",
            )
            clips.append(clip)
        update_job(job_id, progress=62, sub_progress=40, message="Mencari momen terbaik dengan AI...", sub_message=f"Model {options.local_model.upper()} menganalisis transkrip...")
        update_job(job_id, clips=clips, progress=68, sub_progress=75, message="Membuat metadata (Judul, Caption, Hashtag)...", sub_message="AI mengoptimalkan hook dan copywriting klip...")
        generate_clip_metadata(transcript, clips, options.local_model)
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


# ============================================================================
# TIKTOK INTEGRATION
# ============================================================================
TIKTOK_SESSION_FILE = ROOT / "tiktok_session.json"


@app.get("/api/tiktok/status")
def get_tiktok_status() -> dict[str, Any]:
    return {
        "session_exists": TIKTOK_SESSION_FILE.is_file(),
        "session_path": str(TIKTOK_SESSION_FILE),
    }


class TikTokUploadRequest(BaseModel):
    headless: bool = False
    custom_caption: str | None = None


@app.post("/api/jobs/{job_id}/clips/{clip_id}/upload-tiktok")
def upload_clip_to_tiktok_endpoint(
    job_id: str,
    clip_id: str,
    req: TikTokUploadRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job tidak ditemukan")
        clip = next((c for c in job.clips if c.id == clip_id), None)
        if not clip:
            raise HTTPException(status_code=404, detail="Clip tidak ditemukan")

    job_dir = Path(job.job_dir)
    clip_dir = clip_result_dir(job_dir, clip.id, clip.title)
    video_path = clip_dir / "clip.mp4"

    if not video_path.is_file():
        raise HTTPException(
            status_code=400,
            detail="File video clip belum dirender. Silakan render clip terlebih dahulu.",
        )

    if not TIKTOK_SESSION_FILE.is_file():
        raise HTTPException(
            status_code=400,
            detail="Sesi login TikTok belum ada. Silakan jalankan login_tiktok.bat terlebih dahulu.",
        )

    caption = req.custom_caption or (
        f"{clip.caption} {' '.join(clip.hashtags)}".strip() or clip.title
    )

    from Backend_API.tiktok_uploader import upload_to_tiktok

    background_tasks.add_task(
        upload_to_tiktok,
        video_path=video_path,
        caption=caption,
        session_path=TIKTOK_SESSION_FILE,
        headless=req.headless,
    )

    return {
        "status": "processing",
        "message": f"Upload klip '{clip.title}' ke TikTok sedang berjalan di background.",
        "video": str(video_path),
        "caption": caption,
    }

