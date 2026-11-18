"""Render the app icon to packaging/build/ as .png, .ico (Windows) and .icns (macOS)."""

from pathlib import Path

from PIL import Image

from autoinput.ui.icons import app_icon_image

OUT = Path(__file__).resolve().parent / "build"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "icon.png"
    app_icon_image(1024).save(str(png))
    image = Image.open(png)
    image.save(OUT / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    image.save(OUT / "icon.icns")
    print(f"Icons written to {OUT}")


if __name__ == "__main__":
    main()
