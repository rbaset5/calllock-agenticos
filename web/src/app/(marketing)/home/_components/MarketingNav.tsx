"use client"

import { useEffect, useState } from "react"

/**
 * Sticky marketing nav — transparent over hero, solid dark-green
 * background after 120px scroll. Single wordmark + single CTA.
 * Client component only because it needs the scroll listener.
 */
export function MarketingNav() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 120)
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        height: "56px",
        backgroundColor: scrolled ? "var(--mk-bg-field)" : "transparent",
        borderBottom: scrolled
          ? "1px solid var(--mk-border)"
          : "1px solid transparent",
        transition: "background-color 200ms ease, border-color 200ms ease",
      }}
    >
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "0 24px",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <a
          href="/home"
          aria-label="CallLock home"
          className="mk-display"
          style={{
            fontSize: "18px",
            fontWeight: 500,
            color: "var(--mk-fg-primary)",
            textDecoration: "none",
            letterSpacing: "-0.01em",
          }}
        >
          calllock
        </a>
        <a
          href="#audit"
          className="mk-button"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            height: "40px",
            padding: "0 18px",
            borderRadius: "var(--mk-radius-sm)",
            border: "1px solid var(--mk-accent)",
            color: "var(--mk-accent)",
            fontSize: "14px",
            fontWeight: 600,
            textDecoration: "none",
            transition: "background-color 150ms ease, color 150ms ease",
          }}
        >
          Book Audit <span aria-hidden="true">▸</span>
        </a>
      </div>
    </header>
  )
}
