"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import {
  CALL_RECORD_LIST_COLUMNS,
  CALLS_PAGE_SIZE,
  mergeCalls,
  trimCallRecordPage,
} from "@/lib/call-records"
import { createBrowserClient } from "@/lib/supabase"
import { transformCallRecord } from "@/lib/transforms"
import type { Call, CallRecordListRow, CallRecordRow } from "@/types/call"

export function useRealtimeCalls(
  initialCalls: Call[],
  readIds: Set<string>,
  initialHasMore: boolean
) {
  const [calls, setCalls] = useState<Call[]>(initialCalls)
  const [hasMore, setHasMore] = useState(initialHasMore)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null)
  const readIdsRef = useRef(readIds)
  readIdsRef.current = readIds

  // Sync initialCalls on first render (server → client handoff)
  useEffect(() => {
    setCalls(initialCalls)
    setHasMore(initialHasMore)
    setLoadMoreError(null)
  }, [initialCalls, initialHasMore])

  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) {
      return
    }

    const cursor = calls.at(-1)?.createdAt
    if (!cursor) {
      setHasMore(false)
      return
    }

    setIsLoadingMore(true)

    try {
      const supabase = createBrowserClient()
      const { data, error } = await supabase
        .from("call_records")
        .select(CALL_RECORD_LIST_COLUMNS)
        .order("created_at", { ascending: false })
        .lt("created_at", cursor)
        .limit(CALLS_PAGE_SIZE + 1)

      if (error) {
        throw error
      }

      const page = trimCallRecordPage((data as CallRecordListRow[]) ?? [])
      const nextCalls = page.rows.map((row) =>
        transformCallRecord(row, readIdsRef.current)
      )

      setCalls((prev) => mergeCalls(prev, nextCalls, "append"))
      setHasMore(page.hasMore)
      setLoadMoreError(null)
    } catch {
      setLoadMoreError("Unable to load older calls. Retry.")
    } finally {
      setIsLoadingMore(false)
    }
  }, [calls, hasMore, isLoadingMore])

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
          setCalls((prev) => mergeCalls(prev, [call], "prepend"))
        }
      )
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "call_records",
        },
        (payload) => {
          const row = payload.new as CallRecordRow
          const updated = transformCallRecord(row, readIdsRef.current)
          setCalls((prev) =>
            prev.map((c) => (c.id === updated.id ? updated : c))
          )
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

  return {
    calls,
    hasMore,
    isLoadingMore,
    loadMore,
    loadMoreError,
  }
}
