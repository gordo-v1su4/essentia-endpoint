# Silence TensorFlow GPU/NUMA logs before essentia (which loads TF)
import os
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import essentia.standard as es
import numpy as np
from typing import List, Dict, Any, Optional, Set
from fastapi import HTTPException
import math


def _find_model(base_dir: str, filename: str) -> Optional[str]:
    """
    Find a model .pb file, checking both flat and subdirectory layouts.
    The essentia-models repo organizes classification heads in subdirs:
      classification_heads/danceability/danceability-discogs-effnet-1.pb
    But we also support flat layout:
      classification_heads/danceability-discogs-effnet-1.pb
    """
    # 1. Flat: base_dir/filename
    flat = os.path.join(base_dir, filename)
    if os.path.exists(flat):
        return flat

    # 2. Subdirectory: base_dir/{task_name}/filename
    #    e.g. "danceability-discogs-effnet-1.pb" -> subdir "danceability"
    #    e.g. "emomusic-msd-musicnn-1.pb" -> subdir "emomusic"
    #    e.g. "approachability_regression-discogs-effnet-1.pb" -> subdir "approachability"
    #    e.g. "nsynth_acoustic_electronic-discogs-effnet-1.pb" -> subdir "nsynth_acoustic_electronic"
    # Strategy: try progressively shorter prefixes split on '-'
    parts = filename.replace(".pb", "").split("-")
    for i in range(len(parts) - 1, 0, -1):
        subdir = "-".join(parts[:i])
        candidate = os.path.join(base_dir, subdir, filename)
        if os.path.exists(candidate):
            return candidate
        # Also try underscore variant (approachability_regression -> approachability)
        subdir_short = subdir.split("_")[0]
        if subdir_short != subdir:
            candidate = os.path.join(base_dir, subdir_short, filename)
            if os.path.exists(candidate):
                return candidate

    # 3. Brute-force walk (last resort for odd layouts)
    if os.path.isdir(base_dir):
        for root, _dirs, files in os.walk(base_dir):
            if filename in files:
                return os.path.join(root, filename)

    return None


