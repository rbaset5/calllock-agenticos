import { RoiSidebar } from "./RoiSidebar"
import { MicroCta } from "./MicroCta"

/**
 * Feature Block 1 — voicemail filter reframe + ROI math sidebar.
 * Server component. Layout: text-left / ROI-right at ≥1024px,
 * ROI full-bleed BAND above body at <1024px (see mk-block-1 CSS).
 */
export function VoicemailFilter() {
  return (
    <section
      id="voicemail-filter"
      aria-labelledby="voicemail-filter-h2"
      style={{
        padding: "clamp(64px, 10vw, 120px) 0",
        borderTop: "1px solid var(--mk-border)",
      }}
    >
      <div
        className="mk-block-1"
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "0 24px",
          display: "grid",
          gap: "48px",
        }}
      >
        <div className="mk-block-1-body">
          <h2 id="voicemail-filter-h2" style={{ maxWidth: "16ch" }}>
            If they had time to leave a voicemail, it wasn&apos;t urgent.
          </h2>
          <p
            style={{
              marginTop: "28px",
              maxWidth: "var(--mk-measure)",
              fontSize: "17px",
              lineHeight: 1.6,
              color: "var(--mk-fg-secondary)",
            }}
          >
            Most contractors measure missed calls by counting voicemails. That
            only counts the patient callers. The ones who matter most — the
            emergencies, the I-need-someone-today jobs, the $3,000 installs —
            hang up in 10 seconds and call the next shop. You never see them in
            your voicemail inbox. They never existed, as far as you know.
            CallLock catches them.
          </p>
          <ul
            style={{
              marginTop: "28px",
              listStyle: "none",
              padding: 0,
              display: "flex",
              flexDirection: "column",
              gap: "14px",
              maxWidth: "var(--mk-measure)",
              color: "var(--mk-fg-secondary)",
              fontSize: "16px",
              lineHeight: 1.55,
            }}
          >
            {/* TODO(D2): confirm carrier mechanic. Unverified claim pulled pending product confirmation. */}
            <li>
              Forwards to CallLock the moment your phone doesn&apos;t pick up —
              you keep answering everything you want
            </li>
            <li>
              Picks up right where your voicemail would have — 24/7, every day
              of the year
            </li>
            <li>
              Books directly to your Google Calendar or iCal — real bookings,
              not message pads
            </li>
            <li>
              Catches the impatient callers who hang up before the beep — the
              ones you don&apos;t even know about
            </li>
          </ul>
          <div style={{ marginTop: "24px" }}>
            <MicroCta href="#audit" ariaLabel="See a sample missed-call audit">
              See a sample audit
            </MicroCta>
          </div>
        </div>

        <div className="mk-block-1-sidebar">
          <RoiSidebar />
        </div>
      </div>
    </section>
  )
}
