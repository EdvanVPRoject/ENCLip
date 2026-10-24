# ENCLip - Autonomous Podcast Clipper & Publisher

<p align="center">
  <img src="Desktop_UI/icon.png" alt="ENCLip Logo" width="128" height="128" />
</p>

<p align="center">
  <b>Sistem Otomasi Pemotongan Video Podcast & Publikasi Multi-Platform Berbasis AI</b><br>
  <i>Dilengkapi Desktop HUD Monitor, Engine Transkripsi Whisper int8, Analisis Viral Gemini, dan Playwright TikTok Publisher</i>
</p>

<p align="center">
  <a href="https://github.com/EdvanVPRoject/ENCLip/raw/main/ENCLip.exe">
    <img src="https://img.shields.io/badge/Download-ENCLip%20v1.0.0%20(Windows%20.exe)-00C853?style=for-the-badge&logo=windows&logoColor=white" alt="Download Windows Executable" />
  </a>
</p>

---

## Ringkasan Proyek

**ENCLip** adalah sistem otomatisasi pemotongan video (clipping) dan publikasi konten untuk kreator, agensi, dan podcaster. Sistem ini bekerja secara otonom di Windows untuk mengubah video podcast berdurasi panjang menjadi klip video pendek (Shorts/TikTok/Reels) berkualitas Full HD 1080p, lengkap dengan subtitle dinamis, penilaian viralitas, antrean stok, serta pengunggahan terjadwal ke TikTok Studio.

Seluruh proses dapat berjalan mandiri di latar belakang tanpa jendela CMD hitam (*100% silent execution*), dan progres kerja dipantau secara real-time melalui widget floating desktop interaktif (HUD).

---

## Fitur Utama

### 1. Autonomous Pipeline (Jadwal Otomatis Windows Task Scheduler)
* **Produksi Klip Harian (04:00 WIB)**:
  * Memindai video podcast terbaru dari YouTube secara otomatis.
  * Memproses tepat **1 video podcast per hari** untuk menjaga stabilitas resource dan kuota API.
  * Menghasilkan klip viral 1080p Full HD dan menyimpannya ke antrean stok (`Core_Data/upload_queue.json`).
* **Publikasi Berkala (Setiap 2 Jam Sekali)**:
  * Mengambil 1 klip dari antrean stok dan mengunggahnya langsung ke TikTok Studio menggunakan Playwright.
  * Mencatat detail publikasi (judul, skor viral, durasi, URL sumber, caption) ke dokumen teks ([`uploaded_clips.txt`](uploaded_clips.txt)).
  * Menghapus file video lokal `.mp4` beserta foldernya setelah upload berhasil guna menghemat kapasitas disk.

### 2. Desktop Live HUD Widget (`clipper_hud.py`)
* Widget floating modern di pojok kanan bawah layar desktop untuk memantau aktivitas proses pipeline.
* **Dua Tampilan Interaktif**:
  * **Mini Pill (440x40 px)**: Bar ringkas satu baris yang menampilkan indikator tahap aktif (Unduh, Whisper, AI Viral, Subtitle, Render, Upload), judul klip, dan tombol expand.
  * **Expanded Bento Card (520x520 px)**: Panel metriks lengkap yang membuka ke atas dengan animasi halus, menyajikan metrik render, log real-time, inspeksi rincian per tahap, dan daftar klip yang dihasilkan.
* Tombol kontrol minimize/close terletak di bagian bawah dekat jam widget.

### 3. Engine Analisis & Rendering
* **Speech-to-Text**: Menggunakan *Faster-Whisper* CPU multi-core (int8) untuk transkripsi audio presisi tinggi dengan timestamp tingkat kata.
* **Kurasi Momen Viral**: Menganalisis transkrip dengan *Google Gemini 2.5 Flash* untuk mendeteksi siklus tanya-jawab utuh, hook kalimat pembuka, dan relevansi topik tanpa terpotong di tengah kalimat.
* **Rendering Subtitle Otomatis**: Menghasilkan subtitle gaya *Smart Notice* (warna kuning aktif dengan denyut animasi) menggunakan filter libass FFmpeg.
* **Dukungan Format**: Rasio aspek 16:9 (Standard) dan 9:16 (Vertikal TikTok/Shorts) pada resolusi 1080p.

### 4. Zero-Popup Silent Execution
* Semua batch task dijalankan melalui launcher VBScript (`run_clipper_4am_silent.vbs` dan `run_uploader_2hours_silent.vbs`) dengan flag `vbHide`.
* Tidak ada jendela hitam command prompt (`cmd.exe`) atau terminal yang mengganggu saat otomasi bekerja.

---

## Panduan Penggunaan

