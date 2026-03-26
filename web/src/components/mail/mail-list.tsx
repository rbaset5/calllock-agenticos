"use client"

import { useState, useCallback } from "react"
import { formatDistanceToNow, format, isToday, isTomorrow } from "date-fns"
import {
  AlertCircle,
  CalendarCheck,
  ChevronRight,
  CircleCheck,
  Clock,
  Copy,
  Minus,
  MoreHorizontal,
  Phone,
  PhoneMissed,
  ScrollText,
  UserCheck,
  Voicemail,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { formatPhone } from "@/lib/transforms"
import { getAssistTemplate, isUnresolved } from "@/lib/triage"
import { useIsMobile } from "@/hooks/use-mobile"
import {
  DropDrawer,
  DropDrawerContent,
  DropDrawerGroup,
  DropDrawerItem,
  DropDrawerLabel,
  DropDrawerSub,
  DropDrawerSubContent,
  DropDrawerSubTrigger,
  DropDrawerTrigger,
} from "@/components/ui/dropdrawer"
import type { Call, CallbackOutcome, TriageResult } from "@/types/call"

interface MailListProps {
  items: Call[]
  selected: string | null
  onSelect: (id: string) => void
  onOutcomeChange?: (callId: string, outcome: CallbackOutcome | null) => void
  view?: "activity" | "scheduled"
  triageMap?: Map<string, TriageResult>
  pulsingId?: string | null
  onCallBackTap?: (callId: string) => void
  onPulseClear?: () => void
}

const COMMAND_STYLES: Record<string, { text: string; bg: string; border: string }> = {
  "Call now": {
    text: "text-[#5e1b1a]",
    bg: "bg-[#fd9791]/80",
    border: "border-r border-[#484848]/10",
  },
  "Next up": {
    text: "text-[#d2d0cf]",
    bg: "bg-[#474746]",
    border: "border-r border-[#484848]/10",
  },
  "Today": {
    text: "text-[#acabab]",
    bg: "bg-[#474848]",
    border: "border-r border-[#484848]/10",
  },
  "Can wait": {
    text: "text-[#757575]",
    bg: "bg-[#252626]",
    border: "border-r border-[#484848]/10",
  },
}

const COMMAND_ICONS: Record<string, typeof Phone> = {
  "Call now": Phone,
  "Next up": AlertCircle,
  "Today": Clock,
  "Can wait": Minus,
}

function getUrgencyChip(call: Call): { label: string; bg: string; text: string } {
  const isEmergency = call.isSafetyEmergency || call.urgency === "LifeSafety"
  if (isEmergency) {
    return { label: call.hvacIssueType || "Emergency", bg: "bg-[#7f2927]", text: "text-[#ff9993]" }
  }
  return { label: call.hvacIssueType || call.urgency, bg: "bg-[#3b3b3b]", text: "text-[#c1bfbe]" }
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
  view = "activity",
  triageMap,
  pulsingId,
  onCallBackTap,
  onPulseClear,
}: MailListProps) {
  const isMobile = useIsMobile()
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [submittingId, setSubmittingId] = useState<string | null>(null)
  const [openDrawerId, setOpenDrawerId] = useState<string | null>(null)
  const [flashingState, setFlashingState] = useState<{
    cardId: string
    outcome: CallbackOutcome
  } | null>(null)

  const handleDrawerOpenChange = useCallback(
    (cardId: string, open: boolean) => {
      // Prevent drawer close during 600ms green flash
      if (!open && flashingState?.cardId === cardId) return
      setOpenDrawerId(open ? cardId : null)
      if (open) onPulseClear?.()
    },
    [flashingState, onPulseClear]
  )

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
        toast.error("Couldn't save outcome. Try again.")
      } finally {
        setSubmittingId(null)
        setTimeout(() => {
          setFlashingState(null)
          setOpenDrawerId(null)
        }, 600)
      }
    },
    [submittingId, onOutcomeChange]
  )

  const copyPhone = useCallback((phone: string, callId: string) => {
    navigator.clipboard.writeText(phone).then(
      () => {
        setCopiedId(callId)
        setTimeout(() => setCopiedId(null), 2000)
        toast.success("Copied")
      },
      () => toast.error("Copy failed")
    )
  }, [])

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
                    isEmergency ? "bg-[#7f2927] text-[#ff9993]" : "bg-[#3b3b3b] text-[#c1bfbe]"
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
    <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col gap-4 p-4 pb-24">
      {items.map((item) => {
        const isActive = selected === item.id
        const isEmergency = item.isSafetyEmergency || item.urgency === "LifeSafety"
        const urgencyChip = getUrgencyChip(item)
        const statusChip = getStatusChip(item)
        const snippet = item.problemDescription || item.hvacIssueType || "Missed call"
        const triage = triageMap?.get(item.id)
        const callUnresolved = isUnresolved(item)
        const style = COMMAND_STYLES[triage?.command ?? "Can wait"] ?? COMMAND_STYLES["Can wait"]
        const Icon = COMMAND_ICONS[triage?.command ?? "Can wait"] ?? Minus
        const COMPANY_NAME = process.env.NEXT_PUBLIC_COMPANY_NAME ?? "our company"
        const assistTemplate = triage ? getAssistTemplate(triage.reason, COMPANY_NAME) : null
        const isPulsing = pulsingId === item.id

        const handleCardKeyDown = (e: React.KeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            onSelect(item.id)
          }
        }

        return (
          <div
            key={item.id}
            role="button"
            tabIndex={0}
            onKeyDown={handleCardKeyDown}
            className={cn(
              "flex items-stretch overflow-hidden rounded-lg shadow-lg border border-[#484848]/5 cursor-pointer transition-all duration-200 shrink-0",
              isActive ? "bg-[#1f2020] ring-1 ring-[#484848]/30" : "bg-[#131313] hover:bg-[#191a1a]"
            )}
            onClick={() => onSelect(item.id)}
          >
            {/* Triage priority panel */}
            {callUnresolved && triage && (
              <div
                className={cn(
                  "w-[56px] shrink-0 flex flex-col items-center justify-center text-[10px] font-black tracking-tighter uppercase leading-none px-1 text-center",
                  style.bg, style.text, style.border
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
            <div className="flex-1 p-4 flex flex-col gap-3 min-w-0">
              {/* Row 1: Name + phone | Issue type tag */}
              <div className="flex justify-between items-start gap-2">
                <div className="flex flex-col min-w-0">
                  <h4 className="text-[#e7e5e4] text-base font-bold leading-none truncate">
                    {item.customerName || (item.customerPhone ? formatPhone(item.customerPhone) : "Unknown")}
                  </h4>
                  {item.customerName && item.customerPhone && (
                    <p className="text-[#acabaa] text-xs mt-1 font-medium">
                      {formatPhone(item.customerPhone)}
                    </p>
                  )}
                </div>
                <span className={cn(
                  "px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-widest shrink-0",
                  isEmergency
                    ? "bg-[#7f2927]/20 text-[#ee7d77] border border-[#ee7d77]/20"
                    : "bg-[#252626] text-[#acabab] border border-[#474848]/20"
                )}>
                  {urgencyChip.label}
                </span>
              </div>

              {/* Row 2: Quoted transcript snippet */}
              <div className={cn(
                "p-3 rounded border-l",
                isActive ? "bg-[#2a2b2b]" : "bg-[#1f2020]",
                isEmergency ? "border-l-[#ff9993]/40" : "border-l-[#c8c6c5]/40"
              )}>
                <p className="text-[#e7e5e4] text-xs italic leading-relaxed line-clamp-2">
                  &ldquo;{snippet}&rdquo;
                </p>
              </div>

              {/* Row 3: CALL BACK + quick actions (unresolved only) */}
              {callUnresolved && (
                <div className="flex gap-2">
                  {/* CALL BACK: tel: on mobile, navigate on desktop */}
                  {item.customerPhone ? (
                    isMobile ? (
                      <a
                        href={`tel:${item.customerPhone}`}
                        aria-label={`Call back ${item.customerName || "customer"} at ${formatPhone(item.customerPhone)}`}
                        className={cn(
                          "flex-1 min-h-[44px] text-xs font-bold rounded-full flex items-center justify-center gap-2 uppercase tracking-widest transition-colors no-underline",
                          triage?.command === "Call now"
                            ? "bg-[#e4e2e1] text-[#3f3f3f]"
                            : "bg-[#252626] text-[#e7e5e4] border border-[#484848]/10"
                        )}
                        onClick={(e) => {
                          e.stopPropagation()
                          onCallBackTap?.(item.id)
                        }}
                      >
                        <Phone className="h-3.5 w-3.5" />
                        Call Back
                      </a>
                    ) : (
                      <button
                        className={cn(
                          "flex-1 min-h-[44px] text-xs font-bold rounded-full flex items-center justify-center gap-2 uppercase tracking-widest transition-colors",
                          triage?.command === "Call now"
                            ? "bg-[#e4e2e1] text-[#3f3f3f]"
                            : "bg-[#252626] text-[#e7e5e4] border border-[#484848]/10"
                        )}
                        onClick={(e) => { e.stopPropagation(); onSelect(item.id) }}
                      >
                        <Phone className="h-3.5 w-3.5" />
                        Call Back
                      </button>
                    )
                  ) : (
                    <button
                      className="flex-1 min-h-[44px] text-xs font-bold rounded-full flex items-center justify-center gap-2 uppercase tracking-widest bg-[#252626] text-[#e7e5e4] border border-[#484848]/10 transition-colors"
                      onClick={(e) => { e.stopPropagation(); onSelect(item.id) }}
                    >
                      <Phone className="h-3.5 w-3.5" />
                      Call Back
                    </button>
                  )}

                  {/* DropDrawer — controlled mode for 600ms flash */}
                  <DropDrawer
                    open={openDrawerId === item.id}
                    onOpenChange={(o) => handleDrawerOpenChange(item.id, o)}
                  >
                    <DropDrawerTrigger asChild>
                      <button
                        className={cn(
                          "w-11 h-11 bg-[#252626] text-[#acabaa] rounded-full flex items-center justify-center border border-[#484848]/10 shrink-0 transition-all",
                          isPulsing && "animate-pulse ring-2 ring-[#10b981]/40"
                        )}
                        onClick={(e) => e.stopPropagation()}
                        aria-label="Quick actions"
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </button>
                    </DropDrawerTrigger>

                    <DropDrawerContent>
                      {/* Context header */}
                      <DropDrawerLabel>
                        <span className="text-[#e7e5e4] font-semibold">
                          {item.customerName || "Unknown"}
                        </span>
                        {item.customerPhone && (
                          <span className="text-[#acabaa] font-normal"> · {formatPhone(item.customerPhone)}</span>
                        )}
                        {triage && (
                          <span className="text-[#acabaa] font-normal"> · {triage.command}</span>
                        )}
                      </DropDrawerLabel>

                      {/* Group 1: LOG OUTCOME (unresolved only) */}
                      {callUnresolved && (
                        <>
                        <DropDrawerLabel>LOG OUTCOME</DropDrawerLabel>
                        <DropDrawerGroup>
                          {OUTCOME_CONFIG.map(({ value, label, Icon: OutcomeIcon }) => {
                            const isSelected = item.callbackOutcome === value
                            const isFlashing =
                              flashingState?.cardId === item.id &&
                              flashingState.outcome === value
                            return (
                              <DropDrawerItem
                                key={value}
                                disabled={!!submittingId}
                                aria-pressed={isSelected}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleOutcomeClick(item, value)
                                }}
                                className={cn(
                                  isFlashing && "!bg-[#10b981] !text-white",
                                  isSelected && !isFlashing && "bg-[#10b981]/20 text-[#10b981]"
                                )}
                              >
                                <OutcomeIcon className="h-4 w-4 text-[#acabaa] mr-2 shrink-0" />
                                <span className="text-[#e7e5e4]">{label}</span>
                              </DropDrawerItem>
                            )
                          })}
                        </DropDrawerGroup>
                        </>
                      )}

                      {/* Group 2: PREPARE */}
                      {(item.customerPhone || assistTemplate) && (
                        <>
                        <DropDrawerLabel>PREPARE</DropDrawerLabel>
                        <DropDrawerGroup>
                          {item.customerPhone && (
                            <DropDrawerItem
                              onClick={(e) => {
                                e.stopPropagation()
                                copyPhone(item.customerPhone!, item.id)
                              }}
                            >
                              <Copy className="h-4 w-4 text-[#acabaa] mr-2 shrink-0" />
                              <span className="text-[#e7e5e4]">
                                {copiedId === item.id ? "Copied!" : "Copy Phone Number"}
                              </span>
                            </DropDrawerItem>
                          )}
                          {assistTemplate && (
                            <DropDrawerSub>
                              <DropDrawerSubTrigger>
                                <ScrollText className="h-4 w-4 text-[#acabaa] mr-2 shrink-0" />
                                <span className="text-[#e7e5e4]">Callback Opener</span>
                              </DropDrawerSubTrigger>
                              <DropDrawerSubContent>
                                <div className="px-4 py-4">
                                  <p className="text-sm text-[#e7e5e4] leading-relaxed italic">
                                    &ldquo;{assistTemplate}&rdquo;
                                  </p>
                                  {triage && (
                                    <p className="text-[10px] text-[#acabaa] mt-2 uppercase tracking-widest">
                                      {triage.reason.replace(/_/g, " ")}
                                    </p>
                                  )}
                                </div>
                              </DropDrawerSubContent>
                            </DropDrawerSub>
                          )}
                        </DropDrawerGroup>
                        </>
                      )}

                      {/* View Full Details — mobile only */}
                      {isMobile && (
                        <DropDrawerItem
                          onClick={(e) => {
                            e.stopPropagation()
                            setOpenDrawerId(null)
                            onSelect(item.id)
                          }}
                        >
                          <ChevronRight className="h-4 w-4 text-[#acabaa] mr-2 shrink-0" />
                          <span className="text-[#e7e5e4]">View Full Details</span>
                        </DropDrawerItem>
                      )}
                    </DropDrawerContent>
                  </DropDrawer>
                </div>
              )}

              {/* Resolved calls: status chip + time ago */}
              {!callUnresolved && (
                <div className="flex justify-between items-center">
                  {statusChip && (
                    <span className={cn(
                      "text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-tighter",
                      statusChip.bg, statusChip.text
                    )}>
                      {statusChip.label}
                    </span>
                  )}
                  <span className="text-[10px] text-[#acabaa] ml-auto">
                    {formatDistanceToNow(new Date(item.createdAt), { addSuffix: false })} ago
                  </span>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
