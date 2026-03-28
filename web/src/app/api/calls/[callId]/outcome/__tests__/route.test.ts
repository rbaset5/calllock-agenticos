import { describe, it, expect, vi, beforeEach } from "vitest"

// Mock server-only before any imports that pull it in
vi.mock("server-only", () => ({}))

// Mock createServerClient so Supabase is never initialized
vi.mock("@/lib/supabase-server", () => ({
  createServerClient: vi.fn(),
}))

import { PATCH } from "../route"
import { createServerClient } from "@/lib/supabase-server"

const mockUpdate = vi.fn()
const mockEq = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  const mockEq2 = vi.fn().mockResolvedValue({ error: null })
  mockEq.mockReturnValue({ eq: mockEq2 })
  mockUpdate.mockReturnValue({ eq: mockEq })
  ;(createServerClient as ReturnType<typeof vi.fn>).mockReturnValue({
    from: vi.fn().mockReturnValue({ update: mockUpdate }),
  })
})

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/calls/test-call-id/outcome", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

function makeContext(callId: string) {
  return { params: Promise.resolve({ callId }) }
}

describe("PATCH /api/calls/[callId]/outcome", () => {
  it("returns 200 for valid outcome", async () => {
    const req = makeRequest({ outcome: "reached_customer" })
    const res = await PATCH(req, makeContext("call-123"))

    expect(res.status).toBe(200)
    const json = await res.json()
    expect(json).toMatchObject({ ok: true, outcome: "reached_customer" })
    expect(typeof json.touchedAt).toBe("string")
  })

  it("returns 400 for invalid outcome", async () => {
    const req = makeRequest({ outcome: "invalid_value" })
    const res = await PATCH(req, makeContext("call-123"))

    expect(res.status).toBe(400)
    const json = await res.json()
    expect(json.error).toMatch(/Invalid outcome/)
  })

  it("returns 400 for missing body", async () => {
    const req = new Request("http://localhost/api/calls/test-call-id/outcome", {
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
