import { format, isToday, isTomorrow } from "date-fns"
import type { Call } from "@/types/call"
import type { BucketAssignment } from "@/lib/triage"

export function getHandledSummary(call: Call, assignment: BucketAssignment): string {
  if (assignment.handledReason === "escalated") {
    return call.isSafetyEmergency
      ? "Safety emergency escalated to dispatch"
      : "Urgent issue escalated for immediate handling"
  }
  if (assignment.handledReason === "booked") {
    return "Appointment secured by AI"
  }
  if (assignment.handledReason === "non_customer") {
    return "Blocked: non-customer call (spam/vendor)"
  }
  if (assignment.handledReason === "wrong_number") {
    return "Dismissed: wrong number or out of service area"
  }
  return "Resolved: callback completed"
}

export function buildAISummary(call: Call): string {
  const parts: string[] = []

  const who = call.customerName ? `The caller, ${call.customerName},` : "The caller"
  parts.push(who)

  if (call.isSafetyEmergency) {
    parts.push("reported a safety emergency and was immediately escalated to dispatch.")
    if (call.problemDescription) {
      parts.push(`Details: "${call.problemDescription}"`)
    }
    return parts.join(" ")
  }

  if (call.isUrgentEscalation) {
    parts.push("reported an urgent issue and was escalated for immediate handling.")
    if (call.problemDescription) {
      parts.push(`Details: "${call.problemDescription}"`)
    }
    return parts.join(" ")
  }

  if (call.problemDescription) {
    parts.push(`reported: "${call.problemDescription}"`)
  } else if (call.hvacIssueType) {
    parts.push(`requested service for a ${call.hvacIssueType} issue.`)
  } else {
    parts.push("reached out for assistance.")
  }

  if (call.serviceAddress) {
    parts.push(`Service address: ${call.serviceAddress}.`)
  }

  if (call.appointmentBooked) {
    const apptLine = call.appointmentDateTime
      ? (() => {
          try {
            const d = new Date(call.appointmentDateTime)
            if (isToday(d)) return `Today @ ${format(d, "h:mm a")}`
            if (isTomorrow(d)) return `Tomorrow @ ${format(d, "h:mm a")}`
            return format(d, "MMM d @ h:mm a")
          } catch {
            return ""
          }
        })()
      : ""
    parts.push(apptLine ? `The appointment was successfully scheduled for ${apptLine}.` : "The appointment was successfully scheduled.")
  } else if (call.endCallReason === "callback_later") {
    parts.push("Customer requested a callback.")
  }

  return parts.join(" ")
}