### Cara 1: Menggunakan Aplikasi Desktop Siap Pakai (.exe)
Bagi pengguna yang ingin menjalankan antarmuka grafis manual tanpa setup teknis:
1. Unduh **[ENCLip.exe](https://github.com/EdvanVPRoject/ENCLip/raw/main/ENCLip.exe)**.
2. Jalankan `ENCLip.exe` di Windows.
3. Masukkan URL video YouTube atau file video lokal, pilih gaya subtitle, dan mulai proses pembuatan klip.

---

### Cara 2: Menjalankan Sistem Otomasi (Autoclipper & Autouploader)

#### 1. Prasyarat Lingkungan
* Windows 10 / 11 (64-bit).
* Python 3.10 atau lebih baru.
* FFmpeg terpasang pada sistem PATH.

#### 2. Instalasi Dependensi
```bash
git clone https://github.com/EdvanVPRoject/ENCLip.git
cd ENCLip
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

#### 3. Konfigurasi API Key
Salin file template konfigurasi dan masukkan API Key Gemini Anda:
```bash
copy .env.example .env
```
Isi variabel `GEMINI_API_KEY` di dalam file `.env`:
```env
GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere
```

#### 4. Login TikTok Studio (Hanya Perlu 1 Kali)
Jalankan skrip berikut untuk menyimpan sesi cookies TikTok ke `Core_Data/tiktok_session.json`:
```bash
LOGIN_TIKTOK.bat
```
*(Jendela browser Chromium akan terbuka; silakan login menggunakan akun TikTok Anda atau scan QR Code via aplikasi TikTok di HP. Sesi login akan tersimpan otomatis).*

#### 5. Menjalankan Otomasi
* **Menjalankan Pemotongan Klip Subuh Manual**:
  ```bash
  PRODUCE_1_CLIP.bat
  ```
* **Menjalankan Publikasi 1 Klip Manual**:
  ```bash
  UPLOAD_1_CLIP.bat
  ```
* **Membuka Widget HUD Desktop**:
  ```bash
  BUKA_LIVE_HUD.bat
  ```

---

## Struktur Direktori Repository

```
ENCLip/
├── auto_clipper_tiktok.py       # Mesin inti pipeline editing otomatis & TikTok publisher
├── clipper_hud.py               # Widget monitor floating desktop (PyQt6)
├── omnichannel_publisher.py      # Modul otomasi Playwright untuk TikTok & YouTube Shorts
├── autoclipper.py               # CLI entrypoint alternatif untuk publish/produce
├── auto_clipper_omnichannel.py  # Pipeline omnichannel multi-platform (TikTok, YT, IG, X)
├── rlsf_engine.py               # Closed-loop AI analytics engine
│
├── run_clipper_4am.bat          # Eksekutor batch 04:00 subuh (1 video editing)
├── run_clipper_4am_silent.vbs   # Silent launcher tanpa pop-up CMD untuk Task Scheduler
├── run_uploader_2hours.bat      # Eksekutor batch upload berkala 2 jam sekali
├── run_uploader_2hours_silent.vbs # Silent launcher tanpa pop-up CMD untuk Task Scheduler
├── BUKA_LIVE_HUD.bat            # Pintasan cepat meluncurkan widget HUD desktop
├── LOGIN_TIKTOK.bat             # Panduan login 1x untuk menyimpan sesi TikTok Studio
├── PRODUCE_1_CLIP.bat           # Trigger manual produksi 1 video podcast
├── UPLOAD_1_CLIP.bat            # Trigger manual upload 1 klip ke TikTok
│
├── Backend_API/
│   └── web_server.py            # FFmpeg wrapper, trend analyzer, dan job orchestrator
├── Desktop_UI/
│   ├── desktop_gui.py           # GUI aplikasi desktop lengkap (PyQt6)
│   ├── icon.ico / icon.png      # Aset grafis ikon aplikasi
│   ├── VanClipper.spec          # Konfigurasi packaging PyInstaller
│   └── build_desktop.bat        # Skrip kompilasi native Windows .exe
│
├── ENCLip.exe                   # Executable aplikasi Windows native siap pakai
├── requirements.txt             # Daftar dependensi modul Python
├── .env.example                 # Template konfigurasi variabel lingkungan
├── LICENSE                      # Lisensi proyek (MIT License)
└── README.md                    # Dokumentasi resmi proyek
```

---

## Keamanan Data & Privasi
* Repository ini menggunakan `.gitignore` yang ketat:
  * Seluruh file video fisik (`.mp4`, `HasilClip/*`, `VideoMentah/*`) **tidak disimpan ke repository Git**.
  * File kredensial pribadi (`.env`, `Core_Data/tiktok_session.json`) **tidak pernah diunggah ke internet**.
  * Riwayat eksekusi lokal dan dokumen catatan upload (`uploaded_clips.txt`, `*.log`, `upload_queue.json`) dikelola secara privat di komputer lokal.

---

## Lisensi
Proyek ini didistribusikan di bawah lisensi [MIT License](LICENSE). Bebas digunakan dan dikembangkan untuk kebutuhan personal maupun komersial.
