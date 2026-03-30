"use client"

import { useEffect, useState } from "react"
import { format, isToday, isTomorrow } from "date-fns"
import { parseTranscript, formatPhone } from "@/lib/transforms"
import type { Call, TranscriptEntry } from "@/types/call"
import { cn } from "@/lib/utils"

interface ScheduledDisplayProps {
  call: Call | null
}

function formatServiceWindow(dateStr: string | null): { date: string; time: string } {
  if (!dateStr) return { date: "Date TBD", time: "Time TBD" }
  try {
    const d = new Date(dateStr)
    const date = isToday(d)
      ? "Today"
      : isTomorrow(d)
        ? "Tomorrow"
        : format(d, "EEE, MMM d")
    const time = format(d, "h:mm a")
    return { date, time }
  } catch {
    return { date: "Date TBD", time: "Time TBD" }
  }
}

function buildDiagnosticSummary(call: Call): string {
  const parts: string[] = []
  if (call.problemDescription) {
    parts.push(call.problemDescription)
  } else if (call.hvacIssueType) {
    parts.push(`Service request for ${call.hvacIssueType} issue.`)
  }
  if (call.equipmentType || call.equipmentBrand) {
    const equip = [call.equipmentType, call.equipmentBrand].filter(Boolean).join(" — ")
    parts.push(`Equipment: ${equip}.`)
  }
  if (call.serviceAddress) {
    parts.push(`Service location: ${call.serviceAddress}.`)
  }
  return parts.join(" ") || "No diagnostic details available."
}

function getIssueTags(call: Call): string[] {
  const tags: string[] = []
  if (call.hvacIssueType) tags.push(`#${call.hvacIssueType.replace(/\s+/g, "")}`)
  if (call.equipmentType) tags.push(`#${call.equipmentType.replace(/\s+/g, "")}`)
  if (call.equipmentBrand) tags.push(`#${call.equipmentBrand.replace(/\s+/g, "")}`)
  return tags
}

