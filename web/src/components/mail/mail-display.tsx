"use client"

import { useEffect, useState } from "react"
import { format } from "date-fns"
import { Bot, Zap, Play, Sparkles, Archive, Ellipsis } from "lucide-react"
import { createBrowserClient } from "@/lib/supabase"
import { parseTranscript } from "@/lib/transforms"
import type { Call, EndCallReason, TranscriptEntry, UrgencyTier } from "@/types/call"

interface MailDisplayProps {
  call: Call | null
}

type Tab = "summary" | "transcript" | "details"

function urgencyToTag(urgency: UrgencyTier): string {
  switch (urgency) {
    case "LifeSafety": return "urgent"
    case "Urgent": return "needs-review"
    case "Routine": return "routine"
    case "Estimate": return "estimate"
  }
}

function outcomeToText(reason: EndCallReason | null): string {
  if (!reason) return "Outcome pending"
  const map: Record<EndCallReason, string> = {
    completed: "Service call completed",
    booking_failed: "Booking attempt failed",
    callback_later: "Customer will call back",
    safety_emergency: "Safety emergency escalated",
    urgent_escalation: "Urgently escalated to dispatcher",
    wrong_number: "Wrong number",
    out_of_area: "Outside service area",
    waitlist_added: "Added to waitlist",
    customer_hangup: "Customer disconnected",
    sales_lead: "Sales lead captured",
    cancelled: "Appointment cancelled",
    rescheduled: "Appointment rescheduled",
  }
  return map[reason]
}

function Badge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs border border-[#3e3e3e] text-[#ccc] bg-transparent">
      {label}
    </span>
  )
}

function ActionButton({
  icon,
  label,
  primary,
}: {
  icon?: React.ReactNode
  label: string
  primary?: boolean
}) {
  return (
    <button
      className={
        primary
          ? "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium border transition-colors cursor-pointer bg-[#252525] border-[#3e3e3e] text-[#f0f0f0] hover:bg-[#2e2e2e]"
          : "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium border transition-colors cursor-pointer bg-transparent border-[#323232] text-[#ccc] hover:bg-[#1e1e1e] hover:text-[#f0f0f0]"
      }
    >
      {icon}
      {label}
    </button>
  )
}

