"use client"

import type { ReactNode } from "react"
import { motion } from "framer-motion"

/**
 * Hero layout — client component to host framer-motion stagger.
 * Children are passed FROM the server page so the H1 and body copy
 * ship as raw HTML on first paint (LCP ≤2.0s target, see plan
 * Performance contract).
 *
 * Layout: text-left / SMS mock anchored right at ≥1024px, stacked
 * (text above mock) below 1024px.
 */

interface HeroProps {
  headline: ReactNode
  subhead: ReactNode
  cta: ReactNode
  supportingLine: ReactNode
  trustStrip: ReactNode
  sms: ReactNode
}

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (delay: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, delay, ease: [0.2, 0.7, 0.2, 1] as const },
  }),
}

export function Hero({
  headline,
  subhead,
  cta,
  supportingLine,
  trustStrip,
  sms,
}: HeroProps) {
  return (
    <section
      aria-labelledby="hero-headline"
      style={{
        minHeight: "100dvh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        paddingTop: "56px", /* nav height */
      }}
    >
      <div
        style={{
          flex: 1,
          maxWidth: "1200px",
          width: "100%",
          margin: "0 auto",
          padding: "48px 24px 24px",
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr)",
          gap: "48px",
          alignItems: "end",
        }}
        className="mk-hero-grid"
      >
        <div style={{ maxWidth: "760px" }}>
          <motion.h1
            id="hero-headline"
            initial="hidden"
            animate="show"
            variants={fadeUp}
            custom={0}
          >
            {headline}
          </motion.h1>

          <motion.p
            initial="hidden"
            animate="show"
            variants={fadeUp}
            custom={0.1}
            style={{
              marginTop: "28px",
              maxWidth: "34ch",
              fontSize: "clamp(18px, 2vw, 22px)",
              lineHeight: 1.45,
              color: "var(--mk-fg-secondary)",
            }}
          >
            {subhead}
          </motion.p>

          <motion.div
            initial="hidden"
            animate="show"
            variants={fadeUp}
            custom={0.2}
            style={{ marginTop: "36px" }}
          >
            {cta}
            <div
              style={{
                marginTop: "16px",
                fontSize: "14px",
                color: "var(--mk-fg-muted)",
                maxWidth: "42ch",
              }}
            >
              {supportingLine}
            </div>
          </motion.div>
        </div>

        <motion.div
          initial="hidden"
          animate="show"
          variants={fadeUp}
          custom={0.35}
          style={{ justifySelf: "end", width: "100%", display: "flex", justifyContent: "flex-end" }}
          className="mk-hero-sms"
        >
          {sms}
        </motion.div>
      </div>

      <div
        style={{
          maxWidth: "1200px",
          width: "100%",
          margin: "0 auto",
          padding: "20px 24px 32px",
          borderTop: "1px solid var(--mk-border)",
          fontSize: "13px",
          color: "var(--mk-fg-muted)",
        }}
      >
        {trustStrip}
      </div>
    </section>
  )
}
