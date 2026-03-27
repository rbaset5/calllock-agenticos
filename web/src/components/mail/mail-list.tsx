"use client"

import { useState, useCallback } from "react"
import { formatDistanceToNow, format, isToday, isTomorrow } from "date-fns"
import {
  AlertCircle,
  AlertTriangle,
  CalendarCheck,
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
import type { BucketAssignment, HandledReason } from "@/lib/triage"
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
  buckets?: { NEW_LEADS: Call[]; FOLLOW_UPS: Call[]; AI_HANDLED: Call[] }
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

const HANDLED_REASON_LABELS: Record<HandledReason, string> = {
  escalated: "escalated",
  resolved: "resolved",
  non_customer: "spam/vendor",
  wrong_number: "wrong number",
  booked: "booked",
}

type CardSection = "NEW_LEADS" | "FOLLOW_UPS" | "AI_HANDLED"

export function MailList({
  items,
  selected,
  onSelect,
  onOutcomeChange,
  triageMap,
  pulsingId,
  onCallBackTap,
  onPulseClear,
  buckets,
  bucketMap,
}: MailListProps) {
  const [submittingId, setSubmittingId] = useState<string | null>(null)
  const [flashingState, setFlashingState] = useState<{
    cardId: string
    outcome: CallbackOutcome
  } | null>(null)
  const [aiHandledExpanded, setAiHandledExpanded] = useState(false)

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
    const assignment = bucketMap?.get(item.id)

    return (
      <div
        key={item.id}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(item.id) } }}
        className={cn(
          "flex items-stretch overflow-hidden rounded-lg cursor-pointer transition-all duration-200 shrink-0",
          section === "AI_HANDLED" && "opacity-50",
          isActive
            ? "bg-cl-bg-selected"
            : "bg-cl-bg-canvas hover:bg-cl-bg-subtle"
        )}
        onClick={() => onSelect(item.id)}
      >
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

          {/* AI_HANDLED: show escalation marker or handled reason */}
          {section === "AI_HANDLED" && assignment && (
            <span className="inline-flex items-center gap-1 text-[0.6875rem] text-cl-text-muted">
              {assignment.escalationMarker && (
                <AlertTriangle className="h-3 w-3 text-cl-danger" />
              )}
              {assignment.handledReason && (
                <span className="capitalize">
                  {HANDLED_REASON_LABELS[assignment.handledReason]}
                </span>
              )}
            </span>
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
    // Compute AI Handled sub-counts from bucketMap
    const aiHandledSubCounts = new Map<HandledReason, number>()
    for (const call of buckets.AI_HANDLED) {
      const assignment = bucketMap.get(call.id)
      if (assignment?.handledReason) {
        aiHandledSubCounts.set(
          assignment.handledReason,
          (aiHandledSubCounts.get(assignment.handledReason) ?? 0) + 1
        )
      }
    }

    const subCountParts: string[] = []
    const escalated = aiHandledSubCounts.get("escalated") ?? 0
    const resolved = aiHandledSubCounts.get("resolved") ?? 0
    const nonCustomer = aiHandledSubCounts.get("non_customer") ?? 0
    const wrongNumber = aiHandledSubCounts.get("wrong_number") ?? 0
    const booked = aiHandledSubCounts.get("booked") ?? 0

    if (escalated > 0) subCountParts.push(`\u26A0 ${escalated} escalated`)
    if (resolved > 0) subCountParts.push(`${resolved} resolved`)
    if (booked > 0) subCountParts.push(`${booked} booked`)
    if (nonCustomer > 0) subCountParts.push(`${nonCustomer} spam/vendor`)
    if (wrongNumber > 0) subCountParts.push(`${wrongNumber} wrong number`)

    const subCountSummary = subCountParts.join(" \u00B7 ")

    return (
      <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col gap-1 p-4 pb-24 bg-cl-bg-canvas">
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

        {/* AI Handled (collapsible) */}
        {buckets.AI_HANDLED.length > 0 && (
          <div className="mt-8">
            <button
              onClick={() => setAiHandledExpanded((prev) => !prev)}
              aria-expanded={aiHandledExpanded}
              aria-controls="ai-handled-list"
              className="w-full flex items-center justify-between py-3 px-1 text-left group"
            >
              <div className="flex flex-col gap-1">
                <span className="text-sm font-semibold text-cl-text-muted uppercase tracking-wider">
                  AI Handled ({buckets.AI_HANDLED.length})
                </span>
                {subCountSummary && (
                  <span className="text-[0.6875rem] text-cl-text-muted">
                    {subCountSummary}
                  </span>
                )}
              </div>
              <ChevronRight
                className={cn(
                  "h-4 w-4 text-cl-text-muted transition-transform duration-200",
                  aiHandledExpanded && "rotate-90"
                )}
              />
            </button>

            <div
              id="ai-handled-list"
              className={cn(
                "overflow-hidden transition-all duration-200",
                aiHandledExpanded ? "max-h-[5000px] opacity-100" : "max-h-0 opacity-0"
              )}
            >
              <div className="flex flex-col gap-1">
                {buckets.AI_HANDLED.map((item) => renderCard(item, "AI_HANDLED"))}
              </div>
            </div>
          </div>
        )}
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
