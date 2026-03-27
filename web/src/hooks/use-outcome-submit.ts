import { useState, useCallback } from "react"
import type { CallbackOutcome } from "@/types/call"

interface UseOutcomeSubmitResult {
  submitOutcome: (
    callId: string,
    outcome: CallbackOutcome,
    currentOutcome: CallbackOutcome | null
  ) => Promise<boolean>
  submitting: boolean
}

export function useOutcomeSubmit(
  onOptimisticUpdate: (callId: string, outcome: CallbackOutcome | null) => void
): UseOutcomeSubmitResult {
  const [submitting, setSubmitting] = useState(false)

  const submitOutcome = useCallback(
    async (
      callId: string,
      outcome: CallbackOutcome,
      currentOutcome: CallbackOutcome | null
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
    },
    [submitting, onOptimisticUpdate]
  )

  return { submitOutcome, submitting }
}
