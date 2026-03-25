"use client"

import { useEffect, useState } from "react"
import { format } from "date-fns"
import { parseTranscript, formatPhone } from "@/lib/transforms"
import type { Call, TranscriptEntry, CallbackOutcome, TriageResult } from "@/types/call"
import { cn } from "@/lib/utils"
import { isUnresolved, getAssistTemplate } from "@/lib/triage"

interface MailDisplayProps {
  call: Call | null
  triageMap?: Map<string, TriageResult>
  onOutcomeChange?: (callId: string, outcome: CallbackOutcome | null) => void
}

function buildAISummary(call: Call): string {
  const parts: string[] = []

  const who = call.customerName ? `The caller, ${call.customerName},` : "The caller"
  parts.push(who)

  if (call.problemDescription) {
    parts.push(`reported: "${call.problemDescription}"`)
  } else if (call.hvacIssueType) {
    parts.push(`requested service for a ${call.hvacIssueType} issue.`)
  } else {
    parts.push("reached out for assistance.")
  }

  if (call.serviceAddress) {
    parts.push(`Service address: ${call.serviceAddress}.`)
  }

  if (call.appointmentBooked) {
    parts.push("An appointment was successfully scheduled.")
  } else if (call.endCallReason === "callback_later") {
    parts.push("Customer requested a callback.")
  }

  return parts.join(" ")
}

function getEstimatedLTV(urgency: string): string {
  switch (urgency) {
    case "LifeSafety": return "$4,800 – $9,600"
    case "Urgent":     return "$2,400 – $4,800"
    case "Routine":    return "$800 – $2,400"
    case "Estimate":   return "$400 – $1,200"
    default:           return "$800 – $2,400"
  }
}

function getUrgencyRationale(call: Call): string {
  if (call.isSafetyEmergency) {
    return "Active safety hazard detected. Immediate dispatch required."
  }
  switch (call.urgency) {
    case "LifeSafety":
      return "Life-safety situation. High conversion if dispatched within 30 minutes."
    case "Urgent":
      return "Time-sensitive issue. Customer ready for immediate scheduling."
    case "Routine":
      return "Standard service request. Schedule within 24–48 hours."
    case "Estimate":
      return "Estimate requested. Good opportunity for upsell."
    default:
      return "Follow up promptly to maintain customer satisfaction."
  }
}

