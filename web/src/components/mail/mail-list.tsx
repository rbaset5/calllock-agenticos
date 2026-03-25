"use client"

import { formatDistanceToNow, format, isToday, isTomorrow } from "date-fns"
import { cn } from "@/lib/utils"
import { formatPhone } from "@/lib/transforms"
import type { Call, TriageResult } from "@/types/call"

interface MailListProps {
  items: Call[]
  selected: string | null
  onSelect: (id: string) => void
  view?: "activity" | "scheduled"
  triageMap?: Map<string, TriageResult>
}

const COMMAND_STYLES: Record<string, { text: string; border: string }> = {
  "Call now": { text: "text-[#e7e5e4]", border: "border-l-[#e7e5e4]" },
  "Next up":  { text: "text-[#c6c6c7]", border: "border-l-[#c6c6c7]" },
  "Today":    { text: "text-[#acabaa]", border: "border-l-[#acabaa]" },
  "Can wait": { text: "text-[#767575]", border: "border-l-[#767575]" },
}

function getUrgencyChip(call: Call): { label: string; bg: string; text: string } {
  const isEmergency = call.isSafetyEmergency || call.urgency === "LifeSafety"
  if (isEmergency) {
    return {
      label: call.hvacIssueType || "Emergency",
      bg: "bg-[#7f2927]",
      text: "text-[#ff9993]",
    }
  }
  return {
    label: call.hvacIssueType || call.urgency,
    bg: "bg-[#3b3b3b]",
    text: "text-[#c1bfbe]",
  }
}

function getStatusChip(call: Call): { label: string; bg: string; text: string } | null {
  if (call.appointmentBooked) {
    return { label: "captured-lead", bg: "bg-[#c8cbfe]", text: "text-[#3e426c]" }
  }
  if (
    call.endCallReason === "wrong_number" ||
    call.endCallReason === "out_of_area" ||
    call.endCallReason === "cancelled"
  ) {
    return null
  }
  return { label: "requires-followup", bg: "bg-[#252626]", text: "text-[#acabaa]" }
}

function formatAppointmentTime(dateStr: string | null): string {
  if (!dateStr) return "Time TBD"
  try {
    const d = new Date(dateStr)
    if (isToday(d)) return `Today @ ${format(d, "h:mm a")}`
    if (isTomorrow(d)) return `Tomorrow @ ${format(d, "h:mm a")}`
    return format(d, "MMM d @ h:mm a")
  } catch {
    return "Time TBD"
  }
}

