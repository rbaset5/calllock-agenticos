"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type FounderApprovalItem,
  type FounderBlockedWorkItem,
  type FounderHomeResponse,
  type FounderIssueThread,
  type FounderVoiceTruthSummary,
  fetchFounderHome,
} from "@/lib/founder-api";

function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return "Not evaluated yet";
  }

  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function voiceTruthClasses(state: string) {
  switch (state) {
    case "pass":
      return "bg-emerald-500/15 text-emerald-100 ring-1 ring-emerald-400/30";
    case "block":
      return "bg-rose-500/15 text-rose-100 ring-1 ring-rose-400/30";
    case "escalate":
      return "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/30";
    default:
      return "bg-white/10 text-slate-200 ring-1 ring-white/15";
  }
}

function describeTopChange(
  topChange:
    | FounderApprovalItem
    | FounderBlockedWorkItem
    | FounderIssueThread
    | FounderVoiceTruthSummary
    | null
) {
  if (!topChange) {
    return "No major change captured yet.";
  }

  if ("title" in topChange) {
    return `Approval: ${topChange.title}`;
  }

  if ("blocked_reason" in topChange) {
    return `Blocked work: ${topChange.blocked_reason}`;
  }

  if ("incident_key" in topChange) {
    return `Issue thread: ${topChange.alert_type ?? topChange.incident_key}`;
  }

  return `Voice truth: ${topChange.top_reason}`;
}

function IssueThreadRow({ thread }: { thread: FounderIssueThread }) {
  return (
    <li className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-white">
            {thread.alert_type ?? thread.incident_key}
          </p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">
            {thread.incident_domain ?? "issue"} / {thread.incident_category ?? "thread"}
          </p>
        </div>
        <span className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-medium text-slate-200">
          {thread.severity ?? "unknown"}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
        <span>Workflow: {thread.workflow_status ?? "new"}</span>
        <span>Notify: {thread.notification_outcome}</span>
      </div>
    </li>
  );
}

export default function HomePanel() {
  const [data, setData] = useState<FounderHomeResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const response = await fetchFounderHome();
        if (!active) {
          return;
        }

        setData(response);
        setErrorMessage(null);
      } catch (error) {
        if (!active) {
          return;
        }

        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load founder home"
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

  const issueThreads = useMemo(
    () => data?.issue_posture.active_threads ?? [],
    [data]
  );

  if (loading) {
    return (
      <section className="mx-auto max-w-6xl px-6 py-10">
        <div className="rounded-[2rem] border border-white/10 bg-slate-950/70 p-6 text-sm text-slate-300 shadow-2xl backdrop-blur">
          Loading founder home...
        </div>
      </section>
    );
  }

  if (errorMessage) {
    return (
      <section className="mx-auto max-w-6xl px-6 py-10">
        <div className="rounded-[2rem] border border-rose-400/30 bg-rose-500/10 p-6 text-sm text-rose-100 shadow-2xl">
          {errorMessage}
        </div>
      </section>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <section className="mx-auto max-w-6xl px-6 py-10">
      <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <article className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 shadow-2xl backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-cyan-300">
                Briefing
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-white">
                What needs your judgment now
              </h2>
            </div>
            <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-300">
              {formatTimestamp(data.briefing.generated_at)}
            </span>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                Top Change
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-100">
                {describeTopChange(data.briefing.top_change)}
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                Recommended Action
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-100">
                {data.briefing.recommended_action}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                Pending Approval
              </p>
              <p className="mt-2 text-sm text-white">
                {data.briefing.top_pending_approval?.title ?? "None"}
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                Top Issue
              </p>
              <p className="mt-2 text-sm text-white">
                {data.briefing.top_issue_thread?.alert_type ??
                  data.briefing.top_issue_thread?.incident_key ??
                  "None"}
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
                Top Blocked Work
              </p>
              <p className="mt-2 text-sm text-white">
                {data.briefing.top_blocked_work?.blocked_reason ?? "None"}
              </p>
            </div>
          </div>
        </article>

        <div className="grid gap-6">
          <article className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 shadow-2xl backdrop-blur">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-amber-300">
                  Voice Truth
                </p>
                <h2 className="mt-2 text-xl font-semibold text-white">
                  Current gate posture
                </h2>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${voiceTruthClasses(
                  data.voice_truth.state
                )}`}
              >
                {data.voice_truth.state}
              </span>
            </div>

            <p className="mt-4 text-sm leading-6 text-slate-200">
              {data.voice_truth.top_reason}
            </p>

            <dl className="mt-4 grid gap-3 text-sm text-slate-300">
              <div className="flex items-center justify-between gap-4">
                <dt>Last evaluated</dt>
                <dd>{formatTimestamp(data.voice_truth.last_evaluated_at)}</dd>
              </div>
              <div className="flex items-center justify-between gap-4">
                <dt>Failed metrics</dt>
                <dd>{data.voice_truth.failed_metric_count}</dd>
              </div>
            </dl>
          </article>

          <article className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 shadow-2xl backdrop-blur">
            <p className="text-xs uppercase tracking-[0.28em] text-sky-300">
              Active Priority
            </p>
            <p className="mt-3 text-lg font-medium text-white">
              {data.active_priority.label ?? "No active priority set"}
            </p>
            {data.active_priority.constraints.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {data.active_priority.constraints.map((constraint) => (
                  <span
                    key={constraint}
                    className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-200"
                  >
                    {constraint}
                  </span>
                ))}
              </div>
            ) : null}
          </article>
        </div>
      </div>

      <article className="mt-6 rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 shadow-2xl backdrop-blur">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-fuchsia-300">
              Issue Posture
            </p>
            <h2 className="mt-2 text-xl font-semibold text-white">
              Meaningful active threads
            </h2>
          </div>
          <div className="rounded-2xl bg-white/5 px-4 py-2 text-right text-sm text-slate-300">
            <div>{data.issue_posture.counts.open_threads} open</div>
            <div>{data.issue_posture.counts.founder_visible_threads} founder-visible</div>
          </div>
        </div>

        <div className="mt-5">
          {issueThreads.length > 0 ? (
            <ul className="grid gap-3 lg:grid-cols-2">
              {issueThreads.map((thread) => (
                <IssueThreadRow
                  key={thread.incident_id}
                  thread={thread}
                />
              ))}
            </ul>
          ) : (
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-sm text-slate-300">
              No founder-visible issue threads right now.
            </div>
          )}
        </div>
      </article>
    </section>
  );
}
