import { getDefaultSelectedId } from "@/lib/mail-sections"
import type { TriageableCall } from "@/lib/triage"

export function getInitialSelectedId(
  calls: ReadonlyArray<TriageableCall>
): string | null {
  return getDefaultSelectedId([...calls])
}

interface SelectableCall {
  id: string
}

export function resolveStoredSelectedId(
  calls: ReadonlyArray<SelectableCall>,
  storedId: string | null
): string | null {
  if (!storedId) return null
  return calls.some((call) => call.id === storedId) ? storedId : null
}