export function MailDisplay({ call }: MailDisplayProps) {
  const [activeTab, setActiveTab] = useState<Tab>("summary")
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [loadingTranscript, setLoadingTranscript] = useState(false)

  useEffect(() => {
    if (!call) {
      setTranscript([])
      return
    }
    if (call.transcript.length > 0) {
      setTranscript(call.transcript)
      return
    }
    let cancelled = false
    setLoadingTranscript(true)
    const supabase = createBrowserClient()
    const fetchTranscript = async () => {
      try {
        const { data } = await supabase
          .from("call_records")
          .select("transcript")
          .eq("call_id", call.id)
          .single()
        if (cancelled) return
        setLoadingTranscript(false)
        if (typeof data?.transcript !== "string") {
          setTranscript([])
          return
        }
        setTranscript(parseTranscript(data.transcript))
      } catch {
        if (!cancelled) {
          setLoadingTranscript(false)
          setTranscript([])
        }
      }
    }
    fetchTranscript()
    return () => { cancelled = true }
  }, [call?.id, call?.transcript])

  if (!call) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-[#555]">Select a call to view details</p>
      </div>
    )
  }

  const urgencyTag = urgencyToTag(call.urgency)
  const outcomeText = outcomeToText(call.endCallReason)
  const title = call.problemDescription || call.hvacIssueType || "Call record"
  const equipmentParts = [call.equipmentType, call.equipmentBrand, call.equipmentAge].filter(Boolean)
  const bookingTag = call.appointmentBooked ? "booked" : call.endCallReason === "callback_later" ? "callback" : "pending"
  const automationStatus = call.appointmentBooked
    ? "Appointment booked via Cal.com."
    : call.endCallReason === "callback_later"
    ? "Callback scheduled. Autopilot is observe."
    : "No booking action taken."

  return (
    <div className="px-8 py-6 max-w-5xl">
      <h1 className="text-xl font-bold text-[#f5f5f5] leading-tight text-pretty">{title}</h1>

      <div className="mt-2 space-y-0.5">
        {call.customerPhone && (
          <p className="text-sm text-[#777]">From {call.customerPhone}</p>
        )}
        <p className="text-sm text-[#777]">
          {format(new Date(call.createdAt), "MMM d, yyyy, h:mm aa")}
        </p>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <Badge label={urgencyTag} />
        {call.hvacIssueType && <Badge label={call.hvacIssueType.toLowerCase()} />}
        {call.isSafetyEmergency && <Badge label="safety" />}
      </div>

      <div className="mt-4 flex items-center gap-2 flex-wrap">
        <ActionButton primary icon={<Play width={13} height={13} aria-hidden />} label="Review" />
        <ActionButton icon={<Sparkles width={13} height={13} aria-hidden />} label="Ask AI" />
        <ActionButton label="Mark reviewed" />
        <ActionButton icon={<Archive width={13} height={13} aria-hidden />} label="Archive" />
        <ActionButton icon={<Ellipsis width={13} height={13} aria-hidden />} label="More" />
      </div>

      <div className="mt-5 flex items-center gap-6 border-b border-[#252525]">
        {(["summary", "transcript", "details"] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={
              activeTab === tab
                ? "pb-2 text-sm font-medium transition-colors border-b-2 border-[#f0f0f0] text-[#f0f0f0] capitalize"
                : "pb-2 text-sm font-medium transition-colors border-b-2 border-transparent text-[#666] hover:text-[#aaa] capitalize"
            }
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "summary" && (
        <div className="mt-5 grid grid-cols-2 gap-4">
          {/* Why This Matters */}
          <div className="bg-[#191919] border border-[#2a2a2a] rounded-xl p-5 flex flex-col gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[#666]">
              Why This Matters
            </p>
            <div className="text-sm text-[#d0d0d0] leading-relaxed">
              <p>{call.problemDescription || "No problem description captured."}</p>
            </div>
          </div>

          {/* Best Next Move */}
          <div className="bg-[#191919] border border-[#2a2a2a] rounded-xl p-5 flex flex-col gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[#666]">
              Best Next Move
            </p>
            <div className="text-sm text-[#d0d0d0] leading-relaxed">
              <p>{outcomeText}</p>
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <Badge label={urgencyTag} />
                {call.endCallReason && (
                  <Badge label={call.endCallReason.replace(/_/g, "-")} />
                )}
              </div>
            </div>
          </div>

          {/* AI Summary */}
          <div className="bg-[#191919] border border-[#2a2a2a] rounded-xl p-5 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <span className="text-[#888]">
                <Bot width={15} height={15} aria-hidden />
              </span>
              <p className="text-sm font-semibold text-[#f0f0f0]">AI summary</p>
            </div>
            <div className="text-sm text-[#c0c0c0] leading-relaxed">
              <p>{call.problemDescription || "No summary available."}</p>
              {equipmentParts.length > 0 && (
                <div className="mt-3 flex flex-col gap-1.5">
                  {equipmentParts.map((part, i) => (
                    <button
                      key={i}
                      className="text-left text-xs text-[#bbb] px-3 py-2 rounded-md border border-[#2a2a2a] hover:bg-[#222] hover:text-[#f0f0f0] transition-colors"
                    >
                      {part}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Automation Status */}
          <div className="bg-[#191919] border border-[#2a2a2a] rounded-xl p-5 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <span className="text-[#888]">
                <Zap width={15} height={15} aria-hidden />
              </span>
              <p className="text-sm font-semibold text-[#f0f0f0]">Automation status</p>
            </div>
            <div className="text-sm text-[#c0c0c0] leading-relaxed">
              <p className="text-[#777] text-xs">{automationStatus}</p>
              <div className="mt-2 flex items-center gap-2 flex-wrap">
                <Badge label={bookingTag} />
                {call.appointmentBooked && call.appointmentDateTime && (
                  <Badge label={format(new Date(call.appointmentDateTime), "MMM d")} />
                )}
              </div>
              {call.isSafetyEmergency && (
                <p className="mt-2 text-xs text-[#aaa]">Safety emergency was detected and escalated.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === "transcript" && (
        <div className="mt-5">
          {loadingTranscript ? (
            <p className="text-xs text-[#555]">Loading transcript...</p>
          ) : transcript.length > 0 ? (
            <div className="flex flex-col gap-2">
              {transcript.map((entry, i) => (
                <div
                  key={i}
                  className={
                    entry.role === "agent"
                      ? "rounded-lg px-3 py-2 text-sm bg-[#191919] border border-[#2a2a2a]"
                      : "rounded-lg px-3 py-2 text-sm bg-[#141414] border border-[#242424]"
                  }
                >
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-[#666]">
                    {entry.role === "agent" ? "AI Agent" : "Customer"}
                  </span>
                  <p className="mt-0.5 text-[#c0c0c0]">{entry.content}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[#555]">No transcript available for this call.</p>
          )}
        </div>
      )}

      {activeTab === "details" && (
        <div className="mt-5 flex flex-col gap-4">
          {call.serviceAddress && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-[#666] mb-1">
                Service address
              </p>
              <p className="text-sm text-[#d0d0d0]">{call.serviceAddress}</p>
            </div>
          )}
          {equipmentParts.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-[#666] mb-1">
                Equipment
              </p>
              <p className="text-sm text-[#d0d0d0]">{equipmentParts.join(" · ")}</p>
            </div>
          )}
          {call.appointmentBooked && call.appointmentDateTime && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-[#666] mb-1">
                Appointment
              </p>
              <p className="text-sm text-[#d0d0d0]">
                {format(new Date(call.appointmentDateTime), "PPpp")}
              </p>
            </div>
          )}
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[#666] mb-1">
              Call outcome
            </p>
            <p className="text-sm text-[#d0d0d0]">{outcomeText}</p>
          </div>
        </div>
      )}
    </div>
  )
}
