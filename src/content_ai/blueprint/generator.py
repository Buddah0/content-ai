from typing import Any, Dict, List

from .schema import BlueprintSegment, Timeline, Track, UniversalSchema


class BlueprintGenerator:
    """Generates UniversalSchema blueprints from raw input data."""

    def __init__(self):
        pass

    def create_blueprint(self, project_name: str, raw_segments: List[Dict[str, Any]]) -> UniversalSchema:
        """
        Creates a blueprint from a list of raw segments (e.g. from detector).
        
        Args:
            project_name: Name of the project.
            raw_segments: List of dicts, expected to have 'start', 'end', and optional metadata.
        
        Returns:
            A UniversalSchema object.
        """
        # Calculate total duration
        total_duration = 0.0
        if raw_segments:
            total_duration = max(s.get("end", 0) for s in raw_segments)

        # Create video track
        video_track = Track(id="main_video", type="video")

        for raw in raw_segments:
            start = raw.get("start", 0.0)
            end = raw.get("end", 0.0)
            if end <= start:
                continue

            seg = BlueprintSegment(
                start=start,
                duration=end - start,
                visual_description=raw.get("description", "Generated segment"),
                # In a real implementation, we'd map more fields here
            )
            video_track.segments.append(seg)

        # Build schema
        schema = UniversalSchema(
            project_name=project_name,
            timeline=Timeline(
                duration_s=total_duration,
                tracks=[video_track]
            )
        )

        return schema
