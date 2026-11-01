import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from services.shared_gpu import gpu_lease, shared_gpu


@unittest.skipUnless(sys.platform == 'linux', 'VM100 uses Linux flock')
class SharedGpuTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'GPU_LOCK_PATH': str(Path(self.temp.name) / 'gpu.lock'), 'GPU_LOCK_TIMEOUT_SECONDS': '2'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_another_process_waits_until_owner_releases(self):
        script = "from services.shared_gpu import gpu_lease; print('waiting',flush=True); lease=gpu_lease(); lease.__enter__(); print('acquired',flush=True); lease.__exit__(None,None,None)"
        with gpu_lease():
            child = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(child.stdout.readline().strip(), 'waiting')
            self.assertIsNone(child.poll())
        stdout, stderr = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(stdout.strip(), 'acquired')

    def test_busy_timeout_is_explicit(self):
        env = {**os.environ, 'GPU_LOCK_TIMEOUT_SECONDS': '0.1'}
        with gpu_lease():
            child = subprocess.run([sys.executable, '-c', 'from services.shared_gpu import gpu_lease; lease=gpu_lease(); lease.__enter__()'], env=env, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn('shared GPU queue wait timed out', child.stderr)

    def test_nested_calls_and_exception_release(self):
        @shared_gpu
        def inner():
            raise ValueError('test')
        @shared_gpu
        def outer():
            inner()
        with self.assertRaises(ValueError):
            outer()
        with gpu_lease():
            pass


if __name__ == '__main__':
    unittest.main()
