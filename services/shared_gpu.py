"""Cooperate with the existing VM100 Qwen/video/Splitter GPU lock."""
from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import threading
import time

state = threading.local()


@contextmanager
def gpu_lease():
    path = os.getenv('GPU_LOCK_PATH', '').strip()
    if not path or getattr(state, 'depth', 0):
        yield
        return
    import fcntl
    timeout = float(os.getenv('GPU_LOCK_TIMEOUT_SECONDS', '900'))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a') as handle:
        started = time.monotonic()
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() - started >= timeout:
                    raise RuntimeError('GPU is busy; shared GPU queue wait timed out.')
                time.sleep(0.1)
        state.depth = 1
        try:
            yield
        finally:
            state.depth = 0
            fcntl.flock(handle, fcntl.LOCK_UN)


def shared_gpu(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with gpu_lease():
            return function(*args, **kwargs)
    return wrapped
