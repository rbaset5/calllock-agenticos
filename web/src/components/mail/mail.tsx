"use client"

import * as React from "react"
import Image from "next/image"
import {
  Activity as ActivityIcon,
  CalendarDays,
  ChevronLeft,
  Headset,
  LayoutDashboard,
  Phone,
  Settings as SettingsIcon,
} from "lucide-react"
import type { Call, CallbackOutcome } from "@/types/call"
import type { TriageResult } from "@/types/call"
import { triageSort, isUnresolved, computeTriage } from "@/lib/triage"
import { useRealtimeCalls } from "@/hooks/use-realtime-calls"
import { useReadState } from "@/hooks/use-read-state"
import { MailList } from "./mail-list"
import { MailDisplay } from "./mail-display"
import { ScheduledDisplay } from "./scheduled-display"
import { LeadIntel } from "./lead-intel"

interface MailProps {
  initialCalls: Call[]
}

export function Mail({ initialCalls }: MailProps) {
  const [view, setView] = React.useState<"activity" | "test">("activity")
  const [filter, setFilter] = React.useState<"all" | "scheduled">("all")
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

  const scheduledCalls = React.useMemo(
    () =>
      calls
        .filter((c) => c.appointmentBooked)
        .sort((a, b) => {
          if (a.appointmentDateTime && b.appointmentDateTime) {
            return new Date(a.appointmentDateTime).getTime() - new Date(b.appointmentDateTime).getTime()
          }
          if (a.appointmentDateTime) return -1
          if (b.appointmentDateTime) return 1
          return 0
        }),
    [calls]
  )

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

  // Triage-sorted activity calls
  const unresolvedCalls = React.useMemo(
    () => mergedCalls.filter(isUnresolved),
    [mergedCalls]
  )
  const resolvedCalls = React.useMemo(
    () => mergedCalls.filter((c) => !isUnresolved(c)),
    [mergedCalls]
  )
  const triageSortedCalls = React.useMemo(
    () => [...triageSort(unresolvedCalls, now), ...resolvedCalls],
    [unresolvedCalls, resolvedCalls, now]
  )

  // Preserve existing filter logic
  const activityCalls = filter === "scheduled"
    ? triageSortedCalls.filter((c) => c.appointmentBooked)
    : triageSortedCalls

  const testCalls = scheduledCalls
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
    if (view !== "activity") return
    const interval = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(interval)
  }, [view])

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
    () => unresolvedCalls.filter(c => triageMap.get(c.id)?.command === "Call now").length,
    [unresolvedCalls, triageMap]
  )
  const pendingCount = React.useMemo(
    () => unresolvedCalls.filter(c => triageMap.get(c.id)?.command !== "Call now").length,
    [unresolvedCalls, triageMap]
  )

  // Auto-select first item when switching views
  React.useEffect(() => {
    const list = view === "test" ? testCalls : activityCalls
    if (list.length > 0 && !list.find((c) => c.id === selectedId)) {
      setSelectedId(list[0].id)
    }
  }, [view, testCalls, activityCalls, selectedId])

  const handleSelect = (id: string) => {
    setSelectedId(id)
    markAsRead(id)
    setMobileView("detail")
    try { sessionStorage.setItem("calllock_selectedId", id) } catch { /* ignore */ }
  }

  const clearPulse = React.useCallback(() => setPulsingId(null), [])

  return (
    <>
      {/* ── Mobile Top App Bar ── */}
      <header className="fixed top-0 left-0 w-full z-50 md:hidden flex justify-between items-center px-6 h-16 bg-[#0e0e0e] border-b border-[#dfdfdf]/20">
        <span className="text-xl font-headline font-bold tracking-tighter text-[#e7e5e4]">
          CallLock
        </span>
        <div className="flex items-center gap-3">
          {/* AI Receptionist live status */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-[#10b981]/20 bg-[#10b981]/5">
            <Phone className="h-3 w-3 text-[#10b981]/70" />
          </div>
          <button className="p-2 text-[#c6c6c7] hover:bg-[#252626] rounded-[6px] transition-all">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
          </button>
          <div className="w-8 h-8 rounded-full bg-[#252626] border border-[#dfdfdf]/20 flex items-center justify-center text-[#c6c6c7] text-xs font-bold font-headline">
            R
          </div>
        </div>
      </header>

      {/* ── Desktop Left Navigation Rail ── */}
      <aside className="group/sidebar fixed left-0 top-0 z-50 hidden md:flex h-screen w-14 hover:w-64 flex-col border-r border-[#dfdfdf]/20 bg-[#0e0e0e] transition-[width] duration-200 ease-out overflow-hidden">
        <div className="h-14 px-1 group-hover/sidebar:px-1 flex items-center justify-center group-hover/sidebar:justify-start border-b border-[#dfdfdf]/20 transition-all duration-200">
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
            onClick={() => setView("activity")}
            className={`h-8 w-full mt-1 text-left px-2 rounded-[6px] text-sm flex items-center justify-center group-hover/sidebar:justify-start gap-2 transition-colors ${
              view === "activity"
                ? "bg-[#252626] text-[#e7e5e4] font-medium"
                : "text-[#acabaa] hover:bg-[#1b1c1c] hover:text-[#e7e5e4]"
            }`}
          >
            <ActivityIcon className="h-4 w-4 shrink-0" />
            <span className="whitespace-nowrap max-w-0 opacity-0 transition-all duration-150 group-hover/sidebar:max-w-[160px] group-hover/sidebar:opacity-100">
              Activity
            </span>
          </button>
          <button
            onClick={() => setView("test")}
            className={`h-8 w-full mt-1 text-left px-2 rounded-[6px] text-sm flex items-center justify-center group-hover/sidebar:justify-start gap-2 transition-colors ${
              view === "test"
                ? "bg-[#252626] text-[#e7e5e4] font-medium"
                : "text-[#acabaa] hover:bg-[#1b1c1c] hover:text-[#e7e5e4]"
            }`}
          >
            <CalendarDays className="h-4 w-4 shrink-0" />
            <span className="whitespace-nowrap max-w-0 opacity-0 transition-all duration-150 group-hover/sidebar:max-w-[160px] group-hover/sidebar:opacity-100">
              Scheduled Calls
            </span>
          </button>
          <span className="h-8 w-full mt-1 px-2 rounded-[6px] text-sm flex items-center justify-center group-hover/sidebar:justify-start gap-2 text-[#acabaa] hover:bg-[#1b1c1c] hover:text-[#e7e5e4] transition-colors cursor-pointer">
            <SettingsIcon className="h-4 w-4 shrink-0" />
            <span className="whitespace-nowrap max-w-0 opacity-0 transition-all duration-150 group-hover/sidebar:max-w-[160px] group-hover/sidebar:opacity-100">
              Settings
            </span>
          </span>
        </nav>

        <div className="p-2 group-hover/sidebar:p-3 border-t border-[#dfdfdf]/20 transition-all duration-200 flex justify-center group-hover/sidebar:justify-start">
          <div className="w-8 h-8 rounded-full bg-[#252626] border border-[#dfdfdf]/20 flex items-center justify-center text-[#c6c6c7] text-xs font-semibold">
            R
          </div>
        </div>
      </aside>

      {/* ── Mobile layout ── */}
      <main className="pt-16 h-screen md:hidden flex flex-col overflow-hidden">
        {mobileView === "list" ? (
          <>
            <div className="p-5 pb-0 flex justify-between items-center flex-shrink-0">
              <h2 className="font-headline text-lg font-bold tracking-tight text-[#e7e5e4]">
                {view === "test" ? "Upcoming" : "Activity Feed"}
              </h2>
              {view === "test" ? (
                <span className="text-[10px] font-bold tracking-widest uppercase text-[#acabaa]">
                  {scheduledCalls.length} appointment{scheduledCalls.length !== 1 ? "s" : ""}
                </span>
              ) : view === "activity" ? (
                <span className="text-[10px] font-bold tracking-widest uppercase bg-[#252626] text-[#acabaa] px-2 py-1 rounded flex items-center gap-1.5">
                  <Headset className="h-3 w-3 text-[#c6c6c7]" />
                  LIVE
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10b981] opacity-60" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#10b981]" />
                  </span>
                </span>
              ) : null}
            </div>
            {view === "activity" && (
              <div className="grid grid-cols-2 gap-px border-b border-[#484848]/10 flex-shrink-0">
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
            )}
            {view === "activity" ? (
              <div className="px-4 pt-4 pb-2 flex-shrink-0">
                <h3 className="text-[#e7e5e4] text-[12px] font-bold tracking-[0.15em] uppercase border-l-2 border-[#10b981] pl-3">
                  Missed Calls
                </h3>
              </div>
            ) : view === "test" ? (
              <div className="flex gap-6 px-5 pb-3 pt-3 flex-shrink-0">
                <button
                  onClick={() => setFilter("all")}
                  className={`text-sm font-semibold pb-1 border-b-2 transition-colors ${
                    filter === "all"
                      ? "text-[#e7e5e4] border-[#c6c6c7]"
                      : "text-[#acabaa] border-transparent hover:text-[#e7e5e4]"
                  }`}
                >
                  Scheduled Calls
                </button>
              </div>
            ) : null}
            {view === "activity" && unresolvedCalls.length === 0 && (
              <div className="flex items-center justify-center gap-2 py-6 text-[#acabaa]">
                <svg className="h-5 w-5 text-[#10b981]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm font-medium">All calls handled</span>
              </div>
            )}
            <MailList
              items={view === "test" ? testCalls : activityCalls}
              selected={selectedId}
              onSelect={handleSelect}
              onOutcomeChange={handleOutcomeChange}
              triageMap={triageMap}
              pulsingId={pulsingId}
              onCallBackTap={handleCallBackTap}
              onPulseClear={clearPulse}
            />
          </>
        ) : (
          <div className="flex flex-col h-full">
            <div className="flex h-12 items-center gap-2 px-4 bg-[#131313] flex-shrink-0 border-b border-[#dfdfdf]/20">
              <button
                onClick={() => setMobileView("list")}
                className="p-2 text-[#c6c6c7] hover:bg-[#252626] rounded-[6px] transition-all"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-sm font-medium text-[#e7e5e4]">
                {view === "test" ? "Test Details" : "Call Details"}
              </span>
            </div>
            <div className="flex-1 overflow-hidden flex">
              {view === "test" ? (
                <ScheduledDisplay call={selectedCall} />
              ) : (
                <MailDisplay call={selectedCall} triageMap={triageMap} onOutcomeChange={handleOutcomeChange} />
              )}
            </div>
          </div>
        )}

        {/* Mobile Bottom Nav */}
        <nav className="fixed bottom-0 left-0 w-full z-50 flex justify-around items-center px-4 h-16 md:hidden bg-[#131313]/90 backdrop-blur-xl border-t border-[#dfdfdf]/20">
          <button
            onClick={() => setView("activity")}
            className={`flex flex-col items-center justify-center p-2 ${
              view === "activity" ? "bg-[#252626] text-[#e7e5e4] rounded-lg scale-110" : "text-[#acabaa] hover:text-[#e7e5e4]"
            }`}
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
            <span className="font-sans text-[10px] uppercase tracking-widest mt-1">Calls</span>
          </button>
          <button
            onClick={() => setView("test")}
            className={`flex flex-col items-center justify-center p-2 ${
              view === "test" ? "bg-[#252626] text-[#e7e5e4] rounded-lg scale-110" : "text-[#acabaa] hover:text-[#e7e5e4]"
            }`}
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
            <span className="font-sans text-[10px] uppercase tracking-widest mt-1">Test</span>
          </button>
          <button className="flex flex-col items-center justify-center text-[#acabaa] p-2 hover:text-[#e7e5e4]">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="font-sans text-[10px] uppercase tracking-widest mt-1">Leads</span>
          </button>
          <button className="flex flex-col items-center justify-center text-[#acabaa] p-2 hover:text-[#e7e5e4]">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="font-sans text-[10px] uppercase tracking-widest mt-1">Settings</span>
          </button>
        </nav>
      </main>

      {/* ── Desktop layout: 3-pane ── */}
      <main className="h-screen hidden md:flex overflow-hidden pl-14">
        {/* Left Pane */}
        <aside className="w-[320px] bg-[#131313] flex flex-col shrink-0 border-r border-[#dfdfdf]/20">
          <div className="h-14 px-5 flex justify-between items-center flex-shrink-0 border-b border-[#dfdfdf]/20">
            <h2 className="font-headline text-lg font-bold tracking-tight text-[#e7e5e4]">
              {view === "test" ? "Upcoming" : "Activity Feed"}
            </h2>
            {view === "test" ? (
              <span className="text-[10px] font-bold tracking-widest uppercase text-[#acabaa]">
                {scheduledCalls.length} appt{scheduledCalls.length !== 1 ? "s" : ""}
              </span>
            ) : view === "activity" ? (
              <span className="text-[10px] font-bold tracking-widest uppercase bg-[#252626] text-[#acabaa] px-2 py-1 rounded flex items-center gap-1.5">
                <Headset className="h-3 w-3 text-[#c6c6c7]" />
                LIVE
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10b981] opacity-60" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#10b981]" />
                </span>
              </span>
            ) : null}
          </div>
          {view === "activity" && (
            <div className="grid grid-cols-2 gap-px border-b border-[#484848]/10 flex-shrink-0">
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
          )}
          {view === "activity" ? (
            <div className="px-5 pt-4 pb-2 flex-shrink-0">
              <h3 className="text-[#e7e5e4] text-[12px] font-bold tracking-[0.15em] uppercase border-l-2 border-[#10b981] pl-3">
                Missed Calls
              </h3>
            </div>
          ) : view === "test" ? (
            <div className="flex gap-6 px-5 pb-3 pt-3 flex-shrink-0">
              <button
                onClick={() => setFilter("all")}
                className={`text-sm font-semibold pb-1 border-b-2 transition-colors ${
                  filter === "all"
                    ? "text-[#e7e5e4] border-[#c6c6c7]"
                    : "text-[#acabaa] border-transparent hover:text-[#e7e5e4]"
                }`}
              >
                Scheduled Calls
              </button>
            </div>
          ) : null}
          {view === "activity" && unresolvedCalls.length === 0 && (
            <div className="flex items-center justify-center gap-2 py-6 text-[#acabaa]">
              <svg className="h-5 w-5 text-[#10b981]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm font-medium">All calls handled</span>
            </div>
          )}
          <MailList
            items={view === "test" ? testCalls : activityCalls}
            selected={selectedId}
            onSelect={handleSelect}
            onOutcomeChange={handleOutcomeChange}
            triageMap={triageMap}
            pulsingId={pulsingId}
            onCallBackTap={handleCallBackTap}
            onPulseClear={clearPulse}
          />
        </aside>

        {/* Center Pane */}
        {view === "test" ? (
          <ScheduledDisplay call={selectedCall} />
        ) : (
          <MailDisplay call={selectedCall} triageMap={triageMap} onOutcomeChange={handleOutcomeChange} />
        )}

        {/* Right Pane: Lead Intel */}
        <LeadIntel call={selectedCall} />
      </main>
    </>
  )
}
