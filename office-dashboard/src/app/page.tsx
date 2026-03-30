"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo } from "react";

import { subscribeToOfficeRealtime } from "@/lib/supabase-realtime";
import { useAgentStore } from "@/store/agent-store";

const OfficeScene = dynamic(() => import("@/components/office-scene"), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">
      Loading 3D office...
    </div>
  ),
});

export default function Home() {
  const agents = useAgentStore((state) => state.agents);
  const quests = useAgentStore((state) => state.quests);
  const connectionStatus = useAgentStore((state) => state.connectionStatus);

  useEffect(() => {
    const unsubscribe = subscribeToOfficeRealtime();
    return unsubscribe;
  }, []);

  const agentCount = agents.size;
  const pendingQuestCount = useMemo(
    () => quests.filter((quest) => quest.status === "pending").length,
    [quests]
  );

  return (
    <main className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,#1f2937_0%,#0f172a_55%,#020617_100%)] text-slate-100">
      <OfficeScene />

      <section className="pointer-events-none absolute inset-x-0 top-0 flex flex-col gap-4 p-6">
        <div className="max-w-sm rounded-2xl border border-white/10 bg-slate-950/70 p-4 shadow-2xl backdrop-blur">
          <p className="text-xs uppercase tracking-[0.3em] text-orange-300">
            Office Dashboard
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-white">
            Agent Office Prototype
          </h1>
          <p className="mt-2 text-sm text-slate-300">
            Placeholder Three Fiber scene with Supabase Realtime wiring for
            <code className="mx-1 rounded bg-white/10 px-1 py-0.5 text-xs">
              agent_office_state
            </code>
            and
            <code className="mx-1 rounded bg-white/10 px-1 py-0.5 text-xs">
              quest_log
            </code>
            .
          </p>
        </div>

        <div className="grid max-w-3xl gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">
              Connection
            </p>
            <p className="mt-2 text-lg font-medium capitalize">{connectionStatus}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">
              Agents
            </p>
            <p className="mt-2 text-lg font-medium">{agentCount}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">
              Pending Quests
            </p>
            <p className="mt-2 text-lg font-medium">{pendingQuestCount}</p>
          </div>
        </div>
      </section>
    </main>
  );
}
