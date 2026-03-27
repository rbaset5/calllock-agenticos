import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { MailList } from "../mail-list"
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
const otherCall = makeCall("other-1", { endCallReason: "wrong_number" })

const allItems = [escalatedCall, leadCall, followUpCall, bookedCall, otherCall]

const buckets = {
  ESCALATED_BY_AI: [escalatedCall],
  NEW_LEADS: [leadCall],
  FOLLOW_UPS: [followUpCall],
  BOOKED_BY_AI: [bookedCall],
  OTHER_AI_HANDLED: [otherCall],
}

const bucketMap = new Map<string, BucketAssignment>([
  ["esc-1", { bucket: "AI_HANDLED", subGroup: null, escalationMarker: true, handledReason: "escalated" }],
  ["lead-1", { bucket: "ACTION_QUEUE", subGroup: "NEW_LEAD", escalationMarker: false, handledReason: null }],
  ["follow-1", { bucket: "ACTION_QUEUE", subGroup: "FOLLOW_UP", escalationMarker: false, handledReason: null }],
  ["booked-1", { bucket: "AI_HANDLED", subGroup: null, escalationMarker: false, handledReason: "booked" }],
  ["other-1", { bucket: "AI_HANDLED", subGroup: null, escalationMarker: false, handledReason: "wrong_number" }],
])

describe("MailList section ordering and rendering", () => {
  it("renders top-level sections in spec order", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html.indexOf("Escalated by AI")).toBeLessThan(html.indexOf("New Leads"))
    expect(html.indexOf("New Leads")).toBeLessThan(html.indexOf("Follow-ups"))
    expect(html.indexOf("Follow-ups")).toBeLessThan(html.indexOf("Booked by AI"))
    expect(html.indexOf("Booked by AI")).toBeLessThan(html.indexOf("Other AI Handled"))
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

  it("booked cards render success treatment", () => {
    const html = renderToStaticMarkup(
      <MailList
        items={allItems}
        selected={null}
        onSelect={() => {}}
        buckets={buckets}
        bucketMap={bucketMap}
      />
    )

    expect(html).toContain("bg-cl-success/10")
    const bookedSection = html.slice(
      html.indexOf("Booked by AI"),
      html.indexOf("Other AI Handled")
    )
    expect(bookedSection).not.toContain("opacity-50")
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
})
