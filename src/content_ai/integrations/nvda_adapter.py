from typing import Any, Dict


def map_nvda_selection_to_config(selection_id: str) -> Dict[str, Any]:
    """
    Maps a UI selection ID (from an NVDA add-on or CLI menu)
    to a partial configuration dictionary for Content AI.

    Args:
        selection_id: Identifier string from the UI.

    Returns:
        Dictionary of config overrides.
    """
    if selection_id == "high_contrast_webm":
        return {
            "output_format": "webm",
            # Hypothetical future config for high contrast
            "rendering": {
                "contract": {
                    "video_codec": {"crf": 15},  # Higher quality
                }
            },
        }
    elif selection_id == "standard_mp4":
        return {
            "output_format": "mp4",
        }
    elif selection_id == "blueprint_json":
        # This might signal to not render video but export blueprint
        return {
            "output_format": "json",  # Not currently supported by renderer but handled by config logic?
        }

    return {}
