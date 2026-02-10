# Content Re-creation Engine Architecture

> [!NOTE] 
> This document defines the **future** "Content Re-creation Engine" architecture. For the current production pipeline and deterministic rendering contract, see [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Overview
The Content Re-creation Engine is a system for generating video content from abstract blueprints. Unlike the current extraction-based pipeline, this engine focuses on **re-creation**: taking a structured description of intent (visuals, audio, pacing) and assembling it from a library of assets.

## 2. Universal Schema
The core of the re-creation engine is the **Universal Schema**, a JSON-based intermediate representation (IR) that fully describes a video timeline without referencing specific source files until the sourcing phase.

### Schema Definition
```json
{
  "project_name": "example_project",
  "version": "1.0.0",
  "timeline": {
    "duration_s": 60.0,
    "fps": 30,
    "tracks": [
      {
        "id": "track_1_visual",
        "type": "video",
        "segments": [
          {
            "start": 0.0,
            "duration": 5.0,
            "source_query": {
              "tags": ["gameplay", "action", "high_energy"],
              "min_quality": 0.8,
              "preferred_sources": ["library_a"]
            },
            "visual_description": "Player scores a winning goal in Rocket League",
            "effects": [
              {"type": "zoom", "start": 0.0, "end": 1.0, "factor": 1.2}
            ]
          }
        ]
      },
      {
        "id": "track_2_audio",
        "type": "audio",
        "segments": [
          {
            "start": 0.0,
            "duration": 5.0,
            "source_query": {
              "tags": ["sfx", "cheering"],
              "volume": 0.8
            },
            "audio_intent": "Crowd cheering loudly"
          }
        ]
      }
    ]
  },
  "metadata": {
    "generated_by": "BlueprintGenerator",
    "timestamp": "2023-10-27T10:00:00Z"
  }
}
```

## 3. Pipeline Stages
The re-creation pipeline consists of four distinct stages:

1.  **Scan ([Scanner])**:
    *   **Input**: Raw user prompts, game logs, or existing video analysis.
    *   **Output**: Structured data ready for blueprinting.
    *   **Responsibility**: Ingest data from various input sources.

2.  **Analyze/Blueprint ([BlueprintGenerator])**:
    *   **Input**: Structured data from Scan stage.
    *   **Output**: **Universal Schema (JSON)**.
    *   **Responsibility**: Convert abstract intent into a concrete temporal plan. detailed `VisualDescriptions` and `AudioIntent` are generated here.
    *   **Constraint**: Pure function. Same input -> Same JSON.

3.  **Asset Sourcing ([AssetManager])**:
    *   **Input**: Universal Schema.
    *   **Output**: **Resolved Timeline** (Schema with concrete file paths).
    *   **Responsibility**: Resolve `source_query` objects to actual file paths on disk.
    *   **Logic**:
        *   Query local asset database.
        *   Download missing assets (future).
        *   Fallback to placeholders if not found.

4.  **Assembly ([Renderer])**:
    *   **Input**: Resolved Timeline.
    *   **Output**: Final Video File (WebM/MP4).
    *   **Responsibility**: Render the timeline to pixels.
    *   **Note**: Uses the existing robust `renderer.py` logic but adapted for multi-track composition.

## 4. Integration & Constraints

### Constraints
*   **Python 3.11+**: Leverage modern type hinting and performance features.
*   **Lightweight**: Minimal heavy dependencies.
*   **NVDA-Friendly**:
    *   **CLI-First**: All operations must be accessible via CLI for screen reader users.
    *   **No Heavy GUI**: Avoid dependencies on complex GUI frameworks like Qt unless optional.
    *   **Text-Based Configuration**: fully configurable via YAML/JSON.

### Output Strategy Pattern
The `OutputManager` handles exporting the generated blueprint in various formats mainly for human/NVDA consumption:

*   **JSON**: Full Universal Schema (machine readable).
*   **Markdown**: Human-readable summary of the timeline (e.g., "0:00-0:05: [Action] Player scores...").
*   **Plain Text**: Simplified text representation.

### NVDA Integration Hook
A lightweight adapter layer maps UI selections (from a theoretical NVDA add-on) to `OutputConfig` and renderer settings.

```python
# Example Concept
def map_nvda_selection_to_config(selection_id: str) -> dict:
    if selection_id == "high_contrast_webm":
        return {"output_format": "webm", "video_codec": "vp9", "crf": 15}
    return {}
```

## 5. Mapping to Existing Architecture
*   **Renderer**: The existing `renderer.py` will be extended to support the chosen `output_format` (MP4 vs WebM).
*   **determinism**: The blueprint generation must remain deterministic. The `run_meta.json` will capture the specific blueprint version used.

---
*See [ARCHITECTURE.md](ARCHITECTURE.md) for current production pipeline details.*
