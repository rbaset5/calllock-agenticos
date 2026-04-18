"use client"

import { useEffect, useRef, useState } from "react"
import { motion, useInView, useMotionValue, useTransform, animate } from "framer-motion"

/**
 * ROI math sidebar — count-up animation runs ONCE when the sidebar
 * enters the viewport, then never replays. Uses framer-motion's
 * useInView + animate with { once: true }.
 *
 * At <1024px this renders as a full-bleed band ABOVE the feature
 * body (see VoicemailFilter for placement). At ≥1024px it sits
 * beside the feature body text at ~40% width.
 *
 * prefers-reduced-motion is handled by the global .marketing rule
 * in globals.css — the count-up reaches its final value instantly
 * because transition-duration is forced to 0.001ms.
 */

function CountUp({ value, prefix = "$", suffix = "" }: { value: number; prefix?: string; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: "-10% 0px" })
  const count = useMotionValue(0)
  const rounded = useTransform(count, (latest) => Math.round(latest).toLocaleString("en-US"))
  const [display, setDisplay] = useState("0")

  useEffect(() => {
    if (!inView) return
    const controls = animate(count, value, { duration: 0.8, ease: "easeOut" })
    const unsub = rounded.on("change", (v) => setDisplay(v))
    return () => {
      controls.stop()
      unsub()
    }
  }, [inView, value, count, rounded])

  return (
    <span
      ref={ref}
      style={{ fontVariantNumeric: "tabular-nums" }}
      aria-label={`${prefix}${value.toLocaleString("en-US")}${suffix}`}
    >
      {prefix}
      {display}
      {suffix}
    </span>
  )
}

export function RoiSidebar() {
  return (
    <aside
      className="mk-roi-sidebar"
      aria-label="Missed-call revenue math"
      style={{
        backgroundColor: "rgba(0, 0, 0, 0.25)",
        border: "1px solid var(--mk-border)",
        borderRadius: "var(--mk-radius-md)",
        padding: "32px 28px",
        color: "var(--mk-fg-primary)",
      }}
    >
      <div
        style={{
          fontSize: "13px",
          fontWeight: 600,
          color: "var(--mk-cream)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          marginBottom: "18px",
        }}
      >
        Say you get 3 voicemails a day.
      </div>
      <p
        style={{
          fontSize: "15px",
          lineHeight: 1.55,
          color: "var(--mk-fg-secondary)",
          marginBottom: "24px",
        }}
      >
        Industry call-tracking estimates say 30–50% of people who reach voicemail
        don&apos;t leave a message — especially on urgent calls. So your 3 voicemails
        probably represent about <strong style={{ color: "var(--mk-fg-primary)" }}>5
        actual missed calls a day — 3 you see, 2 you don&apos;t</strong>.
      </p>
      <p
        style={{
          fontSize: "15px",
          lineHeight: 1.55,
          color: "var(--mk-fg-secondary)",
          marginBottom: "24px",
        }}
      >
        At a $400 average ticket and a conservative 20% close rate on new customers:
      </p>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          borderTop: "1px solid var(--mk-border)",
          paddingTop: "24px",
        }}
      >
        <div>
          <div
            className="mk-display"
            style={{
              fontSize: "clamp(36px, 4vw, 56px)",
              fontWeight: 700,
              lineHeight: 1,
              color: "var(--mk-accent)",
            }}
          >
            <motion.div>~<CountUp value={8000} />/mo</motion.div>
          </div>
          <div style={{ fontSize: "13px", color: "var(--mk-fg-muted)", marginTop: "6px" }}>
            walking to voicemail — floor estimate
          </div>
        </div>
        <div>
          <div
            className="mk-display"
            style={{
              fontSize: "clamp(36px, 4vw, 56px)",
              fontWeight: 700,
              lineHeight: 1,
              color: "var(--mk-cream)",
            }}
          >
            <motion.div>~<CountUp value={12000} />/mo</motion.div>
          </div>
          <div style={{ fontSize: "13px", color: "var(--mk-fg-muted)", marginTop: "6px" }}>
            at a 30% close rate — more realistic for most shops
          </div>
        </div>
      </div>

      <p
        style={{
          marginTop: "24px",
          fontSize: "12px",
          color: "var(--mk-fg-muted)",
          fontStyle: "italic",
        }}
      >
        These are floor estimates. We&apos;ll do the real math on your actual
        numbers in 15 minutes.
      </p>
    </aside>
  )
}
