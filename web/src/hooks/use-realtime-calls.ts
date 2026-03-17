"use client"

import { useState, useEffect, useRef } from "react"
import { createBrowserClient } from "@/lib/supabase"
import { transformCallRecord } from "@/lib/transforms"
import type { Call, CallRecordRow } from "@/types/call"

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

  // Subscribe to new call_records inserts
  useEffect(() => {
    const supabase = createBrowserClient()

    const channel = supabase
      .channel("call_records_changes")
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "call_records",
        },
        (payload) => {
          const row = payload.new as CallRecordRow
          const call = transformCallRecord(row, readIdsRef.current)
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
