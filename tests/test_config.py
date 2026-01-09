import pytest
from pathlib import Path
from content_ai.config import resolve_config, load_yaml, get_config_value
from content_ai.models import ContentAIConfig


def test_default_config_loads():
    """Test default.yaml loads without errors."""
    config = resolve_config()
    assert isinstance(config, ContentAIConfig)
    assert config.detection.rms_threshold == 0.10
    assert config.processing.context_padding_s == 1.0
    assert config.output.max_duration_s == 90


def test_cli_override_rms_threshold():
    """Test CLI args override YAML defaults."""
    config = resolve_config({"rms_threshold": 0.25})
    assert isinstance(config, ContentAIConfig)
    assert config.detection.rms_threshold == 0.25


def test_cli_override_max_duration():
    """Test max_duration override."""
    config = resolve_config({"max_duration": 120})
    assert isinstance(config, ContentAIConfig)
    assert config.output.max_duration_s == 120


def test_cli_override_max_segments():
    """Test max_segments override."""
    config = resolve_config({"max_segments": 20})
    assert isinstance(config, ContentAIConfig)
    assert config.output.max_segments == 20


def test_cli_override_order():
    """Test order strategy override."""
    config = resolve_config({"order": "score"})
    assert isinstance(config, ContentAIConfig)
    assert config.output.order == "score"


def test_cli_override_keep_temp():
    """Test keep_temp flag override."""
    config = resolve_config({"keep_temp": True})
    assert isinstance(config, ContentAIConfig)
    assert config.output.keep_temp is True


def test_missing_yaml_returns_empty_dict():
    """Test graceful handling of missing config files."""
    result = load_yaml(Path("nonexistent.yaml"))
    assert result == {}


def test_multiple_cli_overrides():
    """Test multiple CLI overrides work together."""
    config = resolve_config({
        "rms_threshold": 0.15,
        "max_duration": 60,
        "order": "hybrid"
    })
    assert isinstance(config, ContentAIConfig)
    assert config.detection.rms_threshold == 0.15
    assert config.output.max_duration_s == 60
    assert config.output.order == "hybrid"


def test_get_config_value_with_pydantic():
    """Test get_config_value helper with Pydantic model."""
    config = resolve_config()
    value = get_config_value(config, "detection.rms_threshold")
    assert value == 0.10


def test_get_config_value_with_dict():
    """Test get_config_value helper with dict."""
    config_dict = {"detection": {"rms_threshold": 0.25}}
    value = get_config_value(config_dict, "detection.rms_threshold")
    assert value == 0.25


def test_get_config_value_missing_returns_default():
    """Test get_config_value returns default for missing keys."""
    config_dict = {"detection": {}}
    value = get_config_value(config_dict, "detection.nonexistent", default="default_val")
    assert value == "default_val"
