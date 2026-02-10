from abc import ABC, abstractmethod

from .schema import UniversalSchema


class OutputStrategy(ABC):
    """Abstract base class for output strategies."""

    @abstractmethod
    def export(self, schema: UniversalSchema) -> str:
        """Export the schema to a string representation."""
        pass

class JSONStrategy(OutputStrategy):
    """Exports as raw Universal Schema JSON."""
    def export(self, schema: UniversalSchema) -> str:
        return schema.model_dump_json(indent=2)

class MarkdownStrategy(OutputStrategy):
    """Exports as a human-readable Markdown summary."""
    def export(self, schema: UniversalSchema) -> str:
        md = f"# Project: {schema.project_name}\n\n"
        md += f"**Duration:** {schema.timeline.duration_s}s | **FPS:** {schema.timeline.fps}\n\n"

        for track in schema.timeline.tracks:
            md += f"## Track: {track.id} ({track.type})\n"
            sorted_segments = sorted(track.segments, key=lambda s: s.start)
            for seg in sorted_segments:
                desc = seg.visual_description or seg.audio_intent or "No description"
                md += f"- **{seg.start:.2f}s - {seg.end:.2f}s**: {desc}\n"
            md += "\n"
        return md

class PlainTextStrategy(OutputStrategy):
    """Exports as a simplified output for screen readers."""
    def export(self, schema: UniversalSchema) -> str:
        text = f"Project {schema.project_name}, {schema.timeline.duration_s} seconds.\n"
        for track in schema.timeline.tracks:
            text += f"Track {track.id} {track.type}:\n"
            for seg in sorted(track.segments, key=lambda s: s.start):
                desc = seg.visual_description or seg.audio_intent or "Content"
                text += f"From {seg.start:.1f} to {seg.end:.1f}: {desc}.\n"
        return text

class OutputManager:
    """Manages output generation using strategies."""

    STRATEGIES = {
        "json": JSONStrategy(),
        "markdown": MarkdownStrategy(),
        "text": PlainTextStrategy(),
    }

    def __init__(self, strategy_name: str = "json"):
        self.strategy = self.STRATEGIES.get(strategy_name, JSONStrategy())

    def set_strategy(self, strategy_name: str):
        if strategy_name not in self.STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        self.strategy = self.STRATEGIES[strategy_name]

    def generate_output(self, schema: UniversalSchema) -> str:
        return self.strategy.export(schema)
