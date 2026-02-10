from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SourceQuery(BaseModel):
    """Criteria for finding a media asset."""

    tags: List[str] = Field(
        default_factory=list, description="Tags to match (e.g., 'gameplay', 'action')"
    )
    min_quality: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum quality score")
    preferred_sources: List[str] = Field(
        default_factory=list, description="Preferred source IDs/libraries"
    )
    volume: Optional[float] = Field(None, ge=0.0, le=1.0, description="Volume level for audio")


class Effect(BaseModel):
    """Visual or Audio effect."""

    type: str = Field(..., description="Effect type (e.g., 'zoom', 'fade')")
    start: float = Field(..., description="Relative start time in segment")
    end: float = Field(..., description="Relative end time in segment")
    params: Dict[str, Any] = Field(default_factory=dict, description="Effect-specific parameters")


class BlueprintSegment(BaseModel):
    """A segment in a track."""

    start: float = Field(..., description="Start time on the timeline")
    duration: float = Field(..., description="Duration of the segment")
    source_query: Optional[SourceQuery] = Field(None, description="Criteria for asset sourcing")
    visual_description: Optional[str] = Field(None, description="Description of visual content")
    audio_intent: Optional[str] = Field(None, description="Description of audio content")
    effects: List[Effect] = Field(default_factory=list, description="Applied effects")

    @property
    def end(self) -> float:
        return self.start + self.duration


class Track(BaseModel):
    """A timeline track."""

    id: str = Field(..., description="Unique track ID")
    type: str = Field(..., description="Track type ('video', 'audio')")
    segments: List[BlueprintSegment] = Field(default_factory=list)


class Timeline(BaseModel):
    """The complete timeline."""

    duration_s: float = Field(..., description="Total duration in seconds")
    fps: int = Field(default=30, description="Frame rate")
    tracks: List[Track] = Field(default_factory=list)


class UniversalSchema(BaseModel):
    """Top-level blueprint schema."""

    project_name: str
    version: str = "1.0.0"
    timeline: Timeline
    metadata: Dict[str, Any] = Field(default_factory=dict)
