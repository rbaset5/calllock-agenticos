/**
 * Final CTA — the audit section. Server component. Single button.
 * Risk reversal line below. This section IS #audit — every CTA
 * on the page anchors here.
 */
export function FinalCta() {
  return (
    <section
      id="audit"
      aria-labelledby="final-cta-h2"
      style={{
        padding: "clamp(96px, 14vw, 160px) 0",
        borderTop: "1px solid var(--mk-border)",
      }}
    >
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "0 24px",
          textAlign: "center",
        }}
      >
        <h2 id="final-cta-h2" style={{ maxWidth: "18ch", marginInline: "auto" }}>
          See what you&apos;re losing this month.
        </h2>
        <p
          style={{
            marginTop: "32px",
            maxWidth: "52ch",
            marginInline: "auto",
            fontSize: "18px",
            lineHeight: 1.55,
            color: "var(--mk-fg-secondary)",
          }}
        >
          15 minutes. Your numbers. A real dollar figure on what&apos;s walking
          away. We&apos;ll take three inputs — your voicemail count, your
          ticket size, your close rate — and show you the calls you don&apos;t
          even know you&apos;re missing. No deck. No demo. Just the math.
        </p>

        <div style={{ marginTop: "44px" }}>
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
            Book My Missed-Call Audit <span aria-hidden="true">▸</span>
          </a>
        </div>

        {/* TODO(D2, D3): restore "Auto-forwards from your existing line — no new
            number" and "Cancel anytime, keep every booking" once product
            confirms carrier mechanic and commercial terms. */}
        <p
          style={{
            marginTop: "32px",
            fontSize: "14px",
            color: "var(--mk-fg-muted)",
          }}
        >
          Live in 72 hours. Flat monthly price. No per-minute surprises.
        </p>
      </div>
    </section>
  )
}
