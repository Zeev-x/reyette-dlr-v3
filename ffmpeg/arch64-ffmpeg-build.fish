#!/usr/bin/env fish

# ============================================================
# FFmpeg 8.0 Native Linux Build
# Arch Linux + NVIDIA NVENC
# NVENC Headers: 13.0.19.1
# Shell: Fish
# ============================================================

# ============================================================
# CONFIGURATION
# ============================================================

set -g ROOT (dirname (realpath (status filename)))
set -g DEPS_DIR "$ROOT/dependencies"
set -g SRC_DIR "$ROOT/source"
set -g OUT_DIR "$ROOT/output"

set -g NVENC_DIR "$DEPS_DIR/nv-codec-headers"
set -g FFMPEG_DIR "$SRC_DIR/FFmpeg"

set -g NVENC_TAG "n13.0.19.1"
set -g FFMPEG_TAG "n8.0"

set -g JOBS 4

# ============================================================
# LOGGING
# ============================================================

function log
    set_color cyan
    echo
    echo "==> $argv"
    set_color normal
end

function success
    set_color green
    echo
    echo "[OK] $argv"
    set_color normal
end

function die
    set_color red
    echo
    echo "ERROR: $argv" >&2
    set_color normal
    exit 1
end

# ============================================================
# CHECK ENVIRONMENT
# ============================================================

if test (uname -s) != Linux
    die "Script ini hanya untuk Linux."
end

if not type -q pacman
    die "pacman tidak ditemukan. Script ini dibuat untuk Arch Linux."
end

# ============================================================
# INSTALL DEPENDENCIES
# ============================================================

log "Memasang build tools dan dependensi"

sudo pacman -S --needed --noconfirm \
    base-devel \
    git \
    nasm \
    yasm \
    pkgconf \
    gcc \
    make \
    binutils

or die "Gagal memasang dependensi."

# ============================================================
# CHECK TOOLS
# ============================================================

log "Memeriksa build tools"

for tool in gcc g++ make git nasm yasm pkg-config ar ranlib strip
    if not type -q $tool
        die "Tool '$tool' tidak ditemukan."
    end
end

# ============================================================
# CREATE DIRECTORIES
# ============================================================

mkdir -p "$DEPS_DIR" "$SRC_DIR" "$OUT_DIR"

or die "Gagal membuat direktori."

# ============================================================
# DOWNLOAD NVENC HEADERS
# ============================================================

log "Mengambil NVIDIA NVENC headers $NVENC_TAG"

if not test -d "$NVENC_DIR/.git"

    git clone \
        --branch "$NVENC_TAG" \
        --depth 1 \
        https://github.com/FFmpeg/nv-codec-headers.git \
        "$NVENC_DIR"

    or die "Gagal mengunduh NVENC headers."

else

    git -C "$NVENC_DIR" fetch \
        --depth 1 \
        origin \
        "refs/tags/$NVENC_TAG:refs/tags/$NVENC_TAG"

    or die "Gagal memperbarui NVENC headers."

    git -C "$NVENC_DIR" checkout --detach "$NVENC_TAG"

    or die "Gagal checkout NVENC headers."

end

set NVENC_CHECK (git -C "$NVENC_DIR" describe --tags)

if test "$NVENC_CHECK" != "$NVENC_TAG"
    die "Versi NVENC headers tidak sesuai: $NVENC_CHECK"
end

# ============================================================
# INSTALL NVENC HEADERS
# ============================================================

log "Memasang NVENC headers ke /usr/local"

sudo make -C "$NVENC_DIR" install PREFIX=/usr/local

or die "Gagal memasang NVENC headers."

# ============================================================
# CONFIGURE PKG-CONFIG
# ============================================================

log "Mengatur PKG_CONFIG_PATH"

set -gx PKG_CONFIG_PATH \
    /usr/local/lib/pkgconfig \
    /usr/local/share/pkgconfig

if set -q PKG_CONFIG_LIBDIR
    set -e PKG_CONFIG_LIBDIR
end

# ============================================================
# CHECK NVENC VERSION
# ============================================================

set NVENC_VERSION (pkg-config --modversion ffnvcodec)

if test $status -ne 0
    die "ffnvcodec tidak ditemukan oleh pkg-config."
end

echo "NVENC headers detected: $NVENC_VERSION"

if not string match -rq '^13\.0\.19\.1(\.|$)' -- "$NVENC_VERSION"
    die "Versi NVENC tidak sesuai: $NVENC_VERSION"
end

success "NVENC headers berhasil dipasang."

# ============================================================
# DOWNLOAD FFMPEG
# ============================================================

