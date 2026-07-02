"""Guard translation strings against ICU message-format pitfalls.

The HA frontend renders translation strings through an ICU message formatter,
so any `{...}` is treated as a placeholder. A group like `{latitude, longitude}`
(a comma inside the braces) is parsed as an argument with an invalid type and
raises `INVALID_ARGUMENT_TYPE` in the UI. Every placeholder we use must be a
bare identifier.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
TRANSLATIONS = Path(__file__).parent.parent / "custom_components" / "kakao_map" / "translations"


def _iter_strings(obj: object) -> list[str]:
    if isinstance(obj, dict):
        return [s for value in obj.values() for s in _iter_strings(value)]
    if isinstance(obj, list):
        return [s for value in obj for s in _iter_strings(value)]
    if isinstance(obj, str):
        return [obj]
    return []


@pytest.mark.parametrize("name", ["en", "ko"])
def test_translation_placeholders_are_bare_identifiers(name: str) -> None:
    """Every {placeholder} in a translation string is a bare identifier."""
    data = json.loads((TRANSLATIONS / f"{name}.json").read_text(encoding="utf-8"))
    for text in _iter_strings(data):
        for placeholder in PLACEHOLDER.findall(text):
            assert placeholder.isidentifier(), (
                f"{name}.json: '{{{placeholder}}}' is not a bare placeholder; "
                "the frontend ICU formatter raises INVALID_ARGUMENT_TYPE"
            )
