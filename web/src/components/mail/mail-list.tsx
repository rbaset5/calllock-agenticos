"use client"

import { useState, useCallback, useMemo } from "react"
import { formatDistanceToNow, format, isToday, isTomorrow, isYesterday } from "date-fns"
import {
  AlertTriangle,
  CalendarCheck,
  CheckCircle2,
  ChevronRight,
  CircleCheck,
  Clock,
  Phone,
  PhoneMissed,
  RotateCcw,
  UserCheck,
  Voicemail,
  X,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { formatPhone } from "@/lib/transforms"
import {
  computeCommand,
  getCallbackReason,
  getFollowUpSubtype,
  isActionable,
  isHotFollowUp,
} from "@/lib/triage"
import type { BucketAssignment, FollowUpSubtype } from "@/lib/triage"
import { countHandledReasons } from "@/lib/mail-sections"
import type { BookingStatus, Call, CallbackOutcome, TriageResult } from "@/types/call"

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
  }

  return segs.slice(0, 3)
}

type CardSection = "ESCALATED_BY_AI" | "NEW_LEADS" | "FOLLOW_UPS" | "BOOKINGS" | "OTHER_AI_HANDLED"

function formatRevenueTier(value: Call["revenueTier"]): string | null {
  if (!value) return null
  return value
    .split("_")
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ")
}

function formatContext(item: Call, max = 36): string | null {
  const raw = (item.hvacIssueType || item.problemDescription || "").trim()
  if (!raw) return null
  return raw.length > max ? `${raw.slice(0, max)}...` : raw
}

function formatDeadline(value: string | null): string | null {
  if (!value) return null
  try {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return null
    return format(d, "h:mm a")
  } catch {
    return null
  }
}

interface ReasonChipProps {
  item: Call
  section: CardSection
  assignment?: BucketAssignment
  triage?: TriageResult
}

const chipBase = "gap-1 text-[0.6875rem] font-semibold [&>svg]:size-3"

const ISSUE_TYPE_VARIANT: Record<string, React.ComponentProps<typeof Badge>["variant"]> = {
  "No Cool": "cl-escalation",
  "No Heat": "cl-escalation",
  "Not Running": "cl-escalation",
  Odor: "cl-amber",
  Leaking: "cl-amber",
  Cooling: "cl-opportunity",
  Heating: "cl-opportunity",
  Maintenance: "cl-opportunity",
  Thermostat: "cl-opportunity",
  "Noisy System": "cl-opportunity",
}

function ChipDetail({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("font-normal opacity-70", className)}>{" \u00b7 "}{children}</span>
}

