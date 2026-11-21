"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Archive,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  Rocket,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { extractAdminApiError } from "@/lib/api/admin-content";
import { ReviewAction } from "@/lib/api/admin-content-review";
import {
  useAdminContentItem,
  useContentReviewDecision,
} from "@/hooks/useAdminContentReview";
import { cn } from "@/lib/utils";

function statusClasses(status: string): string {
  switch (status) {
    case "PUBLISHED":
      return "border-emerald-800/70 bg-emerald-950/60 text-emerald-300";
    case "REVIEW":
      return "border-cyan-800/70 bg-cyan-950/60 text-cyan-300";
    case "DRAFT":
      return "border-amber-800/70 bg-amber-950/60 text-amber-300";
    default:
      return "border-neutral-800 bg-neutral-900 text-neutral-400";
  }
}

export default function AdminContentItemDetailPage({
  params,
}: {
  params: Promise<{ itemId: string }>;
}) {
  const { itemId: rawItemId } = use(params);
  const itemId = decodeURIComponent(rawItemId);

  const { data: item, isPending, isError, error } = useAdminContentItem(itemId);
  const decide = useContentReviewDecision(itemId);

  const [reviewNotes, setReviewNotes] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const handleDecision = async (action: ReviewAction) => {
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await decide.mutateAsync({
        action,
        reviewNotes: reviewNotes || undefined,
      });
      setActionSuccess(
        `Updated status to ${updated.status} (including ${updated.words.length} linked word${updated.words.length === 1 ? "" : "s"}).`
      );
    } catch (err) {
      const { message, code } = extractAdminApiError(err);
      setActionError(code ? `${message} (${code})` : message);
    }
  };

  if (isPending) {
    return (
      <div className="rounded-2xl border border-neutral-900 bg-neutral-950 p-8 text-sm text-neutral-400">
        Loading lesson details…
      </div>
    );
  }

  if (isError || !item) {
    return (
      <div className="space-y-4">
        <Link
          href="/admin/content-review"
          className="inline-flex items-center gap-2 text-sm text-neutral-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Content Review
        </Link>
        <div className="rounded-2xl border border-red-900/60 bg-red-950/30 p-6 text-sm text-red-200">
          {extractAdminApiError(error).message}
        </div>
      </div>
    );
  }

  const body = item.body || {};
  const exercises = Array.isArray(body.exercises)
    ? (body.exercises as Record<string, unknown>[])
    : [];
  const privateEval =
    body.private_evaluation && typeof body.private_evaluation === "object"
      ? (body.private_evaluation as Record<string, unknown>)
      : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <Link
            href="/admin/content-review"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-400 hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            All Content Items
          </Link>

          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold text-white">{item.title}</h1>
            <span
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs font-semibold",
                statusClasses(item.status)
              )}
            >
              {item.status}
            </span>
            <span className="rounded-full border border-neutral-800 bg-neutral-900 px-2.5 py-0.5 text-xs text-neutral-300">
              {item.origin}
            </span>
          </div>

          <p className="mt-1 text-xs text-neutral-400">
            {item.cefr_level} · Cycle {item.cycle ?? "—"} · Day {item.day ?? "—"} ·{" "}
            <span className="font-mono text-neutral-300">{item.release_key}</span>
            {item.generation_batch_key && (
              <>
                {" "}
                · Batch{" "}
                <Link
                  href={`/admin/content-generation/batches/${encodeURIComponent(item.generation_batch_key)}`}
                  className="font-mono text-cyan-400 hover:underline"
                >
                  {item.generation_batch_key}
                </Link>
              </>
            )}
          </p>
        </div>
      </div>

      {/* Editorial Decision Bar */}
      <section className="rounded-2xl border border-neutral-900 bg-neutral-950 p-5 space-y-4">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-sm font-semibold text-white">Editorial Decision</h2>
          {item.review_notes && (
            <span className="text-xs text-neutral-400">
              Last note: {item.review_notes}
            </span>
          )}
        </div>

        <textarea
          rows={2}
          maxLength={2000}
          value={reviewNotes}
          onChange={(e) => setReviewNotes(e.target.value)}
          placeholder="Optional editorial review notes (saved on the lesson and its linked words)..."
          className="w-full rounded-lg border border-neutral-800 bg-black px-3 py-2 text-sm text-white placeholder:text-neutral-600 focus:border-cyan-500 focus:outline-none"
        />

        {actionError && (
          <div
            role="alert"
            className="rounded-xl border border-red-900/70 bg-red-950/40 px-4 py-2.5 text-xs text-red-200"
          >
            {actionError}
          </div>
        )}

        {actionSuccess && (
          <div
            role="status"
            className="rounded-xl border border-emerald-900/70 bg-emerald-950/40 px-4 py-2.5 text-xs text-emerald-200"
          >
            {actionSuccess}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            disabled={decide.isPending || item.status === "PUBLISHED"}
            onClick={() => void handleDecision("APPROVE")}
            className="inline-flex items-center gap-1.5 rounded-xl border border-cyan-800 bg-cyan-950/60 px-4 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-900/60 disabled:opacity-40"
          >
            <CheckCircle2 className="h-4 w-4" />
            Approve (REVIEW)
          </button>

          <button
            type="button"
            disabled={decide.isPending || item.status === "PUBLISHED"}
            onClick={() => void handleDecision("REQUEST_CHANGES")}
            className="inline-flex items-center gap-1.5 rounded-xl border border-amber-800 bg-amber-950/50 px-4 py-2 text-xs font-semibold text-amber-200 hover:bg-amber-900/50 disabled:opacity-40"
          >
            <RotateCcw className="h-4 w-4" />
            Send to Draft
          </button>

          <button
            type="button"
            disabled={
              decide.isPending ||
              item.status === "PUBLISHED" ||
              item.status === "ARCHIVED"
            }
            onClick={() => void handleDecision("PUBLISH")}
            className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-black hover:bg-emerald-400 disabled:opacity-40"
          >
            <Rocket className="h-4 w-4" />
            Publish to Learners
          </button>

          <button
            type="button"
            disabled={decide.isPending || item.status === "ARCHIVED"}
            onClick={() => void handleDecision("ARCHIVE")}
            className="inline-flex items-center gap-1.5 rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-2 text-xs font-semibold text-neutral-300 hover:bg-neutral-800 disabled:opacity-40"
          >
            <Archive className="h-4 w-4" />
            Archive
          </button>
        </div>
      </section>

      {/* AI Quality Review */}
      {item.ai_review && (
        <section className="rounded-2xl border border-neutral-900 bg-neutral-950 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-emerald-400" />
              <h2 className="text-sm font-semibold text-white">
                Independent AI Quality Review
              </h2>
            </div>
            {item.ai_review.review_decision && (
              <span className="rounded-full border border-neutral-800 bg-neutral-900 px-2.5 py-0.5 text-xs font-medium text-neutral-200">
                {item.ai_review.review_decision}
              </span>
            )}
          </div>

          {item.ai_review.review_scores && (
            <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(item.ai_review.review_scores).map(
                ([metric, score]) => (
                  <div
                    key={metric}
                    className="rounded-xl border border-neutral-900 bg-black/60 px-3 py-2.5"
                  >
                    <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                      {metric.replaceAll("_", " ")}
                    </p>
                    <p className="mt-1 text-lg font-bold text-white">
                      {score} <span className="text-xs text-neutral-500">/ 5</span>
                    </p>
                  </div>
                )
              )}
            </div>
          )}

          {item.ai_review.warnings.length > 0 && (
            <div className="rounded-xl border border-amber-900/60 bg-amber-950/30 p-3 text-xs text-amber-200 space-y-1">
              <div className="flex items-center gap-1.5 font-semibold">
                <AlertTriangle className="h-3.5 w-3.5" />
                Warnings
              </div>
              <ul className="list-disc pl-5 space-y-0.5">
                {item.ai_review.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* Lesson Overview & Exercises */}
      <section className="rounded-2xl border border-neutral-900 bg-neutral-950 p-6 space-y-5">
        <div className="flex items-center gap-2 border-b border-neutral-900 pb-3">
          <BookOpen className="h-4 w-4 text-cyan-400" />
          <h2 className="text-base font-semibold text-white">
            Lesson Overview &amp; Exercises
          </h2>
        </div>

        <div className="grid gap-4 md:grid-cols-2 text-sm">
          {typeof body.description === "string" && (
            <div>
              <p className="text-xs uppercase tracking-wider text-neutral-500">
                Description
              </p>
              <p className="mt-1 text-neutral-200">{body.description}</p>
            </div>
          )}
          {typeof body.learning_objective === "string" && (
            <div>
              <p className="text-xs uppercase tracking-wider text-neutral-500">
                Learning Objective
              </p>
              <p className="mt-1 text-neutral-200">{body.learning_objective}</p>
            </div>
          )}
          {typeof body.prompt === "string" && (
            <div className="md:col-span-2">
              <p className="text-xs uppercase tracking-wider text-neutral-500">
                Prompt
              </p>
              <p className="mt-1 text-neutral-200">{body.prompt}</p>
            </div>
          )}
          {typeof body.instructions === "string" && (
            <div className="md:col-span-2">
              <p className="text-xs uppercase tracking-wider text-neutral-500">
                Instructions
              </p>
              <p className="mt-1 text-neutral-200">{body.instructions}</p>
            </div>
          )}
        </div>

        {Array.isArray(body.tips) && body.tips.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
              Tips
            </p>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-neutral-300">
              {(body.tips as string[]).map((tip, idx) => (
                <li key={idx}>{tip}</li>
              ))}
            </ul>
          </div>
        )}

        {exercises.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
              Exercises ({exercises.length})
            </h3>
            <div className="space-y-2.5">
              {exercises.map((ex, idx) => (
                <div
                  key={String(ex.item_id ?? idx)}
                  className="rounded-xl border border-neutral-900 bg-black/60 p-4 text-sm space-y-1.5"
                >
                  <div className="flex items-center gap-2 text-xs">
                    <span className="rounded border border-neutral-800 bg-neutral-900 px-2 py-0.5 font-mono text-neutral-300">
                      {String(ex.type ?? "EXERCISE")}
                    </span>
                    <span className="font-mono text-neutral-500">
                      {String(ex.item_id ?? "")}
                    </span>
                  </div>
                  <p className="text-white">{String(ex.prompt ?? "")}</p>
                  {typeof ex.correct_choice === "string" && (
                    <p className="text-xs text-emerald-400">
                      Correct answer: {ex.correct_choice}
                    </p>
                  )}
                  {typeof ex.correct_choice_id === "string" && (
                    <p className="text-xs text-emerald-400">
                      Correct choice ID: {ex.correct_choice_id}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {privateEval && (
          <details className="rounded-xl border border-neutral-900 bg-black/50 p-4 text-xs">
            <summary className="cursor-pointer font-semibold text-neutral-300">
              Private Evaluation Rubric (redacted from learners)
            </summary>
            <pre className="mt-3 overflow-x-auto text-neutral-400">
              {JSON.stringify(privateEval, null, 2)}
            </pre>
          </details>
        )}

        <details className="rounded-xl border border-neutral-900 bg-black/50 p-4 text-xs">
          <summary className="cursor-pointer font-semibold text-neutral-400">
            Raw Lesson Body JSON
          </summary>
          <pre className="mt-3 overflow-x-auto text-neutral-400">
            {JSON.stringify(body, null, 2)}
          </pre>
        </details>
      </section>

      {/* Linked 10 Vocabulary Words */}
      {item.words.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-base font-semibold text-white">
            Linked Vocabulary Words ({item.words.length})
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {item.words.map((word, idx) => {
              const wb = word.body || {};
              const examples = Array.isArray(wb.examples)
                ? (wb.examples as string[])
                : [];
              const collocations = Array.isArray(wb.collocations)
                ? (wb.collocations as string[])
                : [];
              return (
                <div
                  key={word.id}
                  className="rounded-2xl border border-neutral-900 bg-neutral-950 p-4 space-y-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs font-mono text-neutral-500">
                        #{idx + 1}
                      </span>
                      <h3 className="text-base font-bold text-white">
                        {word.title}
                      </h3>
                      {typeof wb.part_of_speech === "string" && (
                        <span className="text-xs italic text-neutral-400">
                          {wb.part_of_speech}
                        </span>
                      )}
                    </div>
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[11px] font-medium",
                        statusClasses(word.status)
                      )}
                    >
                      {word.status}
                    </span>
                  </div>

                  <p className="text-sm text-neutral-300">
                    {String(wb.definition ?? "")}
                  </p>

                  {examples.length > 0 && (
                    <ul className="space-y-1 border-l-2 border-neutral-800 pl-3 text-xs text-neutral-400">
                      {examples.map((ex, i) => (
                        <li key={i}>“{ex}”</li>
                      ))}
                    </ul>
                  )}

                  {collocations.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {collocations.map((col, i) => (
                        <span
                          key={i}
                          className="rounded-md border border-neutral-800 bg-black px-2 py-0.5 text-[11px] text-neutral-400"
                        >
                          {col}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
