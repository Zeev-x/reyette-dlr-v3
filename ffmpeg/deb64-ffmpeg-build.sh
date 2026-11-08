#!/usr/bin/env bash
# Build FFmpeg 8.0 for Debian x86_64 with NVIDIA NVENC headers 13.0.19.1.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

ROOT="$SCRIPT_DIR"
DEPS_DIR="$ROOT/dependencies"
SRC_DIR="$ROOT/source-debian"
OUT_DIR="$ROOT/build-output-debian-linux64"
FINAL_DIR="$ROOT/ffmpeg-linux64"
NVENC_DIR="$DEPS_DIR/nv-codec-headers"
FFMPEG_DIR="$SRC_DIR/FFmpeg"

NVENC_TAG="n13.0.19.1"
FFMPEG_TAG="n8.0"
JOBS="${JOBS:-$(nproc)}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ "$(uname -s)" == "Linux" ]] || die "Script ini hanya untuk Linux."
[[ "$(uname -m)" == "x86_64" ]] || die "Script ini hanya mendukung Linux x86_64."
[[ -r /etc/os-release ]] || die "Tidak dapat mendeteksi distribusi Linux."
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == "debian" ]] || die "Script ini hanya untuk Debian (ID=${ID:-unknown})."

command -v apt-get >/dev/null 2>&1 || die "apt-get tidak ditemukan."
APT=()
if [[ "$EUID" -ne 0 ]]; then
  command -v sudo >/dev/null 2>&1 || die "Jalankan sebagai root atau pasang sudo."
  APT=(sudo)
fi

log "Memasang toolchain dan dependensi Debian"
"${APT[@]}" apt-get update
"${APT[@]}" apt-get install -y --no-install-recommends \
  build-essential binutils ca-certificates file git nasm pkg-config yasm

for tool in gcc g++ make git nasm yasm pkg-config ar ranlib strip; do
  command -v "$tool" >/dev/null 2>&1 || die "Tool '$tool' belum tersedia."
done

mkdir -p "$DEPS_DIR" "$SRC_DIR" "$OUT_DIR"

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

log "Memasang NVENC headers ke /usr/local"
"${APT[@]}" make -C "$NVENC_DIR" install PREFIX=/usr/local

export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig:/usr/local/share/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
unset PKG_CONFIG_LIBDIR
NVENC_VERSION="$(pkg-config --modversion ffnvcodec)"
[[ "$NVENC_VERSION" == 13.0.19.1* ]] || die "Versi ffnvcodec tidak sesuai: $NVENC_VERSION"
printf 'NVENC headers terdeteksi: %s\n' "$NVENC_VERSION"

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

log "Mengonfigurasi FFmpeg untuk Debian x86_64"
./configure \
  --prefix="$OUT_DIR" \
  --arch=x86_64 \
  --target-os=linux \
  --enable-ffnvcodec \
  --enable-nvenc \
  --disable-debug \
  --disable-doc \
  --disable-shared \
  --enable-static \
  --pkg-config-flags="--static" \
  2>&1 | tee "$ROOT/configure-debian.log"

grep -q '^#define CONFIG_FFNVCODEC 1' config.h \
  || die "Konfigurasi tidak mengaktifkan FFNVCodec."
for encoder in H264 HEVC AV1; do
  grep -q "^#define CONFIG_${encoder}_NVENC_ENCODER 1" config_components.h \
    || die "Konfigurasi tidak mengaktifkan encoder ${encoder,,}_nvenc."
done

log "Mengompilasi FFmpeg menggunakan $JOBS jobs"
make -j"$JOBS" 2>&1 | tee "$ROOT/build-debian.log"

log "Memasang hasil build"
make install 2>&1 | tee "$ROOT/install-debian.log"

for binary in ffmpeg ffprobe; do
  [[ -f "$OUT_DIR/bin/$binary" ]] || die "$binary tidak ditemukan setelah instalasi."
done

log "Mengemas binary ke $FINAL_DIR"
PACKAGE_DIR="$(mktemp -d "$ROOT/.ffmpeg-linux64-package.XXXXXX")"
BACKUP_DIR="$(mktemp -d "$ROOT/.ffmpeg-linux64-backup.XXXXXX")"
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
file "$FINAL_DIR/ffmpeg" "$FINAL_DIR/ffprobe"
"$FINAL_DIR/ffmpeg" -version | head -n 3
"$FINAL_DIR/ffmpeg" -encoders | grep -E 'h264_nvenc|hevc_nvenc|av1_nvenc' || true
printf '\nFFmpeg : %s/ffmpeg\n' "$FINAL_DIR"
printf 'FFprobe: %s/ffprobe\n' "$FINAL_DIR"
printf '\nCatatan: driver NVIDIA diperlukan untuk menjalankan encoder NVENC.\n'

log "Membersihkan source, dependencies, dan log build"
rm -rf "$SRC_DIR" "$DEPS_DIR" \
  || die "Gagal menghapus source atau dependencies."
rm -f "$ROOT/configure-debian.log" "$ROOT/build-debian.log" "$ROOT/install-debian.log" \
  || die "Gagal menghapus log build."
printf 'Cleanup selesai; binary tersimpan di %s\n' "$FINAL_DIR"
