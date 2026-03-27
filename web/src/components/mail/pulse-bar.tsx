"use client"

import { useCallback } from "react"

interface PulseBarProps {
  escalated: number
  leads: number
  followUps: number
  booked: number
  otherHandled: number
  onScrollTo?: (section: "escalated" | "leads" | "followUps" | "booked" | "otherHandled") => void
}

export function PulseBar({ escalated, leads, followUps, booked, onScrollTo }: PulseBarProps) {
  const handleClick = useCallback(
    (section: "escalated" | "leads" | "followUps" | "booked" | "otherHandled") => {
      onScrollTo?.(section)
    },
    [onScrollTo]
  )

  const segments: { label: string; count: number; section: "escalated" | "leads" | "followUps" | "booked" | "otherHandled"; danger?: boolean }[] = []

  if (escalated > 0) segments.push({ label: "urgent escalations", count: escalated, section: "escalated", danger: true })
  if (leads > 0) segments.push({ label: "calls needing you", count: leads, section: "leads" })
  if (followUps > 0) segments.push({ label: "follow-ups", count: followUps, section: "followUps" })
  if (booked > 0) segments.push({ label: "booked by AI", count: booked, section: "booked" })

  if (segments.length === 0) {
    return (
      <div className="bg-[#000000] py-3 px-4" aria-live="polite">
        <p className="text-[#acabaa] text-[0.6875rem] font-semibold tracking-[0.08em] uppercase">
          No calls yet
        </p>
      </div>
    )
  }

  return (
    <div
      className="bg-[#000000] py-3 px-4 flex flex-wrap items-center gap-x-1 min-h-[44px]"
      aria-live="polite"
    >
      {segments.map((seg, i) => (
        <span key={seg.section} className="flex items-center">
          {i > 0 && (
            <span className="text-[#acabaa] text-[0.6875rem] mx-1 select-none" aria-hidden>·</span>
          )}
          <button
            onClick={() => handleClick(seg.section)}
            className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase transition-colors duration-150 active:text-[#e7e5e4] min-h-[44px] flex items-center"
          >
            <span className={seg.danger ? "text-cl-danger" : "text-[#e7e5e4]"}>{seg.count}</span>
            <span className="text-[#acabaa] ml-1">{seg.label}</span>
          </button>
        </span>
      ))}
    </div>
  )
}
