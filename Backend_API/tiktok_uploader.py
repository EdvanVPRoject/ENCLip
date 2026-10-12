"""
Modul Otomasi Upload TikTok menggunakan Playwright.
Mendukung:
1. Penyimpanan sesi login (login manual sekali, simpan cookies).
2. Otomatisasi pengunggahan klip video ke TikTok Creator Studio / TikTok Studio.
3. Pengisian caption, hashtag yang digenerate oleh Gemini / AI.
4. Opsi 'headless' atau 'visible' browser untuk debugging.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TikTokUploader")

DEFAULT_SESSION_FILE = Path(__file__).parent.parent / "Core_Data" / "tiktok_session.json"


def save_tiktok_session(session_path: Path | str = DEFAULT_SESSION_FILE) -> bool:
    """
    Membuka browser Chromium agar user dapat login secara manual ke akun TikTok.
    Setelah login selesai dan user menekan ENTER di terminal, sesi disimpan.
    """
    from playwright.sync_api import sync_playwright

    session_path = Path(session_path)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("▶ LANGKAH LOGIN TIKTOK")
    print("=" * 60)
    print("Browser Chromium akan terbuka.")
    print("Silakan login ke akun TikTok Anda (bisa scan QR Code atau username/password).")
    print("Pastikan sudah berhasil masuk ke beranda / profil TikTok.")
    print("=" * 60 + "\n")

    with sync_playwright() as p:
        # Buka browser terlihat (bukan headless)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            page.goto("https://www.tiktok.com/login", timeout=60000)
        except Exception as e:
            logger.warning(f"Navigasi lambat atau terhenti: {e}")

        print(">>> Masuk ke TikTok di browser sekarang...")
        print(">>> Setelah Anda selesai login dan halaman utama muncul,")
        input(">>> TEKAN [ENTER] DI TERMINAL INI UNTUK MENYIMPAN SESI...")

        # Simpan state (cookies + local storage)
        context.storage_state(path=str(session_path))
        print(f"\n✅ Berhasil! Sesi login disimpan di: {session_path}")
        browser.close()
        return True


def upload_to_tiktok(
    video_path: str | Path,
    caption: str,
    session_path: Path | str = DEFAULT_SESSION_FILE,
    headless: bool = False,
    timeout_minutes: int = 5,
) -> bool:
    """
    Mengunggah video ke TikTok Studio menggunakan sesi login tersimpan.
    """
    from playwright.sync_api import sync_playwright

    video_file = Path(video_path).resolve()
    session_path = Path(session_path).resolve()

    if not video_file.exists():
        logger.error(f"File video tidak ditemukan: {video_file}")
        return False

    if not session_path.exists():
        logger.error(
            f"File sesi login tidak ditemukan di: {session_path}\n"
            "Jalankan langkah login terlebih dahulu dengan perintah: "
            "python tiktok_uploader.py --login"
        )
        return False

    logger.info(f"Memulai proses upload untuk video: {video_file.name}")
    logger.info(f"Caption: {caption[:80]}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        context = browser.new_context(
            storage_state=str(session_path),
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            no_viewport=True,
        )

        page = context.new_page()
        page.set_default_timeout(60000)

        # Navigasi ke halaman upload / TikTok Studio
        upload_urls = [
            "https://www.tiktok.com/tiktokstudio/upload",
            "https://www.tiktok.com/creator-center/upload?from=upload",
        ]

        logger.info("Membuka halaman upload TikTok...")
        opened = False
        for url in upload_urls:
            try:
                page.goto(url, wait_until="domcontentloaded")
                opened = True
                break
            except Exception as e:
                logger.warning(f"Gagal membuka {url}: {e}")

        if not opened:
            logger.error("Tidak dapat membuka halaman upload TikTok.")
            browser.close()
            return False

        time.sleep(4)

        # Periksa apakah sesi expired (misal diredirect ke login)
        if "login" in page.url.lower():
            logger.error("Sesi TikTok sudah kedaluwarsa (terlempar ke halaman login). Silakan jalankan --login ulang.")
            browser.close()
            return False

        # Cari input file
        logger.info("Mencari tombol input video...")
        file_input = None

        # Terkadang input file berada di dalam iframe
        for _ in range(10):
            try:
                # Cek di frame utama
                file_input = page.locator('input[type="file"]')
                if file_input.count() > 0:
                    break
                # Cek di iframes jika ada
                for frame in page.frames:
                    iframe_input = frame.locator('input[type="file"]')
                    if iframe_input.count() > 0:
                        file_input = iframe_input
                        break
                if file_input and file_input.count() > 0:
                    break
            except Exception:
                pass
            time.sleep(2)

        if not file_input or file_input.count() == 0:
            logger.error("Input file upload tidak ditemukan di halaman.")
            browser.close()
            return False

        logger.info(f"Mengirim file video ({video_file.name}) ke TikTok...")
        file_input.first.set_input_files(str(video_file))

        # Tunggu proses upload & rendering form caption muncul
        logger.info("Menunggu video diproses oleh TikTok...")
        time.sleep(8)

        # Cari input caption / description
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
            if loc.count() > 0:
                caption_box = loc.first
                break

        if caption_box:
            logger.info("Menulis caption dan hashtag...")
            caption_box.click()
            time.sleep(0.5)

            # Bersihkan default teks jika ada
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            time.sleep(0.5)

            # Ketik caption (gunakan interval agar tidak dideteksi bot brutal)
            # Ketik per potongan kata
            for chunk in caption.split(" "):
                page.keyboard.type(chunk + " ", delay=25)
                time.sleep(0.05)
            time.sleep(2)
        else:
            logger.warning("Elemen input caption tidak ditemukan, melanjutkan tanpa ubah caption...")

        # Cari tombol Post / Publikasikan
        logger.info("Mencari tombol 'Post' / 'Publikasikan'...")
        time.sleep(5)

        post_button_selectors = [
            'button:has-text("Post")',
            'button:has-text("Posting")',
            'button:has-text("Publikasikan")',
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
            # Tunggu hingga tombol tidak disabled
            try:
                post_btn.wait_for(state="visible", timeout=30000)
                post_btn.click()
                logger.info("Tombol Post berhasil ditekan!")
            except Exception as e:
                logger.error(f"Gagal klik tombol post: {e}")
                browser.close()
                return False

            # Tunggu konfirmasi selesai upload
            logger.info("Menunggu proses finalisasi publish (15 detik)...")
            time.sleep(15)
            logger.info("🎉 Video berhasil dipublikasikan ke TikTok!")
            browser.close()
            return True
        else:
            logger.warning("Tombol Post tidak ditemukan secara otomatis.")
            if not headless:
                logger.info("Browser masih terbuka. Anda dapat menekan tombol Post secara manual sekarang.")
                input("Tekan [ENTER] setelah selesai memposting manual...")
            browser.close()
            return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TikTok Video Auto Uploader")
    parser.add_argument("--login", action="store_true", help="Buka browser untuk login dan simpan sesi")
    parser.add_argument("--video", type=str, help="Path ke file video MP4 yang akan diupload")
    parser.add_argument("--caption", type=str, default="Video seru hari ini! #fyp #viral", help="Caption video")
    parser.add_argument("--headless", action="store_true", help="Jalankan di background tanpa antarmuka browser")

    args = parser.parse_args()

    if args.login:
        save_tiktok_session()
    elif args.video:
        upload_to_tiktok(video_path=args.video, caption=args.caption, headless=args.headless)
    else:
        parser.print_help()
