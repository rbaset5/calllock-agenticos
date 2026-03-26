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
import { triageSort, computeTriage, assignSection } from "@/lib/triage"
import type { SectionKey } from "@/lib/triage"
import { useRealtimeCalls } from "@/hooks/use-realtime-calls"
import { useReadState } from "@/hooks/use-read-state"
import { MailList } from "./mail-list"
import { MailDisplay } from "./mail-display"

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

  // Section assignment: split calls into NEEDS_CALLBACK, HANDLED, UPCOMING
  const sections = React.useMemo(() => {
    const grouped: Record<SectionKey, Call[]> = {
      NEEDS_CALLBACK: [],
      HANDLED: [],
      UPCOMING: [],
    }
    for (const call of mergedCalls) {
      grouped[assignSection(call)].push(call)
    }
    // Sort NEEDS_CALLBACK by triage priority
    grouped.NEEDS_CALLBACK = triageSort(grouped.NEEDS_CALLBACK, now)
    // Sort UPCOMING by appointment date
    grouped.UPCOMING.sort((a, b) => {
      if (a.appointmentDateTime && b.appointmentDateTime) {
        return new Date(a.appointmentDateTime).getTime() - new Date(b.appointmentDateTime).getTime()
      }
      if (a.appointmentDateTime) return -1
      if (b.appointmentDateTime) return 1
      return 0
    })
    return grouped
  }, [mergedCalls, now])

  // Unified feed: NEEDS_CALLBACK → HANDLED → UPCOMING
  const allSectionedCalls = React.useMemo(
    () => [...sections.NEEDS_CALLBACK, ...sections.HANDLED, ...sections.UPCOMING],
    [sections]
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

  // Memoized summary strip counts
  const criticalCount = React.useMemo(
    () => sections.NEEDS_CALLBACK.filter(c => triageMap.get(c.id)?.command === "Call now").length,
    [sections.NEEDS_CALLBACK, triageMap]
  )
  const pendingCount = React.useMemo(
    () => sections.NEEDS_CALLBACK.filter(c => triageMap.get(c.id)?.command !== "Call now").length,
    [sections.NEEDS_CALLBACK, triageMap]
  )

  // Auto-select first item
  React.useEffect(() => {
    if (allSectionedCalls.length > 0 && !allSectionedCalls.find((c) => c.id === selectedId)) {
      setSelectedId(allSectionedCalls[0].id)
    }
  }, [allSectionedCalls, selectedId])

  const handleSelect = (id: string) => {
    setSelectedId(id)
    markAsRead(id)
    setMobileView("detail")
    try { sessionStorage.setItem("calllock_selectedId", id) } catch { /* ignore */ }
  }

  const clearPulse = React.useCallback(() => setPulsingId(null), [])

  const allEmpty = sections.NEEDS_CALLBACK.length === 0 && sections.HANDLED.length === 0 && sections.UPCOMING.length === 0

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
            {/* Counter strip */}
            <div className="bg-[#000000] flex-shrink-0">
              <div className="grid grid-cols-2 gap-px">
                <div className="flex flex-col gap-1 p-4">
                  <p className="text-[#acabaa] text-[10px] font-bold tracking-[0.15em] uppercase">Critical</p>
                  <div className="flex items-baseline gap-2">
                    <p className="text-[#ff9993] tracking-tighter text-3xl font-black leading-none">
                      {String(criticalCount).padStart(2, "0")}
                    </p>
                    <span className="text-[10px] text-[#ed8a85] font-bold tracking-widest uppercase">Need callback</span>
                  </div>
                </div>
                <div className="flex flex-col gap-1 p-4">
                  <p className="text-[#acabaa] text-[10px] font-bold tracking-[0.15em] uppercase">Pending</p>
                  <div className="flex items-baseline gap-2">
                    <p className="text-[#c8c6c5] tracking-tighter text-3xl font-black leading-none">
                      {String(pendingCount).padStart(2, "0")}
                    </p>
                    <span className="text-[10px] text-[#acabaa] font-bold tracking-widest uppercase">In queue</span>
                  </div>
                </div>
              </div>
            </div>

            {/* All caught up empty state */}
            {allEmpty ? (
              <div className="flex-1 flex items-center justify-center bg-[#000000] p-8">
                <p className="text-[#acabaa] text-sm font-medium">All caught up — no callbacks needed</p>
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
                sections={sections}
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
              <MailDisplay call={selectedCall} triageMap={triageMap} onOutcomeChange={handleOutcomeChange} />
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

          {/* Counter strip */}
          <div className="bg-[#000000] flex-shrink-0">
            <div className="grid grid-cols-2 gap-px">
              <div className="flex flex-col gap-1 p-3">
                <p className="text-[#acabaa] text-[10px] font-bold tracking-[0.15em] uppercase">Critical</p>
                <div className="flex items-baseline gap-2">
                  <p className="text-[#ff9993] tracking-tighter text-2xl font-black leading-none">
                    {String(criticalCount).padStart(2, "0")}
                  </p>
                  <span className="text-[10px] text-[#ed8a85] font-bold tracking-widest uppercase">Need callback</span>
                </div>
              </div>
              <div className="flex flex-col gap-1 p-3">
                <p className="text-[#acabaa] text-[10px] font-bold tracking-[0.15em] uppercase">Pending</p>
                <div className="flex items-baseline gap-2">
                  <p className="text-[#c8c6c5] tracking-tighter text-2xl font-black leading-none">
                    {String(pendingCount).padStart(2, "0")}
                  </p>
                  <span className="text-[10px] text-[#acabaa] font-bold tracking-widest uppercase">In queue</span>
                </div>
              </div>
            </div>
          </div>

          {/* All caught up empty state */}
          {allEmpty ? (
            <div className="flex-1 flex items-center justify-center bg-[#000000] p-8">
              <p className="text-[#acabaa] text-sm font-medium">All caught up — no callbacks needed</p>
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
              sections={sections}
            />
          )}
        </aside>

        {/* Detail Panel */}
        <MailDisplay call={selectedCall} triageMap={triageMap} onOutcomeChange={handleOutcomeChange} />
      </main>
    </>
  )
}
