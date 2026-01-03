from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class Section(BaseModel):
    start: float
    end: float
    label: str
    duration: float

class RhythmAnalysis(BaseModel):
    bpm: float
    beats: List[float]
    confidence: float
    onsets: List[float]
    duration: float

class StructureAnalysis(BaseModel):
    sections: List[Section]
    boundaries: List[float]

class FullAnalysis(RhythmAnalysis):
    structure: StructureAnalysis
