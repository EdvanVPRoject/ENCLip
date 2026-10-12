@echo off
chcp 65001 >nul
echo ========================================================
echo        VanClipper - Download Model AI Lokal GGUF
echo ========================================================
echo Spek laptop Anda: RTX 2050 (VRAM 4GB) + RAM 24GB
echo.
echo Rekomendasi model yang optimal untuk spesifikasi Anda:
echo [1] Qwen 2.5 0.5B Instruct (Ultra Ringan ~390 MB) - Paling Cepat ^& Hemat VRAM
echo [2] Qwen 2.5 1.5B Instruct (Rekomendasi Utama ~1.04 GB) - Cerdas ^& Bahasa Indonesia Halus
echo [3] Keluar
echo.
set /p choice="Masukkan pilihan (1/2/3): "

if "%choice%"=="1" (
    echo.
    echo Mengunduh Qwen 2.5 0.5B ke Core_Data\models...
    curl.exe -L -C - --create-dirs -o "Core_Data\models\qwen2.5-0.5b-instruct-q4_k_m.gguf" "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
    echo.
    echo Selesai! Model tersimpan di Core_Data\models.
)
if "%choice%"=="2" (
    echo.
    echo Mengunduh Qwen 2.5 1.5B ke Core_Data\models...
    curl.exe -L -C - --create-dirs -o "Core_Data\models\qwen2.5-1.5b-instruct-q4_k_m.gguf" "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
    echo.
    echo Selesai! Model tersimpan di Core_Data\models.
)
pause
