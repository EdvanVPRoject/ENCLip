# ENCLip - Native AI Video Clipper

<p align="center">
  <img src="Desktop_UI/icon.png" alt="ENCLip Logo" width="128" height="128" />
</p>

<p align="center">
  <b>Aplikasi Desktop Native AI untuk Pemotongan & Kurasi Konten Video Panjang Menjadi Klip Pendek</b><br>
  <i>Mendukung Model AI Lokal (Faster-Whisper int8 & Qwen GGUF) atau Cloud via Google Gemini API</i>
</p>

<p align="center">
  <a href="https://github.com/EdvanVPRoject/ENCLip/releases">
    <img src="https://img.shields.io/badge/Release-ENCLip%20v1.0.0%20(Installer%20%26%20Portable)-00C853?style=for-the-badge&logo=windows&logoColor=white" alt="Download Windows Release" />
  </a>
</p>

---

## Sekilas Tentang ENCLip

**ENCLip** adalah aplikasi desktop native Windows yang dirancang untuk memproses video berdurasi panjang (podcast, livestream, webinar, interview, stand-up comedy) menjadi potongan klip video pendek (Shorts, TikTok, Reels) secara presisi dan efisien.

Aplikasi ini berjalan langsung di perangkat Anda tanpa biaya langganan bulanan:
* **Privasi Penuh & Pemrosesan Lokal**: Transkripsi dan rendering audio-video diproses langsung di perangkat pengguna.
* **Dukungan Hybrid AI**: Bekerja 100% offline dengan model lokal (Faster-Whisper int8 dan LLM GGUF lokal) atau menggunakan Google Gemini Cloud untuk analisis secepat kilat.
* **Output Kualitas Tinggi**: Format 1080p Full HD dengan pilihan rasio 9:16 (vertikal), 16:9 (landscape), atau 1:1 (square), lengkap dengan subtitle dinamis berbasis libass.

---

## Fitur Utama

### 1. Antarmuka Desktop Modern (PyQt6)
* Antarmuka bersih, responsif, dan intuitif.
* Dilengkapi pemutar video interaktif dengan timeline scrubbing dan preview subtitle langsung di layar.
* Terminal terintegrasi di dalam jendela aplikasi untuk memantau proses transkripsi, penilaian momen, dan progress render FFmpeg.

### 2. Transkripsi Suara Presisi (Speech-to-Text)
* Memanfaatkan engine **Faster-Whisper** dengan optimasi int8 multi-core CPU / CUDA GPU untuk mengenali kata dan jeda dialog bahasa Indonesia dengan timestamp tingkat milidetik.
* Opsi transkripsi alternatif melalui **Google Gemini Audio** untuk pemrosesan berbasis cloud.

### 3. Deteksi Momen Penting & Kurasi AI
* Menganalisis transkrip dialog secara kontekstual untuk menemukan siklus tanya-jawab utuh, hook pembuka yang memikat, opini tajam, atau punchline menarik tanpa terpotong di tengah kalimat (*Full Context Auto-Heal*).
* Penilaian skor viralitas objektif berdasarkan dinamika emosi dan kekuatan hook.

### 4. Rendering Subtitle Otomatis (Hardsub)
* Subtitle dinamis dengan berbagai gaya tipografi (Smart Notice, Bold Punch, Highlight, Minimal).
* Pengaturan posisi teks fleksibel (bawah, tengah, atas, atau seret bebas pada kanvas preview).
* Sinkronisasi warna kata aktif saat audio diucapkan (*word-level karaoke highlight*).

---

## Dukungan Integrasi & Skrip Otomatisasi

ENCLip dirancang dengan arsitektur backend modular (`Backend_API`), sehingga selain digunakan melalui antarmuka grafis desktop, aplikasi ini **mendukung penuh integrasi skrip otomatisasi eksternal** (*Headless / CLI Automation*).

### Konsep Otomatisasi pada ENCLip:
Pengguna dapat membangun skrip otomatisasi sendiri (menggunakan Python, Bash, atau PowerShell) untuk menjalankan alur kerja clipping tanpa membuka GUI:

1. **Pemanggilan Headless via Script**:
   * Modul inti ENCLip dapat diimpor langsung ke dalam skrip Python eksternal untuk menjalankan pipeline:
     * *Ingestion*: Mengunduh video podcast terbaru via URL YouTube atau memproses file `.mp4` lokal.
     * *Transcription*: Menghasilkan file teks transkrip audio lengkap.
     * *AI Evaluation*: Menentukan rentang detik awal (`start_sec`) dan akhir (`end_sec`) klip berdasarkan skor terbaik.
     * *Rendering*: Mengeksekusi FFmpeg di background untuk memotong video, mengatur rasio aspek, dan membakar subtitle secara otomatis.

