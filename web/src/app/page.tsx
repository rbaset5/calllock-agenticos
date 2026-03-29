import { createServerClient } from "@/lib/supabase-server"
import { transformCallRecord } from "@/lib/transforms"
import { orderCallsForMail } from "@/lib/mail-sections"
import { getMailDevFixtures } from "@/components/mail/dev-fixtures"
import { Mail } from "@/components/mail/mail"
import type { Call, CallRecordListRow } from "@/types/call"

export const dynamic = "force-dynamic"

export default async function CallsPage() {
  let calls: Call[] = []

  const fixtureMode =
    process.env.NODE_ENV === "development" &&
    process.env.CALLLOCK_MAIL_FIXTURES === "1"

  if (fixtureMode) {
    calls = orderCallsForMail(getMailDevFixtures())
    return <Mail initialCalls={calls} />
  }

  try {
    const supabase = createServerClient()

    const { data, error } = await supabase
      .from("call_records")
      .select(
        "id, tenant_id, call_id, retell_call_id, phone_number, transcript, extracted_fields, extraction_status, urgency_tier, end_call_reason, callback_scheduled, booking_id, callback_outcome, callback_outcome_at, booking_status, booking_status_at, booking_notes, route, caller_type, primary_intent, revenue_tier, created_at, updated_at"
      )
      .order("created_at", { ascending: false })
      .limit(100)

    if (!error && data) {
      const rows = data as CallRecordListRow[]
      const emptyReadIds = new Set<string>()
      calls = orderCallsForMail(rows.map((row) => transformCallRecord(row, emptyReadIds)))
    }
  } catch {
    // Supabase unreachable — render empty state
  }

  return <Mail initialCalls={calls} />
}
