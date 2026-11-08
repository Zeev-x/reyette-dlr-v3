#!/usr/bin/env bash
# Build FFmpeg 8.0 for Windows x64 with NVIDIA NVENC headers 13.0.19.1.
# Run from an MSYS2 UCRT64 terminal, not PowerShell/CMD or MSYS/ MINGW64.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

ROOT="$SCRIPT_DIR"
DEPS_DIR="$ROOT/dependencies"
SRC_DIR="$ROOT/source"
OUT_DIR="$ROOT/build-output-win64"
FINAL_DIR="$ROOT/ffmpeg-win64"
NVENC_DIR="$DEPS_DIR/nv-codec-headers"
FFMPEG_DIR="$SRC_DIR/FFmpeg"

NVENC_TAG="n13.0.19.1"
FFMPEG_TAG="n8.0"
JOBS=4

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# Make sure this script is running in the intended MSYS2 environment.
[[ "${MSYSTEM:-}" == "UCRT64" ]] || die "Buka MSYS2 UCRT64 lalu jalankan script ini dari sana."
command -v pacman >/dev/null 2>&1 || die "pacman tidak ditemukan. Pastikan terminal MSYS2 UCRT64."
command -v git >/dev/null 2>&1 || die "git tidak ditemukan."

mkdir -p "$DEPS_DIR" "$SRC_DIR" "$OUT_DIR"

log "Memasang toolchain dan dependensi build"
pacman -S --needed --noconfirm \
  base-devel git make diffutils \
  mingw-w64-ucrt-x86_64-toolchain \
  mingw-w64-ucrt-x86_64-nasm \
  mingw-w64-ucrt-x86_64-yasm \
  mingw-w64-ucrt-x86_64-pkgconf

for tool in gcc make nasm yasm pkg-config; do
  command -v "$tool" >/dev/null 2>&1 || die "Tool '$tool' belum tersedia."
done

log "Mengambil NVENC headers $NVENC_TAG"
if [[ ! -d "$NVENC_DIR/.git" ]]; then
  git clone --branch "$NVENC_TAG" --depth 1 \
    https://github.com/FFmpeg/nv-codec-headers.git "$NVENC_DIR"
else
  git -C "$NVENC_DIR" fetch --depth 1 origin "refs/tags/$NVENC_TAG:refs/tags/$NVENC_TAG"
  git -C "$NVENC_DIR" checkout --detach "$NVENC_TAG"
fi

NVENC_CHECK="$(git -C "$NVENC_DIR" describe --tags)"
[[ "$NVENC_CHECK" == "$NVENC_TAG" ]] || die "Versi NVENC headers tidak sesuai: $NVENC_CHECK"

log "Memasang NVENC headers ke /ucrt64"
make -C "$NVENC_DIR" install PREFIX=/ucrt64

NVENC_VERSION="$(pkg-config --modversion ffnvcodec)"
printf 'NVENC headers terdeteksi: %s\n' "$NVENC_VERSION"
[[ "$NVENC_VERSION" == 13.0.19.1* ]] || die "Versi ffnvcodec tidak sesuai: $NVENC_VERSION"

log "Mengambil FFmpeg $FFMPEG_TAG"
if [[ ! -d "$FFMPEG_DIR/.git" ]]; then
  git clone --branch "$FFMPEG_TAG" --depth 1 \
    https://github.com/FFmpeg/FFmpeg.git "$FFMPEG_DIR"
else
  git -C "$FFMPEG_DIR" fetch --depth 1 origin "refs/tags/$FFMPEG_TAG:refs/tags/$FFMPEG_TAG"
  git -C "$FFMPEG_DIR" checkout --detach "$FFMPEG_TAG"
fi

FFMPEG_CHECK="$(git -C "$FFMPEG_DIR" describe --tags)"
[[ "$FFMPEG_CHECK" == "$FFMPEG_TAG" ]] || die "Versi FFmpeg tidak sesuai: $FFMPEG_CHECK"

cd "$FFMPEG_DIR"

log "Mengonfigurasi FFmpeg"
./configure \
  --prefix="$OUT_DIR" \
  --arch=x86_64 \
  --target-os=mingw32 \
  --enable-ffnvcodec \
  --enable-nvenc \
  --disable-debug \
  --disable-doc \
  --disable-shared \
  --enable-static \
  --pkg-config-flags="--static" \
  --extra-ldflags="-static -static-libgcc -static-libstdc++" \
  2>&1 | tee "$ROOT/configure.log"

grep -q '^#define CONFIG_FFNVCODEC 1' config.h \
  || die "Konfigurasi tidak mengaktifkan FFNVCodec."
grep -q '^#define CONFIG_H264_NVENC_ENCODER 1' config_components.h \
  || die "Konfigurasi tidak mengaktifkan encoder h264_nvenc."

log "Mengompilasi FFmpeg menggunakan $JOBS jobs"
make -j"$JOBS" 2>&1 | tee "$ROOT/build.log"

log "Memasang hasil build"
make install 2>&1 | tee "$ROOT/install.log"

[[ -f "$OUT_DIR/bin/ffmpeg.exe" ]] || die "ffmpeg.exe tidak ditemukan setelah instalasi."
[[ -f "$OUT_DIR/bin/ffprobe.exe" ]] || die "ffprobe.exe tidak ditemukan setelah instalasi."

log "Mengemas binary ke $FINAL_DIR"
PACKAGE_DIR="$(mktemp -d "$ROOT/.ffmpeg-win64-package.XXXXXX")"
BACKUP_DIR="$(mktemp -d "$ROOT/.ffmpeg-win64-backup.XXXXXX")"
rmdir "$BACKUP_DIR" || die "Gagal menyiapkan direktori backup."
cp -a "$OUT_DIR/bin/." "$PACKAGE_DIR/" || die "Gagal menyalin binary hasil build."

if [[ -e "$FINAL_DIR" ]]; then
  mv "$FINAL_DIR" "$BACKUP_DIR" || die "Gagal mencadangkan output sebelumnya."
fi

if ! mv "$PACKAGE_DIR" "$FINAL_DIR"; then
  [[ ! -e "$BACKUP_DIR" ]] || mv "$BACKUP_DIR" "$FINAL_DIR"
  die "Gagal memindahkan binary ke $FINAL_DIR."
fi

rm -rf "$OUT_DIR" || die "Gagal menghapus direktori staging build."
if [[ -e "$BACKUP_DIR" ]]; then
  rm -rf "$BACKUP_DIR" || die "Gagal menghapus backup output sebelumnya."
fi

log "Build selesai"
printf 'FFmpeg : %s/ffmpeg.exe\n' "$FINAL_DIR"
printf 'FFprobe: %s/ffprobe.exe\n' "$FINAL_DIR"
printf '\nVersi build:\n'
"$FINAL_DIR/ffmpeg.exe" -version | head -n 3
printf '\nEncoder NVENC yang terdaftar:\n'
"$FINAL_DIR/ffmpeg.exe" -encoders | grep -E 'h264_nvenc|hevc_nvenc|av1_nvenc' || true
printf '\nCatatan: encoder yang terdaftar belum tentu didukung oleh hardware GPU Anda.\n'
