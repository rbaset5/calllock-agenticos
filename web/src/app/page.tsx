import { createServerClient } from "@/lib/supabase"
import {
  CALL_RECORD_LIST_COLUMNS,
  CALLS_PAGE_SIZE,
  trimCallRecordPage,
} from "@/lib/call-records"
import { transformCallRecord } from "@/lib/transforms"
import { Mail } from "@/components/mail/mail"
import type { Call, CallRecordListRow } from "@/types/call"

export const dynamic = "force-dynamic"

export default async function CallsPage() {
  let calls: Call[] = []
  let hasMore = false

  try {
    const supabase = createServerClient()

    const { data, error } = await supabase
      .from("call_records")
      .select(CALL_RECORD_LIST_COLUMNS)
      .order("created_at", { ascending: false })
      .limit(CALLS_PAGE_SIZE + 1)

    if (!error && data) {
      const page = trimCallRecordPage(data as CallRecordListRow[])
      const emptyReadIds = new Set<string>()
      calls = page.rows.map((row) => transformCallRecord(row, emptyReadIds))
      hasMore = page.hasMore
    }
  } catch {
    // Supabase unreachable — render empty state
  }

  return (
    <div className="flex h-full flex-col">
      <Mail initialCalls={calls} initialHasMore={hasMore} />
    </div>
  )
}
