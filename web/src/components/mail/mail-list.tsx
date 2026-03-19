"use client"

import type { Call, UrgencyTier } from "@/types/call"

interface MailListProps {
  items: Call[]
  selected: string | null
  onSelect: (id: string) => void
}

function urgencyToTag(urgency: UrgencyTier): string {
  switch (urgency) {
    case "LifeSafety": return "urgent"
    case "Urgent": return "needs-review"
    case "Routine": return "routine"
    case "Estimate": return "estimate"
  }
}

export function MailList({ items, selected, onSelect }: MailListProps) {
  return (
    <div className="flex-1 overflow-y-auto px-3 pb-3 flex flex-col gap-2">
      {items.map((item) => {
        const isSelected = selected === item.id
        const subject = item.problemDescription
          ? item.problemDescription.substring(0, 60)
          : item.hvacIssueType || "Missed call"

        return (
          <div
            key={item.id}
            onClick={() => onSelect(item.id)}
            className={
              isSelected
                ? "rounded-lg p-3 cursor-pointer transition-colors bg-[#1e1e1e] border border-[#3a3a3a] ring-1 ring-[#444]/50"
                : "rounded-lg p-3 cursor-pointer transition-colors bg-[#181818] border border-[#242424] hover:bg-[#1e1e1e]"
            }
          >
            <p className="text-sm font-semibold text-[#f0f0f0] leading-tight">
              {item.customerName || item.customerPhone || "Unknown Caller"}
            </p>
            <p className="text-xs text-[#777] mt-0.5 truncate">{subject}</p>
            <p className="text-xs text-[#999] mt-1.5 leading-relaxed line-clamp-2">
              {item.problemDescription || "No description available."}
            </p>
            <div className="mt-2">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs border border-[#444] text-[#ccc] bg-transparent">
                {urgencyToTag(item.urgency)}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
