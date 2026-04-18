import { SmsMock } from "./SmsMock"
import { MicroCta } from "./MicroCta"

/**
 * Feature Block 3 — spouse / overflow. Quietest section on the page
 * by design (see design review § journey storyboard — the spouse line
 * is the emotional peak; don't sell it, let it land).
 *
 * Server component. Layout: evidence-LEFT (SMS mock) / text-RIGHT at
 * ≥1024px — flips the rhythm from block 1.
 */
export function OverflowHandoff() {
  return (
    <section
      id="overflow-handoff"
      aria-labelledby="overflow-handoff-h2"
      style={{
        padding: "clamp(64px, 10vw, 120px) 0",
        borderTop: "1px solid var(--mk-border)",
      }}
    >
      <div
        className="mk-block-3"
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "0 24px",
          display: "grid",
          gap: "48px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "center" }}>
          <SmsMock scenario="after-hours-overflow" />
        </div>
        <div>
          <h2 id="overflow-handoff-h2" style={{ maxWidth: "16ch" }}>
            Hand off the overflow without hiring anyone.
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
            Right now, when you can&apos;t get to the phone, your spouse does.
            Between jobs. During dinner. On weekends. CallLock takes <em>just</em>
            {" "}that overflow off their plate for less than a part-timer — and
            unlike a part-timer, it works at 2am, doesn&apos;t quit, and
            doesn&apos;t resent your family for it. You still answer what you
            want. They stop being unpaid dispatch.
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
            <li>
              Every rescued call lands on your phone as a 30-second SMS —
              caller name, problem, urgency, booked slot
            </li>
            <li>
              Emergency calls (active leak, no heat, no power) trigger an
              immediate phone alert; routine jobs just text you
            </li>
            <li>
              Spam, SEO pitches, and robocalls get filtered before they ever
              hit your SMS
            </li>
            <li>
              Done-for-you setup in under 72 hours — you don&apos;t touch a
              config screen
            </li>
          </ul>
          <div style={{ marginTop: "24px" }}>
            <MicroCta href="#audit" ariaLabel="See a sample SMS notification">
              See a sample SMS
            </MicroCta>
          </div>
        </div>
      </div>
    </section>
  )
}
