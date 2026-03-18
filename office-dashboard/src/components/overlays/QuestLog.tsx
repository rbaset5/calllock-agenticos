"use client";

import { Html } from "@react-three/drei";
import { useMemo, useState } from "react";

import { AGENT_REGISTRY } from "@/components/agents/agent-registry";
import {
  type QuestLogEntry,
  useAgentStore,
} from "@/store/agent-store";

type QuestLogProps = {
  visible: boolean;
};

type ResolutionAction = "approve" | "deny" | "escalate";

const URGENCY_ORDER: Record<string, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

const URGENCY_BADGE_CLASSES: Record<string, string> = {
  high: "bg-rose-500/20 text-rose-200 ring-1 ring-rose-400/30",
  medium: "bg-amber-500/20 text-amber-200 ring-1 ring-amber-400/30",
  low: "bg-emerald-500/20 text-emerald-200 ring-1 ring-emerald-400/30",
};

function humanizeDepartment(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTimeSince(timestamp: string) {
  const createdAt = new Date(timestamp);
  const diffMs = Date.now() - createdAt.getTime();
  const diffMinutes = Math.max(1, Math.floor(diffMs / 60000));

  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function isResolvedToday(quest: QuestLogEntry) {
  if (!quest.resolved_at) {
    return false;
  }

  const resolvedAt = new Date(quest.resolved_at);
  const now = new Date();

  return (
    resolvedAt.getFullYear() === now.getFullYear() &&
    resolvedAt.getMonth() === now.getMonth() &&
    resolvedAt.getDate() === now.getDate()
  );
}

function sortPending(left: QuestLogEntry, right: QuestLogEntry) {
  const urgencyDelta =
    (URGENCY_ORDER[left.urgency] ?? 99) - (URGENCY_ORDER[right.urgency] ?? 99);
  if (urgencyDelta !== 0) {
    return urgencyDelta;
  }

  return right.created_at.localeCompare(left.created_at);
}

function sortResolved(left: QuestLogEntry, right: QuestLogEntry) {
  return (right.resolved_at ?? "").localeCompare(left.resolved_at ?? "");
}

function QuestCard({
  quest,
  onResolve,
  isSubmitting,
}: {
  quest: QuestLogEntry;
  onResolve: (quest: QuestLogEntry, resolution: ResolutionAction) => void;
  isSubmitting: boolean;
}) {
  const agentName = AGENT_REGISTRY[quest.agent_id]?.name ?? quest.agent_id;
  const badgeClass =
    URGENCY_BADGE_CLASSES[quest.urgency] ?? URGENCY_BADGE_CLASSES.medium;

  return (
    <article className="rounded-2xl border border-white/10 bg-slate-900/80 p-4 shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{agentName}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">
            {humanizeDepartment(quest.department)}
          </p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${badgeClass}`}
        >
          {quest.urgency}
        </span>
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-200">{quest.summary}</p>

      <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
        <span>{formatTimeSince(quest.created_at)}</span>
        <span>{quest.rule_violated}</span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <button
          type="button"
          onClick={() => onResolve(quest, "approve")}
          disabled={isSubmitting}
          className="rounded-xl bg-emerald-500/20 px-3 py-2 text-xs font-medium text-emerald-100 transition hover:bg-emerald-500/30 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button"
          onClick={() => onResolve(quest, "deny")}
          disabled={isSubmitting}
          className="rounded-xl bg-rose-500/20 px-3 py-2 text-xs font-medium text-rose-100 transition hover:bg-rose-500/30 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Deny
        </button>
        <button
          type="button"
          onClick={() => onResolve(quest, "escalate")}
          disabled={isSubmitting}
          className="rounded-xl bg-amber-500/20 px-3 py-2 text-xs font-medium text-amber-100 transition hover:bg-amber-500/30 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Escalate
        </button>
      </div>
    </article>
  );
}

export default function QuestLog({ visible }: QuestLogProps) {
  const quests = useAgentStore((state) => state.quests);
  const upsertQuest = useAgentStore((state) => state.upsertQuest);
  const [expandedResolved, setExpandedResolved] = useState(false);
  const [pendingQuestId, setPendingQuestId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const pendingQuests = useMemo(
    () => quests.filter((quest) => quest.status === "pending").sort(sortPending),
    [quests]
  );
  const resolvedToday = useMemo(
    () =>
      quests
        .filter((quest) => quest.status === "resolved" && isResolvedToday(quest))
        .sort(sortResolved),
    [quests]
  );

  async function handleResolve(
    quest: QuestLogEntry,
    resolution: ResolutionAction
  ) {
    setPendingQuestId(quest.id);
    setErrorMessage(null);

    try {
      const response = await fetch("/api/quest/resolve", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          quest_id: quest.id,
          resolution,
          resolved_by: "office-dashboard",
        }),
      });

      const payload = (await response.json()) as {
        quest?: QuestLogEntry;
        error?: string;
      };

      if (!response.ok || !payload.quest) {
        throw new Error(payload.error ?? "Failed to resolve quest");
      }

      upsertQuest(payload.quest);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to resolve quest"
      );
    } finally {
      setPendingQuestId(null);
    }
  }

  return (
    <group>
      <Html fullscreen style={{ pointerEvents: "none" }}>
        <aside
          className={`absolute right-6 top-28 w-[24rem] max-w-[calc(100vw-3rem)] transition ${
            visible
              ? "translate-y-0 opacity-100 pointer-events-auto"
              : "pointer-events-none translate-y-3 opacity-0"
          }`}
        >
          <div className="rounded-[1.75rem] border border-white/10 bg-slate-950/80 p-4 shadow-2xl backdrop-blur-xl">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-cyan-300">
                  Quest Log
                </p>
                <h2 className="mt-2 text-xl font-semibold text-white">
                  Pending Approvals
                </h2>
              </div>
              <div className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-300">
                {pendingQuests.length} open
              </div>
            </div>

            {errorMessage ? (
              <div className="mt-4 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">
                {errorMessage}
              </div>
            ) : null}

            <div className="mt-4 max-h-[28rem] space-y-3 overflow-y-auto pr-1">
              {pendingQuests.length > 0 ? (
                pendingQuests.map((quest) => (
                  <QuestCard
                    key={quest.id}
                    quest={quest}
                    onResolve={handleResolve}
                    isSubmitting={pendingQuestId === quest.id}
                  />
                ))
              ) : (
                <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 text-sm text-slate-300">
                  No pending quests. The policy gate is quiet.
                </div>
              )}
            </div>

            <div className="mt-5 border-t border-white/10 pt-4">
              <button
                type="button"
                onClick={() => setExpandedResolved((value) => !value)}
                className="flex w-full items-center justify-between rounded-2xl bg-white/5 px-3 py-2 text-left text-sm text-slate-200 transition hover:bg-white/10"
              >
                <span>Resolved Today</span>
                <span className="text-xs text-slate-400">
                  {resolvedToday.length} {expandedResolved ? "hide" : "show"}
                </span>
              </button>

              {expandedResolved ? (
                <div className="mt-3 max-h-52 space-y-2 overflow-y-auto pr-1">
                  {resolvedToday.length > 0 ? (
                    resolvedToday.map((quest) => {
                      const agentName =
                        AGENT_REGISTRY[quest.agent_id]?.name ?? quest.agent_id;

                      return (
                        <div
                          key={quest.id}
                          className="rounded-2xl border border-white/10 bg-slate-900/50 px-3 py-3 text-sm text-slate-300"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <span className="font-medium text-white">
                              {agentName}
                            </span>
                            <span className="text-xs text-slate-500">
                              {quest.resolution ?? "resolved"}
                            </span>
                          </div>
                          <p className="mt-1 text-slate-400">{quest.summary}</p>
                        </div>
                      );
                    })
                  ) : (
                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 px-3 py-3 text-sm text-slate-400">
                      No quests resolved yet today.
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        </aside>
      </Html>
    </group>
  );
}
