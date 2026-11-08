# Reyette Downloader & Converter 🎬🎵

Reyette-dlr adalah tool sederhana berbasis **Python + FFmpeg + yt-dlp** untuk mengunduh video/audio dari berbagai platform (YouTube, TikTok, Instagram, Facebook, Twitter/X) dan mengonversinya ke format MP4/MP3 dengan dukungan **GPU encoder** (NVENC, AMF, QSV) maupun fallback CPU (libx264).

---

## ✨ Fitur Utama
- 🔍 Deteksi otomatis encoder (NVIDIA, AMD, Intel, CPU).
- 🎥 Download video dengan berbagai kualitas.
- 🎵 Ekstrak audio MP3 dengan kualitas 192 kbps.
- ⚡ Konversi cepat menggunakan GPU encoder bila tersedia.
- 📂 Output tersimpan rapi per platform (`audio/` dan `video/`).
- 🛡️ Fallback otomatis ke CPU libx264 jika GPU tidak mendukung.
- 👍 Build in ffmpeg

---

## 📦 Persyaratan
- Gunakan Python 3.12+ (jika ingin pakai ui)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [FFmpeg](https://ffmpeg.org/download.html) (pastikan ada di PATH)
- Driver GPU terbaru (jika ingin pakai NVENC/AMF/QSV)

How to use with ui (Work on windows and linux android not suport):
```bash
- git clone https://github.com/Zeev-x/reyette-dlr-v2
- cd reyette-dlr-v2
- pip install yt-dlp requests kivy
- python main.py
```

How to use no ui (android suport):
```bash
pip install yt-dlp requests
curl https://raw.githubusercontent.com/Zeev-x/reyette-dlr-v2/refs/heads/main/downloader.py >> main.py
python main.py
```

How to build:
```bash
NEXT UPDATE
```
## Tahnks to
* [yt-dlp](https://github.com/yt-dlp/yt-dlp)
* [Reyette](https://github.com/Zeev-x)
