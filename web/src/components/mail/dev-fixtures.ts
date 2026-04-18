/**
 * Deterministic dev fixture data for visual QA.
 * DEVELOPMENT ONLY — never imported in production paths.
 */
import type { Call } from "@/types/call"

const BASE_TIME = new Date("2026-03-27T12:00:00.000Z").getTime()

function makeFixture(id: string, overrides: Partial<Call>, minutesAgo: number): Call {
  return {
    id,
    customerName: "",
    customerPhone: "15551230000",
    serviceAddress: "123 Main St, Tampa, FL",
    problemDescription: "",
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
    bookingStatus: null,
    bookingStatusAt: null,
    bookingNotes: null,
    createdAt: new Date(BASE_TIME - minutesAgo * 60_000).toISOString(),
    ...overrides,
  }
}

export function getMailDevFixtures(): Call[] {
  return [
    makeFixture(
      "fixture-escalated",
      {
        customerName: "Maria Garcia",
        customerPhone: "15551230001",
        isSafetyEmergency: true,
        urgency: "LifeSafety",
        problemDescription: "Smell of gas near the furnace",
      },
      5
    ),
    makeFixture(
      "fixture-lead",
      {
        customerName: "James Wilson",
        customerPhone: "15551230002",
        urgency: "Urgent",
        problemDescription: "AC not cooling at all",
        hvacIssueType: "No Cool",
      },
      20
    ),
    makeFixture(
      "fixture-followup",
      {
        customerName: "Sarah Chen",
        customerPhone: "15551230003",
        endCallReason: "callback_later",
        callbackOutcome: "left_voicemail",
        callbackOutcomeAt: new Date(BASE_TIME - 10 * 60_000).toISOString(),
      },
      45
    ),
    makeFixture(
      "fixture-booked",
      {
        customerName: "Robert Davis",
        customerPhone: "15551230004",
        appointmentBooked: true,
        appointmentDateTime: new Date(BASE_TIME + 24 * 60 * 60_000).toISOString(),
        problemDescription: "Annual AC tune-up",
      },
      60
    ),
    makeFixture(
      "fixture-other-handled",
      {
        customerName: "",
        customerPhone: "15551230005",
        endCallReason: "wrong_number",
      },
      90
    ),
  ]
}
