"""
ENCLip - Autoclipper Entrypoint & CLI Launcher
=============================================
Menghubungkan otomatisasi publisher TikTok & omnichannel dengan pipeline clipper.
Mendukung:
- --upload-only [--headless]: Mengambil 1 klip dari Core_Data/upload_queue.json dan upload ke TikTok Studio.
- --produce-only: Menghasilkan klip video baru dan memasukkannya ke Core_Data/upload_queue.json.
- Full omnichannel pipeline via auto_clipper_omnichannel.py
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Configure utf-8 stdout/stderr for Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AutoClipper")

BASE_DIR = Path(__file__).resolve().parent
CORE_DATA_DIR = BASE_DIR / "Core_Data"
CORE_DATA_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = CORE_DATA_DIR / "upload_queue.json"
HISTORY_FILE = CORE_DATA_DIR / "auto_history.json"


def handle_upload_only(headless: bool = False, platforms: list[str] | None = None, count: int = 2) -> bool:
    """Upload sejumlah klip video dari antrean stok ke platform target (TikTok Studio)."""
    from omnichannel_publisher import OmnichannelDispatcher

    target_platforms = platforms or ["tiktok"]
    dispatcher = OmnichannelDispatcher(queue_path=QUEUE_FILE, history_path=HISTORY_FILE)

    total_successful = 0
    for i in range(count):
        queue = dispatcher.load_queue()
        if not queue:
            if i == 0:
                logger.warning("ℹ️ Antrean upload kosong di Core_Data/upload_queue.json.")
                print("STATUS ANTREAN: 0 File Video Siap Upload.")
            else:
                logger.info(f"ℹ️ Antrean habis setelah berhasil mengunggah {total_successful} klip.")
            break

        item = queue[0]
        clip_title = item.get("clip_title", "Untitled Clip")
        total_stock = len(queue)
        logger.info(f"🚀 [PUBLISHER #{i+1}/{count}] Mengunggah file: '{clip_title}' | 📊 Total Stok: {total_stock} File")

        success = dispatcher.publish_next_from_queue(platforms=target_platforms, headless=headless)

        remaining_queue = dispatcher.load_queue()
        remaining_stock = len(remaining_queue)

        if success:
            total_successful += 1
            logger.info(f"🎉 VIDEO #{i+1}/{count} BERHASIL DIPUBLIKASIKAN KE TIKTOK!")
            logger.info(f"📊 STATUS ANTREAN TERKINI: {remaining_stock} File Video Siap Upload.")
            logger.info(f"✅ Berhasil mengunggah klip '{clip_title}' ke TikTok dari antrean.")
        else:
            logger.error(f"❌ Gagal mengunggah klip '{clip_title}' ke TikTok Studio.")
            break

        if i < count - 1:
            logger.info("⏳ Memberi jeda 30 detik sebelum mengunggah video berikutnya...")
            time.sleep(30)

    return total_successful > 0


def main():
    parser = argparse.ArgumentParser(description="ENCLip Autoclipper & Publisher CLI")
    parser.add_argument("--upload-only", action="store_true", help="Kirim klip dari antrean stok ke TikTok")
    parser.add_argument("--count", "--upload-count", type=int, default=2, dest="count", help="Jumlah video yang diunggah per sesi (default: 2)")
    parser.add_argument("--produce-only", action="store_true", help="Hasilkan klip baru dan masukkan ke antrean stok")
    parser.add_argument("--headless", action="store_true", help="Jalankan browser di background tanpa GUI")
    parser.add_argument("--platforms", type=str, default="tiktok", help="Platform target (default: tiktok)")
    parser.add_argument("--url", type=str, help="URL video YouTube podcast spesifik")
    parser.add_argument("--login-tiktok", action="store_true", help="Login TikTok Studio 1x untuk simpan sesi")
    parser.add_argument("--login-all", action="store_true", help="Login ke semua platform 1x")

    args, unknown = parser.parse_known_args()

    if args.login_tiktok:
        from omnichannel_publisher import save_platform_session
        save_platform_session("tiktok")
        sys.exit(0)
    elif args.login_all:
        from omnichannel_publisher import save_platform_session
        for p in ["tiktok", "youtube", "instagram", "x"]:
            save_platform_session(p)
        sys.exit(0)

    platform_list = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]

    if args.upload_only:
        success = handle_upload_only(headless=args.headless, platforms=platform_list, count=args.count)
        sys.exit(0 if success else 1)

    elif args.produce_only:
        from auto_clipper_omnichannel import OmnichannelAutopilot, fetch_viral_podcast_candidates

        autopilot = OmnichannelAutopilot()
        target_url = args.url
        if not target_url:
            candidates = fetch_viral_podcast_candidates(query=args.query, max_results=1)
            if candidates:
                target_url = candidates[0]["url"]
            else:
                logger.error("Tidak ditemukan kandidat video baru.")
                sys.exit(1)

        autopilot.process_and_queue(
            video_url=target_url,
            target_platforms=platform_list,
            auto_publish_first=False,
            headless=args.headless,
        )
        sys.exit(0)

    else:
        # Default fallback to auto_clipper_omnichannel
        import subprocess
        cmd = [sys.executable, str(BASE_DIR / "auto_clipper_omnichannel.py")] + sys.argv[1:]
        res = subprocess.run(cmd)
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()
