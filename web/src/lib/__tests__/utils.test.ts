import { describe, it, expect } from "vitest"
import { getUrgencyVariant } from "../utils"

describe("getUrgencyVariant", () => {
  it("returns destructive for LifeSafety", () => {
    expect(getUrgencyVariant("LifeSafety")).toBe("destructive")
  })

  it("returns destructive for Urgent", () => {
    expect(getUrgencyVariant("Urgent")).toBe("destructive")
  })

  it("returns outline for Estimate", () => {
    expect(getUrgencyVariant("Estimate")).toBe("outline")
  })

  it("returns secondary for Routine", () => {
    expect(getUrgencyVariant("Routine")).toBe("secondary")
  })

  it("returns secondary for unknown values", () => {
    expect(getUrgencyVariant("something_else")).toBe("secondary")
  })
})
