"""
Centralized Configuration Loader
=================================
Safely loads business rules from ``config/business_rules.yaml``.
All pipeline modules and the Streamlit dashboard import ``load_config()``
from this module to obtain a single-source-of-truth dictionary.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

# ---------------------------------------------------------------------------
# Resolve the YAML path relative to the **project root**, not the CWD.
# This allows the loader to work identically whether invoked from
# ``app/main.py``, ``pipelines/bunching.py``, or a Jupyter notebook.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config" / "business_rules.yaml"


class ConfigLoadError(Exception):
    """Raised when the configuration file cannot be loaded or parsed."""


@lru_cache(maxsize=1)
def load_config(config_path: str | Path | None = None) -> Dict[str, Any]:
    """Load and return the business-rules configuration dictionary.

    Parameters
    ----------
    config_path : str | Path | None
        Absolute or relative path to the YAML file.
        *Defaults* to ``<project_root>/config/business_rules.yaml``.

    Returns
    -------
    dict
        Parsed YAML content as a nested Python dictionary.

    Raises
    ------
    ConfigLoadError
        If the file is missing, unreadable, or contains malformed YAML.
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    if not path.exists():
        raise ConfigLoadError(
            f"Configuration file not found: {path}\n"
            "Please ensure 'config/business_rules.yaml' exists in the project root."
        )

    try:
        with open(path, "r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigLoadError(
            f"Malformed YAML in configuration file: {path}\n{exc}"
        ) from exc
    except OSError as exc:
        raise ConfigLoadError(
            f"Unable to read configuration file: {path}\n{exc}"
        ) from exc

    if not isinstance(config, dict):
        raise ConfigLoadError(
            f"Expected a YAML mapping (dict) at the top level, got {type(config).__name__}."
        )

    return config


# ---------------------------------------------------------------------------
# Convenience: allow ``python -m utils.config_loader`` for a quick sanity check
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from pprint import pprint

    try:
        cfg = load_config()
        print("Configuration loaded successfully!\n")
        pprint(cfg)
    except ConfigLoadError as e:
        print(f"{e}", file=sys.stderr)
        sys.exit(1)
