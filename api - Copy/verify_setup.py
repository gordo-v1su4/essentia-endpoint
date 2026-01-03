try:
    import essentia
    import essentia.standard as es
    import numpy as np
    from fastapi import FastAPI
    from api.models import RhythmAnalysis
    from services.analysis import analyze_rhythm_logic
    print("✅ All modules imported successfully.")
    
    # Simple test data
    audio = np.random.uniform(-1, 1, 44100).astype(np.float32)
    print("⏳ Testing rhythm analysis logic...")
    result = analyze_rhythm_logic(audio)
    print(f"✅ Rhythm analysis test passed. BPM: {result['bpm']}")
    
except ImportError as e:
    print(f"❌ Import failed: {e}")
except Exception as e:
    print(f"❌ Logic test failed: {e}")
    import traceback
    traceback.print_exc()
