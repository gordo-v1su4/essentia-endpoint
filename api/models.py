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

class ClassificationResult(BaseModel):
    label: str
    confidence: float
    all_scores: Dict[str, float]

class ClassificationAnalysis(BaseModel):
    genres: ClassificationResult
    moods: ClassificationResult
    tags: List[str]

class TonalAnalysis(BaseModel):
    key: str
    scale: str
    strength: float

class FullAnalysis(RhythmAnalysis):
    structure: StructureAnalysis
    classification: Optional[ClassificationAnalysis] = None
    tonal: Optional[TonalAnalysis] = None
