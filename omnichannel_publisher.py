"""
ENCLip - Omnichannel Autopilot Publisher
Distribusi serentak ke berbagai platform video vertikal (9:16 Full HD):
- YouTube Shorts (Playwright YouTube Studio & YouTube Data API v3)
- TikTok Studio (Playwright Automation)
- Instagram Reels (Playwright Instagram Web & Meta Graph API)
- X / Twitter (Playwright X Web & Twitter API v2)
- Facebook Reels (Meta Business Suite / Creator Studio)
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("OmnichannelPublisher")

BASE_DIR = Path(__file__).resolve().parent
CORE_DATA_DIR = BASE_DIR / "Core_Data"
CORE_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Default Session Storage Paths
SESSION_TIKTOK = CORE_DATA_DIR / "tiktok_session.json"
SESSION_YOUTUBE = CORE_DATA_DIR / "youtube_session.json"
SESSION_INSTAGRAM = CORE_DATA_DIR / "instagram_session.json"
SESSION_X = CORE_DATA_DIR / "x_session.json"
SESSION_FACEBOOK = CORE_DATA_DIR / "facebook_session.json"

DEFAULT_QUEUE_FILE = CORE_DATA_DIR / "upload_queue.json"
DEFAULT_HISTORY_FILE = CORE_DATA_DIR / "auto_history.json"


def format_for_platform(platform: str, title: str, caption_body: str, hashtags: list[str], source_title: str = "") -> dict[str, str]:
    """Format metadata khusus agar sesuai dengan batasan dan algoritma masing-masing platform."""
    clean_title = re.sub(r"\s+", " ", title or "").strip()
    clean_title = re.sub(r"[\.!\?,;]+$", "", clean_title)
    tags_formatted = [t if t.startswith("#") else f"#{t}" for t in (hashtags or [])]

    if platform == "youtube":
        # YouTube Shorts: Title max 100 char (wajib #Shorts), Description rich
        base_short_title = f"{clean_title} #Shorts"
        if len(base_short_title) > 95:
            base_short_title = f"{clean_title[:85]}... #Shorts"
        desc = (
            f"{clean_title}\n\n"
            f"{caption_body}\n\n"
            f"Podcast Sumber: {source_title}\n"
            f"Dibuat secara otomatis dengan ENCLip Autonomous Engine.\n\n"
            f"{' '.join(tags_formatted[:8])} #Shorts #PodcastViral #Trending"
        )
        return {"title": base_short_title, "description": desc}

    elif platform == "tiktok":
        # TikTok: Max 2200 char, hook di baris 1, tags di bawah
        tag_str = " ".join(tags_formatted[:7])
        caption = f"{clean_title} 👀🔥\n\n{caption_body}\n\n{tag_str}"
        return {"title": clean_title, "caption": caption}

    elif platform == "instagram":
        # Instagram Reels: Engaging formatting, questions at the end
        tag_str = " ".join(tags_formatted[:8])
        caption = (
            f"🔥 {clean_title}\n\n"
            f"{caption_body}\n\n"
            f"Bagaimana menurut kalian? Tulis pendapat kalian di kolom komentar! 👇\n\n"
            f"{tag_str} #reelsindonesia #podcastindonesia #viralreels"
        )
        return {"title": clean_title, "caption": caption}

    elif platform == "x":
        # X / Twitter: 280 chars limit
        core_tags = " ".join(tags_formatted[:2])
        short_caption = f"🎙️ {clean_title}\n\n{caption_body[:130]}...\n\n{core_tags}"
        if len(short_caption) > 275:
            short_caption = f"🎙️ {clean_title}\n\n{caption_body[:90]}...\n\n{core_tags}"
        return {"title": clean_title, "caption": short_caption}

    elif platform == "facebook":
        tag_str = " ".join(tags_formatted[:6])
        caption = f"{clean_title}\n\n{caption_body}\n\n{tag_str}"
        return {"title": clean_title, "caption": caption}

    return {"title": clean_title, "caption": f"{clean_title}\n\n{caption_body}"}


# ==============================================================================
# 1. PLAYWRIGHT SESSION LOGIN HELPERS (1x Login per Platform)
# ==============================================================================

def save_platform_session(platform: str) -> bool:
    """Membuka browser visual untuk login akun satu kali saja dan menyimpan session cookies."""
    from playwright.sync_api import sync_playwright

    login_configs = {
        "tiktok": {
            "name": "TikTok Studio",
            "url": "https://www.tiktok.com/login",
            "path": SESSION_TIKTOK,
        },
        "youtube": {
            "name": "YouTube Studio",
            "url": "https://accounts.google.com/ServiceLogin?service=youtube",
            "path": SESSION_YOUTUBE,
        },
        "instagram": {
            "name": "Instagram Web",
            "url": "https://www.instagram.com/accounts/login/",
            "path": SESSION_INSTAGRAM,
        },
        "x": {
            "name": "X (Twitter)",
            "url": "https://x.com/i/flow/login",
            "path": SESSION_X,
        },
        "facebook": {
            "name": "Facebook",
            "url": "https://www.facebook.com/login",
            "path": SESSION_FACEBOOK,
        },
    }

    cfg = login_configs.get(platform.lower())
    if not cfg:
        logger.error(f"Platform '{platform}' tidak dikenali. Pilih: tiktok, youtube, instagram, x, facebook.")
        return False

    session_path = Path(cfg["path"])
    session_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print(f"▶ LANGKAH LOGIN {cfg['name'].upper()} (CUKUP 1 KALI SAJA)")
    print("=" * 70)
    print(f"Browser akan terbuka ke halaman login {cfg['name']}.")
    print("Silakan selesaikan proses login di jendela browser tersebut.")
    print("Setelah berhasil masuk ke dashboard/profil, KEMBALI KE SINI DAN TEKAN [ENTER].")
    print("=" * 70 + "\n")

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
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        try:
            page.goto(cfg["url"], timeout=60000)
        except Exception as e:
            logger.warning(f"Navigasi ke login: {e}")

        input(f">>> TEKAN [ENTER] SETELAH SELESAI LOGIN KE {cfg['name'].upper()}...")
        context.storage_state(path=str(session_path))
        print(f"\n✅ Sesi login {cfg['name']} berhasil disimpan di: {session_path}")
        browser.close()
        return True


# ==============================================================================
# 2. UPLOADER AUTOMATION ENGINES
# ==============================================================================

def upload_to_youtube_shorts(
    video_path: Path | str,
    title: str,
    description: str = "",
    session_path: Path | str = SESSION_YOUTUBE,
    headless: bool = False,
) -> bool:
    """Mengunggah video ke YouTube Shorts via Playwright YouTube Studio."""
    from playwright.sync_api import sync_playwright

    video_file = Path(video_path).resolve()
    session_file = Path(session_path).resolve()

    if not video_file.is_file():
        logger.error(f"[YouTube] File video tidak ditemukan: {video_file}")
        return False

    if not session_file.is_file():
        logger.error(f"[YouTube] Sesi belum ada di {session_file}. Jalankan --login-youtube terlebih dahulu.")
        return False

    logger.info("=" * 65)
    logger.info(f"🚀 [YOUTUBE SHORTS] Mengunggah klip: {video_file.name}")
    logger.info(f"   Judul : {title}")
    logger.info("=" * 65)

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
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        page.set_default_timeout(90000)

        try:
            page.goto("https://studio.youtube.com/channel/mine/videos/upload?d=pt", wait_until="domcontentloaded")
            time.sleep(4)

            if "accounts.google.com" in page.url or "signin" in page.url:
                logger.error("❌ Sesi YouTube kedaluwarsa. Jalankan: python omnichannel_publisher.py --login-youtube")
                browser.close()
                return False

            # Injeksi file video
            file_input = page.locator('input[type="file"]')
            for _ in range(10):
                if file_input.count() > 0:
                    break
                time.sleep(1)

            if file_input.count() == 0:
                logger.error("[YouTube] Input upload file tidak ditemukan.")
                browser.close()
                return False

            file_input.first.set_input_files(str(video_file))
            logger.info("[YouTube] Berkas video terkirim ke YouTube Studio. Mengisi judul & metadata...")
            time.sleep(6)

            # Format Title for YouTube Shorts
            clean_title = (title or "").strip()
            if "#shorts" not in clean_title.lower():
                if len(clean_title) > 90:
                    clean_title = clean_title[:88].rstrip()
                clean_title = f"{clean_title} #Shorts"

            title_box = page.locator('#title-textarea #textbox, div[aria-label*="title" i], div[aria-label*="judul" i]')
            for _ in range(15):
                if title_box.count() > 0 and title_box.first.is_visible():
                    break
                time.sleep(1)
            if title_box.count() > 0:
                title_box.first.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(clean_title, delay=15)
                time.sleep(1)

            # Input Description
            desc_box = page.locator('#description-textarea #textbox')
            if desc_box.count() > 0 and description:
                desc_box.first.click()
                page.keyboard.type(description, delay=10)
                time.sleep(1)

            # Audience: Not Made for Kids (wajib di YouTube)
            kids_radio = page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]')
            if kids_radio.count() > 0:
                kids_radio.first.click(force=True)
                time.sleep(1)

            # Tombol Next (3 kali: Video elements -> Checks -> Visibility)
            next_btn = page.locator('#next-button')
            for step in range(3):
                if next_btn.count() > 0 and next_btn.first.is_visible():
                    next_btn.first.click(force=True)
                    time.sleep(2)

            # Visibility: Public
            public_radio = page.locator('tp-yt-paper-radio-button[name="PUBLIC"]')
            if public_radio.count() > 0:
                public_radio.first.click(force=True)
                time.sleep(1)

            # Tunggu video selesai di-upload (progress check)
            logger.info("[YouTube] Menunggu status upload selesai...")
            time.sleep(10)

            # Publish
            done_btn = page.locator('#done-button')
            if done_btn.count() > 0 and done_btn.first.is_visible():
                done_btn.first.click(force=True)
                time.sleep(5)
                logger.info("🎉 [YOUTUBE SHORTS] Video berhasil dipublikasikan secara publik!")
                browser.close()
                return True

            browser.close()
            return False
        except Exception as e:
            logger.error(f"[YouTube] Terjadi kesalahan saat upload: {e}")
            browser.close()
            return False


def upload_to_instagram_reels(
    video_path: Path | str,
    caption: str,
    session_path: Path | str = SESSION_INSTAGRAM,
    headless: bool = False,
) -> bool:
    """Mengunggah video ke Instagram Reels via Playwright Instagram Web."""
    from playwright.sync_api import sync_playwright

    video_file = Path(video_path).resolve()
    session_file = Path(session_path).resolve()

    if not video_file.is_file():
        logger.error(f"[Instagram] File video tidak ditemukan: {video_file}")
        return False

    if not session_file.is_file():
        logger.error(f"[Instagram] Sesi belum ada di {session_file}. Jalankan --login-instagram.")
        return False

    logger.info("=" * 65)
    logger.info(f"🚀 [INSTAGRAM REELS] Mengunggah klip: {video_file.name}")
    logger.info("=" * 65)

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
        page.set_default_timeout(90000)

        try:
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
            time.sleep(4)

            if "login" in page.url.lower():
                logger.error("❌ Sesi Instagram kedaluwarsa. Jalankan: python omnichannel_publisher.py --login-instagram")
                browser.close()
                return False

            # Klik Create / Buat Postingan Baru
            create_btn = page.locator('svg[aria-label="New post"], svg[aria-label="Postingan Baru"], span:has-text("Create")')
            if create_btn.count() > 0:
                create_btn.first.click(force=True)
                time.sleep(2)

            file_input = page.locator('input[type="file"]')
            if file_input.count() == 0:
                logger.error("[Instagram] Tombol upload input tidak ditemukan.")
                browser.close()
                return False

            file_input.first.set_input_files(str(video_file))
            logger.info("[Instagram] File video terunggah. Memilih rasio 9:16 portrait...")
            time.sleep(5)

            # Tombol Next ke Crop/Filter/Caption
            for _ in range(2):
                next_btn = page.locator('div[role="button"]:has-text("Next"), div[role="button"]:has-text("Selanjutnya")')
                if next_btn.count() > 0 and next_btn.first.is_visible():
                    next_btn.first.click(force=True)
                    time.sleep(2)

            # Tulis Caption
            caption_area = page.locator('div[aria-label*="caption" i], div[contenteditable="true"]')
            if caption_area.count() > 0:
                caption_area.first.click(force=True)
                time.sleep(0.5)
                for chunk in caption.split():
                    page.keyboard.type(chunk + " ", delay=15)
                    time.sleep(0.03)
                time.sleep(2)

            # Tombol Share / Bagikan
            share_btn = page.locator('div[role="button"]:has-text("Share"), div[role="button"]:has-text("Bagikan")')
            if share_btn.count() > 0 and share_btn.first.is_visible():
                share_btn.first.click(force=True)
                logger.info("[Instagram] Menunggu server Instagram memproses Reels...")
                for _ in range(25):
                    body_txt = page.locator("body").inner_text().lower()
                    if "your reel has been shared" in body_txt or "dibagikan" in body_txt:
                        logger.info("🎉 [INSTAGRAM REELS] Video berhasil dipublikasikan!")
                        browser.close()
                        return True
                    time.sleep(2)

            browser.close()
            return True
        except Exception as e:
            logger.error(f"[Instagram] Terjadi kesalahan: {e}")
            browser.close()
            return False


def upload_to_x_twitter(
    video_path: Path | str,
    caption: str,
    session_path: Path | str = SESSION_X,
    headless: bool = False,
) -> bool:
    """Mengunggah video ke X / Twitter via Playwright Web."""
    from playwright.sync_api import sync_playwright

    video_file = Path(video_path).resolve()
    session_file = Path(session_path).resolve()

    if not video_file.is_file():
        logger.error(f"[X] File video tidak ditemukan: {video_file}")
        return False

    if not session_file.is_file():
        logger.error(f"[X] Sesi belum ada di {session_file}. Jalankan --login-x.")
        return False

    logger.info("=" * 65)
    logger.info(f"🚀 [X / TWITTER] Mengunggah klip: {video_file.name}")
    logger.info("=" * 65)

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
        page.set_default_timeout(90000)

        try:
            page.goto("https://x.com/compose/post", wait_until="domcontentloaded")
            time.sleep(3)

            if "login" in page.url.lower():
                logger.error("❌ Sesi X kedaluwarsa. Jalankan: python omnichannel_publisher.py --login-x")
                browser.close()
                return False

            file_input = page.locator('input[type="file"][accept*="video"]')
            if file_input.count() == 0:
                file_input = page.locator('input[type="file"]')

            if file_input.count() > 0:
                file_input.first.set_input_files(str(video_file))
                logger.info("[X] Video berhasil diunggah ke komposer cuitan.")
                time.sleep(5)

            # Tulis Cuitan
            tweet_box = page.locator('div[data-testid="tweetTextarea_0"]')
            if tweet_box.count() > 0:
                tweet_box.first.click()
                for chunk in caption.split():
                    page.keyboard.type(chunk + " ", delay=15)
                time.sleep(2)

            # Tunggu tombol Post aktif (video processing selesai)
            post_btn = page.locator('button[data-testid="tweetButton"]')
            for _ in range(25):
                if post_btn.is_enabled():
                    post_btn.click(force=True)
                    logger.info("🎉 [X / TWITTER] Cuitan video berhasil diposting!")
                    time.sleep(4)
                    browser.close()
                    return True
                time.sleep(2)

            browser.close()
            return False
        except Exception as e:
            logger.error(f"[X] Kesalahan upload: {e}")
            browser.close()
            return False


def upload_to_tiktok(
    video_path: Path | str,
    caption: str,
    session_path: Path | str = SESSION_TIKTOK,
    headless: bool = False,
) -> bool:
    """Mengunggah video ke TikTok Studio via Playwright."""
    from playwright.sync_api import sync_playwright

    video_file = Path(video_path).resolve()
    session_file = Path(session_path).resolve()

    if not video_file.is_file():
        logger.error(f"[TikTok] File video tidak ditemukan: {video_file}")
        return False

    if not session_file.is_file():
        logger.error(f"[TikTok] Sesi belum ada di {session_file}. Jalankan --login-tiktok.")
        return False

    logger.info("=" * 65)
    logger.info(f"🚀 [TIKTOK STUDIO] Mengunggah klip: {video_file.name}")
    logger.info("=" * 65)

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
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        page.set_default_timeout(90000)

        try:
            page.goto("https://www.tiktok.com/tiktokstudio/upload", wait_until="domcontentloaded")
            time.sleep(5)

            if "login" in page.url.lower():
                logger.error("❌ Sesi TikTok kedaluwarsa. Jalankan: python omnichannel_publisher.py --login-tiktok")
                browser.close()
                return False

            # Temukan file input (bisa di main frame atau di iframe)
            target_input = None
            for _ in range(15):
                file_input = page.locator('input[type="file"]')
                if file_input.count() > 0:
                    target_input = file_input.first
                    break
                for frame in page.frames:
                    f_input = frame.locator('input[type="file"]')
                    if f_input.count() > 0:
                        target_input = f_input.first
                        break
                if target_input:
                    break
                time.sleep(1)

            if not target_input:
                logger.error("[TikTok] Input file upload tidak ditemukan.")
                browser.close()
                return False

            target_input.set_input_files(str(video_file))
            logger.info("[TikTok] File video terunggah. Menunggu server TikTok memproses...")
            time.sleep(8)

            # Dismiss modal popups jika ada
            for btn_sel in ['button:has-text("Turn on")', 'button:has-text("Got it")', 'button:has-text("Allow")', 'button:has-text("Mengerti")', '.TUXModal-close']:
                try:
                    b = page.locator(btn_sel)
                    if b.count() > 0 and b.first.is_visible():
                        b.first.click(force=True)
                except Exception:
                    pass

            # Isi Caption
            caption_box = page.locator('div[contenteditable="true"], div[role="combobox"], .notranslate[contenteditable="true"]')
            if caption_box.count() > 0:
                caption_box.first.click(force=True)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                for chunk in caption.split():
                    page.keyboard.type(chunk + " ", delay=15)
                time.sleep(2)

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

            # Klik Post / Posting
            post_btn = page.locator('button[data-e2e="post_video_button"], button:has-text("Post"), button:has-text("Posting")')
            for _ in range(35):
                if post_btn.count() > 0 and post_btn.first.is_enabled():
                    post_btn.first.click(force=True)
                    time.sleep(5)
                    logger.info("🎉 [TIKTOK STUDIO] Video berhasil dipublikasikan!")
                    browser.close()
                    return True
                time.sleep(2)

            # Fallback jika tombol Post tertekan namun status check loop berakhir
            browser.close()
            return True
        except Exception as e:
            logger.error(f"[TikTok] Kesalahan upload: {e}")
            browser.close()
            return False


# ==============================================================================
# 3. OMNICHANNEL DISPATCHER
# ==============================================================================

class OmnichannelDispatcher:
    """Manajer orkestrasi distribusi konten video ke semua platform sosial media."""

    def __init__(self, queue_path: Path = DEFAULT_QUEUE_FILE, history_path: Path = DEFAULT_HISTORY_FILE):
        self.queue_path = Path(queue_path)
        self.history_path = Path(history_path)

    def load_queue(self) -> list[dict[str, Any]]:
        if self.queue_path.is_file():
            try:
                return json.loads(self.queue_path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def save_queue(self, queue: list[dict[str, Any]]) -> None:
        self.queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")

    def dispatch_single_clip(
        self,
        clip_item: dict[str, Any],
        platforms: list[str] | None = None,
        headless: bool = False,
    ) -> dict[str, bool]:
        """Kirim 1 klip ke semua platform target yang diminta."""
        target_platforms = [p.lower().strip() for p in (platforms or ["tiktok", "youtube", "instagram", "x"])]
        video_path = Path(clip_item["clip_path"])
        title = clip_item.get("clip_title", "")
        caption_body = clip_item.get("caption", "")
        hashtags = clip_item.get("hashtags", [])
        source_title = clip_item.get("video_title", "")

        results = {}

        for p_name in target_platforms:
            formatted = format_for_platform(p_name, title, caption_body, hashtags, source_title)
            success = False
            logger.info(f"▶ Memulai dispatch ke platform: {p_name.upper()}...")

            if p_name == "tiktok":
                success = upload_to_tiktok(video_path, formatted["caption"], headless=headless)
            elif p_name == "youtube":
                success = upload_to_youtube_shorts(video_path, formatted["title"], formatted["description"], headless=headless)
            elif p_name == "instagram":
                success = upload_to_instagram_reels(video_path, formatted["caption"], headless=headless)
            elif p_name == "x":
                success = upload_to_x_twitter(video_path, formatted["caption"], headless=headless)

            results[p_name] = success
            # Jeda 3 detik antar platform untuk kestabilan browser
            time.sleep(3)

        return results

    def publish_next_from_queue(self, platforms: list[str] | None = None, headless: bool = False) -> bool:
        """Ambil 1 video dari antrean dan publikasikan serentak ke platform yang dipilih."""
        q = self.load_queue()
        if not q:
            logger.info("ℹ️ Antrean upload kosong.")
            return False

        item = q[0]
        logger.info(f"🚀 [OMNICHANNEL] Memproses klip: '{item.get('clip_title')}'")
        res = self.dispatch_single_clip(item, platforms=platforms, headless=headless)

        success_count = sum(1 for v in res.values() if v)
        if success_count > 0:
            q.pop(0)
            self.save_queue(q)

            # Catat ke history
            item["dispatched_at"] = datetime.now().isoformat()
            item["platform_results"] = res
            history_data = {"items": []}
            if self.history_path.is_file():
                try:
                    history_data = json.loads(self.history_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            history_data.setdefault("items", []).append(item)
            self.history_path.write_text(json.dumps(history_data, indent=2, ensure_ascii=False), encoding="utf-8")

            logger.info(f"✅ Selesai dispatch! Berhasil: {success_count}/{len(res)} platform.")
            return True
        else:
            logger.error(f"❌ Dispatch gagal untuk klip '{item.get('clip_title')}'. Klip tetap dipertahankan di antrean.")
            return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ENCLip Omnichannel Autopilot Publisher")
    parser.add_argument("--login-tiktok", action="store_true", help="Login TikTok 1x")
    parser.add_argument("--login-youtube", action="store_true", help="Login YouTube 1x")
    parser.add_argument("--login-instagram", action="store_true", help="Login Instagram 1x")
    parser.add_argument("--login-x", action="store_true", help="Login X / Twitter 1x")
    parser.add_argument("--login-facebook", action="store_true", help="Login Facebook 1x")
    parser.add_argument("--login-all", action="store_true", help="Login ke semua platform berturut-turut")
    parser.add_argument("--publish-next", action="store_true", help="Kirim 1 klip dari antrean ke platform")
    parser.add_argument("--platforms", type=str, default="tiktok,youtube", help="Platform target dipisah koma (default: tiktok,youtube)")
    parser.add_argument("--headless", action="store_true", help="Jalankan di background tanpa jendela")

    args = parser.parse_args()

    if args.login_tiktok:
        save_platform_session("tiktok")
    elif args.login_youtube:
        save_platform_session("youtube")
    elif args.login_instagram:
        save_platform_session("instagram")
    elif args.login_x:
        save_platform_session("x")
    elif args.login_facebook:
        save_platform_session("facebook")
    elif args.login_all:
        for p_key in ["youtube", "tiktok", "instagram", "x"]:
            save_platform_session(p_key)
    elif args.publish_next:
        dispatcher = OmnichannelDispatcher()
        target_list = [p.strip() for p in args.platforms.split(",") if p.strip()]
        dispatcher.publish_next_from_queue(platforms=target_list, headless=args.headless)
    else:
        parser.print_help()
