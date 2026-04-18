/**
 * Root layout contract test.
 *
 * Enforces that src/app/layout.tsx stays minimal after the route group refactor:
 * no h-screen, no overflow-hidden, no hardcoded `.dark` class on <html>.
 * Those concerns belong in src/app/(app)/layout.tsx instead.
 *
 * Required by /plan-eng-review iron rule for regressions — a single failed
 * regex here catches the class of refactor that would re-break the marketing
 * route's scroll behavior.
 */
import { readFileSync } from "fs"
import { resolve } from "path"
import { describe, it, expect } from "vitest"

const ROOT_LAYOUT = resolve(__dirname, "../layout.tsx")

describe("root layout contract", () => {
  const contents = readFileSync(ROOT_LAYOUT, "utf-8")

  it("does not hardcode className='dark' on <html>", () => {
    expect(contents).not.toMatch(/<html[^>]*className=["']dark["']/)
  })

  it("does not put h-screen on <body>", () => {
    expect(contents).not.toMatch(/<body[^>]*h-screen/)
  })

  it("does not put overflow-hidden on <body>", () => {
    expect(contents).not.toMatch(/<body[^>]*overflow-hidden/)
  })

  it("does not hardcode Mail app background color on <body>", () => {
    // #0e0e0e belongs to (app)/layout.tsx wrapper div, not the root body
    expect(contents).not.toMatch(/<body[^>]*#0e0e0e/)
  })

  it("still loads the font variables", () => {
    expect(contents).toMatch(/geistSans\.variable/)
    expect(contents).toMatch(/manrope\.variable/)
  })

  it("still renders the Toaster", () => {
    expect(contents).toMatch(/<Toaster/)
  })
})
