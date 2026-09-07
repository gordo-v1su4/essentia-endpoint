"""Additive Studio routes must not change the deployed legacy API contract."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("API_KEYS", "test-owner-a,test-owner-b")
from fastapi.testclient import TestClient
from services.allin1_structure import analyze_structure_allin1_logic

ROOT = Path(__file__).resolve().parents[1]


def load_app(source=None, name="studio_compat_main"):
    analysis = types.ModuleType("services.analysis")
    for symbol in ("load_audio", "analyze_rhythm_logic", "analyze_structure_logic", "analyze_classification_logic",
                   "analyze_tonal_logic", "analyze_tonal_key_logic", "analyze_tonal_tempo_logic",
                   "analyze_tonal_pitch_logic", "analyze_vocals_logic"):
        setattr(analysis, symbol, lambda *a, **kw: None)
    analysis.StructureSegmentationError = ValueError
    analysis.ALL_CLASSIFICATION_FEATURES = set()
    module = types.ModuleType(name); module.__file__ = str(ROOT / "main.py")
    with patch.dict(sys.modules, {"services.analysis": analysis, "uvicorn": types.ModuleType("uvicorn"),
                                 "prometheus_client": None}):
        exec(compile(source or (ROOT / "main.py").read_text(), module.__file__, "exec"), module.__dict__)
    return module


class CompatibilityTests(unittest.TestCase):
    def test_all_legacy_openapi_paths_and_schemas_unchanged(self):
        baseline = json.loads((ROOT / "tests/fixtures/legacy-openapi-7006aec.json").read_text())
        actual = load_app().app.openapi()
        self.assertEqual(actual["info"], baseline["info"])
        for path, contract in baseline["paths"].items():
            self.assertEqual(actual["paths"][path], contract, path)
        for schema, contract in baseline["components"]["schemas"].items():
            self.assertEqual(actual["components"]["schemas"][schema], contract, schema)
        self.assertEqual(actual["components"]["securitySchemes"], baseline["components"]["securitySchemes"])
        self.assertEqual(set(actual["paths"]) - set(baseline["paths"]),
                         {"/analyze/studio/jobs", "/analyze/studio/jobs/{job_id}"})

    def test_studio_initialization_failure_does_not_break_legacy_service(self):
        for failure in (PermissionError("private path"), ModuleNotFoundError("fcntl"), RuntimeError("locked")):
            with self.subTest(failure=type(failure).__name__):
                module = load_app()
                with patch.object(module.StudioJobs, "start", side_effect=failure), self.assertLogs(module.__name__, level="ERROR") as logs:
                    with TestClient(module.app) as client:
                        self.assertIsNone(module.app.state.studio_jobs)
                        self.assertEqual(client.get("/health").json(), {"status": "ok", "version": "4.1.0"})
                        self.assertEqual(client.get("/openapi.json").status_code, 200)
                        headers = {"X-API-Key": "test-owner-a", "Idempotency-Key": "disabled-job"}
                        self.assertEqual(client.post("/analyze/studio/jobs", headers=headers, files={"file": ("a.wav", b"fake")}).status_code, 503)
                        self.assertEqual(client.get("/analyze/studio/jobs/unknown", headers=headers).status_code, 503)
                        self.assertEqual(client.post("/analyze/fast", files={"file": ("a.wav", b"fake")}).status_code, 401)
                self.assertNotIn("private path", "\n".join(logs.output))

    def test_invalid_studio_settings_do_not_prevent_startup(self):
        module = load_app()
        with patch.object(module.JobSettings, "from_env", side_effect=ValueError("bad config")), self.assertLogs(module.__name__, level="ERROR"):
            with TestClient(module.app) as client:
                self.assertEqual(client.get("/health").status_code, 200)

    def test_default_allin1_behavior_retains_legacy_kwargs_and_output(self):
        raw = types.SimpleNamespace(segments=[
            types.SimpleNamespace(start=0, end=1, label="start"),
            types.SimpleNamespace(start=1, end=2, label="verse"),
            types.SimpleNamespace(start=2, end=3, label="verse"),
            types.SimpleNamespace(start=3, end=4, label="end"),
        ], bpm=120)
        analyze = Mock(return_value=raw)
        with patch.dict(sys.modules, {"allin1": types.SimpleNamespace(analyze=analyze)}), patch("services.allin1_structure._resolve_device", return_value="cpu"), patch.dict(os.environ, {"ALLIN1_MODEL": "harmonix-all"}):
            value = analyze_structure_allin1_logic("input.wav")
        analyze.assert_called_once_with(paths="input.wav", model="harmonix-all", device="cpu", keep_byproducts=False)
        self.assertEqual(value, {"source": "allin1", "analyzed_duration_s": 3.0, "boundaries": [1.0, 3.0],
            "sections": [{"start": 1.0, "end": 3.0, "duration": 2.0, "label": "verse", "energy": 0.0}]})


if __name__ == "__main__":
    unittest.main()
