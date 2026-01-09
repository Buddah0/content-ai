"""Pydantic models for configuration and data validation."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class DetectionConfig(BaseModel):
    """Audio detection parameters."""

    rms_threshold: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Minimum RMS energy threshold for event detection"
    )
    min_event_duration_s: float = Field(
        default=0.1,
        gt=0.0,
        description="Minimum event duration in seconds"
    )
    hpss_margin: tuple[float, float] = Field(
        default=(1.0, 5.0),
        description="HPSS (harmonic, percussive) margins"
    )


class ProcessingConfig(BaseModel):
    """Segment processing parameters."""

    context_padding_s: float = Field(
        default=1.0,
        ge=0.0,
        description="Pre/post-roll padding around each event in seconds"
    )
    merge_gap_s: float = Field(
        default=2.0,
        ge=0.0,
        description="Maximum gap to merge adjacent segments in seconds"
    )
    max_segment_duration_s: float = Field(
        default=10.0,
        gt=0.0,
        description="Maximum duration for any single merged segment in seconds"
    )


class OutputConfig(BaseModel):
    """Output generation settings."""

    max_duration_s: int = Field(
        default=90,
        gt=0,
        description="Maximum length of final montage in seconds"
    )
    max_segments: int = Field(
        default=12,
        gt=0,
        description="Maximum number of segments in montage"
    )
    order: Literal["chronological", "score", "hybrid"] = Field(
        default="chronological",
        description="Sorting strategy for output segments"
    )
    keep_temp: bool = Field(
        default=False,
        description="Whether to keep intermediate clip files"
    )


class ContentAIConfig(BaseModel):
    """Complete application configuration with validation."""

    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "ContentAIConfig":
        """Create config from nested dict (YAML)."""
        return cls(**data)

    def merge_cli_overrides(self, cli_args: dict) -> "ContentAIConfig":
        """Apply CLI overrides and return new config instance."""
        # Start with current config as dict
        config_dict = self.model_dump()

        # Apply CLI overrides
        if "rms_threshold" in cli_args:
            config_dict["detection"]["rms_threshold"] = cli_args["rms_threshold"]
        if "max_duration" in cli_args:
            config_dict["output"]["max_duration_s"] = cli_args["max_duration"]
        if "max_segments" in cli_args:
            config_dict["output"]["max_segments"] = cli_args["max_segments"]
        if "order" in cli_args:
            config_dict["output"]["order"] = cli_args["order"]
        if "keep_temp" in cli_args:
            config_dict["output"]["keep_temp"] = cli_args["keep_temp"]

        # Return new validated instance
        return ContentAIConfig.from_dict(config_dict)


class Segment(BaseModel):
    """Video segment with validation."""

    start: float = Field(
        ge=0.0,
        description="Start time in seconds"
    )
    end: float = Field(
        gt=0.0,
        description="End time in seconds"
    )
    score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Quality/energy score for this segment"
    )

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: float, info) -> float:
        """Validate that end time is after start time."""
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError(f"end ({v}) must be > start ({info.data['start']})")
        return v

    @property
    def duration(self) -> float:
        """Calculate segment duration."""
        return self.end - self.start


class DetectionEvent(BaseModel):
    """Detected percussive event with metadata."""

    timestamp: float = Field(
        ge=0.0,
        description="Event timestamp in seconds"
    )
    rms_energy: float = Field(
        ge=0.0,
        description="RMS energy level of the event"
    )
    score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Event quality score"
    )
