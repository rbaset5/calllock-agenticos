"use client"

import { useEffect } from "react"

export function ReactGrabDev() {
  useEffect(() => {
    import("react-grab")
  }, [])
  return null
}
