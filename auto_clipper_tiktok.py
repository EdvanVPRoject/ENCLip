"""
ENCLip - Autonomous Viral Clipper & TikTok Uploader Pipeline
============================================================
Pipeline otomatis tanpa API Key berbayar:
1. Pencarian video podcast / konten viral Indonesia dengan views tinggi via yt-dlp.
2. Pemotongan momen viral & rendering otomatis menggunakan ENCLip Core Engine:
   - 9:16 Vertical Video (Podcast Split / Smart Crop)
   - Karaoke Subtitle (Active Word Highlight)
   - Spicy Hook Banner & Audio Energy Scoring
   - Anti-Copyright (Micro Speed Shift & Color Boost)
   - Auto-Ducking Background Music & Normalisasi Suara
3. Pengunggahan otomatis ke TikTok Creator Studio via Playwright dengan sesi tersimpan.
4. Pencatatan riwayat agar video tidak diproses berulang (auto_history.json).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Reconfigure Windows stdout/stderr to UTF-8 to prevent charmap errors with emojis
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Setup root path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AutoTikTokClipper")

CORE_DATA_DIR = CURRENT_DIR / "Core_Data"
CORE_DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SESSION_FILE = CORE_DATA_DIR / "tiktok_session.json"
DEFAULT_HISTORY_FILE = CORE_DATA_DIR / "auto_history.json"

# Auto-detect Hardware GPU (CUDA) untuk Faster-Whisper agar 30x lebih cepat
if "WHISPER_DEVICE" not in os.environ:
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            os.environ["WHISPER_DEVICE"] = "cuda"
            os.environ["WHISPER_COMPUTE_TYPE"] = "float16"
            logger.info("⚡ NVIDIA GPU (CUDA) terdeteksi! Akselerasi Whisper GPU diaktifkan (30x lebih cepat).")
    except Exception:
        pass


# ==============================================================================
# 1. HISTORY TRACKER
# ==============================================================================
class HistoryTracker:
    """Melacak video yang sudah pernah dicari, dipotong, dan diupload."""

    def __init__(self, history_file: Path = DEFAULT_HISTORY_FILE) -> None:
        self.history_file = Path(history_file)
        self.data: dict[str, Any] = {"processed_ids": [], "items": []}
        self.load()

    def load(self) -> None:
        if self.history_file.is_file():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                    if "processed_ids" not in self.data:
                        self.data["processed_ids"] = []
                    if "items" not in self.data:
                        self.data["items"] = []
            except Exception as e:
                logger.warning(f"Gagal membaca file riwayat ({e}), membuat baru...")

    def save(self) -> None:
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Gagal menyimpan file riwayat: {e}")

    def is_processed(self, video_id: str) -> bool:
        return video_id in self.data.get("processed_ids", [])

    def record(self, video_meta: dict[str, Any], clip_meta: dict[str, Any], uploaded: bool) -> None:
        video_id = video_meta.get("id")
        if video_id and video_id not in self.data["processed_ids"]:
            self.data["processed_ids"].append(video_id)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "video_id": video_id,
            "video_title": video_meta.get("title", ""),
            "channel": video_meta.get("channel", ""),
            "views": video_meta.get("view_count", 0),
            "video_url": video_meta.get("url", ""),
            "clip_title": clip_meta.get("title", ""),
            "clip_path": str(clip_meta.get("path", "")),
            "caption": clip_meta.get("caption", ""),
            "uploaded_tiktok": uploaded,
        }
        self.data["items"].append(entry)
        self.save()


# ==============================================================================
# 2. VIRAL VIDEO FINDER (YOUTUBE / YT-DLP TANPA API KEY)
# ==============================================================================
VIRAL_SEARCH_PRESETS = [
    "podcast viral indonesia terbaru",
    "podcast terlucu indonesia",
    "curhat bang denny sumargo",
    "close the door deddy corbuzier",
    "podkesmas terbaru",
    "vindes terbaru",
    "podcast horor indonesia viral",
]


def search_viral_videos(
    query: str = "podcast viral indonesia",
    min_views: int = 50_000,
    min_duration_sec: int = 600,
    max_duration_sec: int = 10800,
    limit: int = 25,
    history_tracker: HistoryTracker | None = None,
) -> list[dict[str, Any]]:
    """Mencari video viral di YouTube menggunakan yt-dlp tanpa membutuhkan API key."""
    import yt_dlp

    logger.info(f"🔎 Mencari video viral di YouTube dengan kata kunci: '{query}'...")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    candidates: list[dict[str, Any]] = []
    search_query = f"ytsearch{limit}:{query}"

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
                v_channel = entry.get("channel") or entry.get("uploader") or "Unknown"
                v_url = entry.get("webpage_url") or f"https://www.youtube.com/watch?v={v_id}"

                if history_tracker and history_tracker.is_processed(v_id):
                    logger.debug(f"Lewati video (sudah pernah diproses): {v_title[:40]}...")
                    continue

                if v_duration and (v_duration < min_duration_sec or v_duration > max_duration_sec):
                    continue

                if v_views < min_views:
                    continue

                candidates.append(
                    {
                        "id": v_id,
                        "title": v_title,
                        "url": v_url,
                        "view_count": v_views,
                        "duration": v_duration,
                        "channel": v_channel,
                    }
                )
    except Exception as exc:
        logger.error(f"Gagal melakukan pencarian YouTube: {exc}")

    # Urutkan berdasarkan views tertinggi
    candidates.sort(key=lambda x: x["view_count"], reverse=True)
    logger.info(f"✅ Ditemukan {len(candidates)} kandidat video viral yang memenuhi kriteria.")
    return candidates


# ==============================================================================
# 3. ENCLIP AUTOMATION ENGINE
# ==============================================================================
def process_viral_video_with_enclip(
    video_meta: dict[str, Any],
    flavor: str = "spicy_drama",
    layout: str = "podcast_split",
    framing: str = "crop",
    max_clips: int = 1,
    clip_min: int = 30,
    clip_max: int = 60,
    bgm_path: str = "",
    use_ai_model: str = "gemini",
) -> tuple[Path, dict[str, Any]]:
    """
    Menjalankan proses download, transkripsi, deteksi spicy moment,
    dan rendering video vertikal 9:16 menggunakan core backend ENCLip.
    """
    from Backend_API.web_server import (
        CreateJobRequest,
        DATA_DIR,
        Job,
        JOBS,
        JOBS_LOCK,
        JOB_OPTIONS,
        clip_result_dir,
        job_result_dir,
        process_job,
        safe_folder_name,
    )

    job_id = f"auto_{int(time.time())}"
    video_url = video_meta["url"]

    logger.info("=" * 60)
    logger.info(f"🎬 MEMULAI EDITING ENCLIP UNTUK VIDEO:")
    logger.info(f"   Judul  : {video_meta['title']}")
    logger.info(f"   Views  : {video_meta['view_count']:,} | Channel: {video_meta['channel']}")
    logger.info(f"   URL    : {video_url}")
    logger.info(f"   Flavor : {flavor} | Layout: {layout}")
    logger.info("=" * 60)

    # Siapkan request konfigurasi klip sesuai fitur unggulan ENCLip
    options = CreateJobRequest(
        url=video_url,
        aspect_ratio="9:16",
        framing=framing,
        layout=layout,
        clip_mode="smart",
        clip_flavor=flavor,
        clip_count=max_clips,
        max_clips=max_clips,
        min_duration=clip_min,
        max_duration=clip_max,
        smart_duration_mode="auto",
        subtitle_style="bold",
        subtitle_mode="active_highlight",
        subtitle_color="#FFFFFF",
        subtitle_active_color="#FFDD00",
        subtitle_position="bottom",
        subtitle_font_size=16,
        subtitle_max_lines=2,
        snap_sentence_bounds=True,
        trim_opening_filler=True,
        use_audio_energy=True,
        spicy_headline_hook=True,
        hook_banner_enabled=True,
        hook_banner_text="",
        hook_banner_duration=4,
        speed_shift=True,  # anti-copyright
        color_boost=True,  # visual saturation & contrast
        audio_loudnorm=True,  # stabilizer volume suara
        bgm_path=bgm_path,
        bgm_volume=0.16,
        voice_volume=1.0,
        bgm_autoduck=True,
        local_model=use_ai_model,
    )

    # Daftarkan job ke registry sebelum proses dimulai
    initial_job = Job(id=job_id, url=video_url, source_title=video_meta.get("title", ""))
    with JOBS_LOCK:
        JOBS[job_id] = initial_job
        JOB_OPTIONS[job_id] = options

    # Cek apakah video sumber sudah pernah diunduh secara lokal agar tidak perlu download ulang
    source_path = None
    title_folder = safe_folder_name(video_meta.get("title", ""))
    if title_folder:
        candidates = [DATA_DIR / title_folder] + list(DATA_DIR.glob(f"{title_folder}*"))
        for candidate_dir in candidates:
            if candidate_dir.is_dir():
                candidate_mp4 = candidate_dir / "source.mp4"
                if candidate_mp4.is_file() and candidate_mp4.stat().st_size > 10_000_000:
                    source_path = str(candidate_mp4)
                    logger.info(
                        f"⚡ Video sumber lokal ditemukan ({candidate_mp4.name}, {candidate_mp4.stat().st_size / (1024*1024):.1f} MB)! Melewati proses unduh YouTube."
                    )
                    break

    # Jalankan processing ENCLip dengan pemantau progres real-time ke terminal
    stop_monitor = threading.Event()

    def monitor_progress() -> None:
        last_log = ""
        while not stop_monitor.is_set():
            with JOBS_LOCK:
                j = JOBS.get(job_id)
                if j:
                    p = j.progress
                    msg = j.message or ""
                    sub = getattr(j, "sub_message", "")
                else:
                    p, msg, sub = 0, "", ""
            if msg:
                line = f"⏳ [{p:02d}%] {msg}"
                if sub:
                    line += f" · {sub}"
                if line != last_log:
                    logger.info(line)
                    last_log = line
            time.sleep(2)

    monitor = threading.Thread(target=monitor_progress, daemon=True)
    monitor.start()

    try:
        process_job(job_id=job_id, options=options, source_path=source_path)
    finally:
        stop_monitor.set()

    with JOBS_LOCK:
        job = JOBS.get(job_id)

    if not job or job.status == "failed":
        err_msg = job.error if job else "Job tidak ditemukan."
        raise RuntimeError(f"Gagal memproses klip ENCLip: {err_msg}")

    if not job.clips:
        raise RuntimeError("ENCLip tidak menghasilkan klip kandidat untuk video ini.")

    # Pilih klip dengan skor viral AI tertinggi
    top_clip = max(job.clips, key=lambda c: getattr(c, "score", 0))
    job_dir = job_result_dir(job_id)
    clip_dir = clip_result_dir(job_dir, top_clip.id, top_clip.title)
    video_file = clip_dir / "clip.mp4"

    if not video_file.is_file() or video_file.stat().st_size == 0:
        raise RuntimeError(f"File klip video hasil render tidak ditemukan di: {video_file}")

    # Bangun caption & hashtags otomatis yang ramah algoritma TikTok
    clean_title = re.sub(r"[#@⁉️‼️🤣😂]+", "", top_clip.title).strip()
    if not clean_title or clean_title == "Highlight 1":
        clean_title = f"{video_meta.get('channel', 'Podcast')} Seru"

    caption_body = top_clip.caption or f"Momen seru dari {video_meta.get('channel', 'Podcast')}! Tonton sampai habis 🔥"

    hashtags = top_clip.hashtags
    if not hashtags:
        hashtags = ["#fyp", "#viral", "#podcastindonesia", "#trending", "#foryou", "#enclip"]

    tag_str = " ".join([tag if tag.startswith("#") else f"#{tag}" for tag in hashtags])
    full_tiktok_caption = f"{clean_title} ‼️\n\n{caption_body}\n\n{tag_str}"

    clip_info = {
        "id": top_clip.id,
        "title": clean_title,
        "score": top_clip.score,
        "path": video_file,
        "caption": full_tiktok_caption,
        "hashtags": hashtags,
    }

    logger.info("=" * 60)
    logger.info(f"✨ KLIP BERHASIL DIRENDER OLEH ENCLIP!")
    logger.info(f"   Path Video : {video_file}")
    logger.info(f"   Skor Viral : 🔥 {top_clip.score:.1f}%")
    logger.info(f"   Judul Klip : {clean_title}")
    logger.info("=" * 60)

    return video_file, clip_info


# ==============================================================================
# 4. TIKTOK PLAYWRIGHT AUTOMATION (NO API KEY)
# ==============================================================================
def save_tiktok_session(session_path: Path = DEFAULT_SESSION_FILE) -> bool:
    """
    Membuka Chromium interaktif agar pengguna dapat login ke akun TikTok.
    Sesi (cookies + storage) disimpan ke Core_Data/tiktok_session.json.
    """
    from playwright.sync_api import sync_playwright

    session_path = Path(session_path)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 65)
    print("▶ LANGKAH LOGIN TIKTOK (SATU KALI SAJA)")
    print("=" * 65)
    print("Browser Chromium akan terbuka secara otomatis.")
    print("Silakan login ke akun TikTok Anda (Bisa Scan QR Code dari aplikasi TikTok di HP).")
    print("Setelah berhasil login dan masuk ke beranda / profil:")
    print("TEKAN [ENTER] DI TERMINAL INI UNTUK MENYIMPAN SESI...")
    print("=" * 65 + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            no_viewport=True,
        )
        page = context.new_page()

        try:
            page.goto("https://www.tiktok.com/login", timeout=60000)
        except Exception as e:
            logger.warning(f"Navigasi ke login: {e}")

        input(">>> TEKAN [ENTER] DI TERMINAL SETELAH SELESAI LOGIN...")

        context.storage_state(path=str(session_path))
        print(f"\n✅ Sesi login berhasil disimpan di: {session_path}")
        browser.close()
        return True


def upload_to_tiktok(
    video_path: Path | str,
    caption: str,
    session_path: Path | str = DEFAULT_SESSION_FILE,
    headless: bool = False,
) -> bool:
    """Mengunggah video ke TikTok Studio menggunakan Playwright dan sesi tersimpan."""
    from playwright.sync_api import sync_playwright

    video_file = Path(video_path).resolve()
    session_file = Path(session_path).resolve()

    if not video_file.is_file():
        logger.error(f"File video tidak ditemukan: {video_file}")
        return False

    if not session_file.is_file():
        logger.error(
            f"Sesi login TikTok tidak ditemukan di: {session_file}\n"
            "Silakan jalankan perintah berikut untuk login 1x terlebih dahulu:\n"
            "  python auto_clipper_tiktok.py --login-tiktok"
        )
        return False

    logger.info("=" * 60)
    logger.info(f"🚀 MEMULAI UPLOAD KE TIKTOK STUDIO...")
    logger.info(f"   File Video : {video_file.name}")
    logger.info(f"   Headless   : {headless}")
    logger.info("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        context = browser.new_context(
            storage_state=str(session_file),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            no_viewport=True,
        )

        page = context.new_page()
        page.set_default_timeout(60000)

        upload_urls = [
            "https://www.tiktok.com/tiktokstudio/upload",
            "https://www.tiktok.com/creator-center/upload?from=upload",
        ]

        logger.info("Membuka halaman upload TikTok Studio...")
        opened = False
        for url in upload_urls:
            try:
                page.goto(url, wait_until="domcontentloaded")
                opened = True
                break
            except Exception as e:
                logger.warning(f"Gagal membuka {url}: {e}")

        if not opened:
            logger.error("Tidak dapat menjangkau halaman upload TikTok.")
            browser.close()
            return False

        time.sleep(4)

        if "login" in page.url.lower():
            logger.error(
                "❌ Sesi TikTok telah kedaluwarsa atau belum valid (terlempar ke halaman login).\n"
                "Silakan jalankan kembali: python auto_clipper_tiktok.py --login-tiktok"
            )
            browser.close()
            return False

        # Mencari elemen input file (termasuk jika berada di dalam iframe)
        logger.info("Mencari tombol input video di halaman TikTok Studio...")
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

        logger.info(f"Mengirimkan file video ({video_file.name}) ke TikTok...")
        file_input.first.set_input_files(str(video_file))

        # Menunggu proses upload video awal
        logger.info("Menunggu video diproses oleh server TikTok (8 detik)...")
        time.sleep(8)

        # Mencari kotak input caption / deskripsi
        caption_selectors = [
            'div[contenteditable="true"]',
            'div[role="combobox"]',
            '.notranslate[contenteditable="true"]',
            'textarea[placeholder*="caption" i]',
            'textarea[placeholder*="deskripsi" i]',
        ]

        caption_box = None
        for sel in caption_selectors:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                caption_box = loc.first
                break

        if caption_box:
            logger.info("Mengetikkan judul, caption, dan hashtag...")
            caption_box.click()
            time.sleep(0.5)

            # Bersihkan default teks bila ada
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            time.sleep(0.5)

            # Ketik per kata dengan jeda natural
            for chunk in caption.split():
                page.keyboard.type(chunk + " ", delay=20)
                time.sleep(0.04)
            time.sleep(2)
        else:
            logger.warning("Kotak input caption tidak terdeteksi otomatis, melanjutkan...")

        # Menunggu tombol Post / Publikasikan aktif
        logger.info("Mencari tombol 'Post' / 'Publikasikan'...")
        time.sleep(4)

        post_button_selectors = [
            'button:has-text("Post")',
            'button:has-text("Posting")',
            'button:has-text("Publikasikan")',
            'button[data-e2e="post_video_button"]',
            'button.btn-post',
        ]

        post_btn = None
        for p_sel in post_button_selectors:
            btn = page.locator(p_sel)
            if btn.count() > 0 and btn.first.is_visible():
                post_btn = btn.first
                break

        if post_btn:
            logger.info("Menekan tombol Post...")
            try:
                post_btn.wait_for(state="visible", timeout=30000)
                post_btn.click()
                logger.info("Tombol Post berhasil ditekan!")
            except Exception as e:
                logger.error(f"Gagal mengklik tombol post: {e}")
                browser.close()
                return False

            logger.info("Menunggu proses finalisasi publish (15 detik)...")
            time.sleep(15)
            logger.info("🎉 VIDEO BERHASIL DIPUBLIKASIKAN KE TIKTOK!")
            browser.close()
            return True
        else:
            logger.warning("Tombol Post tidak ditemukan secara otomatis.")
            if not headless:
                print("\n>>> Browser masih terbuka. Anda dapat menekan tombol Post secara manual sekarang.")
                input(">>> TEKAN [ENTER] SETELAH SELESAI MEMPOSTING...")
                browser.close()
                return True
            browser.close()
            return False


# ==============================================================================
# 5. ORCHESTRATOR & CLI
# ==============================================================================
def run_autonomous_pipeline(args: argparse.Namespace) -> None:
    history = HistoryTracker()

    # 1. Tentukan video target (bisa dari pencarian otomatis atau langsung dari URL)
    target_video: dict[str, Any] | None = None

    if args.video_url:
        logger.info(f"Menggunakan URL video spesifik: {args.video_url}")
        target_video = {
            "id": args.video_url.split("v=")[-1].split("&")[0] if "v=" in args.video_url else "custom_url",
            "title": "Video YouTube Kustom",
            "url": args.video_url,
            "view_count": 0,
            "channel": "Kustom",
            "duration": 0,
        }
    else:
        # Cari video viral
        candidates = search_viral_videos(
            query=args.query,
            min_views=args.min_views,
            min_duration_sec=args.min_duration * 60,
            max_duration_sec=args.max_duration * 60,
            limit=args.search_limit,
            history_tracker=history,
        )

        if not candidates:
            logger.warning("⚠️ Tidak ada kandidat video baru yang memenuhi kriteria pencarian.")
            print("\nTips:")
            print("1. Turunkan nilai --min-views (misal: --min-views 10000)")
            print("2. Ubah kata kunci pencarian dengan --query (misal: --query 'podcast terlucu indonesia')")
            return

        target_video = candidates[0]

    logger.info(f"🎯 Video terpilih: '{target_video['title']}' ({target_video['view_count']:,} views)")

    # 2. Proses pemotongan dan rendering klip menggunakan ENCLip
    try:
        video_file, clip_info = process_viral_video_with_enclip(
            video_meta=target_video,
            flavor=args.flavor,
            layout=args.layout,
            framing=args.framing,
            max_clips=args.max_clips,
            clip_min=args.clip_min,
            clip_max=args.clip_max,
            bgm_path=args.bgm,
            use_ai_model=args.ai_model,
        )
    except Exception as exc:
        logger.error(f"❌ Terjadi kesalahan saat memproses klip ENCLip: {exc}")
        return

    # 3. Upload ke TikTok (jika tidak dinonaktifkan dengan --no-upload)
    uploaded = False
    if args.no_upload:
        logger.info("⏩ Opsi --no-upload aktif. Klip disimpan di lokal tanpa upload ke TikTok.")
    else:
        if not Path(args.session_path).is_file():
            logger.warning(
                f"\n⚠️ Sesi TikTok belum ditemukan di {args.session_path}.\n"
                f"Klip sudah selesai dibuat di: {video_file}\n"
                f"Silakan jalankan `python auto_clipper_tiktok.py --login-tiktok` untuk menghubungkan akun TikTok Anda."
            )
        else:
            uploaded = upload_to_tiktok(
                video_path=video_file,
                caption=clip_info["caption"],
                session_path=args.session_path,
                headless=args.headless,
            )

    # 4. Catat ke riwayat
    history.record(video_meta=target_video, clip_meta=clip_info, uploaded=uploaded)
    logger.info("🏁 Siklus otomatisasi selesai dengan sukses!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ENCLip - Autonomous Viral Clipper & TikTok Uploader Pipeline"
    )
    parser.add_argument(
        "--login-tiktok",
        action="store_true",
        help="Buka browser Chromium untuk login ke akun TikTok dan simpan sesi (cukup 1x).",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Jalankan pipeline otomatis penuh (Cari video viral -> ENCLip clip -> Upload TikTok).",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="podcast viral indonesia",
        help="Kata kunci pencarian video viral di YouTube (default: 'podcast viral indonesia').",
    )
    parser.add_argument(
        "--min-views",
        type=int,
        default=50000,
        help="Batas minimum views YouTube untuk dipilih (default: 50,000).",
    )
    parser.add_argument(
        "--min-duration",
        type=int,
        default=10,
        help="Batas minimum durasi video sumber dalam menit (default: 10 menit).",
    )
    parser.add_argument(
        "--max-duration",
        type=int,
        default=180,
        help="Batas maksimum durasi video sumber dalam menit (default: 180 menit).",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        default=25,
        help="Jumlah video yang diperiksa dari pencarian YouTube (default: 25).",
    )
    parser.add_argument(
        "--flavor",
        type=str,
        default="spicy_drama",
        choices=["spicy_drama", "viral_all", "funny_blunder", "deep_meat", "hype_rage"],
        help="Gaya pemotongan momen viral AI (default: spicy_drama).",
    )
    parser.add_argument(
        "--layout",
        type=str,
        default="podcast_split",
        choices=["podcast_split", "standard", "facecam_top"],
        help="Tata letak video 9:16 (default: podcast_split).",
    )
    parser.add_argument(
        "--framing",
        type=str,
        default="crop",
        choices=["crop", "fit"],
        help="Mode framing video (default: crop).",
    )
    parser.add_argument(
        "--max-clips",
        type=int,
        default=1,
        help="Jumlah klip terbaik yang dirender (default: 1).",
    )
    parser.add_argument(
        "--clip-min",
        type=int,
        default=30,
        help="Durasi minimal klip dalam detik (default: 30).",
    )
    parser.add_argument(
        "--clip-max",
        type=int,
        default=60,
        help="Durasi maksimal klip dalam detik (default: 60).",
    )
    parser.add_argument(
        "--bgm",
        type=str,
        default="",
        help="Path ke file musik latar (.mp3/.wav) jika ingin menambahkan BGM.",
    )
    parser.add_argument(
        "--ai-model",
        type=str,
        default="gemini",
        help="Model AI untuk clipping metadata (default: 'gemini', menggunakan gemini-3.8-flash).",
    )
    parser.add_argument(
        "--video-url",
        type=str,
        default="",
        help="Jika ingin memproses URL YouTube tertentu secara langsung tanpa pencarian.",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Hanya cari video dan render klip di lokal, jangan upload ke TikTok.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Jalankan browser upload TikTok di latar belakang tanpa jendela GUI.",
    )
    parser.add_argument(
        "--session-path",
        type=str,
        default=str(DEFAULT_SESSION_FILE),
        help=f"Lokasi file sesi TikTok (default: {DEFAULT_SESSION_FILE}).",
    )

    args = parser.parse_args()

    if args.login_tiktok:
        save_tiktok_session(session_path=Path(args.session_path))
    else:
        # Default behavior: jalankan autonomous pipeline
        run_autonomous_pipeline(args)


if __name__ == "__main__":
    main()
