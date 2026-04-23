"""Filesystem layout: project root and standard subdirectories."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESOURCES_DIR = PROJECT_ROOT / "resources"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
