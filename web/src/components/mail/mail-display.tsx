"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { format, isToday, isTomorrow } from "date-fns"
import { Phone } from "lucide-react"
import { parseTranscript, formatPhone } from "@/lib/transforms"
import type {
  Call,
  TranscriptEntry,
  CallbackOutcome,
  CallbackTouch,
  TriageResult,
} from "@/types/call"
import { cn } from "@/lib/utils"
import { getAssistTemplate } from "@/lib/triage"
import type { BucketAssignment } from "@/lib/triage"
import { useOutcomeSubmit } from "@/hooks/use-outcome-submit"
import { buildAISummary, getHandledSummary } from "./mail-copy"

interface MailDisplayProps {
  call: Call | null
  triageMap?: Map<string, TriageResult>
  onOutcomeChange?: (callId: string, outcome: CallbackOutcome | null) => void
  bucketMap?: Map<string, BucketAssignment>
}


function formatTouchTime(value: string): string {
  try {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return value
    if (isToday(d)) return `Today · ${format(d, "h:mm a")}`
    if (isTomorrow(d)) return `Tomorrow · ${format(d, "h:mm a")}`
    return format(d, "MMM d · h:mm a")
  } catch {
    return value
  }
}

export function MailDisplay({ call, triageMap, onOutcomeChange, bucketMap }: MailDisplayProps) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [loadingTranscript, setLoadingTranscript] = useState(false)
  const [touches, setTouches] = useState<CallbackTouch[]>([])
  const [loadingTouches, setLoadingTouches] = useState(false)
  const [activeTab, setActiveTab] = useState<"summary" | "transcript">("summary")
  const touchCacheRef = useRef<Map<string, CallbackTouch[]>>(new Map())

  const optimisticUpdate = useCallback(
    (callId: string, outcome: CallbackOutcome | null) => onOutcomeChange?.(callId, outcome),
    [onOutcomeChange]
  )
  const { submitOutcome, submitting: submittingOutcome } = useOutcomeSubmit(optimisticUpdate)

  const handleOutcome = async (outcome: CallbackOutcome) => {
    if (!call) return
    const ok = await submitOutcome(call.id, outcome, call.callbackOutcome)
    if (!ok) return
    const touch: CallbackTouch = {
      id: `optimistic-${Date.now()}`,
      callId: call.id,
      outcome,
      createdAt: new Date().toISOString(),
    }
    setTouches((prev) => {
      const next = [touch, ...prev]
      touchCacheRef.current.set(call.id, next)
      return next
    })
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

  useEffect(() => {
    if (!call) {
      setTouches([])
      return
    }

    const cached = touchCacheRef.current.get(call.id)
    if (cached) {
      setTouches(cached)
      return
    }

    let cancelled = false
    setLoadingTouches(true)

    const fetchTouches = async () => {
      try {
        const response = await fetch(`/api/calls/${call.id}/touches`, { cache: "no-store" })
        if (!response.ok) throw new Error("failed")
        const data = await response.json()
        const nextTouches = Array.isArray(data?.touches)
          ? (data.touches as CallbackTouch[])
          : []
        if (cancelled) return
        touchCacheRef.current.set(call.id, nextTouches)
        setTouches(nextTouches)
      } catch {
        if (!cancelled) setTouches([])
      } finally {
        if (!cancelled) setLoadingTouches(false)
      }
    }

    fetchTouches()
    return () => { cancelled = true }
  }, [call])

  if (!call) {
    return (
      <section className="flex-1 bg-cl-bg-subtle flex items-center justify-center">
        <p className="text-cl-text-muted text-sm">Select a call to view details</p>
      </section>
    )
  }

  const isEmergency = call.isSafetyEmergency || call.urgency === "LifeSafety"
  const isUrgent = call.urgency === "Urgent"

  const assignment = bucketMap?.get(call.id)
  const callIsActionable = assignment?.bucket === "ACTION_QUEUE"
  const isFollowUp = assignment?.subGroup === "FOLLOW_UP"
  const isAiHandled = assignment?.bucket === "AI_HANDLED"

  const triage = triageMap?.get(call.id)
  const callbackWindowEnd = triage && callIsActionable && triage.callbackWindowValid && triage.callbackWindowEnd
    ? new Date(triage.callbackWindowEnd)
    : null

  return (
    <section className="flex-1 bg-cl-bg-subtle flex flex-col overflow-hidden">
      {/* Header */}
      <header className="p-8 pb-4 flex-shrink-0">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-headline font-extrabold tracking-tighter text-cl-text-primary">
            {call.customerName || (call.customerPhone ? formatPhone(call.customerPhone) : "Unknown Caller")}
          </h1>
          {isEmergency && (
            <span className="bg-cl-danger-soft text-[#490106] text-[10px] font-bold px-2 py-1 rounded uppercase tracking-tight">
              Emergency
            </span>
          )}
          {!isEmergency && isUrgent && (
            <span className="bg-cl-bg-chip text-cl-text-subtle text-[10px] font-bold px-2 py-1 rounded uppercase tracking-tight">
              Urgent
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {call.customerPhone && (
            <a href={`tel:${call.customerPhone}`} className="text-cl-text-muted text-sm hover:text-cl-text-primary transition-colors">
              {formatPhone(call.customerPhone)}
            </a>
          )}
          {call.serviceAddress && (
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(call.serviceAddress)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-cl-text-muted text-sm hover:text-cl-text-primary transition-colors"
            >
              <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>{call.serviceAddress}</span>
            </a>
          )}
          {callbackWindowEnd && (
            <span className="text-[0.6875rem] text-cl-text-muted uppercase">
              {triage?.callbackWindowStart && (
                <>Available {format(new Date(triage.callbackWindowStart), "h:mm a")} – </>
              )}
              {triage?.callbackWindowStart ? format(callbackWindowEnd, "h:mm a") : `Available until ${format(callbackWindowEnd, "h:mm a")}`}
            </span>
          )}
          {call.callRecordingUrl && (
            <a
              href={call.callRecordingUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[0.6875rem] text-cl-text-muted uppercase hover:text-cl-text-primary transition-colors flex items-center gap-1"
            >
              <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Listen
            </a>
          )}
        </div>
        <p className="text-cl-text-muted text-xs mt-1">
          {format(new Date(call.createdAt), "PPpp")}
        </p>
      </header>

      {/* Action Bar */}
      <div className="px-8 pb-4 flex-shrink-0 space-y-3">
        {/* AI Action summary for handled calls */}
        {isAiHandled && assignment && (
          <div className="bg-cl-bg-panel p-4 rounded-md">
            <p className="text-sm text-cl-text-muted">
              {assignment.escalationMarker && <span className="text-cl-danger">⚠ </span>}
              {getHandledSummary(call, assignment)}
              {assignment.handledReason === "booked" && call.appointmentDateTime && (
                <span className="block mt-1 text-cl-text-primary font-medium">
                  {(() => {
                    try {
                      const d = new Date(call.appointmentDateTime)
                      if (isToday(d)) return `Today @ ${format(d, "h:mm a")}`
                      if (isTomorrow(d)) return `Tomorrow @ ${format(d, "h:mm a")}`
                      return format(d, "MMM d @ h:mm a")
                    } catch { return call.appointmentDateTime }
                  })()}
                </span>
              )}
            </p>
          </div>
        )}

        {/* Follow-up touch timeline */}
        {(isFollowUp || touches.length > 0) && (
          <div className="bg-cl-bg-card p-4 rounded-md space-y-2">
            <h4 className="font-headline font-bold text-cl-text-muted text-xs uppercase tracking-widest">
              Touch History
            </h4>
            {loadingTouches ? (
              <p className="text-xs text-cl-text-muted">Loading touch history…</p>
            ) : touches.length === 0 ? (
              <p className="text-xs text-cl-text-muted">No touch history yet.</p>
            ) : (
              <ol className="space-y-1.5">
                {touches.map((touch, idx) => (
                  <li key={`${touch.id}-${idx}`} className="flex items-center justify-between gap-3">
                    <span className="text-[0.6875rem] uppercase font-semibold text-cl-text-subtle">
                      {touch.outcome.replace(/_/g, " ")}
                    </span>
                    <span className="text-[0.6875rem] text-cl-text-muted">
                      {formatTouchTime(touch.createdAt)}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}

        {/* CALL BACK button — only for actionable calls */}
        {callIsActionable && call.customerPhone && (
          <a
            href={`tel:${call.customerPhone}`}
            className={cn(
              "flex items-center justify-center gap-2 w-full h-12 font-bold rounded-lg transition-all active:scale-[0.98]",
              isFollowUp
                ? "bg-cl-bg-chip text-cl-text-subtle hover:bg-cl-bg-chip-hover"
                : "bg-gradient-to-r from-cl-accent to-[#b8b9b9] text-[#3f4041] hover:brightness-110"
            )}
            aria-label={`Call back ${call.customerName}`}
          >
            <Phone className="h-5 w-5" />
            <span>Call Back</span>
          </a>
        )}
        {call && callIsActionable && (
          <div>
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
                    "px-4 py-2 rounded-full text-[0.6875rem] uppercase font-semibold transition-all duration-200",
                    call.callbackOutcome === value
                      ? "bg-cl-success text-white"
                      : "bg-cl-bg-chip text-cl-text-subtle hover:bg-cl-bg-chip-hover hover:text-cl-text-primary",
                    submittingOutcome && "opacity-50 cursor-not-allowed"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            {call.callbackOutcome && (
              <p className="text-xs text-cl-text-muted mt-2">
                Current: <span className="text-cl-text-primary font-medium">{call.callbackOutcome.replace(/_/g, " ")}</span>
                {call.callbackOutcomeAt && (
                  <> at {format(new Date(call.callbackOutcomeAt), "h:mm a")}</>
                )}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Tab toggle */}
      <div className="px-8 pb-0 flex gap-6 border-b border-cl-border/10 flex-shrink-0">
        <button
          onClick={() => setActiveTab("summary")}
          className={cn(
            "text-sm font-semibold pb-3 border-b-2 transition-colors -mb-px",
            activeTab === "summary"
              ? "text-cl-text-primary border-cl-accent"
              : "text-cl-text-muted border-transparent hover:text-cl-text-primary"
          )}
        >
          Summary
        </button>
        <button
          onClick={() => setActiveTab("transcript")}
          className={cn(
            "text-sm font-semibold pb-3 border-b-2 transition-colors -mb-px",
            activeTab === "transcript"
              ? "text-cl-text-primary border-cl-accent"
              : "text-cl-text-muted border-transparent hover:text-cl-text-primary"
          )}
        >
          Transcript
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto no-scrollbar p-8 pt-6">
        {activeTab === "summary" ? (
          <div className="space-y-6 max-w-3xl">
            {/* Callback Opener (above AI Summary) */}
            {call && callIsActionable && (() => {
              const t = triageMap?.get(call.id)
              if (!t) return null
              const COMPANY_NAME = process.env.NEXT_PUBLIC_COMPANY_NAME ?? "our company"
              const template = getAssistTemplate(t.reason, COMPANY_NAME)
              return (
                <div className="bg-cl-bg-card p-4 rounded-md">
                  <h4 className="font-headline font-bold text-cl-text-muted text-xs uppercase tracking-widest mb-2">
                    Callback Opener
                  </h4>
                  <p className="text-sm text-cl-text-primary leading-relaxed italic">
                    &ldquo;{template}&rdquo;
                  </p>
                  <p className="text-[10px] text-cl-text-muted mt-3 uppercase tracking-widest">
                    {t.reason.replace(/_/g, " ")}
                  </p>
                </div>
              )
            })()}

            {/* AI Summary */}
            <div>
              <h3 className="font-headline font-bold text-cl-text-muted text-xs uppercase tracking-widest mb-2">
                AI Receptionist Summary
              </h3>
              <p className="text-cl-text-muted leading-relaxed italic text-sm">
                &ldquo;{buildAISummary(call)}&rdquo;
              </p>
            </div>

            {/* Equipment Details */}
            {(call.equipmentType || call.equipmentBrand || call.equipmentAge) && (
              <div className="bg-cl-bg-panel p-5 rounded-xl">
                <h4 className="font-headline font-bold text-cl-text-muted text-[0.6875rem] uppercase tracking-widest mb-3">
                  Equipment Details
                </h4>
                <div className="flex flex-wrap gap-3 text-[0.6875rem] text-cl-text-primary">
                  {call.equipmentType && <span>{call.equipmentType}</span>}
                  {call.equipmentBrand && (
                    <span className="text-cl-text-muted">· {call.equipmentBrand}</span>
                  )}
                  {call.equipmentAge && (
                    <span className="text-cl-text-muted">· {call.equipmentAge}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Transcript */
          <div className="space-y-2 max-w-3xl">
            {loadingTranscript ? (
              <p className="text-xs text-cl-text-muted">Loading transcript…</p>
            ) : transcript.length > 0 ? (
              transcript.map((entry, i) => (
                <div
                  key={i}
                  className={cn(
                    "rounded-lg px-4 py-3 text-sm",
                    entry.role === "agent" ? "bg-cl-bg-card" : "bg-cl-bg-panel"
                  )}
                >
                  <span className="text-[10px] font-bold text-cl-text-muted uppercase tracking-wider">
                    {entry.role === "agent" ? "AI Agent" : "Customer"}
                  </span>
                  <p className="mt-1 text-cl-text-primary leading-relaxed">{entry.content}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-cl-text-muted">No transcript available</p>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
