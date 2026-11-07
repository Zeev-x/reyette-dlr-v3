# Created by Reyette
# Thanks for yt-dlp and ffmpeg

import argparse
import os
import subprocess
import yt_dlp
import re
import requests
import sys
import platform
from types import SimpleNamespace

if platform.system() == "Windows":
    BASE_DIR = "/Reyette-Downloader"
    FFMPEG_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ffmpeg",
        "ffmpeg-win64",
    )
    FFMPEG_EXECUTABLE = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
else:
    BASE_DIR = "Reyette-Downloader"
    FFMPEG_DIR = None
    FFMPEG_EXECUTABLE = "ffmpeg"

def find_cover():
    asset_path = os.path.join("cover", "cover.png")
    app_dir = (
        os.path.dirname(os.path.abspath(sys.executable))
        if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__))
    )
    external_path = os.path.join(app_dir, asset_path)
    if os.path.isfile(external_path):
        return external_path

    bundled_paths = (
        getattr(sys, "_MEIPASS", None),
        os.path.dirname(os.path.abspath(__file__)),
    )

    for base_path in bundled_paths:
        if not base_path:
            continue
        candidate = os.path.join(base_path, asset_path)
        if candidate != external_path and os.path.isfile(candidate):
            return candidate
    return None

def parse_args():
    parser = argparse.ArgumentParser(
        description="Download media dari URL dengan format: downloader.py url type quality"
    )
    parser.add_argument("url", nargs="?", help="URL target")
    parser.add_argument("type", nargs="?", help="Jenis download: mp3 atau mp4")
    parser.add_argument("quality", nargs="?", help="Kualitas: 360p, 480p, 720p, 1080p, atau max")
    return parser.parse_args()

def is_windows():
    operating_system = platform.system()
    if operating_system == "Windows":
        return True
    else:
        return False


def create_youtube_dl(options=None):
    ydl_options = dict(options or {})
    if FFMPEG_DIR is not None:
        ydl_options["ffmpeg_location"] = FFMPEG_DIR
    return yt_dlp.YoutubeDL(ydl_options)


def normalize_type(value):
    if value is None:
        return "MP4"
    if str(value).strip().lower() in {"mp3", "audio"}:
        return "MP3"
    return "MP4"


def resolve_quality(value):
    if value is None:
        return "bestvideo[vcodec!*=av01]"
    x_qual = str(value).strip().lower()
    if x_qual in ["360p", "360"]:
        return "bestvideo[height<=360][vcodec!*=av01]"
    if x_qual in ["480p", "480"]:
        return "bestvideo[height<=480][vcodec!*=av01]"
    if x_qual in ["720p", "720"]:
        return "bestvideo[height<=720][vcodec!*=av01]"
    if x_qual in ["1080p", "1080"]:
        return "bestvideo[height<=1080][vcodec!*=av01]"
    if x_qual == "max":
        return "bestvideo[vcodec!*=av01]"
    return "bestvideo[vcodec!*=av01]"


def get_url(args=None):
    if args and getattr(args, "url", None):
        return args.url
    if len(sys.argv) > 1 and sys.argv[1] not in {"-h", "--help"}:
        return sys.argv[1]
    return input("Masukkan URL: ").strip()


def get_type(args=None):
    if args and getattr(args, "type", None):
        return normalize_type(args.type)
    if len(sys.argv) > 2:
        return sys.argv[2].upper()
    return input("Pilih mode (MP3/MP4): ").strip().upper()


def get_quality(args=None):
    if args and getattr(args, "quality", None):
        return resolve_quality(args.quality)
    if len(sys.argv) > 3:
        return resolve_quality(sys.argv[3])
    x_qual = input("Pilih kualitas (360p/480p/720p/1080p/max): ").strip().lower()
    return resolve_quality(x_qual)

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|#]', '', name)
    return name.strip().replace(' ', '_')

