"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, FileCheck2, RefreshCw } from "lucide-react";
import { extractAdminApiError } from "@/lib/api/admin-content";
import { useAdminContentItems } from "@/hooks/useAdminContentReview";
import { cn } from "@/lib/utils";

const STATUS_TABS = [
  { label: "All", value: "" },
  { label: "Review", value: "REVIEW" },
  { label: "Draft", value: "DRAFT" },
  { label: "Published", value: "PUBLISHED" },
  { label: "Archived", value: "ARCHIVED" },
];

function statusBadgeClasses(status: string): string {
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

export default function AdminContentReviewPage() {
  const [status, setStatus] = useState("");
  const [releaseKey, setReleaseKey] = useState("");
  const [batchKey, setBatchKey] = useState("");
  const [origin, setOrigin] = useState("AI");

  const { data, isPending, isError, error, isFetching, refetch } =
    useAdminContentItems({
      status: status || undefined,
      release_key: releaseKey.trim() || undefined,
      generation_batch_key: batchKey.trim() || undefined,
      origin: origin || undefined,
      limit: 100,
    });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
            Content Factory · Editorial Queue
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-white md:text-3xl">
            Content Review
          </h1>
          <p className="mt-1 text-sm text-neutral-400">
            Inspect generated lessons and their vocabulary words, verify AI
            quality scores, and approve or publish to learners.
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

      <div className="flex flex-col gap-4 rounded-2xl border border-neutral-900 bg-neutral-950 p-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.label}
              type="button"
              onClick={() => setStatus(tab.value)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                status === tab.value
                  ? "bg-white text-black"
                  : "border border-neutral-800 bg-black text-neutral-400 hover:text-white"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
            aria-label="Filter by origin"
            className="rounded-lg border border-neutral-800 bg-black px-3 py-1.5 text-xs text-neutral-200 focus:border-cyan-500 focus:outline-none"
          >
            <option value="AI">AI generated</option>
            <option value="">All origins</option>
            <option value="HUMAN">Human authored</option>
          </select>

          <input
            type="text"
            value={releaseKey}
            onChange={(e) => setReleaseKey(e.target.value)}
            placeholder="Filter release key..."
            className="w-52 rounded-lg border border-neutral-800 bg-black px-3 py-1.5 font-mono text-xs text-white placeholder:text-neutral-600 focus:border-cyan-500 focus:outline-none"
          />

          <input
            type="text"
            value={batchKey}
            onChange={(e) => setBatchKey(e.target.value)}
            placeholder="Filter batch key..."
            className="w-44 rounded-lg border border-neutral-800 bg-black px-3 py-1.5 font-mono text-xs text-white placeholder:text-neutral-600 focus:border-cyan-500 focus:outline-none"
          />
        </div>
      </div>

      {isPending ? (
        <div className="rounded-2xl border border-neutral-900 bg-neutral-950 p-8 text-sm text-neutral-400">
          Loading content items…
        </div>
      ) : isError ? (
        <div className="rounded-2xl border border-red-900/60 bg-red-950/30 p-6 text-sm text-red-200">
          {extractAdminApiError(error).message}
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-neutral-800 bg-neutral-950 p-10 text-center">
          <FileCheck2 className="h-7 w-7 text-neutral-600" />
          <p className="mt-3 text-sm font-medium text-neutral-300">
            No lessons match these filters yet.
          </p>
          <p className="mt-1 text-xs text-neutral-500">
            Run a live batch (<code className="text-neutral-400">dry_run: false</code>) from{" "}
            <Link
              href="/admin/content-generation"
              className="text-emerald-400 underline underline-offset-2"
            >
              Content Batches
            </Link>{" "}
            to generate lessons for review.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-neutral-900 bg-neutral-950">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-900 text-xs uppercase tracking-wider text-neutral-500">
              <tr>
                <th className="px-4 py-3">Day</th>
                <th className="px-4 py-3">Lesson Title</th>
                <th className="px-4 py-3">Module / Level</th>
                <th className="px-4 py-3">Release</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Reviewed</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-900">
              {data.items.map((item) => (
                <tr key={item.id} className="hover:bg-neutral-900/30">
                  <td className="px-4 py-3 font-semibold text-white">
                    {item.day != null ? `Day ${item.day}` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-white">{item.title}</div>
                    {item.generation_batch_key && (
                      <div className="font-mono text-[11px] text-neutral-500">
                        {item.generation_batch_key}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-neutral-300">
                    {item.module ?? item.kind} · {item.cefr_level ?? "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-neutral-400">
                    {item.release_key}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "inline-block rounded-full border px-2.5 py-0.5 text-xs font-semibold",
                        statusBadgeClasses(item.status)
                      )}
                    >
                      {item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-neutral-400">
                    {item.reviewed_at
                      ? new Date(item.reviewed_at).toLocaleDateString()
                      : "Pending"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/admin/content-review/${encodeURIComponent(item.id)}`}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-neutral-800"
                    >
                      Inspect
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
