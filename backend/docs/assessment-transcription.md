# Assessment audio transcription

The speaking node calls `ai/transcription.py` before language evaluation. This is
an internal worker step, not an HTTP endpoint. It consumes the verified,
response-bound snapshot prepared by the evidence loader.

1. Explicit skips preserve their reason and do not access S3 or OpenAI.
2. Missing metadata or an expired retention deadline produces AUDIO_UNAVAILABLE.
3. The private S3 object is downloaded with the existing bounded reader, which
   checks content type, byte length, and SHA-256 against the verified snapshot.
4. Missing objects and integrity failures produce AUDIO_UNAVAILABLE. Storage
   outages raise a retryable job error.
5. The retention deadline and worker claim are checked again before transcription.
6. The OpenAI wrapper sends bytes with a fixed filename, correct extension/content
   type, and explicit JSON response format. Unsupported types, empty bytes, and
   oversized input are rejected locally. The stream is closed after the call.
7. A valid string transcript is bounded to 20,000 characters. Missing/non-string
   or oversized provider output is a retryable provider failure, not learner
   silence. Fewer than three tokens containing letters gives INSUFFICIENT_EVIDENCE.
8. Usable text goes to the speaking language evaluator. No pronunciation, pace,
   or prosody score is derived from it.

The three-token gate is a minimal usability check; it is not voice activity
detection and cannot guarantee that a transcription is accurate or hallucination
free. No question prompt or sample answer is sent to the transcription model.

## Configuration and failures

Existing settings remain:

```dotenv
OPENAI_API_KEY=
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-mini-transcribe
OPENAI_TIMEOUT_SECONDS=30
```

S3 uses the existing bucket, region, and AWS credential chain. Upload confirmation
already requires FFmpeg verification. This step does not change upload APIs.

SDK retries remain disabled so the job runner owns the bounded retry budget.
Connection/timeouts, rate limits, HTTP 408/409/5xx, and malformed successful
responses are retryable. Authentication, authorization, and other request errors
are not disguised as missing audio; existing worker terminal failure handling
applies. A 403 from S3 is not assumed to mean the object was deleted.

No transcript is logged or added to the public result by this step. The typed
transcript hides text from its repr. There is no database transaction during
network calls and no new table or migration. The graph now saves temporary
claim-fenced checkpoints for retry reuse; see `assessment-checkpoints.md` for
fingerprinting, retention, and the remaining provider-to-commit billing gap.

Checks: lint, imports, and schema generation only; no live S3/OpenAI calls or
database/worker execution. No tests were added or run.

Request contract reference:
[OpenAI Create transcription](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create).
