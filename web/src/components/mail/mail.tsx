"use client"

import * as React from "react"
import { PanelLeft, Phone, RefreshCw, Search } from "lucide-react"
import type { Call } from "@/types/call"
import { useRealtimeCalls } from "@/hooks/use-realtime-calls"
import { useReadState } from "@/hooks/use-read-state"
import { MailList } from "./mail-list"
import { MailDisplay } from "./mail-display"

interface MailProps {
  initialCalls: Call[]
}

export function Mail({ initialCalls }: MailProps) {
  const [selectedId, setSelectedId] = React.useState<string | null>(
    initialCalls[0]?.id ?? null
  )

  const { readIds, markAsRead } = useReadState()
  const calls = useRealtimeCalls(initialCalls, readIds)
  const selectedCall = calls.find((c) => c.id === selectedId) ?? null

  const handleSelect = (id: string) => {
    setSelectedId(id)
    markAsRead(id)
  }

  return (
    <div className="flex flex-col h-screen bg-[#0f0f0f] text-[#f0f0f0] overflow-hidden">
      <header className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a2a] bg-[#111111]">
        <div className="flex items-center gap-3">
          <button className="p-1 text-[#888] hover:text-[#ccc] transition-colors">
            <PanelLeft width={18} height={18} aria-hidden />
            <span className="sr-only">Toggle sidebar</span>
          </button>
          <div>
            <p className="text-sm font-semibold text-[#f0f0f0] leading-tight">Incoming calls</p>
            <p className="text-xs text-[#888]">The queue is already sorted so you can work top-down.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="inline-flex items-center gap-2 h-8 rounded-md px-3 bg-[#1e1e1e] border border-[#3a3a3a] text-[#f0f0f0] hover:bg-[#2a2a2a] hover:text-white text-sm font-medium transition-colors">
            <Phone width={14} height={14} aria-hidden />
            Calls
          </button>
          <button className="inline-flex items-center gap-2 h-8 rounded-md px-3 bg-[#1e1e1e] border border-[#3a3a3a] text-[#f0f0f0] hover:bg-[#2a2a2a] hover:text-white text-sm font-medium transition-colors">
            <RefreshCw width={14} height={14} aria-hidden />
            Refresh
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-[380px] flex-shrink-0 flex flex-col border-r border-[#2a2a2a] bg-[#131313] overflow-hidden">
          <div className="px-4 pt-5 pb-3">
            <h2 className="text-sm font-semibold text-[#f0f0f0]">Incoming calls</h2>
            <p className="text-xs text-[#888] mt-0.5 leading-relaxed">
              The queue is already sorted so you can work top-down.
            </p>
            <div className="mt-3">
              <p className="text-xs font-semibold text-[#f0f0f0]">Call list</p>
              <p className="text-xs text-[#888]">
                {calls.length} visible of {calls.length} calls
              </p>
            </div>
          </div>
          <div className="px-4 pb-3">
            <div className="relative">
              <Search
                width={14}
                height={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[#666]"
                aria-hidden
              />
              <input
                type="text"
                placeholder="Search caller, issue, summary"
                className="w-full bg-[#1c1c1c] border border-[#2e2e2e] rounded-md pl-8 pr-3 py-2 text-xs text-[#aaa] placeholder:text-[#555] focus:outline-none focus:border-[#444] transition-colors"
              />
            </div>
          </div>
          <MailList items={calls} selected={selectedId} onSelect={handleSelect} />
        </aside>

        <main className="flex-1 overflow-y-auto bg-[#0f0f0f]">
          <MailDisplay call={selectedCall} />
        </main>
      </div>
    </div>
  )
}
