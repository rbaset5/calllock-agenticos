"use client"

import { useState, useCallback, useMemo } from "react"
import { formatDistanceToNow, format, isToday, isTomorrow, isYesterday } from "date-fns"
import {
  AlertCircle,
  AlertTriangle,
  CalendarCheck,
  CheckCircle2,
  ChevronRight,
  CircleCheck,
  Clock,
  MessageSquare,
  Minus,
  Phone,
  PhoneMissed,
  RotateCcw,
  UserCheck,
  Voicemail,
  X,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { formatPhone } from "@/lib/transforms"
import { isActionable, isHotFollowUp } from "@/lib/triage"
import type { BucketAssignment } from "@/lib/triage"
import type { BookingStatus, Call, CallbackOutcome, TriageResult } from "@/types/call"
import { CalendarWithEventSlots } from "@/components/ui/calendar-with-event-slots"

interface MailListProps {
  items: Call[]
  selected: string | null
  onSelect: (id: string) => void
  onOutcomeChange?: (callId: string, outcome: CallbackOutcome | null) => void
  onBookingStatusChange?: (callId: string, status: BookingStatus, appointmentDateTime?: string) => void
  triageMap?: Map<string, TriageResult>
  pulsingId?: string | null
  onCallBackTap?: (callId: string) => void
  onPulseClear?: () => void
  buckets?: {
    ESCALATED_BY_AI: Call[]
    NEW_LEADS: Call[]
    FOLLOW_UPS: Call[]
    BOOKINGS: Call[]
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

function truncSeg(s: string, max = 24): string {
  return s.length > max ? s.slice(0, max) + "…" : s
}

function buildIntelSegments(item: Call, isPromoted: boolean): string[] {
  const segs: string[] = []

  if (isPromoted) {
    if (item.endCallReason === "booking_failed") segs.push("Booking failed")
    else if (item.primaryIntent === "complaint") segs.push("Complaint")
    else if (item.primaryIntent === "active_job_issue") segs.push("Active job issue")
  }

  if (item.serviceAddress) segs.push(truncSeg(item.serviceAddress))

  if (item.callerType === "commercial" || item.callerType === "property_manager") {
    segs.push(item.callerType === "commercial" ? "Commercial" : "Property manager")
  } else if (item.revenueTier === "replacement" || item.revenueTier === "major_repair") {
    segs.push(item.revenueTier === "replacement" ? "Replacement opportunity" : "Major repair")
  } else if (item.hvacIssueType) {
    segs.push(item.hvacIssueType)
  }

  return segs.slice(0, 3)
}

type CardSection = "ESCALATED_BY_AI" | "NEW_LEADS" | "FOLLOW_UPS" | "BOOKINGS" | "OTHER_AI_HANDLED"

export function sectionLabel(section: CardSection): string {
  const labels: Record<CardSection, string> = {
    ESCALATED_BY_AI: "Escalated",
    NEW_LEADS: "New",
    FOLLOW_UPS: "Follow-up",
    BOOKINGS: "Bookings",
    OTHER_AI_HANDLED: "Handled",
  }
  return labels[section] ?? ""
}

export function sectionColor(section: CardSection): string {
  const colors: Record<CardSection, string> = {
    ESCALATED_BY_AI: "text-cl-danger",
    NEW_LEADS: "text-cl-accent",
    FOLLOW_UPS: "text-cl-text-muted",
    BOOKINGS: "text-cl-success",
    OTHER_AI_HANDLED: "text-cl-text-muted/60",
  }
  return colors[section] ?? "text-cl-text-muted"
}

export function MailList({
  items,
  selected,
  onSelect,
  onOutcomeChange,
  onBookingStatusChange,
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
  const [activeTab, setActiveTab] = useState<"timeline" | "active">("active")
  const [submittingBookingId, setSubmittingBookingId] = useState<string | null>(null)

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

  const handleBookingAction = useCallback(
    async (call: Call, status: BookingStatus, appointmentDateTime?: string) => {
      if (submittingBookingId) return
      const currentBookingStatus = call.bookingStatus
      setSubmittingBookingId(call.id)
      onBookingStatusChange?.(call.id, status, appointmentDateTime)

      try {
        const res = await fetch(`/api/calls/${call.id}/booking-status`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status, ...(appointmentDateTime ? { appointmentDateTime } : {}) }),
        })
        if (!res.ok) throw new Error("not-ok")
      } catch {
        onBookingStatusChange?.(call.id, currentBookingStatus ?? "cancelled")
        toast.error("Couldn't save — try again")
      } finally {
        setSubmittingBookingId(null)
      }
    },
    [submittingBookingId, onBookingStatusChange]
  )

  const timelineCalls = useMemo(() => {
    const source = buckets
      ? [
          ...buckets.ESCALATED_BY_AI,
          ...buckets.NEW_LEADS,
          ...buckets.FOLLOW_UPS,
          ...buckets.BOOKINGS,
          ...buckets.OTHER_AI_HANDLED,
        ]
      : items
    return [...source].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    )
  }, [buckets, items])

  const timelineGroups = useMemo(() => {
    const groups: { label: string; calls: Call[] }[] = []
    let currentLabel = ""

    for (const call of timelineCalls) {
      const date = new Date(call.createdAt)
      const label = isToday(date) ? "Today" : isYesterday(date) ? "Yesterday" : format(date, "EEEE, MMM d")
      if (label !== currentLabel) {
        groups.push({ label, calls: [call] })
        currentLabel = label
      } else {
        groups[groups.length - 1]?.calls.push(call)
      }
    }

    return groups
  }, [timelineCalls])

  const timelineSectionById = useMemo(() => {
    const sectionById = new Map<string, CardSection>()
    if (buckets) {
      for (const call of buckets.ESCALATED_BY_AI) sectionById.set(call.id, "ESCALATED_BY_AI")
      for (const call of buckets.NEW_LEADS) sectionById.set(call.id, "NEW_LEADS")
      for (const call of buckets.FOLLOW_UPS) sectionById.set(call.id, "FOLLOW_UPS")
      for (const call of buckets.BOOKINGS) sectionById.set(call.id, "BOOKINGS")
      for (const call of buckets.OTHER_AI_HANDLED) sectionById.set(call.id, "OTHER_AI_HANDLED")
    }
    return sectionById
  }, [buckets])

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
            className="w-[56px] shrink-0 flex flex-col items-center justify-center text-[10px] font-black tracking-tighter uppercase leading-none px-1 text-center bg-cl-danger/10 text-cl-danger"
            aria-label="Safety escalation"
          >
            <AlertTriangle className="h-4 w-4 mb-1" />
            <span className="block">ESCA</span>
            <span className="block">LATED</span>
          </div>
        )}

        {/* Bookings: no left panel — status communicated via pill badge in card body */}

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

        {/* Bronze priority panel — hot follow-ups only */}
        {section === "FOLLOW_UPS" && isHotFollowUp(item) && (
          <div
            className="w-[56px] shrink-0 flex flex-col items-center justify-center text-[10px] font-black tracking-tighter uppercase leading-none px-1 text-center bg-cl-opportunity/15 text-cl-opportunity-text"
            aria-label={`Hot follow-up: ${item.endCallReason === "booking_failed" ? "Booking failed" : "Active issue"}`}
          >
            <Phone className="h-4 w-4 mb-1" />
            <span className="block">HOT</span>
            <span className="block">LEAD</span>
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
            <div className="flex items-center gap-2 shrink-0 ml-2">
              {section === "BOOKINGS" && item.appointmentDateTime && (
                <span className="text-xs font-mono text-cl-text-primary shrink-0">
                  {formatAppointmentTime(item.appointmentDateTime)}
                </span>
              )}
              <span className="text-[0.6875rem] text-cl-text-muted shrink-0">
                {formatDistanceToNow(new Date(item.createdAt), { addSuffix: false })} ago
              </span>
            </div>
          </div>

          {/* Line 2: Snippet */}
          <p className="text-cl-text-muted text-sm line-clamp-2 leading-relaxed">{snippet}</p>

          {/* Line 3: Intel line — hot follow-ups only */}
          {section === "FOLLOW_UPS" && isHotFollowUp(item) && (() => {
            if (item.extractionStatus === "pending") {
              return (
                <div className="h-3 w-3/5 rounded bg-cl-bg-card animate-pulse" aria-label="Loading call details" />
              )
            }
            const segs = buildIntelSegments(item, true)
            if (segs.length === 0) return null
            return (
              <p className="text-[0.6875rem] text-cl-text-muted/60 truncate leading-tight" aria-label={`Call details: ${segs.join(", ")}`}>
                {segs.map((seg, i) => (
                  <span key={i}>
                    {i > 0 && <span className="mx-1 text-cl-text-muted/40">&middot;</span>}
                    {seg}
                  </span>
                ))}
              </p>
            )
          })()}

          {/* Escalated: safety label */}
          {section === "ESCALATED_BY_AI" && (
            <span className="inline-flex items-center gap-1 w-fit px-2 py-0.5 rounded-full bg-cl-danger/10 text-cl-danger text-[0.6875rem] font-semibold uppercase">
              <AlertTriangle className="h-3 w-3" />
              {item.isSafetyEmergency ? "Safety emergency escalated" : "Urgent issue escalated"}
            </span>
          )}

          {/* Bookings: appointment status + action buttons when selected */}
          {section === "BOOKINGS" && (
            <>
              <span
                className={cn(
                  "inline-flex items-center gap-1 w-fit px-2 py-0.5 rounded-full text-[0.6875rem] font-semibold uppercase",
                  item.bookingStatus === "confirmed"
                    ? "bg-cl-success/10 text-cl-success"
                    : "bg-cl-success/10 text-cl-success"
                )}
                aria-label={item.bookingStatus === "confirmed" ? "Confirmed" : "Needs confirmation"}
                role="status"
              >
                {item.bookingStatus === "confirmed" ? (
                  <CheckCircle2 className="h-3 w-3" />
                ) : (
                  <span className="relative flex h-2 w-2 mr-0.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cl-success opacity-60 motion-reduce:animate-none" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-cl-success" />
                  </span>
                )}
                {item.bookingStatus === "confirmed"
                  ? `Confirmed · ${formatAppointmentTime(item.appointmentDateTime)}`
                  : `Needs confirmation · ${formatAppointmentTime(item.appointmentDateTime)}`
                }
              </span>
              {isActive && item.bookingStatus === null && (
                <div className="flex flex-col gap-2 mt-1" onClick={(e) => e.stopPropagation()}>
                  <div className="flex gap-1.5 flex-wrap">
                    <button
                      disabled={!!submittingBookingId}
                      onClick={() => handleBookingAction(item, "confirmed")}
                      className="h-7 px-2.5 rounded-full text-[0.6875rem] uppercase font-semibold flex items-center gap-1 bg-cl-success/20 text-cl-success hover:bg-cl-success/30 disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3 w-3" />
                      Confirm
                    </button>
                    <button
                      disabled={!!submittingBookingId}
                      onClick={() => handleBookingAction(item, "cancelled")}
                      className="h-7 px-2.5 rounded-full text-[0.6875rem] uppercase font-semibold flex items-center gap-1 bg-cl-bg-chip text-cl-text-muted hover:bg-cl-bg-chip-hover disabled:opacity-50"
                    >
                      <X className="h-3 w-3" />
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Follow-up: category-specific reason label */}
          {section === "FOLLOW_UPS" && (() => {
            const context = (item.hvacIssueType || item.problemDescription || "").slice(0, 30).toLowerCase()
            const contextSuffix = context ? ` · re: ${context}` : ""

            if (item.callbackOutcome === "left_voicemail" || item.callbackOutcome === "no_answer") {
              return (
                <span className="inline-flex items-center gap-1 w-fit px-2 py-0.5 rounded-full bg-amber-900/30 text-amber-400 text-[0.6875rem] font-semibold">
                  <RotateCcw className="h-3 w-3" />
                  {item.callbackOutcome === "left_voicemail" ? "Left voicemail" : "No answer"}
                  {item.callbackOutcomeAt && (
                    <span className="text-amber-400/60 font-normal">
                      {" · "}{formatOutcomeAge(item)}
                    </span>
                  )}
                  {" · try again"}
                  {contextSuffix && (
                    <span className="text-amber-400/60 font-normal">{contextSuffix}</span>
                  )}
                </span>
              )
            }
            if (item.primaryIntent === "complaint" || item.primaryIntent === "active_job_issue" || item.primaryIntent === "followup") {
              const intentLabel = item.primaryIntent === "complaint"
                ? "Complaint about prior service"
                : item.primaryIntent === "active_job_issue"
                  ? "Following up on active job"
                  : "Caller following up"
              return (
                <span className="inline-flex items-center gap-1 w-fit px-2 py-0.5 rounded-full bg-blue-900/30 text-blue-400 text-[0.6875rem] font-semibold">
                  <MessageSquare className="h-3 w-3" />
                  {intentLabel}
                  {contextSuffix && (
                    <span className="text-blue-400/60 font-normal">{contextSuffix}</span>
                  )}
                </span>
              )
            }
            const reasonLabel = item.endCallReason === "booking_failed"
              ? "Booking failed · needs reschedule"
              : "AI promised a callback"
            return (
              <span className="inline-flex items-center gap-1 w-fit px-2 py-0.5 rounded-full bg-cl-bg-chip text-cl-text-subtle text-[0.6875rem] font-semibold">
                <Phone className="h-3 w-3" />
                {reasonLabel}
                {contextSuffix && (
                  <span className="text-cl-text-muted font-normal">{contextSuffix}</span>
                )}
              </span>
            )
          })()}

          {/* CALL BACK — NEW_LEADS and FOLLOW_UPS only */}
          {(section === "NEW_LEADS" || section === "FOLLOW_UPS") && callActionable && item.customerPhone && (
            <a
              href={`tel:${item.customerPhone}`}
              aria-label={`Call back ${item.customerName || "customer"}`}
              className={cn(
                "mt-1 h-11 text-[0.6875rem] font-bold rounded-md flex items-center justify-center gap-2 uppercase tracking-widest transition-colors no-underline",
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

          {/* Outcome chips — selected card only, action queue sections */}
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
    const bookingsCount = buckets.BOOKINGS.length

    return (
      <div className="flex-1 flex flex-col overflow-hidden bg-cl-bg-canvas">
        {/* Tab bar */}
        <div role="tablist" className="flex shrink-0 px-4 pt-3 gap-1 border-b border-cl-border">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "timeline"}
            onClick={() => setActiveTab("timeline")}
            className={cn(
              "px-3 pb-2.5 text-xs font-semibold uppercase tracking-wider transition-colors border-b-2 -mb-px",
              activeTab === "timeline"
                ? "text-cl-text-primary border-cl-accent"
                : "text-cl-text-muted border-transparent hover:text-cl-text-primary"
            )}
          >
            Timeline
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "active"}
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
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col gap-1 p-4 pb-24">
          {activeTab === "timeline" ? (
            <>
              {timelineGroups.map((group) => (
                <div key={group.label}>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-cl-text-muted pt-4 pb-2 px-1">
                    {group.label}
                  </h3>
                  <div className="flex flex-col gap-1">
                    {group.calls.map((item) => {
                      const isActive = selected === item.id
                      const section = timelineSectionById.get(item.id) ?? "NEW_LEADS"
                      const createdAt = new Date(item.createdAt)
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => onSelect(item.id)}
                          className={cn(
                            "w-full text-left flex items-stretch rounded-xl overflow-hidden transition-colors",
                            isActive
                              ? "bg-cl-bg-card-active ring-1 ring-cl-accent/30"
                              : "bg-cl-bg-card hover:bg-cl-bg-card-hover"
                          )}
                        >
                          <div className="w-14 shrink-0 flex flex-col items-center justify-center bg-cl-bg-canvas/50">
                            <span className="text-xs font-mono text-cl-text-muted">{format(createdAt, "h:mm")}</span>
                            <span className="text-[10px] font-mono text-cl-text-muted/60 uppercase">
                              {format(createdAt, "a")}
                            </span>
                          </div>
                          <div className="flex-1 p-3 flex flex-col gap-1 min-w-0">
                            <div className="flex justify-between items-start gap-2">
                              <span className="text-sm font-semibold text-cl-text-primary truncate">
                                {item.customerName || (item.customerPhone ? formatPhone(item.customerPhone) : "Unknown")}
                              </span>
                              <span className={cn("text-[10px] font-semibold uppercase tracking-wider shrink-0", sectionColor(section))}>
                                {sectionLabel(section)}
                              </span>
                            </div>
                            <p className="text-cl-text-muted text-xs line-clamp-1 leading-relaxed">
                              {item.problemDescription || "No details"}
                            </p>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
              {timelineCalls.length === 0 && (
                <div className="flex-1 flex items-center justify-center p-8">
                  <p className="text-cl-text-muted text-sm font-medium">No calls yet</p>
                </div>
              )}
            </>
          ) : (
            <>
              {/* Bookings */}
              {bookingsCount > 0 && (
                <>
                  <h3
                    role="heading"
                    aria-level={3}
                    className="font-headline text-[1.75rem] font-bold text-cl-text-primary tracking-[-0.02em] pt-4 pb-2"
                  >
                    Bookings ({bookingsCount})
                  </h3>
                  <div className="-ml-4">
                    <CalendarWithEventSlots
                      calls={buckets.BOOKINGS}
                      selectedCallId={selected}
                      onSelectCall={onSelect}
                      onBookingStatusChange={onBookingStatusChange}
                    />
                  </div>
                </>
              )}

              {/* New Leads */}
              {buckets.NEW_LEADS.length > 0 && (
                <>
                  <h3
                    role="heading"
                    aria-level={3}
                    className={cn(
                      "font-headline text-[1.75rem] font-bold text-cl-text-primary tracking-[-0.02em] pb-2",
                      bookingsCount > 0 ? "mt-8 pt-0" : "pt-4"
                    )}
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
