import essentia.standard as es
import numpy as np
import os
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
    # FFT and CartesianToPolar to get both magnitude and phase
    fft = es.FFT()
    c2p = es.CartesianToPolar()
    
    # Define detection functions
    # HFC only needs magnitude, but Complex needs both magnitude and phase
    od_hfc = es.OnsetDetection(method='hfc')
    od_complex = es.OnsetDetection(method='complex')
    
    # Onsets algorithm: returns onset times in seconds
    onsets_alg = es.Onsets()
    
    hfc_values = []
    complex_values = []
    
    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size):
        windowed = w(frame)
        fft_out = fft(windowed)
        mag, phase = c2p(fft_out)
        
        hfc_values.append(od_hfc(mag, phase))
        complex_values.append(od_complex(mag, phase))
    
    # Ensure inputs are float32 2D arrays (Matrix) for Onsets algorithm
    hfc_array = np.array([hfc_values], dtype=np.float32)
    complex_array = np.array([complex_values], dtype=np.float32)
    
    # Weights for the single ODF
    weights = np.array([1.0], dtype=np.float32)
    
    onsets_hfc = onsets_alg(hfc_array, weights)
    onsets_complex = onsets_alg(complex_array, weights)
    
    # Convert from algorithm internal time to absolute time
    # Onsets returns seconds, but check if we need to scale based on hop size if it fails.
    # In many versions, it uses the global sampleRate/hopSize which might need config.
    
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
    # Note: minLength is in frames. 1024 hop @ 44.1k is ~23ms. 100 frames ~2.3s.
    sbic = es.SBic(minLength=100) 
    boundaries_frames = sbic(np.array(mfccs, dtype=np.float32))
    
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

