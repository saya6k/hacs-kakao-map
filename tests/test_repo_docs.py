"""Guard the HACS/repo docs so the integration stays installable and documented."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
SERVICES_YAML = ROOT / "custom_components" / "kakao_map" / "services.yaml"


def test_hacs_json_valid_and_requires_readme() -> None:
    """hacs.json is valid, names the integration, and (render_readme) has a README."""
    data = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert data["name"]
    if data.get("render_readme"):
        assert (ROOT / "README.md").is_file()


def test_readme_documents_every_service() -> None:
    """The README mentions every service defined in services.yaml."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    services = yaml.safe_load(SERVICES_YAML.read_text(encoding="utf-8"))
    for name in services:
        assert f"kakao_map.{name}" in readme, f"README missing kakao_map.{name}"
