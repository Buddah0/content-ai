"""Tests for preset override computation and application logic."""

import pytest

from content_ai.presets import apply_overrides, compute_overrides, migrate_overrides


class TestComputeOverrides:
    """Tests for compute_overrides function."""

    def test_empty_diff(self):
        """Identical dicts should yield empty overrides."""
        defaults = {"a": 1, "b": {"c": 2}}
        current = {"a": 1, "b": {"c": 2}}
        assert compute_overrides(defaults, current) == {}

    def test_simple_diff(self):
        """Simple value change should be captured."""
        defaults = {"a": 1, "b": 2}
        current = {"a": 1, "b": 3}
        assert compute_overrides(defaults, current) == {"b": 3}

    def test_nested_diff(self):
        """Nested value change should be captured with minimal path."""
        defaults = {"detection": {"rms_threshold": 0.1, "sensitivity": 2.5}}
        current = {"detection": {"rms_threshold": 0.3, "sensitivity": 2.5}}
        result = compute_overrides(defaults, current)
        assert result == {"detection": {"rms_threshold": 0.3}}

    def test_new_key(self):
        """New keys in current should be captured."""
        defaults = {"a": 1}
        current = {"a": 1, "b": 2}
        assert compute_overrides(defaults, current) == {"b": 2}


class TestApplyOverrides:
    """Tests for apply_overrides function (JSON Merge Patch RFC 7396)."""

    def test_simple_merge(self):
        """Simple override should replace value."""
        defaults = {"a": 1, "b": 2}
        overrides = {"b": 3}
        result = apply_overrides(defaults, overrides)
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        """Nested override should merge recursively."""
        defaults = {"detection": {"rms_threshold": 0.1, "sensitivity": 2.5}}
        overrides = {"detection": {"rms_threshold": 0.3}}
        result = apply_overrides(defaults, overrides)
        assert result == {"detection": {"rms_threshold": 0.3, "sensitivity": 2.5}}

    def test_null_removes_key(self):
        """None value should remove the key (RFC 7396)."""
        defaults = {"a": 1, "b": 2}
        overrides = {"b": None}
        result = apply_overrides(defaults, overrides)
        assert result == {"a": 1}

    def test_add_new_key(self):
        """New key in overrides should be added."""
        defaults = {"a": 1}
        overrides = {"b": 2}
        result = apply_overrides(defaults, overrides)
        assert result == {"a": 1, "b": 2}

    def test_does_not_mutate_defaults(self):
        """Original defaults should not be mutated."""
        defaults = {"a": {"b": 1}}
        overrides = {"a": {"b": 2}}
        apply_overrides(defaults, overrides)
        assert defaults == {"a": {"b": 1}}


class TestMigrateOverrides:
    """Tests for migrate_overrides function."""

    def test_no_migration_needed(self):
        """Current version should return overrides unchanged."""
        from content_ai.presets import CURRENT_SCHEMA_VERSION
        overrides = {"a": 1}
        result = migrate_overrides(overrides, CURRENT_SCHEMA_VERSION)
        assert result == overrides

    def test_future_version_raises(self):
        """Future schema version should raise error."""
        from content_ai.presets import CURRENT_SCHEMA_VERSION
        with pytest.raises(ValueError, match="newer than"):
            migrate_overrides({}, CURRENT_SCHEMA_VERSION + 1)
