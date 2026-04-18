/**
 * Minimal footer — no menu, no link tree. Category phrase + legal.
 * The page is short enough that scroll navigation IS the navigation.
 */
export function MarketingFooter() {
  return (
    <footer
      style={{
        padding: "48px 0",
        borderTop: "1px solid var(--mk-border)",
      }}
    >
      <div
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "0 24px",
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          gap: "16px",
          fontSize: "13px",
          color: "var(--mk-fg-muted)",
        }}
      >
        <div>Missed-call revenue recovery for contractors.</div>
        <div>© {new Date().getFullYear()} CallLock</div>
      </div>
    </footer>
  )
}
