"""Pydantic models for configuration and data validation."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DetectionConfig(BaseModel):
    """Audio detection parameters."""

    rms_threshold: float = Field(
        default=0.10, ge=0.0, le=1.0, description="Minimum RMS energy threshold for event detection"
    )
    min_event_duration_s: float = Field(
        default=0.1, gt=0.0, description="Minimum event duration in seconds"
    )
    hpss_margin: tuple[float, float] = Field(
        default=(1.0, 5.0), description="HPSS (harmonic, percussive) margins"
    )
    adaptive_threshold: bool = Field(
        default=True, description="Use adaptive thresholding (Mean + k*Std) instead of fixed"
    )
    sensitivity: float = Field(
        default=2.5, ge=0.0, description="Adaptive sensitivity (k in Mean + k*Std). Higher = fewer events."
    )
    event_lookback_s: float = Field(
        default=5.0, ge=0.0, description="Seconds to look back from the start of an event (captures build-up)"
    )


class ProcessingConfig(BaseModel):
    """Segment processing parameters."""

    context_padding_s: float = Field(
        default=1.0, ge=0.0, description="Pre/post-roll padding around each event in seconds"
    )
    merge_gap_s: float = Field(
        default=2.0, ge=0.0, description="Maximum gap to merge adjacent segments in seconds"
    )
    max_segment_duration_s: float = Field(
        default=10.0,
        gt=0.0,
        description="Maximum duration for any single merged segment in seconds",
    )


class OutputConfig(BaseModel):
    """Output generation settings."""

    max_duration_s: int = Field(
        default=90, gt=0, description="Maximum length of final montage in seconds"
    )
    max_segments: int = Field(default=12, gt=0, description="Maximum number of segments in montage")
    order: Literal["chronological", "score", "hybrid"] = Field(
        default="chronological", description="Sorting strategy for output segments"
    )
    keep_temp: bool = Field(default=False, description="Whether to keep intermediate clip files")


class VideoCodecConfig(BaseModel):
    """Video codec specifications for render contract."""

    codec: str = Field(default="libx264", description="Video codec name (e.g., libx264, libx265)")
    profile: Literal["baseline", "main", "high"] = Field(
        default="high", description="H.264 profile level"
    )
    level: str = Field(default="4.1", description="H.264 level (e.g., 4.1 supports 1080p@30fps)")
    pixel_format: str = Field(
        default="yuv420p", description="Pixel format (yuv420p for broad compatibility)"
    )
    target_fps: Optional[int] = Field(
        default=30, gt=0, description="Target frame rate for CFR (None = preserve source fps)"
    )
    crf: int = Field(
        default=23, ge=0, le=51, description="Constant Rate Factor (0-51, lower = better quality)"
    )
    preset: Literal[
        "ultrafast",
        "superfast",
        "veryfast",
        "faster",
        "fast",
        "medium",
        "slow",
        "slower",
        "veryslow",
    ] = Field(default="medium", description="Encoding speed preset (faster = larger files)")


class AudioCodecConfig(BaseModel):
    """Audio codec specifications for render contract."""

    codec: str = Field(default="aac", description="Audio codec name (e.g., aac, mp3)")
    sample_rate: int = Field(default=48000, gt=0, description="Audio sample rate in Hz")
    channels: int = Field(default=2, ge=1, le=8, description="Audio channels (1=mono, 2=stereo)")
    bitrate: str = Field(default="192k", description="Audio bitrate (e.g., '128k', '192k', '320k')")


class RenderContractConfig(BaseModel):
    """Render contract defining guaranteed output specifications."""

    container: str = Field(default="mp4", description="Container format")
    video_codec: VideoCodecConfig = Field(
        default_factory=VideoCodecConfig, description="Video codec settings"
    )
    audio_codec: AudioCodecConfig = Field(
        default_factory=AudioCodecConfig, description="Audio codec settings"
    )


class VFRDetectionConfig(BaseModel):
    """VFR detection parameters."""

    frame_rate_tolerance: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="Max fractional difference between avg_frame_rate and r_frame_rate to consider VFR",
    )


class RenderingConfig(BaseModel):
    """FFmpeg rendering configuration with normalization controls."""

    contract: RenderContractConfig = Field(
        default_factory=RenderContractConfig,
        description="Render contract specifying guaranteed output format",
    )
    normalize_to_contract: bool = Field(
        default=True,
        description="Re-encode segments to contract specs (ensures VFR safety and consistent output)",
    )
    validate_before_concat: bool = Field(
        default=True, description="Probe segments before concat to verify compatibility"
    )
    force_cfr: bool = Field(default=True, description="Convert VFR to CFR to prevent audio desync")
    fast_path_enabled: bool = Field(
        default=True, description="Allow -c copy for compatible sources (speed optimization)"
    )
    vfr_detection: VFRDetectionConfig = Field(
        default_factory=VFRDetectionConfig, description="VFR detection settings"
    )

    # FFmpeg runner settings
    global_timeout_s: int = Field(
        default=1800,
        gt=0,
        description="Maximum duration for any FFmpeg operation in seconds (30 min default)",
    )
    no_progress_timeout_s: int = Field(
        default=120,
        gt=0,
        description="Timeout if no progress update in N seconds (stall detection)",
    )
    max_retries: int = Field(
        default=2, ge=0, description="Number of retry attempts for transient errors"
    )
    temp_dir: Optional[str] = Field(
        default=None, description="Temporary directory for artifacts (None = use worker temp dir)"
    )
    kill_grace_period_s: int = Field(
        default=5, gt=0, description="Grace period between SIGTERM and SIGKILL"
    )
    save_artifacts_on_failure: bool = Field(
        default=True, description="Save FFmpeg logs and commands on failure for debugging"
    )
    ffmpeg_loglevel: str = Field(
        default="info", description="FFmpeg log level: error, warning, info, verbose"
    )


class ContentAIConfig(BaseModel):
    """Complete application configuration with validation."""

    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    rendering: RenderingConfig = Field(default_factory=RenderingConfig)

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

    start: float = Field(ge=0.0, description="Start time in seconds")
    end: float = Field(gt=0.0, description="End time in seconds")
    score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Quality/energy score for this segment"
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

    timestamp: float = Field(ge=0.0, description="Event timestamp in seconds")
    rms_energy: float = Field(ge=0.0, description="RMS energy level of the event")
    score: float = Field(default=0.5, ge=0.0, le=1.0, description="Event quality score")
