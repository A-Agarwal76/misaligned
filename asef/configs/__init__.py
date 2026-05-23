"""
ASEF Configs Package
=====================

Provides path utilities for locating bundled YAML configuration
files shipped with the framework.

.. warning::
    This framework is for defensive AI alignment research only.
"""

from __future__ import annotations

from pathlib import Path

CONFIGS_DIR: Path = Path(__file__).resolve().parent

DEFAULT_CONFIG_PATH: Path = CONFIGS_DIR / "default.yaml"
EVALUATIONS_CONFIG_PATH: Path = CONFIGS_DIR / "evaluations.yaml"
MODELS_CONFIG_PATH: Path = CONFIGS_DIR / "models.yaml"


def get_config_path(name: str) -> Path:
    """Return the absolute path to a named config file.

    Parameters
    ----------
    name:
        Config file stem (without extension) — e.g. ``"default"``,
        ``"evaluations"``, or ``"models"``.

    Returns
    -------
    Path
        Absolute path to the YAML file.

    Raises
    ------
    FileNotFoundError
        If no config file with the given name exists.
    """
    path = CONFIGS_DIR / f"{name}.yaml"
    if not path.is_file():
        msg = f"Configuration file not found: {path}"
        raise FileNotFoundError(msg)
    return path


__all__ = [
    "CONFIGS_DIR",
    "DEFAULT_CONFIG_PATH",
    "EVALUATIONS_CONFIG_PATH",
    "MODELS_CONFIG_PATH",
    "get_config_path",
]
