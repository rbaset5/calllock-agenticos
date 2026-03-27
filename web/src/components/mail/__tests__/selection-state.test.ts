import { describe, expect, it } from "vitest"

import {
  getInitialSelectedId,
  resolveStoredSelectedId,
} from "../selection-state"

describe("selection-state", () => {
  const calls = [{ id: "a" }, { id: "b" }, { id: "c" }]

  it("picks first call as deterministic initial selection", () => {
    expect(getInitialSelectedId(calls)).toBe("a")
    expect(getInitialSelectedId([])).toBeNull()
  })

  it("accepts stored id only when present in current calls", () => {
    expect(resolveStoredSelectedId(calls, "b")).toBe("b")
    expect(resolveStoredSelectedId(calls, "missing")).toBeNull()
    expect(resolveStoredSelectedId(calls, null)).toBeNull()
  })
})