function ReasonChip({ item, section, assignment, triage }: ReasonChipProps) {
  // ── NEW_LEADS ──────────────────────────────────────────────────────
  if (section === "NEW_LEADS") {
    if (item.extractionStatus === "pending") {
      return (
        <Badge variant="cl-muted" className={cn(chipBase, "animate-pulse")} aria-label="Processing call details">
          <Clock /> Processing...
        </Badge>
      )
    }

    const command = computeCommand(item)
    if (command === "Call now" || command === "Can wait") return null

    const callbackReason = getCallbackReason(item)
    if (callbackReason === "AI promised callback") {
      return (
        <Badge variant="cl-commitment" className={chipBase}>
          <Phone /> AI promised callback
        </Badge>
      )
    }
    if (callbackReason === "Booking failed") {
      return (
        <Badge variant="cl-amber" className={chipBase}>
          <RotateCcw /> Booking failed
          <ChipDetail>needs reschedule</ChipDetail>
        </Badge>
      )
    }
    if (callbackReason === "Urgent, needs details") {
      return (
        <Badge variant="cl-escalation" className={chipBase}>
          <AlertTriangle /> Urgent
          <ChipDetail>needs details</ChipDetail>
        </Badge>
      )
    }
    if (item.urgency === "Estimate") {
      return (
        <Badge variant="cl-opportunity" className={chipBase}>
          <CircleCheck /> Estimate
          {formatRevenueTier(item.revenueTier) && (
            <ChipDetail>{formatRevenueTier(item.revenueTier)}</ChipDetail>
          )}
        </Badge>
      )
    }
    if (item.hvacIssueType) {
      const issueVariant = ISSUE_TYPE_VARIANT[item.hvacIssueType] ?? "cl-neutral"
      return (
        <Badge variant={issueVariant} className={chipBase}>
          <Phone /> {item.hvacIssueType}
        </Badge>
      )
    }
    if (item.problemDescription) {
      return (
        <Badge variant="cl-neutral" className={chipBase}>
          <Phone /> Service request
        </Badge>
      )
    }
    return null
  }

  // ── FOLLOW_UPS ─────────────────────────────────────────────────────
  if (section === "FOLLOW_UPS") {
    const subtype: FollowUpSubtype = getFollowUpSubtype(item)

    if (subtype === "booking_failed") {
      return (
        <Badge variant="cl-amber" className={chipBase}>
          <AlertTriangle /> Booking failed
          <ChipDetail>needs reschedule</ChipDetail>
        </Badge>
      )
    }

    if (subtype === "complaint") {
      return (
        <Badge variant="cl-risk" className={chipBase}>
          <AlertTriangle /> Complaint
          {formatContext(item) && <ChipDetail>{formatContext(item)}</ChipDetail>}
        </Badge>
      )
    }

    if (subtype === "active_job_issue") {
      return (
        <Badge variant="cl-job-issue" className={chipBase}>
          <AlertTriangle /> Active job issue
          {formatContext(item) && <ChipDetail>{formatContext(item)}</ChipDetail>}
        </Badge>
      )
    }

    if (subtype === "promised_callback") {
      const deadline = formatDeadline(item.callbackWindowEnd)
      if (item.callbackWindowEnd && deadline && triage && !triage.callbackWindowValid) {
        return (
          <Badge variant="cl-critical" className={chipBase}>
            <AlertTriangle /> Window expired
          </Badge>
        )
      }
      return (
        <Badge variant="cl-commitment" className={chipBase}>
          <Phone /> Callback promised
          {deadline && <ChipDetail>by {deadline}</ChipDetail>}
        </Badge>
      )
    }

    if (subtype === "retry_voicemail" || subtype === "retry_no_answer") {
      return (
        <Badge variant="cl-retry" className={chipBase}>
          <RotateCcw /> {subtype === "retry_voicemail" ? "Left voicemail" : "No answer"}
          {formatOutcomeAge(item) && <ChipDetail>{formatOutcomeAge(item)}</ChipDetail>}
        </Badge>
      )
    }

    return (
      <Badge variant="cl-neutral" className={chipBase}>
        <Phone /> Follow-up
      </Badge>
    )
  }

  // ── ESCALATED_BY_AI ────────────────────────────────────────────────
  if (section === "ESCALATED_BY_AI") {
    if (item.isSafetyEmergency) {
      return (
        <Badge variant="cl-critical" className={chipBase}>
          <AlertTriangle /> Safety emergency
          <ChipDetail>AI gave safety instructions</ChipDetail>
        </Badge>
      )
    }
    if (item.isUrgentEscalation) {
      return (
        <Badge variant="cl-escalation" className={chipBase}>
          <AlertTriangle /> Urgent escalation
          {formatContext(item) && <ChipDetail>{formatContext(item)}</ChipDetail>}
        </Badge>
      )
    }
  }

  // ── OTHER_AI_HANDLED ───────────────────────────────────────────────
  if (section === "OTHER_AI_HANDLED" && assignment?.handledReason) {
    const label =
      assignment.handledReason === "booked"
        ? "Booked by AI"
        : assignment.handledReason === "resolved"
          ? "Resolved"
          : assignment.handledReason === "non_customer" ||
              assignment.handledReason === "wrong_number"
            ? "Filtered"
            : "Other"
    return (
      <Badge variant="cl-resolved" className={chipBase}>
        <CircleCheck /> {label}
      </Badge>
    )
  }

  return null
}

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
  const [bookingsPage, setBookingsPage] = useState(0)
  const BOOKINGS_PER_PAGE = 5

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
    const assignment = bucketMap?.get(item.id)
    const callActionable = isActionable(item)
    const command = computeCommand(item)

    return (
      <div
        key={item.id}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(item.id) } }}
        className={cn(
          "w-full flex items-stretch overflow-hidden rounded-lg cursor-pointer transition-all duration-200",
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

        {/* Bookings: left panel shows booking lifecycle state */}
        {section === "BOOKINGS" && (
          <div
            className={cn(
              "w-[56px] shrink-0 flex flex-col items-center justify-center text-[10px] font-black tracking-tighter uppercase leading-none px-1 text-center",
              item.bookingStatus === "confirmed"
                ? "bg-cl-accent/10 text-cl-accent"
                : "bg-cl-success/10 text-cl-success"
            )}
            aria-label={item.bookingStatus === "confirmed" ? "Scheduled booking" : "AI appointment, needs confirmation"}
          >
            {item.bookingStatus === "confirmed" ? (
              <>
                <CheckCircle2 className="h-4 w-4 mb-1" />
                <span className="block">SCHED</span>
                <span className="block">ULED</span>
              </>
            ) : (
              <>
                <CalendarCheck className="h-4 w-4 mb-1" />
                <span className="block">AI</span>
                <span className="block">APPT</span>
              </>
            )}
          </div>
        )}

        {/* Triage priority panel — keep only Call Now for new leads */}
        {section === "NEW_LEADS" && callActionable && command === "Call now" && (
          <div
            className="w-[56px] shrink-0 flex flex-col items-center justify-center text-[10px] font-black tracking-tighter uppercase leading-none px-1 text-center bg-cl-danger/80 text-[#5e1b1a]"
            suppressHydrationWarning
            aria-label={
              triage
                ? `Priority: ${triage.command}. ${triage.evidence}. ${triage.staleMinutes} minutes waiting.`
                : "Priority: Call now."
            }
          >
            <Phone className="h-4 w-4 mb-1" />
            {command.split(" ").map((word, i) => (
              <span key={i} className="block">{word}</span>
            ))}
            {triage?.isStale && (
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
              <span className="text-sm truncate text-cl-text-primary font-semibold">
                {item.customerName || (item.customerPhone ? formatPhone(item.customerPhone) : "Unknown")}
              </span>
            </div>
            {section === "BOOKINGS" ? (
              <span className="text-xs font-mono text-cl-text-primary shrink-0 ml-2">
                {item.appointmentDateTime ? formatAppointmentTime(item.appointmentDateTime) : "TBD"}
              </span>
            ) : (
              <span className="text-[0.6875rem] text-cl-text-muted shrink-0 ml-2">
                {formatDistanceToNow(new Date(item.createdAt), { addSuffix: false })} ago
              </span>
            )}
          </div>

          {/* Line 3: Snippet */}
          <p className="text-cl-text-muted text-sm line-clamp-2 leading-relaxed">
            {item.problemDescription || item.hvacIssueType || "Missed call"}
          </p>

          <ReasonChip item={item} section={section} assignment={assignment} triage={triage} />

          {/* Line 4: Intel line — hot follow-ups only */}
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

          {/* Bookings: inline confirm/cancel when selected + unconfirmed */}
          {section === "BOOKINGS" && isActive && item.bookingStatus === null && (
            <div className="flex gap-1.5 flex-wrap mt-1" onClick={(e) => e.stopPropagation()}>
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
          )}


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
    const handledCounts = countHandledReasons(buckets.OTHER_AI_HANDLED, bucketMap)

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
              {bookingsCount > 0 && (() => {
                const totalPages = Math.ceil(bookingsCount / BOOKINGS_PER_PAGE)
                const pageStart = bookingsPage * BOOKINGS_PER_PAGE
                const visibleBookings = buckets.BOOKINGS.slice(pageStart, pageStart + BOOKINGS_PER_PAGE)

                return (
                  <>
                    <h3
                      role="heading"
                      aria-level={3}
                      className="font-headline text-[1.75rem] font-bold text-cl-text-primary tracking-[-0.02em] pt-4 pb-2"
                    >
                      Bookings ({bookingsCount})
                    </h3>
                    <div className="flex flex-col gap-1">
                      {visibleBookings.map((item) => renderCard(item, "BOOKINGS"))}
                    </div>
                    {totalPages > 1 && (
                      <div className="flex items-center justify-between mt-2 px-1">
                        <button
                          type="button"
                          disabled={bookingsPage === 0}
                          onClick={() => setBookingsPage((p) => Math.max(0, p - 1))}
                          className="text-xs font-semibold text-cl-text-muted hover:text-cl-text-primary disabled:opacity-30 disabled:cursor-default"
                        >
                          ← Prev
                        </button>
                        <span className="text-xs text-cl-text-muted">
                          {bookingsPage + 1} / {totalPages}
                        </span>
                        <button
                          type="button"
                          disabled={bookingsPage >= totalPages - 1}
                          onClick={() => setBookingsPage((p) => Math.min(totalPages - 1, p + 1))}
                          className="text-xs font-semibold text-cl-text-muted hover:text-cl-text-primary disabled:opacity-30 disabled:cursor-default"
                        >
                          Next →
                        </button>
                      </div>
                    )}
                  </>
                )
              })()}

              {/* New Leads */}
              {buckets.NEW_LEADS.length > 0 && (
                <>
                  <h3
                    role="heading"
                    aria-level={3}
                    className={cn(
                      "font-headline text-[1.75rem] font-bold text-cl-text-primary tracking-[-0.02em] pb-2",
                      bookingsCount > 0 ? "mt-8" : "pt-4"
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
                      AI Handled ({otherCount}){" "}
                      <span className="normal-case">
                        {"\u00b7"} {handledCounts.booked} booked {"\u00b7"} {handledCounts.filtered} filtered {"\u00b7"}{" "}
                        {handledCounts.resolved} resolved {"\u00b7"} {handledCounts.other} other
                      </span>
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
