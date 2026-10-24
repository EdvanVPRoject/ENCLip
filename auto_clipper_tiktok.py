"""

ENCLip - Autonomous Viral Podcast Clipper & TikTok Scheduler (All-in-One Antigravity Edition)

=============================================================================================

1. Smart Adaptive Multi-Face Layout (`auto_smart` dengan 100% Gemini Vision AI Director):

   - 0 Wajah (Artikel/Teks/Presentasi): Utuh di tengah (letterbox/blur), subtitle otomatis di bawah.

   - 1 Wajah (1 Orang Disorot): Fokus tepat di tengah layar (9:16 penuh), subtitle otomatis di bawah.

   - 2 Wajah (2 Orang Podcast): Split Atas-Bawah fokus wajah kiri & kanan, subtitle di tengah.

   - 3 Wajah (2 Berdekatan + 1 Terpisah): Split 2 Panel (Atas 2 orang, Bawah 1 orang), subtitle di tengah.

   - 3 Wajah (Sejajar Kiri-Tengah-Kanan): Split 3 Panel Atas-Tengah-Bawah, subtitle di bawah.

   - 4 Wajah (2 Pasang Berdekatan): Split 2 Panel (Atas 2 orang kiri, Bawah 2 orang kanan), subtitle di tengah.

2. Siklus Tanya-Jawab Utuh (Full Context Auto-Heal & Anti-Duplikat Durasi):

   - Klip selalu dimulai dari awal pernyataan/pertanyaan hingga akhir jawaban sebelum pertanyaan baru.

   - Dijamin tidak memotong di tengah kalimat penjelasan dan tidak menghasilkan judul menggantung.

3. Full Render Malam-Pagi (01:00 - 07:00 WIB) & Siang Hemat Laptop (CPU 0%):

   - Selesai render 1 video podcast otomatis lanjut ke video berikutnya tanpa batas klip per video,

     serta melaporkan jumlah file yang siap di-upload setiap kali selesai.

4. Mendukung flag modular background automation:

   - `--produce-only`: Cari & render klip dari 1 podcast ke antrean stok (upload_queue.json).

   - `--upload-only`: Ambil 1 video dari antrean stok dan publikasikan ke TikTok.

"""



from __future__ import annotations



import argparse

import difflib

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

from datetime import datetime, timedelta

from pathlib import Path

from typing import Any



if sys.platform.startswith("win"):

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ENCLip.Studio.Uploader")
        u32 = ctypes.windll.user32
        h_desk = u32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            u32.SetThreadDesktop(h_desk)

    except Exception:

        pass



CURRENT_DIR = Path(__file__).resolve().parent

if str(CURRENT_DIR) not in sys.path:

    sys.path.insert(0, str(CURRENT_DIR))



logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s [%(levelname)s] %(message)s",

    datefmt="%H:%M:%S",

)

logger = logging.getLogger("AntigravityClipper")



CORE_DATA_DIR = CURRENT_DIR / "Core_Data"

BGM_DIR = CORE_DATA_DIR / "bgm"

CORE_DATA_DIR.mkdir(parents=True, exist_ok=True)

BGM_DIR.mkdir(parents=True, exist_ok=True)



DEFAULT_SESSION_FILE = CORE_DATA_DIR / "tiktok_session.json"
DEFAULT_HISTORY_FILE = CORE_DATA_DIR / "auto_history.json"
DEFAULT_QUEUE_FILE = CORE_DATA_DIR / "upload_queue.json"
UPLOADED_CLIPS_TXT = CORE_DATA_DIR / "uploaded_clips.txt"
PROJECT_UPLOADED_TXT = CURRENT_DIR / "uploaded_clips.txt"