log "Mengambil FFmpeg $FFMPEG_TAG"

if not test -d "$FFMPEG_DIR/.git"

    git clone \
        --branch "$FFMPEG_TAG" \
        --depth 1 \
        https://github.com/FFmpeg/FFmpeg.git \
        "$FFMPEG_DIR"

    or die "Gagal mengunduh FFmpeg."

else

    git -C "$FFMPEG_DIR" fetch \
        --depth 1 \
        origin \
        "refs/tags/$FFMPEG_TAG:refs/tags/$FFMPEG_TAG"

    or die "Gagal memperbarui FFmpeg."

    git -C "$FFMPEG_DIR" checkout --detach "$FFMPEG_TAG"

    or die "Gagal checkout FFmpeg."

end

set FFMPEG_CHECK (git -C "$FFMPEG_DIR" describe --tags)

if test "$FFMPEG_CHECK" != "$FFMPEG_TAG"
    die "Versi FFmpeg tidak sesuai: $FFMPEG_CHECK"
end

# ============================================================
# ENTER FFMPEG DIRECTORY
# ============================================================

cd "$FFMPEG_DIR"

or die "Gagal masuk direktori FFmpeg."

# ============================================================
# CONFIGURE FFMPEG
# ============================================================

log "Mengonfigurasi FFmpeg untuk Linux x86_64"

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
    2>&1 | tee "$ROOT/configure.log"

or die "Konfigurasi FFmpeg gagal."

# ============================================================
# VERIFY CONFIGURATION
# ============================================================

log "Memeriksa konfigurasi NVENC"

if not grep -q '^#define CONFIG_FFNVCODEC 1' config.h
    die "FFNVCodec tidak aktif."
end

if not grep -q '^#define CONFIG_H264_NVENC_ENCODER 1' config_components.h
    die "H264 NVENC encoder tidak aktif."
end

if not grep -q '^#define CONFIG_HEVC_NVENC_ENCODER 1' config_components.h
    die "HEVC NVENC encoder tidak aktif."
end

if not grep -q '^#define CONFIG_AV1_NVENC_ENCODER 1' config_components.h
    die "AV1 NVENC encoder tidak aktif."
end

success "Konfigurasi NVENC berhasil."

# ============================================================
# COMPILE FFMPEG
# ============================================================

log "Mengompilasi FFmpeg menggunakan $JOBS jobs"

make -j$JOBS 2>&1 | tee "$ROOT/build.log"

or die "Kompilasi FFmpeg gagal."

success "Kompilasi selesai."

# ============================================================
# INSTALL FFMPEG
# ============================================================

log "Memasang hasil build"

make install 2>&1 | tee "$ROOT/install.log"

or die "Instalasi FFmpeg gagal."

# ============================================================
# VERIFY OUTPUT
# ============================================================

set FFMPEG_BIN "$OUT_DIR/bin/ffmpeg"
set FFPROBE_BIN "$OUT_DIR/bin/ffprobe"

if not test -f "$FFMPEG_BIN"
    die "Binary ffmpeg tidak ditemukan."
end

if not test -f "$FFPROBE_BIN"
    die "Binary ffprobe tidak ditemukan."
end

success "FFmpeg dan FFprobe berhasil dibuat."

# ============================================================
# VERIFY BINARY
# ============================================================

log "Memeriksa format binary"

file "$FFMPEG_BIN"
file "$FFPROBE_BIN"

# ============================================================
# DISPLAY VERSION
# ============================================================

log "Versi FFmpeg"

"$FFMPEG_BIN" -version | head -n 3

# ============================================================
# CHECK NVENC ENCODERS
# ============================================================

log "Memeriksa encoder NVENC"

"$FFMPEG_BIN" -encoders | grep -E 'h264_nvenc|hevc_nvenc|av1_nvenc'

# ============================================================
# CHECK HWACCEL
# ============================================================

log "Memeriksa hardware acceleration"

"$FFMPEG_BIN" -hwaccels

# ============================================================
# FINAL OUTPUT
# ============================================================

echo
set_color green
echo "============================================"
echo "       BUILD FFMPEG LINUX SELESAI"
echo "============================================"
set_color normal

echo
echo "FFmpeg : $FFMPEG_BIN"
echo "FFprobe: $FFPROBE_BIN"

echo
echo "Catatan:"
echo "- Binary ditujukan untuk Linux x86_64."
echo "- Driver NVIDIA Linux diperlukan untuk NVENC."
echo "- NVENC headers bukan pengganti NVIDIA driver."
echo "- Encoder terdaftar belum menjamin dukungan GPU."

success "Semua proses build selesai."
