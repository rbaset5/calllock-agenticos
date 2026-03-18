import { createServerClient } from "@/lib/supabase"
import { transformCallRecord } from "@/lib/transforms"
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
        "id, tenant_id, call_id, retell_call_id, phone_number, extracted_fields, extraction_status, urgency_tier, end_call_reason, callback_scheduled, booking_id, created_at, updated_at"
      )
      .order("created_at", { ascending: false })
      .limit(100)

    if (!error && data) {
      const rows = data as CallRecordListRow[]
      const emptyReadIds = new Set<string>()
      calls = rows.map((row) => transformCallRecord(row, emptyReadIds))
    }
  } catch {
    // Supabase unreachable — render empty state
  }

  return (
    <div className="flex h-full flex-col">
      <Mail initialCalls={calls} />
    </div>
  )
}
