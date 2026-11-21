"use client";

import { use, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Copy,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import {
  ChildProgress,
  extractAdminApiError,
  generateIdempotencyKey,
  isBatchActive,
} from "@/lib/api/admin-content";
import { useBatchProgress, useRetryBatch } from "@/hooks/useAdminContent";
import { cn } from "@/lib/utils";

function statusPillClasses(status: string): string {
  switch (status) {
    case "SUCCEEDED":
    case "REVIEW":
      return "border-emerald-800/70 bg-emerald-950/60 text-emerald-300";
    case "FAILED":
    case "GENERATION_BUDGET_EXHAUSTED":
      return "border-red-800/70 bg-red-950/60 text-red-300";
    case "RUNNING":
    case "IN_PROGRESS":
      return "border-cyan-800/70 bg-cyan-950/60 text-cyan-300";
    default:
      return "border-neutral-800 bg-neutral-900 text-neutral-300";
  }
}

function isRetryEligible(child: ChildProgress): boolean {
  return child.status === "FAILED" && child.remaining_provider_calls > 0;
}

export default function AdminBatchDetailPage({
  params,
}: {
  params: Promise<{ batchKey: string }>;
}) {
  const { batchKey: rawBatchKey } = use(params);
  const batchKey = decodeURIComponent(rawBatchKey);

  const {
    data: batch,
    isPending,
    isError,
    error,
    isFetching,
    refetch,
  } = useBatchProgress(batchKey);
  const retryBatch = useRetryBatch(batchKey);

  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retrySuccess, setRetrySuccess] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);

  const retryIdempotencyRef = useRef<{ signature: string; key: string } | null>(
    null
  );

  const active = isBatchActive(batch);

  const totals = useMemo(() => {
    if (!batch) {
      return { callsReserved: 0, inputTokens: 0, outputTokens: 0, succeeded: 0, failed: 0 };
    }
    return batch.children.reduce(
      (acc, child) => ({
        callsReserved: acc.callsReserved + child.provider_calls_reserved,
        inputTokens: acc.inputTokens + child.input_tokens,
        outputTokens: acc.outputTokens + child.output_tokens,
        succeeded: acc.succeeded + (child.status === "SUCCEEDED" ? 1 : 0),
        failed: acc.failed + (child.status === "FAILED" ? 1 : 0),
      }),
      { callsReserved: 0, inputTokens: 0, outputTokens: 0, succeeded: 0, failed: 0 }
    );
  }, [batch]);

  const dayRange = useMemo(() => {
    if (!batch || batch.children.length === 0) return { start: 1, end: 1 };
    const days = batch.children.map((c) => c.day);
    return { start: Math.min(...days), end: Math.max(...days) };
  }, [batch]);

  const nextBatchHref = useMemo(() => {
    if (!batch) return "/admin/content-generation";
    const params = new URLSearchParams();
    params.set("release_key", batch.release_key);
    params.set("dry_run", "false");
    if (batch.dry_run) {
      params.set("day_start", String(dayRange.start));
      params.set("day_end", String(dayRange.end));
    } else if (dayRange.end < 21) {
      const nextStart = dayRange.end + 1;
      const nextEnd = Math.min(21, nextStart + (dayRange.end - dayRange.start));
      params.set("day_start", String(nextStart));
      params.set("day_end", String(nextEnd));
    }
    return `/admin/content-generation?${params.toString()}`;
  }, [batch, dayRange]);

  const eligibleFailedChildren = useMemo(
    () => (batch ? batch.children.filter(isRetryEligible) : []),
    [batch]
  );

  const toggleSelect = (jobId: string) => {
    setRetryError(null);
    setRetrySuccess(null);
    setSelectedIds((prev) =>
      prev.includes(jobId) ? prev.filter((id) => id !== jobId) : [...prev, jobId]
    );
  };

  const handleCopyBatchKey = async () => {
    try {
      await navigator.clipboard.writeText(batchKey);
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 1500);
    } catch {
      // Ignore clipboard failures
    }
  };

  const handleRetrySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRetryError(null);
    setRetrySuccess(null);

    const trimmedReason = reason.trim();
    if (selectedIds.length === 0) {
      setRetryError("Select at least one eligible failed day job.");
      return;
    }
    if (!trimmedReason) {
      setRetryError("Provide a reason for retrying the failed jobs.");
      return;
    }

    const payload = {
      child_job_ids: selectedIds,
      reason: trimmedReason,
    };
    const signature = JSON.stringify({
      ids: [...selectedIds].sort(),
      reason: trimmedReason,
    });
    if (
      !retryIdempotencyRef.current ||
      retryIdempotencyRef.current.signature !== signature
    ) {
      retryIdempotencyRef.current = {
        signature,
        key: generateIdempotencyKey("retry-batch"),
      };
    }

    try {
      await retryBatch.mutateAsync({
        payload,
        idempotencyKey: retryIdempotencyRef.current.key,
      });
      retryIdempotencyRef.current = null;
      setSelectedIds([]);
      setReason("");
      setRetrySuccess("Retry queued for selected day jobs.");
    } catch (err) {
      const { message, code } = extractAdminApiError(err);
      if (code === "IDEMPOTENCY_CONFLICT") {
        retryIdempotencyRef.current = null;
      }
      setRetryError(code ? `${message} (${code})` : message);
    }
  };

  if (isPending) {
    return (
      <div className="rounded-2xl border border-neutral-900 bg-neutral-950 p-8 text-sm text-neutral-400">
        Loading batch <span className="font-mono text-white">{batchKey}</span>…
      </div>
    );
  }

  if (isError || !batch) {
    const { message } = extractAdminApiError(error);
    return (
      <div className="space-y-4">
        <Link
          href="/admin/content-generation"
          className="inline-flex items-center gap-2 text-sm text-neutral-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Content Batches
        </Link>
        <div className="rounded-2xl border border-red-900/60 bg-red-950/30 p-6">
          <h1 className="text-lg font-semibold text-red-200">
            Could not load batch
          </h1>
          <p className="mt-1 text-sm text-red-300/80">{message}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <Link
            href="/admin/content-generation"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-400 hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            All Content Batches
          </Link>

          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="font-mono text-xl font-bold text-white md:text-2xl">
              {batch.generation_batch_key}
            </h1>
            <button
              type="button"
              onClick={handleCopyBatchKey}
              className="inline-flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-900 px-2.5 py-1 text-xs text-neutral-300 hover:bg-neutral-800"
              title="Copy batch key"
            >
              {copiedKey ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  Copy
                </>
              )}
            </button>
            <span
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs font-semibold",
                statusPillClasses(batch.status)
              )}
            >
              {batch.status}
            </span>
            {batch.dry_run && (
              <span className="rounded-full border border-amber-800/70 bg-amber-950/50 px-2.5 py-0.5 text-xs font-medium text-amber-300">
                DRY RUN
              </span>
            )}
          </div>

          <p className="mt-1 text-sm text-neutral-400">
            Release <span className="font-mono text-neutral-200">{batch.release_key}</span> ·{" "}
            {batch.child_job_count} day unit{batch.child_job_count === 1 ? "" : "s"}
            {active ? " · Auto-refreshing every 4s" : ""}
          </p>
        </div>

        <button
          type="button"
          onClick={() => void refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 self-start rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-2 text-sm font-medium text-neutral-200 hover:bg-neutral-800 disabled:opacity-50"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          Refresh
        </button>
      </div>

      {batch.status === "GENERATION_COMPLETE" && (
        <div
          role="status"
          className="flex flex-col gap-3 rounded-2xl border border-emerald-800/70 bg-emerald-950/40 p-5 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
            <div>
              <h2 className="text-sm font-semibold text-emerald-200">
                {batch.dry_run
                  ? `Dry run complete — Days ${dayRange.start}–${dayRange.end} blueprints verified`
                  : `Generation complete — ${totals.succeeded} day unit${totals.succeeded === 1 ? "" : "s"} saved`}
              </h2>
              <p className="mt-0.5 text-xs text-emerald-300/80">
                {batch.dry_run
                  ? "No LLM calls were made and no database lessons were written. You can now queue a live generation batch for these days."
                  : "All generated lessons are saved in DRAFT/REVIEW status and ready for editorial inspection."}
              </p>
            </div>
          </div>
          <Link
            href={nextBatchHref}
            className="inline-flex shrink-0 items-center gap-2 self-start rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-black hover:bg-emerald-400 transition-colors sm:self-center"
          >
            {batch.dry_run
              ? "Queue Live Batch"
              : dayRange.end < 21
              ? "Queue Next Days"
              : "Back to Batches"}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}

      <div className="flex items-start gap-3 rounded-xl border border-neutral-800 bg-neutral-950 px-4 py-3 text-xs text-neutral-400">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
        <span>
          Batch generation status tracks worker execution only — it does{" "}
          <strong className="text-neutral-200">not</strong> mean a release is
          ready to publish. Complete 21-day validation and editorial approval
          are still required before learners see generated lessons.
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-neutral-900 bg-neutral-950 p-4">
          <p className="text-xs text-neutral-500">Day units</p>
          <p className="mt-1 text-2xl font-bold text-white">
            {totals.succeeded} / {batch.child_job_count}
          </p>
          <p className="mt-0.5 text-xs text-neutral-400">
            {totals.failed > 0 ? `${totals.failed} failed` : "Succeeded"}
          </p>
        </div>
        <div className="rounded-2xl border border-neutral-900 bg-neutral-950 p-4">
          <p className="text-xs text-neutral-500">Provider calls reserved</p>
          <p className="mt-1 text-2xl font-bold text-white">
            {totals.callsReserved}
          </p>
          <p className="mt-0.5 text-xs text-neutral-400">
            Max {batch.child_job_count * 6} for this batch
          </p>
        </div>
        <div className="rounded-2xl border border-neutral-900 bg-neutral-950 p-4">
          <p className="text-xs text-neutral-500">Input tokens recorded</p>
          <p className="mt-1 text-2xl font-bold text-white">
            {totals.inputTokens.toLocaleString()}
          </p>
          <p className="mt-0.5 text-xs text-neutral-400">
            Observed before parse validation
          </p>
        </div>
        <div className="rounded-2xl border border-neutral-900 bg-neutral-950 p-4">
          <p className="text-xs text-neutral-500">Output tokens recorded</p>
          <p className="mt-1 text-2xl font-bold text-white">
            {totals.outputTokens.toLocaleString()}
          </p>
          <p className="mt-0.5 text-xs text-neutral-400">
            Across generation &amp; AI review
          </p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-neutral-900 bg-neutral-950">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-neutral-900 text-xs uppercase tracking-wider text-neutral-500">
            <tr>
              <th className="px-4 py-3 w-10">Retry</th>
              <th className="px-4 py-3">Day</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Stage</th>
              <th className="px-4 py-3">Attempts</th>
              <th className="px-4 py-3">Item</th>
              <th className="px-4 py-3">Call Budget</th>
              <th className="px-4 py-3">Tokens (In / Out)</th>
              <th className="px-4 py-3">Error</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-900">
            {batch.children.map((child) => {
              const eligible = isRetryEligible(child);
              const checked = selectedIds.includes(child.job_id);
              return (
                <tr key={child.job_id} className="hover:bg-neutral-900/30">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      disabled={!eligible}
                      checked={checked}
                      onChange={() => toggleSelect(child.job_id)}
                      aria-label={`Select day ${child.day} for retry`}
                      title={
                        eligible
                          ? "Select failed job to retry"
                          : child.status === "FAILED"
                          ? "No remaining provider call budget"
                          : "Only failed jobs with remaining budget can be retried"
                      }
                      className="h-4 w-4 rounded border-neutral-700 bg-neutral-900 text-emerald-500 disabled:opacity-30"
                    />
                  </td>
                  <td className="px-4 py-3 font-semibold text-white">
                    Day {child.day}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium",
                        statusPillClasses(child.status)
                      )}
                    >
                      {child.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-neutral-300">
                    {child.stage}
                  </td>
                  <td className="px-4 py-3 text-neutral-300">{child.attempts}</td>
                  <td className="px-4 py-3">
                    {child.item_status ? (
                      <div className="flex flex-col gap-1">
                        <span
                          className={cn(
                            "inline-block w-fit rounded-full border px-2 py-0.5 text-xs",
                            statusPillClasses(child.item_status)
                          )}
                        >
                          {child.item_status}
                        </span>
                        {child.lesson_id && (
                          <Link
                            href={`/admin/content-review/${encodeURIComponent(child.lesson_id)}`}
                            className="font-mono text-[11px] text-cyan-400 hover:text-cyan-300 underline underline-offset-2"
                            title={`Inspect lesson ${child.lesson_id}`}
                          >
                            Review {child.lesson_id.slice(0, 8)}…
                          </Link>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-neutral-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-neutral-300">
                    {child.provider_calls_reserved} used ·{" "}
                    <span className="text-neutral-400">
                      {child.remaining_provider_calls} left
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-neutral-400">
                    {child.input_tokens.toLocaleString()} /{" "}
                    {child.output_tokens.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-red-300">
                    {child.error_code ?? <span className="text-neutral-600">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {eligibleFailedChildren.length > 0 && (
        <section className="rounded-2xl border border-neutral-900 bg-neutral-950 p-6">
          <div className="flex items-center gap-2">
            <RotateCcw className="h-5 w-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-white">
              Retry Failed Day Units
            </h2>
          </div>
          <p className="mt-1 text-xs text-neutral-400">
            Select failed day checkboxes above and provide an operator reason.
            Attempt counts and call budgets are preserved.
          </p>

          <form onSubmit={handleRetrySubmit} className="mt-4 space-y-4">
            <div>
              <label
                htmlFor="retry-reason"
                className="block text-sm font-medium text-neutral-300"
              >
                Retry reason ({selectedIds.length} selected)
              </label>
              <textarea
                id="retry-reason"
                rows={2}
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g., Provider configuration corrected"
                className="mt-1.5 w-full rounded-lg border border-neutral-800 bg-black px-3 py-2 text-sm text-white placeholder:text-neutral-600 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            {retryError && (
              <div
                role="alert"
                className="rounded-xl border border-red-900/70 bg-red-950/40 px-4 py-3 text-sm text-red-200"
              >
                {retryError}
              </div>
            )}

            {retrySuccess && (
              <div
                role="status"
                className="rounded-xl border border-emerald-900/70 bg-emerald-950/40 px-4 py-3 text-sm text-emerald-200"
              >
                {retrySuccess}
              </div>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={retryBatch.isPending || selectedIds.length === 0}
                className="inline-flex items-center gap-2 rounded-xl bg-amber-400 px-4 py-2 text-sm font-semibold text-black hover:bg-amber-300 disabled:opacity-40 transition-colors"
              >
                <RotateCcw className="h-4 w-4" />
                {retryBatch.isPending ? "Queueing retry..." : "Retry Selected"}
              </button>
            </div>
          </form>
        </section>
      )}
    </div>
  );
}
