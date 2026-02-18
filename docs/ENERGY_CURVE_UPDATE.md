# Energy Curve & Section Energy

High-resolution energy data for speed ramping and energy-based visual triggers.

## Energy Curve (Rhythm Analysis)

Returned by `POST /analyze/rhythm` and `POST /analyze/full`.

- **Frame size**: 1024 samples
- **Hop size**: 512 samples (~11.6ms at 44.1kHz)
- **Temporal resolution**: ~86Hz (good for 60fps video sync)
- **Normalization**: 0-1 range

```json
{
  "energy": {
    "mean": 0.45,
    "std": 0.12,
    "curve": [0.0, 0.1, 0.3, 0.5, 0.8, 0.6, ...]
  }
}
```

**Implementation**: `services/analysis.py` — `analyze_rhythm_logic()` computes a normalized RMS energy curve plus mean/std statistics.

## Section Energy (Structure Analysis)

Returned by `POST /analyze/structure` and `POST /analyze/full`.

Each section includes a mean-squared energy value computed from its audio chunk:

```json
{
  "sections": [
    {"start": 0.0, "end": 15.2, "label": "intro", "duration": 15.2, "energy": 0.12},
    {"start": 15.2, "end": 62.8, "label": "chorus", "duration": 47.6, "energy": 0.54}
  ]
}
```

Section energy is also used internally for labeling (chorus = high energy, verse = lower energy).

## Pydantic Models

```python
class EnergyData(BaseModel):
    mean: float
    std: float
    curve: List[float]

class Section(BaseModel):
    start: float
    end: float
    label: str
    duration: float
    energy: float
```

## Use Cases

- **Speed ramping**: Map `energy.curve` values to video playback speed
- **Glitch triggers**: Use section `energy` to drive effect intensity during high-energy sections (chorus/drops)
- **Visual feedback**: Display energy waveform in UI or sync shader effects to the curve
- **Section detection**: Energy differences help distinguish verse/chorus/bridge

## Performance

For a 3-minute song:
- Energy curve: ~15,500 float values (~62KB raw, ~10-15KB gzipped)
- Computation time: ~50-100ms additional

## Testing

```bash
# Get energy curve
curl -X POST http://localhost:7000/analyze/rhythm \
  -H "X-API-Key: your_key" \
  -F "file=@track.mp3" | jq '.energy'

# Get section energies
curl -X POST http://localhost:7000/analyze/structure \
  -H "X-API-Key: your_key" \
  -F "file=@track.mp3" | jq '.sections[] | {label, energy}'
```
