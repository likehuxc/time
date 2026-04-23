"""Load JSON configuration from resources/configs."""

import json
from pathlib import Path
from typing import Any

from app.paths import RESOURCES_DIR

CONFIGS_DIR = RESOURCES_DIR / "configs"


def _read_json(filename: str) -> Any:
    path = CONFIGS_DIR / filename
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_models_registry() -> dict[str, Any]:
    return _read_json("models.json")


def load_template_schema() -> dict[str, Any]:
    return _read_json("template_schema.json")
