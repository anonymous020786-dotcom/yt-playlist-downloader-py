# PyInstaller spec — build a one-folder distribution.
#
#   pip install -e ".[dev]"
#   pyinstaller ytpdl.spec
#
# PyInstaller does not cross-compile: run this on Windows for a Windows
# build, on macOS for a macOS .app, on Linux for a Linux binary (see
# .github/workflows/desktop-build.yml, which does exactly that on real
# runners for each OS).
#
# The result lands in dist/YouTube Playlist Downloader/ (dist/*.app on
# macOS). FFmpeg is located at runtime by ytpdl.core.ffmpeg: a copy next to
# the exe / in bin/ wins, then PATH, then the imageio-ffmpeg binary bundled
# here when it is installed (`pip install -e ".[ffmpeg]"` before building)
# — note it has no ffprobe.

import importlib.util
import os
import sys

from PyInstaller.utils.hooks import collect_all

sys.path.insert(0, SPECPATH)
from ytpdl import __version__ as APP_VERSION  # noqa: E402 — single source of truth for the version

datas = [
    ("ytpdl/i18n/locales", "ytpdl/i18n/locales"),
    ("ytpdl/resources", "ytpdl/resources"),
]
binaries = []
hiddenimports = ["mutagen.easymp4", "mutagen.mp3", "mutagen.easyid3", "ytpdl"]

_pkgs = ["yt_dlp", "ytpdl"]
if importlib.util.find_spec("imageio_ffmpeg"):
    _pkgs.append("imageio_ffmpeg")

for pkg in _pkgs:
    p_datas, p_binaries, p_hidden = collect_all(pkg)
    datas += p_datas
    binaries += p_binaries
    hiddenimports += p_hidden

block_cipher = None

if sys.platform == "darwin":
    icon_file = "ytpdl/resources/app.icns"
elif sys.platform == "win32":
    icon_file = "ytpdl/resources/app.ico"
else:
    # Linux: PyInstaller's EXE(icon=...) is a no-op there anyway — desktop
    # icons come from a .desktop file's Icon= entry, not the binary itself.
    icon_file = None

a = Analysis(
    ["ytpdl_launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore", "matplotlib", "PIL"],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YouTube Playlist Downloader",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon_file,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    [("READ ME FIRST.txt", os.path.join(SPECPATH, "installer", "READ ME FIRST.txt"), "DATA")],
    strip=False,
    upx=False,
    name="YouTube Playlist Downloader",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="YouTube Playlist Downloader.app",
        icon=icon_file,
        bundle_identifier="dev.ytpdl.downloader",
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.video",
        },
    )
