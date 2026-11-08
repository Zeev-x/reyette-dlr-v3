import re
import sys
import os
import shutil
import platform

env_path = "Reyette_Roxylious_Atelier"
url_icon = "https://raw.githubusercontent.com/Zeev-x/py-to-executor/refs/heads/main/icon/icon.ico"
os_system = platform.system().lower()
script_name = os.path.basename(sys.argv[0])
script_location = os.getcwd()

def get_main_file():
    while True:
        main_file = input("Masukkan nama file utama (main.py): ").strip()
        if not main_file:
            print("Nama file utama tidak boleh kosong.")
        elif not main_file.endswith(".py"):
            print("Nama file utama harus berakhiran .py.")
        else:
            return main_file

def portable_py():
    path_py_port = os.path.join(script_location, "reyette_py")
    if not os.path.exists(path_py_port):
        setup_location = os.path.join(script_location, "py_setup.exe")
        ppy_cmd = [
            f"curl -L -o {setup_location} https://github.com/Zeev-x/portable-python-windows/raw/refs/heads/main/py-setup.exe",
            f"{setup_location} 12 64",
            f"del {setup_location}"
        ]
        for cmd in ppy_cmd:
            print(f"Runing >> {cmd}")
            os.system(cmd)
    else:
        print("Portable python sudah ada.")

def create_version_file(app_name="reyette-builder", company="Reyette"):
    content = f"""# UTF-8
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
        [StringStruct(u'CompanyName', u'{company}'),
         StringStruct(u'FileDescription', u'{app_name} Application'),
         StringStruct(u'ProductName', u'{app_name}'),
         StringStruct(u'InternalName', u'{app_name}'),
         StringStruct(u'OriginalFilename', u'{app_name}.exe'),
         StringStruct(u'LegalCopyright', u'(c) 2026 {company}')]
        )
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
  ]
)
"""
    with open("versionfile.txt", "w", encoding="utf-8") as vf:
        vf.write(content)

def get_requirements_or_detect(root_dir="."):
    req_file = os.path.join(root_dir, "requirements.txt")
    if os.path.exists(req_file):
        print("requirements.txt ditemukan, menggunakan daftar paket dari file...")
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                packages = []
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pkg = line.split("==")[0].split(">=")[0].split("<=")[0]
                        packages.append(pkg)
                return " ".join(sorted(set(packages)))
        except Exception as e:
            print(f"Gagal membaca requirements.txt: {e}")
            return None
    else:
        print("requirements.txt tidak ada, build akan dilakukan tanpa paket pip tambahan.")
        return None

def get_all_data(xfile, xdirs, root_dir="."):
    EXCLUDE_DIRS = {env_path, *xdirs}
    EXCLUDE_FILES = {script_name, *xfile}
    additional_data = []
    for dirpath, _, filenames in os.walk(root_dir):
        if any(ex in dirpath.split(os.sep) for ex in EXCLUDE_DIRS):
            continue
        for fname in filenames:
            if fname in EXCLUDE_FILES:
                continue
            file_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(file_path, root_dir)
            dest_folder = os.path.dirname(rel_path)
            # kalau file ada di root, gunakan "." sebagai dest
            if not dest_folder:
                dest_folder = "."
            if os_system == "windows":
                additional_data.append(f"{file_path};{dest_folder}")
            else:
                additional_data.append(f"{file_path}:{dest_folder}")
    return additional_data

def get_icon(url):
    icon_path = os.path.join("icon", "icon.ico")
    if os.path.exists(icon_path):
        print("Icon sudah ada.")
        return
    os.makedirs("icon", exist_ok=True)
    cmd = f"curl -o {icon_path} {url}"
    os.system(cmd)