def detect_encoder():
    try:
        if is_windows() == True:
            result = subprocess.run(
                [FFMPEG_EXECUTABLE, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            result = subprocess.run(
                [FFMPEG_EXECUTABLE, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
        encoders = result.stdout.lower()
        if "h264_nvenc" in encoders:
            return "h264_nvenc"   # NVIDIA
        elif "h264_amf" in encoders:
            return "h264_amf"     # AMD
        elif "h264_qsv" in encoders:
            return "h264_qsv"     # Intel QuickSync
        else:
            return "libx264"      # Fallback CPU
    except Exception:
        return "libx264"

def double_cmd(video_file, audio_file, output_file, encoder=None):
    if encoder is None:
        encoder = detect_encoder()
    cmd = [FFMPEG_EXECUTABLE, "-y", "-hwaccel", "none", "-i", video_file,
           "-hwaccel", "none", "-i", audio_file,
           "-pix_fmt", "yuv420p", "-c:v", encoder]
    if encoder in ["h264_nvenc", "h264_amf", "h264_qsv"]:
        cmd += ["-preset", "slow", "-rc:v", "vbr", "-cq", "8",
                "-b:v", "16M", "-maxrate", "20M", "-bufsize", "25M"]
    else:
        cmd += ["-preset", "slow", "-crf", "23"]
    cmd += ["-c:a", "aac", "-b:a", "320k", output_file]
    return cmd

def single_cmd(video_file, output_file, encoder=None):
    if encoder is None:
        encoder = detect_encoder()
    cmd = [FFMPEG_EXECUTABLE, "-y", "-hwaccel", "none", "-i", video_file,
           "-pix_fmt", "yuv420p", "-c:v", encoder]
    if encoder in ["h264_nvenc", "h264_amf", "h264_qsv"]:
        cmd += ["-preset", "slow", "-rc:v", "vbr", "-cq", "8",
                "-b:v", "16M", "-maxrate", "20M", "-bufsize", "25M"]
    else:
        cmd += ["-preset", "slow", "-crf", "23"]
    cmd += ["-c:a", "aac", "-b:a", "320k", output_file]
    return cmd

def audio_cmd(audio_file, output_file):
    cover_file = find_cover()

    if cover_file:
        cmd = [
            FFMPEG_EXECUTABLE, "-y",
            "-i", audio_file,
            "-i", cover_file,
            "-map", "0:a", "-map", "1:v",
            "-c:a", "libmp3lame", "-q:a", "0",
            "-c:v", "mjpeg",
            "-disposition:v", "attached_pic",
            "-id3v2_version", "3",
            output_file
        ]
    else:
        cmd = [
            FFMPEG_EXECUTABLE, "-y",
            "-i", audio_file,
            "-c:a", "libmp3lame", "-q:a", "0",
            output_file
        ]
    return cmd

def detect_platform(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "tiktok.com" in url:
        return "tiktok"
    elif "facebook.com" in url or "fb.watch" in url:
        return "facebook"
    elif "instagram.com" in url:
        return "instagram"
    elif "xhamster.com" in url:
        return "xhamster"
    elif "xvideos.com" in url:
        return "xvideos"
    elif "xnxx.com" in url:
        return "xnxx"
    elif "twitter.com" in url or "x.com" in url:
        return "twitter"
    else:
        return "other"

def do_work(args=None):
    def log(msg, replace=False):
        if replace:
            sys.stdout.write("\r" + msg)
            sys.stdout.flush()
        else:
            print(msg, flush=True)

    if args is None:
        args = parse_args()

    try:
        url = get_url(args)
        mode = get_type(args)
        
        platform = detect_platform(url)
        
        target_dir = os.path.join(BASE_DIR, "audio" if mode == "MP3" else "video", platform)
        os.makedirs(target_dir, exist_ok=True)

        if mode == "MP3":
            log(f"Downloading MP3 from {platform}...")
            ydl_opts = {
                'outtmpl': f'{target_dir}/%(title)s.%(ext)s',
                'format': 'bestaudio/best',
                'noprogress': False,
                'quiet': False,
                'force-overwrites': True
            }
            with create_youtube_dl(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
                audio_file = ydl.prepare_filename(result)

            log(f"Processing audio with ffmpeg...")
            output_file = os.path.join(target_dir, f"{sanitize_filename(result.get('title', 'audio'))}.mp3")
            cover_file = os.path.join(
                os.path.dirname(output_file),
                os.path.splitext(os.path.basename(audio_file))[0] + "_cover.png"
            )
            
            cmd = audio_cmd(audio_file, output_file)
            if cmd:
                if is_windows() == True:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                else:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )

                for line in process.stdout:
                    log(line.strip())
                process.wait()
                
                log(f"✅ Success: {output_file}")
                if os.path.exists(audio_file) and audio_file != output_file:
                    os.remove(audio_file)
                if os.path.exists(cover_file):
                    os.remove(cover_file)
        elif platform == "youtube":
            fmt = get_quality(args)
            log(f"Mulai mengunduh dari {platform}: {url}")

            ydl_opts_v = {
                'outtmpl': f'{target_dir}/v_temp.%(ext)s', 
                'format': fmt,
                'quiet': True,
                'no_warnings': True,
                'force-overwrites': True
            }
            ydl_opts_a = {
                'outtmpl': f'{target_dir}/a_temp.%(ext)s', 
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'force-overwrites': True
            }

            with create_youtube_dl(ydl_opts_v) as ydl:
                result_v = ydl.extract_info(url, download=True)
                video_file = ydl.prepare_filename(result_v)

            with create_youtube_dl(ydl_opts_a) as ydl:
                result_a = ydl.extract_info(url, download=True)
                audio_file = ydl.prepare_filename(result_a)

            base = result_v.get('title') or result_v.get('id') or "video"
            xname = sanitize_filename(base)
            output_file = os.path.join(target_dir, f"{xname}.mp4")

            if os.path.exists(video_file) and os.path.exists(audio_file):
                log("🔄 Mulai proses encode (Video + Audio)...")
                cmd = double_cmd(video_file, audio_file, output_file)
                
                with create_youtube_dl({'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    duration = info.get('duration', 0)

                log(f"FFmpeg command: {subprocess.list2cmdline(cmd)}")
                if is_windows() == True:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                else:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                
                for line in process.stdout:
                    if "time=" in line and duration > 0:
                        try:
                            time_str = line.split("time=")[1].split(" ")[0]
                            parts = time_str.split(":")
                            h = float(parts[0])
                            m = float(parts[1])
                            s = float(parts[2])
                            current_secs = h * 3600 + m * 60 + s
                            pct = int((current_secs / duration) * 100)
                            if pct > 100: pct = 100
                            print(f"\rEncoding Progres: {pct}%", end="", flush=True)
                        except:
                            pass
                    else:
                        is_detailed = False
                        for x in ["frame=", "fps=", "size="]:
                            if x in line:
                                is_detailed = True
                                break
                        if not is_detailed:
                            log(line.strip())
                
                process.wait()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, cmd)
                print("\n", flush=True)

                log(f"✅ Encode selesai: {output_file}")
                os.remove(video_file)
                os.remove(audio_file)
            else:
                log("❌ Error: file hasil download tidak ditemukan!")
        elif platform in ["xhamster", "xvideos", "xnxx"]:
            fmt = get_quality(args)
            log(f"Mulai mengunduh dari {platform}: {url}")
            ydl_opts = {
                'outtmpl': f'{target_dir}/%(title)s.%(ext)s',
                'format': fmt + "+bestaudio/best[vcodec!*=av01]",
                'noprogress': False,
                'quiet': False,
                'force-overwrites': True,
                'merge_output_format': 'mp4'
            }
            with create_youtube_dl(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
                video_file = ydl.prepare_filename(result)

            if video_file:
                log("Download Selesai di: " + video_file)
        else:
            fmt = get_quality(args)
            log(f"Mulai mengunduh dari {platform}: {url}")
            ydl_opts = {
                'outtmpl': f'{target_dir}/sv_temp.%(ext)s',
                'format': fmt + "+bestaudio/best[vcodec!*=av01]",
                'noprogress': False,
                'quiet': False,
                'force-overwrites': True,
            }
            with create_youtube_dl(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
                video_file = ydl.prepare_filename(result)

            base = result.get('title') or result.get('id') or "video"
            xname = sanitize_filename(base)
            output_file = os.path.join(target_dir, f"{xname}.mp4")

            if os.path.exists(video_file):
                log("🔄 Mulai proses encode (Video)...")
                cmd = single_cmd(video_file, output_file)

                with create_youtube_dl({'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    duration = info.get('duration', 0)

                log(f"FFmpeg command: {subprocess.list2cmdline(cmd)}")
                if is_windows() == True:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                else:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )

                for line in process.stdout:
                    if "time=" in line and duration > 0:
                        try:
                            time_str = line.split("time=")[1].split(" ")[0]
                            parts = time_str.split(":")
                            h = float(parts[0])
                            m = float(parts[1])
                            s = float(parts[2])
                            current_secs = h * 3600 + m * 60 + s
                            pct = int((current_secs / duration) * 100)
                            if pct > 100: pct = 100
                            print(f"\rEncoding Progres: {pct}%", end="", flush=True)
                        except:
                            pass
                    else:
                        is_detailed = False
                        for x in ["frame=", "fps=", "size="]:
                            if x in line:
                                is_detailed = True
                                break
                        if not is_detailed:
                            log(line.strip())
                
                process.wait()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, cmd)
                print("\n", flush=True)

                log(f"✅ Encode selesai: {output_file}")
                os.remove(video_file)
            
    except Exception as e:
        log(f"❌ Error: {e}")
        return False

    return True


def run_download(url, mode, quality):
    args = SimpleNamespace(url=url, type=mode, quality=quality)
    return do_work(args)

if __name__ == "__main__":
    do_work()