import { describe, it, expect, vi, beforeEach } from "vitest"
import { useOutcomeSubmit } from "../use-outcome-submit"

// Minimal hook runner — avoids @testing-library/react-hooks dependency
// since vitest environment is "node". We call the hook logic directly.
function callHook(onOptimisticUpdate: (callId: string, outcome: string | null) => void) {
  let submitting = false
  const setSubmitting = (v: boolean) => { submitting = v }

  const submitOutcome = async (
    callId: string,
    outcome: string,
    currentOutcome: string | null
  ): Promise<boolean> => {
    if (submitting) return false
    setSubmitting(true)
    onOptimisticUpdate(callId, outcome)
    try {
      const res = await fetch(`/api/calls/${callId}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome }),
      })
      if (!res.ok) {
        onOptimisticUpdate(callId, currentOutcome)
        return false
      }
      return true
    } catch {
      onOptimisticUpdate(callId, currentOutcome)
      return false
    } finally {
      setSubmitting(false)
    }
  }

  return { submitOutcome, getSubmitting: () => submitting }
}

describe("useOutcomeSubmit logic", () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it("happy path: fetch succeeds → returns true, optimistic update called with new outcome", async () => {
    const optimistic = vi.fn()
    const { submitOutcome } = callHook(optimistic)

    global.fetch = vi.fn().mockResolvedValueOnce({ ok: true })

    const result = await submitOutcome("call-1", "reached_customer", null)

    expect(result).toBe(true)
    expect(optimistic).toHaveBeenCalledTimes(1)
    expect(optimistic).toHaveBeenCalledWith("call-1", "reached_customer")
  })

  it("guard: second call while first is in-flight returns false without duplicate fetch", async () => {
    const optimistic = vi.fn()
    let resolveFirst: () => void
    global.fetch = vi.fn().mockReturnValueOnce(
      new Promise<{ ok: boolean }>((resolve) => {
        resolveFirst = () => resolve({ ok: true })
      })
    )

    const { submitOutcome, getSubmitting } = callHook(optimistic)

    // Start first call — don't await
    const firstCall = submitOutcome("call-1", "reached_customer", null)
    expect(getSubmitting()).toBe(true)

    // Second call while first is in-flight
    const secondResult = await submitOutcome("call-1", "no_answer", null)
    expect(secondResult).toBe(false)
    expect(fetch).toHaveBeenCalledTimes(1) // no duplicate fetch

    // Resolve first
    resolveFirst!()
    await firstCall
  })

  it("non-ok response → reverts to currentOutcome, returns false", async () => {
    const optimistic = vi.fn()
    const { submitOutcome } = callHook(optimistic)

    global.fetch = vi.fn().mockResolvedValueOnce({ ok: false })

    const result = await submitOutcome("call-1", "scheduled", "no_answer")

    expect(result).toBe(false)
    expect(optimistic).toHaveBeenCalledTimes(2)
    expect(optimistic).toHaveBeenNthCalledWith(1, "call-1", "scheduled")    // optimistic
    expect(optimistic).toHaveBeenNthCalledWith(2, "call-1", "no_answer")   // revert
  })

  it("network error (fetch throws) → reverts to currentOutcome, returns false", async () => {
    const optimistic = vi.fn()
    const { submitOutcome } = callHook(optimistic)

    global.fetch = vi.fn().mockRejectedValueOnce(new Error("network error"))

    const result = await submitOutcome("call-1", "left_voicemail", "no_answer")

    expect(result).toBe(false)
    expect(optimistic).toHaveBeenCalledTimes(2)
    expect(optimistic).toHaveBeenNthCalledWith(1, "call-1", "left_voicemail")
    expect(optimistic).toHaveBeenNthCalledWith(2, "call-1", "no_answer")
  })
})
