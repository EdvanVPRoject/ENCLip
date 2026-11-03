"""
ENCLip TikTok Studio Performance Analyzer & Smart Peak-Time Scheduler
Secara otomatis menganalisis metrik views dari TikTok Studio dan menghitung jam emas (Golden Hours) upload.
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta
import json
import logging
from pathlib import Path
import random
import re
from typing import Any

logger = logging.getLogger("TikTokAnalytics")

BASE_DIR = Path(__file__).resolve().parent
CORE_DATA_DIR = BASE_DIR / "Core_Data"
SESSION_FILE = CORE_DATA_DIR / "tiktok_session.json"
PERFORMANCE_FILE = CORE_DATA_DIR / "tiktok_performance.json"

# Jendela Jam Emas Penonton Aktif Indonesia (Flexible Audience Windows)
# Rentang waktu dinamis di mana audiens TikTok Indonesia paling aktif membuka aplikasi:
FLEXIBLE_PEAK_WINDOWS = [
    {"name": "Slot Siang (Makan Siang & Istirahat Kerja)", "start": (11, 15), "end": (13, 45)},
    {"name": "Slot Sore (Pulang Kerja & Santai Sore)",     "start": (15, 30), "end": (17, 45)},
    {"name": "Slot Malam (Prime Time Santai Indonesia)",   "start": (18, 45), "end": (21, 30)},
]

# Backward compatibility alias
DEFAULT_PEAK_SLOTS = [(11, 30), (16, 30), (19, 30)]

# Jarak minimal antar-upload untuk mencegah kanibalisasi algoritma FYP (150 menit / 2.5 jam)
MIN_SPACING_MINUTES = 150

# Jam Larangan Upload (Blackout Hours: 22:45 - 10:30 WIB)
BLACKOUT_START_TIME = (22, 45)
BLACKOUT_END_TIME = (10, 30)
BLACKOUT_START_HOUR = 23
BLACKOUT_END_HOUR = 10


def fetch_tiktok_studio_performance(
    session_path: Path | str = SESSION_FILE,
    save_path: Path | str = PERFORMANCE_FILE,
    timeout_sec: int = 35,
) -> list[dict[str, Any]]:
    """
    Membuka TikTok Studio via Playwright secara headless dan mengambil metrik performa video terkini.
    """
    s_path = Path(session_path).resolve()
    if not s_path.is_file():
        logger.warning(f"File sesi TikTok tidak ditemukan: {s_path}")
        return []

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                storage_state=str(s_path),
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900},
            )
            page = context.new_page()

            logger.info("📊 Membuka TikTok Studio Content untuk sinkronisasi performa...")
            try:
                page.goto("https://www.tiktok.com/tiktokstudio/content", wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            except Exception:
                pass

            page.wait_for_timeout(4000)
            for _ in range(4):
                page.evaluate("window.scrollBy(0, 1500)")
                page.wait_for_timeout(1000)

            full_text = page.inner_text("body")
            browser.close()

        pattern = re.compile(
            r"(\d{2}:\d{2})\n(.*?)\n([A-Za-z]{3}\s+\d{1,2},\s+\d{1,2}:\d{2}\s+[AP]M)\n(Everyone|Friends|Only me)\n([\d\.,kKmM]+)\n([\d\.,kKmM]+)\n([\d\.,kKmM]+)",
            re.DOTALL,
        )
        matches = pattern.findall(full_text)

        posts: list[dict[str, Any]] = []
        for dur, title, dt, privacy, views_str, likes_str, comments_str in matches:
            t_clean = title.split("\n")[0][:70].strip()
            v_clean = views_str.replace(",", "").strip()
            if "k" in v_clean.lower():
                v_num = int(float(v_clean.lower().replace("k", "")) * 1000)
            elif "m" in v_clean.lower():
                v_num = int(float(v_clean.lower().replace("m", "")) * 1000000)
            else:
                try:
                    v_num = int(float(v_clean))
                except ValueError:
                    v_num = 0

            # Ekstrak jam upload
            m_time = re.search(r"(\d{1,2}):(\d{2})\s+([AP]M)", dt)
            hr = 0
            if m_time:
                hr = int(m_time.group(1))
                ampm = m_time.group(3)
                if ampm == "PM" and hr < 12:
                    hr += 12
                elif ampm == "AM" and hr == 12:
                    hr = 0

            posts.append({
                "title": t_clean,
                "datetime": dt,
                "upload_hour": hr,
                "views": v_num,
                "likes": likes_str,
                "comments": comments_str,
            })

        if posts:
            out_file = Path(save_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            analysis = {
                "last_synced": datetime.now().isoformat(),
                "total_posts_analyzed": len(posts),
                "posts": posts,
            }
            out_file.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(f"✅ Sukses menganalisis {len(posts)} video dari TikTok Studio.")

        return posts

    except Exception as exc:
        logger.warning(f"Gagal mengambil analitik TikTok Studio: {exc}")
        return []


def get_cached_performance() -> dict[str, Any]:
    """Membaca cache hasil analisis performa terakhir."""
    if PERFORMANCE_FILE.is_file():
        try:
            return json.loads(PERFORMANCE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def is_in_blackout(dt: datetime) -> bool:
    """Mengecek apakah waktu berada di dalam jam mati / penonton sepi (22:45 - 10:30 WIB)."""
    t = dt.time()
    return t >= dtime(22, 45) or t < dtime(10, 30)


def get_best_performing_hours() -> list[int]:
    """
    Mengurutkan jam-jam terbaik berdasarkan rata-rata views riil dari TikTok Studio.
    Jika belum ada data, default ke prioritas jam makan siang, malam, dan sore.
    """
    data = get_cached_performance()
    posts = data.get("posts", [])
    if not posts:
        return [11, 19, 16, 12, 20, 17]

    hour_views: dict[int, list[int]] = {}
    for p in posts:
        hr = p.get("upload_hour", 0)
        hour_views.setdefault(hr, []).append(p.get("views", 0))

    avg_by_hour = {hr: (sum(v) / len(v)) for hr, v in hour_views.items()}
    sorted_hours = sorted(avg_by_hour.keys(), key=lambda h: avg_by_hour[h], reverse=True)
    return sorted_hours


def get_next_smart_upload_time(
    now: datetime | None = None,
    last_upload_time: datetime | None = None,
) -> datetime:
    """
    Menghitung jadwal upload berikutnya berbasis Jendela Waktu Fleksibel (Audience Peak Windows).
    
    Fitur Utama:
    1. Fleksibel: Tidak kaku di satu menit tertentu, mengacak menit secara organik di rentang aktif.
    2. Anti-Kanibalisasi: Menjamin jeda minimal 2.5 jam (150 menit) dari video sebelumnya agar
       algoritma TikTok punya waktu mendorong video pertama ke FYP tanpa tertimpa.
    3. Proteksi Jam Mati: Menghindari jam 22:45 - 10:30 WIB agar video tidak mandek di <10 views.
    4. Bobot Data Riil: Memprioritaskan jam-jam yang riil menghasilkan views tertinggi di akun.
    """
    if now is None:
        now = datetime.now()

    # Batas paling awal diperbolehkan upload (anti-kanibalisasi)
    earliest_allowed = now + timedelta(minutes=5)
    if last_upload_time is not None:
        anti_cannibalize_time = last_upload_time + timedelta(minutes=MIN_SPACING_MINUTES)
        if anti_cannibalize_time > earliest_allowed:
            earliest_allowed = anti_cannibalize_time

    # Dapatkan kandidat slot untuk hari ini dan besok
    candidate_slots: list[datetime] = []

    for day_offset in (0, 1):
        target_day = (now + timedelta(days=day_offset)).date()
        for win in FLEXIBLE_PEAK_WINDOWS:
            sh, sm = win["start"]
            eh, em = win["end"]

            win_start_dt = datetime.combine(target_day, dtime(sh, sm))
            win_end_dt = datetime.combine(target_day, dtime(eh, em))
            win_duration_mins = int((win_end_dt - win_start_dt).total_seconds() // 60)

            # Acak menit organik dalam jendela aktif
            offset_mins = random.randint(10, max(15, win_duration_mins - 20))
            candidate_dt = win_start_dt + timedelta(minutes=offset_mins)

            # Jika waktu sekarang berada di dalam jendela aktif hari ini
            if day_offset == 0 and win_start_dt <= now <= win_end_dt:
                if earliest_allowed <= now:
                    # Boleh upload segera dengan variasi human jitter (2 - 8 menit)
                    candidate_dt = now + timedelta(minutes=random.randint(2, 8))
                elif earliest_allowed < win_end_dt:
                    # Masih sempat di jendela ini setelah jeda anti-kanibalisasi
                    remaining_mins = int((win_end_dt - earliest_allowed).total_seconds() // 60)
                    candidate_dt = earliest_allowed + timedelta(minutes=random.randint(1, max(2, min(remaining_mins, 15))))

            if candidate_dt >= earliest_allowed and not is_in_blackout(candidate_dt):
                candidate_slots.append(candidate_dt)

    if candidate_slots:
        candidate_slots.sort()
        return candidate_slots[0]

    # Fallback darurat: slot siang besok dengan variasi acak natural
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=11, minute=random.randint(20, 50), second=0, microsecond=0)


def is_optimal_moment_to_upload(
    now: datetime | None = None,
    last_upload_time: datetime | None = None,
) -> tuple[bool, str]:
    """
    Mengevaluasi apakah detik ini adalah saat yang optimal untuk upload ke TikTok.
    Return: (is_optimal, reason_message)
    """
    if now is None:
        now = datetime.now()

    if is_in_blackout(now):
        return False, f"Saat ini jam sepi audiens ({now.strftime('%H:%M')} WIB). Disarankan menunggu jam aktif."

    if last_upload_time is not None:
        elapsed_mins = (now - last_upload_time).total_seconds() / 60
        if elapsed_mins < MIN_SPACING_MINUTES:
            wait_rem = int(MIN_SPACING_MINUTES - elapsed_mins)
            return False, f"Anti-kanibalisasi aktif: Video sebelumnya baru diupload {int(elapsed_mins)} mnt lalu. Harap tunggu {wait_rem} mnt lagi."

    current_t = now.time()
    for win in FLEXIBLE_PEAK_WINDOWS:
        st = dtime(*win["start"])
        et = dtime(*win["end"])
        if st <= current_t <= et:
            return True, f"Optimal: Berada di dalam '{win['name']}' ({st.strftime('%H:%M')}-{et.strftime('%H:%M')} WIB)."

    return False, f"Di luar jendela jam emas utama ({now.strftime('%H:%M')} WIB). Peak terdekat: {get_next_smart_upload_time(now, last_upload_time).strftime('%H:%M')} WIB."


def format_performance_summary() -> str:
    """Menghasilkan ringkasan teks performa akun untuk log / tampilan."""
    data = get_cached_performance()
    posts = data.get("posts", [])
    if not posts:
        return "Belum ada data performa TikTok Studio tersimpan."

    hour_stats: dict[int, list[int]] = {}
    for p in posts:
        hr = p.get("upload_hour", 0)
        hour_stats.setdefault(hr, []).append(p.get("views", 0))

    lines = ["📊 ANALISIS JAM EMAS TIKTOK STUDIO (BERDASARKAN DATA RIIL AKUN):"]
    for hr in sorted(hour_stats.keys()):
        v_list = hour_stats[hr]
        avg_v = sum(v_list) / len(v_list)
        status = "🔥 PEAK" if avg_v >= 80 else ("📈 BAIK" if avg_v >= 20 else "⚠️ SEPI")
        lines.append(f" - Jam {hr:02d}:00 WIB : Rata-rata {avg_v:>5.1f} views ({len(v_list)} video, Max: {max(v_list)}) [{status}]")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    posts = fetch_tiktok_studio_performance()
    print(format_performance_summary())
    print("\nNext Smart Upload Time:", get_next_smart_upload_time().strftime("%Y-%m-%d %H:%M:%S WIB"))
