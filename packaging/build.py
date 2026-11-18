"""Build installers for the current OS.

macOS   → dist/AutoInput.app + dist/AutoInput-<ver>-macos-<arch>.dmg
Windows → dist/AutoInput/ + dist/AutoInput-<ver>-windows-x64.zip
          (+ dist/AutoInput-<ver>-windows-setup.exe when Inno Setup's ISCC is available)

Usage: uv sync --extra gui --extra web --extra <mac|windows> --group build
       uv run python packaging/build.py
Env:   CODESIGN_IDENTITY="Developer ID Application: …" signs the macOS app (default: ad-hoc).
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
_match = re.search(
    r'__version__ = "([^"]+)"', (ROOT / "src" / "autoinput" / "__init__.py").read_text()
)
assert _match
VERSION = _match.group(1)


def run(*cmd: str | Path) -> None:
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT)


def build_macos() -> None:
    app = DIST / "AutoInput.app"
    identity = os.environ.get("CODESIGN_IDENTITY") or "-"
    run("codesign", "--force", "--deep", "--sign", identity, app)
    dmg = DIST / f"AutoInput-{VERSION}-macos-{platform.machine()}.dmg"
    dmg.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as staging:
        shutil.copytree(app, Path(staging) / app.name, symlinks=True)
        (Path(staging) / "Applications").symlink_to("/Applications")
        run("hdiutil", "create", "-volname", "AutoInput", "-srcfolder", staging,
            "-ov", "-format", "UDZO", dmg)  # fmt: skip
    print(f"✔ {dmg}")


def build_windows() -> None:
    archive = shutil.make_archive(
        str(DIST / f"AutoInput-{VERSION}-windows-x64"), "zip", DIST / "AutoInput"
    )
    print(f"✔ {archive}")
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if Path(iscc).exists():
        run(iscc, f"/DAppVersion={VERSION}", ROOT / "packaging" / "windows" / "AutoInput.iss")
        print(f"✔ {DIST / f'AutoInput-{VERSION}-windows-setup.exe'}")
    else:
        print("Inno Setup not found: skipped Setup.exe (the .zip is still usable).")


def main() -> None:
    run(sys.executable, ROOT / "packaging" / "make_icon.py")
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", DIST, "--workpath", ROOT / "build", ROOT / "packaging" / "autoinput.spec")  # fmt: skip
    # Never ship a bundle that has not been started once under the contained smoke test.
    run(sys.executable, ROOT / "packaging" / "smoke_test.py")
    if sys.platform == "darwin":
        build_macos()
    elif sys.platform == "win32":
        build_windows()


if __name__ == "__main__":
    main()
