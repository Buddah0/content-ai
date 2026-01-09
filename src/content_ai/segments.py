from typing import List, Dict, Any

Segment = Dict[str, Any]  # Dictionary containing at least 'start', 'end'


def merge_segments(
    segments: List[Segment], merge_gap: float, max_duration: float = None
) -> List[Segment]:
    """
    Smart Merging: Merge segments that are close to each other with max duration enforcement.

    This implements the "Audio-First" smart merging strategy:
    1. Apply padding (pre-roll/post-roll) to events BEFORE calling this (done in pipeline)
    2. Merge segments if gap between them < merge_gap
    3. Enforce max_duration cap: if merging would exceed max_duration, keep the
       segment window with highest peak energy (deterministic tie-breaking)

    Assumes segments might be unsorted or overlapping.

    Args:
        segments: List of dicts with 'start' and 'end' keys (and optional 'score').
        merge_gap: Max gap in seconds between segments to trigger a merge.
        max_duration: Maximum duration for any single merged segment (None = no limit).

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
        # Check if we should merge (overlap or within gap)
        gap = next_seg["start"] - current["end"]

        if gap <= merge_gap:
            # Calculate what the merged duration would be
            potential_end = max(current["end"], next_seg["end"])
            potential_duration = potential_end - current["start"]

            # Check max_duration constraint
            if max_duration and potential_duration > max_duration:
                # Cannot merge: would exceed max_duration
                # Strategy: Keep the segment window with highest peak energy
                current_score = current.get("score", 0)
                next_score = next_seg.get("score", 0)

                if next_score > current_score:
                    # Next segment has higher energy, replace current
                    merged.append(current)
                    current = next_seg.copy()
                else:
                    # Current segment has higher/equal energy, keep it and discard next
                    # (Deterministic tie-breaking: keep first encountered on equal scores)
                    merged.append(current)
                    current = next_seg.copy()
            else:
                # Safe to merge
                current["end"] = potential_end
                # Keep max score when merging
                if "score" in next_seg and "score" in current:
                    current["score"] = max(current["score"], next_seg["score"])
                # Merge other metadata if needed
                if "peak_rms" in next_seg and "peak_rms" in current:
                    current["peak_rms"] = max(current["peak_rms"], next_seg["peak_rms"])
        else:
            # Gap too large, finalize current and start new segment
            merged.append(current)
            current = next_seg.copy()

    # Don't forget the last segment
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
