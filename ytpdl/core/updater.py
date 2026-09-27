"""Update check, download and install.

The latest GitHub release is compared against the running version. When it is
newer, the platform's release asset can be downloaded (sha256-verified against
the digest GitHub publishes) and applied:

* Windows, installed via the Inno Setup installer — the new Setup.exe runs
  silently once the app has exited, then relaunches it.
* Linux AppImage — the new AppImage replaces the running one in place.
* macOS — the .dmg is downloaded and opened; the user drags the app across
  (an unsigned bundle can't be swapped safely from inside itself).
* Anything else (source checkout, pip install, portable folder) — the release
  page is opened instead.

yt-dlp updates itself on its own cadence and is checked separately.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import requests

from .. import __version__, config

log = logging.getLogger(__name__)
_RELEASES_API = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest"
_TIMEOUT = 8
_CHUNK = 256 * 1024

# How the running copy was installed, which decides how it can be updated.
INSTALL_WINDOWS_SETUP = "windows-setup"
INSTALL_APPIMAGE = "appimage"
INSTALL_MACOS_DMG = "macos-dmg"
INSTALL_MANUAL = "manual"


class UpdateError(Exception):
    pass


class UpdateCancelled(UpdateError):
    pass


@dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int
    sha256: str = ""  # hex digest, empty when GitHub didn't publish one


@dataclass
class UpdateInfo:
    current: str
    latest: str
    url: str
    notes: str
    update_available: bool
    assets: list[ReleaseAsset] = field(default_factory=list)


def _parse_version(text: str) -> tuple[int, ...]:
    cleaned = text.lstrip("vV").split("-")[0]
    parts: list[int] = []
    for chunk in cleaned.split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            break
    return tuple(parts) or (0,)


def is_newer(candidate: str, than: str) -> bool:
    return _parse_version(candidate) > _parse_version(than)


def _parse_asset(raw: dict) -> ReleaseAsset | None:
    name = raw.get("name") or ""
    url = raw.get("browser_download_url") or ""
    if not name or not url:
        return None
    digest = str(raw.get("digest") or "")
    sha = digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else ""
    return ReleaseAsset(name=name, url=url, size=int(raw.get("size") or 0), sha256=sha)


def check_for_update() -> UpdateInfo | None:
    try:
        resp = requests.get(_RELEASES_API, timeout=_TIMEOUT,
                            headers={"Accept": "application/vnd.github+json"})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.info("update check failed: %s", exc)
        return None

    latest = str(data.get("tag_name") or data.get("name") or "").strip()
    if not latest:
        return None

    assets = [a for a in map(_parse_asset, data.get("assets") or []) if a]
    return UpdateInfo(
        current=__version__,
        latest=latest,
        url=data.get("html_url") or f"https://github.com/{config.GITHUB_REPO}/releases",
        notes=(data.get("body") or "").strip(),
        update_available=is_newer(latest, __version__),
        assets=assets,
    )


# -------------------------------------------------------------- install kind
def install_kind(platform: str | None = None, environ: dict | None = None,
                 executable: str | None = None, frozen: bool | None = None) -> str:
    """Work out how this copy was installed. Arguments exist for tests."""
    platform = platform or sys.platform
    environ = os.environ if environ is None else environ
    executable = executable or sys.executable
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen

    if platform == "linux" and environ.get("APPIMAGE"):
        return INSTALL_APPIMAGE
    if not frozen:
        return INSTALL_MANUAL
    if platform == "win32":
        # Inno Setup drops unins000.exe next to the app; a portable copy has none.
        if any(Path(executable).parent.glob("unins*.exe")):
            return INSTALL_WINDOWS_SETUP
        return INSTALL_MANUAL
    if platform == "darwin":
        return INSTALL_MACOS_DMG
    return INSTALL_MANUAL


def pick_asset(assets: list[ReleaseAsset], kind: str) -> ReleaseAsset | None:
    def first(pred: Callable[[str], bool]) -> ReleaseAsset | None:
        return next((a for a in assets if pred(a.name.lower())), None)

    if kind == INSTALL_WINDOWS_SETUP:
        return first(lambda n: n.endswith(".exe") and "setup" in n) or \
            first(lambda n: n.endswith(".exe"))
    if kind == INSTALL_APPIMAGE:
        return first(lambda n: n.endswith(".appimage"))
    if kind == INSTALL_MACOS_DMG:
        return first(lambda n: n.endswith(".dmg"))
    return None


def can_self_install(kind: str) -> bool:
    """True when the update can be applied without the user doing anything."""
    return kind in (INSTALL_WINDOWS_SETUP, INSTALL_APPIMAGE)


# ------------------------------------------------------------------ download
def updates_dir() -> Path:
    return config.APP_DATA_DIR / "updates"


def download_asset(
    asset: ReleaseAsset,
    dest_dir: Path | None = None,
    progress: Callable[[int, int], None] | None = None,
    cancel: threading.Event | None = None,
) -> Path:
    """Stream ``asset`` to disk, verify it, and return the final path.

    A file already on disk with a matching digest is reused, so an update
    downloaded in the background isn't fetched twice.
    """
    dest_dir = dest_dir or updates_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / asset.name
    if target.exists() and _matches(target, asset):
        return target

    part = target.with_name(target.name + ".part")
    hasher = hashlib.sha256()
    done = 0
    try:
        with requests.get(asset.url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length") or asset.size or 0)
            with part.open("wb") as fh:
                for chunk in resp.iter_content(_CHUNK):
                    if cancel is not None and cancel.is_set():
                        raise UpdateCancelled("cancelled")
                    fh.write(chunk)
                    hasher.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except UpdateCancelled:
        part.unlink(missing_ok=True)
        raise
    except (requests.RequestException, OSError) as exc:
        part.unlink(missing_ok=True)
        raise UpdateError(str(exc)) from exc

    if asset.size and done != asset.size:
        part.unlink(missing_ok=True)
        raise UpdateError(f"incomplete download ({done} of {asset.size} bytes)")
    if asset.sha256 and hasher.hexdigest() != asset.sha256:
        part.unlink(missing_ok=True)
        raise UpdateError("downloaded file failed its checksum")

    part.replace(target)
    return target


def _matches(path: Path, asset: ReleaseAsset) -> bool:
    try:
        if asset.size and path.stat().st_size != asset.size:
            return False
        if not asset.sha256:
            return bool(asset.size)
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(_CHUNK), b""):
                h.update(chunk)
        return h.hexdigest() == asset.sha256
    except OSError:
        return False


def clear_downloads(keep: Path | None = None) -> None:
    """Delete leftover installers from earlier updates."""
    folder = updates_dir()
    if not folder.exists():
        return
    for child in folder.iterdir():
        if keep is not None and child == keep:
            continue
        try:
            child.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------- apply
def apply_update(path: Path, kind: str, *, relaunch: bool) -> bool:
    """Start applying the downloaded update.

    Returns True when the app should now quit so the update can finish
    (Windows installer, AppImage restart); False when the user still has
    something to do (macOS .dmg opened) and the app can keep running.
    """
    if kind == INSTALL_WINDOWS_SETUP:
        args = [str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"]
        if relaunch:
            args.append("/RELAUNCH=1")
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(args, creationflags=flags, close_fds=True)
        return True

    if kind == INSTALL_APPIMAGE:
        current = Path(os.environ["APPIMAGE"])
        staged = current.with_name(current.name + ".new")
        try:
            import shutil

            shutil.copyfile(path, staged)
            staged.chmod(0o755)
            # Linux keeps the running image's inode alive, so replacing the
            # file under ourselves is safe.
            staged.replace(current)
        except OSError as exc:
            staged.unlink(missing_ok=True)
            raise UpdateError(f"could not replace {current}: {exc}") from exc
        if relaunch:
            subprocess.Popen([str(current)], start_new_session=True, close_fds=True)
        return True

    if kind == INSTALL_MACOS_DMG:
        subprocess.Popen(["open", str(path)])
        return False

    raise UpdateError(f"no automatic install for install kind {kind!r}")