def load_audio(file_path: str, sample_rate: int = 44100) -> np.ndarray:
    """Load audio with Essentia and return the signal."""
    try:
        loader = es.MonoLoader(filename=file_path, sampleRate=sample_rate)
        return loader()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load audio: {str(e)}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert to float and clamp non-finite values to a safe default."""
    try:
        f = float(value)
        if math.isfinite(f):
            return f
    except Exception:
        pass
    return default

def get_high_quality_onsets(audio: np.ndarray, sample_rate: int = 44100) -> List[float]:
    """
    High-quality onset detection combining multiple ODFs.
    Uses HFC for percussive onsets and Complex for tonal onsets.
    """
    frame_size = 1024
    hop_size = 512

    w = es.Windowing(type='hann')
    fft = es.FFT()
    c2p = es.CartesianToPolar()

    od_hfc = es.OnsetDetection(method='hfc')
    od_complex = es.OnsetDetection(method='complex')

    onsets_alg = es.Onsets()

    hfc_values = []
    complex_values = []

    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size):
        windowed = w(frame)
        fft_out = fft(windowed)
        mag, phase = c2p(fft_out)

        hfc_values.append(od_hfc(mag, phase))
        complex_values.append(od_complex(mag, phase))

    hfc_array = np.array([hfc_values], dtype=np.float32)
    complex_array = np.array([complex_values], dtype=np.float32)

    weights = np.array([1.0], dtype=np.float32)

    onsets_hfc = onsets_alg(hfc_array, weights)
    onsets_complex = onsets_alg(complex_array, weights)

    all_onsets = sorted(list(set(np.round(onsets_hfc, 3)) | set(np.round(onsets_complex, 3))))

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

    frame_size = 1024
    hop_size = 512
    rms_frames = es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size)
    rms = es.RMS()
    rms_curve = []

    for frame in rms_frames:
        rms_val = rms(frame)
        rms_curve.append(_safe_float(rms_val))

    if rms_curve:
        max_rms = max(rms_curve)
        if max_rms > 0:
            rms_curve = [_safe_float(val / max_rms) for val in rms_curve]

    energy_analyzer = es.Energy()
    energy = energy_analyzer(audio)
    energy_mean = _safe_float(np.mean(energy) if hasattr(energy, '__len__') else energy)
    energy_std = _safe_float(np.std(energy) if hasattr(energy, '__len__') and len(energy) > 1 else 0.0)

    return {
        "bpm": _safe_float(bpm),
        "beats": [_safe_float(b) for b in beats],
        "confidence": _safe_float(beats_confidence),
        "onsets": [_safe_float(o) for o in onsets],
        "duration": _safe_float(duration),
        "energy": {
            "mean": energy_mean,
            "std": energy_std,
            "curve": rms_curve
        }
    }

def generate_fallback_boundaries(duration: float) -> List[float]:
    """
    Generate fallback section boundaries when SBic fails.
    Creates reasonable sections based on typical song structure.
    """
    boundaries = [0.0]

    intro_end = min(duration * 0.10, 15.0)
    if intro_end > 5:
        boundaries.append(intro_end)

    main_start = boundaries[-1]
    outro_start = duration - min(duration * 0.15, 20.0)
    main_duration = outro_start - main_start

    if main_duration > 20:
        num_sections = max(2, int(main_duration / 30))
        section_duration = main_duration / num_sections

        for i in range(1, num_sections):
            boundaries.append(main_start + i * section_duration)

    if duration - outro_start > 5:
        boundaries.append(outro_start)

    boundaries.append(duration)
    return boundaries

def analyze_structure_logic(audio: np.ndarray, sample_rate: int = 44100) -> Dict[str, Any]:
    """
    Structural segmentation using SBic and SegmentClustering.
    Processes audio to find boundaries and repeated patterns.
    """
    duration = float(len(audio) / sample_rate)

    frame_size = 2048
    hop_size = 1024
    w = es.Windowing(type='hann')
    spec = es.Spectrum()
    mfcc = es.MFCC(numberCoefficients=13)

    mfccs = []
    for frame in es.FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size):
        _, m = mfcc(spec(w(frame)))
        mfccs.append(m)

    min_frames = 300

    if len(mfccs) < min_frames * 2:
        print(f"[Structure] Audio too short ({len(mfccs)} frames), using fallback")
        boundaries_frames = []
    else:
        try:
            sbic = es.SBic(minLength=min_frames, cpw=1.5, size1=300, inc1=60, size2=200, inc2=40)
            boundaries_frames = sbic(np.array(mfccs, dtype=np.float32))
            print(f"[Structure] SBic found {len(boundaries_frames)} boundaries: {boundaries_frames}")
        except Exception as e:
            print(f"[Structure] SBic failed: {e}, using fallback")
            boundaries_frames = []

    bound_secs = sorted([float(f * hop_size / sample_rate) for f in boundaries_frames])

    filtered_bounds = []
    for b in bound_secs:
        if b > 2.0 and b < (duration - 2.0):
            if not filtered_bounds or (b - filtered_bounds[-1]) >= 5.0:
                filtered_bounds.append(b)

    boundaries = [0.0] + filtered_bounds + [duration]

    if len(boundaries) <= 2:
        print(f"[Structure] No boundaries found, generating fallback sections for {duration}s track")
        boundaries = generate_fallback_boundaries(duration)

    sections = []
    if len(boundaries) > 2:
        segment_data = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i+1]
            start_s = int(start * sample_rate)
            end_s = int(end * sample_rate)
            chunk = audio[start_s:end_s]

            if len(chunk) > 0:
                energy = _safe_float(np.mean(chunk**2))
            else:
                energy = 0.0

            segment_data.append({
                "start": _safe_float(start),
                "end": _safe_float(end),
                "energy": energy,
                "pos": _safe_float(((start + end) / 2) / duration)
            })

        avg_energy = np.mean([s["energy"] for s in segment_data]) if segment_data else 0
        num_segments = len(segment_data)

        verse_count = 0
        chorus_count = 0

        for i, s in enumerate(segment_data):
            label = "section"

            if i == 0 and s["pos"] < 0.15:
                label = "intro"
            elif i == num_segments - 1 and s["pos"] > 0.80:
                label = "outro"
            elif 0.5 <= s["pos"] <= 0.75 and num_segments >= 5:
                if abs(s["energy"] - avg_energy) < avg_energy * 0.2:
                    label = "bridge"
                elif s["energy"] > avg_energy * 1.1:
                    label = "chorus"
                    chorus_count += 1
                else:
                    label = "verse"
                    verse_count += 1
            else:
                if s["energy"] > avg_energy * 1.1:
                    label = "chorus"
                    chorus_count += 1
                else:
                    label = "verse"
                    verse_count += 1

            sections.append({
                "start": s["start"],
                "end": s["end"],
                "label": label,
                "duration": _safe_float(s["end"] - s["start"]),
                "energy": _safe_float(s["energy"])
            })

        print(f"[Structure] Labeled {num_segments} sections: {verse_count} verse, {chorus_count} chorus")
    else:
        sections.append({
            "start": 0.0,
            "end": duration,
            "label": "full",
            "duration": duration,
            "energy": 0.0
        })

    return {
        "sections": sections,
        "boundaries": boundaries
    }


# ---------------------------------------------------------------------------
# Shared embedding extraction helpers
# ---------------------------------------------------------------------------

ALL_CLASSIFICATION_FEATURES = {
    "genre", "mood", "tags", "danceability", "approachability", "engagement",
    "acoustic_electronic", "bright_dark", "instrument", "tonal_atonal",
}

def _get_effnet_embeddings(audio_16k: np.ndarray, models_dir: str):
    """Extract EffNet embeddings (used by genre + several classification heads)."""
    genre_model_path = os.path.join(models_dir, "discogs-effnet", "discogs-effnet-bs64-1.pb")
    if not os.path.exists(genre_model_path):
        # Fallback to old naming convention
        genre_model_path = os.path.join(models_dir, "effnetdiscogs", "effnetdiscogs-bs64-1.pb")
    if not os.path.exists(genre_model_path):
        genre_model_path = os.path.join(models_dir, "discogs-effnet-bs64-1.pb")

    if not os.path.exists(genre_model_path) or not hasattr(es, 'TensorflowPredictEffnetDiscogs'):
        return None, None

    # Full activations (genre predictions)
    model_genre = es.TensorflowPredictEffnetDiscogs(
        graphFilename=genre_model_path, output="PartitionedCall:1"
    )
    activations = model_genre(audio_16k)

    # Embeddings for classification heads
    model_embed = es.TensorflowPredictEffnetDiscogs(
        graphFilename=genre_model_path, output="PartitionedCall:0"
    )
    embeddings = model_embed(audio_16k)

    return activations, embeddings


def _get_musicnn_embeddings(audio_16k: np.ndarray, models_dir: str):
    """Extract MusiCNN tag activations and embeddings."""
    musicnn_path = os.path.join(models_dir, "musicnn", "msd-musicnn-1.pb")
    if not os.path.exists(musicnn_path):
        musicnn_path = os.path.join(models_dir, "msd-musicnn-1.pb")

    if not os.path.exists(musicnn_path) or not hasattr(es, 'TensorflowPredictMusiCNN'):
        return None, None

    model_tags = es.TensorflowPredictMusiCNN(
        graphFilename=musicnn_path, output="model/Sigmoid"
    )
    tag_activations = model_tags(audio_16k)

    model_embed = es.TensorflowPredictMusiCNN(
        graphFilename=musicnn_path, output="model/dense/BiasAdd"
    )
    embeddings = model_embed(audio_16k)

    return tag_activations, embeddings


def _run_classification_head(embeddings, model_path: Optional[str], input_name: str = "flatten_in_input",
                             output_name: str = "dense_out") -> Optional[np.ndarray]:
    """Run a TensorflowPredict2D classification head on embeddings."""
    if embeddings is None or model_path is None or not os.path.exists(model_path):
        return None
    if not hasattr(es, 'TensorflowPredict2D'):
        return None
    # Different model exports can use different input/output node names.
    # Try known pairs in order.
    candidates = [
        (input_name, output_name),
        ("model/Placeholder", "model/Softmax"),
        ("model/Placeholder", "model/dense_1/BiasAdd"),
    ]
    seen = set()
    last_error = None
    for in_name, out_name in candidates:
        key = (in_name, out_name)
        if key in seen:
            continue
        seen.add(key)
        try:
            model = es.TensorflowPredict2D(
                graphFilename=model_path, input=in_name, output=out_name
            )
            return model(embeddings)
        except Exception as e:
            last_error = e

    print(f"Classification head failed ({model_path}): {last_error}")
    return None


def _binary_classification(embeddings, model_path: str, pos_label: str, neg_label: str,
                           input_name: str = "flatten_in_input",
                           output_name: str = "dense_out") -> Optional[Dict[str, Any]]:
    """Run a binary classification head and return {label, confidence}."""
    preds = _run_classification_head(embeddings, model_path, input_name, output_name)
    if preds is None:
        return None
    mean_pred = float(np.mean(preds))
    mean_pred = _safe_float(mean_pred)
    if mean_pred >= 0.5:
        return {"label": pos_label, "confidence": mean_pred}
    else:
        return {"label": neg_label, "confidence": 1.0 - mean_pred}


# ---------------------------------------------------------------------------
# Classification logic (supports selectable features)
# ---------------------------------------------------------------------------

def analyze_classification_logic(audio: np.ndarray, sample_rate: int = 44100,
                                 features: Optional[Set[str]] = None) -> Dict[str, Any]:
    """
    Classification using Essentia TensorFlow models.
    `features` controls which classification heads to run. None or empty = all.
    """
    if not features:
        features = ALL_CLASSIFICATION_FEATURES

    models_dir = os.environ.get("ESSENTIA_MODELS_PATH", "/app/models")
    heads_dir = os.path.join(models_dir, "classification_heads")
    result: Dict[str, Any] = {}

    # Resample once
    try:
        resample = es.Resample(inputSampleRate=sample_rate, outputSampleRate=16000, quality=0)
        audio_16k = resample(audio)
    except Exception as e:
        print(f"Resampling failed: {e}")
        audio_16k = audio

    from services.labels import GENRE_LABELS, TAG_LABELS, INSTRUMENT_LABELS

    # Extract embeddings only when needed
    need_effnet = features & {"genre", "danceability", "approachability", "engagement",
                              "acoustic_electronic", "bright_dark", "instrument", "tonal_atonal"}
    need_musicnn = features & {"mood", "tags"}

    effnet_activations, effnet_embeddings = (None, None)
    musicnn_activations, musicnn_embeddings = (None, None)

    if need_effnet:
        try:
            effnet_activations, effnet_embeddings = _get_effnet_embeddings(audio_16k, models_dir)
        except Exception as e:
            print(f"EffNet embedding extraction failed: {e}")

    if need_musicnn:
        try:
            musicnn_activations, musicnn_embeddings = _get_musicnn_embeddings(audio_16k, models_dir)
        except Exception as e:
            print(f"MusiCNN embedding extraction failed: {e}")

    # --- Genre ---
    if "genre" in features:
        genres = {"label": "Unknown", "confidence": 0.0, "all_scores": {}}
        if effnet_activations is not None:
            mean_act = np.mean(effnet_activations, axis=0)
            if len(mean_act) == len(GENRE_LABELS):
                top_idx = int(np.argmax(mean_act))
                genres["label"] = GENRE_LABELS[top_idx]
                genres["confidence"] = float(mean_act[top_idx])
                for idx in np.argsort(mean_act)[-5:][::-1]:
                    genres["all_scores"][GENRE_LABELS[idx]] = float(mean_act[idx])
        result["genres"] = genres

    # --- Tags ---
    if "tags" in features:
        tags: List[str] = []
        if musicnn_activations is not None:
            mean_tags = np.mean(musicnn_activations, axis=0)
            for i, score in enumerate(mean_tags):
                if score > 0.15 and i < len(TAG_LABELS):
                    tags.append(TAG_LABELS[i])
        result["tags"] = tags

    # --- Mood ---
    if "mood" in features:
        moods = {"label": "Unknown", "confidence": 0.0, "all_scores": {}}
        if musicnn_embeddings is not None:
            mood_model_path = _find_model(heads_dir, "emomusic-msd-musicnn-1.pb")
            mood_preds = _run_classification_head(musicnn_embeddings, mood_model_path)
            if mood_preds is not None:
                mean_mood = np.mean(mood_preds, axis=0)
                valence = mean_mood[0]
                arousal = mean_mood[1]
                center = 5.0
                if np.max(np.abs(mean_mood)) <= 1.5:
                    center = 0.5
                if valence >= center and arousal >= center:
                    mood_label = "Happy"
                elif valence >= center and arousal < center:
                    mood_label = "Relaxed"
                elif valence < center and arousal < center:
                    mood_label = "Sad"
                else:
                    mood_label = "Aggressive"
                moods["label"] = mood_label
                moods["confidence"] = 1.0
                moods["all_scores"] = {"valence": _safe_float(valence), "arousal": _safe_float(arousal)}
        result["moods"] = moods

    # --- Danceability ---
    if "danceability" in features:
        path = _find_model(heads_dir, "danceability-discogs-effnet-1.pb")
        res = _binary_classification(effnet_embeddings, path, "Danceable", "Not Danceable")
        result["danceability"] = res

    # --- Approachability ---
    if "approachability" in features:
        path = _find_model(heads_dir, "approachability_regression-discogs-effnet-1.pb")
        preds = _run_classification_head(effnet_embeddings, path)
        if preds is not None:
            score = float(np.mean(preds))
            score = _safe_float(score)
            label = "Approachable" if score >= 0.5 else "Not Approachable"
            result["approachability"] = {"label": label, "confidence": score if score >= 0.5 else 1.0 - score}
        else:
            result["approachability"] = None

    # --- Engagement ---
    if "engagement" in features:
        path = _find_model(heads_dir, "engagement_regression-discogs-effnet-1.pb")
        preds = _run_classification_head(effnet_embeddings, path)
        if preds is not None:
            score = float(np.mean(preds))
            score = _safe_float(score)
            label = "Engaging" if score >= 0.5 else "Not Engaging"
            result["engagement"] = {"label": label, "confidence": score if score >= 0.5 else 1.0 - score}
        else:
            result["engagement"] = None

    # --- Acoustic/Electronic ---
    if "acoustic_electronic" in features:
        path = _find_model(heads_dir, "nsynth_acoustic_electronic-discogs-effnet-1.pb")
        res = _binary_classification(effnet_embeddings, path, "Electronic", "Acoustic")
        result["acoustic_electronic"] = res

    # --- Bright/Dark ---
    if "bright_dark" in features:
        path = _find_model(heads_dir, "nsynth_bright_dark-discogs-effnet-1.pb")
        res = _binary_classification(effnet_embeddings, path, "Bright", "Dark")
        result["bright_dark"] = res

    # --- Instrument ---
    if "instrument" in features:
        path = _find_model(heads_dir, "mtg_jamendo_instrument-discogs-effnet-1.pb")
        preds = _run_classification_head(effnet_embeddings, path)
        if preds is not None:
            mean_preds = np.mean(preds, axis=0)
            instruments = []
            for i, score in enumerate(mean_preds):
                if score > 0.15 and i < len(INSTRUMENT_LABELS):
                    instruments.append({"label": INSTRUMENT_LABELS[i], "confidence": float(score)})
                    instruments[-1]["confidence"] = _safe_float(instruments[-1]["confidence"])
            instruments.sort(key=lambda x: x["confidence"], reverse=True)
            result["instrument"] = instruments
        else:
            result["instrument"] = None

    # --- Tonal/Atonal ---
    if "tonal_atonal" in features:
        path = _find_model(heads_dir, "tonal_atonal-discogs-effnet-1.pb")
        res = _binary_classification(effnet_embeddings, path, "Tonal", "Atonal")
        result["tonal_atonal"] = res

    return result


# ---------------------------------------------------------------------------
# Vocal analysis
# ---------------------------------------------------------------------------

def analyze_vocals_logic(audio: np.ndarray, sample_rate: int = 44100) -> Dict[str, Any]:
    """Detect vocal presence using voice_instrumental classification head with EffNet embeddings.
    Returns vocal_presence as a continuous 0-1 score (0=instrumental, 1=vocals)."""
    models_dir = os.environ.get("ESSENTIA_MODELS_PATH", "/app/models")
    heads_dir = os.path.join(models_dir, "classification_heads")

    try:
        resample = es.Resample(inputSampleRate=sample_rate, outputSampleRate=16000, quality=0)
        audio_16k = resample(audio)
    except Exception as e:
        print(f"Resampling failed: {e}")
        return {"vocal_presence": 0.0, "label": "Unknown"}

    _, effnet_embeddings = _get_effnet_embeddings(audio_16k, models_dir)

    path = _find_model(heads_dir, "voice_instrumental-discogs-effnet-1.pb")
    preds = _run_classification_head(effnet_embeddings, path)

    if preds is not None:
        # Raw score: 0.0 = instrumental, 1.0 = vocals
        preds_arr = np.asarray(preds)
        if preds_arr.ndim >= 2 and preds_arr.shape[-1] == 2:
            # Softmax binary heads typically return [instrumental, voice]
            vocal_scores = preds_arr[..., 1]
        else:
            vocal_scores = preds_arr
        vocal_presence = _safe_float(np.mean(vocal_scores))
        if vocal_presence >= 0.5:
            label = "Voice"
        else:
            label = "Instrumental"
        return {
            "vocal_presence": _safe_float(round(vocal_presence, 4)),
            "label": label,
        }

    return {"vocal_presence": 0.0, "label": "Unknown"}


# ---------------------------------------------------------------------------
# Enhanced tonal analysis
# ---------------------------------------------------------------------------

def analyze_tonal_key_logic(audio: np.ndarray, sample_rate: int = 44100) -> Dict[str, Any]:
    """Extract key/scale/strength only."""
    try:
        key_extractor = es.KeyExtractor()
        results = key_extractor(audio)
        return {
            "key": results[0],
            "scale": results[1],
            "strength": _safe_float(results[2]),
        }
    except Exception as e:
        print(f"Key analysis failed: {e}")
        return {"key": "Unknown", "scale": "Unknown", "strength": 0.0}


def analyze_tonal_tempo_logic(audio: np.ndarray, sample_rate: int = 44100) -> Dict[str, Any]:
    """Extract deep-learning tempo only (TempoCNN)."""
    models_dir = os.environ.get("ESSENTIA_MODELS_PATH", "/app/models")
    tempo_cnn_value = None

    try:
        resample = es.Resample(inputSampleRate=sample_rate, outputSampleRate=11025, quality=0)
        audio_11k = resample(audio)

        tempo_model_path = os.path.join(models_dir, "tempocnn", "deeptemp-k16-3.pb")
        if not os.path.exists(tempo_model_path):
            tempo_model_path = os.path.join(models_dir, "tempocnn", "deepsquare-k16-3.pb")

        if os.path.exists(tempo_model_path) and hasattr(es, 'TensorflowPredictTempoCNN'):
            model_tempo = es.TensorflowPredictTempoCNN(graphFilename=tempo_model_path)
            tempo_preds = model_tempo(audio_11k)
            mean_preds = np.mean(tempo_preds, axis=0)
            bpm_range = np.linspace(30, 286, len(mean_preds))
            tempo_cnn_value = _safe_float(bpm_range[int(np.argmax(mean_preds))])
    except Exception as e:
        print(f"TempoCNN analysis failed: {e}")

    return {"tempo_cnn": tempo_cnn_value}


def analyze_tonal_pitch_logic(audio: np.ndarray, sample_rate: int = 44100) -> Dict[str, Any]:
    """Extract pitch only (CREPE mean voiced frequency/confidence)."""
    models_dir = os.environ.get("ESSENTIA_MODELS_PATH", "/app/models")
    pitch_data = None

    try:
        crepe_model_path = os.path.join(models_dir, "crepe", "crepe-full-1.pb")
        if not os.path.exists(crepe_model_path):
            crepe_model_path = os.path.join(models_dir, "crepe", "crepe-tiny-1.pb")

        resample_16k = es.Resample(inputSampleRate=sample_rate, outputSampleRate=16000, quality=0)
        audio_16k = resample_16k(audio)

        if os.path.exists(crepe_model_path) and hasattr(es, 'TensorflowPredictCREPE'):
            model_crepe = es.TensorflowPredictCREPE(graphFilename=crepe_model_path)
            crepe_out = model_crepe(audio_16k)
            if isinstance(crepe_out, tuple) and len(crepe_out) >= 2:
                frequencies = crepe_out[0]
                confidences = crepe_out[1]
            else:
                frequencies = crepe_out
                confidences = np.ones(len(frequencies)) if hasattr(frequencies, '__len__') else np.array([1.0])

            if hasattr(frequencies, '__len__') and len(frequencies) > 0:
                freq_arr = np.array(frequencies)
                conf_arr = np.array(confidences) if hasattr(confidences, '__len__') else np.array([float(confidences)])
                voiced_mask = conf_arr > 0.3
                if np.any(voiced_mask):
                    mean_freq = _safe_float(np.mean(freq_arr[voiced_mask]))
                    mean_conf = _safe_float(np.mean(conf_arr[voiced_mask]))
                else:
                    mean_freq = _safe_float(np.mean(freq_arr))
                    mean_conf = 0.0
                pitch_data = {"mean_frequency": mean_freq, "confidence": mean_conf}
    except Exception as e:
        print(f"CREPE pitch analysis failed: {e}")

    return {"pitch": pitch_data}


def analyze_tonal_logic(audio: np.ndarray, sample_rate: int = 44100) -> Dict[str, Any]:
    """
    Extract Key/Scale via KeyExtractor, deep-learning tempo via TempoCNN,
    and pitch via CREPE.
    """
    key_result = analyze_tonal_key_logic(audio, sample_rate)
    tempo_result = analyze_tonal_tempo_logic(audio, sample_rate)
    pitch_result = analyze_tonal_pitch_logic(audio, sample_rate)

    return {
        **key_result,
        **tempo_result,
        **pitch_result,
    }
