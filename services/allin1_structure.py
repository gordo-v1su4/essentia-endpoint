"""
Music structure analysis via mir-aidj/all-in-one (allin1 PyPI package).

Predicts functional segments (intro, verse, chorus, ...) from demixed audio.
See https://github.com/mir-aidj/all-in-one
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List


class AllInOneStructureError(Exception):
    """Raised when all-in-one cannot produce usable segments."""


class AllInOneCudaRequiredError(AllInOneStructureError):
    """The Studio pipeline never silently runs models on CPU/MPS."""


def require_studio_cuda() -> str:
    if os.getenv("ALLIN1_DEVICE", "").strip().lower() not in ("", "cuda") or not _cuda_usable():
        raise AllInOneCudaRequiredError("Studio requires usable CUDA and ALLIN1_DEVICE=cuda; CPU/MPS inference is disabled.")
    # Torch allocation alone does not validate NATTEN's separate compiled
    # extension. Its CPU-only build can warn and return invalid finite model
    # activations on CUDA instead of raising an exception.
    try:
        import natten

        supported = natten.has_cuda()
    except Exception as exc:
        raise AllInOneCudaRequiredError("Studio requires a compatible CUDA-enabled NATTEN extension.") from exc
    if not supported:
        raise AllInOneCudaRequiredError("Studio requires NATTEN compiled with CUDA support; rebuild the image with NATTEN_WITH_CUDA=1 and the target GPU architecture.")
    return "cuda"


_SKIP_LABELS = frozenset({"start", "end"})
_BRIDGE_LABELS = frozenset({"inst", "solo", "break"})


def _resolve_device() -> str:
    override = os.getenv("ALLIN1_DEVICE", "").strip().lower()
    if override in ("cpu", "cuda", "mps"):
        if override == "cuda" and not _cuda_usable():
            raise AllInOneStructureError(
                "ALLIN1_DEVICE=cuda but CUDA is not usable in this container. "
                "RTX 50-series (sm_120) needs PyTorch cu128; RTX 4090 works with cu118. "
                "On a 5090 dev machine, omit ALLIN1_DEVICE (auto → cpu) or point beatsmaxxer at a 4090 server."
            )
        return override
    try:
        import torch

        if torch.cuda.is_available() and _cuda_usable():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _cuda_usable() -> bool:
    try:
        import torch

        if not torch.cuda.is_available():
            return False
        name = torch.cuda.get_device_name(0)
        arch = torch.cuda.get_device_capability(0)
        torch.zeros(1, device="cuda")
        print(f"[Structure] CUDA ok: {name} (sm_{arch[0]}{arch[1]})")
        return True
    except Exception as exc:
        try:
            import torch

            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                cap = torch.cuda.get_device_capability(0)
                print(
                    f"[Structure] CUDA probe failed on {name} (sm_{cap[0]}{cap[1]}): {exc}. "
                    "If this is a 5090 dev box, use a 4090 server or ALLIN1_DEVICE=cpu."
                )
            else:
                print(f"[Structure] CUDA unavailable: {exc}")
        except Exception:
            print(f"[Structure] CUDA unavailable: {exc}")
        return False


def _normalize_label(raw: str) -> str | None:
    key = raw.strip().lower()
    if key in _SKIP_LABELS:
        return None
    if key in _BRIDGE_LABELS:
        return "bridge"
    if key in ("intro", "verse", "chorus", "bridge", "outro"):
        return key
    return "section"


def _merge_adjacent_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not sections:
        return []
    merged: List[Dict[str, Any]] = [sections[0]]
    for section in sections[1:]:
        prev = merged[-1]
        if section["label"] == prev["label"]:
            prev["end"] = section["end"]
            prev["duration"] = float(prev["end"] - prev["start"])
            continue
        merged.append(section)
    return merged


def analyze_structure_allin1_logic(file_path: str, *, workspace: Path | None = None, preserve_labels: bool = False, require_cuda: bool = False) -> Dict[str, Any]:
    """
    Run all-in-one on a WAV/MP3 file path and map segments to StructureAnalysis shape.
    """
    try:
        import allin1
    except ImportError as exc:
        raise AllInOneStructureError(
            "allin1 is not installed in this container. Rebuild essentia-endpoint with all-in-one deps."
        ) from exc

    device = require_studio_cuda() if require_cuda else _resolve_device()
    model = os.getenv("ALLIN1_MODEL", "harmonix-all").strip() or "harmonix-all"
    print(f"[Structure] allin1 start path={file_path} device={device} model={model}")

    try:
        options = {} if workspace is None else {
            "demix_dir": workspace / "demix", "spec_dir": workspace / "spec",
            "multiprocess": False,
        }
        result = allin1.analyze(
            paths=file_path,
            model=model,
            device=device,
            keep_byproducts=False,
            **options,
        )
    except Exception as exc:
        raise AllInOneStructureError(f"all-in-one analysis failed: {exc}") from exc

    raw_segments = getattr(result, "segments", None) or []
    sections: List[Dict[str, Any]] = []
    for segment in raw_segments:
        label = _normalize_label(getattr(segment, "label", "") or "")
        if label is None:
            if not preserve_labels:
                continue
            # Model start/end intervals represent nonmusical margins, not an
            # inferred intro/outro. Studio keeps their exact time coverage.
            label = "section"
        start = float(getattr(segment, "start", 0.0))
        end = float(getattr(segment, "end", start))
        if end <= start:
            continue
        section = {
                "start": start,
                "end": end,
                "label": label,
                "duration": end - start,
                "energy": 0.0,
            }
        if preserve_labels:
            section["original_label"] = getattr(segment, "label", "").strip().lower()
        sections.append(section)

    # Studio keeps individual model intervals/raw labels (e.g. inst vs solo).
    if not preserve_labels:
        sections = _merge_adjacent_sections(sections)
    if not sections:
        raise AllInOneStructureError("all-in-one returned no functional segments.")

    boundaries = [sections[0]["start"]]
    for section in sections:
        boundaries.append(section["end"])

    duration = float(sections[-1]["end"])
    labels = ", ".join(f"{s['label']} {s['start']:.1f}-{s['end']:.1f}s" for s in sections)
    print(
        f"[Structure] source=allin1 analyzed_duration_s={duration:.2f} "
        f"sections={len(sections)} bpm={getattr(result, 'bpm', None)}"
    )
    print(f"[Structure] allin1 labels: {labels}")

    return {
        "sections": sections,
        "boundaries": boundaries,
        "source": "allin1",
        "analyzed_duration_s": duration,
    }
