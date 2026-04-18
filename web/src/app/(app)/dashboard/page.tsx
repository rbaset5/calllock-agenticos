import { createServerClient } from "@/lib/supabase-server"
import { transformCallRecord } from "@/lib/transforms"
import { DashboardView } from "@/components/dashboard/dashboard-view"
import type { Call, CallRecordListRow } from "@/types/call"

export const dynamic = "force-dynamic"

export default async function DashboardPage() {
  let calls: Call[] = []

  try {
    const supabase = createServerClient()

    const { data, error } = await supabase
      .from("call_records")
      .select(
        "id, tenant_id, call_id, retell_call_id, phone_number, transcript, extracted_fields, extraction_status, urgency_tier, end_call_reason, callback_scheduled, booking_id, created_at, updated_at"
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

  return <DashboardView calls={calls} />
}
