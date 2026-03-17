"use client"

import { useState, useEffect, useRef } from "react"
import { createBrowserClient } from "@/lib/supabase"
import { transformCallSession } from "@/lib/transforms"
import type { Call, CallSessionRow } from "@/types/call"

export function useRealtimeCalls(
  initialCalls: Call[],
  readIds: Set<string>
) {
  const [calls, setCalls] = useState<Call[]>(initialCalls)
  const readIdsRef = useRef(readIds)
  readIdsRef.current = readIds

  // Sync initialCalls on first render (server → client handoff)
  useEffect(() => {
    setCalls(initialCalls)
  }, [initialCalls])

  // Subscribe to new call_sessions inserts
  useEffect(() => {
    const supabase = createBrowserClient()

    const channel = supabase
      .channel("call_sessions_changes")
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "call_sessions",
        },
        (payload) => {
          const row = payload.new as CallSessionRow
          const call = transformCallSession(row, readIdsRef.current)
          setCalls((prev) => [call, ...prev])
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [])

  // Update read status when readIds changes
  useEffect(() => {
    setCalls((prev) =>
      prev.map((c) => ({ ...c, read: readIds.has(c.id) }))
    )
  }, [readIds])

  return calls
}
