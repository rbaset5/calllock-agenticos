/**
 * SMS notification mock — shared visual used by the hero and the
 * Overflow feature block. Server component, zero JS shipped.
 *
 * Renders as a believable iOS-style notification card, NOT a phone chrome.
 * The brand promise ("texts you the details in 30 seconds") lands best
 * when the visual reads like a real text the buyer could have just gotten.
 *
 * role="img" + aria-label makes the proof element accessible to screen
 * readers as a single unit (Pass 6 a11y spec).
 *
 * Scenarios are hardcoded content objects. Unknown scenario throws so
 * type mismatches fail loud at build time rather than rendering silently.
 */

type Scenario = "active-leak-hero" | "after-hours-overflow" | "no-heat-weekend"

interface SmsMockProps {
  scenario: Scenario
}

const SCENARIOS: Record<Scenario, {
  time: string
  caller: string
  problem: string
  urgency: string
  slot: string
}> = {
  "active-leak-hero": {
    time: "2:14 pm",
    caller: "Maria D. · (512) 555-0182",
    problem: "Active leak under kitchen sink, pooling on floor",
    urgency: "Emergency — water damage risk",
    slot: "Today 3:30 pm · $150 diagnostic",
  },
  "after-hours-overflow": {
    time: "11:47 pm",
    caller: "Jared B. · (512) 555-0144",
    problem: "Tankless water heater, no hot water",
    urgency: "Next-day — not urgent tonight",
    slot: "Tomorrow 9:00 am · 7-9 am window",
  },
  "no-heat-weekend": {
    time: "Sat 6:08 am",
    caller: "Amy R. · (512) 555-0169",
    problem: "Furnace not kicking on, 58°F inside",
    urgency: "Urgent — no heat",
    slot: "Today 8:30 am · $95 service call",
  },
}

export function SmsMock({ scenario }: SmsMockProps) {
  const data = SCENARIOS[scenario]
  if (!data) {
    throw new Error(`SmsMock: unknown scenario "${scenario}"`)
  }

  const ariaLabel = `Text message from CallLock at ${data.time}. ${data.caller}. ${data.problem}. ${data.urgency}. Booked ${data.slot}.`

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      className="mk-sms-mock"
      style={{
        width: "min(360px, 100%)",
        backgroundColor: "rgba(255, 255, 255, 0.06)",
        border: "1px solid var(--mk-border)",
        borderRadius: "var(--mk-radius-md)",
        padding: "18px 20px",
        backdropFilter: "blur(8px)",
        fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
        color: "var(--mk-fg-primary)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "12px",
          color: "var(--mk-fg-muted)",
          marginBottom: "10px",
          letterSpacing: "0.02em",
        }}
      >
        <span>CallLock</span>
        <span>{data.time}</span>
      </div>
      <div style={{ fontSize: "14px", fontWeight: 600, marginBottom: "4px" }}>
        New job booked
      </div>
      <div
        style={{
          fontSize: "15px",
          lineHeight: 1.45,
          color: "var(--mk-fg-secondary)",
        }}
      >
        <div>{data.caller}</div>
        <div style={{ marginTop: "6px" }}>{data.problem}</div>
        <div
          style={{
            marginTop: "10px",
            fontSize: "13px",
            color: "var(--mk-cream)",
          }}
        >
          {data.urgency}
        </div>
        <div
          style={{
            marginTop: "14px",
            paddingTop: "12px",
            borderTop: "1px solid var(--mk-border)",
            fontSize: "14px",
            color: "var(--mk-fg-primary)",
          }}
        >
          {data.slot}
        </div>
      </div>
    </div>
  )
}
