#!/usr/bin/env python3
"""Select and run the FFmpeg builder for the current OS and NVENC API."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILDER_DIR = ROOT / "ffmpeg"
SUPPORTED_NVENC_API = "13.0"
BUILD_TARGET_MARKER = BUILDER_DIR / ".ffmpeg-build-target"
NVENC_TAG_PATTERN = re.compile(
    r'NVENC_TAG(?:\s*=\s*|\s+)["\']n?(\d+\.\d+\.\d+\.\d+)["\']'
)
PORTABLE_PYTHON_DIR = "reyette_py"
PORTABLE_PYTHON_DIR_LINUX = "Reyette_Roxylious_Atelier"
ICON_URL = (
    "https://raw.githubusercontent.com/Zeev-x/py-to-executor/"
    "refs/heads/main/icon/icon.ico"
)
APP_NAME = "Premium Downloader"
MAIN_FILE = "main.py"

MODE_OPTION = "--windowed" #Switch to "--windowed" or "--console" depending on your preference for the application window mode.

def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def read_os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = (Path("/etc/os-release")).read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RuntimeError(f"Tidak dapat membaca /etc/os-release: {error}") from error

    for line in lines:
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value.strip().strip('"').strip("'")
    return values


def select_builder() -> tuple[Path, str]:
    system = platform.system()
    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        raise RuntimeError(f"Arsitektur {machine} tidak didukung; builder ini untuk x86_64.")

    if system == "Windows":
        return BUILDER_DIR / "win64-ffmpeg-build.sh", "Windows (MSYS2 UCRT64)"
    if system != "Linux":
        raise RuntimeError(f"OS {system} belum didukung.")

    os_release = read_os_release()
    distribution = os_release.get("ID", "").lower()
    id_like = os_release.get("ID_LIKE", "").lower().split()
    if distribution == "arch":
        return BUILDER_DIR / "arch64-ffmpeg-build.fish", "Arch-based Linux"
    if distribution == "debian":
        return BUILDER_DIR / "deb64-ffmpeg-build.sh", "Debian-based Linux"
    if "arch" in id_like:
        return BUILDER_DIR / "arch64-ffmpeg-build.fish", "Arch-based Linux"
    if "debian" in id_like:
        return BUILDER_DIR / "deb64-ffmpeg-build.sh", "Debian-based Linux"
    raise RuntimeError(
        f"Distribusi Linux '{distribution or 'unknown'}' belum didukung "
        "(builder tersedia untuk distro basis Debian dan Arch)."
    )


def get_configured_nvenc_version(builder: Path) -> tuple[str, str]:
    try:
        content = builder.read_text(encoding="utf-8")
    except OSError as error:
        raise RuntimeError(f"Tidak dapat membaca builder {builder.name}: {error}") from error

    match = NVENC_TAG_PATTERN.search(content)
    if match is None:
        raise RuntimeError(f"Tag NVENC tidak ditemukan di {builder.name}.")

    version = match.group(1)
    api_version = ".".join(version.split(".")[:2])
    return version, api_version


def find_existing_ffmpeg(system: str) -> Path:
    if system == "Windows":
        return BUILDER_DIR / "ffmpeg-win64" / "ffmpeg.exe"
    return BUILDER_DIR / "ffmpeg-linux64" / "ffmpeg"


def is_build_complete(builder: Path, system: str) -> bool:
    executable = find_existing_ffmpeg(system)
    if not executable.is_file() or not BUILD_TARGET_MARKER.is_file():
        return False
    try:
        return BUILD_TARGET_MARKER.read_text(encoding="utf-8").strip() == builder.name
    except OSError as error:
        raise RuntimeError(f"Tidak dapat membaca penanda build: {error}") from error


def find_msys2_root() -> Path:
    candidates: list[Path] = []
    configured_root = os.environ.get("MSYS2_ROOT")
    if configured_root:
        candidates.append(Path(configured_root).expanduser())

    candidates.extend(
        [
            Path(r"C:\msys64"),
            Path(r"C:\tools\msys64"),
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "MSYS2",
        ]
    )

    for candidate in candidates:
        if (candidate / "usr" / "bin" / "bash.exe").is_file() and (
            candidate / "usr" / "bin" / "cygpath.exe"
        ).is_file():
            return candidate

    raise RuntimeError(
        "MSYS2 tidak ditemukan. Pasang MSYS2 UCRT64 atau set environment variable MSYS2_ROOT."
    )


def run_windows_builder(builder: Path) -> int:
    msys2_root = find_msys2_root()
    bash = msys2_root / "usr" / "bin" / "bash.exe"
    cygpath = msys2_root / "usr" / "bin" / "cygpath.exe"

    path_result = subprocess.run(
        [str(cygpath), "-u", str(builder)],
        check=True,
        capture_output=True,
        text=True,
    )
    builder_posix_path = path_result.stdout.strip()

    environment = os.environ.copy()
    environment["MSYSTEM"] = "UCRT64"
    environment["CHERE_INVOKING"] = "1"
    environment["PATH"] = os.pathsep.join(
        [
            str(msys2_root / "ucrt64" / "bin"),
            str(msys2_root / "usr" / "bin"),
            environment.get("PATH", ""),
        ]
    )
    command = (
        '[[ "${MSYSTEM:-}" == "UCRT64" ]] || '
        '{ echo "MSYS2 UCRT64 environment was not initialized." >&2; exit 1; }; '
        'exec bash "$1"'
    )
    result = subprocess.run(
        [str(bash), "--login", "-c", command, "build.py", builder_posix_path],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    return result.returncode


def run_builder(builder: Path) -> int:
    if not builder.is_file():
        return fail(f"Builder tidak ditemukan: {builder}")

    system = platform.system()
    if system == "Windows":
        try:
            return run_windows_builder(builder)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            return fail(f"Gagal menjalankan builder melalui MSYS2 UCRT64: {error}")

    if system == "Linux" and builder.suffix == ".fish":
        fish = shutil.which("fish")
        if fish is None:
            return fail("Fish tidak ditemukan. Pasang Fish untuk menjalankan builder Arch Linux.")
        command = [fish, str(builder)]
    else:
        bash = shutil.which("bash")
        if bash is None:
            return fail("Bash tidak ditemukan.")
        command = [bash, str(builder)]

    try:
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    except OSError as error:
        return fail(f"Gagal menjalankan builder {builder.name}: {error}")


def run_application_build() -> int:
    try:
        return build_application()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        return fail(f"Gagal membuat executable: {error}")


def ensure_icon() -> None:
    icon_path = ROOT / "icon" / "icon.ico"
    if icon_path.is_file():
        return
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl diperlukan untuk mengunduh icon aplikasi.")
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [curl, "-fL", "-o", str(icon_path), ICON_URL],
        cwd=ROOT,
        check=True,
    )


def ensure_portable_python() -> Path:
    portable_python = ROOT / "reyette_py"
    if portable_python.is_dir():
        print("Portable Python sudah tersedia.")
        return ROOT / "pyr.exe"

    setup_path = ROOT / "py_setup.exe"
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl diperlukan untuk mengunduh portable Python.")
    print("Mengunduh installer portable Python...")
    subprocess.run(
        [
            curl,
            "-fL",
            "-o",
            str(setup_path),
            "https://github.com/Zeev-x/portable-python-windows/raw/refs/heads/main/py-setup.exe",
        ],
        cwd=ROOT,
        check=True,
    )
    try:
        subprocess.run([str(setup_path), "12", "64"], cwd=ROOT, check=True)
    finally:
        setup_path.unlink(missing_ok=True)

    python_executable = ROOT / "pyr.exe"
    if not python_executable.is_file():
        raise RuntimeError(f"Portable Python tidak menghasilkan {python_executable.name}.")
    return python_executable


def get_project_packages() -> list[str]:
    requirements = ROOT / "requirements.txt"
    if not requirements.is_file():
        print("requirements.txt tidak ditemukan; tidak ada dependensi proyek tambahan.")
        return []

    packages = [
        line.strip()
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return packages


def collect_additional_data(system: str) -> list[str]:
    excluded_files = {"main.py", "build.py", "pyr.exe"}
    excluded_directories = {PORTABLE_PYTHON_DIR, PORTABLE_PYTHON_DIR_LINUX, "__pycache__", ".git"}
    additional_data: list[str] = []
    separator = ";" if system == "Windows" else ":"

    for current_dir, directories, filenames in os.walk(ROOT):
        directories[:] = [
            directory
            for directory in directories
            if directory not in excluded_directories
            and directory not in {"__pycache__", ".git"}
        ]
        for filename in filenames:
            if filename in excluded_files:
                continue
            source = Path(current_dir) / filename
            destination = source.parent.relative_to(ROOT)
            destination_name = str(destination) if destination.parts else "."
            additional_data.append(f"{source}{separator}{destination_name}")
    return additional_data


def create_version_file() -> Path:
    version_file = ROOT / "versionfile.txt"
    version_file.write_text(
        f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Reyette'),
         StringStruct(u'FileDescription', u'{APP_NAME} Application'),
         StringStruct(u'ProductName', u'{APP_NAME}'),
         StringStruct(u'InternalName', u'{APP_NAME}'),
         StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
         StringStruct(u'LegalCopyright', u'(c) 2026 Reyette')]
        )
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    return version_file


def run_pyinstaller(system: str, additional_data: list[str]) -> Path:
    if system == "Windows":
        python_executable = ensure_portable_python()
        pip_command = [str(python_executable), "-m", "pip", "install", "--upgrade"]
        pip_command.extend(get_project_packages())
        pip_command.append("pyinstaller")
        subprocess.run(pip_command, cwd=ROOT, check=True)
        pyinstaller = [str(python_executable), "-m", "PyInstaller"]
    else:
        environment = ROOT / PORTABLE_PYTHON_DIR
        subprocess.run(
            [sys.executable, "-m", "venv", str(environment)],
            cwd=ROOT,
            check=True,
        )
        python_executable = environment / "bin" / "python"
        subprocess.run(
            [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "--upgrade",
                *get_project_packages(),
                "pyinstaller",
            ],
            cwd=ROOT,
            check=True,
        )
        pyinstaller = [str(environment / "bin" / "pyinstaller")]

    command = [
        *pyinstaller,
        MAIN_FILE,
        "--onefile",
        f"--icon={ROOT / 'icon' / 'icon.ico'}",
        f"--name={APP_NAME}",
        MODE_OPTION,
    ]
    if system == "Windows":
        command.append(f"--version-file={ROOT / 'versionfile.txt'}")
    for data in additional_data:
        command.extend(["--add-data", data])
    subprocess.run(command, cwd=ROOT, check=True)

    suffix = ".exe" if system == "Windows" else ""
    output = ROOT / "dist" / f"{APP_NAME}{suffix}"
    if not output.is_file():
        raise RuntimeError(f"PyInstaller selesai tetapi output tidak ditemukan: {output}")
    return output


def build_application() -> int:
    system = platform.system()
    if system not in {"Windows", "Linux"}:
        raise RuntimeError(f"Build executable tidak didukung pada {system}.")

    ensure_icon()
    version_file = create_version_file()
    additional_data = collect_additional_data(system)
    print(f"\nMenyiapkan executable {APP_NAME}...")
    print(f"Dependensi: {', '.join(get_project_packages()) or 'tidak ada'}")

    try:
        output = run_pyinstaller(system, additional_data)
        destination = ROOT / output.name
        if destination.exists():
            destination.unlink()
        shutil.move(str(output), str(destination))
        print(f"Executable berhasil dibuat: {destination}")
        return 0
    finally:
        cleanup_paths = [ROOT / "build", ROOT / PORTABLE_PYTHON_DIR, ROOT / "dist", version_file]
        if system == "Linux":
            cleanup_paths.append(ROOT / PORTABLE_PYTHON_DIR_LINUX)
        for path in cleanup_paths:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        pyr_executable = ROOT / "pyr.exe"
        pyr_executable.unlink(missing_ok=True)
        spec_file = ROOT / f"{APP_NAME}.spec"
        spec_file.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deteksi OS dan jalankan builder FFmpeg untuk NVENC API 13.0."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tampilkan builder dan versi API yang dipilih tanpa menjalankan build.",
    )
    args = parser.parse_args()

    try:
        builder, os_name = select_builder()
        existing_ffmpeg = find_existing_ffmpeg(platform.system())
        if is_build_complete(builder, platform.system()):
            print(f"FFmpeg sudah tersedia: {existing_ffmpeg}")
            print(f"Builder cocok: {builder.name}")
            print("Build dilewati.")
            if args.dry_run:
                print("Dry run: build executable tidak dijalankan.")
                return 0
            return run_application_build()

        if existing_ffmpeg.is_file():
            print(
                f"FFmpeg tersedia, tetapi belum ditandai sebagai hasil "
                f"{builder.name}; build akan dijalankan ulang."
            )

        nvenc_version, api_version = get_configured_nvenc_version(builder)
    except RuntimeError as error:
        return fail(str(error))

    print(f"OS terdeteksi       : {os_name}")
    print(f"NVENC headers target: {nvenc_version}")
    print(f"NVENC API target    : {api_version}")

    if api_version != SUPPORTED_NVENC_API:
        return fail(
            f"API {api_version} tidak didukung; build hanya dijalankan untuk "
            f"NVENC API {SUPPORTED_NVENC_API}."
        )

    print(f"Builder             : {builder.name}")
    if args.dry_run:
        print("Dry run: builder tidak dijalankan.")
        return 0

    print(f"Menjalankan build FFmpeg untuk {os_name}...")
    result = run_builder(builder)
    if result != 0:
        return result
    try:
        BUILD_TARGET_MARKER.write_text(f"{builder.name}\n", encoding="utf-8")
    except OSError as error:
        return fail(f"Build berhasil, tetapi penanda target tidak dapat disimpan: {error}")
    return run_application_build()


if __name__ == "__main__":
    raise SystemExit(main())