export function MailList({ items, selected, onSelect, view = "activity", triageMap }: MailListProps) {
  if (items.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <p className="text-[#acabaa] text-sm">
          {view === "scheduled" ? "No scheduled appointments" : "No calls yet"}
        </p>
      </div>
    )
  }

  // ── Scheduled / Upcoming view ──
  if (view === "scheduled") {
    return (
      <div className="flex-1 overflow-y-auto no-scrollbar pb-20">
        {items.map((item) => {
          const isActive = selected === item.id
          const isEmergency = item.isSafetyEmergency || item.urgency === "LifeSafety"
          const isUrgent = item.urgency === "Urgent"
          const equipmentLabel = [item.equipmentType, item.equipmentBrand].filter(Boolean).join(" ")

          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              className={cn(
                "w-full text-left p-4 cursor-pointer transition-all border-b border-[#484848]/5",
                isActive
                  ? "bg-[#1f2020] border-l-4 border-l-[#10b981]"
                  : "hover:bg-[#191a1a] border-l-4 border-l-transparent"
              )}
            >
              <div className="flex justify-between items-start mb-2">
                <span className={cn(
                  "text-xs font-bold uppercase tracking-widest",
                  isActive ? "text-[#10b981]" : "text-[#acabaa]"
                )}>
                  {formatAppointmentTime(item.appointmentDateTime)}
                </span>
                {(isEmergency || isUrgent) && (
                  <span className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded font-bold",
                    isEmergency
                      ? "bg-[#7f2927] text-[#ff9993]"
                      : "bg-[#3b3b3b] text-[#c1bfbe]"
                  )}>
                    {isEmergency ? "EMERGENCY" : "URGENT"}
                  </span>
                )}
              </div>
              <p className="text-[#e7e5e4] font-semibold text-base">
                {item.customerName || (item.customerPhone ? formatPhone(item.customerPhone) : "Unknown")}
              </p>
              {(equipmentLabel || item.hvacIssueType) && (
                <p className="text-[#acabaa] text-sm flex items-center gap-1 mt-1">
                  <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                  </svg>
                  {equipmentLabel || item.hvacIssueType}
                </p>
              )}
            </button>
          )
        })}
      </div>
    )
  }

  // ── Activity / Default view ──
  return (
    <div className="flex-1 overflow-y-auto no-scrollbar px-3 space-y-2 pb-20">
      {items.map((item) => {
        const isActive = selected === item.id
        const urgencyChip = getUrgencyChip(item)
        const statusChip = getStatusChip(item)
        const snippet = item.problemDescription || item.hvacIssueType || "Missed call"
        const triage = triageMap?.get(item.id)
        const unresolved = triage?.isUnresolved ?? false
        const style = COMMAND_STYLES[triage?.command ?? "Can wait"] ?? COMMAND_STYLES["Can wait"]

        return (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            className={cn(
              "w-full text-left p-4 rounded-lg cursor-pointer transition-all duration-200 group flex gap-3",
              isActive ? "bg-[#2c2c2c]" : "hover:bg-[#1f2020]"
            )}
          >
            {/* Triage block — desktop: full, mobile: compact */}
            {unresolved && triage && (
              <>
                {/* Desktop: 72px with command + evidence + stale */}
                <div className={cn(
                  "hidden md:flex w-[72px] shrink-0 flex-col items-start justify-center gap-0.5 border-l-2 pl-2",
                  style.border
                )}
                  aria-label={`Priority: ${triage.command}. Reason: ${triage.evidence}. ${triage.staleMinutes} minutes waiting.`}
                >
                  <span className={cn("text-[10px] font-bold uppercase tracking-tight", style.text)}>
                    {triage.command}
                  </span>
                  <span className="text-[9px] text-[#acabaa] leading-tight line-clamp-2">
                    {triage.evidence}
                  </span>
                  {triage.isStale && (
                    <span className="text-[8px] text-[#ff9993] font-bold mt-0.5">
                      {triage.staleMinutes}m ago
                    </span>
                  )}
                  {triage.callbackWindowValid && triage.callbackWindowStart && (
                    <span className="text-[8px] text-[#acabaa] mt-0.5">
                      Avail {new Date(triage.callbackWindowStart).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                    </span>
                  )}
                </div>
                {/* Mobile: 56px with command only */}
                <div className={cn(
                  "flex md:hidden w-[56px] shrink-0 flex-col items-start justify-center border-l-2 pl-2",
                  style.border
                )}
                  aria-label={`Priority: ${triage.command}`}
                >
                  <span className={cn("text-[10px] font-bold uppercase tracking-tight", style.text)}>
                    {triage.command}
                  </span>
                </div>
              </>
            )}

            {/* Existing row content */}
            <div className="flex-1 min-w-0">
              <div className="flex justify-between items-start mb-2">
                <div className="flex flex-col">
                  <span
                    className={cn(
                      "font-sans font-bold text-sm",
                      isActive ? "text-[#e7e5e4]" : "text-[#acabaa] group-hover:text-[#e7e5e4]"
                    )}
                  >
                    {item.customerName || (item.customerPhone ? formatPhone(item.customerPhone) : "Unknown")}
                  </span>
                  {item.customerName && item.customerPhone && (
                    <span className="text-[11px] text-[#acabaa] mt-0.5">
                      {formatPhone(item.customerPhone)}
                    </span>
                  )}
                </div>
                <span className="text-[10px] text-[#acabaa] shrink-0 ml-2">
                  {formatDistanceToNow(new Date(item.createdAt), { addSuffix: false })} ago
                </span>
              </div>
              <p className="text-sm text-[#acabaa] mb-3 line-clamp-2 leading-snug">
                &ldquo;{snippet}&rdquo;
              </p>
              <div className="flex flex-wrap gap-2">
                <span
                  className={cn(
                    "text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-tighter",
                    urgencyChip.bg,
                    urgencyChip.text
                  )}
                >
                  {urgencyChip.label}
                </span>
                {statusChip && (
                  <span
                    className={cn(
                      "text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-tighter",
                      statusChip.bg,
                      statusChip.text
                    )}
                  >
                    {statusChip.label}
                  </span>
                )}
                {!item.read && (
                  <span className="text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-tighter bg-[#c6c6c7]/10 text-[#c6c6c7]">
                    new
                  </span>
                )}
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
