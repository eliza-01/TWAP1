from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "client_desktop" / "assets"
SOURCE_PNG = ASSETS_DIR / "twaps_icon_256.png"
GENERATED_ICO = ASSETS_DIR / "twaps_icon.ico"
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def ensure_windows_icon() -> Path | None:
    """Generate a Windows .ico from the project PNG icon for PyInstaller."""
    if not SOURCE_PNG.exists():
        print(f"TWAPs icon PNG was not found: {SOURCE_PNG}")
        return None

    if GENERATED_ICO.exists() and GENERATED_ICO.stat().st_mtime >= SOURCE_PNG.stat().st_mtime:
        print(f"TWAPs icon is ready: {GENERATED_ICO}")
        return GENERATED_ICO

    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - build-time helper
        raise RuntimeError("Pillow is required to generate client_desktop/assets/twaps_icon.ico") from exc

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(SOURCE_PNG).convert("RGBA")
    image.save(GENERATED_ICO, format="ICO", sizes=ICON_SIZES)
    print(f"Generated TWAPs icon: {GENERATED_ICO}")
    return GENERATED_ICO


if __name__ == "__main__":
    ensure_windows_icon()
