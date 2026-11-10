# Speaking audio uploads

The existing media endpoints now support Speaking as well as Assessment.
Assessment request/response fields and default verification limits are preserved.

## Allocate

`POST /api/v1/media/audio-uploads` with Bearer authentication:

```json
{
  "purpose": "SPEAKING",
  "submission_id": "<owned current draft UUID>",
  "content_type": "audio/webm",
  "size_bytes": 583210,
  "sha256_hex": "<64 hexadecimal characters computed from the exact recording>"
}
```

201 returns upload_id, method=PUT, upload_url, required_headers, expires_at and
status=INITIATED. Upload the exact bytes directly to S3 using every returned
header: Content-Type, x-amz-checksum-sha256 and If-None-Match. The server converts
the hex digest to S3's canonical base64 checksum; Assessment continues accepting
its existing checksum_sha256 base64 field.

The server validates the owned, editable, current pinned Speaking draft and
absence of completion credit. It creates a fresh opaque speaking-audio object
key and atomically replaces practice_submissions.media_upload_id with the new
allocation. Re-recording allocates a new object; verified objects are never
overwritten. Older detached uploads remain eligible for expiry cleanup.

## Confirm

`POST /api/v1/media/audio-uploads/{upload_id}/confirm` requires no payload.
The upload must be owned, purpose=SPEAKING and still attached to the current
editable draft. Replaced uploads fail with 409 UPLOAD_NOT_BOUND.

The server downloads at most the declared size plus one byte, checks S3's size
and MIME metadata, verifies the actual SHA-256, probes for a single mono/stereo
Opus audio stream, and decodes with FFmpeg to measure duration. Invalid data is
persisted as REJECTED; transient storage failures leave it retryable. Missing
objects return UPLOAD_NOT_FOUND. Verification is synchronous and bounded by the
existing storage timeouts and decoder timeouts; no AI providers are called.

200 returns upload_id, submission_id, status=VERIFIED, content_type, size_bytes,
duration_seconds and verified_at. Repeating confirmation of the same verified
upload is safe while its draft is still current/editable and retention has not
expired. Confirmation does not credit activity or advance progress.

## Policy and deployment

- Speaking MIME: audio/webm; decoded codec must be Opus.
- SPEAKING_AUDIO_MAX_BYTES defaults to 15728640 (15 MiB); larger allocations 413.
- SPEAKING_AUDIO_MIN_DURATION_SECONDS defaults to 10.
- SPEAKING_AUDIO_MAX_DURATION_SECONDS defaults to 180 (maximum configurable 600).
- Shared URL validity defaults to 300 seconds; confirmation grace is 15 minutes.
- Shared retention defaults to 7 days, measured from allocation.
- Existing rate limits apply across purposes: allocation 20/hour/user,
  confirmation 40/hour/user. Successful responses are no-store.

S3 credentials/configuration, bucket CORS allowing the signed PUT headers,
FFmpeg/ffprobe, PostgreSQL and Redis must already be configured. All DB writers
use user -> plan/progress -> content -> draft -> upload lock order. Confirmation
holds these locks during bounded verification to serialize replacement/submit.
No new database columns or migration are required for this change; the prior
speaking-drafts migration is still required.

Checks: lint, imports and OpenAPI generation. No tests, live database operations,
S3 uploads or decoder executions were run.
