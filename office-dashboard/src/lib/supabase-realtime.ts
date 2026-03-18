"use client";

import {
  createClient,
  type RealtimeChannel,
  type SupabaseClient,
} from "@supabase/supabase-js";

import {
  type AgentOfficeStateRow,
  type QuestLogEntry,
  useAgentStore,
} from "@/store/agent-store";

let supabaseClient: SupabaseClient | null = null;

function getSupabaseBrowserClient() {
  if (supabaseClient) {
    return supabaseClient;
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    return null;
  }

  supabaseClient = createClient(url, anonKey);
  return supabaseClient;
}

function mapChannelStatus(status: string) {
  const { setConnectionStatus } = useAgentStore.getState();

  if (status === "SUBSCRIBED") {
    setConnectionStatus("connected");
    return;
  }

  if (status === "CHANNEL_ERROR" || status === "TIMED_OUT") {
    setConnectionStatus("reconnecting");
    return;
  }

  if (status === "CLOSED") {
    setConnectionStatus("disconnected");
  }
}

function handleAgentOfficeStateChange(payload: {
  eventType: "INSERT" | "UPDATE" | "DELETE";
  new: AgentOfficeStateRow | null;
  old: Partial<AgentOfficeStateRow> | null;
}) {
  const { upsertAgent, removeAgent } = useAgentStore.getState();

  if (payload.eventType === "DELETE") {
    const agentId = payload.old?.agent_id;
    if (agentId) {
      removeAgent(agentId);
    }
    return;
  }

  if (payload.new) {
    upsertAgent(payload.new);
  }
}

function handleQuestLogChange(payload: {
  eventType: "INSERT" | "UPDATE" | "DELETE";
  new: QuestLogEntry | null;
  old: Partial<QuestLogEntry> | null;
}) {
  const { upsertQuest, removeQuest } = useAgentStore.getState();

  if (payload.eventType === "DELETE") {
    const questId = payload.old?.id;
    if (questId) {
      removeQuest(questId);
    }
    return;
  }

  if (payload.new) {
    upsertQuest(payload.new);
  }
}

export function subscribeToOfficeRealtime() {
  const client = getSupabaseBrowserClient();
  const { setConnectionStatus } = useAgentStore.getState();

  if (!client) {
    setConnectionStatus("disconnected");
    return () => undefined;
  }

  setConnectionStatus("reconnecting");

  const officeChannel = client
    .channel("office-dashboard-realtime")
    .on(
      "postgres_changes",
      {
        event: "*",
        schema: "public",
        table: "agent_office_state",
      },
      (payload) =>
        handleAgentOfficeStateChange({
          eventType: payload.eventType,
          new: payload.new as AgentOfficeStateRow | null,
          old: payload.old as Partial<AgentOfficeStateRow> | null,
        })
    )
    .on(
      "postgres_changes",
      {
        event: "*",
        schema: "public",
        table: "quest_log",
      },
      (payload) =>
        handleQuestLogChange({
          eventType: payload.eventType,
          new: payload.new as QuestLogEntry | null,
          old: payload.old as Partial<QuestLogEntry> | null,
        })
    );

  officeChannel.subscribe((status) => {
    mapChannelStatus(status);
  });

  return () => {
    setConnectionStatus("disconnected");
    void client.removeChannel(officeChannel as RealtimeChannel);
  };
}
