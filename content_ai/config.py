import os
import yaml
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG_PATH = Path("config/default.yaml")
LOCAL_CONFIG_PATH = Path("config/local.yaml")


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def merge_dicts(base: Dict, override: Dict) -> Dict:
    """Recursive merge."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = merge_dicts(result[k], v)
        else:
            result[k] = v
    return result


def resolve_config(cli_args: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Resolve config: Default < Local < CLI
    """
    cli_args = cli_args or {}

    # 1. Default
    config = load_yaml(DEFAULT_CONFIG_PATH)

    # 2. Local
    local = load_yaml(LOCAL_CONFIG_PATH)
    config = merge_dicts(config, local)

    # 3. CLI Overrides (Flattened in CLI args, need to map to nested structure if needed)
    # For now, we assume CLI args that match config top-levels might be passed
    # But typically CLI args like --rms-threshold might map to detection.rms_threshold
    # We will handle specific CLI-to-Config mapping manually or via a schema map here if needed.
    # For this simple tool, I'll allow specific known CLI args to override keys.

    if cli_args.get("rms_threshold") is not None:
        config.setdefault("detection", {})["rms_threshold"] = cli_args["rms_threshold"]

    if cli_args.get("max_duration") is not None:
        config.setdefault("output", {})["max_duration_s"] = cli_args["max_duration"]

    if cli_args.get("max_segments") is not None:
        config.setdefault("output", {})["max_segments"] = cli_args["max_segments"]

    if cli_args.get("keep_temp") is not None:
        config.setdefault("output", {})["keep_temp"] = cli_args["keep_temp"]

    if cli_args.get("order") is not None:
        config.setdefault("output", {})["order"] = cli_args["order"]

    return config
