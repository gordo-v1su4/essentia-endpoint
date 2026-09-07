# Migrating a client from `/analyze/fast` to Studio

This guide is for agents and developers updating other projects. Pull `main` from
`gordo-v1su4/essentia-endpoint`. The deployed service is named `essentia-api` and
uses the same public base URL, `https://essentia.v1su4.dev`, and existing API key.
No second repository, service, or new credentials are required.

**Existing endpoints remain available and compatible.** Moving a client is an
explicit change to its submission, polling and response parsing; changing only
the URL is insufficient. The CUDA repair was deployed from commit `59550eb`.

## GPU requirement — no model fallback

**GPU only for source separation and neural song-structure inference.** Studio
requires CUDA, `ALLIN1_DEVICE=cuda`, and a CUDA-enabled NATTEN attention library.
It does not silently switch these models to CPU or MPS. An unavailable GPU or
unsupported backend produces a failed job with `error.code: "cuda_unavailable"`;
the consuming project must show the failure, not silently retry through
`/analyze/fast` or substitute generic song sections.

The caller does not select a device or supply a GPU option: the server enforces
this policy. Successful results include `structure.provenance.device: "cuda"`.
Ordinary Essentia C++ beat/onset/RMS calculations still run on CPU; the GPU-only
requirement applies to the source-separation and neural structure models, not
every decoding, signal-processing or HTTP operation.

## Input

Upload **one complete song**, with its real filename, as multipart field `file`.
Both WAV and MP3 are accepted. No stems, lyrics, character references or options
are required. Send the actual file bytes, not a JSON URL or a server file path.
Let the HTTP client set the multipart `Content-Type` and boundary.

The route also accepts FLAC, OGG, M4A, AAC, AIF/AIFF, WebM and MP4 extensions;
the contents must contain decodable audio. The full-song live acceptance test
used WAV; acceptance of an extension does not constitute an end-to-end test of
every codec. Default limits are 256 MiB and 30 minutes of decoded audio, subject
also to any limits imposed by a client's own upload proxy.

Keep `X-API-Key` on your application server or trusted worker. Browser clients
should use their authenticated application backend, never receive the key.

## Submit once, then poll

1. Persist a unique `Idempotency-Key` for this logical analysis request before
   uploading. A persisted UUID or stable application job ID is suitable.
2. `POST /analyze/studio/jobs` with `X-API-Key`, `Idempotency-Key`, and `file`.
   HTTP 202 returns a job envelope, normally `{id, status, stage}`.
3. Persist the returned `id`. Poll `GET /analyze/studio/jobs/{id}` with the same
   API key, about every three seconds. HTTP 200 means the lookup succeeded;
   it does **not** mean analysis finished.
4. Read `result` only when `status` is `completed`. For `failed`, show
   `error.message` and retain `error.code`; never fabricate a fallback structure.

States are `queued`, `running`, `completed`, `failed`. The `stage` reports actual
work such as `decoding`, `rhythm`, `structure`, and `validating`; display it as
live feedback without inventing a completion percentage.

After a lost POST response, retry with the **same key and identical file bytes**.
After a polling interruption, resume GET using the saved job ID. Do not create a
new analysis because an HTTP request timed out. Reusing a key with different
bytes returns 409. Terminal failure requires an explicit new request/key to retry.
Idempotency and stored results last only for the retention window (24 hours by
default); persist completed results in the consuming application's own storage.

## Response mapping

The completed envelope contains `result.schema_version = "studio-audio-v1"`.
All event and section times are **seconds**, not milliseconds or frame numbers.

| Result field | Meaning / migration note |
| --- | --- |
| `duration` | Full decoded song duration. Preserve it instead of stretching timestamps to a different player duration. |
| `bpm` | Estimated tempo; retain through application persistence and display. |
| `beats` | Ordered beat timestamps. |
| `confidence` | Beat-tracker confidence, not section confidence or a calibrated percentage. |
| `onsets` | Ordered timestamps of detected sound attacks. |
| `energy.curve` | RMS energy normalized to 0–1. |
| `energy.sample_rate_hz` | Curve sampling rate; currently 86.1328125 Hz. |
| `energy.start_time_s` | Time of the first curve sample; currently 0. Sample `i` is at `start_time_s + i / sample_rate_hz`. |
| `structure.sections` | Each has `start`, `end`, `duration`, `label`, `original_label`, and mean normalized `energy`. |
| `structure.boundaries` | Ordered section edges. |
| `structure.source` | `allin1`, replacing the fast endpoint's SBic structure method. |
| `structure.analyzed_duration_s` | Decoded duration after checking structure coverage. |
| `structure.provenance` | `{status: "detected", method: "allin1:harmonix-all", device: "cuda"}` for the deployed model. |

