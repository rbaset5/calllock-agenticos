import { describe, it, expect, vi, beforeEach } from "vitest"

vi.mock("server-only", () => ({}))

vi.mock("@/lib/supabase-server", () => ({
  createServerClient: vi.fn(),
}))

import { PATCH } from "../route"
import { createServerClient } from "@/lib/supabase-server"

const mockRpc = vi.fn()
const mockUpdate = vi.fn()
const mockEq = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  mockEq.mockResolvedValue({ error: null })
  mockRpc.mockResolvedValue({ error: null })
  mockUpdate.mockReturnValue({ eq: mockEq })
  ;(createServerClient as ReturnType<typeof vi.fn>).mockReturnValue({
    from: vi.fn().mockReturnValue({ update: mockUpdate }),
    rpc: mockRpc,
  })
})

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/calls/test-call-id/booking-status", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

function makeContext(callId: string) {
  return { params: Promise.resolve({ callId }) }
}

describe("PATCH /api/calls/[callId]/booking-status", () => {
  it("returns 200 for confirmed status", async () => {
    const req = makeRequest({ status: "confirmed" })
    const res = await PATCH(req, makeContext("call-123"))

    expect(res.status).toBe(200)
    const json = await res.json()
    expect(json).toMatchObject({ ok: true, status: "confirmed" })
    expect(typeof json.touchedAt).toBe("string")
    expect(mockRpc).not.toHaveBeenCalled()
  })

  it("persists notes when provided", async () => {
    const req = makeRequest({ status: "confirmed", notes: "Gate code 4412" })
    const res = await PATCH(req, makeContext("call-123"))

    expect(res.status).toBe(200)
    expect(mockUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        booking_status: "confirmed",
        booking_notes: "Gate code 4412",
      })
    )
  })

  it("returns 200 for cancelled status", async () => {
    const req = makeRequest({ status: "cancelled" })
    const res = await PATCH(req, makeContext("call-123"))

    expect(res.status).toBe(200)
    const json = await res.json()
    expect(json).toMatchObject({ ok: true, status: "cancelled" })
  })

  it("returns 200 for rescheduled with appointmentDateTime and calls RPC", async () => {
    const req = makeRequest({ status: "rescheduled", appointmentDateTime: "2026-04-01T10:00:00" })
    const res = await PATCH(req, makeContext("call-123"))

    expect(res.status).toBe(200)
    const json = await res.json()
    expect(json).toMatchObject({ ok: true, status: "rescheduled" })
    expect(mockRpc).toHaveBeenCalledWith("update_extracted_field", {
      p_call_id: "call-123",
      p_key: "appointment_datetime",
      p_value: "2026-04-01T10:00:00",
    })
  })

  it("returns 400 when rescheduled is missing appointmentDateTime", async () => {
    const req = makeRequest({ status: "rescheduled" })
    const res = await PATCH(req, makeContext("call-123"))

    expect(res.status).toBe(400)
    const json = await res.json()
    expect(json.error).toMatch(/appointmentDateTime/)
  })

  it("returns 400 for invalid status", async () => {
    const req = makeRequest({ status: "unknown_value" })
    const res = await PATCH(req, makeContext("call-123"))

    expect(res.status).toBe(400)
    const json = await res.json()
    expect(json.error).toMatch(/Invalid status/)
  })

  it("returns 400 for invalid JSON", async () => {
    const req = new Request("http://localhost/api/calls/test-call-id/booking-status", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: "not-json{{{",
    })
    const res = await PATCH(req, makeContext("call-123"))

    expect(res.status).toBe(400)
    const json = await res.json()
    expect(json.error).toBe("Invalid JSON")
  })
})
