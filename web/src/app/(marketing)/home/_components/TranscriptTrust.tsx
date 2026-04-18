import { MicroCta } from "./MicroCta"

/**
 * Feature Block 2 — transcript review / trust. Server component.
 * Layout: stacked. Transcript excerpt renders above the headline
 * as an evidence element (Pass 4 visual rhythm variance).
 */
export function TranscriptTrust() {
  return (
    <section
      id="transcript-trust"
      aria-labelledby="transcript-trust-h2"
      style={{
        padding: "clamp(64px, 10vw, 120px) 0",
        borderTop: "1px solid var(--mk-border)",
      }}
    >
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px" }}>
        {/* Transcript excerpt — visual anchor */}
        <div
          role="img"
          aria-label="Sample transcript excerpt from a CallLock rescued call, showing the AI handling a plumbing emergency intake and booking a slot"
          style={{
            maxWidth: "760px",
            margin: "0 auto 56px",
            backgroundColor: "rgba(0, 0, 0, 0.25)",
            border: "1px solid var(--mk-border)",
            borderRadius: "var(--mk-radius-md)",
            padding: "28px 32px",
            fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
            fontSize: "14px",
            lineHeight: 1.6,
            color: "var(--mk-fg-secondary)",
          }}
        >
          <div style={{ color: "var(--mk-fg-muted)", fontSize: "12px", marginBottom: "14px", letterSpacing: "0.08em" }}>
            CALL · 2:14 PM · ACTIVE LEAK · 1:42
          </div>
          <div><span style={{ color: "var(--mk-cream)" }}>Caller:</span> Hi, my kitchen sink is leaking everywhere, it&apos;s all over the floor —</div>
          <div style={{ marginTop: "8px" }}><span style={{ color: "var(--mk-accent)" }}>CallLock:</span> That sounds urgent. I can get Mike out to you today. What&apos;s the address?</div>
          <div style={{ marginTop: "8px" }}><span style={{ color: "var(--mk-cream)" }}>Caller:</span> 47 Oak Street. How long?</div>
          <div style={{ marginTop: "8px" }}><span style={{ color: "var(--mk-accent)" }}>CallLock:</span> I&apos;ve got you booked for 3:30 today. Diagnostic is $150, applied to any repair. I&apos;ll text the confirmation to this number.</div>
          <div style={{ marginTop: "14px", color: "var(--mk-fg-muted)", fontSize: "12px" }}>— booked to Google Calendar at 2:16 PM —</div>
        </div>

        <h2 id="transcript-trust-h2" style={{ maxWidth: "18ch", marginInline: "auto", textAlign: "center" }}>
          Pull up any call. Read the transcript. Sleep fine.
        </h2>
        <p
          style={{
            marginTop: "28px",
            maxWidth: "var(--mk-measure)",
            marginInline: "auto",
            fontSize: "17px",
            lineHeight: 1.6,
            color: "var(--mk-fg-secondary)",
          }}
        >
          The #1 reason contractors hesitate on voice AI is &quot;what if it
          screws up a customer?&quot; Fair question. So we let you pull up any
          rescued call, read the full transcript, and hear the audio — same
          day, no support ticket. And because CallLock only touches the calls
          you would have missed anyway, the downside of an imperfect call is a
          call you weren&apos;t going to get at all.
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
            marginInline: "auto",
            color: "var(--mk-fg-secondary)",
            fontSize: "16px",
            lineHeight: 1.55,
          }}
        >
          <li>
            Full transcripts and recordings of every call CallLock handles —
            searchable, timestamped
          </li>
          <li>
            See exactly what the AI said, how the caller responded, and which
            slot got booked
          </li>
          {/* TODO(D4): "flag + retrain" feature pulled pending product confirmation that this actually exists. */}
          <li>
            Every call is reviewable the same day — no support ticket, no delay
          </li>
          <li>
            Predictable flat monthly price — not a per-minute bill that spikes
            in your busy season
          </li>
        </ul>
        <div style={{ marginTop: "24px", textAlign: "center" }}>
          <MicroCta href="#audit" ariaLabel="See a real transcript from a sample audit">
            See a real transcript
          </MicroCta>
        </div>
      </div>
    </section>
  )
}
