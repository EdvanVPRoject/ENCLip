# VanClipper

MVP aplikasi clipper video lokal. Masukkan link video, lalu aplikasi akan:

1. Mengunduh video dengan `yt-dlp`.
2. Mengubah audio menjadi teks dengan `faster-whisper`.
3. Memilih momen terbaik memakai model GGUF lokal (Qwen2.5 Coder 14B atau Hermes 3 8B), Ollama lokal jika dikonfigurasi, atau heuristik lokal sebagai fallback.
4. Memotong video dan membakar subtitle ke dalam MP4 memakai `ffmpeg`.

Setelah transkripsi dan pemilihan clip selesai, clip AI langsung dirender dan ditampilkan di tahap review bersama video sumber penuh. Kamu dapat memilih gaya subtitle, format output, framing, dan layout streamer melalui preview, menambahkan clip manual, lalu menekan tombol Render clip final. Pilihan Tanpa subtitle akan menghasilkan video tanpa teks.

Pada tahap review kamu juga dapat menambahkan clip manual dengan waktu mulai dan selesai. Clip manual akan dirender bersama clip AI, dan waktu yang bertumpang tindih akan ditolak agar tidak membuat duplikat.

Setiap clip juga diberi judul, caption, dan hashtag otomatis berdasarkan transkrip clip menggunakan model lokal. Prompt metadata mengutamakan hook, rasa penasaran, manfaat/konflik, dan ajakan interaksi tanpa membuat klaim yang tidak ada di video. Judul manual tetap dipertahankan jika diisi.

Output dapat dipilih sebagai 16:9, 9:16, atau 1:1. Mode **Full video** menjaga seluruh gambar tetap terlihat dan mengisi ruang kosong dengan background blur; mode **Crop memenuhi frame** tersedia jika memang ingin gambar memenuhi layar dengan risiko bagian tertentu terpotong. Tersedia preset subtitle Bold, Highlight, Classic, Minimal, atau Tanpa subtitle. Mode Facecam di atas memakai deteksi wajah lokal dan paling cocok untuk output 9:16.

Mode pemotongan:

- **AI Highlights:** AI memilih jumlah clip otomatis atau mengikuti jumlah yang dipilih. Durasi setiap clip dapat berbeda sesuai momen, dalam batas minimum dan maksimum.
- Pada AI Highlights tersedia durasi **Auto** atau **Durasi tetap**, misalnya semua clip ditargetkan sekitar 60 detik.
- **Bagi berdasarkan jumlah:** misalnya video 10 menit menjadi 10 bagian berdurasi sekitar 1 menit.
- **Bagi berdasarkan durasi:** misalnya setiap 2 menit, sehingga video 10 menit menjadi 5 bagian.

Kualitas sumber video dapat dipilih dari UI: 360p, 480p, 720p, 1080p, atau terbaik hingga 2160p. Kualitas tersebut membatasi resolusi unduhan; hasil clip tetap mengikuti resolusi sumber.

## Prasyarat

- Python 3.10+.
- `ffmpeg` tersedia di PATH, atau paket `imageio-ffmpeg` akan menyediakan binary FFmpeg lokal.
- `yt-dlp` tersedia di PATH, misalnya `pip install yt-dlp`.
- `llama-cpp-python` untuk menjalankan model GGUF secara langsung. Pada Windows, instalasi GPU dapat membutuhkan wheel/build yang sesuai dengan CUDA kamu.
- Opsional: [Ollama](https://ollama.com/) sebagai fallback.

## Menjalankan

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Buka http://127.0.0.1:8000.

## Aplikasi desktop PyQt6

Untuk menjalankan versi native tanpa browser, klik dua kali `run_hermes_desktop.bat`, atau jalankan:

```powershell
python -m pip install -r requirements.txt
python desktop_app.py
```

Versi desktop memakai workflow dua tahap: menu `Video` digunakan untuk mengunduh atau memilih file dari komputer dan menyimpannya di `VideoMentah`, kemudian menu `Buat clip` dibuka. Di menu tersebut tersedia preview sumber, preview format output, dan contoh subtitle. Setelah transkripsi dan clip otomatis selesai, menu `Review` menampilkan video sumber serta preview hasil render; clip manual dapat ditambahkan dari posisi player sebelum `Render final`. Menu `Panduan` dan tombol tema berada di sisi kanan header.

Tahap unduh menerima link yang didukung yt-dlp, seperti YouTube, Vimeo, TikTok, Instagram, Facebook, X, dan banyak situs lain. Dukungan aktual dapat berbeda menurut provider; file lokal juga dapat dipilih dalam format MP4, MOV, MKV, WEBM, AVI, atau M4V.

Untuk membuat paket aplikasi Windows (`.exe`), klik dua kali `build_hermes_desktop.bat`. Hasilnya berada di `dist/VanClipper/VanClipper.exe`. Script tersebut juga menyalin file `.gguf` ke dalam paket, sehingga folder hasil dapat dipindahkan ke komputer lain. Karena kedua model berukuran besar, proses penyalinan dapat memerlukan ruang sekitar 18 GB.

Di dalam aplikasi desktop tersedia tombol `Cari Qwen` dan `Cari Hermes` untuk memilih model `.gguf` dari lokasi mana pun. Lokasi tersebut disimpan lokal dalam `model_paths.json`, yang sengaja diabaikan Git agar model dan path komputer pribadi tidak ikut ter-push ke GitHub.

## Repository public

Repository ini menggunakan lisensi proprietari pada file `LICENSE`. Source boleh dilihat untuk evaluasi, tetapi penggunaan, penjualan, distribusi, atau modifikasi ulang membutuhkan izin tertulis. File `.env.example` hanya berisi contoh konfigurasi; jangan pernah mengunggah `.env`, token, API key, password, model GGUF, atau video ke repository.

Laporan keamanan sebaiknya dikirim secara privat sesuai [SECURITY.md](SECURITY.md), bukan melalui issue public.

Pada proses pertama, Whisper akan mengunduh model yang dipilih ke cache lokal. Ukuran model dapat diatur:

```powershell
$env:WHISPER_MODEL = "base"
```

## Menghubungkan file GGUF

Model yang ada di folder proyek saat ini sudah akan terdeteksi otomatis:

```text
models/Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf
models/Hermes-3-Llama-3.1-8B.Q8_0.gguf
```

Jika ingin memakai path lain, set path absolut ke dua model sebelum menjalankan server. Pilihan modelnya tersedia di UI.

```powershell
$env:QWEN_GGUF_PATH = "D:\Models\qwen3-14b-instruct-q4_k_m.gguf"
$env:HERMES_GGUF_PATH = "D:\Models\hermes-7b-q4_k_m.gguf"
$env:GGUF_N_GPU_LAYERS = "-1"
python -m uvicorn app:app --reload
```

Alternatifnya, letakkan file dengan nama yang mengandung `qwen` dan `hermes` di folder `models/`; aplikasi akan mendeteksinya otomatis.

`GGUF_N_GPU_LAYERS=-1` mencoba memasukkan semua layer ke GPU. Jika memakai CPU, ubah menjadi `0`. Model hanya dimuat ketika dipilih pertama kali dan kemudian tetap berada di memory selama server berjalan.

Untuk GPU NVIDIA, gunakan `WHISPER_DEVICE=cuda` dan `WHISPER_COMPUTE_TYPE=float16`.

## Catatan

- Gunakan hanya video yang kamu punya hak untuk unduh dan olah.
- Subtitle saat ini diburn langsung ke video sehingga hasil MP4 siap dipakai untuk short-form content.
- Backend menyimpan hasil sementara di folder `data/`.
