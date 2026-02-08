"""
Preset configuration logic using JSON Merge Patch semantics (RFC 7396).

This module provides utilities for:
- Computing the minimal overrides (diff) between defaults and current config
- Applying overrides to defaults to get merged config
- Validating merged configs against Pydantic models
"""

from typing import Any, Dict

from content_ai.models import ContentAIConfig

# Schema version for migration support
CURRENT_SCHEMA_VERSION = 1


def compute_overrides(defaults: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute minimal overrides (diff) between defaults and current config.
    
    Uses JSON Merge Patch semantics (RFC 7396):
    - Only values that differ from defaults are included
    - Nested dicts are recursively diffed
    - Null values mean "delete this key" (but we don't use deletion here)
    
    Args:
        defaults: The default configuration dict
        current: The current (modified) configuration dict
        
    Returns:
        Dict containing only the keys/values that differ from defaults
    """
    overrides = {}
    
    for key, current_value in current.items():
        default_value = defaults.get(key)
        
        if isinstance(current_value, dict) and isinstance(default_value, dict):
            # Recursively diff nested dicts
            nested_diff = compute_overrides(default_value, current_value)
            if nested_diff:  # Only include if there are actual differences
                overrides[key] = nested_diff
        elif current_value != default_value:
            # Value differs from default
            overrides[key] = current_value
    
    return overrides


def apply_overrides(defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply overrides to defaults using JSON Merge Patch semantics (RFC 7396).
    
    Args:
        defaults: The default configuration dict
        overrides: The overrides to apply
        
    Returns:
        Merged configuration dict
    """
    import copy
    result = copy.deepcopy(defaults)
    
    for key, override_value in overrides.items():
        if override_value is None:
            # RFC 7396: null means delete the key
            result.pop(key, None)
        elif isinstance(override_value, dict) and isinstance(result.get(key), dict):
            # Recursively merge nested dicts
            result[key] = apply_overrides(result[key], override_value)
        else:
            # Replace value
            result[key] = override_value
    
    return result


def validate_config(config_dict: Dict[str, Any]) -> ContentAIConfig:
    """
    Validate a config dict against the Pydantic model.
    
    Args:
        config_dict: The configuration dict to validate
        
    Returns:
        Validated ContentAIConfig instance
        
    Raises:
        ValidationError: If the config is invalid
    """
    return ContentAIConfig.from_dict(config_dict)


def resolve_with_preset(
    defaults: Dict[str, Any],
    preset_overrides: Dict[str, Any] | None = None,
    request_overrides: Dict[str, Any] | None = None,
) -> ContentAIConfig:
    """
    Resolve final config by layering: defaults -> preset -> request overrides.
    
    Args:
        defaults: Base default configuration
        preset_overrides: Overrides from a saved preset (optional)
        request_overrides: Overrides from the current request (optional)
        
    Returns:
        Validated ContentAIConfig instance
    """
    merged = defaults
    
    if preset_overrides:
        merged = apply_overrides(merged, preset_overrides)
    
    if request_overrides:
        merged = apply_overrides(merged, request_overrides)
    
    return validate_config(merged)


def migrate_overrides(overrides: Dict[str, Any], from_version: int) -> Dict[str, Any]:
    """
    Migrate overrides from an older schema version to current.
    
    Args:
        overrides: The overrides dict to migrate
        from_version: The schema version the overrides were created with
        
    Returns:
        Migrated overrides dict compatible with CURRENT_SCHEMA_VERSION
        
    Raises:
        ValueError: If from_version is newer than CURRENT_SCHEMA_VERSION
    """
    if from_version > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"Preset schema version {from_version} is newer than "
            f"current version {CURRENT_SCHEMA_VERSION}. Please update the application."
        )
    
    if from_version == CURRENT_SCHEMA_VERSION:
        return overrides
    
    # Future migrations would go here
    # For now, we only have version 1, so no migrations needed
    return overrides
