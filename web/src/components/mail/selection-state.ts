interface SelectableCall {
  id: string
}

export function getInitialSelectedId(
  calls: ReadonlyArray<SelectableCall>
): string | null {
  return calls[0]?.id ?? null
}

export function resolveStoredSelectedId(
  calls: ReadonlyArray<SelectableCall>,
  storedId: string | null
): string | null {
  if (!storedId) return null
  return calls.some((call) => call.id === storedId) ? storedId : null
}
