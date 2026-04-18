import type { ReactNode } from "react"
import { Space_Grotesk } from "next/font/google"

/**
 * Marketing route group layout.
 *
 * Scopes Wise-inspired tokens and the display font to the .marketing
 * wrapper only, so the Mail app at / continues to use its own dark
 * workspace tokens without leakage.
 *
 * Display font: Space Grotesk as the founder-guess editorial alternative
 * to Wise's real brand face. Swap to next/font/local with the real woff2
 * once the user runs `npx getdesign@latest add wise` and DESIGN.md lands.
 * Rule from /plan-design-review: never fall back to Inter for display.
 */
const displayFont = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "700"],
  variable: "--mk-font-display",
  display: "swap",
})

export default function MarketingLayout({
  children,
}: Readonly<{
  children: ReactNode
}>) {
  return (
    <div className={`marketing ${displayFont.variable}`}>
      {children}
    </div>
  )
}
