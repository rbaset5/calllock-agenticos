import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { MailList, sectionColor, sectionLabel } from "../mail-list"
import type { Call } from "@/types/call"
import type { BucketAssignment } from "@/lib/triage"

function makeCall(id: string, overrides: Partial<Call> = {}): Call {
  return {
    id,
    customerName: "Test Customer",
    customerPhone: "15551234567",
    serviceAddress: "123 Main St",
    problemDescription: "AC issue",
    urgency: "Routine",
    hvacIssueType: null,
    equipmentType: "",
    equipmentBrand: "",
    equipmentAge: "",
    appointmentBooked: false,
    appointmentDateTime: null,
    endCallReason: null,
    isSafetyEmergency: false,
    isUrgentEscalation: false,
    transcript: [],
    callbackType: null,
    read: false,
    callbackOutcome: null,
    callbackOutcomeAt: null,
    bookingStatus: null,
    bookingStatusAt: null,
    bookingNotes: null,
    callbackWindowStart: null,
    callbackWindowEnd: null,
    callerType: null,
    primaryIntent: null,
    route: null,
    revenueTier: null,
    extractionStatus: null,
    callRecordingUrl: null,
    createdAt: new Date().toISOString(),
    ...overrides,
  }
}

const escalatedCall = makeCall("esc-1", { isSafetyEmergency: true })
const leadCall = makeCall("lead-1")
const followUpCall = makeCall("follow-1", { endCallReason: "callback_later" })
const bookedCall = makeCall("booked-1", { appointmentBooked: true })
const scheduledCall = makeCall("sched-1", { appointmentBooked: true, bookingStatus: "confirmed" })
const otherCall = makeCall("other-1", { endCallReason: "wrong_number" })

const allItems = [escalatedCall, leadCall, followUpCall, bookedCall, scheduledCall, otherCall]

const buckets = {
  ESCALATED_BY_AI: [escalatedCall],
  NEW_LEADS: [leadCall],
  FOLLOW_UPS: [followUpCall],
  BOOKINGS: [bookedCall, scheduledCall],
  OTHER_AI_HANDLED: [otherCall],
}

const bucketMap = new Map<string, BucketAssignment>([
  ["esc-1", { bucket: "AI_HANDLED", subGroup: null, escalationMarker: true, handledReason: "escalated" }],
  ["lead-1", { bucket: "ACTION_QUEUE", subGroup: "NEW_LEAD", escalationMarker: false, handledReason: null }],
  ["follow-1", { bucket: "ACTION_QUEUE", subGroup: "FOLLOW_UP", escalationMarker: false, handledReason: null }],
  ["booked-1", { bucket: "AI_HANDLED", subGroup: null, escalationMarker: false, handledReason: "booked" }],
  ["sched-1", { bucket: "AI_HANDLED", subGroup: null, escalationMarker: false, handledReason: "booked" }],
  ["other-1", { bucket: "AI_HANDLED", subGroup: null, escalationMarker: false, handledReason: "wrong_number" }],
])

describe("MailList section ordering and rendering", () => {
  it("renders Active tab content by default and exposes all tab buttons", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html).toContain("Bookings")
    expect(html).toContain("New Leads")
    expect(html).toContain("Timeline")
    expect(html).not.toContain("Scheduled Bookings")
  })

  it("renders Bookings FIRST in active tab, before New Leads", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html.indexOf("Bookings")).toBeLessThan(html.indexOf("New Leads"))
    expect(html.indexOf("New Leads")).toBeLessThan(html.indexOf("Escalated by AI"))
    expect(html.indexOf("Escalated by AI")).toBeLessThan(html.indexOf("Follow-ups"))
    expect(html.indexOf("Follow-ups")).toBeLessThan(html.indexOf("AI Handled ("))
  })

  it("keeps Other AI Handled collapsible with correct id", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html).toContain("other-ai-handled-list")
  })

  it("escalated cards render danger treatment, not neutral handled opacity", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    // Escalated cards should use danger chip class
    expect(html).toContain("bg-cl-danger/10")
    // Only OTHER_AI_HANDLED should have opacity-50, not escalated
    const escalatedSection = html.slice(
      html.indexOf("Escalated by AI"),
      html.indexOf("New Leads")
    )
    expect(escalatedSection).not.toContain("opacity-50")
  })

  it("bookings section renders booked calendar slots treatment", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html).toContain("Bookings")
    expect(html).toContain("bg-cl-success/10")
    expect(html).toContain("bg-cl-accent/10")
    const bookedSection = html.slice(
      html.indexOf("Bookings"),
      html.indexOf("AI Handled (")
    )
    expect(bookedSection).toContain("Bookings")
  })

  it("Other AI Handled renders with muted opacity treatment", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    const otherSection = html.slice(html.indexOf("other-ai-handled-list"))
    expect(otherSection).toContain("opacity-50")
  })

  it("New Leads section renders Call Back control", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html).toContain("Call Back")
  })

  it("keeps the red Call now panel for urgent concrete new leads", () => {
    const urgentLead = makeCall("urgent-lead", {
      urgency: "Urgent",
      problemDescription: "No cooling and water leak",
    })
    const urgentBuckets = {
      ESCALATED_BY_AI: [],
      NEW_LEADS: [urgentLead],
      FOLLOW_UPS: [],
      BOOKINGS: [],
      OTHER_AI_HANDLED: [],
    }
    const urgentBucketMap = new Map<string, BucketAssignment>([
      ["urgent-lead", { bucket: "ACTION_QUEUE", subGroup: "NEW_LEAD", escalationMarker: false, handledReason: null }],
    ])

    const html = renderToStaticMarkup(
      <MailList
        items={[urgentLead]}
        selected={null}
        onSelect={() => {}}
        buckets={urgentBuckets}
        bucketMap={urgentBucketMap}
      />
    )

    expect(html).toContain("Priority: Call now.")
    expect(html).toContain("bg-cl-danger/80")
  })

  it("shows outcome chips on selected actionable cards", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected="lead-1"
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html).toContain("Reached Customer")
    expect(html).toContain("Scheduled")
    expect(html).toContain("Left Voicemail")
    expect(html).toContain("No Answer")
  })
})

describe("sectionLabel", () => {
  it("returns expected labels for each section", () => {
    expect(sectionLabel("ESCALATED_BY_AI")).toBe("Escalated")
    expect(sectionLabel("NEW_LEADS")).toBe("New")
    expect(sectionLabel("FOLLOW_UPS")).toBe("Follow-up")
    expect(sectionLabel("BOOKINGS")).toBe("Bookings")
    expect(sectionLabel("OTHER_AI_HANDLED")).toBe("Handled")
  })
})

describe("sectionColor", () => {
  it("returns expected color class per section", () => {
    expect(sectionColor("ESCALATED_BY_AI")).toBe("text-cl-danger")
    expect(sectionColor("NEW_LEADS")).toBe("text-cl-accent")
    expect(sectionColor("FOLLOW_UPS")).toBe("text-cl-text-muted")
    expect(sectionColor("BOOKINGS")).toBe("text-cl-success")
    expect(sectionColor("OTHER_AI_HANDLED")).toBe("text-cl-text-muted/60")
  })
})
