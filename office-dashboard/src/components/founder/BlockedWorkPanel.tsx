"use client";

import { useEffect, useState } from "react";

import {
  type FounderBlockedWorkItem,
  fetchFounderBlockedWork,
} from "@/lib/founder-api";

function stateClasses(state: string) {
  switch (state) {
    case "block":
      return "bg-rose-500/15 text-rose-100 ring-1 ring-rose-400/30";
    case "escalate":
      return "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/30";
    case "retry":
      return "bg-sky-500/15 text-sky-100 ring-1 ring-sky-400/30";
    default:
      return "bg-white/10 text-slate-100 ring-1 ring-white/15";
  }
}

function BlockedWorkRow({ item }: { item: FounderBlockedWorkItem }) {
  return (
    <article className="rounded-[1.75rem] border border-white/10 bg-slate-950/75 p-5 shadow-2xl backdrop-blur">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">
            {item.worker_id ?? "unknown-worker"}
          </p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">
            {item.task_type ?? "unknown-task"}
          </p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] ${stateClasses(
            item.state
          )}`}
        >
          {item.state}
        </span>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_0.8fr]">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
            Blocked Reason
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-100">
            {item.blocked_reason}
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
            Recommended Next Step
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-100">
            {item.recommended_next_step ?? "Inspect supporting artifacts."}
          </p>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
          Supporting Artifacts
        </p>
        {item.artifact_refs.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {item.artifact_refs.map((artifact, index) => (
              <li
                key={
                  artifact.id ??
                  `${artifact.run_id}-${artifact.artifact_type}-${index}`
                }
                className="rounded-2xl border border-white/10 bg-slate-950/50 px-3 py-3 text-sm text-slate-200"
              >
                <p className="font-medium text-white">
                  {artifact.artifact_type ?? "artifact"}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Run {artifact.run_id ?? "unknown"} · Created{" "}
                  {artifact.created_at ?? "unknown"}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-300">
            No supporting artifacts are attached yet.
          </p>
        )}
      </div>
    </article>
  );
}

export default function BlockedWorkPanel() {
  const [items, setItems] = useState<FounderBlockedWorkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const response = await fetchFounderBlockedWork();
        if (!active) {
          return;
        }

        setItems(response.items);
        setErrorMessage(null);
      } catch (error) {
        if (!active) {
          return;
        }

        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Failed to load blocked work"
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <section className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 text-sm text-slate-300 shadow-2xl backdrop-blur">
        Loading blocked work...
      </section>
    );
  }

  if (errorMessage) {
    return (
      <section className="rounded-[2rem] border border-rose-400/30 bg-rose-500/10 p-6 text-sm text-rose-100 shadow-2xl">
        {errorMessage}
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 shadow-2xl backdrop-blur">
        <p className="text-xs uppercase tracking-[0.28em] text-amber-300">
          Blocked Work
        </p>
        <h2 className="mt-2 text-xl font-semibold text-white">
          Proposed changes that need inspection
        </h2>
      </div>

      {items.length > 0 ? (
        items.map((item) => (
          <BlockedWorkRow
            key={item.id ?? `${item.worker_id}-${item.task_type}-${item.blocked_reason}`}
            item={item}
          />
        ))
      ) : (
        <div className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 text-sm text-slate-300 shadow-2xl backdrop-blur">
          No blocked or escalated work right now.
        </div>
      )}
    </section>
  );
}
