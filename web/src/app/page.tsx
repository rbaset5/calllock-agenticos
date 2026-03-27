import { createServerClient } from "@/lib/supabase-server"
import { transformCallRecord } from "@/lib/transforms"
import { triageSort, assignBucket, followUpSort } from "@/lib/triage"
import { Mail } from "@/components/mail/mail"
import type { Call, CallRecordListRow } from "@/types/call"

export const dynamic = "force-dynamic"

export default async function CallsPage() {
  let calls: Call[] = []

  try {
    const supabase = createServerClient()

    const { data, error } = await supabase
      .from("call_records")
      .select(
        "id, tenant_id, call_id, retell_call_id, phone_number, transcript, extracted_fields, extraction_status, urgency_tier, end_call_reason, callback_scheduled, booking_id, callback_outcome, callback_outcome_at, route, caller_type, primary_intent, revenue_tier, created_at, updated_at"
      )
      .order("created_at", { ascending: false })
      .limit(100)

    if (!error && data) {
      const rows = data as CallRecordListRow[]
      const emptyReadIds = new Set<string>()
      calls = rows.map((row) => transformCallRecord(row, emptyReadIds))
      // Sort by bucket: Action Queue (New Leads + Follow-ups) first, then AI Handled
      const newLeads: typeof calls = []
      const followUps: typeof calls = []
      const aiHandled: typeof calls = []
      for (const c of calls) {
        const a = assignBucket(c)
        if (a.bucket === "ACTION_QUEUE" && a.subGroup === "FOLLOW_UP") followUps.push(c)
        else if (a.bucket === "ACTION_QUEUE") newLeads.push(c)
        else aiHandled.push(c)
      }
      calls = [
        ...triageSort(newLeads),
        ...followUpSort(followUps),
        ...aiHandled.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()),
      ]
    }
  } catch {
    // Supabase unreachable — render empty state
  }

  return <Mail initialCalls={calls} />
}
