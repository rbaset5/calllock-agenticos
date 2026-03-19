"use client"

import { useEffect, useState } from "react"
import { format } from "date-fns"
import { Phone, MapPin, Wrench, Clock, AlertTriangle, Calendar } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { getUrgencyVariant } from "@/lib/utils"
import { createBrowserClient } from "@/lib/supabase"
import { parseTranscript } from "@/lib/transforms"
import type { Call, TranscriptEntry } from "@/types/call"
import { cn } from "@/lib/utils"

interface MailDisplayProps {
  call: Call | null
}

export function MailDisplay({ call }: MailDisplayProps) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [loadingTranscript, setLoadingTranscript] = useState(false)
  const [transcriptError, setTranscriptError] = useState(false)
  const callId = call?.id ?? null
  const existingTranscript = call?.transcript

  // Lazy-load transcript when a call is selected (review decision 10A)
  useEffect(() => {
    if (!callId) {
      setTranscript([])
      setLoadingTranscript(false)
      setTranscriptError(false)
      return
    }

    // If transcript was already in the initial data, use it
    if ((existingTranscript?.length ?? 0) > 0) {
      setTranscript(existingTranscript ?? [])
      setLoadingTranscript(false)
      setTranscriptError(false)
      return
    }

    // Otherwise fetch the raw transcript for this call
    let cancelled = false
    setLoadingTranscript(true)
    setTranscriptError(false)

    const supabase = createBrowserClient()
    const fetchTranscript = async () => {
      try {
        const { data, error } = await supabase
          .from("call_records")
          .select("transcript")
          .eq("call_id", callId)
          .single()

        if (error) {
          throw error
        }
        if (cancelled) return

        setLoadingTranscript(false)
        setTranscriptError(false)

        if (typeof data?.transcript !== "string") {
          setTranscript([])
          return
        }

        setTranscript(parseTranscript(data.transcript))
      } catch {
        if (!cancelled) {
          setLoadingTranscript(false)
          setTranscript([])
          setTranscriptError(true)
        }
      }
    }
    fetchTranscript()

    return () => {
      cancelled = true
    }
  }, [callId, existingTranscript])

  if (!call) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-muted-foreground">
        <p className="text-sm">Select a call to view details</p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-start p-4">
        <div className="flex items-start gap-4 text-sm">
          <Avatar>
            <AvatarFallback>
              {(call.customerName || "?")
                .split(" ")
                .map((w) => w[0])
                .join("")
                .substring(0, 2)
                .toUpperCase()}
            </AvatarFallback>
          </Avatar>
          <div className="grid gap-1">
            <div className="font-semibold">
              {call.customerName || "Unknown Caller"}
            </div>
            {call.customerPhone && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Phone className="h-3 w-3" />
                {call.customerPhone}
              </div>
            )}
            {call.serviceAddress && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <MapPin className="h-3 w-3" />
                {call.serviceAddress}
              </div>
            )}
          </div>
        </div>
        <div className="ml-auto flex flex-col items-end gap-1">
          <div className="text-xs text-muted-foreground">
            {format(new Date(call.createdAt), "PPpp")}
          </div>
          <div className="flex gap-1">
            <Badge variant={getUrgencyVariant(call.urgency)}>
              {call.urgency}
            </Badge>
            {call.appointmentBooked && (
              <Badge variant="outline">Booked</Badge>
            )}
          </div>
        </div>
      </div>

      <Separator />

      <ScrollArea className="flex-1">
        <div className="space-y-4 p-4">
          {/* Problem Description */}
          {call.problemDescription && (
            <section>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                Problem
              </h3>
              <p className="text-sm">{call.problemDescription}</p>
              {call.hvacIssueType && (
                <Badge variant="outline" className="mt-1">
                  {call.hvacIssueType}
                </Badge>
              )}
            </section>
          )}

          {/* Equipment Details */}
          {(call.equipmentType || call.equipmentBrand || call.equipmentAge) && (
            <section>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                Equipment
              </h3>
              <div className="flex flex-wrap gap-2 text-sm">
                {call.equipmentType && (
                  <div className="flex items-center gap-1">
                    <Wrench className="h-3 w-3 text-muted-foreground" />
                    {call.equipmentType}
                  </div>
                )}
                {call.equipmentBrand && (
                  <span className="text-muted-foreground">
                    · {call.equipmentBrand}
                  </span>
                )}
                {call.equipmentAge && (
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3 text-muted-foreground" />
                    {call.equipmentAge}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Booking Details */}
          {call.appointmentBooked && call.appointmentDateTime && (
            <section>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                Appointment
              </h3>
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="h-3 w-3 text-muted-foreground" />
                {format(new Date(call.appointmentDateTime), "PPpp")}
              </div>
            </section>
          )}

          {/* Safety Warning */}
          {call.isSafetyEmergency && (
            <section className="rounded-md border border-destructive/50 bg-destructive/10 p-3">
              <div className="flex items-center gap-2 text-sm font-medium text-destructive">
                <AlertTriangle className="h-4 w-4" />
                Safety Emergency Detected
              </div>
            </section>
          )}

          {/* Transcript */}
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              Transcript
            </h3>
            {loadingTranscript ? (
              <p className="text-xs text-muted-foreground">Loading transcript...</p>
            ) : transcriptError ? (
              <p className="text-xs text-muted-foreground">
                Transcript unavailable. Try refreshing.
              </p>
            ) : transcript.length > 0 ? (
              <div className="space-y-2">
                {transcript.map((entry, i) => (
                  <div
                    key={i}
                    className={cn(
                      "rounded-lg px-3 py-2 text-sm",
                      entry.role === "agent" ? "bg-muted" : "bg-primary/5"
                    )}
                  >
                    <span className="text-xs font-medium text-muted-foreground">
                      {entry.role === "agent" ? "AI Agent" : "Customer"}
                    </span>
                    <p className="mt-0.5">{entry.content}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No transcript available</p>
            )}
          </section>

          {/* Call Outcome */}
          {call.endCallReason && (
            <section>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                Call Outcome
              </h3>
              <Badge variant="secondary">
                {call.endCallReason.replace(/_/g, " ")}
              </Badge>
            </section>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