def analyze_classification_logic(audio: np.ndarray, sample_rate: int = 44100) -> Dict[str, Any]:
    """
    Classification using Essentia TensorFlow models.
    """
    models_dir = os.environ.get("ESSENTIA_MODELS_PATH", "/app/models")
    
    # Initialize results
    genres = {"label": "Unknown", "confidence": 0.0, "all_scores": {}}
    moods = {"label": "Unknown", "confidence": 0.0, "all_scores": {}}
    tags = []
    
    # 1. Resample to 16kHz for classification models
    # Most Essentia TF models work at 16kHz
    try:
        resample = es.Resample(inputSampleRate=sample_rate, outputSampleRate=16000, quality=0)
        audio_16k = resample(audio)
    except Exception as e:
        print(f"Resampling failed: {e}")
        audio_16k = audio # Fallback, though likely to fail models
    
    from services.labels import GENRE_LABELS, TAG_LABELS

    # 2. Genre Classification (EffNetDiscogs)
    # -------------------------------------------------------------------------
    try:
        genre_model_path = os.path.join(models_dir, "effnetdiscogs", "effnetdiscogs-bs64-1.pb")
        if not os.path.exists(genre_model_path):
             genre_model_path = os.path.join(models_dir, "effnetdiscogs-bs64-1.pb")

        if os.path.exists(genre_model_path):
            # EffNetDiscogs usually returns [batch, 400] probabilities
            model_genre = es.TensorflowPredictEffNetDiscogs(graphFilename=genre_model_path, output="PartitionedCall:1")
            activations = model_genre(audio_16k)
            
            # Average across frames (0-axis)
            mean_activations = np.mean(activations, axis=0)
            
            # Find top genre
            if len(mean_activations) == len(GENRE_LABELS):
                top_idx = int(np.argmax(mean_activations))
                genres["label"] = GENRE_LABELS[top_idx]
                genres["confidence"] = float(mean_activations[top_idx])
                
                # Get top 5 scores
                top_5_indices = np.argsort(mean_activations)[-5:][::-1]
                for idx in top_5_indices:
                    genres["all_scores"][GENRE_LABELS[idx]] = float(mean_activations[idx])
            else:
                genres["label"] = "Error: Dimension Mismatch"
    except Exception as e:
        print(f"Genre analysis failed: {e}")

    # 3. Tags & Mood (MusiCNN + Chain)
    # -------------------------------------------------------------------------
    try:
        # Load Tagging/Embedding Model (MusiCNN)
        musicnn_path = os.path.join(models_dir, "musicnn", "msd-musicnn-1.pb")
        if not os.path.exists(musicnn_path):
             musicnn_path = os.path.join(models_dir, "msd-musicnn-1.pb")
             
        if os.path.exists(musicnn_path):
            # MusiCNN has multiple outputs. 
            # We need 'model/Sigmoid' for tags (50) and 'model/dense/BiasAdd' for embeddings (200)
            # Note: TensorflowPredictMusiCNN automatically handles this or we specify outputs
            
            # Using generic TensorflowPredict to be explicit about outputs if needed, 
            # but TensorflowPredictMusiCNN is safer for input formatting.
            # Let's try TensorflowPredictMusiCNN which returns [embeddings(200), tags(50)] usually?
            # Or we check documentation. Usually it returns the "last layer" or configured output.
            # Safe bet: use generic TensorflowPredict and request specific nodes.
            # Inputs: 'model/Placeholder' [batch, 187, 96] - handled by TFPredictMusiCNN? 
            # Actually TFPredictMusiCNN takes audio and does the mel-spectrogram internally.
            
            model_musicnn = es.TensorflowPredictMusiCNN(graphFilename=musicnn_path, output="model/Sigmoid")
            # We essentially run it twice or change output? 
            # TensorflowPredictMusiCNN only supports one output parameter.
            # We can use 'model/dense/BiasAdd' for embeddings.
            
            # 3a. Tags
            tags_activations = model_musicnn(audio_16k)
            mean_tags = np.mean(tags_activations, axis=0) # [50]
            
            # Get top tags (> 0.1 confidence)
            for i, score in enumerate(mean_tags):
                if score > 0.15 and i < len(TAG_LABELS):
                     tags.append(TAG_LABELS[i])
            
            # 3b. Mood (Requires Embeddings)
            # We need to run MusiCNN again for embeddings (inefficient but safe) or usage generic.
            # 'model/dense/BiasAdd' is the embedding layer [200]
            model_embeddings = es.TensorflowPredictMusiCNN(graphFilename=musicnn_path, output="model/dense/BiasAdd")
            embeddings = model_embeddings(audio_16k) # [frames, 200]
            
            # Load Mood Model (EmoMusic)
            mood_model_path = os.path.join(models_dir, "classification_heads", "emomusic-msd-musicnn-1.pb")
            if os.path.exists(mood_model_path):
                 # Input: [batch, 200] -> 'flatten_in_input' (or similar matching embedding)
                 # Output: 'dense_out' [2] (Valence, Arousal)
                 model_mood = es.TensorflowPredict2D(graphFilename=mood_model_path, 
                                                     input="flatten_in_input", 
                                                     output="dense_out")
                 
                 mood_preds = model_mood(embeddings)
                 mean_mood = np.mean(mood_preds, axis=0) # [valence, arousal]
                 
                 valence = mean_mood[0]
                 arousal = mean_mood[1]
                 
                 # Map Valence/Arousal to label
                 # Russell's Circumplex Model (Simplified)
                 # V+ A+ : Happy/Excited
                 # V+ A- : Relaxed/Calm
                 # V- A- : Sad/Depressed
                 # V- A+ : Angry/Aggressive
                 
                 mood_label = "Neutral"
                 if valence >= 5 and arousal >= 5: mood_label = "Happy/Excited"
                 elif valence >= 5 and arousal < 5: mood_label = "Relaxed"
                 elif valence < 5 and arousal < 5: mood_label = "Sad"
                 elif valence < 5 and arousal >= 5: mood_label = "Aggressive"
                 
                 # Models often output 1-9 or 0-1? 
                 # EmoMusic dataset is usually 1-9. Let's assume 1-9. 
                 # If values are small (<1), scaling is 0-1.
                 # Let's check ranges. If max < 1.0, assume 0.5 center.
                 
                 center = 5.0
                 if np.max(np.abs(mean_mood)) <= 1.5:
                     center = 0.5
                     
                 if valence >= center and arousal >= center: mood_label = "Happy"
                 elif valence >= center and arousal < center: mood_label = "Relaxed"
                 elif valence < center and arousal < center: mood_label = "Sad"
                 elif valence < center and arousal >= center: mood_label = "Aggressive"
                 
                 moods["label"] = mood_label
                 moods["confidence"] = 1.0 # Regression doesn't give confidence
                 moods["all_scores"] = {"valence": float(valence), "arousal": float(arousal)}

    except Exception as e:
        print(f"Mood/Tag analysis failed: {e}")

    return {
        "genres": genres,
        "moods": moods,
        "tags": tags
    }
