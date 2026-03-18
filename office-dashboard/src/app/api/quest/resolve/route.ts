import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

type ResolveQuestPayload = {
  quest_id?: string;
  resolution?: string;
  resolved_by?: string;
};

function getSupabaseAdminClient() {
  const url =
    process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceRoleKey) {
    throw new Error(
      "SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) and SUPABASE_SERVICE_ROLE_KEY are required"
    );
  }

  return createClient(url, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}

export async function POST(request: Request) {
  let payload: ResolveQuestPayload;

  try {
    payload = (await request.json()) as ResolveQuestPayload;
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON payload" },
      { status: 400 }
    );
  }

  const questId = payload.quest_id?.trim();
  const resolution = payload.resolution?.trim();
  const resolvedBy = payload.resolved_by?.trim();

  if (!questId || !resolution || !resolvedBy) {
    return NextResponse.json(
      { error: "quest_id, resolution, and resolved_by are required" },
      { status: 400 }
    );
  }

  try {
    const supabase = getSupabaseAdminClient();
    const { data, error } = await supabase
      .from("quest_log")
      .update({
        status: "resolved",
        resolution,
        resolved_by: resolvedBy,
        resolved_at: new Date().toISOString(),
      })
      .eq("id", questId)
      .select("*")
      .single();

    if (error) {
      throw error;
    }

    return NextResponse.json({ quest: data }, { status: 200 });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error ? error.message : "Failed to resolve quest",
      },
      { status: 500 }
    );
  }
}
