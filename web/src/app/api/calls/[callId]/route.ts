import { NextResponse } from "next/server"

import { createServerClient } from "@/lib/supabase-server"

export const dynamic = "force-dynamic"

export async function GET(
  _request: Request,
  context: { params: Promise<{ callId: string }> }
) {
  const { callId } = await context.params
  const supabase = createServerClient()

  const { data, error } = await supabase
    .from("call_records")
    .select("transcript, raw_retell_payload")
    .eq("call_id", callId)
    .single()

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 404 })
  }

  const transcript = data?.transcript
    ?? (data?.raw_retell_payload as Record<string, unknown> | null)?.transcript
    ?? null

  return NextResponse.json({ transcript })
}
