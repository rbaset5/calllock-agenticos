import type { Metadata } from "next"
import { MarketingNav } from "./_components/MarketingNav"
import { Hero } from "./_components/Hero"
import { SmsMock } from "./_components/SmsMock"
import { VoicemailFilter } from "./_components/VoicemailFilter"
import { TranscriptTrust } from "./_components/TranscriptTrust"
import { OverflowHandoff } from "./_components/OverflowHandoff"
import { FinalCta } from "./_components/FinalCta"
import { MarketingFooter } from "./_components/MarketingFooter"

export const metadata: Metadata = {
  title: "CallLock — Missed-Call Revenue Recovery for Home Services Contractors",
  description:
    "Stop losing HVAC, plumbing, and electrical jobs to voicemail. CallLock answers every call you can't — 24/7 — and books the job straight to your calendar.",
}

/**
 * Marketing homepage — server component composition.
 *
 * Every block of copy is passed as server-rendered children into the
 * Hero client island so the H1 ships as raw HTML on first paint
 * (LCP ≤ 2.0s target). Only Hero, RoiSidebar (inside VoicemailFilter),
 * and MarketingNav are client components; everything else renders
 * statically.
 *
 * Every CTA anchors to #audit which is the FinalCta section id.
 */
export default function HomePage() {
  return (
    <main>
      <MarketingNav />

      <Hero
        headline={<>Stop losing jobs to voicemail.</>}
        subhead={
          <>
            When your cell goes to voicemail — on the job, at dinner, at 2am
            — CallLock picks up 24/7, books the job, and texts you the
            details in 30 seconds. You keep every call you want.
          </>
        }
        cta={
          <a
            href="#audit"
            className="mk-button mk-button-primary mk-display"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "10px",
              height: "56px",
              padding: "0 32px",
              borderRadius: "var(--mk-radius-sm)",
              fontSize: "17px",
              fontWeight: 700,
              textDecoration: "none",
              letterSpacing: "-0.01em",
            }}
          >
            Get My Missed-Call Audit <span aria-hidden="true">▸</span>
          </a>
        }
        supportingLine={
          <>
            Missed-call revenue recovery for contractors. One recovered job a
            month pays for CallLock.
          </>
        }
        trustStrip={
          <>
            Built for <strong style={{ color: "var(--mk-fg-secondary)" }}>US</strong>{" "}
            HVAC, plumbing, electrical, garage door, drain, and water treatment
            shops — 1–5 trucks, live in 72 hours.
          </>
        }
        sms={<SmsMock scenario="active-leak-hero" />}
      />

      <VoicemailFilter />
      <TranscriptTrust />
      <OverflowHandoff />
      <FinalCta />
      <MarketingFooter />
    </main>
  )
}
