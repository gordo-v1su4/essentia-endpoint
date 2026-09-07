"""Versioned, minimal editor analysis and durable job responses."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StudioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StudioEnergy(StudioModel):
    curve: list[float]
    sample_rate_hz: float = Field(gt=0)
    start_time_s: float = Field(ge=0)


class StudioSection(StudioModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    duration: float = Field(gt=0)
    label: str
    original_label: str
    energy: float = Field(ge=0, le=1)


class StudioProvenance(StudioModel):
    status: Literal["detected"]
    method: str
    device: Literal["cuda"]


class StudioStructure(StudioModel):
    sections: list[StudioSection]
    boundaries: list[float]
    source: Literal["allin1"]
    analyzed_duration_s: float = Field(gt=0)
    provenance: StudioProvenance


class StudioAnalysis(StudioModel):
    schema_version: Literal["studio-audio-v1"]
    duration: float = Field(gt=0)
    bpm: float = Field(gt=0)
    beats: list[float]
    confidence: float = Field(ge=0)
    onsets: list[float]
    energy: StudioEnergy
    structure: StudioStructure


class StudioJobError(StudioModel):
    code: str
    message: str


class StudioJobResponse(StudioModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    result: StudioAnalysis | None = None
    error: StudioJobError | None = None
