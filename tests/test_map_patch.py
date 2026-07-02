"""Tests for the experimental frontend map-tile patch logic (T10)."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from custom_components.kakao_map.const import (
    CARTOCDN_TILE_URL,
    FRONTEND_BACKUP_SUFFIX,
    KAKAO_TILE_URL,
)
from custom_components.kakao_map.map_patch import (
    MapPatchError,
    patch_frontend,
    restore_frontend,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_frontend(base: Path) -> Path:
    """Create a fake frontend_latest JS file with the cartocdn tile URL and its .gz."""
    js = base / "frontend_latest" / "map-card.js"
    content = f'const t="{CARTOCDN_TILE_URL}";'
    _write(js, content)
    js.with_name(js.name + ".gz").write_bytes(gzip.compress(content.encode()))
    return js


def test_patch_replaces_url_and_backs_up(tmp_path: Path) -> None:
    """patch swaps the tile URL, backs up the original, and rewrites the .gz."""
    js = _make_frontend(tmp_path)

    patched = patch_frontend(tmp_path)

    assert patched == [js.name]
    new = js.read_text(encoding="utf-8")
    assert KAKAO_TILE_URL in new
    assert CARTOCDN_TILE_URL not in new
    backup = js.with_name(js.name + FRONTEND_BACKUP_SUFFIX)
    assert CARTOCDN_TILE_URL in backup.read_text(encoding="utf-8")
    gz = js.with_name(js.name + ".gz")
    assert KAKAO_TILE_URL in gzip.decompress(gz.read_bytes()).decode()


def test_patch_ignores_unrelated_and_reports_empty(tmp_path: Path) -> None:
    """With no cartocdn files the patch is a no-op (0-target info case, Open Q3)."""
    _write(tmp_path / "frontend_latest" / "other.js", "no tiles here")

    assert patch_frontend(tmp_path) == []


def test_patch_is_idempotent_and_preserves_original_backup(tmp_path: Path) -> None:
    """Re-running patch changes nothing and keeps the first backup intact."""
    js = _make_frontend(tmp_path)
    patch_frontend(tmp_path)

    assert patch_frontend(tmp_path) == []
    backup = js.with_name(js.name + FRONTEND_BACKUP_SUFFIX)
    assert CARTOCDN_TILE_URL in backup.read_text(encoding="utf-8")


def test_restore_reverts_file_and_removes_backup(tmp_path: Path) -> None:
    """restore returns the file to its original bytes and drops the backup."""
    js = _make_frontend(tmp_path)
    original = js.read_text(encoding="utf-8")
    patch_frontend(tmp_path)

    restored = restore_frontend(tmp_path)

    assert restored == [js.name]
    assert js.read_text(encoding="utf-8") == original
    assert not js.with_name(js.name + FRONTEND_BACKUP_SUFFIX).exists()
    gz = js.with_name(js.name + ".gz")
    assert CARTOCDN_TILE_URL in gzip.decompress(gz.read_bytes()).decode()


def test_restore_without_backup_raises(tmp_path: Path) -> None:
    """restore with nothing to revert is a clear error, not a silent no-op."""
    (tmp_path / "frontend_latest").mkdir(parents=True)

    with pytest.raises(MapPatchError):
        restore_frontend(tmp_path)
