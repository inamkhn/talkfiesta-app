# Assessment audio uploads

## Plan and implementation

Allocation persists an owner-bound upload for an assigned speaking response and
returns a short-lived S3 PUT URL. Confirmation validates the object bytes and
decodes audio before marking the upload VERIFIED. Both routes use user -> attempt
-> response -> upload locking, consistent with answer saving and submission.
The new upload binding replaces an earlier binding only while the response remains
ASSIGNED. Existing answers and submitted assessments cannot be changed.

## Frontend flow

1. Finish recording before requesting an upload. Compute its actual byte length
   and SHA-256 digest, encoded as base64 (not hex).
2. POST `/api/v1/media/audio-uploads` with Bearer authentication:

```json
{
  "purpose": "ASSESSMENT",
  "assessment_response_id": "<assigned speaking response UUID>",
  "content_type": "audio/webm",
  "size_bytes": 123456,
  "checksum_sha256": "<base64 SHA-256 digest of those exact bytes>"
}
```

201 returns upload_id, upload_url, method PUT, headers, and expires_at. Do not log
the signed URL. Send the raw recording bytes to that URL with the returned
Content-Type, x-amz-checksum-sha256 and If-None-Match headers. Do not send the app's
Bearer token to S3. The browser supplies Content-Length automatically from the
Blob; do not manually set this forbidden browser header. The exact length is
included in the signature. A repeated successful PUT can return 412 because
If-None-Match prevents overwrite; try confirmation to determine whether it exists.

3. POST `/api/v1/media/audio-uploads/{upload_id}/confirm`, Bearer authenticated,
   with no body. A successful 200 includes upload_id, assessment_response_id,
   status VERIFIED, size_bytes, and duration_seconds.
4. PUT the speaking answer through the existing response endpoint, supplying
   media_upload_id and expected_revision. Confirmation binds/verifies audio but
   does not finalize the answer or increment its revision.

Allowed MIME types: audio/webm, audio/ogg, audio/wav, audio/mpeg, audio/mp4.
Use the canonical type without codec parameters. Defaults: 10 MiB, 0.5–180 seconds,
five-minute upload URL, and a further 15-minute confirmation window. The server
checks S3 length/type, downloads only the expected bounded byte count, compares
SHA-256, and uses FFprobe/FFmpeg to require one mono/stereo audio stream and decode
to bounded PCM. Duration comes from decoded samples, including WebM recordings
without duration metadata. Format guessing and network protocols are disabled.
This verifies technical usability, not whether the learner actually spoke.

Repeated confirmation returns the saved VERIFIED result while still bound and
within retention. Replaced/detached/expired uploads return 409. Invalid bytes,
format, checksum or duration return 422 and persist REJECTED; create a new upload.
A missing S3 object returns 409 UPLOAD_NOT_FOUND without rejecting the record;
transient storage/decoder availability failures return 503. Owner mismatches return
404. Creation and confirmation use the existing Redis rate limiter (20/40 per
user per hour; it fails open when Redis is unavailable).

## Deployment prerequisites

- Apply migration `20261101_audio_binding` after `20261101_submit_keys` against the
  existing V4 database. No migration or live cloud operation was executed here.
- Configure S3_BUCKET/S3_REGION and AWS credentials via the normal boto3 provider
  chain. The service needs PutObject and GetObject access to assessment-audio/*.
- Keep the bucket private with public access blocked and encryption enabled.
  Bucket CORS must allow your actual frontend origin, PUT, Content-Type,
  x-amz-checksum-sha256 and If-None-Match. Do not grant browser AWS credentials.
- Install FFmpeg and ffprobe on the API host and set their paths if needed. Each
  subprocess has a 30-second timeout; uploads/decoding run off the async event loop.
- Configure an S3 lifecycle policy to delete assessment-audio/* after the chosen
  retention interval, including noncurrent versions if versioning is enabled.
  delete_after controls API acceptance; it does not itself delete S3 objects.
  Unconfirmed, rejected and replaced objects also require lifecycle cleanup.
- Future evaluation workers must recheck availability and the persisted checksum
  before transcribing. No dispatcher or evaluation worker was added here.

The added nullable fields preserve existing rows; legacy uploads without binding,
expected size/checksum, and expiry cannot be confirmed through this new flow.
No new table is needed. No tests were added or run; live S3 and codec verification
still require configured infrastructure.

Implementation references: [S3 conditional/checksummed PUT](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/bucket/put_object.html)
and [FFmpeg protocol restrictions](https://www.ffmpeg.org/ffmpeg-protocols.html).
