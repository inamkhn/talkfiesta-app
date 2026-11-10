# Assessment speaking recording and upload

The live speaking item now uses `AssessmentSpeaking` and `useAssessmentRecorder`.

## Learner flow

1. Start recording explicitly requests microphone permission. No microphone is opened on entry.
2. Stop releases microphone tracks and builds a local playable clip. Record again replaces it; no audio has been uploaded yet.
3. Use this recording computes a base64 SHA-256 checksum and allocates an ASSESSMENT upload bound to the response ID.
4. The browser PUTs exactly those bytes to the signed URL with the supplied headers. It never sends application bearer tokens or cookies to storage.
5. POST confirmation verifies the object before the answer is saved with media_upload_id and expected_revision.
6. Only a confirmed answer save advances to the next activity. Optional skip uses the same answer endpoint and an appropriate reason.

## Recovery and resource handling

- Browser-supported WebM/Opus, Ogg/Opus or MP4 is selected without renaming incompatible bytes. Recording requires a supported browser and a secure context (HTTPS or localhost).
- Playback uses a local object URL that is revoked when replaced or unmounted. Streams are stopped on Stop, hidden tab, exit, errors and unmount. Permission results that arrive after exit are discarded and their tracks stopped.
- Client recording is capped at 175 seconds and 10 MiB, below/at backend defaults. Backend configured limits and decoding remain authoritative. Confirmation does not claim speech was recognized; evaluation determines whether evidence is sufficient.
- Audio stays in memory on failed upload/confirmation. Retry reuses the signed ticket where valid. An immutable PUT returning 412 is followed by confirmation, which checks the expected checksum and response binding.
- Expired tickets can be reallocated before answer finalization; abandoned uploads are covered by backend retention cleanup.
- Once answer saving begins, retries keep the exact payload and revision. Re-record/skip is blocked until an uncertain save is resolved. A version conflict offers explicit reload with a download option for the local clip.
- Leaving/reloading before saving loses the in-memory recording. The UI warns; it does not persist audio or signed URLs in browser storage.

## Required deployment configuration

- Existing backend S3 and FFmpeg/ffprobe configuration must be available.
- The storage bucket must allow browser PUT requests from the frontend origin in its CORS rules, including Content-Type, x-amz-checksum-sha256 and If-None-Match headers. API proxy configuration does not replace storage CORS.
- Use HTTPS in production. No AWS credentials belong in the frontend.

Validation: TypeScript, targeted ESLint and whitespace checks. No microphone recording, S3 upload, account mutation or automated test was performed during implementation.

Final review and submission are now connected; see assessment-submission.md. Result reporting and learning-plan handoff are now connected; see assessment-results-handoff.md.
