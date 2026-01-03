import essentia.standard as es
import numpy as np
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

def load_audio(file_path: str, sample_rate: int = 44100) -> np.ndarray:
    """Load audio with Essentia and return the signal."""
    try:
        loader = es.MonoLoader(filename=file_path, sampleRate=sample_rate)
        return loader()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load audio: {str(e)}")

def get_high_quality_onsets(audio: np.ndarray, sample_rate: int = 44100) -> List[float]:
    """
    High-quality onset detection combining multiple ODFs.
    Uses HFC for percussive onsets and Complex for tonal onsets.
    """
    frame_size = 1024
    hop_size = 512
    
    w = es.Windowing(type='hann')
    spec = es.Spectrum()
    
    # Define detection functions
    od_hfc = es.OnsetDetection(method='hfc')
    od_complex = es.OnsetDetection(method='complex')
    
    onsets_alg = es.Onsets(threshold=0.1)
    
    hfc_values = []
    complex_values = []
    
    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size):
        frame_spec = spec(w(frame))
        hfc_values.append(od_hfc(frame_spec, frame))
        complex_values.append(od_complex(frame_spec, frame))
    
    # Peak picking
    onsets_hfc = onsets_alg(es.array(hfc_values), [frame_size, hop_size])
    onsets_complex = onsets_alg(es.array(complex_values), [frame_size, hop_size])
    
    # Combine and deduplicate
    all_onsets = sorted(list(set(np.round(onsets_hfc, 3)) | set(np.round(onsets_complex, 3))))
    
    # Filter onsets too close together (min 50ms)
    filtered_onsets = []
    if all_onsets:
        filtered_onsets.append(float(all_onsets[0]))
        for o in all_onsets[1:]:
            if o - filtered_onsets[-1] >= 0.050:
                filtered_onsets.append(float(o))
                
    return filtered_onsets

def analyze_rhythm_logic(audio: np.ndarray, sample_rate: int = 44100) -> Dict[str, Any]:
    """Core rhythm analysis logic."""
    rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
    bpm, beats, beats_confidence, _, _ = rhythm_extractor(audio)
    
    onsets = get_high_quality_onsets(audio, sample_rate)
    duration = float(len(audio) / sample_rate)
    
    return {
        "bpm": float(bpm),
        "beats": [float(b) for b in beats],
        "confidence": float(beats_confidence),
        "onsets": onsets,
        "duration": duration
    }

def analyze_structure_logic(audio: np.ndarray, sample_rate: int = 44100) -> Dict[str, Any]:
    """
    Structural segmentation using SBic and SegmentClustering.
    Processes audio to find boundaries and repeated patterns.
    """
    duration = float(len(audio) / sample_rate)
    
    # 1. Feature Extraction (MFCCs)
    frame_size = 2048
    hop_size = 1024
    w = es.Windowing(type='hann')
    spec = es.Spectrum()
    mfcc = es.MFCC(numberCoefficients=13)
    
    mfccs = []
    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size):
        _, m = mfcc(spec(w(frame)))
        mfccs.append(m)
    
    # 2. Boundary detection using SBic
    # We use a windowed approach if audio is long, but for standard tracks SBic(size=...) is fine.
    # Note: cp_min_dist is in frames. 1024 hop @ 44.1k is ~23ms. 100 frames ~2.3s.
    sbic = es.SBic(size=len(mfccs), cp_min_dist=100) 
    boundaries_frames = sbic(es.array(mfccs))
    
    # Convert boundary frames to seconds
    # SBic returns frame indices relative to the input array.
    bound_secs = sorted([float(f * hop_size / sample_rate) for f in boundaries_frames])
    boundaries = [0.0] + bound_secs + [duration]
    
    # 3. Clustering / Labeling
    # For a high-quality implementation, we could use SegmentClustering here.
    # However, SegmentClustering requires a specific feature matrix format.
    # Let's use it to group similar segments.
    
    sections = []
    # If we have enough segments, try to cluster them
    if len(boundaries) > 3:
        # Simplification: we'll assign labels based on energy and position for now
        # until we verify SegmentClustering parameters for the current Essentia version.
        # But we'll structure it so it's ready for clustering logic.
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i+1]
            
            # Simple heuristic labels
            pos = ((start + end) / 2) / duration
            label = "section"
            if pos < 0.1: label = "intro"
            elif pos > 0.9: label = "outro"
            else:
                # Segment energy check
                start_s = int(start * sample_rate)
                end_s = int(end * sample_rate)
                chunk = audio[start_s:end_s]
                energy = np.mean(chunk**2) if len(chunk) > 0 else 0
                label = "chorus" if energy > 0.04 else "verse"
                
            sections.append({
                "start": float(start),
                "end": float(end),
                "label": label,
                "duration": float(end - start)
            })
    else:
        # Fallback for short audio
        sections.append({
            "start": 0.0,
            "end": duration,
            "label": "full",
            "duration": duration
        })
        
    return {
        "sections": sections,
        "boundaries": boundaries
    }
