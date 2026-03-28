import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("server-only", () => ({}))
vi.mock("@/lib/supabase-server", () => ({
  createServerClient: vi.fn(),
}))

import { GET } from "../route"
import { createServerClient } from "@/lib/supabase-server"

const mockOrder = vi.fn()
const mockEq = vi.fn()
const mockSelect = vi.fn()
const mockFrom = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  mockOrder.mockResolvedValue({
    data: [
      {
        id: "touch-1",
        call_id: "call-123",
        outcome: "left_voicemail",
        created_at: "2026-03-27T10:00:00.000Z",
      },
    ],
    error: null,
  })
  const mockEq2 = vi.fn().mockReturnValue({ order: mockOrder })
  mockEq.mockReturnValue({ eq: mockEq2 })
  mockSelect.mockReturnValue({ eq: mockEq })
  mockFrom.mockReturnValue({ select: mockSelect })
  ;(createServerClient as ReturnType<typeof vi.fn>).mockReturnValue({
    from: mockFrom,
  })
})

function makeContext(callId: string) {
  return { params: Promise.resolve({ callId }) }
}

describe("GET /api/calls/[callId]/touches", () => {
  it("returns normalized callback touches", async () => {
    const req = new Request("http://localhost/api/calls/call-123/touches")
    const res = await GET(req, makeContext("call-123"))
    const json = await res.json()

    expect(res.status).toBe(200)
    expect(json).toEqual({
      touches: [
        {
          id: "touch-1",
          callId: "call-123",
          outcome: "left_voicemail",
          createdAt: "2026-03-27T10:00:00.000Z",
        },
      ],
    })
  })
})
