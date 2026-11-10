# Speaking dispatcher and worker

The shared outbox dispatcher now validates and routes both assessment and
Speaking events. SPEAKING_FEEDBACK_REQUESTED goes to talkfiesta.speaking.execute
on the durable talkfiesta.speaking queue. Payloads contain only job/submission
UUIDs. Assessment routing remains on talkfiesta.assessments.

## Deployment

Apply the existing Speaking submit/draft migrations first. This worker change
requires no new migration. Configure PostgreSQL, Redis, S3 credentials/bucket,
OPENAI_API_KEY and the existing transcription/evaluation model settings.

Set SPEAKING_EXECUTION_ENABLED=true on the worker, dispatcher and recovery
process. Set OUTBOX_DISPATCH_ENABLED=true on the dispatcher. Assessment execution
can be enabled independently. Disabled job types remain unpublished. The
dispatcher verifies every enabled task is registered before claiming events.

Run from backend in Linux/WSL/Docker (Celery prefork production workers):

```sh
python -m celery -A app.infrastructure.messaging.celery_app:celery_app worker -Q talkfiesta.speaking --pool=prefork --loglevel=INFO
python -m app.workers.dispatch_outbox
python -m app.workers.recover_jobs --loop --interval 20
```

Run the existing assessment worker separately or subscribe a worker to both
queues. Do not enable dispatch until workers with matching flags are deployed.
No processes were started and no .env secrets/settings were changed by this work.

## Processing and recovery

1. Lock user -> owned recorded-speaking submission -> job. Accepted submissions
   only. Duplicate deliveries with a live lease or terminal job do nothing.
2. Assign a fresh claim token, increment attempts, mark job RUNNING and evaluation
   PROCESSING. The fixed lease uses ASSESSMENT_JOB_LEASE_SECONDS (shared execution
   timing, default 360s), validated to exceed the Celery hard timeout.
3. Load validated frozen input, matching content version, verified upload metadata
   and the owned completion credit. Store an evidence fingerprint in job metrics.
   Published or archived pinned lessons are accepted; current module day is not
   used because acceptance has already advanced progress.
4. Download bounded, checksum-verified S3 audio outside DB transactions and
   transcribe using the existing OpenAI helper. Save the original transcript and
   its hash under the live claim. Subsequent attempts reuse it without another
   transcription, including after audio retention expires. Empty text is a valid
   no-speech transcript; unavailable audio without a transcript is a failure.
5. A two-node LangGraph pipeline runs transcription then structured transcript
   coaching through LangChain. Validate bounded feedback and exact original
   correction quotes. Calculate approximate words per recording minute locally.
6. Persist feedback and mark evaluation COMPLETED/job SUCCEEDED under the same
   token, unexpired lease, unchanged evidence and transcript hash. Late workers
   cannot overwrite results after a lease is lost. Never rewrite transcript with
   the improved example answer.

SPEAKING_JOB_MAX_ATTEMPTS defaults to 3. Transient provider/storage failures,
invalid provider output and soft timeouts get bounded PostgreSQL backoff.
Permanent failures or exhausted attempts mark evaluation FAILED. Recovery handles
expired worker leases and missing broker deliveries, creating replacement outbox
events after the retry/visibility deadline. Quarantined unpublished outbox events
remain an operator responsibility. Broker redelivery is not assumed to dedupe.

No completion, progress or plan records are modified by worker success/failure.
Retention cleanup excludes media referenced by a Speaking job with a live lease.
Accepted recordings still have the existing retention deadline; pending jobs do
not indefinitely retain recordings. Provider calls may repeat after a crash
before their results commit; exactly-once billing is not guaranteed.

## Feedback and privacy

speaking-feedback-v1 provides grammar, vocabulary, coherence and task-relevance
coaching scores, corrections, strengths, next steps and an improved example.
Scores are provisional 0–100 coaching indicators, not calibrated CEFR placement.
Pronunciation and pause counts stay null: no acoustic grading is implemented.
No usable speech yields COMPLETED with reviewable=false, NO_USABLE_SPEECH,
null scores and empty coaching lists. Approximate WPM includes recording silence.

LangSmith uses the existing configured redacted client with Speaking metadata.
Keep LANGSMITH_REDACT_LEARNER_TEXT=true; errors log IDs and exception types only.
The stored feedback is exposed through the owner-scoped submission GET endpoint
documented in speaking-results.md.

The provider integration retains JSON transcription, as documented in the
[official OpenAI speech-to-text guide](https://developers.openai.com/api/docs/guides/speech-to-text).
The wrapper now permits Speaking's size cap without changing assessment defaults.

Validation: Ruff, imports, task registration, response-schema generation,
PostgreSQL retention query compilation and diff checks. No tests, live database
queries, broker publishing, storage access, transcription or evaluation calls ran.