2. **Penjadwalan Berkala (Task Scheduler / Cron)**:
   * Skrip otomatisasi buatan Anda dapat didaftarkan ke **Windows Task Scheduler** (atau Cron di Linux) untuk berjalan di jam tertentu (misal: subuh atau setiap beberapa jam).
   * Proses dapat diarahkan untuk berjalan di latar belakang (*silent / background execution*) dan menulis statusnya ke file log atau webhook monitoring.

3. **Integrasi Antrean & Publikasi Mandiri**:
   * Output klip video yang dihasilkan dapat disimpan ke folder antrean lokal.
   * Pengguna dapat menghubungkan output tersebut ke pipeline publisher/uploader favorit (seperti Playwright, REST API, atau webhook bot) untuk mendistribusikan klip secara terjadwal.

---

## Pilihan Distribusi & Cara Menjalankan

### Opsi 1: Versi Native Installer (`naviteversion`) — Direkomendasikan
1. Buka folder `naviteversion/` (atau unduh dari tab [Releases](https://github.com/EdvanVPRoject/ENCLip/releases)).
2. Jalankan file **`ENCLip_Setup_v1.0.exe`**.
3. Ikuti wizard instalasi Windows:
   - Otomatis membuat Shortcut di Desktop dan Start Menu.
   - Terpasang rapi di Program Files.
   - Dilengkapi uninstaller resmi Windows (*Settings > Apps / Control Panel*).

---

### Opsi 2: Versi Portable (`portable/`) — Tanpa Instalasi
1. Buka folder `portable/`.
2. Klik dua kali pada **`ENCLip.exe`** atau jalankan **`Buka_ENCLip_Portable.bat`**.
3. Aplikasi langsung berjalan secara mandiri tanpa menyentuh registry sistem. Sangat cocok ditaruh di Flashdisk atau dipindahkan antar-PC.

---

### Opsi 3: Menjalankan dari Source Code (Developer)
1. **Clone repository**:
   ```bash
   git clone https://github.com/EdvanVPRoject/ENCLip.git
   cd ENCLip
   ```

2. **Setup virtual environment & dependensi**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Konfigurasi Environment (Opsional untuk Gemini Cloud)**:
   Salin template `.env.example` ke `.env`:
   ```bash
   copy .env.example .env
   ```
   Masukkan `GEMINI_API_KEY` Anda di dalam file `.env`.

4. **Jalankan aplikasi desktop**:
   ```bash
   python -m Desktop_UI.desktop_gui
   ```
   Atau cukup jalankan:
   ```bash
   START_ENCLIP_APP.bat
   ```

5. **Kompilasi Sendiri (Build Executable & Installer)**:
   * **Executable Native**: Jalankan `Desktop_UI\build_desktop.bat` (menggunakan PyInstaller 6).
   * **Setup Installer**: Kompilasi script `Desktop_UI\enclip_installer.iss` menggunakan Inno Setup Compiler (ISCC).

---

## Struktur Direktori Repository

```
ENCLip/
├── Backend_API/                 # Modul inti pemrosesan video, transkripsi & evaluasi AI
│   ├── web_server.py            # Core orchestrator, audio extraction, dan FFmpeg renderer
│   └── rlsf_engine.py           # Engine reinforcement learning skor kurasi
├── Desktop_UI/                  # Antarmuka Desktop Native (PyQt6)
│   ├── desktop_gui.py           # Aplikasi GUI utama, video preview, dan panel konfigurasi
│   ├── icon.ico / icon.png      # Aset ikon resolusi tinggi
│   ├── VanClipper.spec          # Konfigurasi PyInstaller 6 bundling
│   ├── build_desktop.bat        # Skrip otomatisasi build executable Windows
│   └── enclip_installer.iss     # Skrip setup installer resmi (Inno Setup)
├── Core_Data/                   # Direktori data operasional (diabaikan oleh git)
│   ├── models/                  # Bobot model Whisper / GGUF lokal
│   ├── VideoMentah/             # Folder sumber video
│   └── HasilClip/               # Folder output hasil klip video
├── ENCLip.exe                   # Executable native Windows
├── START_ENCLIP_APP.bat         # Pintasan peluncur aplikasi desktop
├── requirements.txt             # Daftar dependensi Python
├── .env.example                 # Template variabel lingkungan
├── LICENSE                      # Lisensi open-source (MIT License)
└── README.md                    # Dokumentasi resmi proyek
```

---

## Lisensi
Proyek ini didistribusikan di bawah lisensi [MIT License](LICENSE). Bebas digunakan, dimodifikasi, dan dikembangkan untuk kebutuhan personal maupun komersial.
