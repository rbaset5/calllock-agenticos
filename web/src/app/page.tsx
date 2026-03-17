import { createServerClient } from "@/lib/supabase"
import { transformCallSession } from "@/lib/transforms"
import { Mail } from "@/components/mail/mail"
import type { Call, CallSessionRow } from "@/types/call"

export const dynamic = "force-dynamic"

export default async function CallsPage() {
  let calls: Call[] = []

  try {
    const supabase = createServerClient()

    // Select only needed columns — retell_data is lazy-loaded on detail view
    const { data, error } = await supabase
      .from("call_sessions")
      .select("call_id, conversation_state, created_at, synced_to_dashboard")
      .order("created_at", { ascending: false })
      .limit(100)

    if (!error && data) {
      const rows = data as CallSessionRow[]
      const emptyReadIds = new Set<string>()
      calls = rows.map((row) => transformCallSession(row, emptyReadIds))
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
