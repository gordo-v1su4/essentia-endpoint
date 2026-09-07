# Studio audio jobs

`POST /analyze/studio/jobs` accepts one multipart `file`, authenticated with the
existing `X-API-Key`, and a required `Idempotency-Key` header. It returns HTTP202
after durable upload acceptance. Poll `GET /analyze/studio/jobs/{id}` with the
same API key; HTTP200 returns state, with a result only after completion.

```json
{"id":"opaque-job-id","status":"running","stage":"structure"}
```

States are `queued`, `running`, `completed`, `failed`. Stages additionally report
`starting`, `decoding`, `rhythm`, `structure`, `validating`, `interrupted`.
Failure returns `error: {code, message}` and no result. There is no automatic
retry or estimated song-structure fallback. A new explicit retry needs a new
idempotency key. Identical key/file requests reuse the original job while it is
retained; a key reused for different bytes returns409. Different API keys cannot
retrieve each other's jobs, even with a known job ID (404). Disk metadata stores
owner/key hashes rather than credentials.

The browser must call its authenticated application backend/Trigger task, not
receive this server credential. GET polling is safe through the public HTTPS
endpoint even if model execution exceeds Cloudflare's request timeout.

## Result contract

`schema_version: "studio-audio-v1"` includes only:

- Decoded `duration`, Essentia `bpm`, `beats`, `confidence`, `onsets`.
- `energy: {curve, sample_rate_hz, start_time_s}`. Curve is normalized RMS, not
  classification. The exact sample rate is `44100 / 512 = 86.1328125`, and first
  frame center is0 seconds. Essentia's default `startFromZero=false` centers the
  first frame at0 and pads outside the audio; see its
  [FrameCutter contract](https://essentia.upf.edu/reference/streaming_FrameCutter.html).
- `structure: {sections, boundaries, source: "allin1", analyzed_duration_s,
  provenance: {status: "detected", method: "allin1:<model>", device: "cuda"}}`.
  `analyzed_duration_s` is decoded duration after validating full model coverage.
  Every section has `start`, `end`, `duration`, `label`, `original_label`, `energy`.
  Section energy is the mean of RMS frame centers within that interval.

Studio uses **CUDA only** for all-in-one source separation and neural inference.
Explicit `ALLIN1_DEVICE=cpu`/`mps` or unavailable CUDA fails with terminal
`cuda_unavailable`; there is no CPU/MPS model fallback. Essentia's ordinary C++
rhythm/RMS computations are not neural GPU models. No classification, tonal,
pitch, vocal classifier, or embeddings are requested.

Studio also requires `natten.has_cuda()` to succeed. Torch CUDA allocation alone
is insufficient: NATTEN 0.17.1 built without CUDA can print an unsupported-device
warning and return invalid finite activations instead of failing inference.
The Dockerfile installs the official NATTEN 0.17.1 wheel for **Linux x86_64,
CPython 3.11, Torch 2.1, CUDA 11.8**, matching this image's Torch 2.1.2 ABI.
The pinned wheel is `natten-0.17.1+torch210cu118-cp311-cp311-linux_x86_64.whl`,
with SHA256 `962509c43ed16469a0150db3751d2212268958eaa799f10b38faab479394f272`.
The build checks this digest before installing without dependency changes,
then verifies the compiled library's `has_cuda()` without needing a visible GPU.
The exact wheel passed CUDA 1D/2D query-key and attention-value kernel probes on
VM100's RTX 4090. These probes validate kernel execution, not song predictions.
This artifact is platform-bound; changing Python, Torch, CUDA or architecture
requires a compatible artifact and fresh runtime verification.

For an optional manual source build, clone v0.17.1 with `--recursive` to include
CUTLASS, and set `NATTEN_WITH_CUDA=1`, `NATTEN_CUDA_ARCH=8.9` for the RTX 4090,
and `NATTEN_N_WORKERS=1` to bound compilation memory. Other GPUs require the
appropriate supported architecture; CUDA 11.8 does not support every newer GPU.
These source-build settings are not Docker build arguments. See the pinned
[NATTEN 0.17.1 build settings](https://github.com/SHI-Labs/NATTEN/blob/v0.17.1/setup.py)
and [runtime capability check](https://github.com/SHI-Labs/NATTEN/blob/v0.17.1/src/natten/context.py).
This preflight applies to Studio only; legacy endpoint behavior is unchanged.

Raw all-in-one labels are retained. `inst`/`solo`/`break` have canonical `bridge`
labels for existing consumers but distinct `original_label`s. Raw `start`/`end`
intervals become neutral `section` labels with their exact timing, so a quiet
tail is not silently removed or falsely labeled outro. Adjacent model intervals
are not merged. Structural gaps/overlaps, invalid timing, missing beats, wrong
duration, and nonfinite outputs fail. Up to0.25 seconds of first/last boundary
rounding is accepted **without stretching any model interval**. Larger uncovered
tails fail rather than fabricating a section. These are model predictions, not
proof that every musical label is artistically correct.

## Operations and limits

Use one Uvicorn process, one worker, and a persistent volume mounted at
`/app/studio-jobs` (`STUDIO_JOBS_DIR`). `docker-compose.vm100.yml` includes the
`essentia-studio-jobs` volume. A process lock refuses a second API worker using
the same directory. Jobs, uploads and result files stay on this volume; transient
all-in-one demix/spectrogram files are isolated per job and removed afterwards.
Multipart spooling itself uses Python's temporary directory and is bounded by
the same concurrent/request limits.

This is an additive router/worker within the existing FastAPI process and Docker
container, not a separate service. If Studio storage initialization, configuration,
or process locking fails, only Studio routes become unavailable (503); existing
health and legacy analysis routes continue serving. Initialization logs contain
the exception type, and failed analysis logs retain only the last8KiB of worker
diagnostics with configured credential values redacted. Provider tracebacks are
never returned to clients.

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `STUDIO_JOBS_DIR` | `/app/studio-jobs` | Durable job volume |
| `STUDIO_MAX_UPLOAD_BYTES` |268435456 |256MiB maximum file; request framing allowance1MiB |
| `STUDIO_MAX_UPLOADS` |2 | Concurrent receiving uploads, reserved before multipart parsing |
| `STUDIO_MAX_PENDING` |4 | Running + queued jobs + in-progress new submissions |
| `STUDIO_MAX_JOBS` |64 | Maximum retained jobs |
| `STUDIO_MAX_STORAGE_BYTES` |2147483648 | Admission budget including reserved input/scratch space |
| `STUDIO_MAX_SCRATCH_BYTES` |1073741824 | Per-active-job scratch allowance beyond maximum input size |
| `STUDIO_MAX_RESULT_BYTES` |8388608 | Maximum serialized result |
| `STUDIO_TTL_SECONDS` |86400 | Completed/failed job retention |
| `STUDIO_TIMEOUT_SECONDS` |1200 | Per-job inference deadline; excludes queue wait |
| `STUDIO_MAX_AUDIO_SECONDS` |1800 | Maximum decoded/probed audio duration |
| `ALLIN1_DEVICE` |`cuda` in VM100 compose | Studio accepts CUDA only |
| `ALLIN1_MODEL` |`harmonix-all` | Functional section model |

Size violations return413, unsupported extensions415, invalid keys422,
capacity429, storage admission507, unavailable worker503. Total streamed request
size is checked even without Content-Length. Every inference runs in a child
process supervised for timeout and scratch size, with its process group killed
on failure/shutdown. A quarter-second disk polling interval can permit a small
temporary overshoot; mount a filesystem quota if a strict OS-enforced cap is
required. Host-level Torch/Demucs model caches are separate from per-job scratch.

On restart, queued/running jobs become failed/interrupted, never silently
recomputed. Completed results remain retrievable until TTL expiry. Uploads and
scratch are cleaned after terminal states; terminal jobs expire on periodic
cleanup/read/submission. Clients should poll the original job after network
errors, not use a new idempotency key. At full capacity, wait for a slot rather
than launching duplicate analyses. Polling deadlines must include queue time.

Legacy endpoints remain available. `/analyze/fast` and `/analyze/full` still use
SBic boundaries and energy-derived labels; they do not invoke this dedicated
functional structure pipeline.

## Verification

Install only lightweight test dependencies in a Python3.11 environment:

```bash
uv pip install fastapi python-multipart httpx
python -m unittest discover -s tests -p 'test_studio_jobs.py' -v
```

Tests fake the analyzer and cover durable restart behavior, auth/owner isolation,
idempotency, queue/storage/upload limits, live stages, CUDA-only guards, timing
validation, and raw start/end labels. They do not substitute for a real CUDA song
job, actual output inspection, and application polling verification after deployment.