export function MailDisplay({ call, triageMap, onOutcomeChange }: MailDisplayProps) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [loadingTranscript, setLoadingTranscript] = useState(false)
  const [activeTab, setActiveTab] = useState<"summary" | "transcript">("summary")
  const [submittingOutcome, setSubmittingOutcome] = useState(false)

  const handleOutcome = async (outcome: CallbackOutcome) => {
    if (!call || submittingOutcome) return
    setSubmittingOutcome(true)

    // Optimistic: update parent state immediately
    onOutcomeChange?.(call.id, outcome)

    try {
      const res = await fetch(`/api/calls/${call.id}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome }),
      })
      if (!res.ok) {
        // Revert on failure
        onOutcomeChange?.(call.id, call.callbackOutcome)
      }
    } catch {
      onOutcomeChange?.(call.id, call.callbackOutcome)
    } finally {
      setSubmittingOutcome(false)
    }
  }

  useEffect(() => {
    if (!call) { setTranscript([]); return }
    if (call.transcript.length > 0) { setTranscript(call.transcript); return }

    let cancelled = false
    setLoadingTranscript(true)

    const fetchTranscript = async () => {
      try {
        const response = await fetch(`/api/calls/${call.id}`, { cache: "no-store" })
        if (!response.ok) throw new Error("failed")
        const data = await response.json()
        if (cancelled) return
        setLoadingTranscript(false)
        if (typeof data?.transcript !== "string") { setTranscript([]); return }
        setTranscript(parseTranscript(data.transcript))
      } catch {
        if (!cancelled) { setLoadingTranscript(false); setTranscript([]) }
      }
    }

    fetchTranscript()
    return () => { cancelled = true }
  }, [call])

  if (!call) {
    return (
      <section className="flex-1 bg-[#191a1a] flex items-center justify-center">
        <p className="text-[#acabaa] text-sm">Select a call to view details</p>
      </section>
    )
  }

  const isEmergency = call.isSafetyEmergency || call.urgency === "LifeSafety"
  const isUrgent = call.urgency === "Urgent"

  return (
    <section className="flex-1 bg-[#191a1a] flex flex-col overflow-hidden">
      {/* Header */}
      <header className="p-8 pb-4 flex justify-between items-start flex-shrink-0">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-headline font-extrabold tracking-tighter text-[#e7e5e4]">
              {call.customerName || (call.customerPhone ? formatPhone(call.customerPhone) : "Unknown Caller")}
            </h1>
            {isEmergency && (
              <span className="bg-[#ee7d77] text-[#490106] text-[10px] font-bold px-2 py-1 rounded uppercase tracking-tight">
                Emergency
              </span>
            )}
            {!isEmergency && isUrgent && (
              <span className="bg-[#3b3b3b] text-[#c1bfbe] text-[10px] font-bold px-2 py-1 rounded uppercase tracking-tight">
                Urgent
              </span>
            )}
          </div>
          {call.serviceAddress && (
            <div className="flex items-center gap-2 text-[#acabaa] text-sm mb-1">
              <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>{call.serviceAddress}</span>
            </div>
          )}
          <p className="text-[#acabaa] text-xs">
            {format(new Date(call.createdAt), "PPpp")}
          </p>
        </div>

        <div className="flex gap-2 flex-shrink-0 ml-4">
          <button className="bg-[#3b3b3b] text-[#c1bfbe] px-4 py-2 rounded-lg font-bold text-sm hover:brightness-110 transition-all active:scale-95">
            Archive Lead
          </button>
          <button className="bg-[#c6c6c7] text-[#3f4041] px-6 py-2 rounded-lg font-bold text-sm hover:brightness-110 transition-all active:scale-95">
            Call Client
          </button>
        </div>
      </header>

      {/* Tab toggle */}
      <div className="px-8 pb-0 flex gap-6 border-b border-[#484848]/10 flex-shrink-0">
        <button
          onClick={() => setActiveTab("summary")}
          className={cn(
            "text-sm font-semibold pb-3 border-b-2 transition-colors -mb-px",
            activeTab === "summary"
              ? "text-[#e7e5e4] border-[#c6c6c7]"
              : "text-[#acabaa] border-transparent hover:text-[#e7e5e4]"
          )}
        >
          Summary
        </button>
        <button
          onClick={() => setActiveTab("transcript")}
          className={cn(
            "text-sm font-semibold pb-3 border-b-2 transition-colors -mb-px",
            activeTab === "transcript"
              ? "text-[#e7e5e4] border-[#c6c6c7]"
              : "text-[#acabaa] border-transparent hover:text-[#e7e5e4]"
          )}
        >
          Transcript
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto no-scrollbar p-8 pt-6">
        {activeTab === "summary" ? (
          <div className="space-y-6 max-w-3xl">
            {/* AI Summary Card */}
            <div className="bg-[#252626] p-6 rounded-xl border border-[#484848]/10">
              <div className="flex items-center gap-2 mb-4 text-[#c6c6c7]">
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
                </svg>
                <h3 className="font-headline font-bold">AI Receptionist Summary</h3>
              </div>
              <p className="text-[#e7e5e4] leading-relaxed italic text-sm">
                &ldquo;{buildAISummary(call)}&rdquo;
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Why This Matters */}
              <div className="space-y-4">
                <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                  Why This Matters
                </h4>
                <div className="bg-[#131313] p-5 rounded-xl space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded bg-[#454747] flex items-center justify-center text-[#c6c6c7] shrink-0">
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-[10px] text-[#acabaa] uppercase font-bold">Estimated LTV</p>
                      <p className="text-lg font-headline font-bold text-[#e7e5e4]">
                        {getEstimatedLTV(call.urgency)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded bg-[#7f2927]/20 flex items-center justify-center text-[#ee7d77] shrink-0 mt-0.5">
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-[10px] text-[#acabaa] uppercase font-bold">Urgency Rationale</p>
                      <p className="text-sm text-[#e7e5e4] leading-snug">
                        {getUrgencyRationale(call)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Best Next Move */}
              <div className="space-y-4">
                <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                  Best Next Move
                </h4>
                <div className="flex flex-col gap-3">
                  <button className="w-full flex items-center justify-between p-4 bg-[#c6c6c7] text-[#3f4041] rounded-xl hover:scale-[1.02] transition-transform active:scale-[0.98]">
                    <div className="flex items-center gap-3">
                      <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span className="font-bold text-sm">Schedule Tech Now</span>
                    </div>
                    <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>

                  <button className="w-full flex items-center justify-between p-4 bg-[#3b3b3b] text-[#c1bfbe] rounded-xl hover:scale-[1.02] transition-transform active:scale-[0.98]">
                    <div className="flex items-center gap-3">
                      <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span className="font-bold text-sm">Send Instant Quote</span>
                    </div>
                    <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>

                  <button className="w-full flex items-center justify-between p-4 border border-[#484848]/20 text-[#e7e5e4] rounded-xl hover:bg-[#252626] transition-all">
                    <div className="flex items-center gap-3">
                      <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                      <span className="font-bold text-sm">Transfer to On-Call</span>
                    </div>
                    <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            {/* Callback Outcome Selector */}
            {call && isUnresolved(call) && (
              <div className="space-y-4">
                <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                  Mark Callback Outcome
                </h4>
                <div className="flex flex-wrap gap-2">
                  {([
                    ["reached_customer", "Reached Customer"],
                    ["scheduled", "Scheduled"],
                    ["left_voicemail", "Left Voicemail"],
                    ["no_answer", "No Answer"],
                    ["resolved_elsewhere", "Resolved Elsewhere"],
                  ] as const).map(([value, label]) => (
                    <button
                      key={value}
                      onClick={() => handleOutcome(value)}
                      disabled={submittingOutcome}
                      aria-pressed={call.callbackOutcome === value}
                      className={cn(
                        "px-4 py-3 rounded-lg text-sm font-semibold transition-all duration-200",
                        call.callbackOutcome === value
                          ? "bg-[#10b981] text-white"
                          : "bg-[#3b3b3b] text-[#c1bfbe] hover:bg-[#454747] hover:text-[#e7e5e4]",
                        submittingOutcome && "opacity-50 cursor-not-allowed"
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {call.callbackOutcome && (
                  <p className="text-xs text-[#acabaa]">
                    Current: <span className="text-[#e7e5e4] font-medium">{call.callbackOutcome.replace(/_/g, " ")}</span>
                    {call.callbackOutcomeAt && (
                      <> at {format(new Date(call.callbackOutcomeAt), "h:mm a")}</>
                    )}
                  </p>
                )}
              </div>
            )}

            {/* Callback Window Display */}
            {call && (() => {
              const triage = triageMap?.get(call.id)
              if (!triage || !isUnresolved(call) || !triage.callbackWindowValid || !triage.callbackWindowStart) return null
              const startTime = new Date(triage.callbackWindowStart)
              const endTime = triage.callbackWindowEnd ? new Date(triage.callbackWindowEnd) : null
              return (
                <div className="space-y-4">
                  <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                    Callback Window
                  </h4>
                  <div className="bg-[#252626] p-4 rounded-xl border border-[#484848]/20 flex items-center gap-3">
                    <svg className="h-5 w-5 text-[#acabaa] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                      <p className="text-sm text-[#e7e5e4] font-semibold">
                        {format(startTime, "h:mm a")}
                        {endTime && <> &ndash; {format(endTime, "h:mm a")}</>}
                      </p>
                      <p className="text-xs text-[#acabaa]">Customer available</p>
                    </div>
                  </div>
                </div>
              )
            })()}

            {/* Callback Assist Template */}
            {call && isUnresolved(call) && (() => {
              const triage = triageMap?.get(call.id)
              if (!triage) return null
              const COMPANY_NAME = process.env.NEXT_PUBLIC_COMPANY_NAME ?? "our company"
              const template = getAssistTemplate(triage.reason, COMPANY_NAME)
              return (
                <div className="space-y-4">
                  <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                    Callback Opener
                  </h4>
                  <div className="bg-[#252626] p-5 rounded-xl border border-[#484848]/10">
                    <p className="text-sm text-[#e7e5e4] leading-relaxed italic">
                      &ldquo;{template}&rdquo;
                    </p>
                    <p className="text-[10px] text-[#acabaa] mt-3 uppercase tracking-widest">
                      {triage.reason.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
              )
            })()}

            {/* Equipment Details */}
            {(call.equipmentType || call.equipmentBrand || call.equipmentAge) && (
              <div className="bg-[#252626] p-5 rounded-xl border border-[#484848]/10">
                <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest mb-3">
                  Equipment Details
                </h4>
                <div className="flex flex-wrap gap-3 text-sm text-[#e7e5e4]">
                  {call.equipmentType && <span>{call.equipmentType}</span>}
                  {call.equipmentBrand && (
                    <span className="text-[#acabaa]">· {call.equipmentBrand}</span>
                  )}
                  {call.equipmentAge && (
                    <span className="text-[#acabaa]">· {call.equipmentAge}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Transcript */
          <div className="space-y-2 max-w-3xl">
            {loadingTranscript ? (
              <p className="text-xs text-[#acabaa]">Loading transcript…</p>
            ) : transcript.length > 0 ? (
              transcript.map((entry, i) => (
                <div
                  key={i}
                  className={cn(
                    "rounded-lg px-4 py-3 text-sm",
                    entry.role === "agent" ? "bg-[#252626]" : "bg-[#131313]"
                  )}
                >
                  <span className="text-[10px] font-bold text-[#acabaa] uppercase tracking-wider">
                    {entry.role === "agent" ? "AI Agent" : "Customer"}
                  </span>
                  <p className="mt-1 text-[#e7e5e4] leading-relaxed">{entry.content}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-[#acabaa]">No transcript available</p>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