def run_cmd(main_file, name_of_app, windowed_option, additional_data, package_pip=None):
    def get_pip_final(package_pip):
        return f"{package_pip} pyinstaller" if package_pip else "pyinstaller"

    if os_system == "windows":
        py_location = os.path.join(script_location, "pyr.exe")
        cmd = [
            f"{py_location} -m pip install --upgrade {get_pip_final(package_pip)}",
            f'{py_location} -m PyInstaller {main_file} --onefile --icon=icon/icon.ico --name="{name_of_app}" {windowed_option} --version-file=versionfile.txt {" ".join([f"--add-data \"{data}\"" for data in additional_data])}',
        ]
    else:
        cmd = [
            f"python -m venv {env_path}",
            f"{env_path}/bin/python -m pip install --upgrade {get_pip_final(package_pip)}",
            f'{env_path}/bin/pyinstaller {main_file} --onefile --icon=icon/icon.ico --name="{name_of_app}" {windowed_option} --version-file=versionfile.txt {" ".join([f"--add-data \"{data}\"" for data in additional_data])}',
        ]
    for x in cmd:
        print(f"Running: {x}")
        os.system(x)

def after_build_windows(app_name):
    src = os.path.join("dist", f"{app_name}.exe")
    dst = os.path.join(os.getcwd(), f"{app_name}.exe")
    if os.path.exists(src):
        shutil.move(src, dst)
        print(f"Moved {src} to {dst}")
    for x in [env_path, "build", "dist"]:
        if os.path.exists(x):
            shutil.rmtree(x)
    spec_file = f"{app_name}.spec"
    for y in [spec_file, "versionfile.txt"]:
        if os.path.exists(y):
            os.remove(y)

def after_build_linux(app_name):
    src = os.path.join("dist", app_name)
    dst = os.path.join(os.getcwd(), app_name)
    if os.path.exists(src):
        shutil.move(src, dst)
        print(f"Moved {src} to {dst}")
    for x in [env_path, "build", "dist"]:
        if os.path.exists(x):
            shutil.rmtree(x)
    spec_file = f"{app_name}.spec"
    for y in [spec_file, "versionfile.txt"]:
        if os.path.exists(y):
            os.remove(y)

def worker():
    get_icon(url_icon)
    if os_system == "windows":
        portable_py()

    if len(sys.argv) >= 4:
        main_file = sys.argv[1]
        name_of_app = sys.argv[2]
        windowed_option = sys.argv[3].lower()
        windowed_option = "--windowed" if windowed_option in ("y", "yes", "window", "win", "windowed") else ""
    else:
        main_file = get_main_file()
        name_of_app = input("Nama aplikasi: ").strip()
        windowed_option = input("Apakah aplikasi ini windowed? (y/n): ").strip().lower()
        windowed_option = "--windowed" if windowed_option == "y" else ""

    package_pip_project = get_requirements_or_detect(".")

    if os_system == "windows":
        data_filesx = [main_file, "pyr.exe"]
        data_dirx = ["reyette_py"]
        additional_data = get_all_data(data_filesx, data_dirx, ".")
    else:
        additional_data = get_all_data([main_file], [], ".")

    create_version_file(app_name=name_of_app, company="Reyette")

    print("=== Konfigurasi Build ===")
    print(f"File utama: {main_file}")
    print(f"Package pip: {package_pip_project if package_pip_project else 'Tidak ada'}")
    print(f"Nama aplikasi: {name_of_app}")
    print(f"Mode windowed: {'Ya' if windowed_option else 'Tidak'}")
    if additional_data:
        print("Data tambahan:")
        for data in additional_data:
            print(f" - {data}")

    if len(sys.argv) >= 4:
        confirm = 'y'
    else:
        confirm = input("Lanjutkan build? (y/n): ").strip().lower()

    if confirm == 'y':
        run_cmd(main_file, name_of_app, windowed_option, additional_data, package_pip_project)
        if os_system == "windows":
            after_build_windows(name_of_app)
        else:
            after_build_linux(name_of_app)
    else:
        print("Build dibatalkan.")

if __name__ == "__main__":
    try:
        worker()
    except KeyboardInterrupt:
        print("Closing by user")
    finally:
        if os_system == "windows":
            os.system("pause")
