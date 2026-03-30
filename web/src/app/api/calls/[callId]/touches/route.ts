import { NextResponse } from "next/server"

import { createServerClient } from "@/lib/supabase-server"
import type { CallbackTouch } from "@/types/call"

export const dynamic = "force-dynamic"

export async function GET(
  _request: Request,
  context: { params: Promise<{ callId: string }> }
) {
  const { callId } = await context.params
  const supabase = createServerClient()

  const { data, error } = await supabase
    .from("callback_touches")
    .select("id, call_id, outcome, created_at")
    .eq("tenant_id", "00000000-0000-0000-0000-000000000001")
    .eq("call_id", callId)
    .order("created_at", { ascending: false })

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  const touches: CallbackTouch[] = ((data ?? []) as Array<{
    id: string
    call_id: string
    outcome: CallbackTouch["outcome"]
    created_at: string
  }>).map((row) => ({
    id: row.id,
    callId: row.call_id,
    outcome: row.outcome,
    createdAt: row.created_at,
  }))

  return NextResponse.json({ touches })
}
