"use client"

import { useState, useCallback } from "react"
import { formatDistanceToNow, format, isToday, isTomorrow } from "date-fns"
import {
  AlertCircle,
  AlertTriangle,
  CalendarCheck,
  CheckCircle2,
  ChevronRight,
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
import { isActionable } from "@/lib/triage"
import type { BucketAssignment } from "@/lib/triage"
import type { Call, CallbackOutcome, TriageResult } from "@/types/call"

interface MailListProps {
  items: Call[]
  selected: string | null
  onSelect: (id: string) => void
  onOutcomeChange?: (callId: string, outcome: CallbackOutcome | null) => void
  triageMap?: Map<string, TriageResult>
  pulsingId?: string | null
  onCallBackTap?: (callId: string) => void
  onPulseClear?: () => void
  buckets?: {
    ESCALATED_BY_AI: Call[]
    NEW_LEADS: Call[]
    FOLLOW_UPS: Call[]
    BOOKED_BY_AI: Call[]
    OTHER_AI_HANDLED: Call[]
  }
  bucketMap?: Map<string, BucketAssignment>
}

const COMMAND_STYLES: Record<string, { text: string; bg: string }> = {
  "Call now": { text: "text-[#5e1b1a]", bg: "bg-cl-danger/80" },
  "Next up": { text: "text-[#d2d0cf]", bg: "bg-[#474746]" },
  "Today": { text: "text-[#acabab]", bg: "bg-[#474848]" },
  "Can wait": { text: "text-[#757575]", bg: "bg-cl-bg-card" },
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

function formatOutcomeAge(call: Call): string {
  if (!call.callbackOutcomeAt) return ""
  try {
    return formatDistanceToNow(new Date(call.callbackOutcomeAt), { addSuffix: true })
  } catch {
    return ""
  }
}

const OUTCOME_CONFIG = [
  { value: "reached_customer" as CallbackOutcome, label: "Reached Customer", Icon: UserCheck },
  { value: "scheduled" as CallbackOutcome, label: "Scheduled", Icon: CalendarCheck },
  { value: "left_voicemail" as CallbackOutcome, label: "Left Voicemail", Icon: Voicemail },
  { value: "no_answer" as CallbackOutcome, label: "No Answer", Icon: PhoneMissed },
  { value: "resolved_elsewhere" as CallbackOutcome, label: "Resolved Elsewhere", Icon: CircleCheck },
] as const

type CardSection = "ESCALATED_BY_AI" | "NEW_LEADS" | "FOLLOW_UPS" | "BOOKED_BY_AI" | "OTHER_AI_HANDLED"

export function MailList({
  items,
  selected,
  onSelect,
  onOutcomeChange,
  triageMap,
  onCallBackTap,
  buckets,
  bucketMap,
}: MailListProps) {
  const [submittingId, setSubmittingId] = useState<string | null>(null)
  const [flashingState, setFlashingState] = useState<{
    cardId: string
    outcome: CallbackOutcome
  } | null>(null)
  const [otherHandledExpanded, setOtherHandledExpanded] = useState(false)
  const [activeTab, setActiveTab] = useState<"active" | "booked">("active")

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
  const renderCard = (item: Call, section: CardSection) => {
    const isActive = selected === item.id
    const triage = triageMap?.get(item.id)
    const callActionable = isActionable(item)
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
          section === "OTHER_AI_HANDLED" && "opacity-50",
          isActive
            ? "bg-cl-bg-selected"
            : "bg-cl-bg-canvas hover:bg-cl-bg-subtle"
        )}
        onClick={() => onSelect(item.id)}
      >
        {/* Escalated panel */}
        {section === "ESCALATED_BY_AI" && (
          <div
            className="w-[56px] shrink-0 flex flex-col items-center justify-center text-[10px] font-black tracking-tighter uppercase leading-none px-1 text-center bg-cl-bg-elevated text-cl-text-muted"
            aria-label="Safety escalation"
          >
            <AlertTriangle className="h-4 w-4 mb-1" />
            <span className="block">ESCA</span>
            <span className="block">LATED</span>
          </div>
        )}

        {/* Booked panel */}
        {section === "BOOKED_BY_AI" && (
          <div
            className="w-[56px] shrink-0 flex flex-col items-center justify-center text-[10px] font-black tracking-tighter uppercase leading-none px-1 text-center bg-cl-success/20 text-cl-success"
            aria-label="Booked by AI"
          >
            <CheckCircle2 className="h-4 w-4 mb-1" />
            <span className="block">BOOK</span>
            <span className="block">ED</span>
          </div>
        )}

        {/* Triage priority panel — NEW_LEADS only */}
        {section === "NEW_LEADS" && callActionable && triage && (
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
            {triage.isStale && (
              <span className="block mt-0.5 text-[8px] font-semibold opacity-80">
                {triage.staleMinutes}m
              </span>
            )}
          </div>
        )}

        {/* Card content */}
        <div className="flex-1 p-4 flex flex-col gap-2 min-w-0">
          {/* Line 1: Name · evidence | time-ago */}
          <div className="flex justify-between items-start gap-2">
            <div className="flex items-baseline gap-1.5 min-w-0 truncate">
              {!item.read && (
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-cl-accent shrink-0 mt-1.5 mr-1" aria-label="Unread" />
              )}
              <span className={cn("text-sm truncate", item.read ? "text-cl-text-primary font-semibold" : "text-cl-text-primary font-bold")}>
                {item.customerName || (item.customerPhone ? formatPhone(item.customerPhone) : "Unknown")}
              </span>
              {triage?.evidence && section === "NEW_LEADS" && (
                <>
                  <span className="text-cl-text-muted text-[0.6875rem]">&middot;</span>
                  <span className="text-cl-text-muted text-[0.6875rem] truncate">{triage.evidence}</span>
                </>
              )}
            </div>
            <span className="text-[0.6875rem] text-cl-text-muted shrink-0 ml-2">
              {formatDistanceToNow(new Date(item.createdAt), { addSuffix: false })} ago
            </span>
          </div>

          {/* Line 2: Snippet */}
          <p className="text-cl-text-muted text-sm line-clamp-2 leading-relaxed">{snippet}</p>

          {/* Escalated: safety label */}
          {section === "ESCALATED_BY_AI" && (
            <span className="inline-flex items-center gap-1 w-fit px-2 py-0.5 rounded-full bg-cl-bg-elevated text-cl-text-muted text-[0.6875rem] font-semibold uppercase">
              <AlertTriangle className="h-3 w-3" />
              {item.isSafetyEmergency ? "Safety emergency escalated" : "Urgent issue escalated"}
            </span>
          )}

          {/* Booked: appointment time */}
          {section === "BOOKED_BY_AI" && (
            <span className="inline-flex items-center gap-1 w-fit px-2 py-0.5 rounded-full bg-cl-success/10 text-cl-success text-[0.6875rem] font-semibold uppercase">
              <CheckCircle2 className="h-3 w-3" />
              Appointment secured · {formatAppointmentTime(item.appointmentDateTime)}
            </span>
          )}

          {/* Follow-up: previous outcome chip instead of triage panel */}
          {section === "FOLLOW_UPS" && item.callbackOutcome && (
            <span className="inline-flex items-center gap-1 w-fit px-2 py-0.5 rounded-full bg-cl-bg-chip text-cl-text-subtle text-[0.6875rem] font-semibold uppercase">
              {item.callbackOutcome.replace(/_/g, " ")}
              {item.callbackOutcomeAt && (
                <span className="text-cl-text-muted normal-case font-normal">
                  {" "}{formatOutcomeAge(item)}
                </span>
              )}
            </span>
          )}

          {/* Line 3: CALL BACK — NEW_LEADS and FOLLOW_UPS only */}
          {(section === "NEW_LEADS" || section === "FOLLOW_UPS") && callActionable && item.customerPhone && (
            <a
              href={`tel:${item.customerPhone}`}
              aria-label={`Call back ${item.customerName || "customer"}`}
              className={cn(
                "mt-1 h-8 text-[0.6875rem] font-bold rounded-md flex items-center justify-center gap-2 uppercase tracking-widest transition-colors no-underline",
                "bg-cl-bg-chip text-cl-text-subtle hover:bg-cl-bg-chip-hover"
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

          {/* Line 4: Outcome chips — selected card only, action queue sections */}
          {(section === "NEW_LEADS" || section === "FOLLOW_UPS") && isActive && callActionable && (
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
                        ? "bg-cl-success text-white"
                        : isSelected
                          ? "bg-cl-success/20 text-cl-success"
                          : "bg-cl-bg-chip text-cl-text-subtle hover:bg-cl-bg-chip-hover"
                    )}
                  >
                    <OutcomeIcon className="h-3 w-3" />
                    {label}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-black p-8">
        <p className="text-cl-text-muted text-sm font-medium">All caught up — no callbacks needed</p>
      </div>
    )
  }

  // Bucket-based rendering
  if (buckets && bucketMap) {
    const otherCount = buckets.OTHER_AI_HANDLED.length
    const bookedCount = buckets.BOOKED_BY_AI.length

    return (
      <div className="flex-1 flex flex-col overflow-hidden bg-cl-bg-canvas">
        {/* Tab bar */}
        <div className="flex shrink-0 px-4 pt-3 gap-1 border-b border-cl-border">
          <button
            onClick={() => setActiveTab("active")}
            className={cn(
              "px-3 pb-2.5 text-xs font-semibold uppercase tracking-wider transition-colors border-b-2 -mb-px",
              activeTab === "active"
                ? "text-cl-text-primary border-cl-accent"
                : "text-cl-text-muted border-transparent hover:text-cl-text-primary"
            )}
          >
            Active
          </button>
          <button
            onClick={() => setActiveTab("booked")}
            className={cn(
              "px-3 pb-2.5 text-xs font-semibold uppercase tracking-wider transition-colors border-b-2 -mb-px flex items-center gap-1.5",
              activeTab === "booked"
                ? "text-cl-success border-cl-success"
                : "text-cl-text-muted border-transparent hover:text-cl-text-primary"
            )}
          >
            Booked by AI
            {bookedCount > 0 && (
              <span className={cn(
                "inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-full text-[10px] font-bold",
                activeTab === "booked"
                  ? "bg-cl-success/20 text-cl-success"
                  : "bg-cl-bg-card text-cl-text-muted"
              )}>
                {bookedCount}
              </span>
            )}
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col gap-1 p-4 pb-24">
          {activeTab === "active" ? (
            <>
              {/* New Leads */}
              {buckets.NEW_LEADS.length > 0 && (
                <>
                  <h3
                    role="heading"
                    aria-level={3}
                    className="font-headline text-[1.75rem] font-bold text-cl-text-primary tracking-[-0.02em] pt-4 pb-2"
                  >
                    New Leads ({buckets.NEW_LEADS.length})
                  </h3>
                  <div className="flex flex-col gap-1">
                    {buckets.NEW_LEADS.map((item) => renderCard(item, "NEW_LEADS"))}
                  </div>
                </>
              )}

              {/* Escalated by AI */}
              {buckets.ESCALATED_BY_AI.length > 0 && (
                <>
                  <h3
                    role="heading"
                    aria-level={3}
                    className="font-headline text-[1.75rem] font-bold text-cl-text-primary tracking-[-0.02em] mt-8 pb-2"
                  >
                    Escalated by AI ({buckets.ESCALATED_BY_AI.length})
                  </h3>
                  <div className="flex flex-col gap-1">
                    {buckets.ESCALATED_BY_AI.map((item) => renderCard(item, "ESCALATED_BY_AI"))}
                  </div>
                </>
              )}

              {/* Follow-ups */}
              {buckets.FOLLOW_UPS.length > 0 && (
                <>
                  <h3
                    role="heading"
                    aria-level={3}
                    className="font-headline text-[1.75rem] font-bold text-cl-text-primary tracking-[-0.02em] mt-8 pb-2"
                  >
                    Follow-ups ({buckets.FOLLOW_UPS.length})
                  </h3>
                  <div className="flex flex-col gap-1">
                    {buckets.FOLLOW_UPS.map((item) => renderCard(item, "FOLLOW_UPS"))}
                  </div>
                </>
              )}

              {/* Other AI Handled (collapsible) */}
              {otherCount > 0 && (
                <div className="mt-8">
                  <button
                    onClick={() => setOtherHandledExpanded((prev) => !prev)}
                    aria-expanded={otherHandledExpanded}
                    aria-controls="other-ai-handled-list"
                    className="w-full flex items-center justify-between py-3 px-1 text-left group"
                  >
                    <span className="text-sm font-semibold text-cl-text-muted uppercase tracking-wider">
                      Other AI Handled ({otherCount})
                    </span>
                    <ChevronRight
                      className={cn(
                        "h-4 w-4 text-cl-text-muted transition-transform duration-200",
                        otherHandledExpanded && "rotate-90"
                      )}
                    />
                  </button>
                  <div
                    id="other-ai-handled-list"
                    className={cn(
                      "overflow-hidden transition-all duration-200",
                      otherHandledExpanded ? "max-h-[5000px] opacity-100" : "max-h-0 opacity-0"
                    )}
                  >
                    <div className="flex flex-col gap-1">
                      {buckets.OTHER_AI_HANDLED.map((item) => renderCard(item, "OTHER_AI_HANDLED"))}
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <>
              {/* Booked by AI tab */}
              {bookedCount > 0 ? (
                <>
                  <h3
                    role="heading"
                    aria-level={3}
                    className="font-headline text-[1.75rem] font-bold text-cl-success tracking-[-0.02em] pt-4 pb-2"
                  >
                    Booked by AI ({bookedCount})
                  </h3>
                  <div className="flex flex-col gap-1">
                    {buckets.BOOKED_BY_AI.map((item) => renderCard(item, "BOOKED_BY_AI"))}
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center p-8">
                  <p className="text-cl-text-muted text-sm font-medium">No bookings yet</p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    )
  }

  // Fallback: flat list (no buckets)
  return (
    <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col gap-1 p-4 pb-24 bg-cl-bg-canvas">
      {items.map((item) => renderCard(item, "NEW_LEADS"))}
    </div>
  )
}
