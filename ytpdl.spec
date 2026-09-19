# PyInstaller spec — build a one-folder distribution.
#
#   pip install -e ".[dev]"
#   pyinstaller ytpdl.spec
#
# The result lands in dist/YouTube Playlist Downloader/. FFmpeg is located at
# runtime by ytpdl.core.ffmpeg: a copy next to the exe / in bin/ wins, then
# PATH, then the imageio-ffmpeg binary bundled here when it is installed
# (`pip install -e ".[ffmpeg]"` before building) — note it has no ffprobe.

import importlib.util
import os

from PyInstaller.utils.hooks import collect_all

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
    icon="ytpdl/resources/app.ico",
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
