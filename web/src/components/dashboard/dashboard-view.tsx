"use client"

import { formatDistanceToNow, format } from "date-fns"
import { formatPhone } from "@/lib/transforms"
import type { Call } from "@/types/call"

interface DashboardViewProps {
  calls: Call[]
}

// ── Derived metrics ──

function computeMetrics(calls: Call[]) {
  const urgent = calls.filter(
    (c) => c.isSafetyEmergency || c.urgency === "LifeSafety" || c.urgency === "Urgent"
  ).length
  const routine = calls.length - urgent
  const leads = calls.filter((c) => c.appointmentBooked).length
  const handled = calls.filter(
    (c) => c.endCallReason !== "customer_hangup"
  ).length
  const actionRate = calls.length > 0 ? Math.round((handled / calls.length) * 100) : 0

  // Rough pipeline estimate: $800 per routine lead, $2400 per urgent lead
  const pipelineValue = calls
    .filter((c) => c.appointmentBooked)
    .reduce((sum, c) => {
      if (c.urgency === "LifeSafety" || c.urgency === "Urgent") return sum + 2400
      return sum + 800
    }, 0)

  const sentimentCounts = { calm: 0, stressed: 0, frantic: 0 }
  calls.forEach((c) => {
    if (c.isSafetyEmergency || c.urgency === "LifeSafety") sentimentCounts.frantic++
    else if (c.urgency === "Urgent") sentimentCounts.stressed++
    else sentimentCounts.calm++
  })
  const dominantSentiment =
    sentimentCounts.frantic > sentimentCounts.calm
      ? "Urgent / Frantic"
      : sentimentCounts.stressed > sentimentCounts.calm
        ? "Stressed"
        : "Positive / Calm"

  return { urgent, routine, leads, actionRate, pipelineValue, dominantSentiment }
}

function getActivityIcon(call: Call) {
  if (call.isSafetyEmergency || call.urgency === "LifeSafety") {
    return { bg: "bg-[#7f2927]/20", text: "text-[#ee7d77]", icon: "⚠" }
  }
  if (call.appointmentBooked) {
    return { bg: "bg-[#c8cbfe]/10", text: "text-[#c8cbfe]", icon: "✓" }
  }
  return { bg: "bg-[#252626]", text: "text-[#acabaa]", icon: "☎" }
}

function getStatusLabel(call: Call): { label: string; color: string } {
  if (call.appointmentBooked) return { label: "Captured Lead", color: "text-[#10b981]" }
  if (call.endCallReason === "callback_later") return { label: "Callback", color: "text-[#c8cbfe]" }
  if (call.endCallReason === "wrong_number") return { label: "Wrong Number", color: "text-[#acabaa]" }
  if (call.endCallReason === "out_of_area") return { label: "Out of Area", color: "text-[#acabaa]" }
  if (call.isSafetyEmergency) return { label: "Emergency", color: "text-[#ee7d77]" }
  return { label: "Lead Staged", color: "text-[#acabaa]" }
}

// ── Audit Trail (static for now — will be data-driven) ──

function generateAuditItems(calls: Call[]) {
  const items: { time: string; title: string; description: string; primary: boolean }[] = []

  const scheduled = calls.filter((c) => c.appointmentBooked)
  if (scheduled.length > 0) {
    const latest = scheduled[0]
    items.push({
      time: formatDistanceToNow(new Date(latest.createdAt), { addSuffix: false }) + " ago",
      title: "Appointment Confirmed",
      description: `Booked for ${latest.customerName || formatPhone(latest.customerPhone || "")}`,
      primary: true,
    })
  }

  const emergencies = calls.filter((c) => c.isSafetyEmergency || c.urgency === "LifeSafety")
  if (emergencies.length > 0) {
    items.push({
      time: formatDistanceToNow(new Date(emergencies[0].createdAt), { addSuffix: false }) + " ago",
      title: "Emergency Escalated",
      description: emergencies[0].problemDescription || "Safety concern flagged to owner",
      primary: false,
    })
  }

  items.push({
    time: "On startup",
    title: "AI Receptionist Online",
    description: "Screening calls and processing voice streams",
    primary: false,
  })

  return items.slice(0, 4)
}

