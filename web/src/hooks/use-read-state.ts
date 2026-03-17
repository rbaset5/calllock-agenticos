"use client"

import { useState, useCallback, useEffect } from "react"

const STORAGE_KEY = "calllock-read-calls"

function loadReadIds(): Set<string> {
  if (typeof window === "undefined") return new Set()
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return new Set(stored ? JSON.parse(stored) : [])
  } catch {
    return new Set()
  }
}

export function useReadState() {
  const [readIds, setReadIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    setReadIds(loadReadIds())
  }, [])

  const markAsRead = useCallback((id: string) => {
    setReadIds((prev) => {
      const next = new Set(prev)
      next.add(id)
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]))
      } catch {
        // localStorage full or unavailable — read state is best-effort
      }
      return next
    })
  }, [])

  return { readIds, markAsRead }
}