Unlike the fast response, Studio energy does **not** include `mean` or `std`.
Update consumers that require those fields. If downsampling the curve for a
timeline, use its sampling rate and start time rather than dropping timing metadata.

No lyrics, key/scale, genre, mood, pitch, vocal classification, embeddings,
downbeat array or time signature are returned. Keep other analysis endpoints or
transcription services for features your project still needs.

Studio uses All-In-One functional section predictions; fast/full retain their
existing SBic boundaries and heuristic labels. Section predictions are editable
model output, not guaranteed artistic truth. Adjacent intervals may share a
label: keep raw data, and group adjacent equal labels only as an explicit view
decision. Never collapse non-adjacent verses or choruses into one time interval.
Raw `start`/`end` labels become neutral `section` labels, with `original_label`
retained; do not drop these margins or automatically call the final one an outro.
`inst`, `solo`, and `break` map to `bridge`, also retaining their original label.

## Server-side JavaScript example

This uses standard `fetch`, `File` and `FormData` APIs available in Bun or a modern
Node runtime. Obtain `file` from your backend upload or durable media storage.
Submission and polling are separate so the application can save the job ID and
resume after a restart. Errors deliberately propagate to the application's retry
policy; retrying polling must not call `submitStudio` again.

```js
const base = "https://essentia.v1su4.dev";

async function readJob(response) {
  if (!response.ok) throw new Error(`Essentia HTTP ${response.status}`);
  const job = await response.json();
  if (!job.id || !["queued", "running", "completed", "failed"].includes(job.status)) {
    throw new Error("Invalid Essentia job response");
  }
  return job;
}

async function submitStudio(file, apiKey, persistedRequestKey) {
  const body = new FormData();
  body.set("file", file);
  return readJob(await fetch(`${base}/analyze/studio/jobs`, {
    method: "POST",
    headers: { "X-API-Key": apiKey, "Idempotency-Key": persistedRequestKey },
    body,
    signal: AbortSignal.timeout(90_000),
  }));
}

async function waitForStudio(jobId, apiKey, onStage = () => {}, timeoutMs = 30 * 60_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const job = await readJob(await fetch(
      `${base}/analyze/studio/jobs/${encodeURIComponent(jobId)}`,
      { headers: { "X-API-Key": apiKey }, signal: AbortSignal.timeout(30_000) },
    ));
    if (job.id !== jobId) throw new Error("Unexpected Essentia job ID");
    onStage(job.stage);
    if (job.status === "failed") {
      throw new Error(`${job.error?.code}: ${job.error?.message}`);
    }
    if (job.status === "completed") {
      if (job.result?.schema_version !== "studio-audio-v1") {
        throw new Error("Unsupported Studio result contract");
      }
      return job.result;
    }
    await new Promise(resolve => setTimeout(resolve, 3_000));
  }
  throw new Error(`Polling deadline reached; resume job ${jobId}, do not resubmit`);
}

// const job = await submitStudio(file, serverApiKey, savedRequestKey);
// await saveJobId(job.id); // Persist before polling.
// const result = await waitForStudio(job.id, serverApiKey, publishStage);
// await saveAnalysis(result);
```

Validate the result against [the response models](../api/studio_models.py) before
using it in an edit. Handle 401 as an authentication problem, 409 as a request-key
conflict, 413/415 as input problems, and 429/503 or transient network/5xx errors
with bounded backoff. A client polling deadline can expire during a long queue;
it does not cancel the server job. The example deadline is configurable.

## Migration acceptance for each consuming project

- Replace the synchronous analysis call with durable submission/polling, and show
  real stages and terminal errors in that project's UI.
- Adapt the response wrapper, energy timing, missing energy statistics and raw
  section labels. Persist BPM, duration, provenance and completed results.
- Verify a real local song through the project's actual upload flow, including
  save/reload and timeline alignment. Check that interrupted polling resumes the
  original job and never starts duplicate inference.
- Verify that features needing excluded fields still use their appropriate
  service. Do not mark another project's integration complete just because the
  Essentia server is healthy or its API test passes.

The September 7 server acceptance run analyzed a 246.69995-second WAV in 37.5
seconds including submission/polling. It returned BPM 131.9413, 525 beats, 1,344
onsets, 21,250 RMS samples and sixteen model intervals, with intro/verse/chorus/
bridge transitions and the final tail retained. This is one observed result,
not a latency guarantee or evidence that every client project has migrated.

For queue limits, GPU requirements, failure handling and deployment details, see
[Studio audio jobs](STUDIO_AUDIO_JOBS.md). The live [Swagger UI](https://essentia.v1su4.dev/docs)
and `/openapi.json` describe the deployed API; older checked-in OpenAPI snapshots
may omit the additive Studio routes.
