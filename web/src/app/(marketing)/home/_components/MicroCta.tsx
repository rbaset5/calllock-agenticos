/**
 * Micro-CTA (arrow link) — "See a sample audit →" style.
 * Server component with CSS-only hover, zero JS.
 */

interface MicroCtaProps {
  children: React.ReactNode
  href: string
  ariaLabel: string
}

export function MicroCta({ children, href, ariaLabel }: MicroCtaProps) {
  return (
    <a
      href={href}
      aria-label={ariaLabel}
      className="mk-micro-cta"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "8px",
        color: "var(--mk-cream)",
        textDecoration: "none",
        fontSize: "15px",
        fontWeight: 500,
        paddingBlock: "8px",
      }}
    >
      <span style={{ textDecoration: "underline", textUnderlineOffset: "4px" }}>
        {children}
      </span>
      <span aria-hidden="true" className="mk-micro-cta-arrow">
        →
      </span>
    </a>
  )
}
