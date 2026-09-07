"""The editor needs rhythm, timed RMS and functional sections, not classifiers."""
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Callable

from api.studio_models import StudioAnalysis

SAMPLE_RATE = 44100
RMS_HOP = 512
STRUCTURE_TOLERANCE_S = 0.25


class StudioAnalysisError(ValueError):
    pass


def validate_studio_result(value: dict) -> dict:
    """Reject incomplete/nonphysical outputs without correcting story structure."""
    result = StudioAnalysis.model_validate(value).model_dump()
    duration = result["duration"]
    for name in ("beats", "onsets"):
        points = result[name]
        if name == "beats" and not points:
            raise StudioAnalysisError("No usable beats were detected.")
        if any(not math.isfinite(t) or t < 0 or t > duration for t in points):
            raise StudioAnalysisError(f"Invalid {name} timing.")
        if any(b <= a for a, b in zip(points, points[1:])):
            raise StudioAnalysisError(f"Non-monotonic {name} timing.")
    energy = result["energy"]
    if not energy["curve"] or any(not math.isfinite(v) or not 0 <= v <= 1 for v in energy["curve"]):
        raise StudioAnalysisError("Invalid normalized RMS energy.")
    if energy["start_time_s"] != 0 or abs(energy["sample_rate_hz"] - SAMPLE_RATE / RMS_HOP) > 1e-9:
        raise StudioAnalysisError("Unexpected RMS frame timing.")
    if abs((len(energy["curve"]) - 1) / energy["sample_rate_hz"] - duration) > 2 / energy["sample_rate_hz"]:
        raise StudioAnalysisError("RMS curve does not cover the full audio.")
    structure = result["structure"]
    sections = structure["sections"]
    if not structure["provenance"]["method"].startswith("allin1:") or not sections:
        raise StudioAnalysisError("Functional structure evidence is missing.")
    tolerance = STRUCTURE_TOLERANCE_S
    if sections[0]["start"] > tolerance or abs(sections[-1]["end"] - duration) > tolerance:
        raise StudioAnalysisError("Functional sections do not cover the full audio.")
    if abs(structure["analyzed_duration_s"] - duration) > tolerance:
        raise StudioAnalysisError("Structure duration differs from decoded audio.")
    for i, section in enumerate(sections):
        if section["end"] <= section["start"] or abs(section["duration"] - (section["end"] - section["start"])) > 1e-6:
            raise StudioAnalysisError("Invalid section duration.")
        if i and abs(section["start"] - sections[i - 1]["end"]) > 1e-6:
            raise StudioAnalysisError("Functional sections overlap or contain a gap.")
        if not section["label"].strip() or not section["original_label"].strip():
            raise StudioAnalysisError("Section label is missing.")
    expected = [sections[0]["start"]] + [s["end"] for s in sections]
    if len(expected) != len(structure["boundaries"]) or any(abs(a - b) > 1e-6 for a, b in zip(expected, structure["boundaries"])):
        raise StudioAnalysisError("Section boundaries disagree with sections.")
    return result


def build_studio_result(rhythm: dict, structure: dict, model: str) -> dict:
    rate = SAMPLE_RATE / RMS_HOP
    curve = rhythm["energy"]["curve"]
    sections = []
    for section in structure["sections"]:
        # Average actual normalized RMS frame centers falling in this interval.
        first = max(0, math.ceil(section["start"] * rate))
        last = min(len(curve), math.ceil(section["end"] * rate))
        samples = curve[first:last]
        if not samples:
            raise StudioAnalysisError("Section has no RMS samples.")
        sections.append({**section, "energy": sum(samples) / len(samples)})
    result = validate_studio_result({
        "schema_version": "studio-audio-v1",
        **{name: rhythm[name] for name in ("duration", "bpm", "beats", "confidence", "onsets")},
        "energy": {"curve": curve, "sample_rate_hz": rate, "start_time_s": 0.0},
        "structure": {**structure, "sections": sections, "provenance": {
            "status": "detected", "method": f"allin1:{model}", "device": "cuda",
        }},
    })
    # The decoder is the authority for analyzed duration; keep model section
    # endpoints unchanged, including any accepted sub-frame rounding difference.
    result["structure"]["analyzed_duration_s"] = result["duration"]
    return result


def analyze_studio_file(path: str, progress: Callable[[str], None]) -> dict:
    # Lazy imports keep API/job lifecycle independent from inference startup.
    from services.allin1_structure import analyze_structure_allin1_logic, require_studio_cuda
    require_studio_cuda()
    from services.analysis import load_audio, analyze_rhythm_logic
    progress("decoding")
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path,
    ], capture_output=True, text=True, timeout=20, check=True)
    maximum = float(os.getenv("STUDIO_MAX_AUDIO_SECONDS", "1800"))
    probed_duration = float(json.loads(probe.stdout)["format"]["duration"])
    if not math.isfinite(probed_duration) or not 0 < probed_duration <= maximum:
        raise StudioAnalysisError("Audio duration exceeds the Studio analysis limit.")
    audio = load_audio(path, SAMPLE_RATE)
    duration = len(audio) / SAMPLE_RATE
    if not 0 < duration <= maximum:
        raise StudioAnalysisError("Audio duration exceeds the Studio analysis limit.")
    progress("rhythm")
    rhythm = analyze_rhythm_logic(audio, SAMPLE_RATE)
    progress("structure")
    structure = analyze_structure_allin1_logic(path, workspace=Path(path).parent / "scratch", preserve_labels=True, require_cuda=True)
    progress("validating")
    return build_studio_result(rhythm, structure, os.getenv("ALLIN1_MODEL", "harmonix-all").strip() or "harmonix-all")


if __name__ == "__main__":
    import sys
    path, output, stage = map(Path, sys.argv[1:])
    def progress(value):
        temporary = stage.with_suffix(".tmp")
        temporary.write_text(value)
        temporary.replace(stage)
    try:
        result = analyze_studio_file(str(path), progress)
    except Exception as exc:
        from services.allin1_structure import AllInOneCudaRequiredError
        if isinstance(exc, AllInOneCudaRequiredError):
            (path.parent / "error.json").write_text(json.dumps({"code": "cuda_unavailable"}))
        raise
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, allow_nan=False))
    temporary.replace(output)
