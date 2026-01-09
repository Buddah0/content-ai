import yaml
from pathlib import Path
from typing import Dict, Any, Union
from .models import ContentAIConfig

DEFAULT_CONFIG_PATH = Path("config/default.yaml")
LOCAL_CONFIG_PATH = Path("config/local.yaml")


def get_config_value(config: Union[ContentAIConfig, Dict], path: str, default=None):
    """
    Safely get a config value from either Pydantic model or dict.

    Args:
        config: ContentAIConfig model or dict
        path: Dot-separated path like "detection.rms_threshold"
        default: Default value if not found

    Returns:
        The config value or default
    """
    if isinstance(config, ContentAIConfig):
        # Convert to dict for uniform access
        config = config.model_dump()

    # Navigate nested dict
    keys = path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load YAML file, returning empty dict if not found."""
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def merge_dicts(base: Dict, override: Dict) -> Dict:
    """Recursive merge of two dictionaries."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = merge_dicts(result[k], v)
        else:
            result[k] = v
    return result


def resolve_config(cli_args: Dict[str, Any] = None) -> Union[ContentAIConfig, Dict[str, Any]]:
    """
    Resolve config: Default < Local < CLI
    Returns validated Pydantic ContentAIConfig model.

    For backward compatibility, can also return dict if Pydantic validation fails.
    """
    cli_args = cli_args or {}

    # 1. Load default YAML
    config_data = load_yaml(DEFAULT_CONFIG_PATH)

    # 2. Merge local overrides
    local_data = load_yaml(LOCAL_CONFIG_PATH)
    config_data = merge_dicts(config_data, local_data)

    try:
        # 3. Create validated Pydantic model
        config = ContentAIConfig.from_dict(config_data)

        # 4. Apply CLI overrides
        config = config.merge_cli_overrides(cli_args)

        return config
    except Exception as e:
        # Fallback to dict for backward compatibility during migration
        # TODO: Remove this fallback after full migration
        print(f"Warning: Pydantic validation failed, using dict: {e}")

        # Apply CLI overrides manually for dict fallback
        if cli_args.get("rms_threshold") is not None:
            config_data.setdefault("detection", {})["rms_threshold"] = cli_args["rms_threshold"]
        if cli_args.get("max_duration") is not None:
            config_data.setdefault("output", {})["max_duration_s"] = cli_args["max_duration"]
        if cli_args.get("max_segments") is not None:
            config_data.setdefault("output", {})["max_segments"] = cli_args["max_segments"]
        if cli_args.get("keep_temp") is not None:
            config_data.setdefault("output", {})["keep_temp"] = cli_args["keep_temp"]
        if cli_args.get("order") is not None:
            config_data.setdefault("output", {})["order"] = cli_args["order"]

        return config_data
