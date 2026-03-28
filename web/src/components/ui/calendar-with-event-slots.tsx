"use client"

import { useState, useCallback, useMemo } from "react"
import { format, isToday, isTomorrow, isSameDay } from "date-fns"
import { CheckCircle2, CalendarCheck, X } from "lucide-react"
import type { DayButtonProps } from "react-day-picker"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import type { BookingStatus, Call } from "@/types/call"
import { Calendar } from "@/components/ui/calendar"

interface CalendarWithEventSlotsProps {
  calls: Call[]
  selectedCallId: string | null
  onSelectCall: (id: string) => void
  onBookingStatusChange?: (
    callId: string,
    status: BookingStatus,
    appointmentDateTime?: string
  ) => void
}

function formatSlotTime(dateStr: string | null): string {
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

function bookingDotClass(status: BookingStatus | null): string {
  if (status === "confirmed") return "bg-cl-success"
  if (status === "rescheduled") return "bg-amber-400"
  return "ring-2 ring-cl-success bg-transparent"
}

function bookingSlotAccentClass(status: BookingStatus | null): string {
  if (status === "confirmed") return "after:bg-cl-success/70"
  if (status === "rescheduled") return "after:bg-amber-400/80"
  return "after:bg-transparent after:border after:border-cl-success/80"
}

export function CalendarWithEventSlots({
  calls,
  selectedCallId,
  onSelectCall,
  onBookingStatusChange,
}: CalendarWithEventSlotsProps) {
  const [selectedDate, setSelectedDate] = useState<Date>(new Date())
  const [reschedulingId, setReschedulingId] = useState<string | null>(null)
  const [rescheduleDateTime, setRescheduleDateTime] = useState("")
  const [submittingBookingId, setSubmittingBookingId] = useState<string | null>(null)

  const appointmentsByDay = useMemo(
    () => {
      const grouped = new Map<string, Call[]>()
      for (const call of calls) {
        if (!call.appointmentDateTime) continue
        const key = format(new Date(call.appointmentDateTime), "yyyy-MM-dd")
        const existing = grouped.get(key) ?? []
        existing.push(call)
        grouped.set(key, existing)
      }
      return grouped
    },
    [calls]
  )

  const appointmentDates = useMemo(
    () =>
      calls
        .filter((c) => c.appointmentDateTime)
        .map((c) => new Date(c.appointmentDateTime!)),
    [calls]
  )

  const visibleCalls = useMemo(() => {
    const forDay = calls.filter(
      (c) =>
        c.appointmentDateTime &&
        isSameDay(new Date(c.appointmentDateTime), selectedDate)
    )
    return forDay.length > 0 ? forDay : calls
  }, [calls, selectedDate])

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
          body: JSON.stringify({
            status,
            ...(appointmentDateTime ? { appointmentDateTime } : {}),
          }),
        })
        if (!res.ok) throw new Error("not-ok")
        setReschedulingId(null)
        setRescheduleDateTime("")
      } catch {
        onBookingStatusChange?.(call.id, currentBookingStatus ?? "cancelled")
        toast.error("Couldn't save — try again")
      } finally {
        setSubmittingBookingId(null)
      }
    },
    [submittingBookingId, onBookingStatusChange]
  )

  const showingAllLabel =
    !calls.some(
      (c) =>
        c.appointmentDateTime &&
        isSameDay(new Date(c.appointmentDateTime), selectedDate)
    )

  return (
    <div className="shrink-0 rounded-lg border border-border bg-card">
      {/* Month calendar */}
      <div className="px-4 pt-4 pb-2">
        <Calendar
          mode="single"
          selected={selectedDate}
          onSelect={(day) => {
            if (day) setSelectedDate(day)
          }}
          showOutsideDays
          className="!w-full bg-transparent p-0"
          modifiers={{ hasAppointment: appointmentDates }}
          components={{
            DayButton: (props: DayButtonProps) => {
              const dateKey = format(props.day.date, "yyyy-MM-dd")
              const dayCalls = (appointmentsByDay.get(dateKey) ?? []).slice(0, 4)
              return (
                <button {...props} className={cn(props.className, "relative overflow-visible")}>
                  {props.children}
                  {dayCalls.length > 0 && (
                    <span className="pointer-events-none absolute bottom-0 start-1/2 flex -translate-x-1/2 items-center gap-0.5">
                      {dayCalls.map((call) => {
                        const dotClass = bookingDotClass(call.bookingStatus)
                        return (
                          <span
                            key={`${dateKey}-${call.id}`}
                            className={cn("h-1.5 w-1.5 rounded-full", dotClass)}
                          />
                        )
                      })}
                    </span>
                  )}
                </button>
              )
            },
          }}
        />
      </div>

      {/* Event slots */}
      {visibleCalls.length > 0 && (
        <div className="flex flex-col gap-2 border-t px-4 pt-4 pb-4">
          <div className="flex items-center justify-between px-1">
            <div>
              <div className="text-sm font-medium">
                {showingAllLabel
                  ? "Bookings"
                  : selectedDate?.toLocaleDateString("en-US", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
              </div>
              {showingAllLabel && selectedDate && isToday(selectedDate) && (
                <div className="text-xs text-muted-foreground mt-0.5">Today</div>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            {visibleCalls.map((call) => {
              const isSelected = call.id === selectedCallId
              const hasDateTime = !!call.appointmentDateTime
              const accentClass = bookingSlotAccentClass(call.bookingStatus)

              return (
                <div
                  key={call.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectCall(call.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      onSelectCall(call.id)
                    }
                  }}
                  className={cn(
                    "relative rounded-md p-2 pl-5 text-sm cursor-pointer transition-colors select-none",
                    "after:absolute after:inset-y-2 after:left-1.5 after:w-1 after:rounded-full",
                    accentClass,
                    isSelected
                      ? "bg-cl-bg-chip"
                      : "bg-muted hover:bg-accent/50"
                  )}
                >
                  <div className="font-medium">
                    {call.customerName || call.customerPhone || "Unknown caller"}
                  </div>
                  <div className="text-muted-foreground text-xs">
                    {hasDateTime
                      ? formatSlotTime(call.appointmentDateTime)
                      : "Time TBD"}
                  </div>

                  {/* Confirm / Reschedule / Cancel — selected slot only */}
                  {isSelected && (
                    <div
                      className="flex flex-col gap-2 mt-2"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {reschedulingId === call.id ? (
                        <div className="flex flex-col gap-2">
                          <input
                            type="datetime-local"
                            value={rescheduleDateTime}
                            onChange={(e) => setRescheduleDateTime(e.target.value)}
                            className="h-8 px-2 rounded-md bg-muted text-sm border border-border focus:outline-none focus:border-ring"
                          />
                          <div className="flex gap-1.5">
                            <button
                              disabled={!rescheduleDateTime || !!submittingBookingId}
                              onClick={() =>
                                handleBookingAction(call, "rescheduled", rescheduleDateTime)
                              }
                              className="h-7 px-2.5 rounded-full text-[0.6875rem] uppercase font-semibold flex items-center gap-1 bg-amber-900/30 text-amber-400 hover:bg-amber-900/50 disabled:opacity-50"
                            >
                              <CalendarCheck className="h-3 w-3" />
                              Confirm reschedule
                            </button>
                            <button
                              onClick={() => {
                                setReschedulingId(null)
                                setRescheduleDateTime("")
                              }}
                              className="h-7 px-2 rounded-full text-[0.6875rem] flex items-center gap-1 bg-muted text-muted-foreground hover:bg-accent"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex gap-1.5 flex-wrap">
                          <button
                            disabled={!!submittingBookingId}
                            onClick={() => handleBookingAction(call, "confirmed")}
                            className="h-7 px-2.5 rounded-full text-[0.6875rem] uppercase font-semibold flex items-center gap-1 bg-cl-success/20 text-cl-success hover:bg-cl-success/30 disabled:opacity-50"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            Confirm
                          </button>
                          <button
                            disabled={!!submittingBookingId}
                            onClick={() => {
                              setReschedulingId(call.id)
                              setRescheduleDateTime("")
                            }}
                            className="h-7 px-2.5 rounded-full text-[0.6875rem] uppercase font-semibold flex items-center gap-1 bg-amber-900/30 text-amber-400 hover:bg-amber-900/50 disabled:opacity-50"
                          >
                            <CalendarCheck className="h-3 w-3" />
                            Reschedule
                          </button>
                          <button
                            disabled={!!submittingBookingId}
                            onClick={() => handleBookingAction(call, "cancelled")}
                            className="h-7 px-2.5 rounded-full text-[0.6875rem] uppercase font-semibold flex items-center gap-1 bg-muted text-muted-foreground hover:bg-accent disabled:opacity-50"
                          >
                            <X className="h-3 w-3" />
                            Cancel
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
