"""Queue and processing deadlines remain independently bounded."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from services.studio_analysis import analyze_studio_file, run_studio_analysis
from services.studio_jobs import isolated_analysis, JobError, JobSettings
from services.shared_gpu import GpuQueueTimeoutError


class StudioGpuTimeoutTests(unittest.TestCase):
    def test_lease_precedes_cuda_work_and_publishes_waiting_stage(self):
        events = []
        @contextmanager
        def lease():
            events.append("acquired")
            yield
            events.append("released")
        with patch("services.studio_analysis.gpu_lease", lease), patch(
            "services.studio_analysis._analyze_studio_file",
            side_effect=lambda *args: events.append("cuda_work") or {},
        ):
            analyze_studio_file("input.wav", events.append)
        self.assertEqual(events, ["waiting_gpu", "acquired", "starting", "cuda_work", "released"])

    def test_worker_keeps_acquisition_timestamp_after_later_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def analyze(path, progress):
                progress("decoding")
                progress("structure")
                return {"ok": True}
            with patch("services.studio_analysis.gpu_lease"), patch(
                "services.studio_analysis._analyze_studio_file", side_effect=analyze,
            ), patch("services.studio_analysis.time.monotonic", side_effect=[10, 910]):
                run_studio_analysis(root / "input.wav", root / "analysis.json", root / "stage.txt")
            self.assertEqual(json.loads((root / "stage.txt").read_text()),
                             {"stage": "structure", "waiting_gpu": 10, "starting": 910})

    def test_worker_serializes_queue_failure_without_cuda_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("services.studio_analysis.gpu_lease", side_effect=GpuQueueTimeoutError("busy")), patch(
                "services.studio_analysis._analyze_studio_file",
            ) as analyze:
                with self.assertRaises(GpuQueueTimeoutError):
                    run_studio_analysis(root / "input.wav", root / "analysis.json", root / "stage.txt")
            analyze.assert_not_called()
            self.assertEqual(json.loads((root / "error.json").read_text())["code"], "gpu_queue_timeout")

    def test_supervisor_preserves_child_queue_error_after_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "input.wav"
            path.write_bytes(b"input")
            (root / "error.json").write_text('{"code": "gpu_queue_timeout"}')
            process = Mock(returncode=1)
            process.poll.return_value = 1
            with patch("services.studio_jobs.subprocess.Popen", return_value=process):
                with self.assertRaises(JobError) as error:
                    isolated_analysis(path, lambda stage: None, JobSettings(root))
            self.assertEqual(error.exception.code, "gpu_queue_timeout")

    def supervise(self, states, *, returncode=0, stopping=lambda: False, storage=100000):
        """Drive the real supervisor with a deterministic worker/monotonic clock."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "input.wav"
            path.write_bytes(b"input")
            (root / "analysis.json").write_text('{"ok": true}')
            now = [0]
            process = Mock(pid=123, returncode=returncode)
            updates = iter(states)
            def poll():
                try:
                    elapsed, state = next(updates)
                except StopIteration:
                    return returncode
                now[0] = elapsed
                if state is not None:
                    (root / "stage.txt").write_text(json.dumps(state))
                return None
            process.poll.side_effect = poll
            stages = []
            with patch("services.studio_jobs.subprocess.Popen", return_value=process), patch(
                "services.studio_jobs.time.monotonic", side_effect=lambda: now[0],
            ), patch("services.studio_jobs.time.sleep"), patch(
                "services.studio_jobs.os.killpg", create=True,
            ) as kill, patch.dict(os.environ, {"GPU_LOCK_TIMEOUT_SECONDS": "900"}):
                try:
                    result = isolated_analysis(path, stages.append, JobSettings(root, max_scratch_bytes=storage,
                                               max_upload_bytes=1, timeout_seconds=1200), stopping)
                except JobError as error:
                    return error.code, stages, kill.call_count
            return result, stages, kill.call_count

    def test_nearly_full_queue_wait_leaves_full_processing_budget(self):
        result, stages, kills = self.supervise([
            (0, {"stage": "waiting_gpu", "waiting_gpu": 0}),
            (899, {"stage": "waiting_gpu", "waiting_gpu": 0}),
            (900, {"stage": "decoding", "waiting_gpu": 0, "starting": 899}),
            (2098, {"stage": "structure", "waiting_gpu": 0, "starting": 899}),
        ])
        self.assertEqual(result, {"ok": True})
        self.assertEqual(stages, ["waiting_gpu", "decoding", "structure"])
        self.assertEqual(kills, 0)

    def test_processing_deadline_uses_child_timestamp_even_if_poll_misses_acquisition(self):
        code, _, _ = self.supervise([
            (0, {"stage": "waiting_gpu", "waiting_gpu": 0}),
            (2100, {"stage": "structure", "waiting_gpu": 0, "starting": 899}),
        ])
        self.assertEqual(code, "analysis_timeout")

    def test_stuck_queue_and_startup_are_bounded(self):
        for states, expected in [
            ([(0, {"stage": "waiting_gpu", "waiting_gpu": 0}), (901, None)], "gpu_queue_timeout"),
            ([(1201, None)], "analysis_timeout"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(self.supervise(states)[0], expected)

    def test_shutdown_and_storage_limits_apply_while_waiting(self):
        states = [(0, {"stage": "waiting_gpu", "waiting_gpu": 0})]
        self.assertEqual(self.supervise(states, stopping=lambda: True)[0], "interrupted")
        self.assertEqual(self.supervise(states, storage=1)[0], "analysis_storage_limit")


@unittest.skipUnless(sys.platform == "linux", "Production uses Linux flock/process groups")
class StudioGpuContentionTests(unittest.TestCase):
    def test_real_contention_exceeding_analysis_budget_still_completes(self):
        from services.shared_gpu import gpu_lease
        original = subprocess.Popen
        script = """
import sys, time
from pathlib import Path
from unittest.mock import patch
from services.studio_analysis import run_studio_analysis
def analyze(path, progress):
    progress('decoding')
    time.sleep(0.1)
    return {'ok': True}
with patch('services.studio_analysis._analyze_studio_file', side_effect=analyze):
    run_studio_analysis(*map(Path, sys.argv[1:]))
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "input.wav"
            path.write_bytes(b"input")
            stages = []
            env = {"GPU_LOCK_PATH": str(root / "gpu.lock"), "GPU_LOCK_TIMEOUT_SECONDS": "5"}
            with patch.dict(os.environ, env), gpu_lease():
                def spawn(args, **kwargs):
                    return original([sys.executable, "-c", script, *args[3:]], **kwargs)
                # Release the real lease only after the supervisor observes waiting
                # for longer than the configured processing budget.
                import threading
                result = []
                def run():
                    try:
                        with patch("services.studio_jobs.subprocess.Popen", side_effect=spawn):
                            result.append(isolated_analysis(path, stages.append, JobSettings(root, timeout_seconds=1)))
                    except Exception as error:
                        result.append(error)
                thread = threading.Thread(target=run)
                thread.start()
                import time
                deadline = time.monotonic() + 5
                while "waiting_gpu" not in stages and time.monotonic() < deadline:
                    time.sleep(0.01)
                time.sleep(1.1)
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertIn("waiting_gpu", stages)
            self.assertEqual(result, [{"ok": True}])


if __name__ == "__main__":
    unittest.main()
