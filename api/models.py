from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class Section(BaseModel):
    start: float
    end: float
    label: str
    duration: float
    energy: float

class EnergyData(BaseModel):
    mean: float
    std: float
    curve: List[float]

class RhythmAnalysis(BaseModel):
    bpm: float
    beats: List[float]
    confidence: float
    onsets: List[float]
    duration: float
    energy: EnergyData

class StructureAnalysis(BaseModel):
    sections: List[Section]
    boundaries: List[float]

class ClassificationResult(BaseModel):
    label: str
    confidence: float
    all_scores: Dict[str, float]

class ClassificationFeature(BaseModel):
    label: str
    confidence: float

class ClassificationAnalysis(BaseModel):
    genres: Optional[ClassificationResult] = None
    moods: Optional[ClassificationResult] = None
    tags: Optional[List[str]] = None
    danceability: Optional[ClassificationFeature] = None
    approachability: Optional[ClassificationFeature] = None
    engagement: Optional[ClassificationFeature] = None
    acoustic_electronic: Optional[ClassificationFeature] = None
    bright_dark: Optional[ClassificationFeature] = None
    instrument: Optional[List[ClassificationFeature]] = None
    tonal_atonal: Optional[ClassificationFeature] = None

class TonalAnalysis(BaseModel):
    key: str
    scale: str
    strength: float

class PitchData(BaseModel):
    mean_frequency: float
    confidence: float

class EnhancedTonalAnalysis(BaseModel):
    key: str
    scale: str
    strength: float
    tempo_cnn: Optional[float] = None
    pitch: Optional[PitchData] = None

class VocalAnalysis(BaseModel):
    is_vocal: bool
    confidence: float
    label: str

class FullAnalysis(RhythmAnalysis):
    structure: StructureAnalysis
    classification: Optional[ClassificationAnalysis] = None
    tonal: Optional[EnhancedTonalAnalysis] = None
    vocals: Optional[VocalAnalysis] = None
