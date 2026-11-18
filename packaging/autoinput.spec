# PyInstaller spec — run via `python packaging/build.py` (renders icons first).
# One-folder build: faster start-up than one-file and friendlier to antivirus scanners.
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent
ICONS = ROOT / "packaging" / "build"
APP = "AutoInput"
VERSION = re.search(
    r'__version__ = "([^"]+)"', (ROOT / "src" / "autoinput" / "__init__.py").read_text()
).group(1)

datas = [(str(ROOT / name), name) for name in ("profiles", "mappings", "samples")]
binaries = []
hiddenimports = collect_submodules("autoinput")

# Optional drivers: bundle whichever extras are installed in the build environment.
for package in ("playwright", "pynput", "pywinauto", "comtypes"):
    try:
        d, b, h = collect_all(package)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "mypy", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP,
    console=False,
    icon=str(ICONS / ("icon.icns" if sys.platform == "darwin" else "icon.ico")),
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP}.app",
        icon=str(ICONS / "icon.icns"),
        bundle_identifier="vn.autoinput.desktop",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": APP,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.productivity",
            "NSAppleEventsUsageDescription": (
                "AutoInput điều khiển ứng dụng đích để nhập dữ liệu tự động."
            ),
        },
    )