def append_to_uploaded_txt(clip_info: dict[str, Any]) -> None:
    """Mencatat rincian klip yang berhasil diunggah ke dokumen teks (.txt)."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB")
    title = clip_info.get("clip_title") or "Klip Video"
    score = clip_info.get("clip_score", 0.0)
    dur = round(clip_info.get("clip_end", 0.0) - clip_info.get("clip_start", 0.0), 1)
    v_title = clip_info.get("video_title") or "-"
    channel = clip_info.get("channel") or "-"
    v_url = clip_info.get("video_url") or "-"
    c_path = clip_info.get("clip_path") or "-"
    caption = clip_info.get("caption") or "-"

    entry = (
        f"================================================================================\n"
        f"WAKTU UPLOAD : {now_str}\n"
        f"JUDUL KLIP   : {title}\n"
        f"SKOR VIRAL   : {score}%\n"
        f"DURASI KLIP  : {dur} detik\n"
        f"SUMBER VIDEO : {v_title} ({channel})\n"
        f"URL SUMBER   : {v_url}\n"
        f"BERKAS ASLI  : {c_path} [STATUS: DIHAPUS DARI DISK SETELAH SUKSES]\n"
        f"CAPTION & HASHTAGS:\n"
        f"{caption}\n"
        f"================================================================================\n\n"
    )

    for txt_path in [UPLOADED_CLIPS_TXT, PROJECT_UPLOADED_TXT]:
        try:
            with open(txt_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as exc:
            logger.warning(f"Gagal mencatat ke {txt_path}: {exc}")


def cleanup_uploaded_video_file(clip_path: Path) -> None:
    """Menghapus file video klip lokal dan foldernya setelah upload sukses."""
    try:
        if clip_path.is_file():
            clip_path.unlink(missing_ok=True)
            logger.info(f"🗑️ File video lokal telah dihapus setelah upload sukses: {clip_path.name}")

        parent_dir = clip_path.parent
        if parent_dir.is_dir():
            mp4_remaining = list(parent_dir.glob("*.mp4"))
            if not mp4_remaining:
                shutil.rmtree(parent_dir, ignore_errors=True)
                logger.info(f"🗑️ Folder klip telah dibersihkan: {parent_dir.name}")
    except Exception as exc:
        logger.warning(f"Gagal menghapus file klip {clip_path}: {exc}")





def set_low_cpu_priority() -> None:

    try:

        if sys.platform.startswith("win"):

            import ctypes

            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

            ctypes.windll.kernel32.SetPriorityClass(

                ctypes.windll.kernel32.GetCurrentProcess(),

                BELOW_NORMAL_PRIORITY_CLASS,

            )

        else:

            os.nice(10)

    except Exception:

        pass





if "WHISPER_DEVICE" not in os.environ:

    os.environ["WHISPER_DEVICE"] = "cpu"

    os.environ["WHISPER_COMPUTE_TYPE"] = "int8"

    try:

        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:

            import numpy as np

            from faster_whisper import WhisperModel

            test_m = WhisperModel("small", device="cuda", compute_type="float16")

            list(test_m.transcribe(np.zeros(16000, dtype=np.float32))[0])

            os.environ["WHISPER_DEVICE"] = "cuda"

            os.environ["WHISPER_COMPUTE_TYPE"] = "float16"

            logger.info("⚡ NVIDIA GPU (CUDA) cuBLAS aktif untuk akselerasi transkripsi.")

    except Exception:

        logger.info("ℹ️ Menggunakan CPU multi-core (int8) untuk Whisper transkripsi.")





def is_in_edit_window(start_hour: int = 1, end_hour: int = 7, now: datetime | None = None) -> bool:

    now = now or datetime.now()

    curr_h = now.hour

    if start_hour <= end_hour:

        return start_hour <= curr_h < end_hour

    return curr_h >= start_hour or curr_h < end_hour





def next_edit_window_datetime(start_hour: int = 1, now: datetime | None = None) -> datetime:

    now = now or datetime.now()

    candidate = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)

    if candidate <= now:

        candidate += timedelta(days=1)

    return candidate





def ensure_default_bgm(custom_bgm_path: str = "") -> str:

    if custom_bgm_path and Path(custom_bgm_path).is_file():

        return str(Path(custom_bgm_path).resolve())



    existing_bgm: list[Path] = []

    for ext in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg"):

        existing_bgm.extend(BGM_DIR.glob(ext))

    if existing_bgm:

        return str(random.choice(existing_bgm).resolve())



    generated_bgm = BGM_DIR / "ambient_podcast_anticopyright.wav"

    if generated_bgm.is_file() and generated_bgm.stat().st_size > 50_000:

        return str(generated_bgm.resolve())



    try:

        from Backend_API.web_server import ffmpeg_command

        ffmpeg_bin = ffmpeg_command()

        logger.info("🎵 Membuat BGM Ambient Lo-Fi otomatis (Anti-Copyright Volume Kecil)...")

        lavfi_expr = (

            "aevalsrc='0.11*sin(2*PI*130.81*t)+0.09*sin(2*PI*164.81*t)"

            "+0.08*sin(2*PI*196.00*t)+0.07*sin(2*PI*246.94*t)+0.05*sin(2*PI*293.66*t)"

            "*(0.65+0.35*sin(2*PI*0.22*t))':s=44100:d=90,"

            "lowpass=f=620,afade=t=in:st=0:d=2.5,afade=t=out:st=87:d=3"

        )

        subprocess.run(

            ffmpeg_bin + ["-y", "-f", "lavfi", "-i", lavfi_expr, "-c:a", "pcm_s16le", str(generated_bgm)],

            capture_output=True,

            check=True,

        )

        if generated_bgm.is_file():

            return str(generated_bgm.resolve())

    except Exception as exc:

        logger.warning(f"Gagal membuat BGM otomatis ({exc}).")

    return ""





def normalize_title_key(title: str) -> str:

    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", (title or "").lower())

    return re.sub(r"\s+", " ", clean).strip()





class HistoryTracker:

    def __init__(self, history_file: Path = DEFAULT_HISTORY_FILE, queue_file: Path = DEFAULT_QUEUE_FILE) -> None:

        self.history_file = Path(history_file)

        self.queue_file = Path(queue_file)

        self.data: dict[str, Any] = {

            "processed_ids": [],

            "processed_titles": [],

            "clipped_ranges": {},

            "last_query_index": -1,

            "items": [],

        }

        self.queue: list[dict[str, Any]] = []

        self.load()



    def load(self) -> None:

        if self.history_file.is_file():

            try:

                loaded = json.loads(self.history_file.read_text(encoding="utf-8"))

                if isinstance(loaded, dict):

                    self.data.update(loaded)

            except Exception:

                pass



        self.data.setdefault("processed_ids", [])

        self.data.setdefault("processed_titles", [])

        self.data.setdefault("clipped_ranges", {})

        self.data.setdefault("last_query_index", -1)

        self.data.setdefault("items", [])



        for item in self.data["items"]:

            t_norm = normalize_title_key(item.get("video_title", ""))

            if t_norm and t_norm not in self.data["processed_titles"]:

                self.data["processed_titles"].append(t_norm)

            vid = item.get("video_id")

            if vid and vid not in self.data["processed_ids"]:

                self.data["processed_ids"].append(vid)



        hasil_dir = CORE_DATA_DIR / "HasilClip"

        if hasil_dir.is_dir():

            for sub in hasil_dir.iterdir():

                if sub.is_dir() and not sub.name.startswith("."):

                    t_norm = normalize_title_key(sub.name)

                    if t_norm and t_norm not in self.data["processed_titles"]:

                        self.data["processed_titles"].append(t_norm)



        if self.queue_file.is_file():

            try:

                q_data = json.loads(self.queue_file.read_text(encoding="utf-8"))

                if isinstance(q_data, list):

                    self.queue = [q for q in q_data if Path(q.get("clip_path", "")).is_file()]

            except Exception:

                self.queue = []



    def save(self) -> None:

        try:

            self.history_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

            self.queue_file.write_text(json.dumps(self.queue, indent=2, ensure_ascii=False), encoding="utf-8")

        except Exception as e:

            logger.error(f"Gagal menyimpan riwayat/antrean: {e}")



    def ready_to_upload_count(self) -> int:

        self.queue = [q for q in self.queue if Path(q.get("clip_path", "")).is_file()]

        return len(self.queue)



    def is_already_clipped(self, video_id: str, video_title: str = "") -> bool:

        if video_id and video_id in self.data["processed_ids"]:

            return True

        if any(q.get("video_id") == video_id for q in self.queue if video_id):

            return True



        norm_candidate = normalize_title_key(video_title)

        if norm_candidate:

            for existing_norm in self.data["processed_titles"]:

                if norm_candidate == existing_norm:

                    return True

                if len(norm_candidate) > 15 and difflib.SequenceMatcher(None, norm_candidate, existing_norm).ratio() >= 0.86:

                    return True

        return False



    def is_range_already_clipped(self, video_id: str, start_sec: float, end_sec: float) -> bool:

        if not video_id:

            return False

        for q in self.queue:

            if q.get("video_id") == video_id:

                qs, qe = float(q.get("clip_start", 0.0)), float(q.get("clip_end", 0.0))

                if start_sec < (qe - 2.0) and end_sec > (qs + 2.0):

                    return True

        for r in self.data.get("clipped_ranges", {}).get(video_id, []):

            rs, re_val = float(r.get("start", 0.0)), float(r.get("end", 0.0))

            if start_sec < (re_val - 2.0) and end_sec > (rs + 2.0):

                return True

        return False



    def mark_video_processed(self, video_meta: dict[str, Any]) -> None:

        vid = str(video_meta.get("id") or "")

        title = str(video_meta.get("title") or "")

        if vid and vid not in self.data["processed_ids"]:

            self.data["processed_ids"].append(vid)

        norm_t = normalize_title_key(title)

        if norm_t and norm_t not in self.data["processed_titles"]:

            self.data["processed_titles"].append(norm_t)

        self.save()



    def enqueue_clips(self, video_meta: dict[str, Any], clips_list: list[dict[str, Any]]) -> int:

        added = 0

        vid = str(video_meta.get("id") or "")

        for clip_meta in clips_list:

            c_path = str(clip_meta.get("path", ""))

            if not c_path or not Path(c_path).is_file():

                continue

            c_start = float(clip_meta.get("start", 0.0))

            c_end = float(clip_meta.get("end", 0.0))

            if self.is_range_already_clipped(vid, c_start, c_end):

                continue

            if any(q.get("clip_path") == c_path for q in self.queue):

                continue

            self.queue.append({

                "queued_at": datetime.now().isoformat(),

                "video_id": vid,

                "video_title": video_meta.get("title", ""),

                "channel": video_meta.get("channel", ""),

                "view_count": video_meta.get("view_count", 0),

                "video_url": video_meta.get("url", ""),

                "clip_id": clip_meta.get("id", ""),

                "clip_title": clip_meta.get("title", ""),

                "clip_start": c_start,

                "clip_end": c_end,

                "clip_score": clip_meta.get("score", 90.0),

                "clip_path": c_path,

                "caption": clip_meta.get("caption", ""),

                "hashtags": clip_meta.get("hashtags", []),

            })

            added += 1

        self.mark_video_processed(video_meta)

        self.save()

        return added



    def pop_next_queued_clip(self) -> dict[str, Any] | None:

        while self.queue:

            item = self.queue.pop(0)

            if Path(item.get("clip_path", "")).is_file():

                self.save()

                return item

        self.save()

        return None



    def record_upload(self, queued_item: dict[str, Any], uploaded: bool) -> None:

        vid = str(queued_item.get("video_id") or "")

        if vid:

            ranges = self.data["clipped_ranges"].setdefault(vid, [])

            ranges.append({

                "start": queued_item.get("clip_start", 0.0),

                "end": queued_item.get("clip_end", 0.0),

                "title": queued_item.get("clip_title", ""),

                "timestamp": datetime.now().isoformat(),

            })

        entry = dict(queued_item)

        entry["timestamp"] = datetime.now().isoformat()

        entry["uploaded_tiktok"] = uploaded

        self.data["items"].append(entry)

        self.save()



    def next_search_query(self, user_query: str) -> str:

        if user_query and user_query.strip().lower() not in ("podcast viral indonesia", "auto", ""):

            return user_query.strip()

        idx = (int(self.data.get("last_query_index", -1)) + 1) % len(VIRAL_SEARCH_PRESETS)

        self.data["last_query_index"] = idx

        self.save()

        return VIRAL_SEARCH_PRESETS[idx]





VIRAL_SEARCH_PRESETS = [

    "curhat bang denny sumargo podcast terbaru",

    "close the door deddy corbuzier podcast terbaru",

    "pwk podcast warung kopi has creative terbaru",

    "podhub deddy corbuzier vidi podcast terbaru",

    "vindes podcast terbaru",

    "total politik podcast terbaru",

    "kasisolusi podcast terbaru",

    "raditya dika podcast terbaru",

    "dr richard lee podcast terbaru",

    "pandji pragiwaksono podcast terbaru",

    "dr tirta podcast ngobrol terbaru",

    "gita wirjawan endgame podcast terbaru",

    "helmy yahya bicara podcast terbaru",

    "kemal palevi podcast terbaru",

    "akbar faizal uncensored podcast terbaru",

    "komika podcast indonesia viral terbaru",

]





def search_viral_videos(

    query: str = "auto",

    min_views: int = 35_000,

    min_duration_sec: int = 1800,

    max_duration_sec: int = 12600,

    limit: int = 35,

    history_tracker: HistoryTracker | None = None,

    trend_hijacker: bool = True,

) -> list[dict[str, Any]]:

    import yt_dlp

    from Backend_API.web_server import fetch_current_viral_trends_ws, get_trend_hijacker_queries



    viral_trends = fetch_current_viral_trends_ws()

    primary_query = history_tracker.next_search_query(query) if history_tracker else (

        random.choice(VIRAL_SEARCH_PRESETS) if query in ("auto", "podcast viral indonesia") else query

    )



    if trend_hijacker and query in ("auto", "podcast viral indonesia"):

        logger.info("🔥 [Trend Hijacker Aktif] Memadukan tren Google & Twitter Indonesia terkini...")

        trend_queries = get_trend_hijacker_queries(limit=6)

    else:

        trend_queries = [f"podcast indonesia {t}" for t in viral_trends[:3] if len(t) > 2]



    other_presets = [q for q in VIRAL_SEARCH_PRESETS if q != primary_query]

    random.shuffle(other_presets)

    queries_to_scan = trend_queries[:4] + [primary_query] + trend_queries[4:] + other_presets[:4]



    ydl_opts = {

        "quiet": True,

        "no_warnings": True,

        "extract_flat": True,

        "skip_download": True,

    }



    fresh_candidates: list[dict[str, Any]] = []

    skipped_count = 0



    for q in queries_to_scan:

        logger.info(f"🔎 Memindai YouTube untuk podcast baru (durasi minimal 30 menit): '{q}'...")

        search_query = f"ytsearch{limit}:{q}"

        try:

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                res = ydl.extract_info(search_query, download=False)

                entries = res.get("entries", []) if res else []

                for entry in entries:

                    if not entry:

                        continue

                    v_id = entry.get("id")

                    v_title = entry.get("title", "Video Tanpa Judul")

                    v_views = entry.get("view_count") or 0

                    v_duration = entry.get("duration") or 0

                    v_channel = entry.get("channel") or entry.get("uploader") or "Podcast"

                    v_url = entry.get("webpage_url") or f"https://www.youtube.com/watch?v={v_id}"



                    if not v_id or any(c["id"] == v_id for c in fresh_candidates):

                        continue



                    if history_tracker and history_tracker.is_already_clipped(v_id, v_title):

                        skipped_count += 1

                        continue



                    if v_duration and (v_duration < min_duration_sec or v_duration > max_duration_sec):

                        continue



                    if v_views < min_views:

                        continue



                    title_low = v_title.lower()

                    if any(bad in title_low for bad in ["#shorts", "shorts", "teaser", "cuplikan", "trailer", "monolog"]):

                        continue



                    trend_matches = sum(1 for t in viral_trends if t in title_low)

                    ranking_score = v_views * (1.0 + (0.85 * trend_matches))

                    if trend_matches > 0:

                        logger.info(f"🎯 [Trend Hijacker] Terdeteksi podcast viral relevan: '{v_title}' (+{trend_matches * 85}% bobot)")



                    fresh_candidates.append({

                        "id": v_id,

                        "title": v_title,

                        "url": v_url,

                        "view_count": v_views,

                        "ranking_score": ranking_score,

                        "duration": v_duration,

                        "channel": v_channel,

                    })

        except Exception as exc:

            logger.warning(f"Pencarian '{q}' terkendala: {exc}")



        if len(fresh_candidates) >= 8:

            break



    fresh_candidates.sort(key=lambda x: x.get("ranking_score", x["view_count"]), reverse=True)

    logger.info(

        f"✅ Ditemukan {len(fresh_candidates)} video podcast BARU (durasi >= 30 mnt, melewati {skipped_count} video lama)."

    )

    return fresh_candidates





def extract_speaker_or_topic_hint(video_title: str, channel_name: str) -> str:

    clean = re.sub(r"[\(\[\{].*?[\)\]\}]", "", video_title)

    parts = re.split(r"[-|–—:]", clean)

    core_part = parts[0].strip() if parts else clean.strip()

    words_list = [

        w for w in core_part.split()

        if w.lower() not in {"podcast", "eps", "episode", "full", "terbaru", "viral"}

    ]

    if len(words_list) >= 2:

        return " ".join(words_list[:4]).title()

    return channel_name or "Podcast"





_LEADING_FILLER_PATTERN = re.compile(

    r"^(?:kalau\s+tau\s+kan|kalo\s+tau\s+kan|kalau\s+kan|nah\s+kalau|jadi\s+waktu\s+itu|"

    r"kalau|kalo|karena|sebab|jadi|terus|lalu|tapi|tetapi|namun|makanya|soalnya|padahal|"

    r"nah|eh|iya|ya|oh|kan)\b[\s,.:;-]*",

    flags=re.IGNORECASE,

)



_TRAILING_HANGING_WORDS = {

    "nya", "ususnya", "kan", "gini", "gitu", "dong", "deh", "sih", "yang",

    "dan", "atau", "di", "ke", "dari", "itu", "ini", "sama", "buat", "kalau", "kalo",

}





def clean_and_validate_hook_title(raw_title: str, speaker_hint: str) -> str:

    """

    Membersihkan judul dari potongan kalimat mentah yang menggantung

    (seperti 'Kalau tau kan, barang segera gini. Ususnya') dan memastikan

    judul terdiri dari 4-7 kata utuh yang jelas maknanya.

    """

    clean = re.sub(r"[#@⁉️‼️🤣😂🔥]+", "", raw_title or "").strip().strip('"').strip("'")

    clean = re.sub(r"\s+", " ", clean).strip()



    # Jika terdapat titik di tengah (lebih dari 1 kalimat terpotong), ambil kalimat yang paling utuh & bermakna

    if "." in clean:

        parts = [p.strip() for p in clean.split(".") if p.strip()]

        if parts:

            clean = max(parts, key=lambda seg: len(seg.split()))



    # Bersihkan awalan kata sambung/basa-basi berulang kali

    for _ in range(2):

        clean = _LEADING_FILLER_PATTERN.sub("", clean).strip()



    # Jika ada koma yang memisahkan klausa gantung pendek di depan, ambil klausa utama

    if "," in clean:

        comma_parts = [p.strip() for p in clean.split(",") if p.strip()]

        if len(comma_parts) >= 2 and len(comma_parts[0].split()) <= 3:

            clean = " ".join(comma_parts[1:]).strip()

        else:

            clean = comma_parts[0].strip()



    tokens = clean.split()

    while tokens and re.sub(r"[^a-zA-Z0-9]", "", tokens[-1]).lower() in _TRAILING_HANGING_WORDS:

        tokens.pop()



    # Batasi maksimal 7 kata agar pas di Hook Banner 2 baris

    if len(tokens) > 7:

        tokens = tokens[:7]

        while tokens and re.sub(r"[^a-zA-Z0-9]", "", tokens[-1]).lower() in _TRAILING_HANGING_WORDS:

            tokens.pop()



    final_title = " ".join(tokens).strip(" .,;:-")

    if len(final_title.split()) < 3:

        return f"Fakta Menarik Bersama {speaker_hint}"

    return final_title.title()





def format_curiosity_hook_and_caption(

    raw_clip_title: str,

    raw_clip_caption: str,

    raw_hashtags: list[str],

    video_meta: dict[str, Any],

    clip_start: float = 0.0,

) -> tuple[str, str]:

    speaker_hint = extract_speaker_or_topic_hint(video_meta.get("title", ""), video_meta.get("channel", "Podcast"))

    clean_title = clean_and_validate_hook_title(raw_clip_title, speaker_hint)



    banner_hook = clean_title.upper()

    if not banner_hook.endswith(("?", "!")):

        banner_hook = banner_hook.rstrip(".")



    caption_body = (raw_clip_caption or "").strip()

    if not caption_body or len(caption_body.split()) < 6:

        caption_body = (

            f"Simak pembahasan lengkapnya dari awal sampai akhir biar konteksnya utuh! "

            f"Bagaimana pendapat kalian soal obrolan di {video_meta.get('channel', 'Podcast')} ini? 👇"

        )



    channel_name = str(video_meta.get("channel") or "").strip()

    speaker_line = ""

    if speaker_hint and speaker_hint.lower() not in clean_title.lower() and speaker_hint.lower() not in {"podcast", "channel"}:

        if channel_name and channel_name.lower() not in speaker_hint.lower() and channel_name.lower() != "podcast":

            speaker_line = f"🎙️ {speaker_hint} di {channel_name}:\n"

        else:

            speaker_line = f"🎙️ {speaker_hint}:\n"



    base_tags = ["#podcastindonesia", "#fyp", "#potonganpodcast", "#viral", "#foryou", "#edukasi"]

    merged_tags = list(dict.fromkeys([t if t.startswith("#") else f"#{t}" for t in (raw_hashtags or [])] + base_tags))[:7]

    tag_str = " ".join(merged_tags)



    if speaker_line:

        full_tiktok_caption = f"{speaker_line}{clean_title} 👀🔥\n\n{caption_body}\n\n{tag_str}"

    else:

        full_tiktok_caption = f"{clean_title} 👀🔥\n\n{caption_body}\n\n{tag_str}"

    return banner_hook, full_tiktok_caption





def process_viral_video_with_enclip(

    video_meta: dict[str, Any],

    flavor: str = "spicy_drama",

    layout: str = "standard",

    framing: str = "crop",

    aspect_ratio: str = "16:9",

    skip_if_has_subtitles: bool = True,

    max_clips: int = 0,

    clip_min: int = 45,

    clip_max: int = 125,

    bgm_path: str = "",

    bgm_volume: float = 0.08,

    use_ai_model: str = "gemini",

    quality: str = "1080",

    emoji_subtitles: bool = True,

    micro_zoom: bool = True,

    auto_broll: bool = False,

    broll_folder: str = "",

) -> list[dict[str, Any]]:

    set_low_cpu_priority()

    try:
        from clipper_hud import launch_hud_process
        launch_hud_process()
    except Exception:
        pass

    from Backend_API.web_server import (

        CreateJobRequest,

        Job,

        JOBS,

        JOBS_LOCK,

        JOB_OPTIONS,

        clip_result_dir,

        get_active_gemini_api_key,

        job_result_dir,

        process_job,

    )



    # Pastikan GEMINI_API_KEY aktif dari .env ataupun QSettings GUI

    active_key = get_active_gemini_api_key()

    if active_key:

        logger.info("🔑 Gemini API Key aktif untuk AI Vision Camera-Director & Q&A Context Engine.")



    job_id = f"auto_{int(time.time())}"

    video_url = video_meta["url"]

    effective_bgm = ensure_default_bgm(bgm_path)

    effective_max_clips = max_clips if max_clips > 0 else 8



    logger.info("=" * 74)

    logger.info("🎬 MEMULAI AUTO CLIPPER (100% GEMINI VISION AI CAMERA-DIRECTOR):")

    logger.info(f"   Judul Video    : {video_meta['title']}")

    logger.info(f"   Channel & Views: {video_meta['channel']} ({video_meta['view_count']:,} views)")

    logger.info(f"   Mode Framing   : {framing} (✨ Center-Locked Fokus Manusia Hidup)")

    logger.info(f"   Mode Layout    : {layout} (1=Full Tengah | 2/4=Split 2 | 3=Grup/3-Panel | 0=Utuh)")

    logger.info(f"   Mode Klip      : Siklus Tanya-Jawab Utuh ({clip_min}s s/d {clip_max}s)")

    logger.info(f"   Kualitas Sumber: {quality}p (HD Optimal & Cepat)")

    logger.info("=" * 74)



    qa_prompt = (

        "Potong per SIKLUS TANYA-JAWAB UTUH: Mulai tepat dari awal kalimat pertanyaan/topik pembuka hingga akhir jawaban "

        "tuntas. Dilarang memulai klip dari tengah jawaban ('Kalau...', 'Karena...', 'Jadi...') dan buat judul rangkuman topik 4-7 kata yang utuh!"

    )



    options = CreateJobRequest(

        url=video_url,

        aspect_ratio=aspect_ratio,

        skip_if_has_subtitles=skip_if_has_subtitles,

        framing=framing,

        layout=layout,

        clip_mode="smart",

        clip_profile="standard",

        clip_flavor=flavor,

        clip_count=0,

        max_clips=effective_max_clips,

        min_duration=clip_min,

        max_duration=clip_max,

        smart_duration_mode="auto",

        custom_prompt=qa_prompt,

        subtitle_style="bold",

        subtitle_mode="active_highlight",

        subtitle_color="#FFFFFF",

        subtitle_active_color="#FFDD00",

        subtitle_position="auto",

        subtitle_font_size=18,

        subtitle_max_lines=2,

        snap_sentence_bounds=True,

        trim_opening_filler=False,

        use_audio_energy=True,

        spicy_headline_hook=True,

        hook_banner_enabled=True,

        hook_banner_text="",

        emoji_subtitles=emoji_subtitles,

        dynamic_micro_zoom=micro_zoom,

        auto_broll=auto_broll,

        broll_folder=broll_folder,

        hook_banner_duration=1,

        speed_shift=True,

        color_boost=True,

        audio_loudnorm=True,

        bgm_path=effective_bgm,

        bgm_volume=bgm_volume,

        voice_volume=1.05,

        bgm_autoduck=True,

        local_model=use_ai_model,

        quality=quality,

    )



    initial_job = Job(id=job_id, url=video_url, source_title=video_meta.get("title", ""))

    with JOBS_LOCK:

        JOBS[job_id] = initial_job

        JOB_OPTIONS[job_id] = options



    stop_monitor = threading.Event()



    def monitor_progress() -> None:

        last_log = ""

        while not stop_monitor.is_set():

            with JOBS_LOCK:

                j = JOBS.get(job_id)

                p = j.progress if j else 0

                msg = (j.message or "") if j else ""

                sub = getattr(j, "sub_message", "") if j else ""

            if msg:

                line = f"⏳ [{p:02d}%] {msg}" + (f" · {sub}" if sub else "")

                if line != last_log:

                    logger.info(line)

                    last_log = line

            time.sleep(2)



    monitor = threading.Thread(target=monitor_progress, daemon=True)

    monitor.start()



    try:

        process_job(job_id=job_id, options=options, source_path=None)

    finally:

        stop_monitor.set()



    with JOBS_LOCK:

        job = JOBS.get(job_id)



    if not job or job.status == "failed":

        err_msg = job.error if job else "Job tidak ditemukan."

        raise RuntimeError(f"Gagal memproses klip ENCLip: {err_msg}")



    if not job.clips:

        raise RuntimeError("Tidak ada segmen klip yang dihasilkan untuk video ini.")



    if job.source_title and (video_meta.get("title") == "Video Podcast Kustom" or not video_meta.get("title")):

        video_meta["title"] = job.source_title



    qualifying_clips = [c for c in job.clips if getattr(c, "score", 85.0) >= 70.0] or list(job.clips)

    sorted_clips = sorted(qualifying_clips, key=lambda c: getattr(c, "score", 0), reverse=True)

    if max_clips > 0:

        sorted_clips = sorted_clips[:max_clips]



    job_dir = job_result_dir(job_id)

    produced_results: list[dict[str, Any]] = []

    seen_ranges: list[tuple[float, float]] = []



    for c in sorted_clips:

        if any(c.start < (es - 2.0) and c.end > (ss + 2.0) for ss, es in seen_ranges):

            continue

        c_dir = clip_result_dir(job_dir, c.id, c.title)

        video_file = c_dir / "clip.mp4"

        if not video_file.is_file() or video_file.stat().st_size == 0:

            continue



        banner_hook, full_caption = format_curiosity_hook_and_caption(

            c.title, c.caption, c.hashtags, video_meta, clip_start=c.start

        )

        seen_ranges.append((c.start, c.end))

        produced_results.append({

            "id": c.id,

            "title": banner_hook,

            "start": c.start,

            "end": c.end,

            "score": c.score,

            "path": video_file,

            "caption": full_caption,

            "hashtags": c.hashtags,

        })

        logger.info(

            f"✨ Klip Q&A Siap: '{banner_hook}' | Detik {c.start:.1f}s - {c.end:.1f}s "

            f"(Durasi Utuh: {c.end - c.start:.1f}s) | Skor Viral: 🔥 {c.score:.1f}%"

        )



    try:

        raw_audio = job_dir / "audio.wav"

        raw_source = job_dir / "source.mp4"

        if raw_audio.is_file():

            raw_audio.unlink()

        if raw_source.is_file() and produced_results:

            raw_source.unlink()

    except Exception:

        pass



    return produced_results





def save_tiktok_session(session_path: Path = DEFAULT_SESSION_FILE) -> bool:

    from playwright.sync_api import sync_playwright



    session_path = Path(session_path)

    session_path.parent.mkdir(parents=True, exist_ok=True)



    print("\n" + "=" * 65)

    print("▶ LANGKAH LOGIN TIKTOK (SATU KALI SAJA)")

    print("=" * 65)

    print("Silakan login ke akun TikTok Anda di browser yang terbuka.")

    print("Setelah masuk ke beranda/profil, TEKAN [ENTER] DI TERMINAL INI.")

    print("=" * 65 + "\n")



    with sync_playwright() as p:

        browser = p.chromium.launch(

            headless=False,

            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],

        )

        context = browser.new_context(

            user_agent=(

                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "

                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

            ),

            no_viewport=True,

        )

        page = context.new_page()

        try:

            page.goto("https://www.tiktok.com/login", timeout=60000)

        except Exception as e:

            logger.warning(f"Navigasi ke login: {e}")



        logger.info("⏳ Browser TikTok telah terbuka. Silakan login (Scan QR / Masuk Akun Anda)...")
        logger.info("ℹ️ Sistem akan mendeteksi otomatis saat Anda selesai login, atau tekan ENTER di terminal.")
        import threading
        enter_pressed = threading.Event()
        def _wait():
            try:
                input()
                enter_pressed.set()
            except Exception:
                pass
        t = threading.Thread(target=_wait, daemon=True)
        t.start()

        start_wait = time.time()
        while time.time() - start_wait < 420:
            if enter_pressed.is_set():
                logger.info("Tombol ENTER ditekan pengguna. Memeriksa status login...")
                break
            try:
                cookies = context.cookies()
                has_session = any(c.get("name") in ("sessionid", "sessionid_ss", "sid_tt", "sid_guard") and len(c.get("value", "")) > 10 for c in cookies)
                if has_session:
                    time.sleep(3)
                    logger.info("🎉 Login TikTok berhasil terverifikasi (sessionid terdeteksi)!")
                    break
            except Exception:
                pass
            time.sleep(2.0)

        cookies = context.cookies()
        has_session = any(c.get("name") in ("sessionid", "sessionid_ss", "sid_tt", "sid_guard") and len(c.get("value", "")) > 10 for c in cookies)
        if not has_session:
            logger.error("❌ Login belum selesai atau belum terverifikasi. Sesi tidak disimpan.")
            browser.close()
            return False

        context.storage_state(path=str(session_path))
        logger.info(f"✅ Sesi login berhasil diverifikasi & disimpan di: {session_path}")
        browser.close()
        return True





def upload_to_tiktok(

    video_path: Path | str,

    caption: str,

    session_path: Path | str = DEFAULT_SESSION_FILE,

    headless: bool = False,

) -> bool:

    from playwright.sync_api import sync_playwright



    video_file = Path(video_path).resolve()

    session_file = Path(session_path).resolve()



    if not video_file.is_file():

        logger.error(f"File video tidak ditemukan: {video_file}")

        return False



    if not session_file.is_file():
        logger.info(f"ℹ️ Sesi login TikTok belum ada di {session_file}. Membuka browser untuk login 1x...")
        ok = save_tiktok_session(session_file)
        if not ok or not session_file.is_file():
            logger.error("❌ Login TikTok tidak diselesaikan. Proses upload dibatalkan.")
            return False



    logger.info("=" * 60)

    logger.info(f"🚀 MENGUNGGAH KLIP KE TIKTOK STUDIO: {video_file.name}")

    logger.info("=" * 60)



    with sync_playwright() as p:

        browser = p.chromium.launch(

            headless=headless,

            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],

        )

        context = browser.new_context(

            storage_state=str(session_file),

            user_agent=(

                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "

                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

            ),

            no_viewport=True,

        )

        page = context.new_page()

        page.set_default_timeout(60000)



        upload_urls = [

            "https://www.tiktok.com/tiktokstudio/upload",

            "https://www.tiktok.com/creator-center/upload?from=upload",

        ]

        opened = False

        for url in upload_urls:

            try:

                page.goto(url, wait_until="domcontentloaded")

                opened = True

                break

            except Exception:

                pass



        if not opened:

            browser.close()

            return False



        time.sleep(4)

        if "login" in page.url.lower():

            logger.error("❌ Sesi TikTok kedaluwarsa. Jalankan ulang: python auto_clipper_tiktok.py --login-tiktok")

            browser.close()

            return False



        file_input = None

        for _ in range(12):

            try:

                elem = page.locator('input[type="file"]')

                if elem.count() > 0:

                    file_input = elem

                    break

                for frame in page.frames:

                    iframe_input = frame.locator('input[type="file"]')

                    if iframe_input.count() > 0:

                        file_input = iframe_input

                        break

                if file_input and file_input.count() > 0:

                    break

            except Exception:

                pass

            time.sleep(1.5)



        if not file_input or file_input.count() == 0:

            logger.error("Input file upload tidak ditemukan di halaman TikTok.")

            browser.close()

            return False



        file_input.first.set_input_files(str(video_file))

        logger.info("Menunggu video diproses oleh server TikTok (8 detik)...")

        time.sleep(8)



        dismiss_selectors = [

            'button:has-text("Turn on")', 'button:has-text("Aktifkan")',

            'button:has-text("Allow")', 'button:has-text("Izinkan")',

            'button:has-text("Got it")', 'button:has-text("Mengerti")',

            'button:has-text("Not now")', 'button:has-text("Nanti saja")',

            'button[aria-label="Close"]', 'button[aria-label="Tutup"]',

            '.TUXModal-close',

        ]

        for _ in range(3):

            for btn_sel in dismiss_selectors:

                try:

                    mod_btn = page.locator(btn_sel)

                    if mod_btn.count() > 0 and mod_btn.first.is_visible():

                        mod_btn.first.click(timeout=3000, force=True)

                        time.sleep(1)

                except Exception:

                    pass



        caption_selectors = [

            'div[contenteditable="true"]',

            'div[role="combobox"]',

            '.notranslate[contenteditable="true"]',

            'textarea[placeholder*="caption" i]',

        ]

        caption_box = None

        for sel in caption_selectors:

            loc = page.locator(sel)

            if loc.count() > 0 and loc.first.is_visible():

                caption_box = loc.first

                break



        if caption_box:

            try:

                caption_box.click(force=True, timeout=8000)

                time.sleep(0.5)

                page.keyboard.press("Control+A")

                page.keyboard.press("Backspace")

                time.sleep(0.5)

                for chunk in caption.split():

                    page.keyboard.type(chunk + " ", delay=20)

                    time.sleep(0.04)

                time.sleep(2)

            except Exception as e:

                logger.warning(f"Catatan pengisian caption: {e}")



        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        time.sleep(2)



        post_button_selectors = [

            'button[data-e2e="post_video_button"]',

            'button.Button__root--type-primary:has-text("Post")',

            'button.Button__root--type-primary:has-text("Posting")',

            'button.Button__root--type-primary:has-text("Publikasikan")',

            'button.btn-post',

        ]

        post_btn = None

        for p_sel in post_button_selectors:

            btn = page.locator(p_sel)

            if btn.count() > 0 and btn.first.is_visible():

                post_btn = btn.first

                break



        if post_btn:

            for _ in range(30):

                if post_btn.is_enabled():

                    break

                time.sleep(2)



            try:

                post_btn.scroll_into_view_if_needed()

                time.sleep(1)

                post_btn.click(force=True)

            except Exception as e:

                logger.error(f"Gagal mengklik tombol post: {e}")

                browser.close()

                return False



            time.sleep(2)

            for c_sel in [

                'button:has-text("Post now")',

                'button:has-text("Posting sekarang")',

                'button:has-text("Tetap posting")',

                'button:has-text("Continue to post")',

            ]:

                try:

                    cb = page.locator(c_sel)

                    if cb.count() > 0 and cb.first.is_visible():

                        cb.first.click(force=True)

                        break

                except Exception:

                    pass



            for _ in range(25):

                try:

                    curr_url = page.url.lower()

                    if "content" in curr_url or "posts" in curr_url:

                        break

                    body_txt = page.locator("body").inner_text().lower()

                    if any(

                        t in body_txt

                        for t in [

                            "manage your posts",

                            "your video has been uploaded",

                            "video anda telah diunggah",

                            "kelola postingan",

                            "post another video",

                        ]

                    ):

                        break

                except Exception:

                    pass

                time.sleep(2)



            logger.info("🎉 VIDEO BERHASIL DIPUBLIKASIKAN KE TIKTOK!")

            browser.close()

            return True



        time.sleep(10)

        browser.close()

        return False





def produce_one_video_unlimited_clips(args: argparse.Namespace, history: HistoryTracker) -> int:

    if args.video_url:

        import yt_dlp

        v_url = args.video_url

        v_title = "Video Podcast Kustom"

        v_duration = 0

        v_channel = "Podcast"

        v_views = 100_000

        try:

            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:

                info = ydl.extract_info(v_url, download=False)

                if info:

                    v_title = info.get("title") or v_title

                    v_duration = int(info.get("duration") or 0)

                    v_channel = info.get("channel") or info.get("uploader") or v_channel

                    v_views = int(info.get("view_count") or v_views)

        except Exception as e:

            logger.warning(f"Gagal probe metadata URL: {e}")



        min_sec = args.min_duration * 60

        if v_duration > 0 and v_duration < min_sec:

            raise ValueError(

                f"Video '{v_title}' berdurasi {v_duration // 60}m {v_duration % 60}s. "

                f"Video ini bukan podcast berdurasi penuh. Syarat podcast minimal {args.min_duration} menit ({min_sec}s)."

            )



        vid_id = v_url.split("v=")[-1].split("&")[0] if "v=" in v_url else f"custom_{int(time.time())}"

        target_video = {

            "id": vid_id,

            "title": v_title,

            "url": v_url,

            "view_count": v_views,

            "channel": v_channel,

            "duration": v_duration or 1800,

        }

        args.video_url = ""

    else:

        candidates = search_viral_videos(

            query=args.query,

            min_views=args.min_views,

            min_duration_sec=args.min_duration * 60,

            max_duration_sec=args.max_duration * 60,

            limit=args.search_limit,

            history_tracker=history,

            trend_hijacker=getattr(args, "trend_hijacker", True),

        )

        if not candidates:

            candidates = search_viral_videos(

                query="auto",

                min_views=max(5_000, args.min_views // 3),

                min_duration_sec=args.min_duration * 60,

                max_duration_sec=args.max_duration * 60,

                limit=args.search_limit,

                history_tracker=history,

            )

        if not candidates:

            logger.error("❌ Tidak ada kandidat video baru yang ditemukan.")

            return 0

        target_video = candidates[0]



    logger.info(f"🎯 Memproses Video Podcast Baru: '{target_video['title']}'")

    try:
        from clipper_hud import update_hud_status
        update_hud_status(
            stage="scan",
            title=target_video.get("title", ""),
            progress=5,
            detail=f"Mempersiapkan proses: {target_video.get('title', '')[:50]}",
            channel=target_video.get("channel", ""),
        )
    except Exception:
        pass

    try:

        clips_list = process_viral_video_with_enclip(

            video_meta=target_video,

            flavor=args.flavor,

            layout=args.layout,

            framing=args.framing,

            aspect_ratio=getattr(args, "aspect_ratio", "16:9"),

            skip_if_has_subtitles=getattr(args, "skip_if_has_subtitles", True),

            max_clips=args.clips_per_edit,

            clip_min=args.clip_min,

            clip_max=args.clip_max,

            bgm_path=args.bgm,

            bgm_volume=args.bgm_volume,

            use_ai_model=args.ai_model,

            quality=getattr(args, "quality", "1080"),

            emoji_subtitles=getattr(args, "emoji_subtitles", True),

            micro_zoom=getattr(args, "micro_zoom", True),

            auto_broll=getattr(args, "auto_broll", False),

            broll_folder=getattr(args, "broll_folder", ""),

        )

        added = history.enqueue_clips(target_video, clips_list)

        total_ready = history.ready_to_upload_count()

        try:
            from clipper_hud import update_hud_status
            update_hud_status(
                stage="done",
                title=target_video.get("title", ""),
                progress=100,
                detail=f"Selesai! +{added} klip baru siap di antrean ({total_ready} total siap upload).",
                channel=target_video.get("channel", ""),
            )
        except Exception:
            pass

        logger.info("=" * 74)

        logger.info(f"✅ SELESAI RENDER 1 VIDEO PODCAST: '{target_video['title'][:50]}'")

        logger.info(f"📦 Klip Baru Dihasilkan dari Video Ini : +{added} File Video")

        logger.info(f"📊 TOTAL FILE VIDEO SIAP UPLOAD SAAT INI: {total_ready} FILE VIDEO (di Core_Data/upload_queue.json)")

        logger.info("=" * 74)

        return added

    except Exception as exc:

        logger.error(f"❌ Gagal memproses video '{target_video['title']}': {exc}")

        history.mark_video_processed(target_video)

        return 0





def upload_one_from_queue(args: argparse.Namespace, history: HistoryTracker, cycle_count: int = 1) -> bool:

    queued_clip = history.pop_next_queued_clip()

    if not queued_clip:

        return False



    clip_path = Path(queued_clip["clip_path"])

    remaining = history.ready_to_upload_count()

    logger.info(
        f"🚀 [PUBLISHER #{cycle_count}] Mengunggah file: '{queued_clip['clip_title']}' | "
        f"📊 Sisa File Video Siap Upload: {remaining} File"
    )

    try:
        from clipper_hud import update_hud_status
        update_hud_status(
            stage="upload",
            title=queued_clip.get("clip_title", "Video Klip"),
            progress=50,
            detail=f"Mengunggah ke TikTok: {queued_clip.get('clip_title', '')[:35]}...",
            channel=queued_clip.get("channel", "TikTok"),
        )
    except Exception:
        pass

    uploaded = False

    target_plat = getattr(args, "platform", "tiktok").lower()
    if getattr(args, "no_upload", False):
        logger.info(f"⏩ Opsi --no-upload aktif. File siap di: {clip_path}")
        uploaded = True
    elif target_plat == "youtube":
        from omnichannel_publisher import upload_to_youtube_shorts, SESSION_YOUTUBE
        uploaded = upload_to_youtube_shorts(
            video_path=clip_path,
            title=queued_clip.get("clip_title") or clip_path.stem,
            description=queued_clip.get("caption", ""),
            session_path=SESSION_YOUTUBE,
            headless=args.headless,
        )
    elif target_plat == "both":
        from omnichannel_publisher import upload_to_youtube_shorts, SESSION_YOUTUBE
        tt_ok = upload_to_tiktok(
            video_path=clip_path,
            caption=queued_clip["caption"],
            session_path=args.session_path,
            headless=args.headless,
        )
        yt_ok = upload_to_youtube_shorts(
            video_path=clip_path,
            title=queued_clip.get("clip_title") or clip_path.stem,
            description=queued_clip.get("caption", ""),
            session_path=SESSION_YOUTUBE,
            headless=args.headless,
        )
        uploaded = tt_ok or yt_ok
    else:
        uploaded = upload_to_tiktok(
            video_path=clip_path,
            caption=queued_clip["caption"],
            session_path=args.session_path,
            headless=args.headless,
        )

    if uploaded:
        history.record_upload(queued_clip, uploaded=True)
        if not getattr(args, "no_upload", False):
            append_to_uploaded_txt(queued_clip)
            cleanup_uploaded_video_file(clip_path)
        try:
            from clipper_hud import update_hud_status
            update_hud_status(
                stage="done",
                title=queued_clip.get("clip_title", "Video Klip"),
                progress=100,
                detail=f"Selesai! 1 klip berhasil dipublikasikan ke TikTok.",
                channel=queued_clip.get("channel", "TikTok"),
            )
        except Exception:
            pass
    else:
        history.queue.insert(0, queued_clip)
        history.save()
        try:
            from clipper_hud import update_hud_status
            update_hud_status(
                stage="idle",
                title=queued_clip.get("clip_title", "Video Klip"),
                progress=0,
                detail=f"Gagal/Dibatalkan mengunggah ke TikTok.",
                channel=queued_clip.get("channel", "TikTok"),
            )
        except Exception:
            pass

    logger.info(f"📊 STATUS ANTREAN TERKINI: {history.ready_to_upload_count()} File Video Siap Upload.")

    return uploaded





def run_scheduler_daemon(args: argparse.Namespace) -> None:

    history = HistoryTracker()



    preset_map = {"30m": 30, "1h": 60, "2h": 120, "ideal": 120}

    upload_interval_mins = (

        args.upload_interval_mins if args.upload_interval_mins > 0 else preset_map.get(args.schedule_preset, 120)

    )



    logger.info("=" * 78)

    logger.info("🤖 ANTIGRAVITY SMART ADAPTIVE LAYOUT & FULL NIGHT RENDERER (01:00-07:00) AKTIF!")

    logger.info(f"   Jam Full Render Non-Stop : {args.edit_start_hour:02d}:00 - {args.edit_end_hour:02d}:00 WIB")

    logger.info("   Mode Layout Visual       : 100% Gemini Vision AI (1=Full | 2/4=Split 2 | 3=Grup/3-Panel | 0=Utuh)")

    logger.info("   Mode Pemotongan Klip     : Siklus Tanya-Jawab Utuh (Full Context Auto-Heal)")

    logger.info(f"   📊 JUMLAH FILE SIAP UPLOAD SAAT INI: {history.ready_to_upload_count()} FILE VIDEO")

    logger.info("=" * 78)



    next_upload_time = datetime.now()

    cycle_count = 0

    last_mode_log = ""

    videos_rendered_tonight = 0



    while True:

        now = datetime.now()

        in_night_window = is_in_edit_window(args.edit_start_hour, args.edit_end_hour, now)



        if now >= next_upload_time and history.ready_to_upload_count() > 0:

            cycle_count += 1

            upload_one_from_queue(args, history, cycle_count)



            if not args.daemon and not in_night_window and not args.produce_now:

                logger.info("🏁 Eksekusi selesai.")

                break



            jitter_sec = random.randint(120, 360) if upload_interval_mins >= 30 else 0

            next_upload_time = datetime.now() + timedelta(minutes=upload_interval_mins, seconds=jitter_sec)

            logger.info(

                f"⏳ Upload berikutnya pada: {next_upload_time.strftime('%H:%M:%S')} | "

                f"📊 Total File Siap Upload: {history.ready_to_upload_count()} File"

            )



        now = datetime.now()

        in_night_window = is_in_edit_window(args.edit_start_hour, args.edit_end_hour, now)



        if in_night_window or args.produce_now:

            videos_rendered_tonight += 1

            logger.info(

                f"🌙 [FULL RENDER MALAM {args.edit_start_hour:02d}:00-{args.edit_end_hour:02d}:00 | Video ke-{videos_rendered_tonight}] "

                f"📊 Saat ini sudah ada {history.ready_to_upload_count()} file siap upload. Memulai render video berikutnya..."

            )

            added = produce_one_video_unlimited_clips(args, history)



            if args.produce_now and not in_night_window:

                args.produce_now = False

                if not args.daemon:

                    break



            if added == 0:

                time.sleep(25)

            continue



        videos_rendered_tonight = 0

        next_night = next_edit_window_datetime(args.edit_start_hour, now)

        day_msg = (

            f"☀️ [MODE SIANG HEMAT LAPTOP - CPU 0%] Render dimatikan agar laptop ringan dipakai. "

            f"📊 File Siap Upload: {history.ready_to_upload_count()} File | "

            f"Upload berikutnya: {next_upload_time.strftime('%H:%M:%S')} | "

            f"Full Render berikutnya: {next_night.strftime('%d/%m %H:%M')} WIB"

        )

        if day_msg != last_mode_log:

            logger.info(day_msg)

            last_mode_log = day_msg



        if not args.daemon:

            break



        time.sleep(20)





def main() -> None:

    parser = argparse.ArgumentParser(

        description="ENCLip - Autonomous Viral Podcast Clipper (Smart Adaptive Layout & Full Night Render 01:00-07:00)"

    )

    parser.add_argument("--login-tiktok", action="store_true", help="Buka browser untuk login TikTok 1x dan simpan sesi.")
    parser.add_argument("--login-youtube", action="store_true", help="Buka browser untuk login YouTube Studio 1x dan simpan sesi.")
    parser.add_argument("--upload-youtube", action="store_true", help="Ambil 1 video dari antrean stok (upload_queue.json), upload ke YouTube Shorts, lalu selesai.")
    parser.add_argument(
        "--platform",
        type=str,
        default="tiktok",
        choices=["tiktok", "youtube", "both"],
        help="Target platform upload otomatis: 'tiktok', 'youtube', atau 'both' (default: tiktok).",
    )

    parser.add_argument("--daemon", action="store_true", help="Jalankan terus-menerus secara otomatis (Mode Antigravity).")

    parser.add_argument(

        "--schedule-preset",

        type=str,

        default="ideal",

        choices=["30m", "1h", "2h", "ideal"],

        help="Jadwal upload otomatis sepanjang hari: '30m', '1h', '2h' / 'ideal' (2 jam sekali).",

    )

    parser.add_argument("--upload-interval-mins", type=int, default=0, help="Kustomisasi jeda menit antar upload.")

    parser.add_argument("--edit-start-hour", type=int, default=4, help="Jam mulai Full Render subuh (default: 4 = 04:00 subuh WIB).")

    parser.add_argument("--edit-end-hour", type=int, default=7, help="Jam selesai Full Render pagi (default: 7 = 07:00 pagi WIB).")

    parser.add_argument("--clips-per-edit", type=int, default=0, help="0 = TANPA BATAS (clip semua siklus tanya-jawab menarik di dalam video).")

    parser.add_argument("--produce-now", action="store_true", help="Paksa render 1 video podcast sekarang juga walaupun di luar jam 01:00-07:00.")

    parser.add_argument("--produce-only", action="store_true", help="Cari & render klip dari 1 video podcast ke antrean stok (upload_queue.json), lalu selesai (tanpa upload).")

    parser.add_argument("--upload-only", action="store_true", help="Ambil 1 video dari antrean stok (upload_queue.json), upload ke TikTok via Playwright, lalu selesai.")

    parser.add_argument("--run", action="store_true", help="Jalankan 1 siklus otomatisasi penuh (Cari podcast -> Render klip -> Upload TikTok).")

    parser.add_argument("--query", type=str, default="auto", help="Kata kunci pencarian YouTube.")

    parser.add_argument("--min-views", type=int, default=35000, help="Minimum views YouTube (default: 35,000).")

    parser.add_argument("--min-duration", type=int, default=30, help="Durasi minimal video sumber podcast dalam menit (default: 30 menit).")

    parser.add_argument("--max-duration", type=int, default=210, help="Durasi maksimal video sumber dalam menit.")

    parser.add_argument("--search-limit", type=int, default=35, help="Jumlah hasil pencarian YouTube per query.")

    parser.add_argument(

        "--flavor",

        type=str,

        default="spicy_drama",

        choices=["spicy_drama", "viral_all", "funny_blunder", "deep_meat", "hype_rage"],

        help="Fokus pemilihan topik AI.",

    )

    parser.add_argument(

        "--aspect-ratio",

        type=str,

        default="16:9",

        choices=["16:9", "9:16", "1:1", "4:5"],

        help="Aspek rasio video (default: 16:9).",

    )

    parser.add_argument("--skip-if-has-subtitles", action="store_true", default=True, help="Otomatis lewati penambahan subtitle jika video sudah memiliki subtitle (default: aktif).")

    parser.add_argument("--force-subtitles", dest="skip_if_has_subtitles", action="store_false", help="Paksa tambahkan subtitle baru meskipun video sudah memiliki subtitle.")

    parser.add_argument(

        "--layout",

        type=str,

        default="standard",

        choices=["auto_smart", "podcast_split", "standard", "facecam_top"],

        help="Tata letak 9:16 (default: auto_smart).",

    )

    parser.add_argument("--framing", type=str, default="crop", choices=["crop", "fit"], help="Mode framing video.")

    parser.add_argument("--clip-min", type=int, default=45, help="Durasi minimal klip dalam detik (default: 45s).")

    parser.add_argument("--clip-max", type=int, default=125, help="Durasi maksimal klip dalam detik (default: 125s).")

    parser.add_argument("--bgm", type=str, default="", help="Path file BGM (.mp3/.wav).")

    parser.add_argument("--bgm-volume", type=float, default=0.08, help="Volume BGM latar (default: 0.08 / 8%%).")

    parser.add_argument("--ai-model", type=str, default="gemini", help="Model AI ('gemini' atau 'qwen').")

    parser.add_argument("--video-url", type=str, default="", help="Proses URL YouTube spesifik.")

    parser.add_argument("--no-upload", action="store_true", default=True, help="Hanya cari & render klip tanpa upload ke TikTok (Default: aktif / tidak auto-upload).")
    parser.add_argument("--auto-upload", dest="no_upload", action="store_false", help="Izinkan upload otomatis ke TikTok.")

    parser.add_argument("--quality", type=str, default="1080", choices=["360", "480", "720", "1080", "best"], help="Resolusi download video (default: 1080p Full HD).")

    parser.add_argument("--headless", action="store_true", help="Jalankan browser upload di background.")

    parser.add_argument("--upload-file", type=str, default="", help="Upload langsung 1 file video lokal.")

    parser.add_argument("--caption", type=str, default="", help="Caption kustom untuk --upload-file.")

    parser.add_argument("--session-path", type=str, default=str(DEFAULT_SESSION_FILE), help="Lokasi file sesi TikTok.")

    parser.add_argument("--trend-hijacker", action="store_true", default=True, help="Otomatis pilih podcast berdasarkan trending Google & Twitter/X Indonesia.")

    parser.add_argument("--no-trend-hijacker", dest="trend_hijacker", action="store_false", help="Nonaktifkan Trend Hijacker.")

    parser.add_argument("--emoji-subtitles", action="store_true", default=True, help="Otomatis sertakan emoji ekspresif pada subtitle kata kunci.")

    parser.add_argument("--no-emoji-subtitles", dest="emoji_subtitles", action="store_false", help="Nonaktifkan emoji subtitle.")

    parser.add_argument("--micro-zoom", action="store_true", default=True, help="Punch-in micro-zoom dinamis 1.08x pada punchline.")

    parser.add_argument("--no-micro-zoom", dest="micro_zoom", action="store_false", help="Nonaktifkan micro-zoom.")

    parser.add_argument("--auto-broll", action="store_true", default=False, help="Sisipkan B-Roll ilustrasi 2-3 detik saat topik spesifik dibahas.")

    parser.add_argument("--broll-folder", type=str, default="", help="Folder file video B-Roll kustom (default: Core_Data/broll).")



    args = parser.parse_args()



    if args.login_tiktok:

        save_tiktok_session(session_path=Path(args.session_path))

    elif args.login_youtube:

        from omnichannel_publisher import save_platform_session
        save_platform_session("youtube")

    elif args.upload_youtube:

        history = HistoryTracker(DEFAULT_HISTORY_FILE, DEFAULT_QUEUE_FILE)
        args.platform = "youtube"
        uploaded = upload_one_from_queue(args, history, cycle_count=1)
        if uploaded:
            logger.info("✅ Berhasil mengunggah 1 klip ke YouTube Shorts dari antrean.")
        else:
            logger.info("ℹ️ Tidak ada klip yang diunggah ke YouTube Shorts (antrean kosong atau dilewati).")

    elif args.upload_file:

        up_path = Path(args.upload_file)

        caption = args.caption or f"{up_path.stem} 👀🔥 #podcastindonesia #fyp #viral #trending #foryou"

        upload_to_tiktok(video_path=up_path, caption=caption, session_path=args.session_path, headless=args.headless)

    elif args.upload_only:
        args.no_upload = False
        try:
            from clipper_hud import launch_hud_process
            launch_hud_process()
        except Exception:
            pass

        history = HistoryTracker(DEFAULT_HISTORY_FILE, DEFAULT_QUEUE_FILE)

        uploaded = upload_one_from_queue(args, history, cycle_count=1)

        if uploaded:

            logger.info("✅ Berhasil mengunggah 1 klip ke TikTok dari antrean.")

        else:

            logger.info("ℹ️ Tidak ada klip yang diunggah (antrean kosong atau dilewati).")

    elif args.produce_only:

        try:

            from clipper_hud import launch_hud_process

            launch_hud_process()

        except Exception:

            pass

        args.no_upload = True

        history = HistoryTracker(DEFAULT_HISTORY_FILE, DEFAULT_QUEUE_FILE)

        added = produce_one_video_unlimited_clips(args, history)

        logger.info(f"✅ Selesai memproduksi klip: +{added} klip baru ditambahkan ke antrean.")

    elif args.run or args.video_url:

        try:

            from clipper_hud import launch_hud_process

            launch_hud_process()

        except Exception:

            pass

        history = HistoryTracker(DEFAULT_HISTORY_FILE, DEFAULT_QUEUE_FILE)

        added = produce_one_video_unlimited_clips(args, history)

        if added > 0 and not args.no_upload:

            upload_one_from_queue(args, history, cycle_count=1)

        logger.info("🏁 1 Siklus otomatisasi selesai.")

    else:

        if getattr(args, "daemon", False):
            run_scheduler_daemon(args)
        else:
            logger.info("Mode auto-scheduler daemon tidak aktif otomatis.")





if __name__ == "__main__":

    main()