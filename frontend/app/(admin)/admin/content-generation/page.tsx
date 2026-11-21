"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Clock, Layers, Search, Sparkles } from "lucide-react";
import { z } from "zod";
import {
  extractAdminApiError,
  generateIdempotencyKey,
} from "@/lib/api/admin-content";
import { useCreateBatch, useRecentBatches } from "@/hooks/useAdminContent";

const createBatchSchema = z
  .object({
    day_start: z.number().int().min(1).max(21),
    day_end: z.number().int().min(1).max(21),
    release_key: z
      .string()
      .min(1)
      .max(60)
      .regex(
        /^B1-C1-GENERAL-VOCABULARY-v[1-9][0-9]*$/,
        "Must match B1-C1-GENERAL-VOCABULARY-v1 (or v2, v3, ...)"
      ),
    dry_run: z.boolean(),
  })
  .refine((v) => v.day_end >= v.day_start && v.day_end - v.day_start < 5, {
    message: "Choose 1 to 5 consecutive days in ascending order.",
    path: ["day_end"],
  });

export default function AdminContentGenerationPage() {
  const router = useRouter();
  const createBatch = useCreateBatch();
  const recentBatches = useRecentBatches();

  const [dayStart, setDayStart] = useState(1);
  const [dayEnd, setDayEnd] = useState(5);
  const [releaseKey, setReleaseKey] = useState("B1-C1-GENERAL-VOCABULARY-v1");
  const [dryRun, setDryRun] = useState(true);
  const [lookupKey, setLookupKey] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const startParam = Number(params.get("day_start"));
    const endParam = Number(params.get("day_end"));
    const releaseParam = params.get("release_key");
    const dryRunParam = params.get("dry_run");
    if (Number.isInteger(startParam) && startParam >= 1 && startParam <= 21) {
      setDayStart(startParam);
    }
    if (Number.isInteger(endParam) && endParam >= 1 && endParam <= 21) {
      setDayEnd(endParam);
    }
    if (releaseParam) {
      setReleaseKey(releaseParam);
    }
    if (dryRunParam === "false") {
      setDryRun(false);
    } else if (dryRunParam === "true") {
      setDryRun(true);
    }
  }, []);

  // Keep a stable Idempotency-Key for the current payload until inputs change or it succeeds.
  const idempotencyRef = useRef<{ signature: string; key: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const parsed = createBatchSchema.safeParse({
      day_start: Number(dayStart),
      day_end: Number(dayEnd),
      release_key: releaseKey.trim(),
      dry_run: dryRun,
    });
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message || "Invalid batch settings.");
      return;
    }

    const payload = {
      cefr_level: "B1" as const,
      cycle: 1 as const,
      module: "VOCABULARY" as const,
      goal_variant: "GENERAL" as const,
      ...parsed.data,
    };
    const signature = JSON.stringify(payload);
    if (!idempotencyRef.current || idempotencyRef.current.signature !== signature) {
      idempotencyRef.current = {
        signature,
        key: generateIdempotencyKey("create-batch"),
      };
    }

    try {
      const batch = await createBatch.mutateAsync({
        payload,
        idempotencyKey: idempotencyRef.current.key,
      });
      idempotencyRef.current = null;
      router.push(
        `/admin/content-generation/batches/${encodeURIComponent(batch.generation_batch_key)}`
      );
    } catch (err) {
      const { message, code } = extractAdminApiError(err);
      if (code === "IDEMPOTENCY_CONFLICT") {
        idempotencyRef.current = null;
      }
      setFormError(code ? `${message} (${code})` : message);
    }
  };

  const handleLookup = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = lookupKey.trim();
    if (!trimmed) return;
    router.push(
      `/admin/content-generation/batches/${encodeURIComponent(trimmed)}`
    );
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400">
            Content Factory · Pilot Console
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-white md:text-3xl">
            Content Generation Batches
          </h1>
          <p className="mt-1 text-sm text-neutral-400">
            Queue bounded 1–5 day B1 Vocabulary generation jobs and monitor
            worker progress.
          </p>
        </div>

        <form onSubmit={handleLookup} className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              value={lookupKey}
              onChange={(e) => setLookupKey(e.target.value)}
              placeholder="Open batch key..."
              aria-label="Open batch by key"
              className="w-56 rounded-lg border border-neutral-800 bg-neutral-950 py-2 pl-9 pr-3 text-sm text-white placeholder:text-neutral-500 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={!lookupKey.trim()}
            className="rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm font-medium text-neutral-200 hover:bg-neutral-800 disabled:opacity-40"
          >
            Open
          </button>
        </form>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2 rounded-2xl border border-neutral-900 bg-neutral-950 p-6">
          <div className="flex items-center justify-between border-b border-neutral-900 pb-4">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-emerald-400" />
              <h2 className="text-lg font-semibold text-white">
                Create Vocabulary Batch
              </h2>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-neutral-800 bg-neutral-900 px-2.5 py-1 text-neutral-300">
                B1 · Cycle 1
              </span>
              <span className="rounded-full border border-neutral-800 bg-neutral-900 px-2.5 py-1 text-neutral-300">
                GENERAL · VOCABULARY
              </span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="mt-6 space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="day-start"
                  className="block text-sm font-medium text-neutral-300"
                >
                  Day start (1–21)
                </label>
                <input
                  id="day-start"
                  type="number"
                  min={1}
                  max={21}
                  value={dayStart}
                  onChange={(e) => setDayStart(Number(e.target.value))}
                  className="mt-1.5 w-full rounded-lg border border-neutral-800 bg-black px-3 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div>
                <label
                  htmlFor="day-end"
                  className="block text-sm font-medium text-neutral-300"
                >
                  Day end (max 5 consecutive days)
                </label>
                <input
                  id="day-end"
                  type="number"
                  min={1}
                  max={21}
                  value={dayEnd}
                  onChange={(e) => setDayEnd(Number(e.target.value))}
                  className="mt-1.5 w-full rounded-lg border border-neutral-800 bg-black px-3 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="release-key"
                className="block text-sm font-medium text-neutral-300"
              >
                Release key
              </label>
              <input
                id="release-key"
                type="text"
                value={releaseKey}
                onChange={(e) => setReleaseKey(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-neutral-800 bg-black px-3 py-2 font-mono text-sm text-white focus:border-emerald-500 focus:outline-none"
              />
              <p className="mt-1 text-xs text-neutral-500">
                Pattern: <code className="text-neutral-400">B1-C1-GENERAL-VOCABULARY-v1</code>
              </p>
            </div>

            <label className="flex items-start gap-3 rounded-xl border border-neutral-900 bg-black/60 p-4 cursor-pointer">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-neutral-700 bg-neutral-900 text-emerald-500 focus:ring-emerald-500"
              />
              <div>
                <span className="block text-sm font-medium text-white">
                  Dry run (recommended for smoke tests)
                </span>
                <span className="block text-xs text-neutral-400">
                  Resolves blueprints without making LLM calls or reserving live
                  release day slots.
                </span>
              </div>
            </label>

            {formError && (
              <div
                role="alert"
                className="rounded-xl border border-red-900/70 bg-red-950/40 px-4 py-3 text-sm text-red-200"
              >
                {formError}
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <p className="text-xs text-neutral-500">
                Max 6 provider calls per day unit (30 calls per 5-day batch).
              </p>
              <button
                type="submit"
                disabled={createBatch.isPending}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-black hover:bg-emerald-400 disabled:opacity-50 transition-colors"
              >
                {createBatch.isPending ? "Queueing batch..." : "Queue Batch"}
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </form>
        </section>

        <section className="rounded-2xl border border-neutral-900 bg-neutral-950 p-6">
          <div className="flex items-center gap-2 border-b border-neutral-900 pb-4">
            <Clock className="h-5 w-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Recent Batches</h2>
          </div>

          {recentBatches.length === 0 ? (
            <div className="mt-6 flex flex-col items-center justify-center rounded-xl border border-dashed border-neutral-800 p-6 text-center">
              <Layers className="h-6 w-6 text-neutral-600" />
              <p className="mt-2 text-sm text-neutral-400">
                No batches opened on this browser yet.
              </p>
              <p className="mt-1 text-xs text-neutral-500">
                Queue a batch or paste a batch key above to monitor it.
              </p>
            </div>
          ) : (
            <ul className="mt-4 space-y-2.5">
              {recentBatches.map((item) => (
                <li key={item.batchKey}>
                  <Link
                    href={`/admin/content-generation/batches/${encodeURIComponent(item.batchKey)}`}
                    className="block rounded-xl border border-neutral-900 bg-black/60 p-3.5 hover:border-neutral-700 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-mono text-xs text-neutral-200">
                        {item.batchKey}
                      </span>
                      <span className="shrink-0 rounded-full border border-neutral-800 bg-neutral-900 px-2 py-0.5 text-[11px] font-medium text-neutral-300">
                        {item.status}
                      </span>
                    </div>
                    <div className="mt-1.5 flex items-center justify-between text-xs text-neutral-500">
                      <span>
                        Days {item.dayStart}–{item.dayEnd}
                        {item.dryRun ? " · Dry run" : ""}
                      </span>
                      <span className="truncate max-w-[140px]">
                        {item.releaseKey}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
