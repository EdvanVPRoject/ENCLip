"""
ENCLip - RLSF Engine (Reinforcement Learning from Social Feedback)
================================================================
Modul analitik cerdas untuk menutup siklus feedback (Closed-Loop AI):
1. Audit Metrik Penonton: Mengecek view count secara otomatis setelah 24 jam penayangan
   di YouTube Shorts, TikTok, Instagram Reels, dan X (Twitter).
2. Filter Breakout Viral: Mengidentifikasi konten yang menembus batas viralitas (>100k views).
3. Ekstraksi DNA Viral: Menyimpan judul, banner hook, dan pola topik ke high_performing_hooks.json.
4. Prompt Injection Dinamis: Menyuntikkan contoh pemenang nyata (few-shot learning)
   ke prompt pemotongan Gemini untuk generasi klip berikutnya.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Windows UTF-8 stdout configuration
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [RLSF] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("RLSFEngine")

BASE_DIR = Path(__file__).resolve().parent
CORE_DATA_DIR = BASE_DIR / "Core_Data"
CORE_DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_HISTORY_FILE = CORE_DATA_DIR / "auto_history.json"
HIGH_PERFORMING_HOOKS_FILE = CORE_DATA_DIR / "high_performing_hooks.json"
RLSF_AUDIT_LOG_FILE = CORE_DATA_DIR / "rlsf_audit_log.json"

DEFAULT_VIRAL_THRESHOLD = 100000  # 100k views threshold

# Seed Hook Examples (Digunakan jika belum ada data riwayat 24 jam pertama)
INITIAL_SEED_WINNERS = [
    {
        "hook_title": "Bahaya Makan Usus Ayam Menurut Medis",
        "banner_hook": "DOKTER BONGKAR FAKTA INI! 😱",
        "views": 245000,
        "platform": "youtube",
        "formula": "Headline subjek medis/kesehatan tajam + curiosity gap + tanpa filler.",
    },
    {
        "hook_title": "Gaji Pertama Di Dunia Hiburan Yang Tak Terduga",
        "banner_hook": "NOMINALNYA BIKIN KAGET BANGET!",
        "views": 182000,
        "platform": "tiktok",
        "formula": "Pengakuan finansial/realita di balik layar yang tabu dibicarakan.",
    },
    {
        "hook_title": "Detik-Detik Kejadian Tragis Yang Jarang Diketahui",
        "banner_hook": "MERINDING DENGAR CERITANYA 😭",
        "views": 128000,
        "platform": "instagram",
        "formula": "Klimaks investigasi/pengalaman nyata dengan emosi mendalam.",
    },
]


# ==============================================================================
# 1. METRICS PROBE (Universal Public Views Scraper)
# ==============================================================================

def probe_youtube_shorts_views(video_id_or_url: str) -> int:
    """Mengambil jumlah views publik YouTube Shorts tanpa autentikasi via yt-dlp atau requests."""
    url = video_id_or_url
    if not url.startswith("http"):
        url = f"https://www.youtube.com/shorts/{video_id_or_url}"

    # Coba via yt-dlp dump-json cepat
    try:
        res = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-warnings", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode == 0 and res.stdout.strip():
            meta = json.loads(res.stdout.strip())
            v = int(meta.get("view_count", 0))
            if v > 0:
                return v
    except Exception as e:
        logger.debug(f"yt-dlp probe YouTube gagal: {e}")

    # Fallback cepat via HTTP regex parsing
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Cari viewCount dalam initialData
            match = re.search(r'"viewCount":\s*"(\d+)"', html)
            if match:
                return int(match.group(1))
            # Format lain: 100,523 views
            match2 = re.search(r'([\d,.]+)\s+views', html, re.IGNORECASE)
            if match2:
                raw_s = match2.group(1).replace(",", "").replace(".", "")
                if raw_s.isdigit():
                    return int(raw_s)
    except Exception as e:
        logger.debug(f"HTTP probe YouTube gagal: {e}")

    return 0


def probe_tiktok_views(video_url: str) -> int:
    """Mengambil jumlah views publik TikTok via metadata scraping."""
    if not video_url or not video_url.startswith("http"):
        return 0

    try:
        res = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-warnings", video_url],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode == 0 and res.stdout.strip():
            meta = json.loads(res.stdout.strip())
            return int(meta.get("view_count", 0))
    except Exception:
        pass

    try:
        import urllib.request
        req = urllib.request.Request(
            video_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            match = re.search(r'"playCount":\s*(\d+)', html)
            if match:
                return int(match.group(1))
    except Exception:
        pass

    return 0


def probe_views_for_platform(platform: str, post_identifier: str) -> int:
    """Universal dispatcher probe views per platform."""
    if not post_identifier:
        return 0

    p = platform.lower().strip()
    if p in ("youtube", "shorts"):
        return probe_youtube_shorts_views(post_identifier)
    elif p == "tiktok":
        return probe_tiktok_views(post_identifier)
    elif p in ("instagram", "x", "facebook"):
        # Untuk IG, X, FB fallback ke yt-dlp jika didukung
        try:
            res = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-warnings", post_identifier],
                capture_output=True,
                text=True,
                timeout=12,
                encoding="utf-8",
                errors="replace",
            )
            if res.returncode == 0 and res.stdout.strip():
                meta = json.loads(res.stdout.strip())
                return int(meta.get("view_count", 0))
        except Exception:
            pass

    return 0


# ==============================================================================
# 2. RLSF FEEDBACK ENGINE CLASS
# ==============================================================================

class RLSFEngine:
    """
    Mesin Reinforcement Learning from Social Feedback untuk ENCLip.
    Mengatur siklus analitik, penyimpanan hook viral, dan prompt injection.
    """

    def __init__(
        self,
        history_path: Path | None = None,
        hooks_path: Path | None = None,
        viral_threshold: int = DEFAULT_VIRAL_THRESHOLD,
    ):
        self.history_path = history_path or DEFAULT_HISTORY_FILE
        self.hooks_path = hooks_path or HIGH_PERFORMING_HOOKS_FILE
        self.audit_log_path = RLSF_AUDIT_LOG_FILE
        self.viral_threshold = viral_threshold

    def load_history(self) -> dict[str, Any]:
        """Membaca auto_history.json secara aman."""
        if not self.history_path.is_file():
            return {"items": []}
        try:
            return json.loads(self.history_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Gagal membaca history file: {e}")
            return {"items": []}

    def save_history(self, data: dict[str, Any]) -> None:
        """Menyimpan data history terupdate."""
        try:
            self.history_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Gagal menyimpan history: {e}")

    def load_winning_hooks(self) -> list[dict[str, Any]]:
        """Membaca daftar hook pemenang dari high_performing_hooks.json."""
        if not self.hooks_path.is_file():
            # Inisialisasi awal dengan seed winners berkualitas tinggi
            self.save_winning_hooks(INITIAL_SEED_WINNERS)
            return INITIAL_SEED_WINNERS
        try:
            items = json.loads(self.hooks_path.read_text(encoding="utf-8"))
            return items if isinstance(items, list) else []
        except Exception as e:
            logger.warning(f"Gagal membaca high_performing_hooks: {e}")
            return INITIAL_SEED_WINNERS

    def save_winning_hooks(self, hooks: list[dict[str, Any]]) -> None:
        """Menyimpan daftar hook pemenang."""
        try:
            self.hooks_path.write_text(
                json.dumps(hooks, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Gagal menyimpan high_performing_hooks: {e}")

    def sync_history_performance(self, min_age_hours: float = 24.0, force_all: bool = False) -> dict[str, Any]:
        """
        Audit 24 Jam: Memeriksa semua klip yang sudah diunggah, memperbarui views,
        dan mempromosikan klip dengan views >= threshold menjadi acuan RLSF.
        """
        hist = self.load_history()
        items = hist.get("items", [])
        if not items:
            logger.info("ℹ️ Belum ada riwayat unggahan di auto_history.json untuk diaudit.")
            return {"audited": 0, "viral_breakouts": 0}

        now = datetime.now()
        existing_hooks = self.load_winning_hooks()
        existing_titles = {h.get("hook_title", "").strip().lower() for h in existing_hooks}

        audited_count = 0
        new_viral_count = 0
        audit_events = []

        logger.info(f"🔍 [RLSF] Memulai audit performa penonton (Batas viralitas: {self.viral_threshold:,} views)...")

        for item in items:
            # Waktu dispatch
            disp_str = item.get("dispatched_at") or item.get("created_at") or ""
            if not disp_str:
                continue

            try:
                disp_time = datetime.fromisoformat(disp_str.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue

            age_hours = (now - disp_time).total_seconds() / 3600.0
            if age_hours < min_age_hours and not force_all:
                continue

            audited_count += 1
            clip_title = item.get("clip_title") or item.get("title") or "Untitled Clip"
            logger.info(f"📊 Mengaudit klip: '{clip_title}' (Usia: {age_hours:.1f} jam)")

            # Cek views untuk setiap platform yang berhasil
            platform_results = item.get("platform_results", {})
            metrics = item.setdefault("metrics", {})
            total_clip_views = 0

            for p_name, success in platform_results.items():
                if not success:
                    continue

                post_url = item.get(f"{p_name}_url") or item.get("post_url") or ""
                # Coba probe views
                views = probe_views_for_platform(p_name, post_url)
                if views > 0:
                    metrics[f"{p_name}_views"] = views
                    metrics[f"{p_name}_last_checked"] = now.isoformat()
                    logger.info(f"   Platform {p_name.upper()}: {views:,} views")
                else:
                    views = metrics.get(f"{p_name}_views", 0)

                total_clip_views += views

            metrics["total_views"] = total_clip_views
            item["last_audit_at"] = now.isoformat()

            # Apakah menembus batas viralitas?
            if total_clip_views >= self.viral_threshold or item.get("viral_champion"):
                item["viral_champion"] = True
                norm_title = clip_title.strip().lower()

                if norm_title not in existing_titles and norm_title:
                    new_winner = {
                        "hook_title": clip_title,
                        "banner_hook": item.get("banner_hook", clip_title[:45]),
                        "caption_preview": item.get("caption", "")[:120],
                        "views": total_clip_views,
                        "source_title": item.get("video_title", ""),
                        "added_at": now.isoformat(),
                        "age_hours": round(age_hours, 1),
                        "formula": "Terbukti viral >100k views pada distribusi otomatis.",
                    }
                    existing_hooks.append(new_winner)
                    existing_titles.add(norm_title)
                    new_viral_count += 1
                    logger.info(f"🔥 [VIRAL BREAKOUT!] Klip '{clip_title}' ({total_clip_views:,} views) ditambahkan ke acuan RLSF!")

            audit_events.append({
                "clip_title": clip_title,
                "total_views": total_clip_views,
                "age_hours": round(age_hours, 1),
                "is_viral": total_clip_views >= self.viral_threshold,
            })

        # Urutkan hook pemenang berdasarkan views tertinggi
        existing_hooks.sort(key=lambda x: int(x.get("views", 0)), reverse=True)
        # Batasi simpan 20 hook terbaik
        self.save_winning_hooks(existing_hooks[:20])
        self.save_history(hist)

        # Simpan audit log
        try:
            self.audit_log_path.write_text(
                json.dumps({
                    "last_audit": now.isoformat(),
                    "audited_count": audited_count,
                    "new_viral_count": new_viral_count,
                    "events": audit_events,
                }, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception:
            pass

        logger.info(f"✅ Selesai audit RLSF! Diaudit: {audited_count} klip, Pemenang viral baru: {new_viral_count}.")
        return {"audited": audited_count, "viral_breakouts": new_viral_count}

    def get_rlsf_prompt_injection(self, max_examples: int = 4) -> str:
        """
        Menghasilkan instruksi prompt dinamis (Few-Shot Prompt Injection)
        yang dimasukkan ke prompt Gemini di web_server.py.
        """
        hooks = self.load_winning_hooks()
        if not hooks:
            return ""

        top_hooks = sorted(hooks, key=lambda x: int(x.get("views", 0)), reverse=True)[:max_examples]

        bullet_points = []
        for h in top_hooks:
            v_str = f"{int(h.get('views', 0)):,} views"
            t = h.get("hook_title", "")
            bh = h.get("banner_hook", "")
            form = h.get("formula", "Struktur curiosity-gap padat")
            bullet_points.append(
                f"- [{v_str}] Judul: \"{t}\"\n"
                f"  * Hook Banner: \"{bh}\"\n"
                f"  * Pola Sukses: {form}"
            )

        examples_text = "\n".join(bullet_points)

        injection = (
            "\n"
            "==============================================================================\n"
            "🔥 PREFERENSI FEEDBACK-LOOP KONTEN VIRAL TERBUKTI (RLSF REAL PERFORMANCE):\n"
            "Data analitik 24 jam membuktikan bahwa klip dengan struktur dan gaya berikut\n"
            "berhasil menembus >100.000 views di YouTube Shorts, TikTok, dan Reels.\n"
            "JADIKAN CONTOH PEMENANG INI SEBAGAI ACUAN UTAMA SAAT MEMILIH SEGMEN & MEMBUAT JUDUL:\n"
            f"{examples_text}\n\n"
            "ATURAN RLSF:\n"
            "1. PILIH MOMEN YANG MEMILIKI TENSI EMOSIONAL ATAU BOBOT INFORMASI SETARA CONTOH DI ATAS.\n"
            "2. JUDUL ('hook_title') WAJIB MENGADOPSI POLA DI ATAS: Jelas subjeknya, ringkas 4-7 kata, dan tidak menggantung!\n"
            "==============================================================================\n"
        )
        return injection


# ==============================================================================
# 3. CONVENIENCE MODULE FUNCTIONS
# ==============================================================================

def get_rlsf_prompt_injection() -> str:
    """Helper global yang langsung dipanggil oleh Backend_API/web_server.py."""
    engine = RLSFEngine()
    return engine.get_rlsf_prompt_injection()


def trigger_rlsf_audit(force_all: bool = False) -> dict[str, Any]:
    """Helper global untuk memicu audit performa."""
    engine = RLSFEngine()
    return engine.sync_history_performance(min_age_hours=24.0, force_all=force_all)


# ==============================================================================
# 4. CLI INTERFACE
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ENCLip RLSF Feedback Engine")
    parser.add_argument("--audit-now", action="store_true", help="Jalankan audit performa views 24 jam sekarang")
    parser.add_argument("--force-all", action="store_true", help="Audit semua klip tanpa melihat batas waktu 24 jam")
    parser.add_argument("--status", action="store_true", help="Tampilkan daftar hook viral pemenang saat ini")
    parser.add_argument("--print-prompt", action="store_true", help="Tampilkan teks prompt injection RLSF")
    parser.add_argument("--add-winner", type=str, help="Tambah hook pemenang manual (Judul)")
    parser.add_argument("--views", type=int, default=150000, help="Jumlah views untuk winner manual")
    parser.add_argument("--threshold", type=int, default=DEFAULT_VIRAL_THRESHOLD, help="Set threshold views viral")

    args = parser.parse_args()
    engine = RLSFEngine(viral_threshold=args.threshold)

    if args.audit_now:
        res = engine.sync_history_performance(min_age_hours=0.0 if args.force_all else 24.0, force_all=args.force_all)
        print(f"\nHasil Audit: {res}")
    elif args.status:
        hooks = engine.load_winning_hooks()
        print(f"\n🏆 DAFTAR VIRAL CHAMPION HOOKS ({len(hooks)} item):")
        for i, h in enumerate(hooks, 1):
            print(f"{i}. [{int(h.get('views', 0)):,} views] {h.get('hook_title')}")
            print(f"   Hook: {h.get('banner_hook')} | Ditambahkan: {h.get('added_at', 'Initial Seed')}")
    elif args.print_prompt:
        inj = engine.get_rlsf_prompt_injection()
        print("\n--- INJECTED RLSF PROMPT ---")
        print(inj)
    elif args.add_winner:
        hooks = engine.load_winning_hooks()
        hooks.append({
            "hook_title": args.add_winner,
            "banner_hook": args.add_winner.upper()[:45],
            "views": args.views,
            "added_at": datetime.now().isoformat(),
            "formula": "Manual champion entry.",
        })
        engine.save_winning_hooks(hooks)
        print(f"✅ Berhasil menambahkan '{args.add_winner}' dengan {args.views:,} views!")
    else:
        parser.print_help()