export function DashboardView({ calls }: DashboardViewProps) {
  const metrics = computeMetrics(calls)
  const recentCalls = calls.slice(0, 5)
  const auditItems = generateAuditItems(calls)

  return (
    <div className="min-h-screen bg-[#0e0e0e]">
      {/* Top Nav */}
      <header className="sticky top-0 z-50 flex justify-between items-center px-6 h-16 bg-[#131313] border-b border-[#484848]/20">
        <div className="flex items-center gap-8">
          <span className="text-xl font-headline font-bold tracking-tighter text-[#e7e5e4]">
            CallLock
          </span>
          <nav className="hidden md:flex gap-6 items-center">
            <a
              href="/"
              className="text-[#acabaa] text-sm cursor-pointer hover:text-[#e7e5e4] transition-colors"
            >
              Activity
            </a>
            <span className="text-[#e7e5e4] text-sm border-b-2 border-[#c6c6c7] pb-0.5 cursor-pointer">
              Dashboard
            </span>
            <span className="text-[#acabaa] text-sm cursor-pointer hover:text-[#e7e5e4] transition-colors">
              Leads
            </span>
            <span className="text-[#acabaa] text-sm cursor-pointer hover:text-[#e7e5e4] transition-colors">
              Settings
            </span>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <button className="p-2 text-[#c6c6c7] hover:bg-[#252626] rounded-full transition-all">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
          </button>
          <div className="w-8 h-8 rounded-full bg-[#252626] border border-[#484848]/20 flex items-center justify-center text-[#c6c6c7] text-xs font-bold font-headline">
            R
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-8">
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <h1 className="text-4xl font-headline font-extrabold tracking-tighter text-[#e7e5e4] mb-2">
              Operational Dashboard
            </h1>
            <p className="text-[#acabaa] max-w-2xl">
              <span className="text-[#c6c6c7] font-semibold">
                {calls.length} Calls today, {metrics.leads} Leads captured.
              </span>{" "}
              AI Receptionist is online and actively screening calls.
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <button className="flex items-center gap-2 px-4 py-2 bg-[#3b3b3b] text-[#c1bfbe] rounded-lg font-medium text-sm hover:bg-[#2c2c2c] transition-colors">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
            <a
              href="/"
              className="flex items-center gap-2 px-4 py-2 bg-[#c6c6c7] text-[#3f4041] rounded-lg font-bold text-sm hover:opacity-90 transition-all"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
              </svg>
              New Lead
            </a>
          </div>
        </div>

        {/* Bento Grid: 8/4 split */}
        <div className="grid grid-cols-12 gap-6">
          {/* ── Left Column (8 cols) ── */}
          <div className="col-span-12 lg:col-span-8 space-y-6">
            {/* 4-Column Metrics Row (V2 style) */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* Missed Calls */}
              <div className="bg-[#131313] p-5 rounded-xl border border-[#484848]/10">
                <p className="text-[10px] uppercase font-bold text-[#acabaa] tracking-widest mb-3">
                  Missed Calls
                </p>
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-3xl font-headline font-black text-[#e7e5e4]">
                    {calls.length}
                  </span>
                </div>
                <p className="text-[10px] text-[#acabaa] leading-tight">
                  {metrics.urgent > 0 && (
                    <span className="text-[#ee7d77] font-medium">{metrics.urgent} urgent</span>
                  )}
                  {metrics.urgent > 0 && metrics.routine > 0 && ", "}
                  {metrics.routine > 0 && `${metrics.routine} routine`}
                </p>
              </div>

              {/* Leads Captured */}
              <div className="bg-[#131313] p-5 rounded-xl border border-[#484848]/10">
                <p className="text-[10px] uppercase font-bold text-[#acabaa] tracking-widest mb-3">
                  Leads Captured
                </p>
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-3xl font-headline font-black text-[#10b981]">
                    {metrics.leads}
                  </span>
                </div>
                <p className="text-[10px] text-[#acabaa] leading-tight">
                  Pipeline value:{" "}
                  <span className="text-[#e7e5e4] font-bold">
                    ${metrics.pipelineValue.toLocaleString()}
                  </span>
                </p>
              </div>

              {/* AI Action Rate */}
              <div className="bg-[#131313] p-5 rounded-xl border border-[#484848]/10">
                <p className="text-[10px] uppercase font-bold text-[#acabaa] tracking-widest mb-3">
                  Action Rate
                </p>
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-3xl font-headline font-black text-[#e7e5e4]">
                    {metrics.actionRate}%
                  </span>
                </div>
                <p className="text-[10px] text-[#acabaa] leading-tight">
                  Handled without intervention
                </p>
              </div>

              {/* Sentiment */}
              <div className="bg-[#131313] p-5 rounded-xl border border-[#484848]/10">
                <p className="text-[10px] uppercase font-bold text-[#acabaa] tracking-widest mb-3">
                  Sentiment
                </p>
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-[#c6c6c7] animate-pulse shadow-[0_0_12px_rgba(198,198,199,0.3)]" />
                  <span className="text-lg font-headline font-bold text-[#e7e5e4]">
                    {metrics.dominantSentiment}
                  </span>
                </div>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-[#131313] rounded-xl border border-[#484848]/10 overflow-hidden">
              <div className="px-6 py-4 border-b border-[#484848]/10 flex justify-between items-center">
                <h3 className="text-sm font-bold uppercase tracking-widest text-[#e7e5e4]">
                  Recent Activity
                </h3>
                <a
                  href="/"
                  className="text-xs text-[#c6c6c7] hover:underline font-bold"
                >
                  View All
                </a>
              </div>
              {recentCalls.length === 0 ? (
                <div className="px-6 py-8 text-center">
                  <p className="text-[#acabaa] text-sm">No calls yet</p>
                </div>
              ) : (
                <div className="divide-y divide-[#484848]/5">
                  {recentCalls.map((call) => {
                    const icon = getActivityIcon(call)
                    const status = getStatusLabel(call)
                    const urgencyChip = call.isSafetyEmergency || call.urgency === "LifeSafety"
                      ? { label: call.hvacIssueType || "Emergency", bg: "bg-[#7f2927]", text: "text-[#ff9993]" }
                      : call.urgency === "Urgent"
                        ? { label: call.hvacIssueType || "Urgent", bg: "bg-[#3b3b3b]", text: "text-[#c1bfbe]" }
                        : null

                    return (
                      <div
                        key={call.id}
                        className="px-6 py-4 flex items-center justify-between hover:bg-[#1f2020] transition-colors cursor-pointer group"
                      >
                        <div className="flex items-center gap-4">
                          <div className={`w-10 h-10 rounded-lg ${icon.bg} flex items-center justify-center ${icon.text} text-lg shrink-0`}>
                            {icon.icon}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-[#e7e5e4] text-sm">
                                {call.customerName || (call.customerPhone ? formatPhone(call.customerPhone) : "Unknown")}
                              </span>
                              {urgencyChip && (
                                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-tighter ${urgencyChip.bg} ${urgencyChip.text}`}>
                                  {urgencyChip.label}
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-[#acabaa] mt-0.5">
                              {call.problemDescription || call.hvacIssueType || "Incoming call"}
                            </p>
                          </div>
                        </div>
                        <div className="text-right shrink-0 ml-4">
                          <span className="text-xs font-medium text-[#e7e5e4] block">
                            {format(new Date(call.createdAt), "HH:mm")}
                          </span>
                          <span className={`text-[10px] uppercase ${status.color}`}>
                            {status.label}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Automation Log */}
            <div className="bg-black rounded-xl border border-[#484848]/10 p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-[#c6c6c7]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  <h3 className="text-sm font-bold uppercase tracking-widest text-[#e7e5e4]">
                    Automation Log
                  </h3>
                </div>
                <button className="text-[#acabaa] hover:text-[#e7e5e4] transition-colors">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </div>
              <div className="space-y-3 font-mono text-[11px] text-[#acabaa]">
                {recentCalls.slice(0, 4).map((call, i) => (
                  <div key={call.id} className="flex gap-4">
                    <span className="text-[#c6c6c7]/40 shrink-0">
                      {format(new Date(call.createdAt), "HH:mm:ss")}
                    </span>
                    <span>
                      {i === 0 && "[AI] Call received. Initiating greeting..."}
                      {i === 1 && `[NLU] Intent classified: ${call.hvacIssueType || call.urgency}. ${call.isSafetyEmergency ? "Escalating to high priority..." : "Processing..."}`}
                      {i === 2 && `[AI] ${call.appointmentBooked ? "Appointment booked successfully." : "SMS verification sent to caller."}`}
                      {i === 3 && `[DB] Lead created: ${call.id.slice(0, 12)}. Action: Notify owner.`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Right Column (4 cols) ── */}
          <div className="col-span-12 lg:col-span-4 space-y-6">
            {/* Receptionist Status */}
            <div className="bg-[#1f2020] p-6 rounded-xl border border-[#484848]/10">
              <h3 className="text-xs font-bold uppercase tracking-widest text-[#acabaa] mb-6">
                Receptionist Status
              </h3>
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <div className="w-3 h-3 bg-[#10b981] rounded-full shadow-[0_0_15px_rgba(16,185,129,0.4)] animate-pulse" />
                  <div>
                    <span className="text-xl font-headline font-bold text-[#e7e5e4] block">Online</span>
                    <span className="text-xs text-[#acabaa]">
                      Processing {calls.length > 0 ? "voice streams" : "idle"}
                    </span>
                  </div>
                </div>
                <div className="h-12 w-24 bg-black rounded-lg border border-[#484848]/5 flex items-center justify-center">
                  <span className="text-[10px] font-mono text-[#c6c6c7]">v2.4.1</span>
                </div>
              </div>

              {/* Service Mode Toggle */}
              <div className="space-y-3 pt-6 border-t border-[#484848]/10">
                <label className="text-[10px] font-bold uppercase tracking-widest text-[#acabaa] block">
                  Service Mode
                </label>
                <div className="grid grid-cols-2 gap-2 p-1 bg-black rounded-lg">
                  <button className="py-2 text-xs font-bold rounded-md transition-all bg-[#252626] text-[#e7e5e4]">
                    Observe
                  </button>
                  <button className="py-2 text-xs font-bold rounded-md transition-all text-[#acabaa] hover:text-[#e7e5e4]">
                    Enforce
                  </button>
                </div>
                <p className="text-[10px] text-[#acabaa] italic">
                  In Observe mode, AI logs suggestions without immediate SMS dispatch.
                </p>
              </div>
            </div>

            {/* Audit Trail (V2 timeline styling) */}
            <div className="bg-[#131313] rounded-xl border border-[#484848]/10 flex-grow">
              <div className="px-6 py-4 border-b border-[#484848]/10">
                <h3 className="text-xs font-bold uppercase tracking-widest text-[#e7e5e4]">
                  Audit Trail
                </h3>
              </div>
              <div className="p-6">
                <div className="relative pl-6 border-l border-[#484848]/20 space-y-8">
                  {auditItems.map((item, i) => (
                    <div key={i} className="relative">
                      <div className={`absolute -left-[31px] top-1 w-2.5 h-2.5 rounded-full border-4 border-[#131313] ${
                        item.primary ? "bg-[#c6c6c7]" : "bg-[#252626]"
                      }`} />
                      <span className="text-[10px] font-bold text-[#acabaa] block mb-1 uppercase">
                        {item.time}
                      </span>
                      <h4 className="text-xs font-bold text-[#e7e5e4] mb-1">
                        {item.title}
                      </h4>
                      <p className="text-[11px] text-[#acabaa] leading-relaxed">
                        {item.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="p-4 border-t border-[#484848]/10">
                <button className="w-full py-2 bg-[#252626] border border-[#484848]/20 rounded-lg text-xs font-bold text-[#e7e5e4] hover:bg-[#2c2c2c] transition-colors">
                  Export Logs
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
