from typing import List, Dict, Any

Segment = Dict[str, Any]  # Dictionary containing at least 'start', 'end'


def merge_segments(segments: List[Segment], merge_gap: float) -> List[Segment]:
    """
    Merge segments that are close to each other.
    Assumes segments might be unsorted or overlapping.

    Args:
        segments: List of dicts with 'start' and 'end' keys.
        merge_gap: Max gap in seconds between segments to trigger a merge.

    Returns:
        New list of merged segments (sorted).
    """
    if not segments:
        return []

    # Sort by start time
    sorted_segs = sorted(segments, key=lambda x: x["start"])

    merged = []
    # Start with the first
    current = sorted_segs[0].copy()

    for next_seg in sorted_segs[1:]:
        # If overlap or within gap
        # current end + gap >= next start
        if current["end"] + merge_gap >= next_seg["start"]:
            # Merge
            current["end"] = max(current["end"], next_seg["end"])
            # We can also merge metadata if needed, e.g. keep max score
            if "score" in next_seg and "score" in current:
                current["score"] = max(current["score"], next_seg["score"])
            # If one has higher peak, take it? For now, just keep expanding.
        else:
            merged.append(current)
            current = next_seg.copy()

    merged.append(current)
    return merged


def clamp_segments(
    segments: List[Segment], min_time: float, max_time: float
) -> List[Segment]:
    """
    Clamp segment start/end times to valid range [min_time, max_time].
    Removes segments that become invalid (start >= end) after clamping.
    """
    clamped = []
    for seg in segments:
        new_seg = seg.copy()
        new_seg["start"] = max(min_time, new_seg["start"])
        new_seg["end"] = min(max_time, new_seg["end"])

        if new_seg["end"] > new_seg["start"]:
            clamped.append(new_seg)

    return clamped


def filter_min_duration(segments: List[Segment], min_duration: float) -> List[Segment]:
    """
    Remove segments shorter than min_duration.
    """
    return [s for s in segments if (s["end"] - s["start"]) >= min_duration]


def pad_segments(segments: List[Segment], padding: float) -> List[Segment]:
    """
    Apply padding to start/end of each segment.
    Note: Does NOT clamp (that happens later) or merge (happens after).
    """
    padded = []
    for seg in segments:
        new_seg = seg.copy()
        new_seg["start"] = seg["start"] - padding
        new_seg["end"] = seg["end"] + padding
        padded.append(new_seg)
    return padded
