"""Experimental frontend map-tile patching for the Kakao Map integration.

Swaps the cartocdn raster-tile URL in HA's frontend bundle for Kakao's, keeping a
`.backup` of each original so the change is reversible. All logic is plain Python
run in an executor — no remote scripts (see SPEC Boundaries). Projection alignment
of the Kakao tiles is unresolved (Open Q1) and verified separately in T11.
"""

from __future__ import annotations

import gzip
import importlib.util
from pathlib import Path

from .const import (
    CARTOCDN_TILE_URL,
    FRONTEND_BACKUP_SUFFIX,
    FRONTEND_SUBDIRS,
    FRONTEND_TILE_MARKER,
    KAKAO_TILE_URL,
)


class MapPatchError(Exception):
    """Raised when a frontend patch or restore cannot complete."""


def find_frontend_dir() -> Path:
    """Return the installed ``hass_frontend`` package directory."""
    spec = importlib.util.find_spec("hass_frontend")
    if spec is None or not spec.submodule_search_locations:
        raise MapPatchError("hass_frontend package not found")
    return Path(next(iter(spec.submodule_search_locations)))


def _regen_gzip(path: Path) -> None:
    """Rewrite the sibling ``.gz`` asset if the frontend shipped one."""
    gz = path.with_name(path.name + ".gz")
    if gz.exists():
        gz.write_bytes(gzip.compress(path.read_bytes()))


def patch_frontend(base: Path) -> list[str]:
    """Swap cartocdn tile URLs for Kakao tiles under ``base``.

    Returns the names of the files that were changed (empty if none match, which is
    an informational no-op rather than an error — see Open Q3).
    """
    patched: list[str] = []
    for subdir in FRONTEND_SUBDIRS:
        directory = base / subdir
        if not directory.is_dir():
            continue
        for path in directory.glob("*.js"):
            original = path.read_text(encoding="utf-8")
            if FRONTEND_TILE_MARKER not in original:
                continue
            replaced = original.replace(CARTOCDN_TILE_URL, KAKAO_TILE_URL)
            if replaced == original:
                continue
            backup = path.with_name(path.name + FRONTEND_BACKUP_SUFFIX)
            if not backup.exists():
                backup.write_text(original, encoding="utf-8")
            path.write_text(replaced, encoding="utf-8")
            _regen_gzip(path)
            patched.append(path.name)
    return patched


def restore_frontend(base: Path) -> list[str]:
    """Restore every patched file from its ``.backup`` under ``base``.

    Returns the names of the restored files. Raises ``MapPatchError`` if no backup
    exists, so a restore with nothing to revert is a clear error.
    """
    restored: list[str] = []
    for subdir in FRONTEND_SUBDIRS:
        directory = base / subdir
        if not directory.is_dir():
            continue
        for backup in directory.glob("*" + FRONTEND_BACKUP_SUFFIX):
            target = backup.with_name(backup.name[: -len(FRONTEND_BACKUP_SUFFIX)])
            target.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
            _regen_gzip(target)
            backup.unlink()
            restored.append(target.name)
    if not restored:
        raise MapPatchError("no backups found to restore")
    return restored
