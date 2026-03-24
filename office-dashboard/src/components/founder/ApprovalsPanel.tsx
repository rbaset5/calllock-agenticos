"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type FounderApprovalItem,
  fetchFounderApprovals,
  resolveFounderApproval,
} from "@/lib/founder-api";

type DecisionAction = "approved" | "rejected" | "cancelled";

const RISK_RANK: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

function riskClasses(riskLevel: string) {
  switch (riskLevel) {
    case "critical":
    case "high":
      return "bg-rose-500/15 text-rose-100 ring-1 ring-rose-400/30";
    case "medium":
      return "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/30";
    default:
      return "bg-white/10 text-slate-100 ring-1 ring-white/15";
  }
}

function parseAgeToMinutes(age: string) {
  const match = age.match(/^(\d+)(m|h|d)$/);
  if (!match) {
    return 0;
  }

  const value = Number(match[1]);
  const unit = match[2];

  switch (unit) {
    case "d":
      return value * 24 * 60;
    case "h":
      return value * 60;
    default:
      return value;
  }
}

function sortApprovals(items: FounderApprovalItem[]) {
  return [...items].sort((left, right) => {
    const riskDelta =
      (RISK_RANK[left.risk_level] ?? 99) - (RISK_RANK[right.risk_level] ?? 99);
    if (riskDelta !== 0) {
      return riskDelta;
    }

    return parseAgeToMinutes(right.age) - parseAgeToMinutes(left.age);
  });
}

type ApprovalsPanelProps = {
  tenantId?: string | null;
};

export default function ApprovalsPanel({
  tenantId = null,
}: ApprovalsPanelProps) {
  const [items, setItems] = useState<FounderApprovalItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [submittingAction, setSubmittingAction] =
    useState<DecisionAction | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function loadApprovals() {
    const response = await fetchFounderApprovals({ tenantId });
    const sorted = sortApprovals(response.items);
    setItems(sorted);
    setSelectedId((current) => {
      if (current && sorted.some((item) => item.id === current)) {
        return current;
      }

      return sorted[0]?.id ?? null;
    });
  }

  useEffect(() => {
    let active = true;

    setLoading(true);
    setItems([]);
    setSelectedId(null);
    setErrorMessage(null);

    void (async () => {
      try {
        const response = await fetchFounderApprovals({ tenantId });
        if (!active) {
          return;
        }

        const sorted = sortApprovals(response.items);
        setItems(sorted);
        setSelectedId(sorted[0]?.id ?? null);
        setErrorMessage(null);
      } catch (error) {
        if (!active) {
          return;
        }

        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Failed to load founder approvals"
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
  }, [tenantId]);

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId) ?? items[0] ?? null,
    [items, selectedId]
  );

  async function handleDecision(status: DecisionAction) {
    if (!selectedItem?.id) {
      return;
    }

    setSubmittingAction(status);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await resolveFounderApproval(selectedItem.id, {
        status,
        resolution_notes: resolutionNotes.trim() || `Founder ${status}`,
      }, {
        tenantId,
      });

      await loadApprovals();
      setResolutionNotes("");
      setSuccessMessage(
        status === "cancelled"
          ? "Approval deferred."
          : `Approval ${status === "approved" ? "approved" : "denied"}.`
      );
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Failed to resolve approval"
      );
    } finally {
      setSubmittingAction(null);
    }
  }

  if (loading) {
    return (
      <section className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 text-sm text-slate-300 shadow-2xl backdrop-blur">
        Loading approvals...
      </section>
    );
  }

  return (
    <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
      <article className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 shadow-2xl backdrop-blur">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-cyan-300">
              Approvals
            </p>
            <h2 className="mt-2 text-xl font-semibold text-white">
              Pending founder decisions
            </h2>
          </div>
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-300">
            {items.length} open
          </span>
        </div>

        {errorMessage ? (
          <div className="mt-4 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {errorMessage}
          </div>
        ) : null}

        {successMessage ? (
          <div className="mt-4 rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
            {successMessage}
          </div>
        ) : null}

        <div className="mt-5 space-y-3">
          {items.length > 0 ? (
            items.map((item) => {
              const isSelected = item.id === selectedItem?.id;

              return (
                <button
                  key={item.id ?? `${item.title}-${item.age}`}
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                    isSelected
                      ? "border-cyan-300/40 bg-cyan-400/10"
                      : "border-white/10 bg-white/5 hover:bg-white/10"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">
                        {item.title}
                      </p>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">
                        {item.affected_surface}
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${riskClasses(
                        item.risk_level
                      )}`}
                    >
                      {item.risk_level}
                    </span>
                  </div>

                  <p className="mt-3 text-sm leading-6 text-slate-200">
                    {item.reason}
                  </p>
                  <p className="mt-3 text-xs text-slate-400">{item.age}</p>
                </button>
              );
            })
          ) : (
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-sm text-slate-300">
              No pending approvals right now.
            </div>
          )}
        </div>
      </article>

      <article className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-6 shadow-2xl backdrop-blur">
        <p className="text-xs uppercase tracking-[0.28em] text-fuchsia-300">
          Detail
        </p>
        <h2 className="mt-2 text-xl font-semibold text-white">
          {selectedItem?.title ?? "Select an approval"}
        </h2>

        {selectedItem ? (
          <>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                  Affected Surface
                </p>
                <p className="mt-2 text-sm text-white">
                  {selectedItem.affected_surface}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                  Requested Action
                </p>
                <p className="mt-2 text-sm text-white">
                  {selectedItem.requested_action}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                  Risk Level
                </p>
                <p className="mt-2 text-sm text-white">
                  {selectedItem.risk_level}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                  Age
                </p>
                <p className="mt-2 text-sm text-white">{selectedItem.age}</p>
              </div>
            </div>

            <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                Reason
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-100">
                {selectedItem.reason}
              </p>
            </div>

            <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                Evidence Summary
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-100">
                {selectedItem.evidence_summary}
              </p>
            </div>

            <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                Recommended Action
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-100">
                {selectedItem.recommended_action}
              </p>
            </div>

            <label className="mt-5 block">
              <span className="text-xs uppercase tracking-[0.18em] text-slate-500">
                Resolution Notes
              </span>
              <textarea
                value={resolutionNotes}
                onChange={(event) => setResolutionNotes(event.target.value)}
                rows={4}
                className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
                placeholder="Add context for your decision..."
              />
            </label>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <button
                type="button"
                onClick={() => void handleDecision("approved")}
                disabled={submittingAction !== null}
                className="rounded-2xl bg-emerald-500/20 px-4 py-3 text-sm font-medium text-emerald-100 transition hover:bg-emerald-500/30 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submittingAction === "approved" ? "Approving..." : "Approve"}
              </button>
              <button
                type="button"
                onClick={() => void handleDecision("rejected")}
                disabled={submittingAction !== null}
                className="rounded-2xl bg-rose-500/20 px-4 py-3 text-sm font-medium text-rose-100 transition hover:bg-rose-500/30 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submittingAction === "rejected" ? "Denying..." : "Deny"}
              </button>
              <button
                type="button"
                onClick={() => void handleDecision("cancelled")}
                disabled={submittingAction !== null}
                className="rounded-2xl bg-amber-500/20 px-4 py-3 text-sm font-medium text-amber-100 transition hover:bg-amber-500/30 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submittingAction === "cancelled" ? "Deferring..." : "Defer"}
              </button>
            </div>
          </>
        ) : (
          <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-sm text-slate-300">
            No approval selected.
          </div>
        )}
      </article>
    </section>
  );
}
