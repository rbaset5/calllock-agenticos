import { NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase-server"

const VALID_STATUSES = new Set(["confirmed", "rescheduled", "cancelled"])

export async function PATCH(
  request: Request,
  context: { params: Promise<{ callId: string }> }
) {
  const { callId } = await context.params

  let body: { status: string; appointmentDateTime?: string; notes?: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 })
  }

  if (!body.status || !VALID_STATUSES.has(body.status)) {
    return NextResponse.json(
      { error: `Invalid status. Must be one of: ${[...VALID_STATUSES].join(", ")}` },
      { status: 400 }
    )
  }

  if (body.status === "rescheduled" && !body.appointmentDateTime) {
    return NextResponse.json(
      { error: "appointmentDateTime is required when status is rescheduled" },
      { status: 400 }
    )
  }

  const supabase = createServerClient()
  const touchedAt = new Date().toISOString()
  const notes = body.notes as string | undefined

  const { error } = await supabase
    .from("call_records")
    .update({
      booking_status: body.status,
      booking_status_at: touchedAt,
      booking_notes: notes ?? null,
    })
    .eq("call_id", callId)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  if (body.status === "rescheduled" && body.appointmentDateTime) {
    const { error: rpcError } = await supabase.rpc("update_extracted_field", {
      p_call_id: callId,
      p_key: "appointment_datetime",
      p_value: body.appointmentDateTime,
    })

    if (rpcError) {
      return NextResponse.json({ error: rpcError.message }, { status: 500 })
    }
  }

  return NextResponse.json({ ok: true, status: body.status, touchedAt })
}
