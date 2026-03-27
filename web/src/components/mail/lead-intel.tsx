"use client"

import { useState, useEffect, useRef } from "react"
import type { Call } from "@/types/call"
import { formatPhone } from "@/lib/transforms"
import { Map3DWrapper } from "@/components/ui/map-3d-wrapper"

interface LeadIntelProps {
  call: Call | null
}

interface Coords {
  lat: number
  lng: number
}

const HQ_COORDS = { lat: 27.9506, lng: -82.4572 } // Tampa, FL

function haversineDistance(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const R = 3958.8 // Earth radius in miles
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const sinLat = Math.sin(dLat / 2)
  const sinLng = Math.sin(dLng / 2)
  const h = sinLat * sinLat + Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * sinLng * sinLng
  return R * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h))
}

function getSentiment(call: Call): string {
  if (call.isSafetyEmergency || call.urgency === "LifeSafety") return "Frantic / Urgent"
  if (call.urgency === "Urgent") return "Stressed / Concerned"
  if (call.urgency === "Estimate") return "Inquiring"
  return "Calm / Cooperative"
}

export function LeadIntel({ call }: LeadIntelProps) {
  const [coords, setCoords] = useState<Coords | null>(null)

  // Geocode cache to avoid redundant requests
  const geocodeCacheRef = useRef<Map<string, Coords | null>>(new Map())

  useEffect(() => {
    if (!call?.serviceAddress) { setCoords(null); return }
    const address = call.serviceAddress

    // Check cache first
    if (geocodeCacheRef.current.has(address)) {
      setCoords(geocodeCacheRef.current.get(address) ?? null)
      return
    }

    const token = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN
    if (!token) return

    let cancelled = false

    // Debounce: 300ms delay before firing geocode
    const timer = setTimeout(() => {
      const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(address)}.json?access_token=${token}&limit=1`
      fetch(url)
        .then(r => r.json())
        .then(data => {
          if (cancelled) return
          const [lng, lat] = data.features?.[0]?.center ?? []
          const result = lat && lng ? { lat, lng } : null
          geocodeCacheRef.current.set(address, result)
          setCoords(result)
        })
        .catch(() => { if (!cancelled) { setCoords(null) } })
    }, 300)

    return () => { cancelled = true; clearTimeout(timer) }
  }, [call?.serviceAddress])

  if (!call) {
    return (
      <aside className="flex w-[320px] bg-[#131313] flex-col border-l border-[#484848]/20 overflow-y-auto no-scrollbar p-6 shrink-0">
        <p className="text-[#acabaa] text-sm">No call selected</p>
      </aside>
    )
  }

  return (
    <aside className="hidden md:flex w-[320px] bg-[#131313] flex-col border-l border-[#484848]/20 overflow-y-auto no-scrollbar p-6 space-y-8 shrink-0">

      {/* Lead Intelligence section */}
      <div>
        <h3 className="font-headline font-bold text-xs uppercase tracking-widest text-[#acabaa] mb-6">
          Lead Intelligence
        </h3>

        {/* Map View */}
        {call.serviceAddress ? (
          <div className="bg-black rounded-[6px] border border-[#484848]/20 mb-8 overflow-hidden">
            <div className="relative h-36">
              {coords ? (
                <Map3DWrapper lat={coords.lat} lng={coords.lng} className="w-full h-full" />
              ) : (
                <div className="w-full h-full bg-[#0d1a3a] animate-pulse" />
              )}
              <a
                href={`https://maps.google.com/maps?q=${encodeURIComponent(call.serviceAddress)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="absolute bottom-2 right-2 bg-black/80 backdrop-blur-sm border border-[#484848]/20 text-[#e7e5e4] text-[10px] font-bold tracking-wider px-2 py-1 rounded-[6px] uppercase flex items-center gap-1 hover:bg-black transition-colors"
              >
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                  <path d="M2 8L8 2M8 2H4M8 2V6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Open
              </a>
            </div>
            <div className="px-4 py-3">
              <p className="text-[10px] text-[#acabaa] uppercase font-bold tracking-tighter mb-0.5">Distance to Warehouse</p>
              <p className="text-[#e7e5e4] text-xs font-medium leading-tight">
                {coords ? `${Math.round(haversineDistance(coords, HQ_COORDS))} miles` : "Calculating…"}
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-black rounded-[6px] border border-[#484848]/20 mb-8 flex items-center justify-center h-36">
            <p className="text-[#acabaa] text-xs">No address on file</p>
          </div>
        )}

        {/* Entity List */}
        <div className="space-y-6">
          {call.customerName && (
            <div className="space-y-1">
              <p className="text-[10px] text-[#acabaa] uppercase font-bold tracking-tighter">
                Contact Name
              </p>
              <p className="text-[#e7e5e4] font-medium">{call.customerName}</p>
            </div>
          )}

          {call.customerPhone && (
            <div className="space-y-1">
              <p className="text-[10px] text-[#acabaa] uppercase font-bold tracking-tighter">
                Phone Number
              </p>
              <p className="text-[#e7e5e4] font-medium">{formatPhone(call.customerPhone)}</p>
            </div>
          )}

          {call.serviceAddress && (
            <div className="space-y-1">
              <p className="text-[10px] text-[#acabaa] uppercase font-bold tracking-tighter">
                Address
              </p>
              <a
                href={`https://maps.google.com/maps?q=${encodeURIComponent(call.serviceAddress)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-1.5 group"
              >
                <svg className="shrink-0 mt-0.5 text-[#acabaa] group-hover:text-[#e7e5e4] transition-colors" width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M6 1C4.067 1 2.5 2.567 2.5 4.5C2.5 7 6 11 6 11C6 11 9.5 7 9.5 4.5C9.5 2.567 7.933 1 6 1ZM6 5.75C5.31 5.75 4.75 5.19 4.75 4.5C4.75 3.81 5.31 3.25 6 3.25C6.69 3.25 7.25 3.81 7.25 4.5C7.25 5.19 6.69 5.75 6 5.75Z" fill="currentColor"/>
                </svg>
                <span className="text-[#e7e5e4] font-medium leading-tight group-hover:text-white transition-colors">
                  {call.serviceAddress}
                </span>
              </a>
            </div>
          )}

          <div className="space-y-1">
            <p className="text-[10px] text-[#acabaa] uppercase font-bold tracking-tighter">
              Lead Sentiment
            </p>
            <p className="text-[#e7e5e4] font-medium">{getSentiment(call)}</p>
          </div>

          {call.hvacIssueType && (
            <div className="space-y-1">
              <p className="text-[10px] text-[#acabaa] uppercase font-bold tracking-tighter">
                Issue Type
              </p>
              <p className="text-[#e7e5e4] font-medium">{call.hvacIssueType}</p>
            </div>
          )}

          {call.revenueTier && call.revenueTier !== "unknown" && (
            <div className="space-y-1">
              <p className="text-[10px] text-[#acabaa] uppercase font-bold tracking-tighter">
                Estimated Value
              </p>
              <p className="text-[#e7e5e4] font-medium capitalize">
                {call.revenueTier.replace(/_/g, " ")}
              </p>
            </div>
          )}

          {(call.equipmentType || call.equipmentBrand || call.equipmentAge) && (
            <div className="space-y-1">
              <p className="text-[10px] text-[#acabaa] uppercase font-bold tracking-tighter">
                Equipment
              </p>
              <p className="text-[#e7e5e4] font-medium leading-tight">
                {[call.equipmentBrand, call.equipmentType].filter(Boolean).join(" ")}
                {call.equipmentAge && (
                  <span className="text-[#acabaa]"> · {call.equipmentAge}</span>
                )}
              </p>
            </div>
          )}

          {call.callerType && call.callerType !== "unknown" && (
            <div className="space-y-1">
              <p className="text-[10px] text-[#acabaa] uppercase font-bold tracking-tighter">
                Caller Type
              </p>
              <p className="text-[#e7e5e4] font-medium capitalize">
                {call.callerType.replace(/_/g, " ")}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Caller History */}
      <div className="pt-8 border-t border-[#484848]/20">
        <h3 className="font-headline font-bold text-xs uppercase tracking-widest text-[#acabaa] mb-4">
          Caller History
        </h3>
        <div className="space-y-4">
          <div className="bg-[#252626] p-3 rounded-[6px] border border-[#484848]/20">
            <p className="text-xs text-[#e7e5e4] font-bold">
              {call.appointmentBooked ? "Returning Customer" : "New Prospect"}
            </p>
            <p className="text-[10px] text-[#acabaa]">
              {call.appointmentBooked
                ? "Appointment previously scheduled with this number."
                : "No prior records found for this number."}
            </p>
          </div>

          {call.endCallReason && (
            <div className="bg-[#252626] p-3 rounded-[6px] border border-[#484848]/20 border-l-2 border-l-[#c6c6c7]">
              <p className="text-xs text-[#e7e5e4] font-bold">Call Outcome</p>
              <p className="text-[10px] text-[#acabaa] capitalize">
                {call.endCallReason.replace(/_/g, " ")}
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