export function ScheduledDisplay({ call }: ScheduledDisplayProps) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [loadingTranscript, setLoadingTranscript] = useState(false)
  const [activeTab, setActiveTab] = useState<"booking" | "transcript">("booking")

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
        <p className="text-[#acabaa] text-sm">Select an appointment to view details</p>
      </section>
    )
  }

  const serviceWindow = formatServiceWindow(call.appointmentDateTime)
  const isEmergency = call.isSafetyEmergency || call.urgency === "LifeSafety"
  const isUrgent = call.urgency === "Urgent"
  const tags = getIssueTags(call)

  return (
    <section className="flex-1 bg-[#191a1a] flex flex-col overflow-hidden">
      {/* Header — matches MailDisplay structure */}
      <header className="p-8 pb-4 flex justify-between items-start flex-shrink-0">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-headline font-extrabold tracking-tighter text-[#e7e5e4]">
              {call.customerName || (call.customerPhone ? formatPhone(call.customerPhone) : "Unknown Caller")}
            </h1>
            <span className="bg-[#10b981]/10 text-[#10b981] text-[10px] font-bold px-2 py-1 rounded uppercase tracking-tight border border-[#10b981]/20">
              Scheduled
            </span>
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
            Reschedule
          </button>
          <button className="bg-[#10b981] text-[#004a31] px-6 py-2 rounded-lg font-bold text-sm hover:brightness-110 transition-all active:scale-95">
            Assign Tech
          </button>
        </div>
      </header>

      {/* Tab toggle — matches MailDisplay */}
      <div className="px-8 pb-0 flex gap-6 border-b border-[#484848]/10 flex-shrink-0">
        <button
          onClick={() => setActiveTab("booking")}
          className={cn(
            "text-sm font-semibold pb-3 border-b-2 transition-colors -mb-px",
            activeTab === "booking"
              ? "text-[#e7e5e4] border-[#c6c6c7]"
              : "text-[#acabaa] border-transparent hover:text-[#e7e5e4]"
          )}
        >
          Booking
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
        {activeTab === "booking" ? (
          <div className="space-y-6 max-w-3xl">
            {/* Booking Confirmed Card */}
            <div className="bg-[#252626] p-6 rounded-xl border border-[#484848]/10 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-48 h-full bg-gradient-to-l from-[#10b981]/5 to-transparent" />
              <div className="relative z-10 flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-[#10b981]/10 flex items-center justify-center text-[#10b981] ring-4 ring-[#10b981]/5 shrink-0">
                  <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-headline font-bold text-[#e7e5e4]">Booking Confirmed</h3>
                  <p className="text-[#acabaa] text-sm">
                    Reservation secured. Pre-diagnostic AI review complete.
                  </p>
                </div>
              </div>
            </div>

            {/* Service Window + Tech Assignment */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Service Window */}
              <div className="space-y-4">
                <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                  Service Window
                </h4>
                <div className="bg-[#131313] p-5 rounded-xl space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded bg-[#454747] flex items-center justify-center text-[#c6c6c7] shrink-0">
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-[10px] text-[#acabaa] uppercase font-bold">Date</p>
                      <p className="text-lg font-headline font-bold text-[#e7e5e4]">
                        {serviceWindow.date}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded bg-[#454747] flex items-center justify-center text-[#c6c6c7] shrink-0">
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-[10px] text-[#acabaa] uppercase font-bold">Time</p>
                      <p className="text-lg font-headline font-bold text-[#e7e5e4]">
                        {serviceWindow.time}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Technician Assignment */}
              <div className="space-y-4">
                <h4 className="font-headline font-bold text-[#acabaa] text-xs uppercase tracking-widest">
                  Technician
                </h4>
                <div className="flex flex-col gap-3">
                  <button className="w-full flex items-center justify-between p-4 bg-[#10b981] text-[#004a31] rounded-xl hover:scale-[1.02] transition-transform active:scale-[0.98]">
                    <div className="flex items-center gap-3">
                      <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                      </svg>
                      <span className="font-bold text-sm">Assign Technician</span>
                    </div>
                    <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>

                  <button className="w-full flex items-center justify-between p-4 bg-[#3b3b3b] text-[#c1bfbe] rounded-xl hover:scale-[1.02] transition-transform active:scale-[0.98]">
                    <div className="flex items-center gap-3">
                      <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>
                      <span className="font-bold text-sm">Message Customer</span>
                    </div>
                    <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>

                  <button className="w-full flex items-center justify-between p-4 border border-[#484848]/20 text-[#e7e5e4] rounded-xl hover:bg-[#252626] transition-all">
                    <div className="flex items-center gap-3">
                      <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span className="font-bold text-sm">Reschedule</span>
                    </div>
                    <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            {/* AI Diagnostic Summary */}
            <div className="bg-[#252626] p-6 rounded-xl border border-[#484848]/10">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 text-[#c6c6c7]">
                  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1.17A3.001 3.001 0 0117 21H7a3.001 3.001 0 01-2.83-2H3a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2zm-4 14a1 1 0 100 2 1 1 0 000-2zm8 0a1 1 0 100 2 1 1 0 000-2z" />
                  </svg>
                  <h3 className="font-headline font-bold">AI Diagnostic Summary</h3>
                </div>
                <span className="text-[10px] text-[#acabaa] font-mono bg-[#131313] px-2 py-1 rounded">
                  {format(new Date(call.createdAt), "h:mm a")}
                </span>
              </div>
              <p className="text-[#e7e5e4] leading-relaxed italic text-sm">
                &ldquo;{buildDiagnosticSummary(call)}&rdquo;
              </p>
              {tags.length > 0 && (
                <div className="flex gap-2 mt-4">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-3 py-1 bg-[#131313] rounded-full text-xs font-medium text-[#e7e5e4]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>

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
          /* Transcript — identical to MailDisplay */
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
