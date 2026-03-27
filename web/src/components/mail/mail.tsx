"use client"

import * as React from "react"
import Image from "next/image"
import {
  Activity as ActivityIcon,
  ChevronLeft,
  Headset,
  LayoutDashboard,
  Phone,
  Settings as SettingsIcon,
} from "lucide-react"
import type { Call, CallbackOutcome } from "@/types/call"
import type { TriageResult } from "@/types/call"
import { triageSort, computeTriage, assignBucket, followUpSort } from "@/lib/triage"
import type { BucketAssignment } from "@/lib/triage"
import { useRealtimeCalls } from "@/hooks/use-realtime-calls"
import { useReadState } from "@/hooks/use-read-state"
import { MailList } from "./mail-list"
import { MailDisplay } from "./mail-display"
import { LeadIntel } from "./lead-intel"
import { PulseBar } from "./pulse-bar"

interface MailProps {
  initialCalls: Call[]
}

export function Mail({ initialCalls }: MailProps) {
  const [mobileView, setMobileView] = React.useState<"list" | "detail">("list")
  const [selectedId, setSelectedId] = React.useState<string | null>(() => {
    try {
      const stored = sessionStorage.getItem("calllock_selectedId")
      if (stored && initialCalls.some((c) => c.id === stored)) return stored
    } catch {
      // sessionStorage unavailable (private browsing)
    }
    return initialCalls[0]?.id ?? null
  })

  const { readIds, markAsRead } = useReadState()
  const { calls } = useRealtimeCalls(initialCalls, readIds, false)

  const [now, setNow] = React.useState(Date.now)

  // Optimistic overlay for callback outcomes
  const [optimisticOverrides, setOptimisticOverrides] = React.useState<
    Record<string, { callbackOutcome: CallbackOutcome | null; callbackOutcomeAt: string | null }>
  >({})

  // Merge optimistic overrides into calls
  const mergedCalls = React.useMemo(
    () => calls.map((c) => {
      const override = optimisticOverrides[c.id]
      return override ? { ...c, ...override } : c
    }),
    [calls, optimisticOverrides]
  )

  // Compute triage map once per tick
  const triageMap = React.useMemo(() => {
    const map = new Map<string, TriageResult>()
    for (const call of mergedCalls) {
      map.set(call.id, computeTriage(call, now))
    }
    return map
  }, [mergedCalls, now])

  // Bucket assignment: split calls into ACTION_QUEUE (New Leads + Follow-ups) and AI_HANDLED
  const { buckets, bucketMap } = React.useMemo(() => {
    const newLeads: Call[] = []
    const followUps: Call[] = []
    const aiHandled: Call[] = []
    const map = new Map<string, BucketAssignment>()

    for (const call of mergedCalls) {
      const assignment = assignBucket(call)
      map.set(call.id, assignment)

      if (assignment.bucket === "ACTION_QUEUE" && assignment.subGroup === "FOLLOW_UP") {
        followUps.push(call)
      } else if (assignment.bucket === "ACTION_QUEUE") {
        newLeads.push(call)
      } else {
        aiHandled.push(call)
      }
    }

    return {
      buckets: {
        NEW_LEADS: triageSort(newLeads, now),
        FOLLOW_UPS: followUpSort(followUps),
        AI_HANDLED: aiHandled.sort(
          (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        ),
      },
      bucketMap: map,
    }
  }, [mergedCalls, now])

  // Unified feed: New Leads → Follow-ups → AI Handled
  const allSectionedCalls = React.useMemo(
    () => [...buckets.NEW_LEADS, ...buckets.FOLLOW_UPS, ...buckets.AI_HANDLED],
    [buckets]
  )

  // Actionable calls (for auto-select)
  const actionableCalls = React.useMemo(
    () => [...buckets.NEW_LEADS, ...buckets.FOLLOW_UPS],
    [buckets]
  )

  const selectedCall = mergedCalls.find((c) => c.id === selectedId) ?? null

  // Post-call pulse behavior
  const lastCallBackRef = React.useRef<{ id: string; time: number } | null>(null)
  const [pulsingId, setPulsingId] = React.useState<string | null>(null)

  React.useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState !== "visible") return
      const ref = lastCallBackRef.current
      if (!ref) return
      if (Date.now() - ref.time < 300_000) {
        setPulsingId(ref.id)
        setTimeout(() => setPulsingId(null), 3_000)
      }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange)
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange)
  }, [])

  const handleCallBackTap = React.useCallback((callId: string) => {
    lastCallBackRef.current = { id: callId, time: Date.now() }
  }, [])

  // Stale-recompute timer
  React.useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(interval)
  }, [])

  // Optimistic outcome handler
  const handleOutcomeChange = React.useCallback(
    (callId: string, outcome: CallbackOutcome | null) => {
      setOptimisticOverrides((prev) => ({
        ...prev,
        [callId]: { callbackOutcome: outcome, callbackOutcomeAt: new Date().toISOString() },
      }))
    },
    []
  )

  // Clear optimistic overrides when realtime confirms
  React.useEffect(() => {
    setOptimisticOverrides((prev) => {
      const next = { ...prev }
      let changed = false
      for (const [id, override] of Object.entries(next)) {
        const real = calls.find((c) => c.id === id)
        if (real && real.callbackOutcome === override.callbackOutcome) {
          delete next[id]
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [calls])

  // Pulse bar counts
  const pulseBarCounts = React.useMemo(() => ({
    leads: buckets.NEW_LEADS.length,
    followUps: buckets.FOLLOW_UPS.length,
    aiHandled: buckets.AI_HANDLED.length,
  }), [buckets])

  // Auto-select first actionable item (only from Action Queue, not AI Handled)
  React.useEffect(() => {
    if (actionableCalls.length > 0 && !actionableCalls.find((c) => c.id === selectedId)) {
      setSelectedId(actionableCalls[0].id)
    } else if (actionableCalls.length === 0) {
      setSelectedId(null)
    }
  }, [actionableCalls, selectedId])

  const handleSelect = (id: string) => {
    setSelectedId(id)
    markAsRead(id)
    setMobileView("detail")
    try { sessionStorage.setItem("calllock_selectedId", id) } catch { /* ignore */ }
  }

  const clearPulse = React.useCallback(() => setPulsingId(null), [])

  const actionQueueEmpty = buckets.NEW_LEADS.length === 0 && buckets.FOLLOW_UPS.length === 0

  return (
    <>
      {/* ── Mobile Top App Bar ── */}
      <header className="fixed top-0 left-0 w-full z-50 md:hidden flex justify-between items-center px-6 h-16 bg-[#0e0e0e]">
        <span className="text-xl font-headline font-bold tracking-tighter text-[#e7e5e4]">
          CallLock
        </span>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-[#10b981]/20 bg-[#10b981]/5">
            <Phone className="h-3 w-3 text-[#10b981]/70" />
          </div>
          <button className="p-2 text-[#c6c6c7] hover:bg-[#252626] rounded-[6px] transition-all">
            <SettingsIcon className="h-5 w-5" />
          </button>
          <div className="w-8 h-8 rounded-full bg-[#252626] flex items-center justify-center text-[#c6c6c7] text-xs font-bold font-headline">
            R
          </div>
        </div>
      </header>

      {/* ── Desktop Left Navigation Rail ── */}
      <aside className="group/sidebar fixed left-0 top-0 z-50 hidden md:flex h-screen w-14 hover:w-64 flex-col bg-[#0e0e0e] transition-[width] duration-200 ease-out overflow-hidden">
        <div className="h-14 px-1 group-hover/sidebar:px-1 flex items-center justify-center group-hover/sidebar:justify-start transition-all duration-200">
          <div className="h-12 w-12 mt-2 -ml-1 group-hover/sidebar:ml-0 rounded-[8px] flex items-center justify-center transition-all duration-200">
            <Image
              src="/calllock-logo.png"
              alt="CallLock logo"
              width={48}
              height={48}
              className="h-12 w-12 object-contain transition-all duration-200"
            />
          </div>
          <span className="ml-0 mt-2 text-sm font-medium text-[#e7e5e4] whitespace-nowrap max-w-0 opacity-0 transition-all duration-150 group-hover/sidebar:max-w-[160px] group-hover/sidebar:opacity-100">
            CallLock
          </span>
        </div>

        <nav className="flex-1 p-2">
          <a
            href="/dashboard"
            className="h-8 w-full rounded-[6px] px-2 text-sm flex items-center justify-center group-hover/sidebar:justify-start gap-2 text-[#acabaa] hover:bg-[#1b1c1c] hover:text-[#e7e5e4] transition-colors"
          >
            <LayoutDashboard className="h-4 w-4 shrink-0" />
            <span className="whitespace-nowrap max-w-0 opacity-0 transition-all duration-150 group-hover/sidebar:max-w-[160px] group-hover/sidebar:opacity-100">
              Dashboard
            </span>
          </a>
          <button
            className="h-8 w-full mt-1 text-left px-2 rounded-[6px] text-sm flex items-center justify-center group-hover/sidebar:justify-start gap-2 transition-colors bg-[#252626] text-[#e7e5e4] font-medium"
          >
            <ActivityIcon className="h-4 w-4 shrink-0" />
            <span className="whitespace-nowrap max-w-0 opacity-0 transition-all duration-150 group-hover/sidebar:max-w-[160px] group-hover/sidebar:opacity-100">
              Activity
            </span>
          </button>
          <span className="h-8 w-full mt-1 px-2 rounded-[6px] text-sm flex items-center justify-center group-hover/sidebar:justify-start gap-2 text-[#acabaa] hover:bg-[#1b1c1c] hover:text-[#e7e5e4] transition-colors cursor-pointer">
            <SettingsIcon className="h-4 w-4 shrink-0" />
            <span className="whitespace-nowrap max-w-0 opacity-0 transition-all duration-150 group-hover/sidebar:max-w-[160px] group-hover/sidebar:opacity-100">
              Settings
            </span>
          </span>
        </nav>

        <div className="p-2 group-hover/sidebar:p-3 transition-all duration-200 flex justify-center group-hover/sidebar:justify-start">
          <div className="w-8 h-8 rounded-full bg-[#252626] flex items-center justify-center text-[#c6c6c7] text-xs font-semibold">
            R
          </div>
        </div>
      </aside>

      {/* ── Mobile layout ── */}
      <main className="pt-16 h-screen md:hidden flex flex-col overflow-hidden">
        {mobileView === "list" ? (
          <>
            {/* Pulse bar */}
            <PulseBar {...pulseBarCounts} />

            {/* All caught up or call list */}
            {actionQueueEmpty && buckets.AI_HANDLED.length === 0 ? (
              <div className="flex-1 flex items-center justify-center bg-[#000000] p-8">
                <p className="text-[#acabaa] text-sm font-medium">All caught up — no callbacks needed</p>
              </div>
            ) : actionQueueEmpty ? (
              <div className="flex-1 flex flex-col bg-[#0e0e0e]">
                <div className="flex-1 flex flex-col items-center justify-center p-8 gap-3">
                  <p className="text-[#e7e5e4] text-sm font-medium">All caught up</p>
                  <p className="text-[#acabaa] text-xs">AI handled {buckets.AI_HANDLED.length} calls</p>
                </div>
                <MailList
                  items={allSectionedCalls}
                  selected={selectedId}
                  onSelect={handleSelect}
                  onOutcomeChange={handleOutcomeChange}
                  triageMap={triageMap}
                  pulsingId={pulsingId}
                  onCallBackTap={handleCallBackTap}
                  onPulseClear={clearPulse}
                  buckets={buckets}
                  bucketMap={bucketMap}
                />
              </div>
            ) : (
              <MailList
                items={allSectionedCalls}
                selected={selectedId}
                onSelect={handleSelect}
                onOutcomeChange={handleOutcomeChange}
                triageMap={triageMap}
                pulsingId={pulsingId}
                onCallBackTap={handleCallBackTap}
                onPulseClear={clearPulse}
                buckets={buckets}
                bucketMap={bucketMap}
              />
            )}
          </>
        ) : (
          <div className="flex flex-col h-full">
            <div className="flex h-12 items-center gap-2 px-4 bg-[#131313] flex-shrink-0">
              <button
                onClick={() => setMobileView("list")}
                className="p-2 text-[#c6c6c7] hover:bg-[#252626] rounded-[6px] transition-all"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-sm font-medium text-[#e7e5e4]">Call Details</span>
            </div>
            <div className="flex-1 overflow-hidden flex">
              <MailDisplay call={selectedCall} triageMap={triageMap} onOutcomeChange={handleOutcomeChange} bucketMap={bucketMap} />
            </div>
          </div>
        )}
      </main>

      {/* ── Desktop layout: 2-panel ── */}
      <main className="h-screen hidden md:flex overflow-hidden pl-14">
        {/* Action Feed */}
        <aside className="w-[380px] bg-[#0e0e0e] flex flex-col shrink-0">
          <div className="h-14 px-5 flex justify-between items-center flex-shrink-0">
            <h2 className="font-headline text-lg font-bold tracking-tight text-[#e7e5e4]">
              Activity Feed
            </h2>
            <span className="text-[10px] font-bold tracking-widest uppercase bg-[#252626] text-[#acabaa] px-2 py-1 rounded flex items-center gap-1.5">
              <Headset className="h-3 w-3 text-[#c6c6c7]" />
              LIVE
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10b981] opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#10b981]" />
              </span>
            </span>
          </div>

          {/* Pulse bar */}
          <PulseBar {...pulseBarCounts} />

          {/* All caught up or call list */}
          {actionQueueEmpty && buckets.AI_HANDLED.length === 0 ? (
            <div className="flex-1 flex items-center justify-center bg-[#000000] p-8">
              <p className="text-[#acabaa] text-sm font-medium">All caught up — no callbacks needed</p>
            </div>
          ) : actionQueueEmpty ? (
            <div className="flex-1 flex flex-col bg-[#0e0e0e]">
              <div className="flex flex-col items-center justify-center p-8 gap-3">
                <p className="text-[#e7e5e4] text-sm font-medium">All caught up</p>
                <p className="text-[#acabaa] text-xs">AI handled {buckets.AI_HANDLED.length} calls</p>
              </div>
              <MailList
                items={allSectionedCalls}
                selected={selectedId}
                onSelect={handleSelect}
                onOutcomeChange={handleOutcomeChange}
                triageMap={triageMap}
                pulsingId={pulsingId}
                onCallBackTap={handleCallBackTap}
                onPulseClear={clearPulse}
                buckets={buckets}
                bucketMap={bucketMap}
              />
            </div>
          ) : (
            <MailList
              items={allSectionedCalls}
              selected={selectedId}
              onSelect={handleSelect}
              onOutcomeChange={handleOutcomeChange}
              triageMap={triageMap}
              pulsingId={pulsingId}
              onCallBackTap={handleCallBackTap}
              onPulseClear={clearPulse}
              buckets={buckets}
              bucketMap={bucketMap}
            />
          )}
        </aside>

        {/* Detail Panel */}
        <MailDisplay call={selectedCall} triageMap={triageMap} onOutcomeChange={handleOutcomeChange} bucketMap={bucketMap} />

        {/* Lead Intel Sidebar — xl (≥1280px) only */}
        <div className="hidden xl:flex">
          <LeadIntel call={selectedCall} />
        </div>
      </main>
    </>
  )
}
