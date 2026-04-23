"""Ensure standard project directories exist on disk."""

from app.paths import DATA_DIR, RESOURCES_DIR, RUNTIME_DIR


def bootstrap() -> None:
    for d in (DATA_DIR, RESOURCES_DIR, RUNTIME_DIR):
        d.mkdir(parents=True, exist_ok=True)
