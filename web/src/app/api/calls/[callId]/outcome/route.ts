import { NextResponse } from "next/server"
import { createServerClient } from "@/lib/supabase-server"

const VALID_OUTCOMES = new Set([
  "reached_customer",
  "scheduled",
  "left_voicemail",
  "no_answer",
  "resolved_elsewhere",
])

export async function PATCH(
  request: Request,
  context: { params: Promise<{ callId: string }> }
) {
  const { callId } = await context.params

  let body: { outcome: string }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 })
  }

  if (!body.outcome || !VALID_OUTCOMES.has(body.outcome)) {
    return NextResponse.json(
      { error: `Invalid outcome. Must be one of: ${[...VALID_OUTCOMES].join(", ")}` },
      { status: 400 }
    )
  }

  const supabase = createServerClient()
  const touchedAt = new Date().toISOString()

  const { error } = await supabase
    .from("call_records")
    .update({
      callback_outcome: body.outcome,
      callback_outcome_at: touchedAt,
    })
    .eq("call_id", callId)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json({ ok: true, outcome: body.outcome, touchedAt })
}
