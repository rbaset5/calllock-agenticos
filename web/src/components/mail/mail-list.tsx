"use client"

import { useState, useCallback } from "react"
import { formatDistanceToNow, format, isToday, isTomorrow } from "date-fns"
import {
  AlertCircle,
  CalendarCheck,
  CircleCheck,
  Clock,
  Minus,
  Phone,
  PhoneMissed,
  UserCheck,
  Voicemail,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { formatPhone } from "@/lib/transforms"
import { isUnresolved } from "@/lib/triage"
import type { SectionKey } from "@/lib/triage"
import type { Call, CallbackOutcome, TriageResult } from "@/types/call"

interface MailListProps {
  items: Call[]
  selected: string | null
  onSelect: (id: string) => void
  onOutcomeChange?: (callId: string, outcome: CallbackOutcome | null) => void
  triageMap?: Map<string, TriageResult>
  pulsingId?: string | null
  onCallBackTap?: (callId: string) => void
  onPulseClear?: () => void  // kept for post-phone return flow
  sections?: Record<SectionKey, Call[]>
}

const COMMAND_STYLES: Record<string, { text: string; bg: string }> = {
  "Call now": { text: "text-[#5e1b1a]", bg: "bg-[#fd9791]/80" },
  "Next up": { text: "text-[#d2d0cf]", bg: "bg-[#474746]" },
  "Today": { text: "text-[#acabab]", bg: "bg-[#474848]" },
  "Can wait": { text: "text-[#757575]", bg: "bg-[#252626]" },
}

const COMMAND_ICONS: Record<string, typeof Phone> = {
  "Call now": Phone,
  "Next up": AlertCircle,
  "Today": Clock,
  "Can wait": Minus,
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

const OUTCOME_CONFIG = [
  { value: "reached_customer" as CallbackOutcome, label: "Reached Customer", Icon: UserCheck },
  { value: "scheduled" as CallbackOutcome, label: "Scheduled", Icon: CalendarCheck },
  { value: "left_voicemail" as CallbackOutcome, label: "Left Voicemail", Icon: Voicemail },
  { value: "no_answer" as CallbackOutcome, label: "No Answer", Icon: PhoneMissed },
  { value: "resolved_elsewhere" as CallbackOutcome, label: "Resolved Elsewhere", Icon: CircleCheck },
] as const

export function MailList({
  items,
  selected,
  onSelect,
  onOutcomeChange,
  triageMap,
  pulsingId,
  onCallBackTap,
  onPulseClear,
  sections,
}: MailListProps) {
  const [submittingId, setSubmittingId] = useState<string | null>(null)
  const [flashingState, setFlashingState] = useState<{
    cardId: string
    outcome: CallbackOutcome
  } | null>(null)

  const handleOutcomeClick = useCallback(
    async (call: Call, outcome: CallbackOutcome) => {
      if (submittingId) return
      const currentOutcome = call.callbackOutcome
      setSubmittingId(call.id)
      setFlashingState({ cardId: call.id, outcome })
      onOutcomeChange?.(call.id, outcome)

      try {
        const res = await fetch(`/api/calls/${call.id}/outcome`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ outcome }),
        })
        if (!res.ok) throw new Error("not-ok")
      } catch {
        onOutcomeChange?.(call.id, currentOutcome)
        toast.error("Couldn't save — try again")
      } finally {
        setSubmittingId(null)
        setTimeout(() => setFlashingState(null), 600)
      }
    },
    [submittingId, onOutcomeChange]
  )

  // Render a single call card
  const renderCard = (item: Call, section: SectionKey) => {
    const isActive = selected === item.id
    const triage = triageMap?.get(item.id)
    const callUnresolved = isUnresolved(item)
    const style = COMMAND_STYLES[triage?.command ?? "Can wait"] ?? COMMAND_STYLES["Can wait"]
    const Icon = COMMAND_ICONS[triage?.command ?? "Can wait"] ?? Minus
    const snippet = item.problemDescription || item.hvacIssueType || "Missed call"

    return (
      <div
        key={item.id}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(item.id) } }}
        className={cn(
          "flex items-stretch overflow-hidden rounded-lg cursor-pointer transition-all duration-200 shrink-0",
          section === "HANDLED" && "opacity-60",
          isActive
            ? "bg-[#252626]"
            : section === "HANDLED" ? "bg-[#131313]" : "bg-[#131313] hover:bg-[#191a1a]"
        )}
        onClick={() => onSelect(item.id)}
      >
        {/* Triage priority panel — NEEDS_CALLBACK only */}
        {section === "NEEDS_CALLBACK" && callUnresolved && triage && (
          <div
            className={cn(
              "w-[56px] shrink-0 flex flex-col items-center justify-center text-[10px] font-black tracking-tighter uppercase leading-none px-1 text-center",
              style.bg, style.text
            )}
            suppressHydrationWarning
            aria-label={`Priority: ${triage.command}. ${triage.evidence}. ${triage.staleMinutes} minutes waiting.`}
          >
            <Icon className="h-4 w-4 mb-1" />
            {triage.command.split(" ").map((word, i) => (
              <span key={i} className="block">{word}</span>
            ))}
          </div>
        )}

        {/* Card content */}
        <div className="flex-1 p-4 flex flex-col gap-2 min-w-0">
          {/* Line 1: Name · evidence | time-ago */}
          <div className="flex justify-between items-start gap-2">
            <div className="flex items-baseline gap-1.5 min-w-0 truncate">
              <span className="text-[#e7e5e4] text-sm font-semibold truncate">
                {item.customerName || (item.customerPhone ? formatPhone(item.customerPhone) : "Unknown")}
              </span>
              {triage?.evidence && section === "NEEDS_CALLBACK" && (
                <>
                  <span className="text-[#acabaa] text-[0.6875rem]">·</span>
                  <span className="text-[#acabaa] text-[0.6875rem] truncate">{triage.evidence}</span>
                </>
              )}
            </div>
            {section !== "UPCOMING" && (
              <span className="text-[0.6875rem] text-[#acabaa] shrink-0 ml-2">
                {formatDistanceToNow(new Date(item.createdAt), { addSuffix: false })} ago
              </span>
            )}
            {section === "UPCOMING" && (
              <span className="text-[0.6875rem] text-[#acabaa] shrink-0 ml-2">
                {formatAppointmentTime(item.appointmentDateTime)}
              </span>
            )}
          </div>

          {/* Line 2: Snippet */}
          <p className="text-[#acabaa] text-sm line-clamp-2 leading-relaxed">{snippet}</p>

          {/* Line 3: CALL BACK — tel: link on ALL platforms (NEEDS_CALLBACK only) */}
          {section === "NEEDS_CALLBACK" && callUnresolved && item.customerPhone && (
            <a
              href={`tel:${item.customerPhone}`}
              aria-label={`Call back ${item.customerName || "customer"}`}
              className={cn(
                "mt-1 h-8 text-[0.6875rem] font-bold rounded-md flex items-center justify-center gap-2 uppercase tracking-widest transition-colors no-underline",
                "bg-[#3b3b3b] text-[#c1bfbe] hover:bg-[#454747]"
              )}
              onClick={(e) => {
                e.stopPropagation()
                onCallBackTap?.(item.id)
              }}
            >
              <Phone className="h-3 w-3" />
              Call Back
            </a>
          )}

          {/* Line 4: Outcome chips — selected card only, NEEDS_CALLBACK */}
          {section === "NEEDS_CALLBACK" && isActive && callUnresolved && (
            <div className="flex gap-1.5 mt-1 flex-wrap">
              {OUTCOME_CONFIG.map(({ value, label, Icon: OutcomeIcon }) => {
                const isSelected = item.callbackOutcome === value
                const isFlashing = flashingState?.cardId === item.id && flashingState.outcome === value
                return (
                  <button
                    key={value}
                    disabled={!!submittingId}
                    onClick={(e) => { e.stopPropagation(); handleOutcomeClick(item, value) }}
                    className={cn(
                      "h-7 px-2.5 rounded-full text-[0.6875rem] uppercase font-semibold flex items-center gap-1 transition-all",
                      isFlashing
                        ? "bg-[#10b981] text-white"
                        : isSelected
                          ? "bg-[#10b981]/20 text-[#10b981]"
                          : "bg-[#3b3b3b] text-[#c1bfbe] hover:bg-[#454747]"
                    )}
                  >
                    <OutcomeIcon className="h-3 w-3" />
                    {label}
                  </button>
                )
              })}
            </div>
          )}

          {/* HANDLED section: show outcome label */}
          {section === "HANDLED" && item.callbackOutcome && (
            <span className="text-[0.6875rem] text-[#acabaa] capitalize">
              {item.callbackOutcome.replace(/_/g, " ")}
            </span>
          )}
        </div>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#000000] p-8">
        <p className="text-[#acabaa] text-sm font-medium">All caught up — no callbacks needed</p>
      </div>
    )
  }

  // Unified timeline with section headers
  if (sections) {
    return (
      <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col gap-1 p-4 pb-24 bg-[#0e0e0e]">
        {/* NEEDS CALLBACK */}
        {sections.NEEDS_CALLBACK.length > 0 && (
          <>
            <h3 className="font-headline text-[1.75rem] font-bold text-[#e7e5e4] tracking-[-0.02em] pt-4 pb-2">
              Needs Callback ({sections.NEEDS_CALLBACK.length})
            </h3>
            <div className="flex flex-col gap-1">
              {sections.NEEDS_CALLBACK.map((item) => renderCard(item, "NEEDS_CALLBACK"))}
            </div>
          </>
        )}

        {/* HANDLED */}
        {sections.HANDLED.length > 0 && (
          <>
            <h3 className="text-sm font-semibold text-[#acabaa] uppercase tracking-wider pt-8 pb-2">
              Handled
            </h3>
            <div className="flex flex-col gap-1">
              {sections.HANDLED.map((item) => renderCard(item, "HANDLED"))}
            </div>
          </>
        )}

        {/* UPCOMING */}
        {sections.UPCOMING.length > 0 && (
          <>
            <h3 className="text-sm font-semibold text-[#acabaa] uppercase tracking-wider pt-8 pb-2">
              Upcoming ({sections.UPCOMING.length})
            </h3>
            <div className="flex flex-col gap-1">
              {sections.UPCOMING.map((item) => renderCard(item, "UPCOMING"))}
            </div>
          </>
        )}
      </div>
    )
  }

  // Fallback: flat list (no sections)
  return (
    <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col gap-1 p-4 pb-24 bg-[#0e0e0e]">
      {items.map((item) => renderCard(item, "NEEDS_CALLBACK"))}
    </div>
  )
}
